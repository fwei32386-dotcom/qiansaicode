from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.interfaces import Detection, RiskEvent
from safety_brain.ppe_association import PersonPPE, associate_ppe
from safety_brain.scene_graph import SceneGraph


@dataclass(frozen=True)
class Rule:
    rule_id: str
    name: str
    priority: int
    event_type: str
    object_name: str
    zone: str
    missing_ppe: list[str]
    score: int
    level: str
    actions: dict[str, Any]


SCENE_POLICIES: dict[str, dict[str, Any]] = {
    "construction": {
        "required_ppe": ["helmet", "vest"],
        "rules": [
            Rule(
                rule_id="SCENE_CONSTRUCTION_HELMET",
                name="工地人员缺少安全帽",
                priority=100,
                event_type="ppe_violation",
                object_name="person",
                zone="*",
                missing_ppe=["helmet"],
                score=82,
                level="high",
                actions={
                    "voice": "工地人员缺少安全帽，请立即佩戴。",
                    "led": "red",
                    "buzzer": True,
                    "snapshot": True,
                    "log": True,
                },
            ),
            Rule(
                rule_id="SCENE_CONSTRUCTION_VEST",
                name="工地人员缺少反光背心",
                priority=80,
                event_type="ppe_violation",
                object_name="person",
                zone="*",
                missing_ppe=["vest"],
                score=65,
                level="warning",
                actions={
                    "voice": "工地人员缺少反光背心，请立即穿戴。",
                    "led": "yellow",
                    "buzzer": False,
                    "snapshot": True,
                    "log": True,
                },
            ),
        ],
    },
    "lab": {
        "required_ppe": ["goggles", "gloves"],
        "rules": [
            Rule(
                rule_id="SCENE_LAB_GOGGLES",
                name="实验室人员缺少护目镜",
                priority=90,
                event_type="ppe_violation",
                object_name="person",
                zone="*",
                missing_ppe=["goggles"],
                score=78,
                level="high",
                actions={
                    "voice": "实验室人员缺少护目镜，请佩戴眼部防护。",
                    "led": "red",
                    "buzzer": True,
                    "snapshot": True,
                    "log": True,
                },
            ),
            Rule(
                rule_id="SCENE_LAB_GLOVES",
                name="实验室人员缺少防护手套",
                priority=70,
                event_type="ppe_violation",
                object_name="person",
                zone="*",
                missing_ppe=["gloves"],
                score=62,
                level="warning",
                actions={
                    "voice": "实验室人员缺少防护手套，请立即佩戴。",
                    "led": "yellow",
                    "buzzer": False,
                    "snapshot": True,
                    "log": True,
                },
            ),
        ],
    },
}


class RuleDslEngine:
    def __init__(self, scene_graph: SceneGraph, rules: list[Rule], scene_mode: str | None = None) -> None:
        self.scene_graph = scene_graph
        self.rules = rules
        self.scene_mode = scene_mode
        self._event_index = 0

    @classmethod
    def from_files(
        cls,
        semantic_map_path: str | Path = "configs/semantic_map.json",
        rule_dsl_path: str | Path = "configs/rule_dsl.json",
        scene_mode: str | None = None,
    ) -> "RuleDslEngine":
        return cls(
            scene_graph=SceneGraph.from_json(semantic_map_path),
            rules=_load_rules(rule_dsl_path),
            scene_mode=scene_mode,
        )

    def evaluate(self, detections: list[Detection]) -> list[RiskEvent]:
        events: list[RiskEvent] = []
        for person_ppe in associate_ppe(detections):
            zone = self.scene_graph.find_zone(person_ppe.person.center)
            if not zone:
                continue
            if self.scene_mode in SCENE_POLICIES:
                scene_event = self._evaluate_scene_policy(person_ppe, zone.zone_id)
                if scene_event:
                    events.append(scene_event)
                continue
            matches: list[Rule] = []
            for rule in self.rules:
                if self._matches(rule, person_ppe, zone.zone_id):
                    matches.append(rule)
            if matches:
                matches.sort(key=lambda item: item.priority, reverse=True)
                events.append(self._make_event(matches[0], person_ppe, zone.zone_id, matches[1:]))
        return events

    def _matches(self, rule: Rule, person_ppe: PersonPPE, zone_id: str) -> bool:
        if rule.object_name != "person":
            return False
        if rule.zone != zone_id:
            return False
        return all(item in person_ppe.missing_ppe for item in rule.missing_ppe)

    def _evaluate_scene_policy(self, person_ppe: PersonPPE, zone_id: str) -> RiskEvent | None:
        policy = SCENE_POLICIES[str(self.scene_mode)]
        missing = [item for item in policy["required_ppe"] if item in person_ppe.missing_ppe]
        if not missing:
            return None
        for rule in policy["rules"]:
            if rule.missing_ppe[0] in missing:
                return self._make_scene_event(rule, person_ppe, zone_id, missing)
        return None

    def _make_scene_event(
        self,
        rule: Rule,
        person_ppe: PersonPPE,
        zone_id: str,
        scene_missing_ppe: list[str],
    ) -> RiskEvent:
        self._event_index += 1
        reasons = [
            f"rule {rule.rule_id}: {rule.name}",
            f"scene_mode={self.scene_mode}",
            f"zone={zone_id}",
            f"missing_ppe={', '.join(scene_missing_ppe)}",
        ]
        return RiskEvent(
            event_id=f"D{int(time.time())}_{self._event_index:04d}",
            frame_id=person_ppe.person.frame_id,
            source_type=person_ppe.person.source_type,
            event_type=rule.event_type,  # type: ignore[arg-type]
            risk_score=rule.score,
            risk_level=rule.level,  # type: ignore[arg-type]
            reasons=reasons,
            bbox=person_ppe.person.bbox,
            need_alarm=True,
            need_snapshot=True,
            need_log=True,
            timestamp=time.time(),
            rule_id=rule.rule_id,
            action_hint=rule.actions,
        )

    def _make_event(
        self,
        rule: Rule,
        person_ppe: PersonPPE,
        zone_id: str,
        suppressed_rules: list[Rule],
    ) -> RiskEvent:
        self._event_index += 1
        missing = ", ".join(person_ppe.missing_ppe) if person_ppe.missing_ppe else "none"
        reasons = [
            f"rule {rule.rule_id}: {rule.name}",
            f"zone={zone_id}",
            f"missing_ppe={missing}",
        ]
        if suppressed_rules:
            reasons.append(
                "suppressed_rules="
                + ",".join(f"{item.rule_id}:{item.name}" for item in suppressed_rules)
            )
        return RiskEvent(
            event_id=f"D{int(time.time())}_{self._event_index:04d}",
            frame_id=person_ppe.person.frame_id,
            source_type=person_ppe.person.source_type,
            event_type=rule.event_type,  # type: ignore[arg-type]
            risk_score=rule.score,
            risk_level=rule.level,  # type: ignore[arg-type]
            reasons=reasons,
            bbox=person_ppe.person.bbox,
            need_alarm=True,
            need_snapshot=True,
            need_log=True,
            timestamp=time.time(),
            rule_id=rule.rule_id,
            action_hint=rule.actions,
        )


def _load_rules(path: str | Path) -> list[Rule]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rules: list[Rule] = []
    for item in payload.get("rules", []):
        risk = item.get("risk", {})
        rules.append(
            Rule(
                rule_id=str(item["id"]),
                name=str(item["name"]),
                priority=int(item.get("priority", 0)),
                event_type=str(item["event_type"]),
                object_name=str(item["object"]),
                zone=str(item["zone"]),
                missing_ppe=[str(v) for v in item.get("missing_ppe", [])],
                score=int(risk["score"]),
                level=str(risk["level"]),
                actions=dict(item.get("actions", {})),
            )
        )
    return rules

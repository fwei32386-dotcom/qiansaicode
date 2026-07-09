from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from actuator.alarm_manager import AlarmManager
from evidence.event_logger import EventLogger
from runtime.interfaces import AlarmAction, RiskEvent
from runtime.timeline_loader import DetectionFrame
from safety_brain.event_state_machine import EventStateMachine, TimelineStage
from safety_brain.ppe_temporal import PpeTemporalConfirmation, PpeTemporalDecision
from safety_brain.rule_dsl_engine import RuleDslEngine
from safety_brain.smoke_fire_temporal import SmokeFireTemporal, TemporalDecision
from dashboard.scene_mode import build_scene_mode_state, DEFAULT_SCENE_MODE


@dataclass
class ReplayResult:
    events: list[RiskEvent] = field(default_factory=list)
    actions: list[AlarmAction] = field(default_factory=list)
    timeline: list[TimelineStage] = field(default_factory=list)


class ReplayRunner:
    def __init__(self, events_dir: str | Path = "data/events", scene_mode_path: str | Path = DEFAULT_SCENE_MODE) -> None:
        self.temporal = SmokeFireTemporal()
        self.ppe_temporal = PpeTemporalConfirmation()
        self.state_machine = EventStateMachine()
        self.ppe_state_machine = EventStateMachine()
        scene_mode = build_scene_mode_state(scene_mode_path)["scene_mode"]["mode"]
        self.rule_engine = RuleDslEngine.from_files(scene_mode=scene_mode)
        self.alarm_manager = AlarmManager()
        self.logger = EventLogger(events_dir)
        self._event_index = 0

    def run(self, frames: list[DetectionFrame]) -> ReplayResult:
        result = ReplayResult()
        for frame in frames:
            ppe_decisions = self.ppe_temporal.update(self.rule_engine.evaluate(frame.detections))
            for decision in ppe_decisions:
                stage = self._update_ppe_state(decision, frame)
                if not stage:
                    continue
                result.timeline.append(stage)
                if stage.should_alarm and decision.event:
                    event = self._make_ppe_event(decision)
                    action = self.alarm_manager.build_action(event)
                    self.logger.log_event(event.to_dict())
                    self.logger.log_action(action.to_dict())
                    result.events.append(event)
                    result.actions.append(action)

            decisions = self.temporal.update(frame.detections)
            for decision in decisions:
                stage = self._update_state(decision, frame)
                if not stage:
                    continue
                result.timeline.append(stage)
                if stage.should_alarm and decision.detection:
                    event = self._make_event(decision, frame)
                    action = self.alarm_manager.build_action(event)
                    self.logger.log_event(event.to_dict())
                    self.logger.log_action(action.to_dict())
                    result.events.append(event)
                    result.actions.append(action)
        return result

    def write_csv_report(self, result: ReplayResult, output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["event_key", "stage", "frame_id", "timestamp", "detail", "should_alarm"],
            )
            writer.writeheader()
            for item in result.timeline:
                writer.writerow(
                    {
                        "event_key": item.event_key,
                        "stage": item.stage,
                        "frame_id": item.frame_id,
                        "timestamp": item.timestamp,
                        "detail": item.detail,
                        "should_alarm": item.should_alarm,
                    }
                )
        return path

    def write_timeline_json(self, result: ReplayResult, output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timeline": [
                {
                    "event_key": item.event_key,
                    "stage": item.stage,
                    "frame_id": item.frame_id,
                    "timestamp": item.timestamp,
                    "detail": item.detail,
                    "should_alarm": item.should_alarm,
                }
                for item in result.timeline
            ],
            "summary": {
                "timeline_stages": len(result.timeline),
                "events": len(result.events),
                "actions": len(result.actions),
            },
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _update_state(self, decision: TemporalDecision, frame: DetectionFrame) -> TimelineStage | None:
        return self.state_machine.update(
            event_key=decision.class_name,
            observed_state=decision.state,
            frame_id=frame.frame_id,
            timestamp=frame.timestamp,
        )

    def _update_ppe_state(self, decision: PpeTemporalDecision, frame: DetectionFrame) -> TimelineStage | None:
        return self.ppe_state_machine.update(
            event_key=decision.event_key,
            observed_state=decision.state,
            frame_id=frame.frame_id,
            timestamp=frame.timestamp,
        )

    @staticmethod
    def _make_ppe_event(decision: PpeTemporalDecision) -> RiskEvent:
        if not decision.event:
            raise ValueError("confirmed PPE decision must carry a risk event")
        return RiskEvent(
            event_id=decision.event.event_id,
            frame_id=decision.event.frame_id,
            source_type=decision.event.source_type,
            event_type=decision.event.event_type,
            risk_score=decision.event.risk_score,
            risk_level=decision.event.risk_level,
            reasons=[*decision.event.reasons, *decision.reasons],
            bbox=decision.event.bbox,
            need_alarm=decision.event.need_alarm,
            need_snapshot=decision.event.need_snapshot,
            need_log=decision.event.need_log,
            timestamp=decision.event.timestamp,
            rule_id=decision.event.rule_id,
            action_hint=decision.event.action_hint,
        )

    def _make_event(self, decision: TemporalDecision, frame: DetectionFrame) -> RiskEvent:
        if not decision.detection:
            raise ValueError("confirmed temporal decision must carry a detection")
        self._event_index += 1
        is_fire = decision.class_name == "fire"
        return RiskEvent(
            event_id=f"R{int(time.time())}_{self._event_index:04d}",
            frame_id=frame.frame_id,
            source_type=decision.detection.source_type,
            event_type=decision.class_name,  # type: ignore[arg-type]
            risk_score=90 if is_fire else 80,
            risk_level="emergency" if is_fire else "high",
            reasons=decision.reasons,
            bbox=decision.detection.bbox,
            need_alarm=True,
            need_snapshot=True,
            need_log=True,
            timestamp=time.time(),
        )

from __future__ import annotations

import time

from runtime.interfaces import Detection, RiskEvent


class SimpleRuleEngine:
    """Minimal rule engine for the first project milestone."""

    def __init__(self) -> None:
        self._event_index = 0

    def evaluate(self, detections: list[Detection]) -> list[RiskEvent]:
        events: list[RiskEvent] = []
        persons = [d for d in detections if d.class_name == "person"]
        helmets = [d for d in detections if d.class_name == "helmet"]
        vests = [d for d in detections if d.class_name == "vest"]
        goggles = [d for d in detections if d.class_name == "goggles"]
        gloves = [d for d in detections if d.class_name == "gloves"]
        smoke_or_fire = [d for d in detections if d.class_name in ("smoke", "fire")]

        for person in persons:
            reasons: list[str] = []
            if not self._has_related_object(person, helmets):
                reasons.append("helmet missing")
            if not self._has_related_object(person, vests):
                reasons.append("vest missing")
            if not self._has_related_object(person, goggles):
                reasons.append("goggles missing")
            if not self._has_related_object(person, gloves):
                reasons.append("gloves missing")

            if reasons:
                high_risk = any(reason in reasons for reason in ("helmet missing", "goggles missing"))
                events.append(
                    self._make_event(
                        detection=person,
                        event_type="ppe_violation",
                        risk_score=72 if high_risk else 55,
                        risk_level="high" if high_risk else "warning",
                        reasons=reasons,
                    )
                )

        for detection in smoke_or_fire:
            is_fire = detection.class_name == "fire"
            events.append(
                self._make_event(
                    detection=detection,
                    event_type=detection.class_name,
                    risk_score=90 if is_fire else 80,
                    risk_level="emergency" if is_fire else "high",
                    reasons=[f"{detection.class_name} detected by vision model"],
                )
            )

        return events

    def _make_event(
        self,
        detection: Detection,
        event_type: str,
        risk_score: int,
        risk_level: str,
        reasons: list[str],
    ) -> RiskEvent:
        self._event_index += 1
        return RiskEvent(
            event_id=f"E{int(time.time())}_{self._event_index:04d}",
            frame_id=detection.frame_id,
            source_type=detection.source_type,
            event_type=event_type,  # type: ignore[arg-type]
            risk_score=risk_score,
            risk_level=risk_level,  # type: ignore[arg-type]
            reasons=reasons,
            bbox=detection.bbox,
            need_alarm=True,
            need_snapshot=True,
            need_log=True,
            timestamp=time.time(),
        )

    @staticmethod
    def _has_related_object(person: Detection, objects: list[Detection]) -> bool:
        px1, py1, px2, py2 = person.bbox
        for obj in objects:
            cx, cy = obj.center
            if px1 <= cx <= px2 and py1 <= cy <= py2:
                return True
        return False

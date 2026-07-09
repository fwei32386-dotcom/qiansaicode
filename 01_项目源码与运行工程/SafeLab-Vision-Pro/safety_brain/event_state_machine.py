from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TimelineStage:
    event_key: str
    stage: str
    frame_id: int
    timestamp: float
    detail: str
    should_alarm: bool = False


@dataclass
class EventStateMachine:
    states: dict[str, str] = field(default_factory=dict)

    def update(self, event_key: str, observed_state: str, frame_id: int, timestamp: float) -> TimelineStage | None:
        previous = self.states.get(event_key, "normal")

        if observed_state == "suspicious" and previous == "normal":
            self.states[event_key] = "suspicious"
            return TimelineStage(event_key, "suspicious", frame_id, timestamp, f"{event_key} became suspicious")

        if observed_state == "confirmed" and previous in ("normal", "suspicious"):
            self.states[event_key] = "alarmed"
            return TimelineStage(
                event_key,
                "alarmed",
                frame_id,
                timestamp,
                f"{event_key} confirmed and alarmed",
                should_alarm=True,
            )

        if observed_state == "confirmed" and previous == "alarmed":
            return None

        if observed_state == "recovered" and previous == "alarmed":
            self.states[event_key] = "closed"
            return TimelineStage(event_key, "closed", frame_id, timestamp, f"{event_key} recovered and closed")

        return None


from __future__ import annotations

from dataclasses import dataclass, field

from runtime.interfaces import RiskEvent


@dataclass
class PpeTemporalDecision:
    event_key: str
    state: str
    event: RiskEvent | None
    appear_count: int
    miss_count: int
    reasons: list[str] = field(default_factory=list)


class PpeTemporalConfirmation:
    def __init__(self, confirm_frames: int = 3, recover_frames: int = 2) -> None:
        self.confirm_frames = confirm_frames
        self.recover_frames = recover_frames
        self._appear_count: dict[str, int] = {}
        self._miss_count: dict[str, int] = {}
        self._confirmed: dict[str, bool] = {}

    def update(self, events: list[RiskEvent]) -> list[PpeTemporalDecision]:
        observed = {self._event_key(event): event for event in events if event.event_type == "ppe_violation"}
        known_keys = set(self._appear_count) | set(observed)
        decisions: list[PpeTemporalDecision] = []

        for key in sorted(known_keys):
            event = observed.get(key)
            if event:
                self._appear_count[key] = self._appear_count.get(key, 0) + 1
                self._miss_count[key] = 0
                if self._appear_count[key] >= self.confirm_frames:
                    self._confirmed[key] = True
                    decisions.append(
                        PpeTemporalDecision(
                            event_key=key,
                            state="confirmed",
                            event=event,
                            appear_count=self._appear_count[key],
                            miss_count=0,
                            reasons=[f"{key} appeared for {self._appear_count[key]} consecutive frames"],
                        )
                    )
                else:
                    decisions.append(
                        PpeTemporalDecision(
                            event_key=key,
                            state="suspicious",
                            event=event,
                            appear_count=self._appear_count[key],
                            miss_count=0,
                            reasons=[f"{key} needs {self.confirm_frames} frames to confirm"],
                        )
                    )
            else:
                self._miss_count[key] = self._miss_count.get(key, 0) + 1
                if self._confirmed.get(key, False) and self._miss_count[key] >= self.recover_frames:
                    decisions.append(
                        PpeTemporalDecision(
                            event_key=key,
                            state="recovered",
                            event=None,
                            appear_count=self._appear_count.get(key, 0),
                            miss_count=self._miss_count[key],
                            reasons=[f"{key} disappeared for {self._miss_count[key]} frames"],
                        )
                    )
                    self._confirmed[key] = False
                    self._appear_count[key] = 0
                    self._miss_count[key] = 0
                elif self._appear_count.get(key, 0) > 0:
                    self._appear_count[key] = 0

        return decisions

    @staticmethod
    def _event_key(event: RiskEvent) -> str:
        x1, y1, x2, y2 = event.bbox
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        # PPE boxes jitter frame-to-frame; coarse center cells keep one person stable
        # long enough for temporal confirmation without merging distant people.
        cell_size = 320
        return f"{event.rule_id or event.event_type}:{event.source_type}:{center_x // cell_size},{center_y // cell_size}"

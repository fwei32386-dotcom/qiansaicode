from __future__ import annotations

from dataclasses import dataclass, field

from runtime.interfaces import Detection


@dataclass
class TemporalDecision:
    class_name: str
    state: str
    detection: Detection | None
    appear_count: int
    miss_count: int
    reasons: list[str] = field(default_factory=list)


class SmokeFireTemporal:
    def __init__(self, confirm_frames: int = 3, recover_frames: int = 2) -> None:
        self.confirm_frames = confirm_frames
        self.recover_frames = recover_frames
        self._appear_count = {"smoke": 0, "fire": 0}
        self._miss_count = {"smoke": 0, "fire": 0}
        self._confirmed = {"smoke": False, "fire": False}

    def update(self, detections: list[Detection]) -> list[TemporalDecision]:
        decisions: list[TemporalDecision] = []
        for class_name in ("smoke", "fire"):
            candidates = [d for d in detections if d.class_name == class_name]
            detection = max(candidates, key=lambda d: d.confidence, default=None)

            if detection:
                self._appear_count[class_name] += 1
                self._miss_count[class_name] = 0
                if self._appear_count[class_name] >= self.confirm_frames:
                    self._confirmed[class_name] = True
                    decisions.append(
                        TemporalDecision(
                            class_name=class_name,
                            state="confirmed",
                            detection=detection,
                            appear_count=self._appear_count[class_name],
                            miss_count=0,
                            reasons=[
                                f"{class_name} appeared for {self._appear_count[class_name]} consecutive frames"
                            ],
                        )
                    )
                else:
                    decisions.append(
                        TemporalDecision(
                            class_name=class_name,
                            state="suspicious",
                            detection=detection,
                            appear_count=self._appear_count[class_name],
                            miss_count=0,
                            reasons=[
                                f"{class_name} needs {self.confirm_frames} frames to confirm"
                            ],
                        )
                    )
            else:
                self._miss_count[class_name] += 1
                if self._confirmed[class_name] and self._miss_count[class_name] >= self.recover_frames:
                    decisions.append(
                        TemporalDecision(
                            class_name=class_name,
                            state="recovered",
                            detection=None,
                            appear_count=self._appear_count[class_name],
                            miss_count=self._miss_count[class_name],
                            reasons=[f"{class_name} disappeared for {self._miss_count[class_name]} frames"],
                        )
                    )
                    self._confirmed[class_name] = False
                    self._appear_count[class_name] = 0
                    self._miss_count[class_name] = 0
                elif self._appear_count[class_name] > 0:
                    self._appear_count[class_name] = 0

        return decisions


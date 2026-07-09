from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from runtime.interfaces import VideoFrame


RuntimeState = Literal["normal", "suspicious", "alarmed"]
InferenceMode = Literal["full_frame", "roi"]


@dataclass(frozen=True)
class SchedulerDecision:
    should_process: bool
    mode: InferenceMode
    reason: str
    frame_id: int
    runtime_state: RuntimeState


@dataclass
class FrameScheduler:
    normal_interval: int = 5
    suspicious_interval: int = 1
    alarmed_interval: int = 2

    def decide(
        self,
        frame: VideoFrame,
        runtime_state: RuntimeState = "normal",
        has_roi: bool = False,
    ) -> SchedulerDecision:
        interval = self._interval_for(runtime_state)
        should_process = frame.frame_id == 1 or frame.frame_id % interval == 0
        mode: InferenceMode = "roi" if has_roi and runtime_state in ("suspicious", "alarmed") else "full_frame"
        if should_process:
            reason = f"{runtime_state} state uses every {interval} frame(s)"
        else:
            reason = f"skip frame to keep latest-only latency; interval={interval}"
        return SchedulerDecision(
            should_process=should_process,
            mode=mode,
            reason=reason,
            frame_id=frame.frame_id,
            runtime_state=runtime_state,
        )

    def _interval_for(self, runtime_state: RuntimeState) -> int:
        if runtime_state == "suspicious":
            return max(self.suspicious_interval, 1)
        if runtime_state == "alarmed":
            return max(self.alarmed_interval, 1)
        return max(self.normal_interval, 1)

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from runtime.interfaces import VideoFrame


@dataclass
class LatestFrameBuffer:
    """Keep only the newest frame to avoid cumulative latency."""

    _frame: VideoFrame | None = None
    _dropped_count: int = 0

    def __post_init__(self) -> None:
        self._lock = Lock()

    def put(self, frame: VideoFrame) -> None:
        with self._lock:
            if self._frame is not None:
                self._dropped_count += 1
            self._frame = frame

    def get_latest(self) -> VideoFrame | None:
        with self._lock:
            return self._frame

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped_count

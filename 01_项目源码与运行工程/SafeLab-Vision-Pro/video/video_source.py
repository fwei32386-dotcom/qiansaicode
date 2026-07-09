from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from runtime.interfaces import SourceType, VideoFrame


@dataclass(frozen=True)
class VideoSourceConfig:
    source_type: SourceType
    source_name: str
    width: int
    height: int
    device: str | None = None
    path: str | None = None
    fps: int | None = None


class VideoSource(ABC):
    def __init__(self, config: VideoSourceConfig) -> None:
        self.config = config
        self._frame_id = 0

    @abstractmethod
    def read(self) -> VideoFrame | None:
        """Return the next frame, or None when the source is exhausted/unavailable."""

    def close(self) -> None:
        """Release source resources."""

    def _make_frame(self, frame: Any | None = None) -> VideoFrame:
        self._frame_id += 1
        return VideoFrame(
            frame_id=self._frame_id,
            source_type=self.config.source_type,
            timestamp=time.time(),
            width=self.config.width,
            height=self.config.height,
            source_name=self.config.source_name,
            frame=frame,
        )


class MockVideoSource(VideoSource):
    def __init__(self, config: VideoSourceConfig, frame_count: int = 1) -> None:
        super().__init__(config)
        self.frame_count = frame_count

    def read(self) -> VideoFrame | None:
        if self._frame_id >= self.frame_count:
            return None
        return self._make_frame(frame=None)

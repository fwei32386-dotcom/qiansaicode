from __future__ import annotations

from pathlib import Path

from runtime.interfaces import VideoFrame
from video.video_source import VideoSource, VideoSourceConfig


class ImageFileSource(VideoSource):
    """Read one local image as a single video frame for the detector pipeline."""

    def __init__(self, config: VideoSourceConfig) -> None:
        super().__init__(config)
        if not config.path:
            raise ValueError("image file source requires a path")
        if not Path(config.path).exists():
            raise FileNotFoundError(config.path)
        import cv2  # type: ignore[import-not-found]

        frame = cv2.imread(config.path)
        if frame is None:
            raise RuntimeError(f"failed to open image file: {config.path}")
        height, width = frame.shape[:2]
        self.config = VideoSourceConfig(
            source_type=config.source_type,
            source_name=config.source_name,
            width=int(width),
            height=int(height),
            device=config.device,
            path=config.path,
            fps=config.fps,
        )
        self._frame = frame
        self._used = False

    def read(self) -> VideoFrame | None:
        if self._used:
            return None
        self._used = True
        return self._make_frame(frame=self._frame)

from __future__ import annotations

import time

from runtime.interfaces import VideoFrame
from video.video_source import VideoSource, VideoSourceConfig


class CameraSource(VideoSource):
    """OpenCV-backed V4L2 camera source."""

    def __init__(self, config: VideoSourceConfig) -> None:
        super().__init__(config)
        if not config.device:
            raise ValueError("camera source requires a device")
        import cv2  # type: ignore[import-not-found]

        self._cv2 = cv2
        self._capture = cv2.VideoCapture(config.device)
        if config.width:
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
        if config.height:
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)
        if config.fps:
            self._capture.set(cv2.CAP_PROP_FPS, config.fps)
        if not self._capture.isOpened():
            raise RuntimeError(f"failed to open camera device: {config.device}")

    def read(self) -> VideoFrame | None:
        ok, frame = self._capture.read()
        if not ok:
            return None
        height, width = frame.shape[:2]
        self._frame_id += 1
        return VideoFrame(
            frame_id=self._frame_id,
            source_type=self.config.source_type,
            timestamp=time.time(),
            width=int(width),
            height=int(height),
            source_name=self.config.source_name,
            frame=frame,
        )

    def close(self) -> None:
        self._capture.release()

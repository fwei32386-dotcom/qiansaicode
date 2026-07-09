from __future__ import annotations

from pathlib import Path

from runtime.interfaces import VideoFrame
from video.image_file_source import ImageFileSource
from video.video_source import VideoSource, VideoSourceConfig


IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".ppm", ".webp"}


class FileVideoSource(VideoSource):
    """OpenCV-backed video file source.

    OpenCV is imported lazily so board environments without Python/OpenCV can
    still run config and shell checks.
    """

    def __init__(self, config: VideoSourceConfig) -> None:
        super().__init__(config)
        if not config.path:
            raise ValueError("file video source requires a path")
        path = Path(config.path)
        if not path.exists():
            raise FileNotFoundError(config.path)
        self._image_source: ImageFileSource | None = None
        if path.suffix.lower() in IMAGE_SUFFIXES:
            self._image_source = ImageFileSource(config)
            self.config = self._image_source.config
            self._capture = None
            return
        import cv2  # type: ignore[import-not-found]

        self._cv2 = cv2
        self._capture = cv2.VideoCapture(config.path)
        if not self._capture.isOpened():
            raise RuntimeError(f"failed to open video file: {config.path}")

    def read(self) -> VideoFrame | None:
        if self._image_source is not None:
            return self._image_source.read()
        assert self._capture is not None
        ok, frame = self._capture.read()
        if not ok:
            return None
        height, width = frame.shape[:2]
        if width != self.config.width or height != self.config.height:
            self.config = VideoSourceConfig(
                source_type=self.config.source_type,
                source_name=self.config.source_name,
                width=int(width),
                height=int(height),
                device=self.config.device,
                path=self.config.path,
                fps=self.config.fps,
            )
        return self._make_frame(frame=frame)

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()

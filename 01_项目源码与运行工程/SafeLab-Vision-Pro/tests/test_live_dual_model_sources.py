from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dashboard.input_source import save_input_source
from tools.live_dual_model_sources import build_active_frame_source


class LiveDualModelSourcesTest(unittest.TestCase):
    def test_camera_source_uses_camera_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_video_config(root)
            runtime = root / "runtime" / "input_source.json"
            save_input_source("camera_ov13855", config, runtime)

            source = build_active_frame_source(
                video_config_path=config,
                input_source_path=runtime,
                camera_frame_url="http://camera/frame.jpg",
                camera_status_url="http://camera/status",
            )

        self.assertEqual(source.key, "camera_ov13855")
        self.assertEqual(source.source_type, "camera")
        self.assertEqual(source.frame_url, "http://camera/frame.jpg")
        self.assertEqual(source.status_url, "http://camera/status")

    def test_file_source_resolves_path_relative_to_video_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video_path = root / "video" / "demo.mp4"
            video_path.parent.mkdir(parents=True)
            video_path.write_bytes(b"placeholder")
            config = _write_video_config(root)
            runtime = root / "runtime" / "input_source.json"
            save_input_source("file_demo", config, runtime)

            source = build_active_frame_source(
                video_config_path=config,
                input_source_path=runtime,
                camera_frame_url="http://camera/frame.jpg",
                camera_status_url="http://camera/status",
            )

        self.assertEqual(source.key, "file_demo")
        self.assertEqual(source.source_type, "file")
        self.assertEqual(source.path, video_path)

    def test_board_file_source_uses_remote_board_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_video_config(root)
            runtime = root / "runtime" / "input_source.json"
            local_video = root / "data" / "runtime" / "board_media" / "current_demo.mp4"
            local_video.parent.mkdir(parents=True)
            local_video.write_bytes(b"placeholder")
            save_input_source(
                "board_file_demo",
                config,
                runtime,
                source_overrides={
                    "board_path": "/root/safelab_media/current_demo.mp4",
                    "path": str(local_video),
                    "width": "362",
                    "height": "398",
                    "media_type": "image",
                },
            )

            source = build_active_frame_source(
                video_config_path=config,
                input_source_path=runtime,
                camera_frame_url="http://camera/frame.jpg",
                camera_status_url="http://camera/status",
            )

        self.assertEqual(source.key, "board_file_demo")
        self.assertEqual(source.source_type, "board_file")
        self.assertEqual(source.board_path, "/root/safelab_media/current_demo.mp4")
        self.assertEqual(source.path, local_video)
        self.assertEqual(source.width, 362)
        self.assertEqual(source.height, 398)
        self.assertEqual(source.media_type, "image")


def _write_video_config(root: Path) -> Path:
    config = root / "configs" / "video_config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "\n".join(
            [
                "video_sources:",
                "  default: camera_ov13855",
                "  camera_ov13855:",
                "    source_type: camera",
                "    device: /dev/video-camera0",
                "    source_name: ov13855_video11",
                "  file_demo:",
                "    source_type: file",
                "    path: ../video/demo.mp4",
                "    source_name: local_demo_video",
                "  board_file_demo:",
                "    source_type: board_file",
                "    board_path: /root/safelab_media/current_demo.mp4",
                "    source_name: rk_local_video",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return config


if __name__ == "__main__":
    unittest.main()

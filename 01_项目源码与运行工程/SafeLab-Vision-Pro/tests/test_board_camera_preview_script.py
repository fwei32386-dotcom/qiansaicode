from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BoardCameraPreviewScriptTest(unittest.TestCase):
    def test_preview_script_uses_gstreamer_and_camera_alias(self) -> None:
        script = (ROOT / "tools" / "board_camera_preview.sh").read_text(encoding="utf-8")

        self.assertIn("/dev/video-camera0", script)
        self.assertIn("gst-launch-1.0", script)
        self.assertIn("board_camera_preview.jpg", script)
        self.assertIn("autovideosink", script)
        self.assertIn("snapshot_with_retry", script)

    def test_snapshot_preview_outputs_yolo_sized_frame(self) -> None:
        script = (ROOT / "tools" / "board_camera_preview.sh").read_text(encoding="utf-8")

        self.assertIn("num-buffers=1", script)
        self.assertIn("video/x-raw,width=640,height=640", script)

    def test_report_index_includes_camera_preview(self) -> None:
        index_script = (ROOT / "tools" / "generate_report_index.py").read_text(encoding="utf-8")

        self.assertIn("board_camera_preview.html", index_script)
        self.assertIn("board_camera_preview.txt", index_script)


if __name__ == "__main__":
    unittest.main()

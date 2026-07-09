from __future__ import annotations

import unittest
from pathlib import Path

from tools.start_board_camera_live_preview import SharedFrame, build_gstreamer_command, build_mock_overlay


ROOT = Path(__file__).resolve().parents[1]


class BoardCameraLivePreviewTest(unittest.TestCase):
    def test_gstreamer_command_streams_to_stdout_without_filesink_location(self) -> None:
        command = build_gstreamer_command("/dev/video-camera0", 4224, 3136, 5, 960)

        self.assertIn("v4l2src device=/dev/video-camera0", command)
        self.assertIn("jpegenc", command)
        self.assertIn("fdsink fd=1", command)
        self.assertNotIn("filesink location=", command)

    def test_gstreamer_command_preserves_camera_aspect_ratio(self) -> None:
        command = build_gstreamer_command("/dev/video-camera0", 4224, 3136, 5, 480)

        self.assertIn("video/x-raw,width=480,height=356", command)

    def test_powershell_wrapper_runs_local_python_server(self) -> None:
        text = (ROOT / "tools" / "start_board_camera_live_preview.ps1").read_text(encoding="utf-8")

        self.assertIn("start_board_camera_live_preview.py", text)
        self.assertIn("--port $Port", text)
        self.assertIn("--fps $Fps", text)

    def test_mock_overlay_uses_source_coordinates_and_events(self) -> None:
        payload = build_mock_overlay(frame_id=10, source_width=4224, source_height=3136)

        self.assertEqual(payload["mode"], "mock_overlay")
        self.assertEqual(payload["source_width"], 4224)
        self.assertEqual(payload["source_height"], 3136)
        self.assertGreaterEqual(len(payload["detections"]), 3)
        self.assertEqual(payload["events"][0]["rule_id"], "R001")

    def test_live_monitor_page_exposes_overlay_controls(self) -> None:
        text = (ROOT / "tools" / "start_board_camera_live_preview.py").read_text(encoding="utf-8")

        self.assertIn("/detections?frame_id=", text)
        self.assertIn("Mock Overlay Off", text)
        self.assertIn("let overlayEnabled = false", text)
        self.assertIn("overlay-box", text)

    def test_shared_frame_snapshot_marks_old_frame_as_stale(self) -> None:
        shared = SharedFrame({"stale_after_seconds": 1.0})
        shared.update_frame(b"jpg")
        shared.last_frame_at -= 2.0

        status = shared.snapshot()

        self.assertTrue(status["stale"])
        self.assertEqual(status["estimated_fps"], 0.0)

    def test_camera_preview_script_has_reader_reconnect_delay(self) -> None:
        text = (ROOT / "tools" / "start_board_camera_live_preview.py").read_text(encoding="utf-8")

        self.assertIn("--reconnect-delay", text)
        self.assertIn("reconnect_delay_seconds", text)


if __name__ == "__main__":
    unittest.main()

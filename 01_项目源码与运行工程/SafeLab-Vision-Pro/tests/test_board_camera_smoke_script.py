from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BoardCameraSmokeScriptTest(unittest.TestCase):
    def test_camera_smoke_script_uses_verified_ov13855_node(self) -> None:
        script = (ROOT / "tools" / "board_camera_smoke_test.sh").read_text(encoding="utf-8")

        self.assertIn("/dev/video-camera0", script)
        self.assertIn("/dev/video11", script)
        self.assertIn("--stream-count=1", script)
        self.assertIn("timeout 8", script)
        self.assertIn("Camera smoke test passed", script)

    def test_video_config_prefers_camera_alias(self) -> None:
        config = (ROOT / "configs" / "video_config.yaml").read_text(encoding="utf-8")

        self.assertIn("device: /dev/video-camera0", config)
        self.assertIn("source_name: ov13855_video11", config)


if __name__ == "__main__":
    unittest.main()

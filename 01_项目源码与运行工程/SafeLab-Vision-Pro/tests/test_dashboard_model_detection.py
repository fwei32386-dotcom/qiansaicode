from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dashboard.model_detection import build_model_detection_state, save_model_detection


class DashboardModelDetectionTest(unittest.TestCase):
    def test_missing_runtime_file_uses_enabled_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = build_model_detection_state(Path(tmp) / "model_detection.json")

        self.assertTrue(state["model_detection"]["enabled"])
        self.assertEqual(state["model_detection"]["interval_frames"], 75)

    def test_save_model_detection_validates_and_persists_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime" / "model_detection.json"

            state = save_model_detection(False, 90, path)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertFalse(state["model_detection"]["enabled"])
        self.assertEqual(state["model_detection"]["interval_frames"], 90)
        self.assertFalse(payload["enabled"])

    def test_invalid_interval_is_rejected_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime" / "model_detection.json"
            save_model_detection(True, 75, path)

            with self.assertRaises(ValueError):
                save_model_detection(True, 0, path)

            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["interval_frames"], 75)


if __name__ == "__main__":
    unittest.main()

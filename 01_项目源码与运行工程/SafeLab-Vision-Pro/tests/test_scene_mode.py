from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dashboard.scene_mode import build_scene_mode_state, save_scene_mode


class SceneModeTest(unittest.TestCase):
    def test_missing_scene_mode_defaults_to_construction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = build_scene_mode_state(Path(tmp) / "scene_mode.json")

        self.assertEqual(state["scene_mode"]["mode"], "construction")
        self.assertEqual(state["scene_mode"]["label"], "工地")
        self.assertEqual(state["scene_mode"]["required_ppe"], ["helmet", "vest"])

    def test_save_lab_scene_mode_persists_lab_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime" / "scene_mode.json"

            state = save_scene_mode("lab", path)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(state["scene_mode"]["mode"], "lab")
        self.assertEqual(state["scene_mode"]["label"], "实验室")
        self.assertEqual(state["scene_mode"]["required_ppe"], ["goggles", "gloves"])
        self.assertEqual(payload["mode"], "lab")

    def test_unknown_scene_mode_is_rejected_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime" / "scene_mode.json"
            save_scene_mode("construction", path)

            with self.assertRaises(ValueError):
                save_scene_mode("office", path)

            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["mode"], "construction")


if __name__ == "__main__":
    unittest.main()

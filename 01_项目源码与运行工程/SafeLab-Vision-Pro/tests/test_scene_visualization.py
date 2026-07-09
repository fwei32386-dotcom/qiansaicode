from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.visualize_scene import write_scene_visualization


class SceneVisualizationTest(unittest.TestCase):
    def test_scene_visualization_contains_zones_and_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = write_scene_visualization(output_path=Path(tmp) / "scene.html")
            html = output.read_text(encoding="utf-8")

        self.assertIn("SafeLab Scene Visualization", html)
        self.assertIn("danger_zone", html)
        self.assertIn("person", html)
        self.assertIn("R001", html)


if __name__ == "__main__":
    unittest.main()


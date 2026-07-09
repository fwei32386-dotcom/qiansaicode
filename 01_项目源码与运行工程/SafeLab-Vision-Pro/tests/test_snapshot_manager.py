from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evidence.snapshot_manager import SnapshotManager
from runtime.replay_runner import ReplayRunner
from runtime.timeline_loader import load_timeline


ROOT = Path(__file__).resolve().parents[1]


class SnapshotManagerTest(unittest.TestCase):
    def test_snapshot_manager_writes_raw_and_marked_svg(self) -> None:
        frames = load_timeline(ROOT / "data" / "mock_scenarios" / "timeline_smoke.json")
        result = ReplayRunner().run(frames)
        detections = [detection for frame in frames for detection in frame.detections]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manager = SnapshotManager(tmp_path / "raw", tmp_path / "marked")
            paths = manager.save_event_snapshot(result.events[0], detections)
            raw = Path(paths["raw"])
            marked = Path(paths["marked"])
            marked_text = marked.read_text(encoding="utf-8")
            self.assertTrue(raw.exists())
            self.assertTrue(marked.exists())
            self.assertIn(result.events[0].event_id, marked_text)
            self.assertIn("consecutive frames", marked_text)
            self.assertIn("<svg", marked_text)


if __name__ == "__main__":
    unittest.main()

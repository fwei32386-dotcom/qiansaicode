from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evidence.event_timeline import build_event_timelines, write_event_timelines
from runtime.replay_runner import ReplayRunner
from runtime.timeline_loader import load_timeline


ROOT = Path(__file__).resolve().parents[1]


class EventTimelineTest(unittest.TestCase):
    def test_event_timelines_group_lifecycle_by_event_key(self) -> None:
        result = _replay_smoke()
        grouped = build_event_timelines(result.timeline)

        self.assertEqual(sorted(grouped), ["smoke"])
        self.assertEqual([item["stage"] for item in grouped["smoke"]], ["suspicious", "alarmed", "closed"])

    def test_event_timeline_files_are_written(self) -> None:
        result = _replay_smoke()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = write_event_timelines(
                result.timeline,
                output_dir=tmp_path / "timelines",
                index_path=tmp_path / "timelines" / "index.json",
            )
            smoke_payload = json.loads(paths["smoke"].read_text(encoding="utf-8"))
            index_payload = json.loads(paths["_index"].read_text(encoding="utf-8"))

        self.assertEqual(smoke_payload["summary"]["alarm_count"], 1)
        self.assertEqual(smoke_payload["summary"]["closed_count"], 1)
        self.assertEqual(index_payload["event_count"], 1)


def _replay_smoke():
    frames = load_timeline(ROOT / "data" / "mock_scenarios" / "timeline_smoke.json")
    return ReplayRunner().run(frames)


if __name__ == "__main__":
    unittest.main()

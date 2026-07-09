from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from runtime.replay_runner import ReplayRunner
from runtime.timeline_loader import load_timeline


ROOT = Path(__file__).resolve().parents[1]


class ReplayRunnerTest(unittest.TestCase):
    def test_timeline_smoke_confirms_once_and_closes(self) -> None:
        frames = load_timeline(ROOT / "data" / "mock_scenarios" / "timeline_smoke.json")
        result = ReplayRunner().run(frames)

        self.assertEqual([stage.stage for stage in result.timeline], ["suspicious", "alarmed", "closed"])
        self.assertEqual(len(result.events), 1)
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.events[0].event_type, "smoke")
        self.assertIn("consecutive frames", result.events[0].reasons[0])

    def test_timeline_ppe_confirms_once_and_closes(self) -> None:
        frames = load_timeline(ROOT / "data" / "mock_scenarios" / "timeline_ppe_missing_goggles.json")
        result = ReplayRunner().run(frames)

        self.assertEqual([stage.stage for stage in result.timeline], ["suspicious", "alarmed", "closed"])
        self.assertEqual(len(result.events), 1)
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.events[0].event_type, "ppe_violation")
        self.assertEqual(result.events[0].rule_id, "R004")
        self.assertTrue(any("consecutive frames" in reason for reason in result.events[0].reasons))

    def test_csv_report_is_written(self) -> None:
        frames = load_timeline(ROOT / "data" / "mock_scenarios" / "timeline_smoke.json")
        runner = ReplayRunner()
        result = runner.run(frames)

        with tempfile.TemporaryDirectory() as tmp:
            output = runner.write_csv_report(result, Path(tmp) / "replay.csv")
            with output.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]["stage"], "alarmed")
        self.assertEqual(rows[1]["should_alarm"], "True")

    def test_timeline_json_is_written(self) -> None:
        frames = load_timeline(ROOT / "data" / "mock_scenarios" / "timeline_smoke.json")
        runner = ReplayRunner()
        result = runner.run(frames)

        with tempfile.TemporaryDirectory() as tmp:
            output = runner.write_timeline_json(result, Path(tmp) / "timeline.json")
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["summary"]["timeline_stages"], 3)
        self.assertEqual(payload["timeline"][1]["stage"], "alarmed")
        self.assertTrue(payload["timeline"][1]["should_alarm"])


if __name__ == "__main__":
    unittest.main()

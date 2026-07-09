from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.replay_runner import ReplayRunner
from runtime.timeline_loader import load_timeline
from tools.generate_eval_summary import generate_eval_summary
from tools.validate_config import validate_config


ROOT = Path(__file__).resolve().parents[1]


class ToolsReportsTest(unittest.TestCase):
    def test_validate_config_ok(self) -> None:
        errors = validate_config(
            ROOT / "configs" / "semantic_map.json",
            ROOT / "configs" / "rule_dsl.json",
        )

        self.assertEqual(errors, [])

    def test_eval_summary_counts_replay_stages(self) -> None:
        frames = load_timeline(ROOT / "data" / "mock_scenarios" / "timeline_smoke.json")
        runner = ReplayRunner()
        result = runner.run(frames)

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "replay.csv"
            output_path = Path(tmp) / "summary.json"
            runner.write_csv_report(result, csv_path)
            summary = generate_eval_summary(csv_path, output_path)

        self.assertEqual(summary["alarm_count"], 1)
        self.assertEqual(summary["duplicate_alarm_count"], 0)
        self.assertEqual(summary["first_alarm_frame"], 203)
        self.assertEqual(summary["first_closed_frame"], 206)


if __name__ == "__main__":
    unittest.main()


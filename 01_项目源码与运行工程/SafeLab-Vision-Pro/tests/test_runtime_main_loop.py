from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.main_loop import run_mock_main_loop


class RuntimeMainLoopTest(unittest.TestCase):
    def test_mock_main_loop_generates_events_actions_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_mock_main_loop(
                frame_count=8,
                output_dir=root / "events",
                summary_path=root / "main_loop_summary.json",
            )
            events_log = (root / "events" / "events.jsonl").read_text(encoding="utf-8").splitlines()
            actions_log = (root / "events" / "alarm_actions.jsonl").read_text(encoding="utf-8").splitlines()
            summary = json.loads((root / "main_loop_summary.json").read_text(encoding="utf-8"))

        self.assertEqual(result.frames_read, 8)
        self.assertGreaterEqual(result.frames_processed, 2)
        self.assertGreaterEqual(result.frames_skipped, 1)
        self.assertEqual(result.events, 2)
        self.assertEqual(result.actions, 2)
        self.assertEqual(len(events_log), 2)
        self.assertEqual(len(actions_log), 2)
        self.assertTrue(summary["watchdog_healthy"])
        self.assertIn("rule_eval_ms", summary["profiler"]["average_ms"])


if __name__ == "__main__":
    unittest.main()

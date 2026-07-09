from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from tools.benchmark_track_manager import benchmark_track_manager


class TrackManagerBenchmarkTest(unittest.TestCase):
    def test_track_manager_report_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            summary = benchmark_track_manager(
                csv_path=tmp_path / "track_trace.csv",
                summary_path=tmp_path / "track_summary.json",
            )
            with (tmp_path / "track_trace.csv").open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))

        self.assertEqual(summary["trace_rows"], 4)
        self.assertTrue(summary["first_person_track_stable"])
        self.assertEqual(summary["first_person_final_state"], "confirmed")
        self.assertEqual(rows[2]["hit_count"], "3")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from tools.benchmark_roi_manager import benchmark_roi_manager


class ROIManagerBenchmarkTest(unittest.TestCase):
    def test_roi_manager_report_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            summary = benchmark_roi_manager(
                csv_path=tmp_path / "roi_trace.csv",
                summary_path=tmp_path / "roi_summary.json",
            )
            with (tmp_path / "roi_trace.csv").open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))

        self.assertEqual(summary["roi_count"], 2)
        self.assertEqual(len(rows), 2)
        self.assertTrue(summary["normal_track_skipped"])
        self.assertGreater(summary["estimated_saved_ratio"], 0.0)


if __name__ == "__main__":
    unittest.main()

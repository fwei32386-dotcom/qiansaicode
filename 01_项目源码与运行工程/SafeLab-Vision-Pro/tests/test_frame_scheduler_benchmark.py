from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from tools.benchmark_frame_scheduler import benchmark_frame_scheduler


class FrameSchedulerBenchmarkTest(unittest.TestCase):
    def test_frame_scheduler_report_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            summary = benchmark_frame_scheduler(
                frame_count=12,
                csv_path=tmp_path / "trace.csv",
                summary_path=tmp_path / "summary.json",
            )
            with (tmp_path / "trace.csv").open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))

        self.assertEqual(summary["frame_count"], 12)
        self.assertEqual(len(rows), 12)
        self.assertGreater(summary["processed_count"], summary["skipped_count"])
        self.assertGreater(summary["roi_count"], 0)


if __name__ == "__main__":
    unittest.main()

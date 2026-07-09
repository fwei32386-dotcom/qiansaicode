from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from tools.benchmark_pipeline_latency import benchmark_pipeline_latency


ROOT = Path(__file__).resolve().parents[1]


class PipelineLatencyTest(unittest.TestCase):
    def test_pipeline_latency_report_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            summary = benchmark_pipeline_latency(
                ROOT / "data" / "mock_scenarios" / "danger_zone_ppe.json",
                iterations=2,
                csv_path=tmp_path / "pipeline_latency.csv",
                summary_path=tmp_path / "pipeline_latency_summary.json",
            )
            rows = _read_csv(tmp_path / "pipeline_latency.csv")

        self.assertEqual(summary["iterations"], 2)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["events"], "1")
        self.assertIn("total_ms", rows[0])
        self.assertGreaterEqual(float(summary["average_ms"]["total_ms"]), 0.0)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    unittest.main()

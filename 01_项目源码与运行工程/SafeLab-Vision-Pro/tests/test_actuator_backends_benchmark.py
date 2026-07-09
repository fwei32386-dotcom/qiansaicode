from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from tools.benchmark_actuator_backends import benchmark_actuator_backends


class ActuatorBackendsBenchmarkTest(unittest.TestCase):
    def test_actuator_backend_report_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            summary = benchmark_actuator_backends(
                csv_path=tmp_path / "actuator_trace.csv",
                summary_path=tmp_path / "actuator_summary.json",
                log_path=tmp_path / "actuator_check.jsonl",
            )
            with (tmp_path / "actuator_trace.csv").open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))

        self.assertEqual(summary["backend_count"], 3)
        self.assertEqual(set(summary["backends"]), {"mock", "shell", "gpio"})
        self.assertTrue(summary["hardware_safe"])
        self.assertEqual(len(rows), 3)


if __name__ == "__main__":
    unittest.main()

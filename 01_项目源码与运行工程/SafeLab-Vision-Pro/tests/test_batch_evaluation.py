from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from tools.run_batch_evaluation import run_batch_evaluation


ROOT = Path(__file__).resolve().parents[1]


class BatchEvaluationTest(unittest.TestCase):
    def test_batch_evaluation_all_cases_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_csv = Path(tmp) / "batch.csv"
            summary_json = Path(tmp) / "summary.json"
            summary = run_batch_evaluation(
                ROOT / "configs" / "evaluation_cases.json",
                report_csv,
                summary_json,
            )
            with report_csv.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

        self.assertEqual(summary["case_count"], 7)
        self.assertEqual(summary["failed_count"], 0)
        self.assertEqual(len(rows), 7)
        self.assertTrue(all(row["passed"] == "True" for row in rows))


if __name__ == "__main__":
    unittest.main()

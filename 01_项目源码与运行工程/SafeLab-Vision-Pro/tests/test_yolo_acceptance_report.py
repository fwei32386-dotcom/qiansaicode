from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.yolo_acceptance_report import AcceptanceTarget, evaluate_metrics_csv, write_acceptance_report


class YoloAcceptanceReportTest(unittest.TestCase):
    def test_evaluate_metrics_csv_marks_unqualified_classes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            metrics_path = Path(temp_dir) / "metrics.csv"
            metrics_path.write_text(
                "class_id,class_name,gt,pred,tp,fp,fn,precision,recall\n"
                "0,person,10,10,8,2,2,0.8,0.8\n"
                "5,fire,10,8,6,2,4,0.75,0.6\n",
                encoding="utf-8",
            )

            result = evaluate_metrics_csv(
                metrics_path,
                targets={
                    "person": AcceptanceTarget(min_precision=0.7, min_recall=0.7),
                    "fire": AcceptanceTarget(min_precision=0.7, min_recall=0.7),
                },
            )

        self.assertFalse(result["qualified"])
        self.assertEqual(result["classes"]["person"]["status"], "pass")
        self.assertEqual(result["classes"]["fire"]["status"], "fail")
        self.assertIn("recall 0.600 < 0.700", result["classes"]["fire"]["reasons"])

    def test_write_acceptance_report_records_source_plan_and_detection_contract(self) -> None:
        result = {
            "qualified": False,
            "metrics_path": "metrics.csv",
            "classes": {
                "person": {"precision": 0.8, "recall": 0.8, "status": "pass", "reasons": []},
            },
        }

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report.md"
            write_acceptance_report(result, output_path, source_plan="SafeLab docx")

            text = output_path.read_text(encoding="utf-8")

        self.assertIn("SafeLab docx", text)
        self.assertIn("Detection contract", text)
        self.assertIn("qualified: false", text)


if __name__ == "__main__":
    unittest.main()

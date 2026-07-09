from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.generate_final_acceptance_report import generate_final_acceptance_report


class FinalAcceptanceReportTest(unittest.TestCase):
    def test_final_acceptance_report_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output = generate_final_acceptance_report(
                html_path=tmp_path / "final.html",
                json_path=tmp_path / "final.json",
            )
            html = Path(output["html"]).read_text(encoding="utf-8")
            summary = json.loads(Path(output["json"]).read_text(encoding="utf-8"))

        self.assertIn("SafeLab-Vision Pro 最终验收报告", html)
        self.assertIn("验收完成度", html)
        self.assertGreaterEqual(summary["completion"]["non_yolo_system_percent"], 80)
        self.assertGreaterEqual(summary["completion"]["board_fallback_percent"], 50)
        self.assertIn("remaining_blockers", summary)
        self.assertIn("board_connection_status", summary["evidence"])
        self.assertIn("board_report_pull_downloaded", summary["evidence"])
        self.assertIn("camera_preview_jpg_bytes", summary["evidence"])
        self.assertTrue(summary["rknn_runtime"]["detection_json_ready"])
        self.assertTrue(summary["rknn_runtime"]["safelab_binary_present"])
        self.assertEqual(summary["rknn_runtime"]["build_state"], "board_binary_present")
        self.assertIn("rknn_detection_json_ready", summary["evidence"])
        check_names = [check["name"] for check in summary["checks"]]
        self.assertIn("RKNN Detection JSON contract", check_names)
        self.assertIn("RKNN Detection JSONL rule replay", check_names)
        self.assertIn("RKNN SafeLab native source contract", check_names)
        self.assertIn("RKNN SafeLab board binary", check_names)
        self.assertIn("Board audio and onboard MIC", check_names)
        self.assertIn("GPIO controlled outputs", check_names)


if __name__ == "__main__":
    unittest.main()

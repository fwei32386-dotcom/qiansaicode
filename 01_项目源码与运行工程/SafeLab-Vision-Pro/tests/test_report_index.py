from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.generate_report_index import generate_report_index


class ReportIndexTest(unittest.TestCase):
    def test_report_index_lists_existing_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports_dir = Path(tmp)
            (reports_dir / "alarm_dashboard.html").write_text("dashboard", encoding="utf-8")
            (reports_dir / "live_dashboard.html").write_text("live", encoding="utf-8")
            (reports_dir / "board_camera_preview.html").write_text("preview", encoding="utf-8")
            (reports_dir / "board_camera_preview.jpg").write_bytes(b"fake-image")
            (reports_dir / "final_acceptance_summary.json").write_text(
                '{"completion":{"full_system_percent":91,"test_count":113}}',
                encoding="utf-8",
            )
            (reports_dir / "live_dashboard_state.json").write_text(
                '{"input_source":{"selected_source":"camera_ov13855","label":"Camera","source_type":"camera"},'
                '"available_input_sources":[{"id":"camera_ov13855","label":"Camera"},{"id":"file_demo","label":"本地输入"}]}',
                encoding="utf-8",
            )
            (reports_dir / "batch_eval_report.csv").write_text("case_id,passed\n", encoding="utf-8")
            (reports_dir / "board_connection_check.txt").write_text("Status: reachable\n", encoding="utf-8")
            (reports_dir / "pull_board_reports_summary.txt").write_text("downloaded_count: 3\n", encoding="utf-8")
            output = generate_report_index(reports_dir, reports_dir / "index.html")
            html = output.read_text(encoding="utf-8")

        self.assertIn("SafeLab \u9a8c\u6536\u9a7e\u9a76\u8231", html)
        self.assertIn('data-testid="quick-link-live"', html)
        self.assertIn('id="mission-metrics"', html)
        self.assertIn('data-refresh-ms="3000"', html)
        self.assertIn('id="status-input-source"', html)
        self.assertIn('data-source-id="camera_ov13855"', html)
        self.assertIn('data-source-id="file_demo"', html)
        self.assertNotIn('data-source-id="hdmi_capture"', html)
        self.assertIn("\u8f93\u5165\u6e90", html)
        self.assertIn("board_camera_preview.jpg", html)
        self.assertIn("alarm_dashboard.html", html)
        self.assertIn("batch_eval_report.csv", html)
        self.assertIn("board_connection_check.txt", html)
        self.assertIn("pull_board_reports_summary.txt", html)
        self.assertIn("AI \u8bf4\u660e", html)
        self.assertNotIn("\u7cfb\u7edf\u5b8c\u6210\u5ea6", html)

    def test_report_index_infers_camera_source_and_shows_mission_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports_dir = Path(tmp)
            (reports_dir / "board_camera_preview.html").write_text("preview", encoding="utf-8")
            (reports_dir / "board_camera_preview.jpg").write_bytes(b"fake-image")
            (reports_dir / "live_dashboard.html").write_text("live", encoding="utf-8")
            (reports_dir / "live_dashboard_state.json").write_text(
                '{"health":{"camera":"present","fallback_mode":"shell_only+mock_detection"},'
                '"counts":{"events":32,"high_risk_events":31,"actions":32},'
                '"status":{"risk_state":"alarm"}}',
                encoding="utf-8",
            )
            (reports_dir / "final_acceptance_summary.json").write_text(
                '{"completion":{"full_system_percent":83}}',
                encoding="utf-8",
            )
            output = generate_report_index(reports_dir, reports_dir / "index.html")
            html = output.read_text(encoding="utf-8")

        self.assertIn("\u4efb\u52a1\u56de\u653e", html)
        self.assertIn("\u6444\u50cf\u5934", html)
        self.assertIn("\u6839\u636e\u677f\u7aef\u76f8\u673a\u8bc1\u636e\u63a8\u65ad", html)
        self.assertIn('class="source-mode active"', html)
        for step in [
            "\u8f93\u5165\u6e90",
            "RKNN \u89c6\u89c9\u8bc6\u522b",
            "\u89c4\u5219\u5f15\u64ce",
            "\u544a\u8b66\u52a8\u4f5c",
            "\u8bc1\u636e\u5305",
        ]:
            self.assertIn(step, html)
        self.assertNotIn('<strong id="input-source-label">unknown</strong>', html)

    def test_report_index_uses_chinese_ui_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports_dir = Path(tmp)
            (reports_dir / "alarm_dashboard.html").write_text("dashboard", encoding="utf-8")
            (reports_dir / "latest_report.html").write_text("report", encoding="utf-8")
            (reports_dir / "batch_eval_report.csv").write_text("case_id,passed\n", encoding="utf-8")
            (reports_dir / "demo_export.zip").write_bytes(b"zip")
            output = generate_report_index(reports_dir, reports_dir / "index.html")
            html = output.read_text(encoding="utf-8")

        for label in [
            "\u9a8c\u6536\u6750\u6599",
            "\u5de5\u7a0b\u539f\u59cb\u6587\u4ef6",
            "\u4eea\u8868\u76d8",
            "\u62a5\u544a",
            "\u8bc4\u4f30\u6570\u636e",
            "\u5bfc\u51fa\u5305",
            "\u4e3b\u8981\u6d41\u7a0b",
            "\u8f93\u5165\u6e90",
        ]:
            self.assertIn(label, html)
        for old_label in [
            ">Report Library<",
            ">Dashboards<",
            ">Reports<",
            ">Evaluation Data<",
            ">Export<",
            ">Primary Workflows<",
            ">Input Source<",
        ]:
            self.assertNotIn(old_label, html)

    def test_report_index_prioritizes_acceptance_materials_and_collapses_raw_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports_dir = Path(tmp)
            (reports_dir / "final_acceptance_report.html").write_text("acceptance", encoding="utf-8")
            (reports_dir / "live_dashboard.html").write_text("live", encoding="utf-8")
            (reports_dir / "board_camera_preview.html").write_text("preview", encoding="utf-8")
            (reports_dir / "config_audit.html").write_text("config", encoding="utf-8")
            (reports_dir / "batch_eval_report.csv").write_text("case_id,passed\n", encoding="utf-8")
            (reports_dir / "demo_export.zip").write_bytes(b"zip")
            output = generate_report_index(reports_dir, reports_dir / "index.html")
            html = output.read_text(encoding="utf-8")

        self.assertIn("\u9a8c\u6536\u6750\u6599", html)
        self.assertIn("\u6700\u7ec8\u9a8c\u6536\u62a5\u544a", html)
        self.assertIn("\u5de5\u7a0b\u539f\u59cb\u6587\u4ef6\uff08\u5907\u67e5\uff09", html)
        self.assertIn('<details class="raw-library"', html)
        self.assertIn('class="evidence-visual"', html)
        self.assertIn('href="final_acceptance_report.html"', html)
        self.assertIn('href="demo_export.zip"', html)
        self.assertIn("\u6279\u91cf\u8bc4\u4f30\u660e\u7ec6", html)


if __name__ == "__main__":
    unittest.main()

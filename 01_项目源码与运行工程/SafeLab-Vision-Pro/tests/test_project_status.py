from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.generate_project_status import generate_project_status


class ProjectStatusTest(unittest.TestCase):
    def test_project_status_reports_are_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outputs = generate_project_status(
                Path(tmp) / "project_status.md",
                Path(tmp) / "project_status.html",
            )
            markdown = Path(outputs["markdown"]).read_text(encoding="utf-8")
            html = Path(outputs["html"]).read_text(encoding="utf-8")

        self.assertIn("SafeLab-Vision Pro Project Status", markdown)
        self.assertIn("Completed Features", markdown)
        self.assertIn("Board Path", markdown)
        self.assertIn("<html", html)

    def test_gap_analysis_and_cross_compile_docs_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        gap_text = (root / "docs" / "implementation_gap_analysis.md").read_text(encoding="utf-8")
        cross_text = (root / "docs" / "rknn_cross_compile_ubuntu.md").read_text(encoding="utf-8")

        self.assertIn("GPIO hardware bring-up is not part of the current work", gap_text)
        self.assertIn("SQLite", gap_text)
        self.assertIn("AI explanation -> speech output bridge", gap_text)
        self.assertIn("Keep DeepSeek in cloud or host-side service", gap_text)
        self.assertIn("cross_compile_required", gap_text)
        self.assertIn("aarch64-buildroot-linux-gnu-g++", cross_text)
        self.assertIn("/mnt/d/ELFrk3588/06-常用工具/01-编译工具安装脚本/aarch64-buildroot-linux-gnu_sdk-buildroot.tar.gz", cross_text)
        self.assertIn("Do not use the SDK directory extracted by Windows", cross_text)
        self.assertIn("board_rknn_runtime_check.json", cross_text)
        self.assertTrue(
            (
                root.parent
                / "06-常用工具"
                / "01-编译工具安装脚本"
                / "aarch64-buildroot-linux-gnu_sdk-buildroot.tar.gz"
            ).exists()
        )


if __name__ == "__main__":
    unittest.main()

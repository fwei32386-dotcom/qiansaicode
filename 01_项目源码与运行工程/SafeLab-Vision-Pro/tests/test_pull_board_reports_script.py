from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PullBoardReportsScriptTest(unittest.TestCase):
    def test_pull_script_stays_under_root_and_uses_paramiko(self) -> None:
        text = (ROOT / "tools" / "pull_board_reports.ps1").read_text(encoding="utf-8")

        self.assertIn('RemoteRoot must stay under /root', text)
        self.assertIn('import paramiko', text)
        self.assertIn('$RemoteReports = "$RemoteProject/reports"', text)
        self.assertIn('pull_board_reports_summary.json', text)

    def test_pull_script_keeps_events_optional(self) -> None:
        text = (ROOT / "tools" / "pull_board_reports.ps1").read_text(encoding="utf-8")

        self.assertIn("[switch]$IncludeEvents", text)
        self.assertIn('"include_events": include_events', text)
        self.assertIn('local_reports / "board_pull" / "data_events"', text)


if __name__ == "__main__":
    unittest.main()

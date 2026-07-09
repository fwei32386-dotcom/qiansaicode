from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BoardConnectionScriptTest(unittest.TestCase):
    def test_connection_script_writes_json_and_text_reports(self) -> None:
        text = (ROOT / "tools" / "check_board_connection.ps1").read_text(encoding="utf-8")

        self.assertIn("board_connection_check.txt", text)
        self.assertIn("board_connection_check.json", text)
        self.assertIn("Test-Connection", text)
        self.assertIn("expected_pc_ip", text)

    def test_connection_script_reports_subnet_recommendation(self) -> None:
        text = (ROOT / "tools" / "check_board_connection.ps1").read_text(encoding="utf-8")

        self.assertIn("pc_not_in_board_subnet", text)
        self.assertIn("Set the Windows Ethernet IPv4 address", text)
        self.assertIn("255.255.255.0", text)


if __name__ == "__main__":
    unittest.main()

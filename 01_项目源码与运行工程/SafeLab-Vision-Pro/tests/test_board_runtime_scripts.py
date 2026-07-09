from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BoardRuntimeScriptsTest(unittest.TestCase):
    def test_runtime_scripts_exist_and_use_shell(self) -> None:
        for name in ["start_safelab.sh", "status_safelab.sh", "stop_safelab.sh"]:
            path = ROOT / "tools" / name
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("#!/bin/sh"), name)
            self.assertIn("runtime_status", text)

    def test_start_script_treats_camera_check_as_optional(self) -> None:
        text = (ROOT / "tools" / "start_safelab.sh").read_text(encoding="utf-8")

        self.assertIn("run_optional_step \"Board camera check\"", text)
        self.assertIn("fallback runtime can still start", text)

    def test_board_health_check_requires_runtime_scripts(self) -> None:
        text = (ROOT / "tools" / "board_health_check.sh").read_text(encoding="utf-8")

        self.assertIn("tools/start_safelab.sh", text)
        self.assertIn("tools/status_safelab.sh", text)
        self.assertIn("tools/stop_safelab.sh", text)

    def test_board_log_and_competition_scripts_include_sqlite_alarm_log(self) -> None:
        log_tools = (ROOT / "tools" / "board_log_tools.sh").read_text(encoding="utf-8")
        competition = (ROOT / "demo" / "board_competition_mode.sh").read_text(encoding="utf-8")
        acceptance = (ROOT / "tools" / "board_acceptance_summary.sh").read_text(encoding="utf-8")

        self.assertIn("alarm_log.db", log_tools)
        self.assertIn("alarm_log.db", competition)
        self.assertIn("alarm_log.db", acceptance)


if __name__ == "__main__":
    unittest.main()

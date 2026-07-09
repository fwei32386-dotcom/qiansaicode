from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from tools.ablation_runner import run_ablation


ROOT = Path(__file__).resolve().parents[1]


class AblationRunnerTest(unittest.TestCase):
    def test_ablation_reports_compare_naive_and_stateful_methods(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            summary = run_ablation(
                ROOT / "data" / "mock_scenarios" / "timeline_smoke.json",
                tmp_path / "smoke_temporal_ablation.csv",
                tmp_path / "state_machine_ablation.csv",
                tmp_path / "ablation_summary.json",
            )
            smoke_rows = _read_csv(tmp_path / "smoke_temporal_ablation.csv")
            state_rows = _read_csv(tmp_path / "state_machine_ablation.csv")

        self.assertEqual(summary["temporal"][0]["method"], "single_frame_alarm")
        self.assertEqual(smoke_rows[0]["alarm_count"], "4")
        self.assertEqual(smoke_rows[1]["alarm_count"], "1")
        self.assertEqual(smoke_rows[1]["closed_count"], "1")
        self.assertEqual(state_rows[0]["duplicate_alarm_count"], "1")
        self.assertEqual(state_rows[1]["duplicate_alarm_count"], "0")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    unittest.main()

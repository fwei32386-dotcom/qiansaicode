from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evidence.risk_curve import build_risk_curve, write_risk_curve_outputs
from runtime.replay_runner import ReplayRunner
from runtime.timeline_loader import load_timeline


ROOT = Path(__file__).resolve().parents[1]


class RiskCurveTest(unittest.TestCase):
    def test_risk_curve_scores_follow_event_lifecycle(self) -> None:
        result = _replay_smoke()
        curve = build_risk_curve(result.timeline)

        self.assertEqual([item["risk_score"] for item in curve], [35, 80, 0])
        self.assertEqual([item["stage"] for item in curve], ["suspicious", "alarmed", "closed"])

    def test_risk_curve_outputs_are_written(self) -> None:
        result = _replay_smoke()
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_risk_curve_outputs(
                result.timeline,
                Path(tmp) / "risk_curve.csv",
                Path(tmp) / "risk_curve.json",
                Path(tmp) / "risk_curve.html",
            )
            payload = json.loads(paths["json"].read_text(encoding="utf-8"))
            html = paths["html"].read_text(encoding="utf-8")

        self.assertEqual(len(payload["risk_curve"]), 3)
        self.assertIn("SafeLab Risk Curve", html)


def _replay_smoke():
    frames = load_timeline(ROOT / "data" / "mock_scenarios" / "timeline_smoke.json")
    return ReplayRunner().run(frames)


if __name__ == "__main__":
    unittest.main()


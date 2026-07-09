from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from actuator.alarm_manager import AlarmManager
from ai_engine.json_detection_loader import load_detections_from_json
from evidence.html_report import write_html_report
from safety_brain.simple_rule_engine import SimpleRuleEngine


ROOT = Path(__file__).resolve().parents[1]


class JsonPipelineTest(unittest.TestCase):
    def test_ppe_json_scenario_generates_event(self) -> None:
        detections = load_detections_from_json(
            ROOT / "data" / "mock_scenarios" / "ppe_missing_helmet.json"
        )
        events = SimpleRuleEngine().evaluate(detections)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "ppe_violation")
        self.assertIn("helmet missing", events[0].reasons)

    def test_fire_json_scenario_generates_emergency_action(self) -> None:
        detections = load_detections_from_json(ROOT / "data" / "mock_scenarios" / "fire_risk.json")
        events = SimpleRuleEngine().evaluate(detections)
        actions = [AlarmManager().build_action(event) for event in events]

        self.assertEqual(events[0].risk_level, "emergency")
        self.assertTrue(actions[0].buzzer)
        self.assertEqual(actions[0].led_color, "red")

    def test_html_report_is_written(self) -> None:
        detections = load_detections_from_json(ROOT / "data" / "mock_scenarios" / "fire_risk.json")
        events = SimpleRuleEngine().evaluate(detections)
        actions = [AlarmManager().build_action(event) for event in events]

        with tempfile.TemporaryDirectory() as tmp:
            output = write_html_report(detections, events, actions, Path(tmp) / "report.html")
            html = output.read_text(encoding="utf-8")

        self.assertIn("SafeLab \u68c0\u6d4b\u62a5\u544a", html)
        self.assertIn("fire", html)
        self.assertIn("emergency", html)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from actuator.alarm_manager import AlarmManager
from actuator.backends import ActuatorPinConfig, create_actuator_backend
from actuator.mock_actuator import MockActuator
from ai_engine.json_detection_loader import load_detections_from_json
from dashboard.static_dashboard import write_alarm_dashboard
from safety_brain.rule_dsl_engine import RuleDslEngine


ROOT = Path(__file__).resolve().parents[1]


class DashboardActuatorTest(unittest.TestCase):
    def test_mock_actuator_writes_execution_record(self) -> None:
        event = _load_dsl_event()
        action = AlarmManager().build_action(event)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "actuator_log.jsonl"
            record = MockActuator(path).execute(action)
            lines = path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(record["backend"], "mock")
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["led"]["color"], "red")

    def test_shell_actuator_records_planned_commands_only(self) -> None:
        event = _load_dsl_event()
        action = AlarmManager().build_action(event)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "actuator_log.jsonl"
            record = create_actuator_backend("shell", path).execute(action)
            saved = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual(record["backend"], "shell")
        self.assertFalse(record["executed"])
        self.assertTrue(saved["shell_commands"])

    def test_gpio_actuator_records_pin_contract_without_writing_pins(self) -> None:
        event = _load_dsl_event()
        action = AlarmManager().build_action(event)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "actuator_log.jsonl"
            record = create_actuator_backend(
                "gpio",
                path,
                ActuatorPinConfig(led_red=17, buzzer=18, relay=27),
            ).execute(action)

        self.assertEqual(record["backend"], "gpio")
        self.assertEqual(record["pin_config"]["led_red"], 17)
        self.assertFalse(record["executed"])

    def test_dashboard_contains_alarm_content(self) -> None:
        event = _load_dsl_event()
        action = AlarmManager().build_action(event)
        record = {
            "event_id": action.event_id,
            "voice": {"text": action.voice_text},
            "led": {"color": action.led_color},
            "buzzer": {"enabled": action.buzzer},
            "backend": "mock",
        }

        with tempfile.TemporaryDirectory() as tmp:
            output = write_alarm_dashboard([event], [action], [record], Path(tmp) / "dashboard.html")
            html = output.read_text(encoding="utf-8")

        self.assertIn("SafeLab \u544a\u8b66\u590d\u76d8", html)
        self.assertIn("\u5371\u9669\u533a\u57df\u7f3a\u5c11\u5b89\u5168\u5e3d", html)
        self.assertIn("red", html)


def _load_dsl_event():
    detections = load_detections_from_json(ROOT / "data" / "mock_scenarios" / "danger_zone_ppe.json")
    engine = RuleDslEngine.from_files(
        ROOT / "configs" / "semantic_map.json",
        ROOT / "configs" / "rule_dsl.json",
    )
    return engine.evaluate(detections)[0]


if __name__ == "__main__":
    unittest.main()

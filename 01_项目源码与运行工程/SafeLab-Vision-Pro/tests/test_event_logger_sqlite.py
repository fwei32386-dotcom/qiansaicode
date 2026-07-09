from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from evidence.event_logger import EventLogger


class EventLoggerSqliteTest(unittest.TestCase):
    def test_event_logger_writes_jsonl_and_alarm_log_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            logger = EventLogger(output_dir)

            event = {
                "event_id": "E_TEST_001",
                "frame_id": 7,
                "source_type": "mock",
                "event_type": "smoke",
                "risk_score": 85,
                "risk_level": "emergency",
                "reasons": ["3 consecutive smoke frames"],
                "bbox": [10, 20, 40, 80],
                "timestamp": 1710000000.1,
            }
            action = {
                "event_id": "E_TEST_001",
                "voice_text": "Smoke risk detected.",
                "led_color": "red",
                "buzzer": True,
                "relay": False,
                "snapshot": True,
                "log": True,
                "cooldown_ms": 20000,
            }

            logger.log_event(event)
            logger.log_action(action)

            self.assertTrue((output_dir / "events.jsonl").exists())
            self.assertTrue((output_dir / "alarm_actions.jsonl").exists())
            self.assertTrue((output_dir / "alarm_log.db").exists())

            conn = sqlite3.connect(output_dir / "alarm_log.db")
            try:
                event_row = conn.execute(
                    "select event_id, event_type, risk_level, payload_json from events"
                ).fetchone()
                action_row = conn.execute(
                    "select event_id, led_color, buzzer, payload_json from alarm_actions"
                ).fetchone()
            finally:
                conn.close()

            self.assertEqual(event_row[:3], ("E_TEST_001", "smoke", "emergency"))
            self.assertEqual(json.loads(event_row[3])["reasons"], ["3 consecutive smoke frames"])
            self.assertEqual(action_row[:3], ("E_TEST_001", "red", 1))
            self.assertTrue(json.loads(action_row[3])["snapshot"])


if __name__ == "__main__":
    unittest.main()

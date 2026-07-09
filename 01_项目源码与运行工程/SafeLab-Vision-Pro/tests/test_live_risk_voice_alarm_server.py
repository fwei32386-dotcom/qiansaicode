from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from dashboard.live_server import LiveDashboardConfig, LiveDashboardServer
from dashboard.risk_voice_alarm import RiskVoiceAnnouncer


class LiveRiskVoiceAlarmServerTest(unittest.TestCase):
    def test_build_state_triggers_board_voice_alarm_for_active_ppe_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.jsonl"
            spoken: list[str] = []
            events.write_text(
                json.dumps(
                    {
                        "event_id": "E1",
                        "event_type": "ppe_violation",
                        "risk_level": "high",
                        "timestamp": time.time(),
                        "reasons": ["missing_ppe=helmet, vest"],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            server = LiveDashboardServer(
                ("127.0.0.1", 0),
                LiveDashboardConfig(
                    events_path=events,
                    risk_voice_enabled=True,
                    risk_voice_interval_seconds=5,
                    risk_voice_active_ttl_seconds=60,
                ),
            )
            server.risk_voice_announcer = RiskVoiceAnnouncer(
                speaker=lambda text: spoken.append(text) or {"executed": True},
                interval_seconds=5,
                active_ttl_seconds=60,
                async_mode=False,
            )
            try:
                state = server.build_state()
            finally:
                server.server_close()

        self.assertEqual(spoken, ["警报，防护违规：人员缺少安全帽、反光背心。"])
        self.assertTrue(state["risk_voice_alarm"]["announced"])


if __name__ == "__main__":
    unittest.main()

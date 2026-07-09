from __future__ import annotations

import unittest

from dashboard.risk_voice_alarm import RiskVoiceAnnouncer, build_alarm_text, build_ppe_alarm_text


class RiskVoiceAlarmTest(unittest.TestCase):
    def test_builds_alarm_text_from_missing_ppe_reason(self) -> None:
        event = {
            "event_id": "E1",
            "event_type": "ppe_violation",
            "risk_level": "high",
            "timestamp": 100.0,
            "reasons": [
                "rule SCENE_CONSTRUCTION_HELMET: 工地人员缺少安全帽",
                "missing_ppe=helmet, vest",
            ],
        }

        self.assertEqual(build_ppe_alarm_text(event), "警报，防护违规：人员缺少安全帽、反光背心。")

    def test_suppresses_same_violation_for_twenty_seconds_and_announces_new_violation_immediately(self) -> None:
        spoken: list[str] = []
        announcer = RiskVoiceAnnouncer(
            speaker=lambda text: spoken.append(text) or {"executed": True},
            interval_seconds=5,
            same_violation_cooldown_seconds=20,
            active_ttl_seconds=60,
            async_mode=False,
        )
        first_event = {
            "event_id": "E1",
            "event_type": "ppe_violation",
            "risk_level": "high",
            "timestamp": 100.0,
            "reasons": ["missing_ppe=gloves, goggles"],
        }
        same_violation_new_event_id = {
            **first_event,
            "event_id": "E2",
            "timestamp": 106.0,
        }
        new_violation = {
            **first_event,
            "event_id": "E3",
            "timestamp": 107.0,
            "reasons": ["missing_ppe=helmet, vest"],
        }

        first = announcer.maybe_announce([first_event], now=100.0)
        same_too_soon = announcer.maybe_announce([same_violation_new_event_id], now=106.0)
        changed = announcer.maybe_announce([same_violation_new_event_id, new_violation], now=107.0)
        same_after_cooldown = announcer.maybe_announce([same_violation_new_event_id], now=120.0)
        expired = announcer.maybe_announce([same_violation_new_event_id], now=167.0)

        self.assertTrue(first["announced"])
        self.assertFalse(same_too_soon["announced"])
        self.assertEqual(same_too_soon["reason"], "same_violation_cooling_down")
        self.assertTrue(changed["announced"])
        self.assertTrue(same_after_cooldown["announced"])
        self.assertFalse(expired["announced"])
        self.assertEqual(
            spoken,
            [
                "警报，防护违规：人员缺少防护手套、护目镜。",
                "警报，防护违规：人员缺少安全帽、反光背心。",
                "警报，防护违规：人员缺少防护手套、护目镜。",
            ],
        )

    def test_announces_fire_and_smoke_events_too(self) -> None:
        spoken: list[str] = []
        announcer = RiskVoiceAnnouncer(
            speaker=lambda text: spoken.append(text) or {"executed": True},
            interval_seconds=5,
            same_violation_cooldown_seconds=20,
            active_ttl_seconds=60,
            async_mode=False,
        )
        smoke_event = {
            "event_id": "S1",
            "event_type": "smoke",
            "risk_level": "high",
            "timestamp": 100.0,
            "reasons": ["smoke appeared for 3 consecutive frames"],
        }
        fire_event = {
            "event_id": "F1",
            "event_type": "fire",
            "risk_level": "emergency",
            "timestamp": 101.0,
            "reasons": ["fire appeared for 3 consecutive frames"],
        }

        smoke = announcer.maybe_announce([smoke_event], now=100.0)
        fire = announcer.maybe_announce([smoke_event, fire_event], now=101.0)

        self.assertEqual(build_alarm_text(smoke_event), "警报，检测到烟雾风险，请立即复核现场。")
        self.assertTrue(smoke["announced"])
        self.assertTrue(fire["announced"])
        self.assertEqual(
            spoken,
            [
                "警报，检测到烟雾风险，请立即复核现场。",
                "警报，检测到火焰风险，请立即复核现场。",
            ],
        )

    def test_announces_warning_ppe_when_alarm_is_required(self) -> None:
        spoken: list[str] = []
        announcer = RiskVoiceAnnouncer(
            speaker=lambda text: spoken.append(text) or {"executed": True},
            interval_seconds=5,
            same_violation_cooldown_seconds=20,
            active_ttl_seconds=60,
            async_mode=False,
        )
        event = {
            "event_id": "W1",
            "event_type": "ppe_violation",
            "risk_level": "warning",
            "need_alarm": True,
            "timestamp": 100.0,
            "reasons": ["missing_ppe=vest"],
        }

        result = announcer.maybe_announce([event], now=100.0)

        self.assertTrue(result["announced"])
        self.assertEqual(spoken, ["警报，防护违规：人员缺少反光背心。"])


if __name__ == "__main__":
    unittest.main()

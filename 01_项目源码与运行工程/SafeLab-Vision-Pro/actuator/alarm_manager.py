from __future__ import annotations

from runtime.interfaces import AlarmAction, RiskEvent


class AlarmManager:
    def build_action(self, event: RiskEvent) -> AlarmAction:
        if event.action_hint:
            return AlarmAction(
                event_id=event.event_id,
                voice_text=str(event.action_hint.get("voice", "Risk event detected.")),
                led_color=str(event.action_hint.get("led", "yellow")),
                buzzer=bool(event.action_hint.get("buzzer", False)),
                relay=bool(event.action_hint.get("relay", False)),
                snapshot=bool(event.action_hint.get("snapshot", event.need_snapshot)),
                log=bool(event.action_hint.get("log", event.need_log)),
                cooldown_ms=int(event.action_hint.get("cooldown_ms", 20000)),
            )

        if event.event_type == "fire":
            voice_text = "Fire risk detected. Please check the lab immediately."
            led_color = "red"
            buzzer = True
        elif event.event_type == "smoke":
            voice_text = "Smoke risk detected. Please check the lab."
            led_color = "red"
            buzzer = True
        elif event.event_type == "ppe_violation":
            voice_text = "PPE violation detected. Please wear required safety equipment."
            led_color = "yellow" if event.risk_level == "warning" else "red"
            buzzer = event.risk_level in ("high", "emergency")
        else:
            voice_text = "Risk event detected."
            led_color = "yellow"
            buzzer = False

        return AlarmAction(
            event_id=event.event_id,
            voice_text=voice_text,
            led_color=led_color,
            buzzer=buzzer,
            relay=False,
            snapshot=event.need_snapshot,
            log=event.need_log,
            cooldown_ms=20000,
        )

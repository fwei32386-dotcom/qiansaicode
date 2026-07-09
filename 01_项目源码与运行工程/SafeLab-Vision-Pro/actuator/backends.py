from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from runtime.interfaces import AlarmAction


ActuatorBackendName = Literal["mock", "shell", "gpio"]


class ActuatorBackend(Protocol):
    backend_name: str

    def execute(self, action: AlarmAction) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ActuatorPinConfig:
    led_red: int | None = None
    led_yellow: int | None = None
    buzzer: int | None = None
    relay: int | None = None


class JsonlActuatorBackend:
    backend_name = "mock"

    def __init__(self, output_path: str | Path = "data/events/actuator_log.jsonl") -> None:
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def execute(self, action: AlarmAction) -> dict[str, Any]:
        record = _base_record(action, self.backend_name)
        self._write(record)
        return record

    def _write(self, record: dict[str, Any]) -> None:
        with self.output_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class ShellActuatorBackend(JsonlActuatorBackend):
    backend_name = "shell"

    def execute(self, action: AlarmAction) -> dict[str, Any]:
        record = _base_record(action, self.backend_name)
        record["shell_commands"] = _planned_shell_commands(action)
        record["executed"] = False
        record["detail"] = "planned shell actuator commands only; no hardware command executed"
        self._write(record)
        return record


class GpioActuatorBackend(JsonlActuatorBackend):
    backend_name = "gpio"

    def __init__(
        self,
        output_path: str | Path = "data/events/actuator_log.jsonl",
        pin_config: ActuatorPinConfig | None = None,
    ) -> None:
        super().__init__(output_path)
        self.pin_config = pin_config or ActuatorPinConfig()

    def execute(self, action: AlarmAction) -> dict[str, Any]:
        record = _base_record(action, self.backend_name)
        record["pin_config"] = {
            "led_red": self.pin_config.led_red,
            "led_yellow": self.pin_config.led_yellow,
            "buzzer": self.pin_config.buzzer,
            "relay": self.pin_config.relay,
        }
        record["executed"] = False
        record["detail"] = "GPIO backend contract is ready; real pin writes are disabled until wiring is confirmed"
        self._write(record)
        return record


def create_actuator_backend(
    backend: ActuatorBackendName = "mock",
    output_path: str | Path = "data/events/actuator_log.jsonl",
    pin_config: ActuatorPinConfig | None = None,
) -> ActuatorBackend:
    if backend == "mock":
        return JsonlActuatorBackend(output_path)
    if backend == "shell":
        return ShellActuatorBackend(output_path)
    if backend == "gpio":
        return GpioActuatorBackend(output_path, pin_config)
    raise ValueError(f"unsupported actuator backend: {backend}")


def _base_record(action: AlarmAction, backend: str) -> dict[str, Any]:
    return {
        "event_id": action.event_id,
        "timestamp": time.time(),
        "voice": {
            "enabled": bool(action.voice_text),
            "text": action.voice_text,
        },
        "led": {
            "enabled": bool(action.led_color),
            "color": action.led_color,
        },
        "buzzer": {
            "enabled": action.buzzer,
        },
        "relay": {
            "enabled": action.relay,
        },
        "snapshot": action.snapshot,
        "log": action.log,
        "cooldown_ms": action.cooldown_ms,
        "backend": backend,
    }


def _planned_shell_commands(action: AlarmAction) -> list[str]:
    commands: list[str] = []
    if action.led_color:
        commands.append(f"echo led:{action.led_color}")
    if action.buzzer:
        commands.append("echo buzzer:on")
    if action.relay:
        commands.append("echo relay:on")
    if action.voice_text:
        commands.append(f"echo voice:{action.voice_text}")
    return commands

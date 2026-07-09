from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AudioDeviceStatus:
    aplay: str
    cards: list[str]
    default_device: str | None
    speech_backend: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "aplay": self.aplay,
            "cards": self.cards,
            "default_device": self.default_device,
            "speech_backend": self.speech_backend,
        }


def probe_audio_devices() -> AudioDeviceStatus:
    cards = _read_asound_cards()
    return AudioDeviceStatus(
        aplay="ok" if shutil.which("aplay") else "missing",
        cards=cards,
        default_device=_choose_default_device(cards),
        speech_backend=_choose_speech_backend(),
    )


def speak_text(
    text: str,
    log_path: str | Path = "data/events/speech_output.jsonl",
    dry_run: bool = True,
    device: str | None = None,
) -> dict[str, Any]:
    status = probe_audio_devices()
    record: dict[str, Any] = {
        "timestamp": time.time(),
        "text": text,
        "dry_run": dry_run,
        "device": device or status.default_device,
        "audio": status.to_dict(),
        "executed": False,
        "detail": "speech output recorded only",
    }
    if not dry_run:
        record.update(_execute_speech(text, status.speech_backend))
    output = Path(log_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _read_asound_cards() -> list[str]:
    path = Path("/proc/asound/cards")
    if not path.exists():
        return []
    return [line.rstrip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def _choose_default_device(cards: list[str]) -> str | None:
    joined = "\n".join(cards).lower()
    if "usb" in joined:
        return "usb-audio"
    if "nau" in joined:
        return "rockchip-nau8822"
    if "hdmi" in joined:
        return "rockchip-hdmi"
    return None


def _choose_speech_backend() -> str | None:
    if os.environ.get("SAFELAB_SPEAK_CMD"):
        return "custom"
    if shutil.which("espeak-ng"):
        return "espeak-ng"
    if shutil.which("espeak"):
        return "espeak"
    if shutil.which("spd-say"):
        return "spd-say"
    if platform.system().lower() == "windows" and shutil.which("powershell"):
        return "windows-sapi"
    return None


def _execute_speech(text: str, backend: str | None) -> dict[str, Any]:
    command = _speech_command(text, backend)
    if not command:
        return {"executed": False, "detail": "no speech backend found"}
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"executed": False, "detail": str(exc), "command": command}
    return {
        "executed": completed.returncode == 0,
        "detail": completed.stderr.strip() or completed.stdout.strip() or f"{backend} executed",
        "command": command[:4] + ["..."] if len(command) > 4 else command,
        "returncode": completed.returncode,
    }


def _speech_command(text: str, backend: str | None) -> list[str] | None:
    custom = os.environ.get("SAFELAB_SPEAK_CMD")
    if backend == "custom" and custom:
        return custom.format(text=text).split()
    if backend == "espeak-ng":
        return ["espeak-ng", "-v", "zh", text]
    if backend == "espeak":
        return ["espeak", "-v", "zh", text]
    if backend == "spd-say":
        return ["spd-say", text]
    if backend == "windows-sapi":
        script = "$speaker = New-Object -ComObject SAPI.SpVoice; $speaker.Speak($args[0]) | Out-Null"
        return ["powershell", "-NoProfile", "-Command", script, text]
    return None

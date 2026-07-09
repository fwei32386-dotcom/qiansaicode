from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

import paramiko


PPE_LABELS = {
    "helmet": "安全帽",
    "vest": "反光背心",
    "goggles": "护目镜",
    "gloves": "防护手套",
    "mask": "口罩",
    "protective_suit": "防护服",
}


class RiskVoiceAnnouncer:
    def __init__(
        self,
        speaker: Callable[[str], dict[str, Any]],
        *,
        interval_seconds: float = 5.0,
        same_violation_cooldown_seconds: float = 20.0,
        active_ttl_seconds: float = 60.0,
        async_mode: bool = True,
    ) -> None:
        self.speaker = speaker
        self.interval_seconds = interval_seconds
        self.same_violation_cooldown_seconds = same_violation_cooldown_seconds
        self.active_ttl_seconds = active_ttl_seconds
        self.async_mode = async_mode
        self._lock = threading.Lock()
        self._last_spoken_at = 0.0
        self._last_text = ""
        self._last_signature_spoken_at: dict[str, float] = {}
        self._in_flight = False
        self.last_result: dict[str, Any] = {"announced": False, "reason": "not_started"}

    def maybe_announce(self, events: list[dict[str, Any]], *, now: float | None = None) -> dict[str, Any]:
        current_time = time.time() if now is None else now
        event = latest_active_alarm_event(events, now=current_time, ttl_seconds=self.active_ttl_seconds)
        if not event:
            return self._record({"announced": False, "reason": "no_active_alarm_event"})
        text = build_alarm_text(event)
        if not text:
            return self._record({"announced": False, "reason": "empty_alarm_text"})
        signature = alarm_event_signature(event)
        with self._lock:
            if text == self._last_text and current_time - self._last_spoken_at < self.interval_seconds:
                return self._record({"announced": False, "reason": "interval_not_reached", "text": text})
            signature_last_spoken = self._last_signature_spoken_at.get(signature, 0.0)
            if current_time - signature_last_spoken < self.same_violation_cooldown_seconds:
                return self._record(
                    {
                        "announced": False,
                        "reason": "same_violation_cooling_down",
                        "text": text,
                        "signature": signature,
                    }
                )
            if self._in_flight:
                return self._record({"announced": False, "reason": "speaker_busy", "text": text})
            self._last_spoken_at = current_time
            self._last_text = text
            self._last_signature_spoken_at[signature] = current_time
            self._in_flight = True
        if self.async_mode:
            threading.Thread(target=self._speak_and_record, args=(text, event), daemon=True).start()
            return self._record(
                {"announced": True, "text": text, "event_id": event.get("event_id"), "signature": signature, "async": True}
            )
        result = self._speak_and_record(text, event)
        return {
            "announced": True,
            "text": text,
            "event_id": event.get("event_id"),
            "signature": signature,
            "speaker": result,
        }

    def _speak_and_record(self, text: str, event: dict[str, Any]) -> dict[str, Any]:
        try:
            result = self.speaker(text)
        except Exception as exc:  # noqa: BLE001 - speech failures must not break dashboard refresh.
            result = {"executed": False, "error": str(exc)}
        finally:
            with self._lock:
                self._in_flight = False
        return self._record(
            {
                "announced": True,
                "text": text,
                "event_id": event.get("event_id"),
                "speaker": result,
            }
        )

    def _record(self, result: dict[str, Any]) -> dict[str, Any]:
        self.last_result = dict(result)
        return self.last_result


class BoardSpeaker:
    def __init__(
        self,
        *,
        host: str,
        username: str,
        password: str,
        log_path: str | Path,
        remote_wav_path: str = "/root/safelab_audio/latest_alarm.wav",
        audio_device: str = "plughw:1,0",
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.log_path = Path(log_path)
        self.remote_wav_path = remote_wav_path
        self.audio_device = audio_device

    def __call__(self, text: str) -> dict[str, Any]:
        started = time.time()
        record: dict[str, Any] = {
            "timestamp": started,
            "speech_source": "risk_voice_alarm",
            "text": text,
            "dry_run": False,
            "device": self.audio_device,
            "board_host": self.host,
            "executed": False,
        }
        try:
            wav_path = synthesize_text_to_wav(text)
            remote_result = self._upload_and_play(wav_path)
            record.update(remote_result)
        except Exception as exc:  # noqa: BLE001 - keep alarm logging even if playback fails.
            record.update({"executed": False, "detail": str(exc)})
        record["elapsed_seconds"] = round(time.time() - started, 3)
        self._append_record(record)
        return record

    def _upload_and_play(self, wav_path: Path) -> dict[str, Any]:
        remote_dir = os.path.dirname(self.remote_wav_path) or "/root"
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            self.host,
            username=self.username,
            password=self.password,
            timeout=8,
            banner_timeout=8,
            auth_timeout=8,
            look_for_keys=False,
            allow_agent=False,
        )
        try:
            stdin, stdout, stderr = client.exec_command(f"mkdir -p {remote_dir}", get_pty=True, timeout=8)
            stdout.read()
            stderr.read()
            sftp = client.open_sftp()
            try:
                sftp.put(str(wav_path), self.remote_wav_path)
            finally:
                sftp.close()
            command = (
                "if [ -x /root/safelab_audio/enable_speaker_route.sh ]; "
                "then /root/safelab_audio/enable_speaker_route.sh >/dev/null 2>&1; fi; "
                f"aplay -D {self.audio_device} {self.remote_wav_path}"
            )
            stdin, stdout, stderr = client.exec_command(command, get_pty=True, timeout=20)
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            exit_status = stdout.channel.recv_exit_status()
            return {
                "executed": exit_status == 0,
                "detail": err or out or "board speaker played",
                "returncode": exit_status,
                "remote_wav_path": self.remote_wav_path,
            }
        finally:
            client.close()

    def _append_record(self, record: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def latest_active_ppe_event(
    events: list[dict[str, Any]],
    *,
    now: float,
    ttl_seconds: float,
) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("event_type") != "ppe_violation":
            continue
        if event.get("risk_level") not in {"high", "emergency"}:
            continue
        timestamp = _event_timestamp(event)
        if timestamp is not None and now - timestamp > ttl_seconds:
            continue
        return event
    return None


def latest_active_alarm_event(
    events: list[dict[str, Any]],
    *,
    now: float,
    ttl_seconds: float,
) -> dict[str, Any] | None:
    for event in reversed(events):
        event_type = str(event.get("event_type", ""))
        if event_type not in {"ppe_violation", "fire", "smoke"}:
            continue
        if event_type == "ppe_violation":
            if event.get("need_alarm") is False:
                continue
        elif event.get("risk_level") not in {"high", "emergency"}:
            continue
        timestamp = _event_timestamp(event)
        if timestamp is not None and now - timestamp > ttl_seconds:
            continue
        return event
    return None


def build_alarm_text(event: dict[str, Any]) -> str:
    event_type = str(event.get("event_type", ""))
    if event_type == "ppe_violation":
        return build_ppe_alarm_text(event)
    if event_type == "fire":
        return "警报，检测到火焰风险，请立即复核现场。"
    if event_type == "smoke":
        return "警报，检测到烟雾风险，请立即复核现场。"
    return ""


def build_ppe_alarm_text(event: dict[str, Any]) -> str:
    missing = _missing_ppe_labels(event)
    if missing:
        return "警报，防护违规：人员缺少" + "、".join(missing) + "。"
    action_hint = event.get("action_hint")
    if isinstance(action_hint, dict):
        voice = str(action_hint.get("voice", "")).strip()
        if voice:
            return "警报，防护违规：" + _normalize_sentence(voice)
    reasons = event.get("reasons")
    if isinstance(reasons, list):
        for reason in reasons:
            value = str(reason).strip()
            if "缺少" in value:
                return "警报，防护违规：" + _normalize_sentence(value.split(":", 1)[-1].strip())
    return ""


def ppe_violation_signature(event: dict[str, Any]) -> str:
    missing = _missing_ppe_keys(event)
    if missing:
        return "ppe:" + ",".join(sorted(missing))
    return "ppe:" + build_ppe_alarm_text(event)


def alarm_event_signature(event: dict[str, Any]) -> str:
    event_type = str(event.get("event_type", ""))
    if event_type == "ppe_violation":
        return ppe_violation_signature(event)
    return event_type


def synthesize_text_to_wav(text: str) -> Path:
    custom = os.environ.get("SAFELAB_TTS_WAV_CMD")
    output = Path(tempfile.gettempdir()) / "safelab_alarm_tts.wav"
    if custom:
        subprocess.run(custom.format(text=text, output=str(output)), shell=True, check=True, timeout=20)
        return output
    if platform.system().lower() == "windows" and shutil.which("powershell"):
        script_path = Path(tempfile.gettempdir()) / "safelab_tts_to_wav.ps1"
        script_path.write_text(
            "\n".join(
                [
                    "param([string]$Text, [string]$Output)",
                    "Add-Type -AssemblyName System.Speech",
                    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
                    "$s.Volume = 100",
                    "$s.Rate = 2",
                    "$s.SetOutputToWaveFile($Output)",
                    "$s.Speak($Text)",
                    "$s.Dispose()",
                ]
            )
            + "\n",
            encoding="utf-8-sig",
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), text, str(output)],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=20,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "PowerShell TTS failed").strip()
            raise RuntimeError(detail)
        return output
    raise RuntimeError("no TTS wav backend found; set SAFELAB_TTS_WAV_CMD or run dashboard on Windows")


def _missing_ppe_labels(event: dict[str, Any]) -> list[str]:
    return [PPE_LABELS.get(key, key) for key in _missing_ppe_keys(event)]


def _missing_ppe_keys(event: dict[str, Any]) -> list[str]:
    reasons = event.get("reasons")
    if not isinstance(reasons, list):
        return []
    for reason in reasons:
        value = str(reason)
        if "missing_ppe=" not in value:
            continue
        raw = value.split("missing_ppe=", 1)[1].split(";", 1)[0]
        labels = []
        for item in raw.split(","):
            key = item.strip()
            if not key:
                continue
            labels.append(key)
        return labels
    return []


def _event_timestamp(event: dict[str, Any]) -> float | None:
    try:
        return float(event["timestamp"])
    except (KeyError, TypeError, ValueError):
        return None


def _normalize_sentence(value: str) -> str:
    text = value.strip().rstrip("。.")
    return text + "。"

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MODEL_DETECTION = Path("data/runtime/model_detection.json")
DEFAULT_CAMERA_FPS = 15.0
DEFAULT_INTERVAL_FRAMES = 75
MIN_INTERVAL_FRAMES = 1
MAX_INTERVAL_FRAMES = 900


def build_model_detection_state(
    model_detection_path: str | Path = DEFAULT_MODEL_DETECTION,
) -> dict[str, Any]:
    return {"model_detection": _read_model_detection(Path(model_detection_path))}


def save_model_detection(
    enabled: object,
    interval_frames: object,
    model_detection_path: str | Path = DEFAULT_MODEL_DETECTION,
) -> dict[str, Any]:
    state = _model_detection_state(enabled=enabled, interval_frames=interval_frames)
    output = Path(model_detection_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"model_detection": state}


def _read_model_detection(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return _model_detection_state(
                enabled=payload.get("enabled", True),
                interval_frames=payload.get("interval_frames", _seconds_to_frames(payload.get("interval_seconds", 5.0))),
                updated_at=payload.get("updated_at"),
            )
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    return _model_detection_state(enabled=True, interval_frames=DEFAULT_INTERVAL_FRAMES)


def _model_detection_state(
    *,
    enabled: object,
    interval_frames: object,
    updated_at: object | None = None,
) -> dict[str, Any]:
    interval = int(float(interval_frames))
    if interval < MIN_INTERVAL_FRAMES or interval > MAX_INTERVAL_FRAMES:
        raise ValueError(f"interval_frames must be between {MIN_INTERVAL_FRAMES:g} and {MAX_INTERVAL_FRAMES:g}")
    return {
        "enabled": _coerce_enabled(enabled),
        "interval_frames": interval,
        "interval_seconds": round(interval / DEFAULT_CAMERA_FPS, 3),
        "models": ["ppe", "fire_smoke"],
        "updated_at": str(updated_at) if updated_at else datetime.now(timezone.utc).isoformat(),
    }


def _seconds_to_frames(value: object) -> int:
    return int(round(float(value) * DEFAULT_CAMERA_FPS))


def _coerce_enabled(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("1", "true", "yes", "on", "enabled"):
            return True
        if lowered in ("0", "false", "no", "off", "disabled"):
            return False
    return bool(value)

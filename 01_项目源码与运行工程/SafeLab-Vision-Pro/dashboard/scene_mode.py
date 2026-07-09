from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SCENE_MODE = Path("data/runtime/scene_mode.json")

SCENE_MODES: dict[str, dict[str, Any]] = {
    "construction": {
        "label": "工地",
        "required_ppe": ["helmet", "vest"],
        "required_ppe_labels": ["安全帽", "反光背心"],
    },
    "lab": {
        "label": "实验室",
        "required_ppe": ["goggles", "gloves"],
        "required_ppe_labels": ["护目镜", "防护手套"],
    },
}


def build_scene_mode_state(scene_mode_path: str | Path = DEFAULT_SCENE_MODE) -> dict[str, Any]:
    return {"scene_mode": _read_scene_mode(Path(scene_mode_path))}


def save_scene_mode(mode: object, scene_mode_path: str | Path = DEFAULT_SCENE_MODE) -> dict[str, Any]:
    state = _scene_mode_state(str(mode))
    output = Path(scene_mode_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"scene_mode": state}


def _read_scene_mode(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return _scene_mode_state(str(payload.get("mode", "construction")), updated_at=payload.get("updated_at"))
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    return _scene_mode_state("construction")


def _scene_mode_state(mode: str, updated_at: object | None = None) -> dict[str, Any]:
    normalized = mode.strip().lower()
    if normalized not in SCENE_MODES:
        raise ValueError(f"unknown scene mode: {mode}")
    config = SCENE_MODES[normalized]
    return {
        "mode": normalized,
        "label": config["label"],
        "required_ppe": list(config["required_ppe"]),
        "required_ppe_labels": list(config["required_ppe_labels"]),
        "updated_at": str(updated_at) if updated_at else datetime.now(timezone.utc).isoformat(),
    }

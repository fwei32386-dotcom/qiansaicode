from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_VIDEO_CONFIG = Path("configs/video_config.yaml")
DEFAULT_INPUT_SOURCE = Path("data/runtime/input_source.json")


def build_input_source_state(
    video_config_path: str | Path = DEFAULT_VIDEO_CONFIG,
    input_source_path: str | Path = DEFAULT_INPUT_SOURCE,
) -> dict[str, Any]:
    resolved = resolve_input_source(video_config_path, input_source_path)
    return {
        "input_source": resolved["input_source"],
        "available_input_sources": resolved["available_input_sources"],
    }


def resolve_input_source(
    video_config_path: str | Path = DEFAULT_VIDEO_CONFIG,
    input_source_path: str | Path = DEFAULT_INPUT_SOURCE,
) -> dict[str, Any]:
    config = _read_video_sources(Path(video_config_path))
    available = _available_sources(config)
    selected = _read_selected_source(Path(input_source_path), config)
    selected_id = str(selected["selected_source"])
    source_config = dict(_selectable_sources(config)[selected_id])
    if selected.get("path"):
        source_config["path"] = str(selected["path"])
    if selected.get("board_path"):
        source_config["board_path"] = str(selected["board_path"])
    if selected.get("media_type"):
        source_config["media_type"] = str(selected["media_type"])
    for key in ("width", "height", "fps"):
        if selected.get(key) is not None:
            source_config[key] = str(selected[key])
    return {
        "input_source": selected,
        "available_input_sources": available,
        "source_config": source_config,
    }


def save_input_source(
    selected_source: str,
    video_config_path: str | Path = DEFAULT_VIDEO_CONFIG,
    input_source_path: str | Path = DEFAULT_INPUT_SOURCE,
    source_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    config = _read_video_sources(Path(video_config_path))
    sources = _selectable_sources(config)
    if selected_source not in sources:
        raise ValueError(f"unknown input source: {selected_source}")

    source = dict(sources[selected_source])
    if not source_overrides:
        previous = _read_selected_source(Path(input_source_path), config)
        if previous.get("selected_source") == selected_source:
            for key in ("path", "board_path", "media_type", "width", "height", "fps"):
                if previous.get(key) is not None:
                    source[key] = str(previous[key])
    if source_overrides:
        source.update(source_overrides)
    state = _source_state(selected_source, source)
    output = Path(input_source_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Write only after validation so an invalid request cannot clobber the current source.
    output.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "input_source": state,
        "available_input_sources": _available_sources(config),
    }


def _read_selected_source(input_source_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    sources = _selectable_sources(config)
    default_id = config["default"]
    if input_source_path.exists():
        try:
            payload = json.loads(input_source_path.read_text(encoding="utf-8"))
            selected = str(payload.get("selected_source", ""))
            if selected in sources:
                source = dict(sources[selected])
                if payload.get("path"):
                    source["path"] = str(payload["path"])
                if payload.get("board_path"):
                    source["board_path"] = str(payload["board_path"])
                if payload.get("media_type"):
                    source["media_type"] = str(payload["media_type"])
                for key in ("width", "height", "fps"):
                    if payload.get(key) is not None:
                        source[key] = str(payload[key])
                return _source_state(selected, source, updated_at=payload.get("updated_at"))
        except (json.JSONDecodeError, OSError):
            pass

    # Missing or malformed runtime state falls back to the config default.
    fallback = default_id if default_id in sources else next(iter(sources), "camera_ov13855")
    return _source_state(fallback, sources.get(fallback, {"source_type": "camera"}))


def _source_state(source_id: str, source: dict[str, str], updated_at: object | None = None) -> dict[str, Any]:
    source_type = str(source.get("source_type", "camera"))
    state = {
        "selected_source": source_id,
        "label": _label_for_source(source_id, source_type),
        "source_type": source_type,
        "requires_restart": True,
        "updated_at": str(updated_at) if updated_at else datetime.now(timezone.utc).isoformat(),
    }
    if source.get("path"):
        state["path"] = str(source["path"])
    if source_type == "board_file" and source.get("board_path"):
        state["board_path"] = str(source["board_path"])
    if source_type == "board_file" and source.get("media_type"):
        state["media_type"] = str(source["media_type"])
    for key in ("width", "height", "fps"):
        if source.get(key) not in (None, ""):
            try:
                state[key] = int(float(str(source[key])))
            except ValueError:
                pass
    return state


def _available_sources(config: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for source_id, source in _selectable_sources(config).items():
        source_type = str(source.get("source_type", source_id))
        if source_type == "file":
            continue
        items.append(
            {
                "id": source_id,
                "label": _label_for_source(source_id, source_type),
                "source_type": source_type,
            }
        )
    return items


def _selectable_sources(config: dict[str, Any]) -> dict[str, Any]:
    return {
        source_id: source
        for source_id, source in config["sources"].items()
        if str(source.get("source_type", source_id)) in {"camera", "file", "board_file"}
    }


def _label_for_source(source_id: str, source_type: str) -> str:
    if source_type == "board_file":
        return "本地视频"
    if source_type == "file":
        return "本地输入"
    if source_type == "camera" or "camera" in source_id.lower():
        return "摄像头输入"
    return source_id


def _read_video_sources(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"default": "camera_ov13855", "sources": {"camera_ov13855": {"source_type": "camera"}}}

    default = "camera_ov13855"
    sources: dict[str, dict[str, str]] = {}
    current_id: str | None = None
    in_video_sources = False
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if indent == 0:
            in_video_sources = stripped == "video_sources:"
            current_id = None
            continue
        if not in_video_sources:
            continue
        if indent == 2 and stripped.startswith("default:"):
            default = stripped.split(":", 1)[1].strip()
            current_id = None
            continue
        if indent == 2 and stripped.endswith(":"):
            current_id = stripped[:-1]
            sources[current_id] = {}
            continue
        if indent >= 4 and current_id and ":" in stripped:
            key, value = stripped.split(":", 1)
            sources[current_id][key.strip()] = value.strip()

    if not sources:
        sources["camera_ov13855"] = {"source_type": "camera"}
    return {"default": default, "sources": sources}

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from dashboard.input_source import resolve_input_source


@dataclass(frozen=True)
class ActiveFrameSource:
    key: str
    source_type: str
    label: str
    frame_url: str | None = None
    status_url: str | None = None
    path: Path | None = None
    board_path: str | None = None
    source_name: str | None = None
    fps: int | None = None
    width: int | None = None
    height: int | None = None
    media_type: str | None = None


def build_active_frame_source(
    *,
    video_config_path: str | Path,
    input_source_path: str | Path,
    camera_frame_url: str,
    camera_status_url: str,
) -> ActiveFrameSource:
    resolved = resolve_input_source(video_config_path, input_source_path)
    state = resolved["input_source"]
    source_config = resolved["source_config"]
    source_type = str(source_config.get("source_type", state.get("source_type", "camera")))
    key = str(state["selected_source"])

    if source_type == "camera":
        return ActiveFrameSource(
            key=key,
            source_type="camera",
            label=str(state.get("label", key)),
            frame_url=camera_frame_url,
            status_url=camera_status_url,
            source_name=str(source_config.get("source_name", key)),
            fps=_optional_int(source_config.get("fps")),
        )

    if source_type == "file":
        raw_path = str(source_config.get("path", "")).strip()
        if not raw_path:
            raise ValueError(f"file input source {key} is missing path")
        return ActiveFrameSource(
            key=key,
            source_type="file",
            label=str(state.get("label", key)),
            path=_resolve_path(raw_path, Path(video_config_path)),
            source_name=str(source_config.get("source_name", key)),
            fps=_optional_int(source_config.get("fps")),
        )

    if source_type == "board_file":
        board_path = str(source_config.get("board_path", "")).strip()
        if not board_path:
            raise ValueError(f"board file input source {key} is missing board_path")
        raw_path = str(source_config.get("path", "")).strip()
        return ActiveFrameSource(
            key=key,
            source_type="board_file",
            label=str(state.get("label", key)),
            path=_resolve_path(raw_path, Path(video_config_path)) if raw_path else None,
            board_path=board_path,
            source_name=str(source_config.get("source_name", key)),
            fps=_optional_int(source_config.get("fps")),
            width=_optional_int(source_config.get("width")),
            height=_optional_int(source_config.get("height")),
            media_type=str(source_config.get("media_type", "video")),
        )

    raise ValueError(f"unsupported input source type: {source_type}")


def _resolve_path(raw_path: str, video_config_path: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    config_relative = (video_config_path.parent / path).resolve()
    if config_relative.exists():
        return config_relative
    return (ROOT / path).resolve()


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except ValueError:
        return None

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_engine.json_detection_loader import _detection_from_dict
from runtime.interfaces import Detection


@dataclass(frozen=True)
class DetectionFrame:
    frame_id: int
    timestamp: float
    detections: list[Detection]


def load_timeline(path: str | Path) -> list[DetectionFrame]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_frames = payload.get("frames")
    if not isinstance(raw_frames, list):
        raise ValueError("timeline JSON must contain a frames list")
    return [_frame_from_dict(item) for item in raw_frames]


def _frame_from_dict(payload: dict[str, Any]) -> DetectionFrame:
    frame_id = int(payload["frame_id"])
    timestamp = float(payload.get("timestamp", frame_id))
    detections = [_detection_from_dict(item) for item in payload.get("detections", [])]
    return DetectionFrame(frame_id=frame_id, timestamp=timestamp, detections=detections)


from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.interfaces import Detection


def load_detections_from_json(path: str | Path) -> list[Detection]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_detections = payload.get("detections")
    if not isinstance(raw_detections, list):
        raise ValueError("scenario JSON must contain a detections list")

    return [_detection_from_dict(item) for item in raw_detections]


def _detection_from_dict(payload: dict[str, Any]) -> Detection:
    required = {
        "frame_id",
        "source_type",
        "class_name",
        "confidence",
        "bbox",
        "center",
        "area",
        "model_name",
        "infer_time_ms",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"detection missing required fields: {', '.join(missing)}")

    return Detection(
        frame_id=int(payload["frame_id"]),
        source_type=payload["source_type"],
        class_name=payload["class_name"],
        confidence=float(payload["confidence"]),
        bbox=[int(v) for v in payload["bbox"]],
        center=[int(v) for v in payload["center"]],
        area=int(payload["area"]),
        model_name=str(payload["model_name"]),
        infer_time_ms=float(payload["infer_time_ms"]),
    )


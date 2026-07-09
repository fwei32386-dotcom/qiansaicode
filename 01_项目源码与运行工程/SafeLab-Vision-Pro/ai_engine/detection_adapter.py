from __future__ import annotations

from typing import Any

from runtime.interfaces import ClassName, Detection, VideoFrame


DEFAULT_LABELS: tuple[ClassName, ...] = (
    "person",
    "helmet",
    "vest",
    "goggles",
    "gloves",
    "fire",
    "smoke",
)


def adapt_model_outputs(
    outputs: list[dict[str, Any] | list[float] | tuple[float, ...]],
    frame: VideoFrame,
    labels: list[str] | tuple[str, ...] = DEFAULT_LABELS,
    model_name: str = "safelab_detector",
    infer_time_ms: float = 0.0,
    min_confidence: float = 0.0,
) -> list[Detection]:
    detections: list[Detection] = []
    for item in outputs:
        parsed = _parse_output(item)
        if parsed["confidence"] < min_confidence:
            continue
        class_name = _label_from_id(parsed["class_id"], labels)
        bbox = _clip_bbox(parsed["bbox"], frame.width, frame.height)
        if bbox is None:
            continue
        x1, y1, x2, y2 = bbox
        detections.append(
            Detection(
                frame_id=frame.frame_id,
                source_type=frame.source_type,
                class_name=class_name,
                confidence=parsed["confidence"],
                bbox=bbox,
                center=[(x1 + x2) // 2, (y1 + y2) // 2],
                area=(x2 - x1) * (y2 - y1),
                model_name=model_name,
                infer_time_ms=infer_time_ms,
            )
        )
    return detections


def _parse_output(item: dict[str, Any] | list[float] | tuple[float, ...]) -> dict[str, Any]:
    if isinstance(item, dict):
        bbox = item.get("bbox")
        confidence = item.get("confidence", item.get("score"))
        class_id = item.get("class_id", item.get("label_id"))
    else:
        if len(item) < 6:
            raise ValueError("model output list must be [x1, y1, x2, y2, confidence, class_id]")
        bbox = item[:4]
        confidence = item[4]
        class_id = item[5]

    if bbox is None or confidence is None or class_id is None:
        raise ValueError("model output must contain bbox, confidence/score, and class_id/label_id")

    return {
        "bbox": [float(value) for value in bbox],
        "confidence": float(confidence),
        "class_id": int(class_id),
    }


def _label_from_id(class_id: int, labels: list[str] | tuple[str, ...]) -> ClassName:
    if class_id < 0 or class_id >= len(labels):
        raise ValueError(f"class_id {class_id} is outside labels range 0..{len(labels) - 1}")
    label = labels[class_id]
    if label not in DEFAULT_LABELS:
        raise ValueError(f"unsupported class label: {label}")
    return label  # type: ignore[return-value]


def _clip_bbox(bbox: list[float], width: int, height: int) -> list[int] | None:
    if len(bbox) != 4:
        raise ValueError("bbox must contain four values")
    x1, y1, x2, y2 = bbox
    x1_i = max(0, min(int(round(x1)), width - 1))
    y1_i = max(0, min(int(round(y1)), height - 1))
    x2_i = max(0, min(int(round(x2)), width - 1))
    y2_i = max(0, min(int(round(y2)), height - 1))
    if x2_i <= x1_i or y2_i <= y1_i:
        return None
    return [x1_i, y1_i, x2_i, y2_i]

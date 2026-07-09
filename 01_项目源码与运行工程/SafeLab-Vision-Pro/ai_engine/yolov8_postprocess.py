from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class LetterboxMeta:
    source_width: int
    source_height: int
    input_width: int = 640
    input_height: int = 640

    @property
    def scale(self) -> float:
        return min(self.input_width / self.source_width, self.input_height / self.source_height)

    @property
    def pad_x(self) -> float:
        return (self.input_width - self.source_width * self.scale) / 2

    @property
    def pad_y(self) -> float:
        return (self.input_height - self.source_height * self.scale) / 2


def dequantize_int8(values: Sequence[int], zero_point: int, scale: float) -> list[float]:
    return [(int(value) - zero_point) * scale for value in values]


def postprocess_yolov8_output(
    output: Sequence[Sequence[float]] | Sequence[float],
    source_width: int,
    source_height: int,
    input_width: int = 640,
    input_height: int = 640,
    num_classes: int = 7,
    confidence_threshold: float = 0.25,
    nms_iou_threshold: float = 0.45,
) -> list[list[float]]:
    channels = 4 + num_classes
    matrix = _as_channel_major(output, channels)
    meta = LetterboxMeta(
        source_width=source_width,
        source_height=source_height,
        input_width=input_width,
        input_height=input_height,
    )

    candidates: list[list[float]] = []
    anchor_count = len(matrix[0])
    for anchor_index in range(anchor_count):
        cx = matrix[0][anchor_index]
        cy = matrix[1][anchor_index]
        w = matrix[2][anchor_index]
        h = matrix[3][anchor_index]
        class_scores = [matrix[4 + class_id][anchor_index] for class_id in range(num_classes)]
        class_id, confidence = max(enumerate(class_scores), key=lambda item: item[1])
        if confidence < confidence_threshold:
            continue
        bbox = _xywh_to_source_xyxy(cx, cy, w, h, meta)
        if bbox is None:
            continue
        candidates.append([*bbox, confidence, float(class_id)])

    return nms(candidates, nms_iou_threshold)


def postprocess_yolov8_int8_output(
    output: Sequence[Sequence[int]] | Sequence[int],
    source_width: int,
    source_height: int,
    zero_point: int,
    scale: float,
    input_width: int = 640,
    input_height: int = 640,
    num_classes: int = 7,
    confidence_threshold: float = 0.25,
    nms_iou_threshold: float = 0.45,
) -> list[list[float]]:
    channels = 4 + num_classes
    matrix = _as_channel_major(output, channels)
    dequantized = [dequantize_int8(channel, zero_point, scale) for channel in matrix]
    return postprocess_yolov8_output(
        dequantized,
        source_width=source_width,
        source_height=source_height,
        input_width=input_width,
        input_height=input_height,
        num_classes=num_classes,
        confidence_threshold=confidence_threshold,
        nms_iou_threshold=nms_iou_threshold,
    )


def nms(boxes: list[list[float]], iou_threshold: float) -> list[list[float]]:
    selected: list[list[float]] = []
    remaining = sorted(boxes, key=lambda box: box[4], reverse=True)
    while remaining:
        current = remaining.pop(0)
        selected.append(current)
        remaining = [
            box
            for box in remaining
            if int(box[5]) != int(current[5]) or _iou_xyxy(box[:4], current[:4]) <= iou_threshold
        ]
    return selected


def _as_channel_major(
    output: Sequence[Sequence[float]] | Sequence[float] | Sequence[Sequence[int]] | Sequence[int],
    channels: int,
) -> list[list[float]]:
    if not output:
        return [[] for _ in range(channels)]

    first = output[0]  # type: ignore[index]
    if isinstance(first, (list, tuple)):
        rows = [list(row) for row in output]  # type: ignore[arg-type]
        if len(rows) == 1 and rows and isinstance(rows[0][0], (list, tuple)):
            rows = [list(row) for row in rows[0]]  # type: ignore[list-item]
        if len(rows) != channels:
            raise ValueError(f"YOLOv8 output must have {channels} channels, got {len(rows)}")
        return [[float(value) for value in row] for row in rows]

    flat = [float(value) for value in output]  # type: ignore[arg-type]
    if len(flat) % channels != 0:
        raise ValueError(f"flat YOLOv8 output length must be divisible by {channels}")
    anchor_count = len(flat) // channels
    return [flat[channel * anchor_count : (channel + 1) * anchor_count] for channel in range(channels)]


def _xywh_to_source_xyxy(cx: float, cy: float, w: float, h: float, meta: LetterboxMeta) -> list[float] | None:
    x1 = (cx - w / 2 - meta.pad_x) / meta.scale
    y1 = (cy - h / 2 - meta.pad_y) / meta.scale
    x2 = (cx + w / 2 - meta.pad_x) / meta.scale
    y2 = (cy + h / 2 - meta.pad_y) / meta.scale

    x1 = max(0.0, min(x1, float(meta.source_width - 1)))
    y1 = max(0.0, min(y1, float(meta.source_height - 1)))
    x2 = max(0.0, min(x2, float(meta.source_width - 1)))
    y2 = max(0.0, min(y2, float(meta.source_height - 1)))
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]


def _iou_xyxy(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(ix2 - ix1, 0.0)
    ih = max(iy2 - iy1, 0.0)
    intersection = iw * ih
    area_a = max(ax2 - ax1, 0.0) * max(ay2 - ay1, 0.0)
    area_b = max(bx2 - bx1, 0.0) * max(by2 - by1, 0.0)
    union = area_a + area_b - intersection
    if union <= 0:
        return 0.0
    return intersection / union

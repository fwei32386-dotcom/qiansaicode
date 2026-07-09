from __future__ import annotations

from dataclasses import dataclass

from runtime.interfaces import Detection, PersonTrack, ROIRegion, VideoFrame


@dataclass(frozen=True)
class ROIStats:
    roi_count: int
    frame_area: int
    roi_area: int

    @property
    def area_ratio(self) -> float:
        if self.frame_area <= 0:
            return 0.0
        return min(self.roi_area / self.frame_area, 1.0)

    @property
    def estimated_saved_ratio(self) -> float:
        return max(1.0 - self.area_ratio, 0.0)

    def to_dict(self) -> dict[str, float | int]:
        return {
            "roi_count": self.roi_count,
            "frame_area": self.frame_area,
            "roi_area": self.roi_area,
            "area_ratio": round(self.area_ratio, 6),
            "estimated_saved_ratio": round(self.estimated_saved_ratio, 6),
        }


class ROIManager:
    def __init__(self, margin_ratio: float = 0.2, min_size: int = 32) -> None:
        self.margin_ratio = max(margin_ratio, 0.0)
        self.min_size = max(min_size, 1)

    def build_roi(
        self,
        frame: VideoFrame,
        source_bbox: list[int],
        reason: str,
        roi_id: str | None = None,
        margin_ratio: float | None = None,
        source_track_id: int | None = None,
    ) -> ROIRegion:
        margin = self.margin_ratio if margin_ratio is None else max(margin_ratio, 0.0)
        roi_bbox = self.expand_and_clip(source_bbox, frame.width, frame.height, margin)
        return ROIRegion(
            roi_id=roi_id or _roi_id(frame.frame_id, roi_bbox, source_track_id),
            frame_id=frame.frame_id,
            bbox=roi_bbox,
            source_bbox=list(source_bbox),
            frame_width=frame.width,
            frame_height=frame.height,
            reason=reason,
            margin_ratio=margin,
            source_track_id=source_track_id,
        )

    def build_rois_from_tracks(
        self,
        frame: VideoFrame,
        tracks: list[PersonTrack],
        only_risky: bool = True,
    ) -> list[ROIRegion]:
        rois: list[ROIRegion] = []
        for track in tracks:
            if only_risky and track.risk_state == "normal" and track.ppe_status == "ok":
                continue
            rois.append(
                self.build_roi(
                    frame=frame,
                    source_bbox=track.bbox,
                    reason=f"track:{track.track_id}:{track.risk_state}:{track.ppe_status}",
                    source_track_id=track.track_id,
                )
            )
        return rois

    def expand_and_clip(
        self,
        bbox: list[int],
        frame_width: int,
        frame_height: int,
        margin_ratio: float | None = None,
    ) -> list[int]:
        if frame_width <= 0 or frame_height <= 0:
            return [0, 0, 0, 0]

        x1, y1, x2, y2 = _normalize_bbox(bbox)
        margin = self.margin_ratio if margin_ratio is None else max(margin_ratio, 0.0)
        width = max(x2 - x1, self.min_size)
        height = max(y2 - y1, self.min_size)
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        expanded_w = width * (1.0 + margin * 2.0)
        expanded_h = height * (1.0 + margin * 2.0)

        rx1 = round(cx - expanded_w / 2.0)
        ry1 = round(cy - expanded_h / 2.0)
        rx2 = round(cx + expanded_w / 2.0)
        ry2 = round(cy + expanded_h / 2.0)

        return [
            _clamp(rx1, 0, frame_width),
            _clamp(ry1, 0, frame_height),
            _clamp(rx2, 0, frame_width),
            _clamp(ry2, 0, frame_height),
        ]

    def map_detection_to_global(self, detection: Detection, roi: ROIRegion) -> Detection:
        x1, y1, x2, y2 = detection.bbox
        ox, oy = roi.bbox[0], roi.bbox[1]
        global_bbox = [
            _clamp(x1 + ox, 0, roi.frame_width),
            _clamp(y1 + oy, 0, roi.frame_height),
            _clamp(x2 + ox, 0, roi.frame_width),
            _clamp(y2 + oy, 0, roi.frame_height),
        ]
        gx1, gy1, gx2, gy2 = global_bbox
        return Detection(
            frame_id=roi.frame_id,
            source_type=detection.source_type,
            class_name=detection.class_name,
            confidence=detection.confidence,
            bbox=global_bbox,
            center=[(gx1 + gx2) // 2, (gy1 + gy2) // 2],
            area=max(gx2 - gx1, 0) * max(gy2 - gy1, 0),
            model_name=detection.model_name,
            infer_time_ms=detection.infer_time_ms,
        )

    def summarize(self, frame: VideoFrame, rois: list[ROIRegion]) -> ROIStats:
        frame_area = max(frame.width, 0) * max(frame.height, 0)
        roi_area = sum(_bbox_area(roi.bbox) for roi in rois)
        return ROIStats(roi_count=len(rois), frame_area=frame_area, roi_area=roi_area)


def _roi_id(frame_id: int, bbox: list[int], source_track_id: int | None) -> str:
    prefix = f"T{source_track_id}" if source_track_id is not None else "B"
    return f"ROI_F{frame_id}_{prefix}_{bbox[0]}_{bbox[1]}_{bbox[2]}_{bbox[3]}"


def _normalize_bbox(bbox: list[int]) -> list[int]:
    if len(bbox) != 4:
        raise ValueError("bbox must contain exactly four integers")
    x1, y1, x2, y2 = bbox
    return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]


def _bbox_area(bbox: list[int]) -> int:
    x1, y1, x2, y2 = bbox
    return max(x2 - x1, 0) * max(y2 - y1, 0)


def _clamp(value: int, low: int, high: int) -> int:
    return min(max(value, low), high)

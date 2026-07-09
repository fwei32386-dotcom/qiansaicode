from __future__ import annotations

import unittest

from ai_engine.roi_manager import ROIManager
from runtime.interfaces import Detection, PersonTrack, VideoFrame


class ROIManagerTest(unittest.TestCase):
    def test_expand_and_clip_keeps_roi_inside_frame(self) -> None:
        manager = ROIManager(margin_ratio=0.25)
        frame = _frame()

        roi = manager.build_roi(frame, [10, 20, 110, 220], reason="person_missing_ppe")

        self.assertEqual(roi.bbox, [0, 0, 135, 270])
        self.assertEqual(roi.source_bbox, [10, 20, 110, 220])
        self.assertEqual(roi.frame_width, 1280)
        self.assertEqual(roi.frame_height, 720)

    def test_local_detection_maps_back_to_global_coordinates(self) -> None:
        manager = ROIManager(margin_ratio=0.2)
        frame = _frame()
        roi = manager.build_roi(frame, [100, 120, 300, 520], reason="track:1:suspicious")
        local = _detection(frame_id=1, bbox=[20, 30, 80, 90])

        mapped = manager.map_detection_to_global(local, roi)

        self.assertEqual(mapped.bbox, [80, 70, 140, 130])
        self.assertEqual(mapped.center, [110, 100])
        self.assertEqual(mapped.area, 3600)

    def test_risky_tracks_build_rois_and_skip_normal_tracks(self) -> None:
        manager = ROIManager(margin_ratio=0.1)
        frame = _frame()
        tracks = [
            _track(1, [100, 100, 300, 500], "normal", "ok"),
            _track(2, [500, 100, 760, 620], "confirmed", "helmet_missing"),
        ]

        rois = manager.build_rois_from_tracks(frame, tracks)
        stats = manager.summarize(frame, rois)

        self.assertEqual(len(rois), 1)
        self.assertEqual(rois[0].source_track_id, 2)
        self.assertIn("confirmed", rois[0].reason)
        self.assertEqual(stats.roi_count, 1)
        self.assertGreater(stats.estimated_saved_ratio, 0.0)


def _frame() -> VideoFrame:
    return VideoFrame(
        frame_id=1,
        source_type="mock",
        timestamp=1.0,
        width=1280,
        height=720,
        source_name="roi_test",
    )


def _detection(frame_id: int, bbox: list[int]) -> Detection:
    x1, y1, x2, y2 = bbox
    return Detection(
        frame_id=frame_id,
        source_type="mock",
        class_name="helmet",
        confidence=0.9,
        bbox=bbox,
        center=[(x1 + x2) // 2, (y1 + y2) // 2],
        area=max(x2 - x1, 0) * max(y2 - y1, 0),
        model_name="roi_test_detector",
        infer_time_ms=0.1,
    )


def _track(track_id: int, bbox: list[int], risk_state: str, ppe_status: str) -> PersonTrack:
    return PersonTrack(
        track_id=track_id,
        frame_id=1,
        bbox=bbox,
        zone_id="danger_zone",
        has_helmet=ppe_status == "ok",
        has_vest=True,
        has_goggles=True,
        has_gloves=True,
        ppe_status=ppe_status,
        risk_state=risk_state,  # type: ignore[arg-type]
        hit_count=3,
        miss_count=0,
        last_update_ts=1.0,
    )


if __name__ == "__main__":
    unittest.main()

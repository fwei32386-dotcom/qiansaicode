from __future__ import annotations

import unittest

from runtime.interfaces import Detection
from safety_brain.ppe_association import associate_ppe
from safety_brain.scene_graph import SceneGraph, Zone
from safety_brain.track_manager import TrackManager


class TrackManagerTest(unittest.TestCase):
    def test_track_manager_keeps_track_id_across_nearby_frames(self) -> None:
        manager = TrackManager(_scene(), confirm_hits=3)

        first = manager.update(associate_ppe([_person(1, [100, 100, 300, 500])]), timestamp=1.0)
        second = manager.update(associate_ppe([_person(2, [110, 105, 310, 505])]), timestamp=2.0)
        third = manager.update(associate_ppe([_person(3, [120, 110, 320, 510])]), timestamp=3.0)

        self.assertEqual(first[0].track_id, second[0].track_id)
        self.assertEqual(second[0].track_id, third[0].track_id)
        self.assertEqual(first[0].risk_state, "suspicious")
        self.assertEqual(third[0].risk_state, "confirmed")
        self.assertEqual(third[0].hit_count, 3)

    def test_track_manager_creates_new_track_for_far_person(self) -> None:
        manager = TrackManager(_scene())

        first = manager.update(associate_ppe([_person(1, [100, 100, 300, 500])]))
        second = manager.update(associate_ppe([_person(2, [700, 100, 900, 500])]))

        self.assertNotEqual(first[0].track_id, second[0].track_id)

    def test_track_manager_removes_track_after_misses(self) -> None:
        manager = TrackManager(_scene(), max_misses=1)
        manager.update(associate_ppe([_person(1, [100, 100, 300, 500])]))

        manager.update([])
        self.assertEqual(manager.active_count, 1)
        manager.update([])
        self.assertEqual(manager.active_count, 0)

    def test_track_manager_reports_ok_when_ppe_present(self) -> None:
        manager = TrackManager(_scene())
        tracks = manager.update(
            associate_ppe(
                [
                    _person(1, [100, 100, 300, 500]),
                    _object(1, "helmet", [150, 105, 250, 190]),
                    _object(1, "vest", [135, 240, 280, 420]),
                    _object(1, "goggles", [155, 145, 245, 185]),
                    _object(1, "gloves", [285, 280, 340, 360]),
                ]
            )
        )

        self.assertEqual(tracks[0].ppe_status, "ok")
        self.assertEqual(tracks[0].risk_state, "normal")


def _scene() -> SceneGraph:
    return SceneGraph(
        [
            Zone(
                zone_id="danger_zone",
                name="danger zone",
                risk_weight=25,
                polygon=[[0, 0], [1280, 0], [1280, 720], [0, 720]],
            )
        ]
    )


def _person(frame_id: int, bbox: list[int]) -> Detection:
    return _object(frame_id, "person", bbox)


def _object(frame_id: int, class_name: str, bbox: list[int]) -> Detection:
    x1, y1, x2, y2 = bbox
    return Detection(
        frame_id=frame_id,
        source_type="mock",
        class_name=class_name,  # type: ignore[arg-type]
        confidence=0.9,
        bbox=bbox,
        center=[(x1 + x2) // 2, (y1 + y2) // 2],
        area=max(x2 - x1, 0) * max(y2 - y1, 0),
        model_name="test",
        infer_time_ms=0.1,
    )


if __name__ == "__main__":
    unittest.main()

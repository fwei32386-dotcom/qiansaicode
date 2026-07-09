from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.replay_detection_jsonl import load_detection_jsonl, replay_detection_jsonl


class RknnDetectionJsonlReplayTest(unittest.TestCase):
    def test_rknn_detection_jsonl_feeds_rule_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jsonl = root / "rknn.jsonl"
            jsonl.write_text(
                "\n".join(json.dumps(_smoke_detection(frame_id)) for frame_id in (1, 2, 3)) + "\n",
                encoding="utf-8",
            )

            output = replay_detection_jsonl(
                detection_jsonl=jsonl,
                csv_path=root / "events.csv",
                timeline_path=root / "timeline.json",
                html_path=root / "report.html",
                dashboard_path=root / "dashboard.html",
                events_dir=root / "ui_events",
            )
            timeline = json.loads((root / "timeline.json").read_text(encoding="utf-8"))
            self.assertTrue((root / "ui_events" / "events.jsonl").exists())
            self.assertTrue((root / "ui_events" / "alarm_actions.jsonl").exists())

        self.assertEqual(output["frames"], 3)
        self.assertEqual(output["detections"], 3)
        self.assertEqual(output["events"], 1)
        self.assertEqual(output["actions"], 1)
        self.assertEqual(timeline["summary"]["events"], 1)

    def test_load_detection_jsonl_groups_by_frame(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "detections.jsonl"
            path.write_text(
                json.dumps(_smoke_detection(2)) + "\n" + json.dumps(_smoke_detection(1)) + "\n",
                encoding="utf-8",
            )
            frames = load_detection_jsonl(path)

        self.assertEqual([frame.frame_id for frame in frames], [1, 2])
        self.assertEqual(frames[0].detections[0].source_type, "camera")
        self.assertEqual(frames[0].detections[0].model_name, "safelab_yolov8n_rknn")

    def test_replay_uses_scene_mode_for_ppe_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            construction_jsonl = root / "construction.jsonl"
            lab_jsonl = root / "lab.jsonl"
            scene_mode = root / "scene_mode.json"
            construction_jsonl.write_text(
                "\n".join(json.dumps(_person_detection(frame_id)) for frame_id in (1, 2, 3)) + "\n",
                encoding="utf-8",
            )
            lab_records: list[dict[str, object]] = []
            for frame_id in (1, 2, 3):
                lab_records.extend(
                    [
                        _person_detection(frame_id),
                        _ppe_detection(frame_id, "goggles", [525, 150, 610, 190]),
                        _ppe_detection(frame_id, "gloves", [720, 360, 790, 450]),
                    ]
                )
            lab_jsonl.write_text("\n".join(json.dumps(item) for item in lab_records) + "\n", encoding="utf-8")

            scene_mode.write_text(json.dumps({"mode": "construction"}), encoding="utf-8")
            construction_output = replay_detection_jsonl(
                detection_jsonl=construction_jsonl,
                csv_path=root / "construction.csv",
                timeline_path=root / "construction_timeline.json",
                html_path=root / "construction.html",
                dashboard_path=root / "construction_dashboard.html",
                events_dir=root / "construction_events",
                scene_mode_path=scene_mode,
            )

            scene_mode.write_text(json.dumps({"mode": "lab"}), encoding="utf-8")
            lab_output = replay_detection_jsonl(
                detection_jsonl=lab_jsonl,
                csv_path=root / "lab.csv",
                timeline_path=root / "lab_timeline.json",
                html_path=root / "lab.html",
                dashboard_path=root / "lab_dashboard.html",
                events_dir=root / "lab_events",
                scene_mode_path=scene_mode,
            )

        self.assertEqual(construction_output["events"], 1)
        self.assertEqual(lab_output["events"], 0)

    def test_construction_ppe_violation_confirms_when_person_box_jitters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jsonl = root / "jitter_person.jsonl"
            scene_mode = root / "scene_mode.json"
            records = [
                _person_detection(1, bbox=[383, 8, 959, 707]),
                _person_detection(2, bbox=[383, 14, 959, 713]),
                _person_detection(3, bbox=[398, 15, 959, 699]),
            ]
            jsonl.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
            scene_mode.write_text(json.dumps({"mode": "construction"}), encoding="utf-8")

            output = replay_detection_jsonl(
                detection_jsonl=jsonl,
                csv_path=root / "events.csv",
                timeline_path=root / "timeline.json",
                html_path=root / "report.html",
                dashboard_path=root / "dashboard.html",
                events_dir=root / "events",
                scene_mode_path=scene_mode,
            )
            events_path = root / "events" / "events.jsonl"
            events = (
                [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if events_path.exists()
                else []
            )

        self.assertEqual(output["events"], 1)
        self.assertEqual(events[0]["event_type"], "ppe_violation")
        self.assertEqual(events[0]["rule_id"], "SCENE_CONSTRUCTION_HELMET")
        self.assertIn("missing_ppe=helmet, vest", events[0]["reasons"])

    def test_construction_vest_missing_confirms_when_person_is_inferred_from_moving_helmet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jsonl = root / "moving_helmet_only.jsonl"
            scene_mode = root / "scene_mode.json"
            records = [
                _ppe_detection(1, "helmet", [71, 91, 155, 189]),
                _ppe_detection(2, "helmet", [125, 83, 225, 204]),
                _ppe_detection(3, "helmet", [158, 79, 279, 207]),
            ]
            jsonl.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
            scene_mode.write_text(json.dumps({"mode": "construction"}), encoding="utf-8")

            output = replay_detection_jsonl(
                detection_jsonl=jsonl,
                csv_path=root / "events.csv",
                timeline_path=root / "timeline.json",
                html_path=root / "report.html",
                dashboard_path=root / "dashboard.html",
                events_dir=root / "events",
                scene_mode_path=scene_mode,
            )
            events_path = root / "events" / "events.jsonl"
            events = (
                [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if events_path.exists()
                else []
            )

        self.assertEqual(output["events"], 1)
        self.assertEqual(events[0]["rule_id"], "SCENE_CONSTRUCTION_VEST")
        self.assertIn("missing_ppe=vest", events[0]["reasons"])


def _smoke_detection(frame_id: int) -> dict[str, object]:
    return {
        "frame_id": frame_id,
        "source_type": "camera",
        "class_name": "smoke",
        "confidence": 0.88,
        "bbox": [410, 92, 735, 385],
        "center": [572, 238],
        "area": 95225,
        "model_name": "safelab_yolov8n_rknn",
        "infer_time_ms": 61.34,
    }


def _person_detection(frame_id: int, bbox: list[int] | None = None) -> dict[str, object]:
    bbox = bbox or [500, 100, 760, 620]
    x1, y1, x2, y2 = bbox
    return {
        "frame_id": frame_id,
        "source_type": "camera",
        "class_name": "person",
        "confidence": 0.91,
        "bbox": bbox,
        "center": [(x1 + x2) // 2, (y1 + y2) // 2],
        "area": (x2 - x1) * (y2 - y1),
        "model_name": "safelab_ppe_rknn",
        "infer_time_ms": 22.0,
    }


def _ppe_detection(frame_id: int, class_name: str, bbox: list[int]) -> dict[str, object]:
    x1, y1, x2, y2 = bbox
    return {
        "frame_id": frame_id,
        "source_type": "camera",
        "class_name": class_name,
        "confidence": 0.86,
        "bbox": bbox,
        "center": [(x1 + x2) // 2, (y1 + y2) // 2],
        "area": (x2 - x1) * (y2 - y1),
        "model_name": "safelab_ppe_rknn",
        "infer_time_ms": 22.0,
    }


if __name__ == "__main__":
    unittest.main()

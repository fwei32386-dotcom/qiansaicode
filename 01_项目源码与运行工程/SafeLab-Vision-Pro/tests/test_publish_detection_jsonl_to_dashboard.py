from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.publish_detection_jsonl_to_dashboard import expand_detection_jsonl, publish_detection_jsonl


class PublishDetectionJsonlToDashboardTest(unittest.TestCase):
    def test_expand_detection_jsonl_repeats_frame_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jsonl"
            expanded = root / "expanded.jsonl"
            source.write_text(
                json.dumps(_smoke_detection(7)) + "\n" + json.dumps(_fire_detection(7)) + "\n",
                encoding="utf-8",
            )

            count = expand_detection_jsonl(source, expanded, repeat_frames=3)
            records = [json.loads(line) for line in expanded.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(count, 6)
        self.assertEqual([record["frame_id"] for record in records], [1, 1, 2, 2, 3, 3])
        self.assertEqual([record["class_name"] for record in records[:2]], ["smoke", "fire"])

    def test_publish_resets_event_files_and_writes_ui_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jsonl"
            events_dir = root / "data" / "events"
            reports_dir = root / "reports"
            events_dir.mkdir(parents=True)
            (events_dir / "events.jsonl").write_text("old\n", encoding="utf-8")
            source.write_text(json.dumps(_smoke_detection(1)) + "\n", encoding="utf-8")

            summary = publish_detection_jsonl(
                detection_jsonl=source,
                events_dir=events_dir,
                reports_dir=reports_dir,
                reset=True,
                repeat_frames=3,
            )
            event_text = (events_dir / "events.jsonl").read_text(encoding="utf-8")
            self.assertTrue((events_dir / "alarm_actions.jsonl").exists())

        self.assertEqual(summary["events"], 1)
        self.assertEqual(summary["actions"], 1)
        self.assertNotIn("old", event_text)

    def test_publish_reset_preserves_ai_explanations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "empty.jsonl"
            events_dir = root / "data" / "events"
            reports_dir = root / "reports"
            events_dir.mkdir(parents=True)
            ai_path = events_dir / "ai_explanations.jsonl"
            ai_path.write_text(json.dumps({"event_id": "E1", "summary": "keep me"}) + "\n", encoding="utf-8")
            source.write_text("", encoding="utf-8")

            publish_detection_jsonl(
                detection_jsonl=source,
                events_dir=events_dir,
                reports_dir=reports_dir,
                reset=True,
            )

            self.assertTrue(ai_path.exists())
            self.assertIn("keep me", ai_path.read_text(encoding="utf-8"))

    def test_publish_retains_recent_events_for_one_minute_when_next_window_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "empty.jsonl"
            events_dir = root / "data" / "events"
            reports_dir = root / "reports"
            events_dir.mkdir(parents=True)
            previous_event = _ppe_warning_event(timestamp=1000.0)
            (events_dir / "events.jsonl").write_text(
                json.dumps(previous_event, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            source.write_text("", encoding="utf-8")

            summary = publish_detection_jsonl(
                detection_jsonl=source,
                events_dir=events_dir,
                reports_dir=reports_dir,
                reset=True,
                now=1059.0,
            )
            retained_events = _read_jsonl(events_dir / "events.jsonl")

        self.assertEqual(summary["events"], 0)
        self.assertEqual(summary["retained_events"], 1)
        self.assertEqual(retained_events, [previous_event])

    def test_publish_drops_retained_events_after_one_minute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "empty.jsonl"
            events_dir = root / "data" / "events"
            reports_dir = root / "reports"
            events_dir.mkdir(parents=True)
            (events_dir / "events.jsonl").write_text(
                json.dumps(_ppe_warning_event(timestamp=1000.0), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            source.write_text("", encoding="utf-8")

            summary = publish_detection_jsonl(
                detection_jsonl=source,
                events_dir=events_dir,
                reports_dir=reports_dir,
                reset=True,
                now=1061.0,
            )

        self.assertEqual(summary["events"], 0)
        self.assertEqual(summary["retained_events"], 0)
        self.assertFalse((events_dir / "events.jsonl").exists())

    def test_publish_keeps_current_window_events_even_when_frame_timestamp_is_old(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jsonl"
            events_dir = root / "data" / "events"
            reports_dir = root / "reports"
            events_dir.mkdir(parents=True)
            source.write_text(
                "\n".join(json.dumps(_smoke_detection(frame_id)) for frame_id in [1, 2, 3]) + "\n",
                encoding="utf-8",
            )

            summary = publish_detection_jsonl(
                detection_jsonl=source,
                events_dir=events_dir,
                reports_dir=reports_dir,
                reset=True,
                now=999999.0,
            )
            retained_events = _read_jsonl(events_dir / "events.jsonl")

        self.assertEqual(summary["events"], 1)
        self.assertEqual(summary["retained_events"], 1)
        self.assertEqual(retained_events[0]["event_type"], "smoke")


def _smoke_detection(frame_id: int) -> dict[str, object]:
    return {
        "frame_id": frame_id,
        "source_type": "camera",
        "class_name": "smoke",
        "confidence": 0.88,
        "bbox": [410, 92, 735, 385],
        "center": [572, 238],
        "area": 95225,
        "model_name": "safelab_fire_smoke_rknn",
        "infer_time_ms": 61.34,
    }


def _fire_detection(frame_id: int) -> dict[str, object]:
    item = _smoke_detection(frame_id)
    item["class_name"] = "fire"
    item["model_name"] = "safelab_fire_smoke_rknn"
    return item


def _ppe_warning_event(timestamp: float) -> dict[str, object]:
    return {
        "event_id": "ppe-warning-1",
        "frame_id": 7,
        "event_type": "ppe_violation",
        "risk_level": "warning",
        "timestamp": timestamp,
        "reasons": ["missing_ppe=vest"],
    }


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    unittest.main()

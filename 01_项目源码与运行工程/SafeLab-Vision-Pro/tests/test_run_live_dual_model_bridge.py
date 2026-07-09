from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.live_dual_model_sources import ActiveFrameSource
from tools.run_live_dual_model_bridge import _build_board_media_extract_command
from tools.run_live_dual_model_bridge import annotate_detection_jsonl_source_image, append_jsonl_to_window, should_process_camera_frame
from tools.run_live_dual_model_bridge import build_board_file_local_fallback_source
from tools.run_live_dual_model_bridge import LocalVideoFrameReader
from tools.run_live_dual_model_bridge import reset_detection_window
from tools.run_live_dual_model_bridge import run_captured_frame_once


class RunLiveDualModelBridgeTest(unittest.TestCase):
    def test_should_process_camera_frame_uses_frame_delta(self) -> None:
        self.assertTrue(
            should_process_camera_frame(
                current_camera_frame_id=100,
                last_processed_camera_frame_id=None,
                interval_frames=75,
            )
        )
        self.assertFalse(
            should_process_camera_frame(
                current_camera_frame_id=140,
                last_processed_camera_frame_id=100,
                interval_frames=75,
            )
        )
        self.assertTrue(
            should_process_camera_frame(
                current_camera_frame_id=175,
                last_processed_camera_frame_id=100,
                interval_frames=75,
            )
        )

    def test_should_process_camera_frame_handles_camera_stream_restart(self) -> None:
        self.assertTrue(
            should_process_camera_frame(
                current_camera_frame_id=12,
                last_processed_camera_frame_id=15936,
                interval_frames=75,
            )
        )

    def test_append_jsonl_to_window_keeps_recent_frame_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = root / "window.jsonl"
            first = root / "first.jsonl"
            second = root / "second.jsonl"
            first.write_text(
                json.dumps({"frame_id": 1, "class_name": "person"}) + "\n"
                + json.dumps({"frame_id": 2, "class_name": "smoke"}) + "\n",
                encoding="utf-8",
            )
            second.write_text(
                json.dumps({"frame_id": 3, "class_name": "fire"}) + "\n",
                encoding="utf-8",
            )

            append_jsonl_to_window(first, window, max_frames=2)
            summary = append_jsonl_to_window(second, window, max_frames=2)
            records = [json.loads(line) for line in window.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(summary["frames"], 2)
        self.assertEqual(summary["detections"], 2)
        self.assertEqual([record["frame_id"] for record in records], [2, 3])
        self.assertEqual([record["class_name"] for record in records], ["smoke", "fire"])

    def test_append_jsonl_to_window_keeps_recent_arrival_when_camera_frame_id_resets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = root / "window.jsonl"
            current = root / "current.jsonl"
            window.write_text(json.dumps({"frame_id": 15936, "class_name": "person"}) + "\n", encoding="utf-8")
            current.write_text(json.dumps({"frame_id": 12, "class_name": "helmet"}) + "\n", encoding="utf-8")

            summary = append_jsonl_to_window(current, window, max_frames=1)
            records = [json.loads(line) for line in window.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(summary, {"frames": 1, "detections": 1})
        self.assertEqual(records, [{"frame_id": 12, "class_name": "helmet"}])

    def test_reset_detection_window_removes_stale_source_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = root / "work" / "detections_window.jsonl"
            window.parent.mkdir(parents=True, exist_ok=True)
            window.write_text(json.dumps({"frame_id": 1, "source_type": "board_file"}) + "\n", encoding="utf-8")

            removed = reset_detection_window(root / "work")

        self.assertEqual(removed, [str(window)])
        self.assertFalse(window.exists())

    def test_annotate_detection_jsonl_source_image_adds_frame_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            detections = root / "detections.jsonl"
            frame = root / "frame.jpg"
            frame.write_bytes(b"jpg")
            detections.write_text(json.dumps({"frame_id": 1, "class_name": "helmet"}) + "\n", encoding="utf-8")

            count = annotate_detection_jsonl_source_image(detections, frame)
            records = [json.loads(line) for line in detections.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(count, 1)
        self.assertEqual(records[0]["source_image"], str(frame))

    def test_run_captured_frame_once_keeps_previous_window_when_current_frame_has_no_detections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame = root / "frame.jpg"
            frame.write_bytes(b"jpg")
            window = root / "work" / "detections_window.jsonl"
            window.parent.mkdir(parents=True, exist_ok=True)
            previous = {"frame_id": 7, "class_name": "person"}
            window.write_text(json.dumps(previous) + "\n", encoding="utf-8")

            with patch("tools.run_live_dual_model_bridge.run_board_dual_model_image") as infer, patch(
                "tools.run_live_dual_model_bridge.publish_detection_jsonl"
            ) as publish:
                infer.return_value = {"detections": 0}
                publish.return_value = {"frames": 1, "detections": 1}

                summary = run_captured_frame_once(
                    frame_path=frame,
                    detection_frame_id=8,
                    frame_id=1,
                    source_key="file_demo",
                    source_type="file",
                    work_dir=root / "work",
                    events_dir=root / "events",
                    reports_dir=root / "reports",
                    host="board",
                    username="root",
                    password="root",
                    ppe_confidence_threshold=0.2,
                    fire_smoke_confidence_threshold=0.25,
                    max_window_frames=3,
                )

            records = [json.loads(line) for line in window.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(records, [previous])
        self.assertEqual(summary["window"], {"frames": 1, "detections": 1})

    def test_run_captured_frame_once_creates_empty_window_when_no_detections_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame = root / "frame.jpg"
            frame.write_bytes(b"jpg")
            window = root / "work" / "detections_window.jsonl"

            with patch("tools.run_live_dual_model_bridge.run_board_dual_model_image") as infer, patch(
                "tools.run_live_dual_model_bridge.publish_detection_jsonl"
            ) as publish:
                infer.return_value = {"detections": 0}
                publish.return_value = {"frames": 0, "detections": 0}

                summary = run_captured_frame_once(
                    frame_path=frame,
                    detection_frame_id=8,
                    frame_id=1,
                    source_key="camera_ov13855",
                    source_type="camera",
                    work_dir=root / "work",
                    events_dir=root / "events",
                    reports_dir=root / "reports",
                    host="board",
                    username="root",
                    password="root",
                    ppe_confidence_threshold=0.2,
                    fire_smoke_confidence_threshold=0.25,
                    max_window_frames=3,
                )

            self.assertTrue(window.exists())
            self.assertEqual(window.read_text(encoding="utf-8"), "")
            self.assertEqual(summary["window"], {"frames": 0, "detections": 0})

    def test_run_captured_frame_once_overrides_detection_source_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame = root / "frame.jpg"
            frame.write_bytes(b"jpg")

            def fake_infer(**kwargs):
                output_jsonl = Path(kwargs["output_jsonl"])
                output_jsonl.parent.mkdir(parents=True, exist_ok=True)
                output_jsonl.write_text(
                    json.dumps({"frame_id": 9, "source_type": "camera", "class_name": "helmet"}) + "\n",
                    encoding="utf-8",
                )
                return {"detections": 1}

            with patch("tools.run_live_dual_model_bridge.run_board_dual_model_image", side_effect=fake_infer), patch(
                "tools.run_live_dual_model_bridge.publish_detection_jsonl"
            ) as publish:
                publish.return_value = {"frames": 1, "detections": 1}
                run_captured_frame_once(
                    frame_path=frame,
                    detection_frame_id=9,
                    frame_id=1,
                    source_key="file_demo",
                    source_type="file",
                    work_dir=root / "work",
                    events_dir=root / "events",
                    reports_dir=root / "reports",
                    host="board",
                    username="root",
                    password="root",
                    ppe_confidence_threshold=0.2,
                    fire_smoke_confidence_threshold=0.25,
                    max_window_frames=3,
                )

            window = root / "work" / "detections_window.jsonl"
            records = [json.loads(line) for line in window.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(records[0]["source_type"], "file")
        self.assertEqual(records[0]["source_key"], "file_demo")

    def test_run_captured_frame_once_passes_board_model_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame = root / "frame.jpg"
            frame.write_bytes(b"jpg")

            with patch("tools.run_live_dual_model_bridge.run_board_dual_model_image") as infer, patch(
                "tools.run_live_dual_model_bridge.publish_detection_jsonl"
            ) as publish:
                infer.return_value = {"detections": 0}
                publish.return_value = {"frames": 0, "detections": 0}

                run_captured_frame_once(
                    frame_path=frame,
                    detection_frame_id=9,
                    frame_id=1,
                    source_key="board_file_demo",
                    source_type="board_file",
                    work_dir=root / "work",
                    events_dir=root / "events",
                    reports_dir=root / "reports",
                    host="board",
                    username="root",
                    password="root",
                    ppe_confidence_threshold=0.2,
                    fire_smoke_confidence_threshold=0.25,
                    max_window_frames=3,
                    binary="/custom/bin",
                    ppe_model="/custom/ppe.rknn",
                    fire_smoke_model="/custom/fire.rknn",
                    remote_dir="/custom/run",
                )

            kwargs = infer.call_args.kwargs

        self.assertEqual(kwargs["binary"], "/custom/bin")
        self.assertEqual(kwargs["ppe_model"], "/custom/ppe.rknn")
        self.assertEqual(kwargs["fire_smoke_model"], "/custom/fire.rknn")
        self.assertEqual(kwargs["remote_dir"], "/custom/run")

    def test_board_file_local_fallback_source_uses_uploaded_local_path(self) -> None:
        source = ActiveFrameSource(
            key="board_file_demo",
            source_type="board_file",
            label="本地视频",
            path=Path("data/runtime/board_media/current.mp4"),
            board_path="/root/safelab_media/current_demo.mp4",
            source_name="demo",
            fps=15,
            width=362,
            height=398,
            media_type="video",
        )

        fallback = build_board_file_local_fallback_source(source)

        self.assertEqual(fallback.key, "board_file_demo")
        self.assertEqual(fallback.source_type, "file")
        self.assertEqual(fallback.path, Path("data/runtime/board_media/current.mp4"))
        self.assertIsNone(fallback.board_path)
        self.assertEqual(fallback.media_type, "video")

    def test_local_video_frame_reader_writes_interval_frame(self) -> None:
        cv2 = _import_cv2_or_skip(self)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video_path = root / "sample.avi"
            writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (16, 16))
            if not writer.isOpened():
                self.skipTest("OpenCV MJPG writer is unavailable")
            for index in range(6):
                frame = cv2.UMat(16, 16, cv2.CV_8UC3).get()
                frame[:] = index * 20
                writer.write(frame)
            writer.release()
            source = ActiveFrameSource(key="file_demo", source_type="file", label="file", path=video_path)
            reader = LocalVideoFrameReader(source)
            try:
                first = reader.capture_interval_frame(interval_frames=3, output_dir=root / "frames")
                second = reader.capture_interval_frame(interval_frames=3, output_dir=root / "frames")
                first_exists = Path(first["frame_path"]).exists()
                second_exists = Path(second["frame_path"]).exists()
            finally:
                reader.close()

        self.assertEqual(first["frame_id"], 1)
        self.assertEqual(second["frame_id"], 4)
        self.assertTrue(first_exists)
        self.assertTrue(second_exists)

    def test_local_video_frame_reader_writes_frame_under_unicode_directory(self) -> None:
        cv2 = _import_cv2_or_skip(self)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video_path = root / "sample.avi"
            writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (16, 16))
            if not writer.isOpened():
                self.skipTest("OpenCV MJPG writer is unavailable")
            frame = cv2.UMat(16, 16, cv2.CV_8UC3).get()
            frame[:] = 80
            writer.write(frame)
            writer.release()
            source = ActiveFrameSource(key="file_demo", source_type="file", label="file", path=video_path)
            reader = LocalVideoFrameReader(source)
            try:
                captured = reader.capture_interval_frame(interval_frames=1, output_dir=root / "资料帧")
                frame_exists = Path(captured["frame_path"]).exists()
            finally:
                reader.close()

        self.assertTrue(frame_exists)

    def test_board_video_extract_command_falls_back_when_frame_index_is_past_end(self) -> None:
        command = _build_board_media_extract_command(
            media_path="/root/safelab_media/current_demo.mp4",
            media_type="video",
            frame_index=9327,
            remote_blob="/root/run/frame.rgb",
            remote_preview="/root/run/frame.jpg",
        )

        self.assertIn("test -s /root/run/frame_extract.jpg", command)
        self.assertIn("-frames:v 1 /root/run/frame_extract.jpg", command)
        self.assertIn("select=eq(n\\,9327)", command)


def _import_cv2_or_skip(case: unittest.TestCase):
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError:
        case.skipTest("OpenCV is unavailable")
    return cv2


if __name__ == "__main__":
    unittest.main()

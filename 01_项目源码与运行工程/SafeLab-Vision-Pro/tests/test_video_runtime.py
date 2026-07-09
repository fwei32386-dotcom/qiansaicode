from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runtime.frame_scheduler import FrameScheduler
from runtime.latest_frame_buffer import LatestFrameBuffer
from runtime.pipeline_profiler import PipelineProfiler
from video.file_video_source import FileVideoSource
from video.video_source import MockVideoSource, VideoSourceConfig
from video.image_file_source import ImageFileSource


class VideoRuntimeTest(unittest.TestCase):
    def test_mock_source_outputs_monotonic_video_frames(self) -> None:
        source = MockVideoSource(
            VideoSourceConfig(
                source_type="mock",
                source_name="mock_video",
                width=640,
                height=480,
            ),
            frame_count=2,
        )

        first = source.read()
        second = source.read()
        third = source.read()

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertIsNone(third)
        assert first is not None
        assert second is not None
        self.assertEqual(first.frame_id, 1)
        self.assertEqual(second.frame_id, 2)
        self.assertEqual(first.source_type, "mock")
        self.assertEqual(first.to_dict()["source_name"], "mock_video")
        self.assertNotIn("frame", first.to_dict())

    def test_image_file_source_outputs_single_frame_with_real_dimensions(self) -> None:
        with TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "sample.ppm"
            image_path.write_bytes(b"P6\n3 2\n255\n" + bytes(range(18)))
            source = ImageFileSource(
                VideoSourceConfig(
                    source_type="file",
                    source_name="local_sample_image",
                    width=1,
                    height=1,
                    path=str(image_path),
                )
            )

            first = source.read()
            second = source.read()

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        assert first is not None
        self.assertEqual(first.frame_id, 1)
        self.assertEqual(first.source_type, "file")
        self.assertEqual(first.source_name, "local_sample_image")
        self.assertEqual((first.width, first.height), (3, 2))
        self.assertIsNotNone(first.frame)

    def test_file_video_source_accepts_local_image_files(self) -> None:
        with TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "sample.ppm"
            image_path.write_bytes(b"P6\n4 3\n255\n" + bytes(range(36)))
            source = FileVideoSource(
                VideoSourceConfig(
                    source_type="file",
                    source_name="local_media_file",
                    width=1,
                    height=1,
                    path=str(image_path),
                )
            )

            first = source.read()
            second = source.read()
            source.close()

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        assert first is not None
        self.assertEqual((first.width, first.height), (4, 3))
        self.assertEqual(first.source_type, "file")

    def test_latest_frame_buffer_keeps_only_newest_frame(self) -> None:
        source = MockVideoSource(
            VideoSourceConfig(
                source_type="mock",
                source_name="mock_video",
                width=640,
                height=480,
            ),
            frame_count=3,
        )
        buffer = LatestFrameBuffer()

        first = source.read()
        second = source.read()
        third = source.read()
        assert first is not None
        assert second is not None
        assert third is not None

        buffer.put(first)
        buffer.put(second)
        buffer.put(third)

        latest = buffer.get_latest()
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest.frame_id, 3)
        self.assertEqual(buffer.dropped_count, 2)

    def test_frame_scheduler_drops_normal_frames_and_prioritizes_risk_frames(self) -> None:
        scheduler = FrameScheduler(normal_interval=5, suspicious_interval=1, alarmed_interval=2)
        source = MockVideoSource(
            VideoSourceConfig(
                source_type="mock",
                source_name="mock_video",
                width=640,
                height=480,
            ),
            frame_count=10,
        )
        frames = [frame for frame in (source.read() for _ in range(10)) if frame is not None]

        normal = [scheduler.decide(frame, "normal") for frame in frames[:5]]
        suspicious = [scheduler.decide(frame, "suspicious", has_roi=True) for frame in frames[5:8]]
        alarmed = [scheduler.decide(frame, "alarmed", has_roi=True) for frame in frames[8:]]

        self.assertEqual([d.should_process for d in normal], [True, False, False, False, True])
        self.assertTrue(all(d.should_process for d in suspicious))
        self.assertTrue(all(d.mode == "roi" for d in suspicious))
        self.assertEqual([d.should_process for d in alarmed], [False, True])

    def test_pipeline_profiler_records_stage_summary(self) -> None:
        profiler = PipelineProfiler()
        with profiler.stage("rule_eval_ms"):
            sum(range(10))
        profiler.record("rule_eval_ms", 2.0)

        latest = profiler.latest()
        summary = profiler.summary()

        self.assertIn("rule_eval_ms", latest)
        self.assertEqual(summary["count"]["rule_eval_ms"], 2)
        self.assertGreaterEqual(summary["max_ms"]["rule_eval_ms"], summary["average_ms"]["rule_eval_ms"])


if __name__ == "__main__":
    unittest.main()

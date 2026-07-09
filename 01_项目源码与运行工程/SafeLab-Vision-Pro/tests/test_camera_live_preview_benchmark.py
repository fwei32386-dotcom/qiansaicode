from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.benchmark_camera_live_preview import run_camera_live_preview_benchmark


class CameraLivePreviewBenchmarkTest(unittest.TestCase):
    def test_benchmark_writes_summary_from_status_samples(self) -> None:
        payloads = [
            {
                "frame_id": 10,
                "estimated_fps": 10.0,
                "last_frame_age_seconds": 0.1,
                "frame_bytes": 102400,
                "last_error": "",
                "stream_config": {"target_fps": 10, "preview_width": 960},
            },
            {
                "frame_id": 15,
                "estimated_fps": 10.1,
                "last_frame_age_seconds": 0.08,
                "frame_bytes": 112640,
                "last_error": "",
                "stream_config": {"target_fps": 10, "preview_width": 960},
            },
        ]

        class FakeResponse:
            def __init__(self, payload: dict[str, object]) -> None:
                self.payload = payload

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps(self.payload).encode("utf-8")

        calls = iter(payloads)

        def fake_urlopen(_url: str, timeout: int = 2) -> FakeResponse:
            return FakeResponse(next(calls, payloads[-1]))

        with tempfile.TemporaryDirectory() as tmp, patch("tools.benchmark_camera_live_preview.urlopen", fake_urlopen):
            output = Path(tmp) / "camera_live_preview_benchmark.json"
            summary = run_camera_live_preview_benchmark(
                duration_seconds=0.02,
                sample_interval_seconds=0.01,
                output_path=output,
            )
            saved = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(summary["status"], "ok")
        self.assertGreaterEqual(summary["average_reported_fps"], 10)
        self.assertEqual(saved["stream_config"]["preview_width"], 960)
        self.assertGreater(saved["frame_id_delta"], 0)


if __name__ == "__main__":
    unittest.main()

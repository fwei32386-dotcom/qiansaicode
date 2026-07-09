from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.benchmark_latest_frame_buffer import run_latest_frame_buffer_benchmark


class LatestFrameBufferBenchmarkTest(unittest.TestCase):
    def test_benchmark_reports_latest_only_in_memory_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "summary.json"
            summary = run_latest_frame_buffer_benchmark(
                capture_frames=12,
                detector_reads=3,
                output_path=output,
            )
            saved = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(summary["frame_storage_policy"], "in_memory_only")
        self.assertEqual(summary["captures_written_to_disk"], 0)
        self.assertTrue(summary["old_frames_dropped"])
        self.assertTrue(summary["detector_uses_newest_frame"])
        self.assertEqual(saved["latest_frame_id"], 12)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.interfaces import VideoFrame
from runtime.latest_frame_buffer import LatestFrameBuffer


def run_latest_frame_buffer_benchmark(
    capture_frames: int = 30,
    detector_reads: int = 8,
    output_path: str | Path = ROOT / "reports" / "latest_frame_buffer_summary.json",
) -> dict[str, object]:
    buffer = LatestFrameBuffer()
    captured_ids: list[int] = []
    processed_ids: list[int] = []

    start = time.time()
    for frame_id in range(1, capture_frames + 1):
        frame = VideoFrame(
            frame_id=frame_id,
            source_type="camera",
            timestamp=start + frame_id * 0.001,
            width=960,
            height=713,
            source_name="ov13855_ddr_buffer",
            frame={"memory": "ddr", "mock_payload": frame_id},
        )
        buffer.put(frame)
        captured_ids.append(frame_id)

        should_read = frame_id % max(capture_frames // detector_reads, 1) == 0
        if should_read:
            latest = buffer.get_latest()
            if latest is not None:
                processed_ids.append(latest.frame_id)

    latest = buffer.get_latest()
    latest_id = latest.frame_id if latest else None
    summary = {
        "pipeline": "camera_frame -> DDR latest_frame_buffer -> detector -> rule_engine",
        "frame_storage_policy": "in_memory_only",
        "captures_written_to_disk": 0,
        "capture_frames": capture_frames,
        "detector_reads": len(processed_ids),
        "captured_first_id": captured_ids[0] if captured_ids else None,
        "captured_last_id": captured_ids[-1] if captured_ids else None,
        "processed_frame_ids": processed_ids,
        "latest_frame_id": latest_id,
        "dropped_frames": buffer.dropped_count,
        "old_frames_dropped": buffer.dropped_count > 0,
        "detector_uses_newest_frame": bool(processed_ids and processed_ids[-1] == latest_id),
        "notes": [
            "The buffer intentionally keeps one newest VideoFrame object in memory.",
            "When detector/RKNN is slower than capture, older frames are overwritten instead of queued.",
            "VideoFrame.frame is runtime data and is excluded from JSON logs.",
        ],
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark latest-frame DDR buffer semantics.")
    parser.add_argument("--capture-frames", type=int, default=30)
    parser.add_argument("--detector-reads", type=int, default=8)
    parser.add_argument("--output", default=str(ROOT / "reports" / "latest_frame_buffer_summary.json"))
    args = parser.parse_args()

    summary = run_latest_frame_buffer_benchmark(args.capture_frames, args.detector_reads, args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.latest_frame_buffer import LatestFrameBuffer
from video.video_source import MockVideoSource, VideoSourceConfig


def main() -> int:
    source = MockVideoSource(
        VideoSourceConfig(
            source_type="mock",
            source_name="mock_video_runtime",
            width=640,
            height=480,
        ),
        frame_count=3,
    )
    buffer = LatestFrameBuffer()
    frames = []
    while True:
        frame = source.read()
        if frame is None:
            break
        buffer.put(frame)
        frames.append(frame.to_dict())

    latest = buffer.get_latest()
    payload = {
        "frames_read": len(frames),
        "latest_frame": latest.to_dict() if latest else None,
        "dropped_count": buffer.dropped_count,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["frames_read"] == 3 and payload["dropped_count"] == 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())

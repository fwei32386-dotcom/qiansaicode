from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.frame_scheduler import FrameScheduler
from runtime.interfaces import VideoFrame


def benchmark_frame_scheduler(
    frame_count: int = 12,
    csv_path: str | Path = ROOT / "reports" / "frame_scheduler_trace.csv",
    summary_path: str | Path = ROOT / "reports" / "frame_scheduler_summary.json",
) -> dict[str, Any]:
    scheduler = FrameScheduler(normal_interval=5, suspicious_interval=1, alarmed_interval=2)
    rows: list[dict[str, Any]] = []
    for frame_id in range(1, frame_count + 1):
        state = _state_for_frame(frame_id)
        decision = scheduler.decide(
            VideoFrame(
                frame_id=frame_id,
                source_type="mock",
                timestamp=time.time(),
                width=1280,
                height=720,
                source_name="scheduler_mock",
            ),
            runtime_state=state,
            has_roi=state != "normal",
        )
        rows.append(
            {
                "frame_id": frame_id,
                "runtime_state": state,
                "should_process": decision.should_process,
                "mode": decision.mode,
                "reason": decision.reason,
            }
        )

    _write_csv(rows, csv_path)
    summary = {
        "frame_count": frame_count,
        "processed_count": sum(1 for row in rows if row["should_process"]),
        "skipped_count": sum(1 for row in rows if not row["should_process"]),
        "roi_count": sum(1 for row in rows if row["mode"] == "roi" and row["should_process"]),
        "report_csv": str(csv_path),
        "policy": {
            "normal_interval": scheduler.normal_interval,
            "suspicious_interval": scheduler.suspicious_interval,
            "alarmed_interval": scheduler.alarmed_interval,
        },
    }
    output = Path(summary_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a frame scheduler trace report.")
    parser.add_argument("--frames", type=int, default=12)
    parser.add_argument("--csv", default=str(ROOT / "reports" / "frame_scheduler_trace.csv"))
    parser.add_argument("--summary", default=str(ROOT / "reports" / "frame_scheduler_summary.json"))
    args = parser.parse_args()

    summary = benchmark_frame_scheduler(args.frames, args.csv, args.summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _state_for_frame(frame_id: int) -> str:
    if frame_id <= 4:
        return "normal"
    if frame_id <= 8:
        return "suspicious"
    return "alarmed"


def _write_csv(rows: list[dict[str, Any]], csv_path: str | Path) -> Path:
    output = Path(csv_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["frame_id", "runtime_state", "should_process", "mode", "reason"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output


if __name__ == "__main__":
    raise SystemExit(main())

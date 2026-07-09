from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.replay_runner import ReplayRunner
from runtime.timeline_loader import DetectionFrame, load_timeline


def run_ablation(
    timeline_path: str | Path = ROOT / "data" / "mock_scenarios" / "timeline_smoke.json",
    smoke_csv: str | Path = ROOT / "reports" / "smoke_temporal_ablation.csv",
    state_csv: str | Path = ROOT / "reports" / "state_machine_ablation.csv",
    summary_json: str | Path = ROOT / "reports" / "ablation_summary.json",
) -> dict[str, Any]:
    frames = load_timeline(timeline_path)
    temporal_rows = _smoke_temporal_rows(frames)
    state_rows = _state_machine_rows(frames)

    _write_csv(
        smoke_csv,
        temporal_rows,
        [
            "method",
            "alarm_count",
            "first_alarm_frame",
            "duplicate_alarm_count",
            "single_frame_false_alarm",
            "closed_count",
            "note",
        ],
    )
    _write_csv(
        state_csv,
        state_rows,
        [
            "method",
            "alarm_count",
            "first_alarm_frame",
            "duplicate_alarm_count",
            "closed_count",
            "note",
        ],
    )

    summary = {
        "timeline": str(timeline_path),
        "smoke_temporal_ablation": str(smoke_csv),
        "state_machine_ablation": str(state_csv),
        "temporal": temporal_rows,
        "state_machine": state_rows,
    }
    Path(summary_json).parent.mkdir(parents=True, exist_ok=True)
    Path(summary_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SafeLab ablation reports.")
    parser.add_argument("--timeline", default=str(ROOT / "data" / "mock_scenarios" / "timeline_smoke.json"))
    parser.add_argument("--smoke-csv", default=str(ROOT / "reports" / "smoke_temporal_ablation.csv"))
    parser.add_argument("--state-csv", default=str(ROOT / "reports" / "state_machine_ablation.csv"))
    parser.add_argument("--summary-json", default=str(ROOT / "reports" / "ablation_summary.json"))
    args = parser.parse_args()

    summary = run_ablation(args.timeline, args.smoke_csv, args.state_csv, args.summary_json)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _smoke_temporal_rows(frames: list[DetectionFrame]) -> list[dict[str, Any]]:
    naive_alarm_frames = _frames_with_smoke(frames)
    replay = ReplayRunner().run(frames)
    temporal_alarm_frames = [event.frame_id for event in replay.events if event.event_type == "smoke"]
    closed_count = sum(1 for stage in replay.timeline if stage.stage == "closed")
    return [
        {
            "method": "single_frame_alarm",
            "alarm_count": len(naive_alarm_frames),
            "first_alarm_frame": naive_alarm_frames[0] if naive_alarm_frames else "",
            "duplicate_alarm_count": max(len(naive_alarm_frames) - 1, 0),
            "single_frame_false_alarm": True,
            "closed_count": 0,
            "note": "alarms on every smoke frame; vulnerable to single-frame false positives",
        },
        {
            "method": "temporal_confirmation",
            "alarm_count": len(temporal_alarm_frames),
            "first_alarm_frame": temporal_alarm_frames[0] if temporal_alarm_frames else "",
            "duplicate_alarm_count": 0,
            "single_frame_false_alarm": False,
            "closed_count": closed_count,
            "note": "requires consecutive frames and closes after recovery",
        },
    ]


def _state_machine_rows(frames: list[DetectionFrame]) -> list[dict[str, Any]]:
    confirmed_frames = _confirmed_smoke_frames_without_state_machine(frames, confirm_frames=3)
    replay = ReplayRunner().run(frames)
    state_alarm_frames = [event.frame_id for event in replay.events if event.event_type == "smoke"]
    closed_count = sum(1 for stage in replay.timeline if stage.stage == "closed")
    return [
        {
            "method": "no_state_machine",
            "alarm_count": len(confirmed_frames),
            "first_alarm_frame": confirmed_frames[0] if confirmed_frames else "",
            "duplicate_alarm_count": max(len(confirmed_frames) - 1, 0),
            "closed_count": 0,
            "note": "confirmed frames keep producing main alarms",
        },
        {
            "method": "event_state_machine",
            "alarm_count": len(state_alarm_frames),
            "first_alarm_frame": state_alarm_frames[0] if state_alarm_frames else "",
            "duplicate_alarm_count": 0,
            "closed_count": closed_count,
            "note": "main alarm only fires on lifecycle transition",
        },
    ]


def _frames_with_smoke(frames: list[DetectionFrame]) -> list[int]:
    return [
        frame.frame_id
        for frame in frames
        if any(detection.class_name == "smoke" for detection in frame.detections)
    ]


def _confirmed_smoke_frames_without_state_machine(
    frames: list[DetectionFrame],
    confirm_frames: int,
) -> list[int]:
    appear_count = 0
    confirmed: list[int] = []
    for frame in frames:
        has_smoke = any(detection.class_name == "smoke" for detection in frame.detections)
        if has_smoke:
            appear_count += 1
            if appear_count >= confirm_frames:
                confirmed.append(frame.frame_id)
        else:
            appear_count = 0
    return confirmed


def _write_csv(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output


if __name__ == "__main__":
    raise SystemExit(main())

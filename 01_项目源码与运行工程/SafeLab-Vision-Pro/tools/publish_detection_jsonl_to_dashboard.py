from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.replay_detection_jsonl import replay_detection_jsonl

EVENT_FILES = (
    "events.jsonl",
    "alarm_actions.jsonl",
    "actuator_log.jsonl",
    "alarm_log.db",
)


def reset_dashboard_events(events_dir: str | Path) -> list[str]:
    path = Path(events_dir)
    path.mkdir(parents=True, exist_ok=True)
    removed: list[str] = []
    for name in EVENT_FILES:
        target = path / name
        if target.exists():
            target.unlink()
            removed.append(str(target))
    return removed


def _read_jsonl_records(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _write_jsonl_records(path: str | Path, records: list[dict[str, Any]]) -> None:
    target = Path(path)
    if not records:
        if target.exists():
            target.unlink()
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _event_identity(event: dict[str, Any], index: int) -> str:
    event_id = event.get("event_id")
    if event_id:
        return str(event_id)
    return "|".join(
        [
            str(event.get("frame_id", "")),
            str(event.get("event_type", "")),
            str(event.get("risk_level", "")),
            str(event.get("timestamp", "")),
            str(index),
        ]
    )


def _is_recent_event(event: dict[str, Any], *, now: float, retention_seconds: float) -> bool:
    try:
        timestamp = float(event["timestamp"])
    except (KeyError, TypeError, ValueError):
        return False
    return now - timestamp <= retention_seconds


def retain_recent_dashboard_events(
    events_dir: str | Path,
    previous_events: list[dict[str, Any]],
    *,
    now: float,
    retention_seconds: float,
) -> int:
    events_path = Path(events_dir) / "events.jsonl"
    current_events = _read_jsonl_records(events_path)
    retained_previous = [
        event
        for event in previous_events
        if _is_recent_event(event, now=now, retention_seconds=retention_seconds)
    ]

    merged: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(retained_previous):
        merged[_event_identity(event, index)] = event
    for index, event in enumerate(current_events, start=len(retained_previous)):
        merged[_event_identity(event, index)] = event

    merged_events = list(merged.values())
    _write_jsonl_records(events_path, merged_events)
    return len(merged_events)


def expand_detection_jsonl(source_path: str | Path, output_path: str | Path, repeat_frames: int) -> int:
    if repeat_frames < 1:
        raise ValueError("repeat_frames must be >= 1")

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for line_number, line in enumerate(Path(source_path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{source_path}:{line_number}: invalid JSONL detection") from exc
        grouped[int(payload["frame_id"])].append(payload)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    next_frame_id = 1
    with output.open("w", encoding="utf-8") as f:
        for original_frame_id in sorted(grouped):
            records = grouped[original_frame_id]
            for _ in range(repeat_frames):
                for record in records:
                    cloned = dict(record)
                    cloned["frame_id"] = next_frame_id
                    f.write(json.dumps(cloned, ensure_ascii=False) + "\n")
                    written += 1
                next_frame_id += 1
    return written


def publish_detection_jsonl(
    detection_jsonl: str | Path,
    events_dir: str | Path = ROOT / "data" / "events",
    reports_dir: str | Path = ROOT / "reports" / "live_pipeline",
    reset: bool = False,
    repeat_frames: int = 1,
    scene_mode_path: str | Path = ROOT / "data" / "runtime" / "scene_mode.json",
    event_retention_seconds: float = 60.0,
    now: float | None = None,
) -> dict[str, Any]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    previous_events = (
        _read_jsonl_records(Path(events_dir) / "events.jsonl")
        if reset and event_retention_seconds > 0
        else []
    )
    removed = reset_dashboard_events(events_dir) if reset else []
    replay_input = Path(detection_jsonl)
    expanded_records = 0
    if repeat_frames > 1:
        replay_input = reports_path / "expanded_detection_frames.jsonl"
        expanded_records = expand_detection_jsonl(detection_jsonl, replay_input, repeat_frames=repeat_frames)

    summary = replay_detection_jsonl(
        detection_jsonl=replay_input,
        csv_path=reports_path / "event_report.csv",
        timeline_path=reports_path / "timeline.json",
        html_path=reports_path / "report.html",
        dashboard_path=reports_path / "dashboard.html",
        events_dir=events_dir,
        scene_mode_path=scene_mode_path,
    )
    retained_events = retain_recent_dashboard_events(
        events_dir,
        previous_events,
        now=time.time() if now is None else now,
        retention_seconds=event_retention_seconds,
    ) if reset and event_retention_seconds > 0 else len(_read_jsonl_records(Path(events_dir) / "events.jsonl"))
    summary.update(
        {
            "source_detection_jsonl": str(Path(detection_jsonl)),
            "replay_input": str(replay_input),
            "events_dir": str(Path(events_dir)),
            "reports_dir": str(reports_path),
            "reset_removed": removed,
            "repeat_frames": repeat_frames,
            "expanded_records": expanded_records,
            "scene_mode_path": str(Path(scene_mode_path)),
            "event_retention_seconds": event_retention_seconds,
            "retained_events": retained_events,
        }
    )
    summary_path = reports_path / "publish_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Detection JSONL into live dashboard event files.")
    parser.add_argument("detection_jsonl")
    parser.add_argument("--events-dir", default=str(ROOT / "data" / "events"))
    parser.add_argument("--reports-dir", default=str(ROOT / "reports" / "live_pipeline"))
    parser.add_argument("--repeat-frames", type=int, default=1)
    parser.add_argument("--reset", action="store_true", help="clear existing dashboard event files before replay")
    parser.add_argument("--scene-mode", default=str(ROOT / "data" / "runtime" / "scene_mode.json"))
    parser.add_argument(
        "--event-retention-seconds",
        type=float,
        default=60.0,
        help="keep dashboard risk events visible for this many seconds after the latest publish",
    )
    args = parser.parse_args()

    summary = publish_detection_jsonl(
        detection_jsonl=args.detection_jsonl,
        events_dir=args.events_dir,
        reports_dir=args.reports_dir,
        reset=args.reset,
        repeat_frames=args.repeat_frames,
        scene_mode_path=args.scene_mode,
        event_retention_seconds=args.event_retention_seconds,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

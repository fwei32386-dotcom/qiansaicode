from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from safety_brain.event_state_machine import TimelineStage


def build_event_timelines(timeline: list[TimelineStage]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in timeline:
        grouped.setdefault(item.event_key, []).append(
            {
                "event_key": item.event_key,
                "stage": item.stage,
                "frame_id": item.frame_id,
                "timestamp": item.timestamp,
                "detail": item.detail,
                "should_alarm": item.should_alarm,
            }
        )
    return grouped


def write_event_timelines(
    timeline: list[TimelineStage],
    output_dir: str | Path = "data/events/timelines",
    index_path: str | Path = "data/events/timelines/index.json",
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    grouped = build_event_timelines(timeline)
    paths: dict[str, Path] = {}
    for event_key, items in grouped.items():
        path = output / f"{_safe_name(event_key)}_timeline.json"
        payload = {
            "event_key": event_key,
            "stages": items,
            "summary": {
                "stage_count": len(items),
                "alarm_count": sum(1 for item in items if item["should_alarm"]),
                "closed_count": sum(1 for item in items if item["stage"] == "closed"),
                "first_frame": items[0]["frame_id"] if items else None,
                "last_frame": items[-1]["frame_id"] if items else None,
            },
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        paths[event_key] = path

    index = {
        "event_count": len(grouped),
        "events": [
            {
                "event_key": key,
                "timeline_path": str(path),
                "stage_count": len(grouped[key]),
            }
            for key, path in sorted(paths.items())
        ],
    }
    index_output = Path(index_path)
    index_output.parent.mkdir(parents=True, exist_ok=True)
    index_output.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["_index"] = index_output
    return paths


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)

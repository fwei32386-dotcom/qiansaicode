from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_engine.json_detection_loader import _detection_from_dict
from dashboard.static_dashboard import write_alarm_dashboard
from evidence.html_report import write_html_report
from runtime.replay_runner import ReplayRunner
from runtime.timeline_loader import DetectionFrame


def load_detection_jsonl(path: str | Path) -> list[DetectionFrame]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSONL detection") from exc
        grouped[int(payload["frame_id"])].append(payload)

    frames: list[DetectionFrame] = []
    for frame_id in sorted(grouped):
        detections = [_detection_from_dict(item) for item in grouped[frame_id]]
        frames.append(DetectionFrame(frame_id=frame_id, timestamp=float(frame_id), detections=detections))
    return frames


def replay_detection_jsonl(
    detection_jsonl: str | Path,
    csv_path: str | Path = ROOT / "reports" / "rknn_replay_event_report.csv",
    timeline_path: str | Path = ROOT / "reports" / "rknn_replay_timeline.json",
    html_path: str | Path = ROOT / "reports" / "rknn_replay_report.html",
    dashboard_path: str | Path = ROOT / "reports" / "rknn_replay_dashboard.html",
    events_dir: str | Path = ROOT / "data" / "events",
    scene_mode_path: str | Path = ROOT / "data" / "runtime" / "scene_mode.json",
) -> dict[str, Any]:
    frames = load_detection_jsonl(detection_jsonl)
    runner = ReplayRunner(events_dir=events_dir, scene_mode_path=scene_mode_path)
    result = runner.run(frames)
    csv_output = runner.write_csv_report(result, csv_path)
    timeline_output = runner.write_timeline_json(result, timeline_path)
    all_detections = [detection for frame in frames for detection in frame.detections]
    html_output = write_html_report(all_detections, result.events, result.actions, html_path)
    dashboard_output = write_alarm_dashboard(result.events, result.actions, [], dashboard_path)
    return {
        "detection_jsonl": str(Path(detection_jsonl)),
        "frames": len(frames),
        "detections": len(all_detections),
        "events": len(result.events),
        "actions": len(result.actions),
        "timeline_stages": len(result.timeline),
        "csv_path": str(csv_output),
        "timeline_path": str(timeline_output),
        "html_path": str(html_output),
        "dashboard_path": str(dashboard_output),
        "events_dir": str(Path(events_dir)),
        "scene_mode_path": str(Path(scene_mode_path)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay RKNN Detection JSONL through the SafeLab rule pipeline.")
    parser.add_argument("detection_jsonl")
    parser.add_argument("--csv", default=str(ROOT / "reports" / "rknn_replay_event_report.csv"))
    parser.add_argument("--timeline-json", default=str(ROOT / "reports" / "rknn_replay_timeline.json"))
    parser.add_argument("--html", default=str(ROOT / "reports" / "rknn_replay_report.html"))
    parser.add_argument("--dashboard", default=str(ROOT / "reports" / "rknn_replay_dashboard.html"))
    parser.add_argument("--events-dir", default=str(ROOT / "data" / "events"))
    parser.add_argument("--scene-mode", default=str(ROOT / "data" / "runtime" / "scene_mode.json"))
    args = parser.parse_args()

    output = replay_detection_jsonl(
        detection_jsonl=args.detection_jsonl,
        csv_path=args.csv,
        timeline_path=args.timeline_json,
        html_path=args.html,
        dashboard_path=args.dashboard,
        events_dir=args.events_dir,
        scene_mode_path=args.scene_mode,
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

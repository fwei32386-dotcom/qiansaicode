from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actuator.backends import create_actuator_backend
from dashboard.static_dashboard import write_alarm_dashboard
from evidence.event_timeline import write_event_timelines
from evidence.html_report import write_html_report
from evidence.risk_curve import write_risk_curve_outputs
from evidence.snapshot_manager import SnapshotManager
from runtime.replay_runner import ReplayRunner
from runtime.timeline_loader import load_timeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay a multi-frame Detection timeline.")
    parser.add_argument("timeline_json", help="Path to a timeline JSON file.")
    parser.add_argument(
        "--csv",
        default="reports/replay_event_report.csv",
        help="Output CSV report path.",
    )
    parser.add_argument(
        "--timeline-json",
        dest="timeline_json_output",
        default="reports/replay_timeline.json",
        help="Output timeline JSON path.",
    )
    parser.add_argument(
        "--html",
        default="reports/replay_latest_report.html",
        help="Output HTML report path.",
    )
    parser.add_argument(
        "--dashboard",
        default="reports/replay_alarm_dashboard.html",
        help="Output alarm dashboard path.",
    )
    parser.add_argument(
        "--execute-actions",
        action="store_true",
        help="Execute alarm actions through the configured actuator backend.",
    )
    parser.add_argument(
        "--actuator-backend",
        default="mock",
        choices=["mock", "shell", "gpio"],
        help="Actuator backend to use when --execute-actions is set.",
    )
    args = parser.parse_args()

    frames = load_timeline(args.timeline_json)
    runner = ReplayRunner()
    result = runner.run(frames)
    csv_path = runner.write_csv_report(result, args.csv)
    timeline_json_path = runner.write_timeline_json(result, args.timeline_json_output)
    event_timeline_paths = write_event_timelines(result.timeline)
    risk_curve_paths = write_risk_curve_outputs(result.timeline)
    all_detections = [detection for frame in frames for detection in frame.detections]
    snapshot_manager = SnapshotManager()
    snapshot_paths = {
        event.event_id: snapshot_manager.save_event_snapshot(event, all_detections)
        for event in result.events
        if event.need_snapshot
    }
    html_path = write_html_report(all_detections, result.events, result.actions, args.html)
    actuator_records = []
    if args.execute_actions:
        actuator = create_actuator_backend(args.actuator_backend)
        actuator_records = [actuator.execute(action) for action in result.actions]
    dashboard_path = write_alarm_dashboard(result.events, result.actions, actuator_records, args.dashboard)

    print(
        json.dumps(
            {
                "timeline_json": str(Path(args.timeline_json)),
                "frames": len(frames),
                "timeline_stages": len(result.timeline),
                "events": len(result.events),
                "actions": len(result.actions),
                "csv_path": str(csv_path),
                "timeline_json_path": str(timeline_json_path),
                "event_timelines": {key: str(value) for key, value in event_timeline_paths.items()},
                "snapshots": snapshot_paths,
                "risk_curve": {key: str(value) for key, value in risk_curve_paths.items()},
                "html_path": str(html_path),
                "dashboard_path": str(dashboard_path),
                "actuator_records": len(actuator_records),
                "actuator_backend": args.actuator_backend if args.execute_actions else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_engine.json_detection_loader import load_detections_from_json
from actuator.alarm_manager import AlarmManager
from actuator.backends import create_actuator_backend
from ai_engine.mock_detector import load_mock_detections
from dashboard.static_dashboard import write_alarm_dashboard
from evidence.html_report import write_html_report
from evidence.event_logger import EventLogger
from safety_brain.rule_dsl_engine import RuleDslEngine
from safety_brain.simple_rule_engine import SimpleRuleEngine


def run_pipeline(
    mock_case: str | None,
    scenario_json: str | None,
    report: bool,
    engine: str,
    execute_actions: bool,
    dashboard: bool,
    actuator_backend: str = "mock",
) -> int:
    if scenario_json:
        detections = load_detections_from_json(scenario_json)
        input_name = str(Path(scenario_json))
    else:
        detections = load_mock_detections(mock_case or "ppe")
        input_name = mock_case or "ppe"

    if engine == "dsl":
        rule_engine = RuleDslEngine.from_files()
    else:
        rule_engine = SimpleRuleEngine()
    alarm_manager = AlarmManager()
    logger = EventLogger()

    events = rule_engine.evaluate(detections)
    actions = [alarm_manager.build_action(event) for event in events]

    for event in events:
        logger.log_event(event.to_dict())
    for action in actions:
        logger.log_action(action.to_dict())

    actuator_records = []
    if execute_actions:
        actuator = create_actuator_backend(actuator_backend)  # type: ignore[arg-type]
        actuator_records = [actuator.execute(action) for action in actions]

    report_path = None
    if report:
        report_path = write_html_report(detections, events, actions)

    dashboard_path = None
    if dashboard:
        dashboard_path = write_alarm_dashboard(events, actions, actuator_records)

    print(
        json.dumps(
            {
                "input": input_name,
                "engine": engine,
                "detections": [d.to_dict() for d in detections],
                "events": [e.to_dict() for e in events],
                "actions": [a.to_dict() for a in actions],
                "actuator_records": actuator_records,
                "actuator_backend": actuator_backend if execute_actions else None,
                "report_path": str(report_path) if report_path else None,
                "dashboard_path": str(dashboard_path) if dashboard_path else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SafeLab mock pipeline.")
    parser.add_argument(
        "--mock-case",
        default="ppe",
        choices=["ppe", "smoke", "safe"],
        help="Mock input scenario.",
    )
    parser.add_argument(
        "--scenario-json",
        help="Read detections from a JSON scenario file instead of built-in mock data.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate reports/latest_report.html.",
    )
    parser.add_argument(
        "--engine",
        default="simple",
        choices=["simple", "dsl"],
        help="Risk engine to use.",
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
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Generate reports/alarm_dashboard.html.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(
        run_pipeline(
            args.mock_case,
            args.scenario_json,
            args.report,
            args.engine,
            args.execute_actions,
            args.dashboard,
            args.actuator_backend,
        )
    )

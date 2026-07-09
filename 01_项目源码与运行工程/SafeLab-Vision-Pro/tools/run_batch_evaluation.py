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

from actuator.alarm_manager import AlarmManager
from ai_engine.json_detection_loader import load_detections_from_json
from runtime.replay_runner import ReplayRunner
from runtime.timeline_loader import load_timeline
from safety_brain.rule_dsl_engine import RuleDslEngine
from safety_brain.simple_rule_engine import SimpleRuleEngine
from tools.generate_eval_summary import generate_eval_summary


RISK_RANK = {
    "normal": 0,
    "notice": 1,
    "warning": 2,
    "high": 3,
    "emergency": 4,
}


def run_batch_evaluation(
    cases_path: str | Path = ROOT / "configs" / "evaluation_cases.json",
    report_csv: str | Path = ROOT / "reports" / "batch_eval_report.csv",
    summary_json: str | Path = ROOT / "reports" / "batch_eval_summary.json",
) -> dict[str, Any]:
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8")).get("cases", [])
    rows = [_run_case(case) for case in cases]

    report_path = Path(report_csv)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "case_id",
            "type",
            "input",
            "passed",
            "events",
            "actions",
            "timeline_stages",
            "max_risk_level",
            "duplicate_alarm_count",
            "message",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "case_count": len(rows),
        "passed_count": sum(1 for row in rows if row["passed"]),
        "failed_count": sum(1 for row in rows if not row["passed"]),
        "report_csv": str(report_path),
        "failed_cases": [row["case_id"] for row in rows if not row["passed"]],
    }
    Path(summary_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run batch evaluation cases.")
    parser.add_argument("--cases", default=str(ROOT / "configs" / "evaluation_cases.json"))
    parser.add_argument("--report-csv", default=str(ROOT / "reports" / "batch_eval_report.csv"))
    parser.add_argument("--summary-json", default=str(ROOT / "reports" / "batch_eval_summary.json"))
    args = parser.parse_args()

    summary = run_batch_evaluation(args.cases, args.report_csv, args.summary_json)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed_count"] == 0 else 1


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    if case["type"] == "timeline":
        metrics = _run_timeline_case(case)
    else:
        metrics = _run_single_case(case)
    passed, message = _compare(metrics, case.get("expected", {}))
    return {
        "case_id": case["id"],
        "type": case["type"],
        "input": case["input"],
        "passed": passed,
        "events": metrics.get("events", 0),
        "actions": metrics.get("actions", 0),
        "timeline_stages": metrics.get("timeline_stages", 0),
        "max_risk_level": metrics.get("max_risk_level", "normal"),
        "duplicate_alarm_count": metrics.get("duplicate_alarm_count", 0),
        "message": message,
    }


def _run_single_case(case: dict[str, Any]) -> dict[str, Any]:
    detections = load_detections_from_json(ROOT / case["input"])
    if case.get("engine") == "dsl":
        events = RuleDslEngine.from_files().evaluate(detections)
    else:
        events = SimpleRuleEngine().evaluate(detections)
    actions = [AlarmManager().build_action(event) for event in events]
    return {
        "events": len(events),
        "actions": len(actions),
        "timeline_stages": 0,
        "max_risk_level": _max_risk_level([event.risk_level for event in events]),
        "duplicate_alarm_count": 0,
    }


def _run_timeline_case(case: dict[str, Any]) -> dict[str, Any]:
    frames = load_timeline(ROOT / case["input"])
    runner = ReplayRunner()
    result = runner.run(frames)
    tmp_csv = ROOT / "reports" / "_batch_tmp_replay.csv"
    runner.write_csv_report(result, tmp_csv)
    summary = generate_eval_summary(tmp_csv, ROOT / "reports" / "_batch_tmp_summary.json")
    return {
        "events": len(result.events),
        "actions": len(result.actions),
        "timeline_stages": len(result.timeline),
        "max_risk_level": _max_risk_level([event.risk_level for event in result.events]),
        "duplicate_alarm_count": summary["duplicate_alarm_count"],
    }


def _compare(metrics: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, str]:
    failures: list[str] = []
    for key, value in expected.items():
        if metrics.get(key) != value:
            failures.append(f"{key}: expected {value}, got {metrics.get(key)}")
    return (not failures, "; ".join(failures) or "ok")


def _max_risk_level(levels: list[str]) -> str:
    if not levels:
        return "normal"
    return max(levels, key=lambda level: RISK_RANK.get(level, -1))


if __name__ == "__main__":
    raise SystemExit(main())


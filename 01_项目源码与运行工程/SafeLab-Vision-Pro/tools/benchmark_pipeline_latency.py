from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
import time
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actuator.alarm_manager import AlarmManager
from ai_engine.json_detection_loader import load_detections_from_json
from evidence.event_logger import EventLogger
from runtime.pipeline_profiler import PipelineProfiler
from safety_brain.rule_dsl_engine import RuleDslEngine


DEFAULT_SCENARIO = ROOT / "data" / "mock_scenarios" / "danger_zone_ppe.json"


def benchmark_pipeline_latency(
    scenario_path: str | Path = DEFAULT_SCENARIO,
    iterations: int = 20,
    csv_path: str | Path = ROOT / "reports" / "pipeline_latency.csv",
    summary_path: str | Path = ROOT / "reports" / "pipeline_latency_summary.json",
) -> dict[str, Any]:
    scenario_path = Path(scenario_path)
    rows: list[dict[str, Any]] = []
    for index in range(1, iterations + 1):
        with tempfile.TemporaryDirectory() as tmp:
            row = _run_once(index, scenario_path, Path(tmp))
        rows.append(row)

    _write_csv(rows, csv_path)
    summary = _build_summary(rows, scenario_path, csv_path)
    Path(summary_path).parent.mkdir(parents=True, exist_ok=True)
    Path(summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark SafeLab CPU-side pipeline latency.")
    parser.add_argument("--scenario", default=str(DEFAULT_SCENARIO))
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--csv", default=str(ROOT / "reports" / "pipeline_latency.csv"))
    parser.add_argument("--summary", default=str(ROOT / "reports" / "pipeline_latency_summary.json"))
    args = parser.parse_args()

    summary = benchmark_pipeline_latency(args.scenario, args.iterations, args.csv, args.summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _run_once(index: int, scenario_path: Path, log_dir: Path) -> dict[str, Any]:
    profiler = PipelineProfiler()
    total_start = time.perf_counter()

    with profiler.stage("load_detections_ms"):
        detections = load_detections_from_json(scenario_path)
    with profiler.stage("load_rules_ms"):
        engine = RuleDslEngine.from_files()
    with profiler.stage("rule_eval_ms"):
        events = engine.evaluate(detections)
    alarm_manager = AlarmManager()
    with profiler.stage("build_actions_ms"):
        actions = [alarm_manager.build_action(event) for event in events]
    logger = EventLogger(log_dir)

    with profiler.stage("write_logs_ms"):
        for event in events:
            logger.log_event(event.to_dict())
        for action in actions:
            logger.log_action(action.to_dict())

    timings = profiler.latest()
    timings["total_ms"] = (time.perf_counter() - total_start) * 1000.0

    return {
        "iteration": index,
        "scenario": str(scenario_path),
        "detections": len(detections),
        "events": len(events),
        "actions": len(actions),
        **{key: round(value, 4) for key, value in timings.items()},
    }


def _write_csv(rows: list[dict[str, Any]], csv_path: str | Path) -> Path:
    output = Path(csv_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "iteration",
        "scenario",
        "detections",
        "events",
        "actions",
        "load_detections_ms",
        "load_rules_ms",
        "rule_eval_ms",
        "build_actions_ms",
        "write_logs_ms",
        "total_ms",
    ]
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output


def _build_summary(rows: list[dict[str, Any]], scenario_path: Path, csv_path: str | Path) -> dict[str, Any]:
    latency_keys = [
        "load_detections_ms",
        "load_rules_ms",
        "rule_eval_ms",
        "build_actions_ms",
        "write_logs_ms",
        "total_ms",
    ]
    averages = {
        key: round(mean(float(row[key]) for row in rows), 4) if rows else 0.0
        for key in latency_keys
    }
    maxima = {
        key: round(max(float(row[key]) for row in rows), 4) if rows else 0.0
        for key in latency_keys
    }
    return {
        "scenario": str(scenario_path),
        "iterations": len(rows),
        "report_csv": str(csv_path),
        "average_ms": averages,
        "max_ms": maxima,
    }


if __name__ == "__main__":
    raise SystemExit(main())

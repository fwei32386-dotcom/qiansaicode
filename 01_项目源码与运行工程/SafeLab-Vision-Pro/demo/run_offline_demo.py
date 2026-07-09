from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    _clean_outputs()
    commands = [
        ["tools/validate_config.py"],
        [
            "main.py",
            "--scenario-json",
            "data/mock_scenarios/danger_zone_ppe.json",
            "--engine",
            "dsl",
            "--report",
            "--execute-actions",
            "--dashboard",
        ],
        [
            "tools/replay_detection_file.py",
            "data/mock_scenarios/timeline_smoke.json",
            "--execute-actions",
        ],
        ["tools/visualize_scene.py"],
        ["tools/run_batch_evaluation.py"],
        ["tools/generate_eval_summary.py"],
        ["tools/generate_config_audit.py"],
        ["tools/generate_scenario_catalog.py"],
        ["tools/generate_project_status.py"],
        ["tools/generate_report_index.py"],
        ["tools/export_demo_package.py"],
    ]

    results = []
    for command in commands:
        completed = subprocess.run(
            [sys.executable, *command],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        results.append(
            {
                "command": " ".join(command),
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
        if completed.returncode != 0:
            print(json.dumps({"status": "failed", "results": results}, ensure_ascii=False, indent=2))
            return completed.returncode

    summary = {
        "status": "ok",
        "outputs": [
            "reports/latest_report.html",
            "reports/alarm_dashboard.html",
            "reports/replay_latest_report.html",
            "reports/replay_alarm_dashboard.html",
            "reports/scene_visualization.html",
            "reports/batch_eval_report.csv",
            "reports/batch_eval_summary.json",
            "reports/replay_event_report.csv",
            "reports/replay_timeline.json",
            "reports/risk_curve.csv",
            "reports/risk_curve.json",
            "reports/risk_curve.html",
            "reports/eval_summary.json",
            "reports/config_audit.json",
            "reports/config_audit.html",
            "reports/scenario_catalog.json",
            "reports/scenario_catalog.html",
            "reports/project_status.md",
            "reports/project_status.html",
            "reports/index.html",
            "reports/demo_export.zip",
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _clean_outputs() -> None:
    for path in [
        ROOT / "reports",
        ROOT / "data" / "events" / "events.jsonl",
        ROOT / "data" / "events" / "alarm_actions.jsonl",
        ROOT / "data" / "events" / "actuator_log.jsonl",
    ]:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())

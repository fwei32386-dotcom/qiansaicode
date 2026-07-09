from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print("== Validating config ==")
    validate = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate_config.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if validate.returncode != 0:
        print(validate.stdout)
        print(validate.stderr, file=sys.stderr)
        return validate.returncode
    print(validate.stdout)

    commands = [
        ["--mock-case", "ppe"],
        ["--mock-case", "smoke"],
        ["--mock-case", "safe"],
        ["--scenario-json", "data/mock_scenarios/ppe_missing_helmet.json", "--report"],
        ["--scenario-json", "data/mock_scenarios/fire_risk.json", "--report"],
        [
            "--scenario-json",
            "data/mock_scenarios/danger_zone_ppe.json",
            "--engine",
            "dsl",
            "--report",
            "--execute-actions",
            "--dashboard",
        ],
        ["--scenario-json", "data/mock_scenarios/normal_zone_no_ppe.json", "--engine", "dsl", "--report"],
    ]
    for args in commands:
        label = " ".join(args)
        print(f"== Running: {label} ==")
        completed = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            return completed.returncode
        print(completed.stdout)
    print("== Running replay timeline ==")
    replay = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "replay_detection_file.py"),
            "data/mock_scenarios/timeline_smoke.json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if replay.returncode != 0:
        print(replay.stdout)
        print(replay.stderr, file=sys.stderr)
        return replay.returncode
    print(replay.stdout)
    print("== Rendering scene visualization ==")
    scene = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "visualize_scene.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if scene.returncode != 0:
        print(scene.stdout)
        print(scene.stderr, file=sys.stderr)
        return scene.returncode
    print(scene.stdout)
    print("== Running batch evaluation ==")
    batch = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "run_batch_evaluation.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if batch.returncode != 0:
        print(batch.stdout)
        print(batch.stderr, file=sys.stderr)
        return batch.returncode
    print(batch.stdout)
    print("== Generating eval summary ==")
    summary = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "generate_eval_summary.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if summary.returncode != 0:
        print(summary.stdout)
        print(summary.stderr, file=sys.stderr)
        return summary.returncode
    print(summary.stdout)
    print("== Generating config audit ==")
    audit = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "generate_config_audit.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if audit.returncode != 0:
        print(audit.stdout)
        print(audit.stderr, file=sys.stderr)
        return audit.returncode
    print(audit.stdout)
    print("== Generating scenario catalog ==")
    catalog = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "generate_scenario_catalog.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if catalog.returncode != 0:
        print(catalog.stdout)
        print(catalog.stderr, file=sys.stderr)
        return catalog.returncode
    print(catalog.stdout)
    print("== Generating project status ==")
    status = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "generate_project_status.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if status.returncode != 0:
        print(status.stdout)
        print(status.stderr, file=sys.stderr)
        return status.returncode
    print(status.stdout)
    print("== Generating report index ==")
    index = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "generate_report_index.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if index.returncode != 0:
        print(index.stdout)
        print(index.stderr, file=sys.stderr)
        return index.returncode
    print(index.stdout)
    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

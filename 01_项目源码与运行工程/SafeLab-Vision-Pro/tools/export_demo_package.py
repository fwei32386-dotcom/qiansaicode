from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def export_demo_package(
    output_zip: str | Path = ROOT / "reports" / "demo_export.zip",
) -> Path:
    output_zip = Path(output_zip)
    export_dir = output_zip.parent / "demo_export"
    if export_dir.exists():
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "project": "SafeLab-Vision Pro",
        "description": "Offline demo export: configs, reports, dashboards, logs, and mock scenarios.",
        "files": [],
    }

    for source in _export_sources():
        src = ROOT / source
        if not src.exists():
            continue
        dst = export_dir / source
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        manifest["files"].append(source)

    manifest_path = export_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if output_zip.exists():
        output_zip.unlink()
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in export_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(export_dir))
    return output_zip


def main() -> int:
    parser = argparse.ArgumentParser(description="Export SafeLab demo reports and configs.")
    parser.add_argument("--output", default=str(ROOT / "reports" / "demo_export.zip"))
    args = parser.parse_args()

    output = export_demo_package(args.output)
    print(json.dumps({"demo_export": str(output), "size_bytes": output.stat().st_size}, indent=2))
    return 0


def _export_sources() -> list[str]:
    return [
        "README.md",
        "docs/interface_spec.md",
        "configs/semantic_map.json",
        "configs/rule_dsl.json",
        "configs/evaluation_cases.json",
        "data/mock_scenarios/danger_zone_ppe.json",
        "data/mock_scenarios/normal_zone_no_ppe.json",
        "data/mock_scenarios/timeline_smoke.json",
        "data/events/events.jsonl",
        "data/events/alarm_actions.jsonl",
        "data/events/alarm_log.db",
        "data/events/actuator_log.jsonl",
        "data/events/timelines/index.json",
        "data/events/timelines/smoke_timeline.json",
        "data/events/raw",
        "data/events/marked",
        "reports/latest_report.html",
        "reports/alarm_dashboard.html",
        "reports/replay_latest_report.html",
        "reports/replay_alarm_dashboard.html",
        "reports/scene_visualization.html",
        "reports/batch_eval_report.csv",
        "reports/batch_eval_summary.json",
        "reports/smoke_temporal_ablation.csv",
        "reports/state_machine_ablation.csv",
        "reports/ablation_summary.json",
        "reports/pipeline_latency.csv",
        "reports/pipeline_latency_summary.json",
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
    ]


if __name__ == "__main__":
    raise SystemExit(main())

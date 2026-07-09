from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def generate_project_status(
    markdown_path: str | Path = ROOT / "reports" / "project_status.md",
    html_path: str | Path = ROOT / "reports" / "project_status.html",
) -> dict[str, str]:
    markdown_path = Path(markdown_path)
    html_path = Path(html_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    status = _collect_status()
    markdown = _render_markdown(status)
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(_render_html(markdown), encoding="utf-8")
    return {"markdown": str(markdown_path), "html": str(html_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SafeLab project status report.")
    parser.add_argument("--markdown", default=str(ROOT / "reports" / "project_status.md"))
    parser.add_argument("--html", default=str(ROOT / "reports" / "project_status.html"))
    args = parser.parse_args()

    outputs = generate_project_status(args.markdown, args.html)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


def _collect_status() -> dict[str, Any]:
    batch = _read_json(ROOT / "reports" / "batch_eval_summary.json")
    eval_summary = _read_json(ROOT / "reports" / "eval_summary.json")
    test_files = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "tests").glob("test_*.py"))
    report_files = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "reports").glob("*") if path.is_file())
    return {
        "completed_features": [
            "Unified Detection, RiskEvent, and AlarmAction interfaces",
            "JSON Detection input and mock scenarios",
            "PPE association with person-region checks",
            "Semantic map and configurable rule DSL",
            "Rule priority merging and suppressed-rule explanations",
            "Smoke/fire temporal confirmation and event state machine",
            "Mock alarm actuator, static dashboards, and realtime HTTP/SSE dashboard service",
            "JSONL evidence logs mirrored into SQLite alarm_log.db",
            "Built-in rockchipnau8822 audio codec and onboard MIC probe path",
            "Scene visualization for zones, detections, PPE regions, and matched rules",
            "Batch offline evaluation and demo export package",
            "Config audit report with hashes and structure summaries",
            "Mock scenario catalog with class distribution and expected results",
        ],
        "pending_features": [
            "Real camera or video source input",
            "YOLO model inference",
            "RKNN/NPU deployment",
            "Paused stage items: GPIO LED, buzzer, and relay control",
            "Board-side Python or C/C++ runtime decision",
        ],
        "batch": batch,
        "eval_summary": eval_summary,
        "test_files": test_files,
        "report_files": report_files,
        "board_path": "/root/SafeLab-Vision-Pro",
    }


def _render_markdown(status: dict[str, Any]) -> str:
    lines = [
        "# SafeLab-Vision Pro Project Status",
        "",
        "## Current Position",
        "",
        "Offline risk cognition, rule orchestration, alarm decision, reporting, visualization, and batch evaluation are implemented. Real camera/model/hardware integration is still pending.",
        "",
        "## Completed Features",
        "",
    ]
    lines.extend(f"- {item}" for item in status["completed_features"])
    lines.extend(["", "## Pending Features", ""])
    lines.extend(f"- {item}" for item in status["pending_features"])
    lines.extend(
        [
            "",
            "## Batch Evaluation",
            "",
            f"- Cases: {status['batch'].get('case_count', 0)}",
            f"- Passed: {status['batch'].get('passed_count', 0)}",
            f"- Failed: {status['batch'].get('failed_count', 0)}",
            "",
            "## Smoke Timeline Evaluation",
            "",
            f"- Alarm count: {status['eval_summary'].get('alarm_count')}",
            f"- Duplicate alarm count: {status['eval_summary'].get('duplicate_alarm_count')}",
            f"- First alarm frame: {status['eval_summary'].get('first_alarm_frame')}",
            f"- First closed frame: {status['eval_summary'].get('first_closed_frame')}",
            "",
            "## Tests",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in status["test_files"])
    lines.extend(["", "## Generated Reports", ""])
    lines.extend(f"- {item}" for item in status["report_files"])
    lines.extend(["", "## Board Path", "", f"`{status['board_path']}`", ""])
    return "\n".join(lines)


def _render_html(markdown: str) -> str:
    body = "\n".join(_markdown_line_to_html(line) for line in markdown.splitlines())
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SafeLab Project Status</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 28px; color: #172026; line-height: 1.5; }}
    h1 {{ border-bottom: 2px solid #111827; padding-bottom: 8px; }}
    h2 {{ margin-top: 28px; }}
    code {{ background: #f2f4f7; padding: 2px 5px; border-radius: 4px; }}
    li {{ margin: 4px 0; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def _markdown_line_to_html(line: str) -> str:
    if line.startswith("# "):
        return f"<h1>{escape(line[2:])}</h1>"
    if line.startswith("## "):
        return f"<h2>{escape(line[3:])}</h2>"
    if line.startswith("- "):
        return f"<li>{escape(line[2:])}</li>"
    if line.startswith("`") and line.endswith("`"):
        return f"<p><code>{escape(line[1:-1])}</code></p>"
    if not line:
        return ""
    return f"<p>{escape(line)}</p>"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())

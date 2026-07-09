from __future__ import annotations

import csv
import json
from html import escape
from pathlib import Path
from typing import Any

from safety_brain.event_state_machine import TimelineStage


STAGE_SCORE = {
    "suspicious": 35,
    "confirmed": 65,
    "alarmed": 80,
    "closed": 0,
}


def build_risk_curve(timeline: list[TimelineStage]) -> list[dict[str, Any]]:
    return [
        {
            "event_key": item.event_key,
            "stage": item.stage,
            "frame_id": item.frame_id,
            "timestamp": item.timestamp,
            "risk_score": STAGE_SCORE.get(item.stage, 0),
            "detail": item.detail,
        }
        for item in timeline
    ]


def write_risk_curve_outputs(
    timeline: list[TimelineStage],
    csv_path: str | Path = "reports/risk_curve.csv",
    json_path: str | Path = "reports/risk_curve.json",
    html_path: str | Path = "reports/risk_curve.html",
) -> dict[str, Path]:
    curve = build_risk_curve(timeline)
    csv_output = _write_csv(curve, csv_path)
    json_output = _write_json(curve, json_path)
    html_output = _write_html(curve, html_path)
    return {"csv": csv_output, "json": json_output, "html": html_output}


def _write_csv(curve: list[dict[str, Any]], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["event_key", "stage", "frame_id", "timestamp", "risk_score", "detail"],
        )
        writer.writeheader()
        writer.writerows(curve)
    return output


def _write_json(curve: list[dict[str, Any]], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"risk_curve": curve}, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def _write_html(curve: list[dict[str, Any]], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render_html(curve), encoding="utf-8")
    return output


def _render_html(curve: list[dict[str, Any]]) -> str:
    width = 760
    height = 320
    padding = 44
    points = _svg_points(curve, width, height, padding)
    circles = "\n".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#b42318"><title>{escape(item["stage"])} {item["risk_score"]}</title></circle>'
        for (x, y), item in zip(points, curve)
    )
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    rows = "".join(
        f"<tr><td>{item['frame_id']}</td><td>{item['timestamp']}</td><td>{escape(item['stage'])}</td>"
        f"<td>{item['risk_score']}</td><td>{escape(item['detail'])}</td></tr>"
        for item in curve
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SafeLab Risk Curve</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 28px; color: #172026; }}
    svg {{ border: 1px solid #d8dee4; background: #fbfcfd; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 18px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; font-size: 14px; text-align: left; }}
    th {{ background: #eef1f4; }}
  </style>
</head>
<body>
  <h1>SafeLab Risk Curve</h1>
  <svg viewBox="0 0 {width} {height}" role="img" aria-label="risk curve">
    <line x1="{padding}" y1="{height - padding}" x2="{width - padding}" y2="{height - padding}" stroke="#111827" />
    <line x1="{padding}" y1="{padding}" x2="{padding}" y2="{height - padding}" stroke="#111827" />
    <text x="8" y="{padding}" font-size="13">100</text>
    <text x="18" y="{height - padding}" font-size="13">0</text>
    <polyline points="{polyline}" fill="none" stroke="#b42318" stroke-width="4" />
    {circles}
  </svg>
  <table>
    <tr><th>Frame</th><th>Time</th><th>Stage</th><th>Risk Score</th><th>Detail</th></tr>
    {rows}
  </table>
</body>
</html>
"""


def _svg_points(curve: list[dict[str, Any]], width: int, height: int, padding: int) -> list[tuple[float, float]]:
    if not curve:
        return []
    timestamps = [float(item["timestamp"]) for item in curve]
    min_t = min(timestamps)
    max_t = max(timestamps)
    span = max(max_t - min_t, 1.0)
    points: list[tuple[float, float]] = []
    for item in curve:
        t = float(item["timestamp"])
        score = float(item["risk_score"])
        x = padding + (t - min_t) / span * (width - padding * 2)
        y = height - padding - score / 100.0 * (height - padding * 2)
        points.append((x, y))
    return points


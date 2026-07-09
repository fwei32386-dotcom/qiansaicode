from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_engine.json_detection_loader import load_detections_from_json
from safety_brain.ppe_association import associate_ppe
from safety_brain.rule_dsl_engine import RuleDslEngine
from safety_brain.scene_graph import SceneGraph


def write_scene_visualization(
    scenario_json: str | Path = ROOT / "data" / "mock_scenarios" / "danger_zone_ppe.json",
    semantic_map: str | Path = ROOT / "configs" / "semantic_map.json",
    rule_dsl: str | Path = ROOT / "configs" / "rule_dsl.json",
    output_path: str | Path = ROOT / "reports" / "scene_visualization.html",
) -> Path:
    detections = load_detections_from_json(scenario_json)
    scene = SceneGraph.from_json(semantic_map)
    events = RuleDslEngine.from_files(semantic_map, rule_dsl).evaluate(detections)
    ppe = associate_ppe(detections)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render(scene, detections, events, ppe), encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Render semantic map and Detection boxes as HTML/SVG.")
    parser.add_argument("--scenario-json", default=str(ROOT / "data" / "mock_scenarios" / "danger_zone_ppe.json"))
    parser.add_argument("--semantic-map", default=str(ROOT / "configs" / "semantic_map.json"))
    parser.add_argument("--rule-dsl", default=str(ROOT / "configs" / "rule_dsl.json"))
    parser.add_argument("--output", default=str(ROOT / "reports" / "scene_visualization.html"))
    args = parser.parse_args()

    output = write_scene_visualization(args.scenario_json, args.semantic_map, args.rule_dsl, args.output)
    print(json.dumps({"scene_visualization": str(output), "size_bytes": output.stat().st_size}, indent=2))
    return 0


def _render(scene: SceneGraph, detections, events, ppe) -> str:
    svg_width = 960
    svg_height = 760
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SafeLab Scene Visualization</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #172026; background: #f7f8fa; }}
    header {{ padding: 20px 28px; background: #111827; color: white; }}
    main {{ padding: 24px 28px; display: grid; grid-template-columns: minmax(720px, 1fr) 360px; gap: 20px; }}
    .panel {{ background: white; border: 1px solid #d8dee4; border-radius: 6px; padding: 16px; }}
    svg {{ width: 100%; height: auto; background: #fbfcfd; border: 1px solid #d8dee4; }}
    .risk-high {{ color: #b42318; font-weight: bold; }}
    .muted {{ color: #6b7280; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; font-size: 13px; }}
  </style>
</head>
<body>
  <header>
    <h1>SafeLab Scene Visualization</h1>
    <div class="muted">Semantic zones, Detection boxes, PPE association, and matched rule events.</div>
  </header>
  <main>
    <section class="panel">
      <svg viewBox="0 0 {svg_width} {svg_height}" role="img" aria-label="scene visualization">
        {_zone_svg(scene)}
        {_ppe_region_svg(ppe)}
        {_detection_svg(detections)}
      </svg>
    </section>
    <aside class="panel">
      <h2>Rule Events</h2>
      {_events_html(events)}
      <h2>PPE Association</h2>
      {_ppe_html(ppe)}
      <h2>Legend</h2>
      <table>
        <tr><td><strong style="color:#b42318">Red zone</strong></td><td>danger_zone</td></tr>
        <tr><td><strong style="color:#175cd3">Blue zone</strong></td><td>normal_zone</td></tr>
        <tr><td><strong>Dashed boxes</strong></td><td>expected PPE regions</td></tr>
      </table>
    </aside>
  </main>
</body>
</html>
"""


def _zone_svg(scene: SceneGraph) -> str:
    parts: list[str] = []
    for zone in scene.zones:
        points = " ".join(f"{x},{y}" for x, y in zone.polygon)
        is_danger = zone.zone_id == "danger_zone"
        fill = "#fee4e2" if is_danger else "#dbeafe"
        stroke = "#b42318" if is_danger else "#175cd3"
        parts.append(
            f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="3" opacity="0.55" />'
        )
        x, y = zone.polygon[0]
        parts.append(
            f'<text x="{x + 10}" y="{y + 28}" fill="{stroke}" font-size="22" font-weight="700">{escape(zone.zone_id)}</text>'
        )
    return "\n".join(parts)


def _detection_svg(detections) -> str:
    colors = {
        "person": "#111827",
        "helmet": "#16a34a",
        "vest": "#f59e0b",
        "smoke": "#6b7280",
        "fire": "#dc2626",
    }
    parts: list[str] = []
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox
        color = colors.get(detection.class_name, "#111827")
        parts.append(
            f'<rect x="{x1}" y="{y1}" width="{x2 - x1}" height="{y2 - y1}" '
            f'fill="none" stroke="{color}" stroke-width="4" />'
        )
        parts.append(
            f'<text x="{x1}" y="{max(y1 - 8, 18)}" fill="{color}" font-size="18" font-weight="700">'
            f'{escape(detection.class_name)} {detection.confidence:.2f}</text>'
        )
    return "\n".join(parts)


def _ppe_region_svg(ppe) -> str:
    parts: list[str] = []
    for item in ppe:
        x1, y1, x2, y2 = item.person.bbox
        height = y2 - y1
        helmet_y2 = y1 + height * 0.45
        vest_y1 = y1 + height * 0.30
        vest_y2 = y1 + height * 0.95
        parts.append(
            f'<rect x="{x1}" y="{y1}" width="{x2 - x1}" height="{helmet_y2 - y1}" '
            f'fill="none" stroke="#16a34a" stroke-width="2" stroke-dasharray="8 6" />'
        )
        parts.append(
            f'<rect x="{x1}" y="{vest_y1}" width="{x2 - x1}" height="{vest_y2 - vest_y1}" '
            f'fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="8 6" />'
        )
    return "\n".join(parts)


def _events_html(events) -> str:
    if not events:
        return "<p>No rule events.</p>"
    rows = [
        "<tr><th>Rule</th><th>Level</th><th>Reasons</th></tr>",
        *[
            f"<tr><td>{escape(event.rule_id or '')}</td><td class=\"risk-high\">{escape(event.risk_level)}</td>"
            f"<td>{escape('; '.join(event.reasons))}</td></tr>"
            for event in events
        ],
    ]
    return "<table>" + "".join(rows) + "</table>"


def _ppe_html(ppe) -> str:
    if not ppe:
        return "<p>No person detections.</p>"
    rows = ["<tr><th>Person</th><th>Helmet</th><th>Vest</th><th>Missing</th></tr>"]
    for index, item in enumerate(ppe, start=1):
        rows.append(
            f"<tr><td>person_{index}</td><td>{item.has_helmet}</td><td>{item.has_vest}</td>"
            f"<td>{escape(', '.join(item.missing_ppe) or 'none')}</td></tr>"
        )
    return "<table>" + "".join(rows) + "</table>"


if __name__ == "__main__":
    raise SystemExit(main())


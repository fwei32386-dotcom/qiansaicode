from __future__ import annotations

import argparse
import json
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def generate_scenario_catalog(
    scenarios_dir: str | Path = ROOT / "data" / "mock_scenarios",
    evaluation_cases_path: str | Path = ROOT / "configs" / "evaluation_cases.json",
    json_path: str | Path = ROOT / "reports" / "scenario_catalog.json",
    html_path: str | Path = ROOT / "reports" / "scenario_catalog.html",
) -> dict[str, str]:
    scenarios_dir = Path(scenarios_dir)
    evaluation_cases_path = Path(evaluation_cases_path)
    json_path = Path(json_path)
    html_path = Path(html_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)

    catalog = _collect_catalog(scenarios_dir, evaluation_cases_path)
    json_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(_render_html(catalog), encoding="utf-8")
    return {"json": str(json_path), "html": str(html_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SafeLab mock scenario catalog.")
    parser.add_argument("--scenarios-dir", default=str(ROOT / "data" / "mock_scenarios"))
    parser.add_argument("--evaluation-cases", default=str(ROOT / "configs" / "evaluation_cases.json"))
    parser.add_argument("--json", default=str(ROOT / "reports" / "scenario_catalog.json"))
    parser.add_argument("--html", default=str(ROOT / "reports" / "scenario_catalog.html"))
    args = parser.parse_args()

    outputs = generate_scenario_catalog(args.scenarios_dir, args.evaluation_cases, args.json, args.html)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


def _collect_catalog(scenarios_dir: Path, evaluation_cases_path: Path) -> dict[str, Any]:
    cases_by_input = _cases_by_input(evaluation_cases_path)
    scenarios = []
    for path in sorted(scenarios_dir.glob("*.json")):
        scenario = _inspect_scenario(path, scenarios_dir)
        scenario["evaluation_cases"] = cases_by_input.get(f"data/mock_scenarios/{path.name}", [])
        scenarios.append(scenario)
    return {
        "project": "SafeLab-Vision Pro",
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    }


def _cases_by_input(evaluation_cases_path: Path) -> dict[str, list[dict[str, Any]]]:
    if not evaluation_cases_path.exists():
        return {}
    data = json.loads(evaluation_cases_path.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for case in data.get("cases", []):
        grouped.setdefault(case.get("input", ""), []).append(
            {
                "id": case.get("id"),
                "type": case.get("type"),
                "engine": case.get("engine", ""),
                "expected": case.get("expected", {}),
            }
        )
    return grouped


def _inspect_scenario(path: Path, scenarios_dir: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    frames = _frames(data)
    detections = [detection for frame in frames for detection in frame["detections"]]
    classes = Counter(str(item.get("class_name", "unknown")) for item in detections)
    confidences = [float(item.get("confidence", 0)) for item in detections if "confidence" in item]
    return {
        "file": str(path.relative_to(scenarios_dir)),
        "name": data.get("name", path.stem),
        "type": "timeline" if "frames" in data else "single",
        "frame_count": len(frames),
        "detection_count": len(detections),
        "class_counts": dict(sorted(classes.items())),
        "confidence_min": min(confidences) if confidences else None,
        "confidence_max": max(confidences) if confidences else None,
        "frame_ids": [frame["frame_id"] for frame in frames],
    }


def _frames(data: dict[str, Any]) -> list[dict[str, Any]]:
    if "frames" in data:
        return [
            {
                "frame_id": frame.get("frame_id"),
                "detections": frame.get("detections", []),
            }
            for frame in data.get("frames", [])
        ]
    detections = data.get("detections", [])
    frame_id = detections[0].get("frame_id") if detections else None
    return [{"frame_id": frame_id, "detections": detections}]


def _render_html(catalog: dict[str, Any]) -> str:
    rows = "\n".join(_row_html(item) for item in catalog["scenarios"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SafeLab Scenario Catalog</title>
  <style>
    body {{ margin: 28px; font-family: Arial, sans-serif; color: #172026; line-height: 1.45; }}
    h1 {{ margin-bottom: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 18px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f2f4f7; }}
    code {{ font-family: Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }}
    .meta {{ color: #667085; }}
  </style>
</head>
<body>
  <h1>SafeLab Scenario Catalog</h1>
  <div class="meta">{catalog["scenario_count"]} mock scenarios inspected.</div>
  <table>
    <thead><tr><th>Scenario</th><th>Frames</th><th>Detections</th><th>Classes</th><th>Evaluation</th></tr></thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
"""


def _row_html(item: dict[str, Any]) -> str:
    confidence = _confidence_text(item)
    cases = json.dumps(item["evaluation_cases"], ensure_ascii=False, sort_keys=True)
    classes = json.dumps(item["class_counts"], ensure_ascii=False, sort_keys=True)
    return (
        "<tr>"
        f"<td><strong>{escape(item['name'])}</strong><br><code>{escape(item['file'])}</code><br>{escape(item['type'])}</td>"
        f"<td>{item['frame_count']}<br><span class=\"meta\">{escape(str(item['frame_ids']))}</span></td>"
        f"<td>{item['detection_count']}<br><span class=\"meta\">{escape(confidence)}</span></td>"
        f"<td><code>{escape(classes)}</code></td>"
        f"<td><code>{escape(cases)}</code></td>"
        "</tr>"
    )


def _confidence_text(item: dict[str, Any]) -> str:
    if item["confidence_min"] is None or item["confidence_max"] is None:
        return "confidence: n/a"
    return f"confidence: {item['confidence_min']:.2f}-{item['confidence_max']:.2f}"


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_TARGETS = {
    "person": (0.70, 0.70),
    "helmet": (0.70, 0.70),
    "vest": (0.70, 0.70),
    "goggles": (0.70, 0.70),
    "gloves": (0.70, 0.70),
    "fire": (0.70, 0.70),
    "smoke": (0.70, 0.70),
}


@dataclass(frozen=True)
class AcceptanceTarget:
    min_precision: float
    min_recall: float


def default_targets() -> dict[str, AcceptanceTarget]:
    return {
        class_name: AcceptanceTarget(min_precision=precision, min_recall=recall)
        for class_name, (precision, recall) in DEFAULT_TARGETS.items()
    }


def evaluate_metrics_csv(
    metrics_path: Path,
    targets: dict[str, AcceptanceTarget] | None = None,
) -> dict[str, Any]:
    active_targets = targets or default_targets()
    classes: dict[str, Any] = {}
    with metrics_path.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            class_name = row["class_name"]
            precision = float(row["precision"])
            recall = float(row["recall"])
            target = active_targets.get(class_name)
            reasons: list[str] = []
            if target is not None:
                if precision < target.min_precision:
                    reasons.append(f"precision {precision:.3f} < {target.min_precision:.3f}")
                if recall < target.min_recall:
                    reasons.append(f"recall {recall:.3f} < {target.min_recall:.3f}")
            classes[class_name] = {
                "precision": precision,
                "recall": recall,
                "status": "fail" if reasons else "pass",
                "reasons": reasons,
            }
    return {
        "qualified": all(item["status"] == "pass" for item in classes.values()),
        "metrics_path": str(metrics_path),
        "classes": classes,
    }


def write_acceptance_report(result: dict[str, Any], output_path: Path, source_plan: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        "# YOLO Acceptance Report",
        "",
        f"- source_plan: {source_plan}",
        f"- metrics_path: {result['metrics_path']}",
        f"- qualified: {str(result['qualified']).lower()}",
        "",
        "## Detection contract",
        "",
        "Candidate models must preserve the stable label order and output objects that can be adapted to `Detection` in `docs/interface_spec.md`.",
        "",
        "| class | precision | recall | status | reasons |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for class_name, item in result["classes"].items():
        rows.append(
            f"| {class_name} | {item['precision']:.3f} | {item['recall']:.3f} | {item['status']} | {', '.join(item['reasons'])} |"
        )
    rows.extend(
        [
            "",
            "## Next Gate",
            "",
            "- If qualified is false, do not replace the deployed model.",
            "- Continue with data review, hard-example curation, threshold or temporal-rule tuning, then rerun the same fixed probe.",
        ]
    )
    output_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a SafeLab YOLO acceptance report from probe IoU metrics.")
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--source-plan", default="SafeLab-Vision Pro master DOCX")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = evaluate_metrics_csv(args.metrics)
    write_acceptance_report(result, args.output_md, args.source_plan)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

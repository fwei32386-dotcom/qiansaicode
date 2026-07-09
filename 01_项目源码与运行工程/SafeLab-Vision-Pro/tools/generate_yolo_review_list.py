from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PRIORITY_CLASSES = {"gloves", "vest", "fire", "smoke"}


def load_probe_report(report_path: Path) -> dict[str, Any]:
    return json.loads(report_path.read_text(encoding="utf-8"))


def rank_review_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in report["rows"]:
        missed = row.get("missed_truth", [])
        false_positive = row.get("false_positive", [])
        priority_hits = [name for name in missed + false_positive if name in PRIORITY_CLASSES]
        if not priority_hits:
            continue
        reason_counts = Counter(priority_hits)
        rows.append(
            {
                "image": row["image"],
                "truth": ", ".join(row.get("truth", [])),
                "predictions": ", ".join(row.get("predictions", [])),
                "missed_truth": ", ".join(missed),
                "false_positive": ", ".join(false_positive),
                "priority_score": len(priority_hits),
                "review_reason": ", ".join(f"{name}:{count}" for name, count in sorted(reason_counts.items())),
            }
        )
    rows.sort(key=lambda item: (-int(item["priority_score"]), item["image"]))
    return rows


def write_review_list(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["image", "priority_score", "review_reason", "truth", "predictions", "missed_truth", "false_positive"]
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a prioritized manual review list from a YOLO probe report.")
    parser.add_argument("--report-json", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = load_probe_report(args.report_json)
    rows = rank_review_rows(report)
    write_review_list(rows, args.output_csv)
    print(f"wrote {len(rows)} review rows to {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _load_manifest(manifest_json: Path) -> dict[str, dict[str, Any]]:
    records = json.loads(manifest_json.read_text(encoding="utf-8"))
    by_image: dict[str, dict[str, Any]] = {}
    for record in records:
        image_name = Path(record["image"]).name
        by_image[image_name] = record
    return by_image


def enrich_review_rows(review_csv: Path, manifest_json: Path) -> list[dict[str, str]]:
    manifest = _load_manifest(manifest_json)
    rows: list[dict[str, str]] = []
    with review_csv.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            source = manifest.get(row["image"], {})
            rows.append(
                {
                    **row,
                    "source_image": str(source.get("image_path", "")),
                    "source_label": str(source.get("label_path", "")),
                    "source_split": str(source.get("split", "")),
                    "target_class": str(source.get("class_name", "")),
                }
            )
    return rows


def write_enriched_rows(rows: list[dict[str, str]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with output_csv.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add source dataset paths to a YOLO review CSV.")
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--manifest-json", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = enrich_review_rows(args.review_csv, args.manifest_json)
    write_enriched_rows(rows, args.output_csv)
    print(f"wrote {len(rows)} enriched rows to {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

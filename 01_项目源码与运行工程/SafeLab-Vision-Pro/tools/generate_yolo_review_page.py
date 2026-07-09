from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Any


def build_review_items(review_csv: Path, prediction_image_dir: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with review_csv.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            preview_path = prediction_image_dir / row["image"]
            items.append(
                {
                    **row,
                    "preview_exists": preview_path.exists(),
                    "preview_relative": f"../predictions/conf250/{row['image']}",
                }
            )
    return items


def write_review_page(items: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        '<!doctype html><meta charset="utf-8"><title>YOLO Manual Review</title>',
        "<style>",
        "body{font-family:Arial,sans-serif;margin:24px;background:#f7f7f7;color:#202124}",
        "h1{margin-bottom:4px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px}",
        ".card{background:white;border:1px solid #ddd;border-radius:8px;padding:12px;box-shadow:0 1px 2px #0001}",
        ".score{display:inline-block;background:#111;color:#fff;border-radius:12px;padding:2px 8px;font-size:12px}",
        ".reason{font-weight:bold;color:#b00020}.kv{font-size:13px;margin:4px 0}.muted{color:#666}",
        "img{width:100%;max-height:280px;object-fit:contain;background:#111;border-radius:4px}",
        "textarea{width:100%;min-height:72px;margin-top:8px}",
        "</style>",
        "<h1>YOLO Manual Review</h1>",
        '<p class="muted">Review priority samples before changing labels or retraining. This page is static; write decisions in the CSV or your labeling tool.</p>',
        "<div class=\"grid\">",
    ]
    for index, item in enumerate(items, 1):
        preview = ""
        if item["preview_exists"]:
            src = html.escape(item["preview_relative"])
            preview = f'<a href="{src}"><img src="{src}" alt="{html.escape(item["image"])}"></a>'
        else:
            preview = '<div class="muted">Preview image missing</div>'
        rows.extend(
            [
                '<section class="card">',
                f'<div><span class="score">#{index} score {html.escape(str(item["priority_score"]))}</span></div>',
                f'<h3>{html.escape(item["image"])}</h3>',
                preview,
                f'<div class="kv reason">Reason: {html.escape(item["review_reason"])}</div>',
                f'<div class="kv"><b>Truth:</b> {html.escape(item["truth"])}</div>',
                f'<div class="kv"><b>Pred:</b> {html.escape(item["predictions"])}</div>',
                f'<div class="kv"><b>Missed:</b> {html.escape(item["missed_truth"])}</div>',
                f'<div class="kv"><b>False positive:</b> {html.escape(item["false_positive"])}</div>',
                '<textarea placeholder="Manual decision: keep / relabel / remove / add negative note"></textarea>',
                "</section>",
            ]
        )
    rows.append("</div>")
    output_path.write_text("\n".join(rows), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a static HTML page for YOLO manual review samples.")
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--prediction-images", required=True, type=Path)
    parser.add_argument("--output-html", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    items = build_review_items(args.review_csv, args.prediction_images)
    write_review_page(items, args.output_html)
    sidecar = args.output_html.with_suffix(".json")
    sidecar.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(items)} review cards to {args.output_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

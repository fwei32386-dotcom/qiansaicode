from __future__ import annotations

import argparse
import csv
import html
import shutil
from pathlib import Path
from typing import Any


FIRE_SMOKE = {"fire", "smoke"}
SMALL_PPE = {"gloves", "vest"}


def _split_classes(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def classify_review_row(row: dict[str, str]) -> dict[str, str]:
    truth = _split_classes(row.get("truth", ""))
    predictions = _split_classes(row.get("predictions", ""))
    missed = _split_classes(row.get("missed_truth", ""))
    false_positive = _split_classes(row.get("false_positive", ""))
    involved = truth | predictions | missed | false_positive

    if involved & FIRE_SMOKE and (missed | false_positive) & FIRE_SMOKE:
        issue_type = "fire_smoke_boundary"
        suggested_action = "manual_relabel_or_split"
        rationale = "Fire/smoke miss or false positive suggests label boundary confusion or weak smoke/fire examples."
    elif (missed | false_positive) & SMALL_PPE:
        issue_type = "small_ppe_recall"
        suggested_action = "add_or_relabel_training_example"
        rationale = "Gloves/vest failures are likely small-object recall, occlusion, or loose labels."
    else:
        issue_type = "general_detection_review"
        suggested_action = "manual_review"
        rationale = "Review image and label quality before using it for retraining."

    return {
        "issue_type": issue_type,
        "suggested_action": suggested_action,
        "rationale": rationale,
    }


def make_cleaning_plan(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        decision = classify_review_row(row)
        output.append({**row, **decision, "decision": "unreviewed", "notes": ""})
    output.sort(key=lambda item: (-int(item.get("priority_score", "0") or 0), item["image"]))
    return output


def read_review_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_cleaning_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "image",
        "priority_score",
        "issue_type",
        "suggested_action",
        "decision",
        "review_reason",
        "truth",
        "predictions",
        "missed_truth",
        "false_positive",
        "rationale",
        "source_image",
        "source_label",
        "source_split",
        "target_class",
        "notes",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_cleaning_html(rows: list[dict[str, str]], output_path: Path, prediction_dir: Path | None = None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_rows = [
        '<!doctype html><meta charset="utf-8"><title>YOLO Cleaning Plan</title>',
        "<style>body{font-family:Arial,sans-serif;margin:24px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:6px;vertical-align:top}th{background:#f2f2f2}.fire_smoke_boundary{background:#fff1f0}.small_ppe_recall{background:#fffbe6}img{max-width:260px;max-height:180px}</style>",
        "<h1>YOLO Cleaning Plan</h1>",
        "<table><tr><th>Image</th><th>Issue</th><th>Action</th><th>Reason</th><th>Truth</th><th>Pred</th><th>Missed</th><th>False Positive</th><th>Preview</th></tr>",
    ]
    for row in rows:
        preview = ""
        if prediction_dir is not None:
            image_path = prediction_dir / row["image"]
            if image_path.exists():
                relative = Path("predictions") / "conf250" / row["image"]
                preview = f'<a href="{relative.as_posix()}"><img src="{relative.as_posix()}"></a>'
        html_rows.append(
            f'<tr class="{html.escape(row["issue_type"])}">'
            f'<td>{html.escape(row["image"])}</td>'
            f'<td>{html.escape(row["issue_type"])}</td>'
            f'<td>{html.escape(row["suggested_action"])}</td>'
            f'<td>{html.escape(row["review_reason"])}</td>'
            f'<td>{html.escape(row["truth"])}</td>'
            f'<td>{html.escape(row["predictions"])}</td>'
            f'<td>{html.escape(row["missed_truth"])}</td>'
            f'<td>{html.escape(row["false_positive"])}</td>'
            f"<td>{preview}</td>"
            "</tr>"
        )
    html_rows.append("</table>")
    output_path.write_text("\n".join(html_rows), encoding="utf-8")


def write_review_pack(rows: list[dict[str, str]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_dir = output_dir / "images"
    label_dir = output_dir / "labels"
    image_dir.mkdir(exist_ok=True)
    label_dir.mkdir(exist_ok=True)

    manifest_rows: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        source_image = Path(row.get("source_image", ""))
        source_label = Path(row.get("source_label", ""))
        issue_type = row.get("issue_type", "review").replace(" ", "_")
        target_class = row.get("target_class", "unknown").replace(" ", "_")
        base_name = f"{index:04d}_{issue_type}_{target_class}"
        copied_image = ""
        copied_label = ""
        if source_image.exists():
            image_name = f"{base_name}{source_image.suffix.lower()}"
            shutil.copy2(source_image, image_dir / image_name)
            copied_image = image_name
        if source_label.exists():
            label_name = f"{base_name}.txt"
            shutil.copy2(source_label, label_dir / label_name)
            copied_label = label_name
        manifest_rows.append(
            {
                "pack_image": copied_image,
                "pack_label": copied_label,
                "original_image": str(source_image),
                "original_label": str(source_label),
                "issue_type": row.get("issue_type", ""),
                "target_class": row.get("target_class", ""),
                "review_reason": row.get("review_reason", ""),
            }
        )

    with (output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as csv_file:
        fieldnames = ["pack_image", "pack_label", "original_image", "original_label", "issue_type", "target_class", "review_reason"]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a conservative manual cleaning plan from YOLO review rows.")
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--output-html", type=Path)
    parser.add_argument("--prediction-images", type=Path)
    parser.add_argument("--review-pack-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = make_cleaning_plan(read_review_csv(args.review_csv))
    write_cleaning_csv(rows, args.output_csv)
    if args.output_html:
        write_cleaning_html(rows, args.output_html, args.prediction_images)
    if args.review_pack_dir:
        write_review_pack(rows, args.review_pack_dir)
    print(f"wrote {len(rows)} cleaning rows to {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

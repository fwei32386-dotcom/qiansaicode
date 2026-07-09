from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Any

from PIL import Image


DEFAULT_CLASS_NAMES = {
    0: "person",
    1: "helmet",
    2: "vest",
    3: "goggles",
    4: "gloves",
    5: "fire",
    6: "smoke",
}
CLASS_NAMES = DEFAULT_CLASS_NAMES


def load_class_names(data_yaml: Path) -> dict[int, str]:
    if not data_yaml.exists():
        return DEFAULT_CLASS_NAMES
    names: dict[int, str] = {}
    for line in data_yaml.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        if key.strip().isdigit():
            names[int(key.strip())] = value.strip()
    return names or DEFAULT_CLASS_NAMES


def yolo_to_xyxy(values: list[float] | list[str], width: int, height: int) -> list[float]:
    x_center, y_center, box_width, box_height = [float(value) for value in values]
    return [
        (x_center - box_width / 2) * width,
        (y_center - box_height / 2) * height,
        (x_center + box_width / 2) * width,
        (y_center + box_height / 2) * height,
    ]


def box_iou(left: list[float], right: list[float]) -> float:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[2], right[2])
    y2 = min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _image_size(image_path: Path) -> tuple[int, int]:
    with Image.open(image_path) as image:
        return image.size


def _read_truth(label_path: Path, image_path: Path) -> list[dict[str, Any]]:
    width, height = _image_size(image_path)
    boxes: list[dict[str, Any]] = []
    for line in label_path.read_text(errors="ignore").splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        boxes.append(
            {
                "class_id": int(float(parts[0])),
                "box": yolo_to_xyxy(parts[1:5], width, height),
                "matched": False,
            }
        )
    return boxes


def _read_predictions(label_path: Path, image_path: Path) -> list[dict[str, Any]]:
    if not label_path.exists():
        return []
    width, height = _image_size(image_path)
    boxes: list[dict[str, Any]] = []
    for line in label_path.read_text(errors="ignore").splitlines():
        parts = line.split()
        if len(parts) < 6:
            continue
        boxes.append(
            {
                "class_id": int(float(parts[0])),
                "box": yolo_to_xyxy(parts[1:5], width, height),
                "confidence": float(parts[5]),
                "matched": False,
            }
        )
    return boxes


def evaluate_probe(
    image_dir: Path,
    truth_label_dir: Path,
    prediction_label_dir: Path,
    iou_threshold: float = 0.5,
    class_names: dict[int, str] | None = None,
) -> dict[str, Any]:
    names = class_names or DEFAULT_CLASS_NAMES
    stats = {
        class_id: {"class_id": class_id, "class_name": name, "gt": 0, "pred": 0, "tp": 0, "fp": 0, "fn": 0}
        for class_id, name in names.items()
    }
    rows: list[dict[str, Any]] = []

    image_paths = [
        path
        for path in sorted(image_dir.iterdir())
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
    ]
    for image_path in image_paths:
        truth = _read_truth(truth_label_dir / f"{image_path.stem}.txt", image_path)
        predictions = _read_predictions(prediction_label_dir / f"{image_path.stem}.txt", image_path)

        for item in truth:
            stats.setdefault(item["class_id"], {"class_id": item["class_id"], "class_name": str(item["class_id"]), "gt": 0, "pred": 0, "tp": 0, "fp": 0, "fn": 0})
            stats[item["class_id"]]["gt"] += 1
        for item in predictions:
            stats.setdefault(item["class_id"], {"class_id": item["class_id"], "class_name": str(item["class_id"]), "gt": 0, "pred": 0, "tp": 0, "fp": 0, "fn": 0})
            stats[item["class_id"]]["pred"] += 1

        for prediction in sorted(predictions, key=lambda item: item["confidence"], reverse=True):
            best_iou = 0.0
            best_truth: dict[str, Any] | None = None
            for truth_item in truth:
                if truth_item["matched"] or truth_item["class_id"] != prediction["class_id"]:
                    continue
                current_iou = box_iou(prediction["box"], truth_item["box"])
                if current_iou > best_iou:
                    best_iou = current_iou
                    best_truth = truth_item
            if best_truth is not None and best_iou >= iou_threshold:
                prediction["matched"] = True
                best_truth["matched"] = True
                stats[prediction["class_id"]]["tp"] += 1
            else:
                stats[prediction["class_id"]]["fp"] += 1

        for truth_item in truth:
            if not truth_item["matched"]:
                stats[truth_item["class_id"]]["fn"] += 1

        rows.append(
            {
                "image": image_path.name,
                "truth": [stats[item["class_id"]]["class_name"] for item in truth],
                "predictions": [stats[item["class_id"]]["class_name"] for item in predictions],
                "missed_truth": [stats[item["class_id"]]["class_name"] for item in truth if not item["matched"]],
                "false_positive": [stats[item["class_id"]]["class_name"] for item in predictions if not item["matched"]],
            }
        )

    metrics = []
    for class_id in sorted(stats):
        item = stats[class_id]
        precision_denominator = item["tp"] + item["fp"]
        recall_denominator = item["tp"] + item["fn"]
        item["precision"] = item["tp"] / precision_denominator if precision_denominator else 0.0
        item["recall"] = item["tp"] / recall_denominator if recall_denominator else 0.0
        metrics.append(item)
    return {"metrics": metrics, "rows": rows, "iou_threshold": iou_threshold}


def write_outputs(result: dict[str, Any], output_dir: Path, prediction_image_dir: Path | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "iou_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    with (output_dir / "iou_metrics.csv").open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(result["metrics"][0].keys()))
        writer.writeheader()
        writer.writerows(result["metrics"])

    html_rows = [
        '<!doctype html><meta charset="utf-8"><title>YOLO Probe IoU Report</title>',
        "<style>body{font-family:Arial,sans-serif;margin:24px}table{border-collapse:collapse;width:100%;margin:12px 0}td,th{border:1px solid #ddd;padding:6px}th{background:#f2f2f2}.bad{background:#ffecec}.mid{background:#fff8df}.ok{background:#edfff0}img{max-width:260px;max-height:180px}</style>",
        "<h1>YOLO Probe IoU Report</h1>",
        "<table><tr><th>Class</th><th>GT</th><th>Pred</th><th>TP</th><th>FP</th><th>FN</th><th>Precision</th><th>Recall</th></tr>",
    ]
    for metric in result["metrics"]:
        precision = metric["precision"]
        recall = metric["recall"]
        css_class = "ok" if precision >= 0.8 and recall >= 0.8 else "mid" if precision >= 0.6 and recall >= 0.6 else "bad"
        html_rows.append(
            f'<tr class="{css_class}"><td>{metric["class_name"]}</td><td>{metric["gt"]}</td><td>{metric["pred"]}</td><td>{metric["tp"]}</td><td>{metric["fp"]}</td><td>{metric["fn"]}</td><td>{precision:.2f}</td><td>{recall:.2f}</td></tr>'
        )
    html_rows.append("</table>")
    html_rows.append("<h2>Missed And False Positive Samples</h2>")
    html_rows.append("<table><tr><th>Image</th><th>Truth</th><th>Predictions</th><th>Missed Truth</th><th>False Positive</th><th>Preview</th></tr>")
    for row in result["rows"]:
        if not row["missed_truth"] and not row["false_positive"]:
            continue
        preview = ""
        if prediction_image_dir is not None:
            preview_path = prediction_image_dir / row["image"]
            if preview_path.exists():
                relative = Path("..") / prediction_image_dir.name / row["image"]
                preview = f'<a href="{relative.as_posix()}"><img src="{relative.as_posix()}"></a>'
        html_rows.append(
            "<tr>"
            f"<td>{html.escape(row['image'])}</td>"
            f"<td>{html.escape(', '.join(row['truth']))}</td>"
            f"<td>{html.escape(', '.join(row['predictions']))}</td>"
            f"<td>{html.escape(', '.join(row['missed_truth']))}</td>"
            f"<td>{html.escape(', '.join(row['false_positive']))}</td>"
            f"<td>{preview}</td>"
            "</tr>"
        )
    html_rows.append("</table>")
    (output_dir / "iou_report.html").write_text("\n".join(html_rows), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze YOLO prediction labels against YOLO truth labels.")
    parser.add_argument("--images", required=True, type=Path)
    parser.add_argument("--truth-labels", required=True, type=Path)
    parser.add_argument("--prediction-labels", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--prediction-images", type=Path)
    parser.add_argument("--data-yaml", type=Path)
    parser.add_argument("--iou", type=float, default=0.5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    class_names = load_class_names(args.data_yaml) if args.data_yaml else DEFAULT_CLASS_NAMES
    result = evaluate_probe(args.images, args.truth_labels, args.prediction_labels, args.iou, class_names)
    write_outputs(result, args.output_dir, args.prediction_images)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def _load_names(data_yaml: Path) -> dict[int, str]:
    if not data_yaml.exists():
        return {}
    names: dict[int, str] = {}
    for line in data_yaml.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = re.match(r"\s*(\d+):\s*(.+?)\s*$", line)
        if match:
            names[int(match.group(1))] = match.group(2)
    return names


def _count_images(image_dir: Path) -> int:
    if not image_dir.exists():
        return 0
    return sum(1 for path in image_dir.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"})


def summarize_yolo_dataset(dataset_dir: Path) -> dict[str, Any]:
    class_names = _load_names(dataset_dir / "data.yaml")
    class_counts = {class_names[class_id]: 0 for class_id in sorted(class_names)}
    summary: dict[str, Any] = {
        "dataset": str(dataset_dir),
        "total_images": 0,
        "total_label_files": 0,
        "total_boxes": 0,
        "splits": {},
        "class_counts": class_counts,
    }

    for split in ["train", "val", "test"]:
        image_count = _count_images(dataset_dir / "images" / split)
        label_dir = dataset_dir / "labels" / split
        label_files = list(label_dir.glob("*.txt")) if label_dir.exists() else []
        split_boxes = 0
        for label_path in label_files:
            for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                parts = line.split()
                if len(parts) < 5:
                    continue
                class_id = int(float(parts[0]))
                class_name = class_names.get(class_id, str(class_id))
                summary["class_counts"].setdefault(class_name, 0)
                summary["class_counts"][class_name] += 1
                split_boxes += 1
        summary["splits"][split] = {
            "images": image_count,
            "label_files": len(label_files),
            "boxes": split_boxes,
        }
        summary["total_images"] += image_count
        summary["total_label_files"] += len(label_files)
        summary["total_boxes"] += split_boxes
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize a YOLO dataset.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = summarize_yolo_dataset(args.dataset)
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

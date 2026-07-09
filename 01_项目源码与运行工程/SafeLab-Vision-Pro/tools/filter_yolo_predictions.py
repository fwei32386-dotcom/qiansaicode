from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def parse_thresholds(value: str) -> dict[int, float]:
    thresholds: dict[int, float] = {}
    for item in value.split(","):
        if not item.strip():
            continue
        class_id, threshold = item.split(":", 1)
        thresholds[int(class_id.strip())] = float(threshold.strip())
    return thresholds


def filter_prediction_labels(source_dir: Path, output_dir: Path, thresholds: dict[int, float]) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for source_file in source_dir.glob("*.txt"):
        kept: list[str] = []
        for line in source_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.split()
            if len(parts) < 6:
                continue
            class_id = int(float(parts[0]))
            confidence = float(parts[5])
            threshold = thresholds.get(class_id, 0.0)
            if confidence >= threshold:
                kept.append(line)
        if kept:
            (output_dir / source_file.name).write_text("\n".join(kept) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filter YOLO prediction label files by per-class confidence thresholds.")
    parser.add_argument("--source-labels", required=True, type=Path)
    parser.add_argument("--output-labels", required=True, type=Path)
    parser.add_argument("--thresholds", required=True, help="Comma-separated class_id:threshold pairs, e.g. 4:0.5,5:0.6")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    thresholds = parse_thresholds(args.thresholds)
    filter_prediction_labels(args.source_labels, args.output_labels, thresholds)
    print(f"wrote filtered labels to {args.output_labels}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

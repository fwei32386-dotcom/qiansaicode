from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def parse_class_ids(value: str) -> set[int]:
    return {int(item.strip()) for item in value.split(",") if item.strip()}


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]


def _line_class_id(line: str) -> int | None:
    parts = line.split()
    if len(parts) < 6:
        return None
    return int(float(parts[0]))


def merge_prediction_labels(primary_dir: Path, secondary_dir: Path, output_dir: Path, secondary_class_ids: set[int]) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stems = {path.stem for path in primary_dir.glob("*.txt")} | {path.stem for path in secondary_dir.glob("*.txt")}
    for stem in sorted(stems):
        primary_lines = _read_lines(primary_dir / f"{stem}.txt")
        secondary_lines = _read_lines(secondary_dir / f"{stem}.txt")
        merged: list[str] = []
        for line in primary_lines:
            class_id = _line_class_id(line)
            if class_id is not None and class_id not in secondary_class_ids:
                merged.append(line)
        for line in secondary_lines:
            class_id = _line_class_id(line)
            if class_id is not None and class_id in secondary_class_ids:
                merged.append(line)
        if merged:
            (output_dir / f"{stem}.txt").write_text("\n".join(merged) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge two YOLO prediction label directories by class id.")
    parser.add_argument("--primary-labels", required=True, type=Path)
    parser.add_argument("--secondary-labels", required=True, type=Path)
    parser.add_argument("--output-labels", required=True, type=Path)
    parser.add_argument("--secondary-classes", required=True, help="Comma-separated class ids to take from secondary labels")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    merge_prediction_labels(
        args.primary_labels,
        args.secondary_labels,
        args.output_labels,
        parse_class_ids(args.secondary_classes),
    )
    print(f"wrote merged labels to {args.output_labels}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

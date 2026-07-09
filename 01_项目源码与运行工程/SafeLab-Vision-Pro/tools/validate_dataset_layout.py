from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def validate_dataset_layout(
    dataset_dir: str | Path = ROOT / "datasets" / "safelab",
    labels_path: str | Path = ROOT / "models" / "labels.txt",
) -> list[str]:
    dataset_dir = Path(dataset_dir)
    labels_path = Path(labels_path)
    if labels_path == ROOT / "models" / "labels.txt" and dataset_dir.name == "safelab_ppe":
        labels_path = ROOT / "models" / "ppe_labels.txt"
    errors: list[str] = []

    expected_classes = _read_labels(labels_path, errors)
    data_yaml = dataset_dir / "data.yaml"
    if not data_yaml.exists():
        errors.append(f"{data_yaml}: missing")
    else:
        _validate_data_yaml(data_yaml, expected_classes, errors)

    for split in ("train", "val", "test"):
        image_dir = dataset_dir / "images" / split
        label_dir = dataset_dir / "labels" / split
        if not image_dir.exists():
            errors.append(f"{image_dir}: missing")
            continue
        if not label_dir.exists():
            errors.append(f"{label_dir}: missing")
            continue
        _validate_split(split, image_dir, label_dir, len(expected_classes), errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SafeLab YOLO dataset layout.")
    parser.add_argument("--dataset-dir", default=str(ROOT / "datasets" / "safelab"))
    parser.add_argument("--labels", default=str(ROOT / "models" / "labels.txt"))
    args = parser.parse_args()

    errors = validate_dataset_layout(args.dataset_dir, args.labels)
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"status": "ok", "errors": []}, ensure_ascii=False, indent=2))
    return 0


def _read_labels(path: Path, errors: list[str]) -> list[str]:
    if not path.exists():
        errors.append(f"{path}: missing")
        return []
    labels = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(labels) != len(set(labels)):
        errors.append(f"{path}: duplicate labels")
    return labels


def _validate_data_yaml(path: Path, expected_classes: list[str], errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    for token in ("path:", "train:", "val:", "names:"):
        if token not in text:
            errors.append(f"{path}: missing {token}")
    for index, label in enumerate(expected_classes):
        expected_line = f"{index}: {label}"
        if expected_line not in text:
            errors.append(f"{path}: missing class mapping {expected_line}")


def _validate_split(
    split: str,
    image_dir: Path,
    label_dir: Path,
    class_count: int,
    errors: list[str],
) -> None:
    images = {
        path.stem
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    }
    labels = {path.stem for path in label_dir.glob("*.txt")}

    for stem in sorted(labels - images):
        errors.append(f"{split}: label without matching image: {stem}.txt")

    for label_path in sorted(label_dir.glob("*.txt")):
        _validate_label_file(split, label_path, class_count, errors)


def _validate_label_file(split: str, path: Path, class_count: int, errors: list[str]) -> None:
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) != 5:
            errors.append(f"{split}: {path.name}:{line_number} must have 5 fields")
            continue
        class_id = _parse_int(parts[0])
        if class_id is None or class_id < 0 or class_id >= class_count:
            errors.append(f"{split}: {path.name}:{line_number} invalid class id {parts[0]}")
        for value in parts[1:]:
            number = _parse_float(value)
            if number is None or number < 0 or number > 1:
                errors.append(f"{split}: {path.name}:{line_number} bbox value out of range {value}")


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _parse_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())

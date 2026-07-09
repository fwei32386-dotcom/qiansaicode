from __future__ import annotations

import argparse
import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TargetSample:
    split: str
    target_class_id: int
    image_path: Path
    label_path: Path


def _find_image(image_dir: Path, stem: str) -> Path | None:
    for extension in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
        candidate = image_dir / f"{stem}{extension}"
        if candidate.exists():
            return candidate
    return None


def _read_class_ids(label_path: Path) -> list[int]:
    class_ids: list[int] = []
    for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) >= 5:
            class_ids.append(int(float(parts[0])))
    return class_ids


def collect_target_samples(
    dataset_dir: Path,
    split: str,
    target_class_ids: list[int],
    per_class: int,
    seed: int = 20260629,
) -> list[TargetSample]:
    rng = random.Random(seed)
    label_dir = dataset_dir / "labels" / split
    image_dir = dataset_dir / "images" / split
    selected: list[TargetSample] = []
    used_images: set[Path] = set()
    if not label_dir.exists() or not image_dir.exists():
        return selected

    label_paths = list(label_dir.glob("*.txt"))
    for class_id in target_class_ids:
        candidates = label_paths[:]
        rng.shuffle(candidates)
        class_count = 0
        for label_path in candidates:
            if class_count >= per_class:
                break
            if class_id not in _read_class_ids(label_path):
                continue
            image_path = _find_image(image_dir, label_path.stem)
            if image_path is None or image_path in used_images:
                continue
            selected.append(TargetSample(split=split, target_class_id=class_id, image_path=image_path, label_path=label_path))
            used_images.add(image_path)
            class_count += 1
    return selected


def parse_class_counts(value: str) -> dict[int, int]:
    counts: dict[int, int] = {}
    for item in value.split(","):
        if not item.strip():
            continue
        class_id, count = item.split(":", 1)
        counts[int(class_id.strip())] = int(count.strip())
    return counts


def _copy_data_yaml(source_dataset: Path, output_dataset: Path) -> None:
    source_yaml = source_dataset / "data.yaml"
    output_yaml = output_dataset / "data.yaml"
    if source_yaml.exists():
        content = source_yaml.read_text(encoding="utf-8", errors="ignore")
        lines = []
        for line in content.splitlines():
            if line.startswith("path:"):
                lines.append(f"path: {output_dataset.as_posix()}")
            else:
                lines.append(line)
        output_yaml.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_balanced_subset(
    source_dataset: Path,
    output_dataset: Path,
    target_class_ids: list[int],
    per_class: int,
    seed: int = 20260629,
    class_counts: dict[int, int] | None = None,
) -> dict[str, Any]:
    if output_dataset.exists():
        shutil.rmtree(output_dataset)
    for split in ["train", "val", "test"]:
        (output_dataset / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dataset / "labels" / split).mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "source_dataset": str(source_dataset),
        "output_dataset": str(output_dataset),
        "target_class_ids": target_class_ids,
        "per_class": per_class,
        "class_counts": class_counts or {},
        "splits": {},
        "total_images": 0,
    }

    for split in ["train", "val", "test"]:
        samples: list[TargetSample] = []
        for class_id in target_class_ids:
            target_count = (class_counts or {}).get(class_id, per_class)
            split_per_class = target_count if split == "train" else max(1, target_count // 4)
            samples.extend(collect_target_samples(source_dataset, split, [class_id], split_per_class, seed))
        copied: set[Path] = set()
        for sample in samples:
            target_image = output_dataset / "images" / split / sample.image_path.name
            target_label = output_dataset / "labels" / split / sample.label_path.name
            if target_image in copied:
                continue
            shutil.copy2(sample.image_path, target_image)
            shutil.copy2(sample.label_path, target_label)
            copied.add(target_image)
        summary["splits"][split] = {"images": len(copied)}
        summary["total_images"] += len(copied)

    _copy_data_yaml(source_dataset, output_dataset)
    (output_dataset / "subset_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a quick balanced YOLO subset focused on weak classes.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--classes", required=True, help="Comma-separated class ids, e.g. 2,4")
    parser.add_argument("--per-class", type=int, default=800)
    parser.add_argument("--class-counts", help="Comma-separated per-class counts, e.g. 0:500,4:1200")
    parser.add_argument("--seed", type=int, default=20260629)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    class_ids = [int(item.strip()) for item in args.classes.split(",") if item.strip()]
    class_counts = parse_class_counts(args.class_counts) if args.class_counts else None
    summary = build_balanced_subset(args.source, args.output, class_ids, args.per_class, args.seed, class_counts)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

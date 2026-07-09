from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


CLASS_MAP = {5: 0, 6: 1}
CLASS_NAMES = {0: "fire", 1: "smoke"}


def remap_fire_smoke_lines(lines: list[str]) -> list[str]:
    remapped: list[str] = []
    for line in lines:
        parts = line.split()
        if len(parts) < 5:
            continue
        original_class = int(float(parts[0]))
        if original_class not in CLASS_MAP:
            continue
        remapped.append(" ".join([str(CLASS_MAP[original_class]), *parts[1:5]]))
    return remapped


def _find_image(image_dir: Path, stem: str) -> Path | None:
    for extension in [".jpg", ".jpeg", ".png", ".bmp"]:
        candidate = image_dir / f"{stem}{extension}"
        if candidate.exists():
            return candidate
    return None


def build_fire_smoke_dataset(source_dataset: Path, output_dataset: Path) -> dict[str, Any]:
    if output_dataset.exists():
        shutil.rmtree(output_dataset)

    summary: dict[str, Any] = {
        "source_dataset": str(source_dataset),
        "output_dataset": str(output_dataset),
        "total_images": 0,
        "splits": {},
        "class_counts": {"fire": 0, "smoke": 0},
    }

    for split in ["train", "val", "test"]:
        source_labels = source_dataset / "labels" / split
        source_images = source_dataset / "images" / split
        output_labels = output_dataset / "labels" / split
        output_images = output_dataset / "images" / split
        output_labels.mkdir(parents=True, exist_ok=True)
        output_images.mkdir(parents=True, exist_ok=True)
        split_count = 0

        if not source_labels.exists():
            summary["splits"][split] = {"images": 0}
            continue

        for label_path in sorted(source_labels.glob("*.txt")):
            lines = label_path.read_text(errors="ignore").splitlines()
            remapped = remap_fire_smoke_lines(lines)
            if not remapped:
                continue
            image_path = _find_image(source_images, label_path.stem)
            if image_path is None:
                continue
            shutil.copy2(image_path, output_images / image_path.name)
            (output_labels / label_path.name).write_text("\n".join(remapped) + "\n", encoding="utf-8")
            split_count += 1
            summary["total_images"] += 1
            for line in remapped:
                class_name = CLASS_NAMES[int(line.split()[0])]
                summary["class_counts"][class_name] += 1
        summary["splits"][split] = {"images": split_count}

    data_yaml = output_dataset / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                f"path: {output_dataset.as_posix()}",
                "train: images/train",
                "val: images/val",
                "test: images/test",
                "",
                "names:",
                "  0: fire",
                "  1: smoke",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (output_dataset / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fire/smoke-only YOLO dataset from the SafeLab 7-class dataset.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_fire_smoke_dataset(args.source, args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PPE_CLASSES = ["person", "helmet", "vest", "goggles", "gloves"]


def prepare_ppe_dataset(
    source_dir: str | Path = ROOT / "datasets" / "safelab",
    output_dir: str | Path = ROOT / "datasets" / "safelab_ppe",
) -> dict[str, int | str]:
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    copied = 0
    skipped = 0
    _ensure_dirs(output_dir)
    _write_data_yaml(output_dir)

    for split in ("train", "val", "test"):
        image_dir = source_dir / "images" / split
        label_dir = source_dir / "labels" / split
        if not image_dir.exists() or not label_dir.exists():
            continue
        for label_path in label_dir.glob("*.txt"):
            rewritten = _ppe_label_lines(label_path)
            if not rewritten:
                skipped += 1
                continue
            image_path = _find_image(image_dir, label_path.stem)
            if image_path is None:
                skipped += 1
                continue
            target_label = output_dir / "labels" / split / label_path.name
            target_image = output_dir / "images" / split / image_path.name
            target_label.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
            shutil.copy2(image_path, target_image)
            copied += 1

    return {"copied": copied, "skipped": skipped, "output": str(output_dir)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a PPE-only YOLO dataset from datasets/safelab.")
    parser.add_argument("--source-dir", default=str(ROOT / "datasets" / "safelab"))
    parser.add_argument("--output-dir", default=str(ROOT / "datasets" / "safelab_ppe"))
    args = parser.parse_args()

    result = prepare_ppe_dataset(args.source_dir, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _ensure_dirs(output_dir: Path) -> None:
    for split in ("train", "val", "test"):
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)


def _write_data_yaml(output_dir: Path) -> None:
    lines = [
        f"path: {output_dir.as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "",
        "names:",
    ]
    lines.extend(f"  {index}: {name}" for index, name in enumerate(PPE_CLASSES))
    (output_dir / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ppe_label_lines(path: Path) -> list[str]:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        class_id = int(parts[0])
        if class_id in {0, 1, 2, 3, 4}:
            lines.append(line)
    return lines


def _find_image(image_dir: Path, stem: str) -> Path | None:
    for extension in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
        path = image_dir / f"{stem}{extension}"
        if path.exists():
            return path
    return None


if __name__ == "__main__":
    raise SystemExit(main())

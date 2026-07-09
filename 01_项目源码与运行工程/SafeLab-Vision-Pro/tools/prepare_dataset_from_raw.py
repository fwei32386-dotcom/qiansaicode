from __future__ import annotations

import argparse
import ast
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET_CLASSES = ["person", "helmet", "vest", "goggles", "gloves", "fire", "smoke"]


def prepare_dataset_from_raw(
    raw_dir: str | Path = ROOT / "datasets" / "raw",
    output_dir: str | Path = ROOT / "datasets" / "safelab",
) -> dict[str, object]:
    raw_dir = Path(raw_dir)
    output_dir = Path(output_dir)
    copied_images = 0
    copied_labels = 0
    skipped_labels = 0

    _ensure_output_dirs(output_dir)
    _write_data_yaml(output_dir, TARGET_CLASSES)
    for source in _discover_yolo_sources(raw_dir):
        mapping = _class_mapping(source)
        if not mapping:
            continue
        if _is_flat_split_source(source):
            result = _copy_flat_split_source(source, output_dir, mapping)
            copied_images += result["copied_images"]
            copied_labels += result["copied_labels"]
            skipped_labels += result["skipped_empty_labels"]
            continue
        if _is_unpartitioned_nested_source(source):
            result = _copy_unpartitioned_nested_source(source, output_dir, mapping)
            copied_images += result["copied_images"]
            copied_labels += result["copied_labels"]
            skipped_labels += result["skipped_empty_labels"]
            continue
        for split in ("train", "val", "test"):
            image_dir, label_dir = _split_dirs(source, split)
            if not image_dir.exists() or not label_dir.exists():
                continue
            for image_path in _image_files(image_dir):
                stem = f"{source.name}_{image_path.stem}"
                label_path = label_dir / f"{image_path.stem}.txt"
                if not label_path.exists():
                    continue
                target_label = output_dir / "labels" / split / f"{stem}.txt"
                kept = _rewrite_label(label_path, target_label, mapping)
                if kept == 0:
                    skipped_labels += 1
                    target_label.unlink(missing_ok=True)
                    continue
                target_image = output_dir / "images" / split / f"{stem}{image_path.suffix.lower()}"
                shutil.copy2(image_path, target_image)
                copied_images += 1
                copied_labels += 1

    return {
        "copied_images": copied_images,
        "copied_labels": copied_labels,
        "skipped_empty_labels": skipped_labels,
        "output": str(output_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize raw YOLO datasets into datasets/safelab.")
    parser.add_argument("--raw-dir", default=str(ROOT / "datasets" / "raw"))
    parser.add_argument("--output-dir", default=str(ROOT / "datasets" / "safelab"))
    args = parser.parse_args()

    result = prepare_dataset_from_raw(args.raw_dir, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _ensure_output_dirs(output_dir: Path) -> None:
    for split in ("train", "val", "test"):
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)


def _write_data_yaml(output_dir: Path, classes: list[str]) -> None:
    lines = [
        f"path: {output_dir.as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "",
        "names:",
    ]
    lines.extend(f"  {index}: {name}" for index, name in enumerate(classes))
    (output_dir / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _discover_yolo_sources(raw_dir: Path) -> list[Path]:
    sources = []
    for path in raw_dir.rglob("*"):
        if "_kagglehub_cache" in path.parts:
            continue
        if path.is_dir() and (
            (path / "data.yaml").exists()
            or (path / "sh17.yaml").exists()
            or (path / "labels" / "classes.txt").exists()
        ):
            sources.append(path)
    return sources


def _class_mapping(source: Path) -> dict[int, int]:
    names_path = source / "data.yaml"
    if not names_path.exists():
        names_path = source / "sh17.yaml"
    if not names_path.exists():
        names_path = source / "labels" / "classes.txt"
    names = _read_names(names_path)
    mapping = {}
    for source_id, name in names.items():
        normalized = _normalize_class_name(name)
        if normalized in TARGET_CLASSES:
            mapping[source_id] = TARGET_CLASSES.index(normalized)
    return mapping


def _read_names(data_yaml: Path) -> dict[int, str]:
    names: dict[int, str] = {}
    if data_yaml.name == "classes.txt":
        return {
            index: line.strip()
            for index, line in enumerate(data_yaml.read_text(encoding="utf-8", errors="replace").splitlines())
            if line.strip()
        }
    in_names = False
    for raw_line in data_yaml.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if line.startswith("names:"):
            inline_value = line.split(":", 1)[1].strip()
            if inline_value:
                parsed = _parse_inline_names(inline_value)
                if parsed:
                    return parsed
            in_names = True
            continue
        if in_names and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key.isdigit():
                names[int(key)] = value
        elif in_names and line and not raw_line.startswith(" "):
            break
    return names


def _parse_inline_names(value: str) -> dict[int, str]:
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return {}
    if isinstance(parsed, list):
        return {index: str(name) for index, name in enumerate(parsed)}
    if isinstance(parsed, dict):
        return {int(key): str(name) for key, name in parsed.items()}
    return {}


def _normalize_class_name(name: str) -> str:
    cleaned = name.strip().lower().replace("_", "-")
    aliases = {
        "person": "person",
        "helmet": "helmet",
        "hardhat": "helmet",
        "hard-hat": "helmet",
        "safety-helmet": "helmet",
        "vest": "vest",
        "safety-vest": "vest",
        "safety-vests": "vest",
        "goggle": "goggles",
        "goggles": "goggles",
        "safety-goggle": "goggles",
        "safety-goggles": "goggles",
        "glove": "gloves",
        "gloves": "gloves",
        "safety-glove": "gloves",
        "safety-gloves": "gloves",
        "fire": "fire",
        "smoke": "smoke",
    }
    return aliases.get(cleaned, cleaned)


def _split_dirs(source: Path, split: str) -> tuple[Path, Path]:
    source_split = "valid" if split == "val" and (source / "valid").exists() else split
    candidates = [
        (source / "images" / source_split, source / "labels" / source_split),
        (source / source_split / "images", source / source_split / "labels"),
        (source / "data" / source_split / "images", source / "data" / source_split / "labels"),
    ]
    for image_dir, label_dir in candidates:
        if image_dir.exists() and label_dir.exists():
            return image_dir, label_dir
    return candidates[0]


def _is_flat_split_source(source: Path) -> bool:
    return (
        (source / "images").is_dir()
        and (source / "labels").is_dir()
        and ((source / "train_files.txt").exists() or (source / "val_files.txt").exists())
    )


def _is_unpartitioned_nested_source(source: Path) -> bool:
    return (source / "image" / "image").is_dir() and (source / "labels" / "labels").is_dir()


def _copy_unpartitioned_nested_source(source: Path, output_dir: Path, mapping: dict[int, int]) -> dict[str, int]:
    copied_images = 0
    copied_labels = 0
    skipped_labels = 0
    image_dir = source / "image" / "image"
    label_dir = source / "labels" / "labels"
    image_paths = sorted(_image_files(image_dir), key=lambda path: path.name)
    total = len(image_paths)
    train_end = int(total * 0.8)
    val_end = int(total * 0.9)
    for index, image_path in enumerate(image_paths):
        split = "train" if index < train_end else "val" if index < val_end else "test"
        label_path = label_dir / f"{image_path.stem}.txt"
        if not label_path.exists():
            continue
        stem = f"{source.name}_{image_path.stem}"
        target_label = output_dir / "labels" / split / f"{stem}.txt"
        kept = _rewrite_label(label_path, target_label, mapping)
        if kept == 0:
            skipped_labels += 1
            target_label.unlink(missing_ok=True)
            continue
        target_image = output_dir / "images" / split / f"{stem}{image_path.suffix.lower()}"
        shutil.copy2(image_path, target_image)
        copied_images += 1
        copied_labels += 1
    return {
        "copied_images": copied_images,
        "copied_labels": copied_labels,
        "skipped_empty_labels": skipped_labels,
    }


def _copy_flat_split_source(source: Path, output_dir: Path, mapping: dict[int, int]) -> dict[str, int]:
    copied_images = 0
    copied_labels = 0
    skipped_labels = 0
    for split, list_name in (("train", "train_files.txt"), ("val", "val_files.txt")):
        list_path = source / list_name
        if not list_path.exists():
            continue
        for raw_name in list_path.read_text(encoding="utf-8", errors="replace").splitlines():
            image_name = raw_name.strip()
            if not image_name:
                continue
            image_path = source / "images" / Path(image_name).name
            label_path = source / "labels" / f"{Path(image_name).stem}.txt"
            if not image_path.exists() or not label_path.exists():
                continue
            stem = f"{source.name}_{image_path.stem}"
            target_label = output_dir / "labels" / split / f"{stem}.txt"
            kept = _rewrite_label(label_path, target_label, mapping)
            if kept == 0:
                skipped_labels += 1
                target_label.unlink(missing_ok=True)
                continue
            target_image = output_dir / "images" / split / f"{stem}{image_path.suffix.lower()}"
            shutil.copy2(image_path, target_image)
            copied_images += 1
            copied_labels += 1
    return {
        "copied_images": copied_images,
        "copied_labels": copied_labels,
        "skipped_empty_labels": skipped_labels,
    }


def _image_files(image_dir: Path) -> list[Path]:
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    return [path for path in image_dir.iterdir() if path.is_file() and path.suffix.lower() in extensions]


def _rewrite_label(source: Path, target: Path, mapping: dict[int, int]) -> int:
    kept = 0
    lines = []
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        try:
            old_id = int(parts[0])
        except ValueError:
            continue
        if old_id not in mapping:
            continue
        bbox = []
        for value in parts[1:]:
            try:
                number = float(value)
            except ValueError:
                bbox = []
                break
            if number < 0 or number > 1:
                bbox = []
                break
            bbox.append(value)
        if len(bbox) != 4:
            continue
        lines.append(" ".join([str(mapping[old_id]), *bbox]))
        kept += 1
    if lines:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return kept


if __name__ == "__main__":
    raise SystemExit(main())

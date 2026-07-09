from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.analyze_yolo_probe import evaluate_probe, load_class_names, write_outputs


@dataclass(frozen=True)
class ProbeSample:
    class_id: int
    class_name: str
    split: str
    image_path: Path
    label_path: Path
    target_class_count: int
    total_label_count: int


def _find_image(image_dir: Path, stem: str) -> Path | None:
    for extension in [".jpg", ".jpeg", ".png", ".bmp"]:
        candidate = image_dir / f"{stem}{extension}"
        if candidate.exists():
            return candidate
    return None


def _label_class_counts(label_path: Path) -> tuple[list[int], int]:
    class_ids: list[int] = []
    for line in label_path.read_text(errors="ignore").splitlines():
        parts = line.split()
        if not parts:
            continue
        class_ids.append(int(float(parts[0])))
    return class_ids, len(class_ids)


def collect_class_samples(
    dataset_dir: Path,
    class_ids: list[int] | None = None,
    per_class: int = 10,
    seed: int = 20260629,
    splits: list[str] | None = None,
) -> list[ProbeSample]:
    selected: list[ProbeSample] = []
    used_images: set[Path] = set()
    rng = random.Random(seed)
    class_names = load_class_names(dataset_dir / "data.yaml")
    target_class_ids = class_ids if class_ids is not None else sorted(class_names)
    target_splits = splits if splits is not None else ["val", "test", "train"]

    for class_id in target_class_ids:
        class_samples: list[ProbeSample] = []
        for split in target_splits:
            label_dir = dataset_dir / "labels" / split
            image_dir = dataset_dir / "images" / split
            if not label_dir.exists() or not image_dir.exists():
                continue
            candidates = list(label_dir.glob("*.txt"))
            rng.shuffle(candidates)
            for label_path in candidates:
                label_classes, total_label_count = _label_class_counts(label_path)
                if class_id not in label_classes:
                    continue
                image_path = _find_image(image_dir, label_path.stem)
                if image_path is None or image_path in used_images:
                    continue
                class_samples.append(
                    ProbeSample(
                        class_id=class_id,
                        class_name=class_names.get(class_id, str(class_id)),
                        split=split,
                        image_path=image_path,
                        label_path=label_path,
                        target_class_count=label_classes.count(class_id),
                        total_label_count=total_label_count,
                    )
                )
                used_images.add(image_path)
                if len(class_samples) >= per_class:
                    break
            if len(class_samples) >= per_class:
                break
        selected.extend(class_samples)
    return selected


def copy_probe_samples(samples: list[ProbeSample], output_dir: Path) -> list[dict[str, str | int]]:
    image_dir = output_dir / "images"
    label_dir = output_dir / "labels"
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, str | int]] = []

    for index, sample in enumerate(samples, 1):
        stem = f"{sample.class_id}_{sample.class_name}_{index:03d}_{sample.image_path.stem}"
        image_output = image_dir / f"{stem}{sample.image_path.suffix.lower()}"
        label_output = label_dir / f"{stem}.txt"
        shutil.copy2(sample.image_path, image_output)
        shutil.copy2(sample.label_path, label_output)
        record = asdict(sample)
        record["image_path"] = str(sample.image_path)
        record["label_path"] = str(sample.label_path)
        record.update({"image": str(image_output), "label": str(label_output)})
        manifest.append(record)

    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def run_predictions(model_path: Path, image_dir: Path, output_dir: Path, confidence: float) -> Path:
    from ultralytics import YOLO

    run_name = f"conf{int(confidence * 1000):03d}"
    model = YOLO(str(model_path))
    model.predict(
        source=str(image_dir),
        imgsz=640,
        conf=confidence,
        save=True,
        save_txt=True,
        save_conf=True,
        project=str(output_dir / "predictions"),
        name=run_name,
        exist_ok=True,
        verbose=False,
    )
    return output_dir / "predictions" / run_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample a YOLO dataset, run predictions, and create IoU reports.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--per-class", type=int, default=10)
    parser.add_argument("--conf", type=float, action="append", default=None)
    parser.add_argument("--seed", type=int, default=20260629)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)
    samples = collect_class_samples(args.dataset, per_class=args.per_class, seed=args.seed)
    copy_probe_samples(samples, args.output_dir)

    confidences = args.conf if args.conf is not None else [0.25]
    for confidence in confidences:
        prediction_dir = run_predictions(args.model, args.output_dir / "images", args.output_dir, confidence)
        result = evaluate_probe(
            args.output_dir / "images",
            args.output_dir / "labels",
            prediction_dir / "labels",
            class_names=load_class_names(args.dataset / "data.yaml"),
        )
        write_outputs(result, args.output_dir / "summary" / prediction_dir.name, prediction_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


CLASS_NAMES = {
    0: "person",
    1: "helmet",
    2: "vest",
    3: "goggles",
    4: "gloves",
}

DEFAULT_ACCEPTANCE_COUNTS = {0: 40, 1: 40, 2: 40, 3: 40, 4: 40}
DEFAULT_HARD_COUNTS = {0: 120, 1: 80, 2: 100, 3: 100, 4: 100}
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp"]


@dataclass(frozen=True)
class YoloSample:
    split: str
    image_path: Path
    label_path: Path
    class_ids: tuple[int, ...]
    min_area_by_class: dict[int, float]
    scene_tag: str


def scene_tag_for_name(name: str) -> str:
    lowered = name.lower()
    if "hardhat" in lowered or "construction" in lowered:
        return "construction"
    if "ppe_dataset" in lowered or "pp02" in lowered or "ppe_data" in lowered or "n5h" in lowered:
        return "lab_ppe"
    if "css-data" in lowered:
        return "css_generic"
    return "other"


def parse_class_counts(value: str | None) -> dict[int, int]:
    if not value:
        return {}
    counts: dict[int, int] = {}
    for part in value.split(","):
        key, raw_count = part.strip().split(":", 1)
        counts[int(key)] = int(raw_count)
    return counts


def parse_label(label_path: Path) -> tuple[tuple[int, ...], dict[int, float]]:
    class_ids: list[int] = []
    min_area_by_class: dict[int, float] = {}
    for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        class_id = int(float(parts[0]))
        width = float(parts[3])
        height = float(parts[4])
        area = width * height
        class_ids.append(class_id)
        min_area_by_class[class_id] = min(min_area_by_class.get(class_id, area), area)
    return tuple(sorted(set(class_ids))), min_area_by_class


def find_image(images_dir: Path, stem: str) -> Path | None:
    for extension in IMAGE_EXTENSIONS:
        candidate = images_dir / f"{stem}{extension}"
        if candidate.exists():
            return candidate
    return None


def collect_samples(source: Path) -> list[YoloSample]:
    samples: list[YoloSample] = []
    for split in ["train", "val", "test"]:
        labels_dir = source / "labels" / split
        images_dir = source / "images" / split
        if not labels_dir.exists() or not images_dir.exists():
            continue
        for label_path in sorted(labels_dir.glob("*.txt")):
            class_ids, min_area_by_class = parse_label(label_path)
            if not class_ids:
                continue
            image_path = find_image(images_dir, label_path.stem)
            if image_path is None:
                continue
            samples.append(
                YoloSample(
                    split=split,
                    image_path=image_path,
                    label_path=label_path,
                    class_ids=class_ids,
                    min_area_by_class=min_area_by_class,
                    scene_tag=scene_tag_for_name(label_path.stem),
                )
            )
    return samples


def acceptance_rank(sample: YoloSample, class_id: int) -> tuple[int, float, str]:
    scene_order_by_class = {
        0: {"lab_ppe": 0, "construction": 1, "other": 2, "css_generic": 3},
        1: {"construction": 0, "lab_ppe": 1, "other": 2, "css_generic": 3},
        2: {"construction": 0, "other": 1, "lab_ppe": 2, "css_generic": 3},
        3: {"lab_ppe": 0, "other": 1, "construction": 2, "css_generic": 3},
        4: {"lab_ppe": 0, "other": 1, "construction": 2, "css_generic": 3},
    }
    scene_rank = scene_order_by_class.get(class_id, {}).get(sample.scene_tag, 9)
    area = sample.min_area_by_class.get(class_id, 1.0)
    return scene_rank, area, sample.image_path.name


def hard_rank(sample: YoloSample, class_id: int) -> tuple[int, float, str]:
    scene_rank, area, name = acceptance_rank(sample, class_id)
    small_target_bonus = 0 if area <= 0.03 else 1
    return small_target_bonus, scene_rank, area, name


def select_by_class(
    samples: list[YoloSample],
    *,
    class_counts: dict[int, int],
    splits: set[str],
    rank_mode: str,
    blocked_stems: set[str] | None = None,
) -> list[YoloSample]:
    selected: list[YoloSample] = []
    selected_stems: set[str] = set(blocked_stems or set())
    ranker = hard_rank if rank_mode == "hard" else acceptance_rank
    for class_id, count in class_counts.items():
        candidates = [
            sample
            for sample in samples
            if sample.split in splits and class_id in sample.class_ids and sample.image_path.stem not in selected_stems
        ]
        candidates.sort(key=lambda sample: ranker(sample, class_id))
        for sample in candidates[:count]:
            selected.append(sample)
            selected_stems.add(sample.image_path.stem)
    return selected


def reset_yolo_dirs(output: Path, active_splits: list[str]) -> None:
    if output.exists():
        shutil.rmtree(output)
    for split in ["train", "val", "test"]:
        (output / "images" / split).mkdir(parents=True, exist_ok=True)
        (output / "labels" / split).mkdir(parents=True, exist_ok=True)


def copy_samples(samples: list[YoloSample], output: Path, split: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for sample in samples:
        image_dest = output / "images" / split / sample.image_path.name
        label_dest = output / "labels" / split / sample.label_path.name
        shutil.copy2(sample.image_path, image_dest)
        shutil.copy2(sample.label_path, label_dest)
        rows.append(
            {
                "split": split,
                "source_split": sample.split,
                "image": sample.image_path.name,
                "label": sample.label_path.name,
                "scene_tag": sample.scene_tag,
                "classes": " ".join(CLASS_NAMES[class_id] for class_id in sample.class_ids if class_id in CLASS_NAMES),
            }
        )
    return rows


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_data_yaml(output: Path, train: str, val: str, test: str) -> None:
    names = "\n".join(f"  {class_id}: {name}" for class_id, name in CLASS_NAMES.items())
    output.joinpath("data.yaml").write_text(
        f"path: {output.as_posix()}\ntrain: {train}\nval: {val}\ntest: {test}\n\nnames:\n{names}\n",
        encoding="utf-8",
    )


def summarize(rows: list[dict[str, str]]) -> dict[str, object]:
    scene_counts = Counter(row["scene_tag"] for row in rows)
    class_image_counts: Counter[str] = Counter()
    for row in rows:
        for class_name in row["classes"].split():
            class_image_counts[class_name] += 1
    return {
        "images": len(rows),
        "scene_counts": dict(scene_counts),
        "class_image_counts": dict(class_image_counts),
    }


def build_ppe_target_sets(
    source: Path,
    acceptance_output: Path,
    hard_output: Path,
    *,
    acceptance_counts: dict[int, int] | None = None,
    hard_counts: dict[int, int] | None = None,
) -> dict[str, object]:
    acceptance_counts = acceptance_counts or DEFAULT_ACCEPTANCE_COUNTS
    hard_counts = hard_counts or DEFAULT_HARD_COUNTS
    samples = collect_samples(source)

    acceptance_samples = select_by_class(
        samples,
        class_counts=acceptance_counts,
        splits={"val", "test"},
        rank_mode="acceptance",
    )
    acceptance_stems = {sample.image_path.stem for sample in acceptance_samples}
    hard_samples = select_by_class(
        samples,
        class_counts=hard_counts,
        splits={"train"},
        rank_mode="hard",
        blocked_stems=acceptance_stems,
    )

    reset_yolo_dirs(acceptance_output, ["test"])
    reset_yolo_dirs(hard_output, ["train"])
    acceptance_rows = copy_samples(acceptance_samples, acceptance_output, "test")
    hard_rows = copy_samples(hard_samples, hard_output, "train")
    write_data_yaml(acceptance_output, train="images/test", val="images/test", test="images/test")
    write_data_yaml(hard_output, train="images/train", val="images/train", test="images/train")
    write_manifest(acceptance_output / "manifest.csv", acceptance_rows)
    write_manifest(hard_output / "manifest.csv", hard_rows)

    summary = {
        "source": str(source),
        "acceptance": summarize(acceptance_rows),
        "hard": summarize(hard_rows),
    }
    (acceptance_output / "curation_summary.json").write_text(
        json.dumps(summary["acceptance"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (hard_output / "curation_summary.json").write_text(
        json.dumps(summary["hard"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare PPE acceptance and hard-sample YOLO datasets.")
    parser.add_argument("--source", type=Path, required=True, help="Source YOLO dataset root.")
    parser.add_argument("--acceptance-output", type=Path, required=True, help="Output acceptance dataset root.")
    parser.add_argument("--hard-output", type=Path, required=True, help="Output hard-sample training dataset root.")
    parser.add_argument(
        "--acceptance-counts",
        default=",".join(f"{class_id}:{count}" for class_id, count in DEFAULT_ACCEPTANCE_COUNTS.items()),
        help="Per-class image targets, e.g. 0:40,1:40.",
    )
    parser.add_argument(
        "--hard-counts",
        default=",".join(f"{class_id}:{count}" for class_id, count in DEFAULT_HARD_COUNTS.items()),
        help="Per-class image targets, e.g. 0:120,2:100.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_ppe_target_sets(
        args.source,
        args.acceptance_output,
        args.hard_output,
        acceptance_counts=parse_class_counts(args.acceptance_counts),
        hard_counts=parse_class_counts(args.hard_counts),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

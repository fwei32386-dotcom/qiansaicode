from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


VALID_DECISIONS = {"keep", "remove", "add_negative", "relabel", "unreviewed"}


class CleaningDecisionError(RuntimeError):
    pass


def _read_rows(plan_csv: Path) -> list[dict[str, str]]:
    with plan_csv.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def _safe_split(value: str) -> str:
    split = (value or "train").strip()
    return split if split in {"train", "val", "test"} else "train"


def _copy_data_yaml(output_dataset: Path) -> None:
    (output_dataset / "data.yaml").write_text(
        "\n".join(
            [
                f"path: {output_dataset.as_posix()}",
                "train: images/train",
                "val: images/val",
                "test: images/test",
                "",
                "names:",
                "  0: person",
                "  1: helmet",
                "  2: vest",
                "  3: goggles",
                "  4: gloves",
                "  5: fire",
                "  6: smoke",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _copy_sample(row: dict[str, str], output_dataset: Path, label_override: Path | None = None, empty_label: bool = False) -> None:
    source_image = Path(row.get("source_image", ""))
    source_label = label_override or Path(row.get("source_label", ""))
    if not source_image.exists():
        raise CleaningDecisionError(f"missing source image: {source_image}")
    if not empty_label and not source_label.exists():
        raise CleaningDecisionError(f"missing source label: {source_label}")

    split = _safe_split(row.get("source_split", "train"))
    target_image = output_dataset / "images" / split / source_image.name
    target_label = output_dataset / "labels" / split / f"{source_image.stem}.txt"
    target_image.parent.mkdir(parents=True, exist_ok=True)
    target_label.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_image, target_image)
    if empty_label:
        target_label.write_text("", encoding="utf-8")
    else:
        shutil.copy2(source_label, target_label)


def build_curated_dataset(
    plan_csv: Path,
    output_dataset: Path,
    allow_unreviewed: str | None = None,
) -> dict[str, Any]:
    rows = _read_rows(plan_csv)
    decisions = Counter((row.get("decision") or "unreviewed").strip() for row in rows)
    unknown = sorted(decision for decision in decisions if decision not in VALID_DECISIONS)
    if unknown:
        raise CleaningDecisionError(f"unknown decisions: {', '.join(unknown)}")
    if decisions.get("unreviewed", 0) and allow_unreviewed is None:
        raise CleaningDecisionError(f"{decisions['unreviewed']} rows are unreviewed")

    if output_dataset.exists():
        shutil.rmtree(output_dataset)
    for split in ["train", "val", "test"]:
        (output_dataset / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dataset / "labels" / split).mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped = 0
    for row in rows:
        decision = (row.get("decision") or "unreviewed").strip()
        if decision == "unreviewed":
            decision = allow_unreviewed or "unreviewed"
        if decision == "remove":
            skipped += 1
            continue
        if decision == "keep":
            _copy_sample(row, output_dataset)
            copied += 1
        elif decision == "add_negative":
            _copy_sample(row, output_dataset, empty_label=True)
            copied += 1
        elif decision == "relabel":
            review_label = Path(row.get("review_label", ""))
            if not review_label.exists():
                raise CleaningDecisionError(f"relabel row needs existing review_label: {row.get('image', '')}")
            _copy_sample(row, output_dataset, label_override=review_label)
            copied += 1
        else:
            raise CleaningDecisionError(f"unsupported decision after normalization: {decision}")

    _copy_data_yaml(output_dataset)
    summary = {
        "plan_csv": str(plan_csv),
        "output_dataset": str(output_dataset),
        "decisions": dict(decisions),
        "allow_unreviewed": allow_unreviewed,
        "copied": copied,
        "skipped": skipped,
    }
    (output_dataset / "curation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply reviewed YOLO cleaning decisions to build a curated dataset.")
    parser.add_argument("--plan-csv", required=True, type=Path)
    parser.add_argument("--output-dataset", required=True, type=Path)
    parser.add_argument("--allow-unreviewed", choices=["keep", "remove", "add_negative"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_curated_dataset(args.plan_csv, args.output_dataset, args.allow_unreviewed)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

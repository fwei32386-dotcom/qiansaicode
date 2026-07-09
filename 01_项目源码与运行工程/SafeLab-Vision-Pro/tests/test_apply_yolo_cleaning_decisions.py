from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.apply_yolo_cleaning_decisions import CleaningDecisionError, build_curated_dataset


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "image",
        "decision",
        "source_image",
        "source_label",
        "source_split",
    ]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class ApplyYoloCleaningDecisionsTest(unittest.TestCase):
    def test_build_curated_dataset_rejects_unreviewed_rows_by_default(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "sample.jpg"
            label = root / "sample.txt"
            image.write_bytes(b"image")
            label.write_text("5 0.5 0.5 0.2 0.2\n", encoding="utf-8")
            plan = root / "plan.csv"
            _write_csv(
                plan,
                [
                    {
                        "image": "sample.jpg",
                        "decision": "unreviewed",
                        "source_image": str(image),
                        "source_label": str(label),
                        "source_split": "train",
                    }
                ],
            )

            with self.assertRaises(CleaningDecisionError):
                build_curated_dataset(plan, root / "output")

    def test_build_curated_dataset_applies_remove_and_add_negative(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            kept_image = root / "keep.jpg"
            kept_label = root / "keep.txt"
            removed_image = root / "remove.jpg"
            removed_label = root / "remove.txt"
            negative_image = root / "negative.jpg"
            negative_label = root / "negative.txt"
            for image in [kept_image, removed_image, negative_image]:
                image.write_bytes(b"image")
            for label in [kept_label, removed_label, negative_label]:
                label.write_text("5 0.5 0.5 0.2 0.2\n", encoding="utf-8")
            plan = root / "plan.csv"
            _write_csv(
                plan,
                [
                    {"image": "keep.jpg", "decision": "keep", "source_image": str(kept_image), "source_label": str(kept_label), "source_split": "train"},
                    {"image": "remove.jpg", "decision": "remove", "source_image": str(removed_image), "source_label": str(removed_label), "source_split": "train"},
                    {"image": "negative.jpg", "decision": "add_negative", "source_image": str(negative_image), "source_label": str(negative_label), "source_split": "val"},
                ],
            )

            summary = build_curated_dataset(plan, root / "output")

            output = root / "output"

            self.assertEqual(summary["decisions"]["keep"], 1)
            self.assertEqual(summary["decisions"]["remove"], 1)
            self.assertEqual(summary["decisions"]["add_negative"], 1)
            self.assertTrue((output / "images" / "train" / "keep.jpg").exists())
            self.assertTrue((output / "labels" / "train" / "keep.txt").exists())
            self.assertFalse((output / "images" / "train" / "remove.jpg").exists())
            self.assertTrue((output / "images" / "val" / "negative.jpg").exists())
            self.assertEqual((output / "labels" / "val" / "negative.txt").read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.generate_yolo_cleaning_plan import classify_review_row, make_cleaning_plan, write_cleaning_csv, write_review_pack


class YoloCleaningPlanTest(unittest.TestCase):
    def test_classify_fire_smoke_mixture_as_boundary_review(self) -> None:
        row = {
            "image": "sample.jpg",
            "review_reason": "fire:3, smoke:1",
            "truth": "fire, smoke",
            "predictions": "smoke, fire",
            "missed_truth": "fire",
            "false_positive": "smoke",
        }

        decision = classify_review_row(row)

        self.assertEqual(decision["issue_type"], "fire_smoke_boundary")
        self.assertEqual(decision["suggested_action"], "manual_relabel_or_split")

    def test_classify_gloves_miss_as_ppe_recall_review(self) -> None:
        row = {
            "image": "gloves.jpg",
            "review_reason": "gloves:2",
            "truth": "gloves, gloves, person",
            "predictions": "person",
            "missed_truth": "gloves, gloves",
            "false_positive": "",
        }

        decision = classify_review_row(row)

        self.assertEqual(decision["issue_type"], "small_ppe_recall")
        self.assertEqual(decision["suggested_action"], "add_or_relabel_training_example")

    def test_make_cleaning_plan_preserves_priority_order(self) -> None:
        rows = [
            {
                "image": "a.jpg",
                "priority_score": "1",
                "review_reason": "vest:1",
                "truth": "vest",
                "predictions": "",
                "missed_truth": "vest",
                "false_positive": "",
            },
            {
                "image": "b.jpg",
                "priority_score": "5",
                "review_reason": "fire:5",
                "truth": "fire",
                "predictions": "fire",
                "missed_truth": "fire",
                "false_positive": "fire",
            },
        ]

        plan = make_cleaning_plan(rows)

        self.assertEqual([item["image"] for item in plan], ["b.jpg", "a.jpg"])

    def test_write_cleaning_csv_preserves_source_paths_for_review_pack(self) -> None:
        rows = [
            {
                "image": "fire.jpg",
                "priority_score": "7",
                "issue_type": "fire_smoke_boundary",
                "suggested_action": "manual_relabel_or_split",
                "decision": "unreviewed",
                "review_reason": "fire:3",
                "truth": "fire",
                "predictions": "smoke",
                "missed_truth": "fire",
                "false_positive": "smoke",
                "rationale": "review",
                "source_image": "D:/dataset/images/fire.jpg",
                "source_label": "D:/dataset/labels/fire.txt",
                "source_split": "val",
                "target_class": "fire",
                "notes": "",
            }
        ]

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "cleaning.csv"

            write_cleaning_csv(rows, output_path)

            text = output_path.read_text(encoding="utf-8")

        self.assertIn("source_image", text)
        self.assertIn("D:/dataset/images/fire.jpg", text)
        self.assertIn("source_label", text)
        self.assertIn("target_class", text)

    def test_write_review_pack_uses_short_names_and_manifest(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_image = root / ("very-long-source-image-name-" + "x" * 80 + ".jpg")
            source_label = root / ("very-long-source-image-name-" + "x" * 80 + ".txt")
            source_image.write_bytes(b"image")
            source_label.write_text("5 0.5 0.5 0.2 0.2\n", encoding="utf-8")
            output_dir = root / "pack"

            write_review_pack(
                [
                    {
                        "image": source_image.name,
                        "priority_score": "7",
                        "issue_type": "fire_smoke_boundary",
                        "source_image": str(source_image),
                        "source_label": str(source_label),
                    }
                ],
                output_dir,
            )

            copied_images = list((output_dir / "images").glob("*.jpg"))
            copied_labels = list((output_dir / "labels").glob("*.txt"))
            manifest = (output_dir / "manifest.csv").read_text(encoding="utf-8")

        self.assertEqual(len(copied_images), 1)
        self.assertEqual(len(copied_labels), 1)
        self.assertLessEqual(len(copied_images[0].name), 64)
        self.assertIn("original_image", manifest)
        self.assertIn(source_image.name, manifest)


if __name__ == "__main__":
    unittest.main()

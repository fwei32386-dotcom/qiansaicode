from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.generate_yolo_review_page import build_review_items, write_review_page


class YoloReviewPageTest(unittest.TestCase):
    def test_build_review_items_links_existing_prediction_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "review.csv"
            pred_dir = root / "predictions"
            pred_dir.mkdir()
            Image.new("RGB", (24, 24), "white").save(pred_dir / "sample.jpg")
            with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=[
                        "image",
                        "priority_score",
                        "review_reason",
                        "truth",
                        "predictions",
                        "missed_truth",
                        "false_positive",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "image": "sample.jpg",
                        "priority_score": "2",
                        "review_reason": "fire:1, smoke:1",
                        "truth": "fire",
                        "predictions": "smoke",
                        "missed_truth": "fire",
                        "false_positive": "smoke",
                    }
                )

            items = build_review_items(csv_path, pred_dir)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["image"], "sample.jpg")
        self.assertTrue(items[0]["preview_exists"])

    def test_write_review_page_contains_reason_and_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "review.html"
            write_review_page(
                [
                    {
                        "image": "sample.jpg",
                        "priority_score": "2",
                        "review_reason": "fire:1",
                        "truth": "fire",
                        "predictions": "smoke",
                        "missed_truth": "fire",
                        "false_positive": "smoke",
                        "preview_relative": "../predictions/sample.jpg",
                        "preview_exists": True,
                    }
                ],
                output,
            )
            html = output.read_text(encoding="utf-8")

        self.assertIn("fire:1", html)
        self.assertIn("../predictions/sample.jpg", html)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.enrich_yolo_review import enrich_review_rows


class EnrichYoloReviewTest(unittest.TestCase):
    def test_enrich_review_rows_adds_source_paths_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_csv = root / "review.csv"
            manifest_json = root / "manifest.json"
            with review_csv.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=["image", "review_reason"])
                writer.writeheader()
                writer.writerow({"image": "probe_a.jpg", "review_reason": "gloves:1"})
            manifest_json.write_text(
                json.dumps(
                    [
                        {
                            "image": str(root / "probe_a.jpg"),
                            "image_path": str(root / "source.jpg"),
                            "label_path": str(root / "source.txt"),
                            "split": "val",
                            "class_name": "gloves",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            rows = enrich_review_rows(review_csv, manifest_json)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_image"], str(root / "source.jpg"))
        self.assertEqual(rows[0]["source_label"], str(root / "source.txt"))
        self.assertEqual(rows[0]["source_split"], "val")
        self.assertEqual(rows[0]["target_class"], "gloves")


if __name__ == "__main__":
    unittest.main()

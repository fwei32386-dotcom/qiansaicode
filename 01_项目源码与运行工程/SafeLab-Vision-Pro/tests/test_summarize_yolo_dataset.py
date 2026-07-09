from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.summarize_yolo_dataset import summarize_yolo_dataset


class SummarizeYoloDatasetTest(unittest.TestCase):
    def test_summarize_counts_images_labels_and_classes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "dataset"
            for split in ["train", "val", "test"]:
                (dataset / "images" / split).mkdir(parents=True)
                (dataset / "labels" / split).mkdir(parents=True)
            Image.new("RGB", (16, 16), "white").save(dataset / "images" / "train" / "a.jpg")
            (dataset / "labels" / "train" / "a.txt").write_text(
                "0 0.5 0.5 0.5 0.5\n1 0.4 0.4 0.2 0.2\n",
                encoding="utf-8",
            )
            (dataset / "data.yaml").write_text(
                "names:\n  0: fire\n  1: smoke\n",
                encoding="utf-8",
            )

            summary = summarize_yolo_dataset(dataset)

        self.assertEqual(summary["total_images"], 1)
        self.assertEqual(summary["total_label_files"], 1)
        self.assertEqual(summary["splits"]["train"]["images"], 1)
        self.assertEqual(summary["class_counts"], {"fire": 1, "smoke": 1})


if __name__ == "__main__":
    unittest.main()

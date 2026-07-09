from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.prepare_balanced_yolo_subset import build_balanced_subset, collect_target_samples, parse_class_counts


class PrepareBalancedSubsetTest(unittest.TestCase):
    def test_collect_target_samples_prioritizes_requested_classes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "dataset"
            for split in ["train", "val", "test"]:
                (dataset / "images" / split).mkdir(parents=True)
                (dataset / "labels" / split).mkdir(parents=True)
            for index, class_id in enumerate([0, 1, 1, 2]):
                Image.new("RGB", (16, 16), "white").save(dataset / "images" / "train" / f"{index}.jpg")
                (dataset / "labels" / "train" / f"{index}.txt").write_text(
                    f"{class_id} 0.5 0.5 0.4 0.4\n",
                    encoding="utf-8",
                )

            samples = collect_target_samples(dataset, split="train", target_class_ids=[1], per_class=2)

        self.assertEqual(len(samples), 2)
        self.assertTrue(all(sample.target_class_id == 1 for sample in samples))

    def test_build_balanced_subset_writes_dataset_yaml_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            output = Path(tmp) / "output"
            for split in ["train", "val", "test"]:
                (source / "images" / split).mkdir(parents=True)
                (source / "labels" / split).mkdir(parents=True)
            Image.new("RGB", (16, 16), "white").save(source / "images" / "train" / "a.jpg")
            (source / "labels" / "train" / "a.txt").write_text("1 0.5 0.5 0.4 0.4\n", encoding="utf-8")
            (source / "data.yaml").write_text("names:\n  0: person\n  1: helmet\n", encoding="utf-8")

            summary = build_balanced_subset(source, output, target_class_ids=[1], per_class=1)

            self.assertEqual(summary["total_images"], 1)
            self.assertTrue((output / "data.yaml").exists())
            self.assertTrue((output / "images" / "train" / "a.jpg").exists())
            self.assertEqual(
                (output / "labels" / "train" / "a.txt").read_text(encoding="utf-8").strip(),
                "1 0.5 0.5 0.4 0.4",
            )

    def test_parse_class_counts_accepts_per_class_overrides(self) -> None:
        self.assertEqual(parse_class_counts("1:2, 2:3"), {1: 2, 2: 3})

    def test_build_balanced_subset_accepts_per_class_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            output = Path(tmp) / "output"
            for split in ["train", "val", "test"]:
                (source / "images" / split).mkdir(parents=True)
                (source / "labels" / split).mkdir(parents=True)
            for index, class_id in enumerate([1, 1, 2, 2, 2]):
                Image.new("RGB", (16, 16), "white").save(source / "images" / "train" / f"{index}.jpg")
                (source / "labels" / "train" / f"{index}.txt").write_text(
                    f"{class_id} 0.5 0.5 0.4 0.4\n",
                    encoding="utf-8",
                )
            (source / "data.yaml").write_text("names:\n  1: helmet\n  2: vest\n", encoding="utf-8")

            summary = build_balanced_subset(source, output, target_class_ids=[1, 2], per_class=1, class_counts={1: 1, 2: 2})

            copied_images = list((output / "images" / "train").glob("*.jpg"))

        self.assertEqual(len(copied_images), 3)
        self.assertEqual(summary["class_counts"], {1: 1, 2: 2})


if __name__ == "__main__":
    unittest.main()

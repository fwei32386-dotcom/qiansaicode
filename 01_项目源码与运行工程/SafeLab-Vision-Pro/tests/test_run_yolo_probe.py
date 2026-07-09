from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tools.run_yolo_probe import collect_class_samples, copy_probe_samples


class RunYoloProbeTest(unittest.TestCase):
    def test_collect_class_samples_limits_each_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "dataset"
            for split in ["val", "train"]:
                (dataset / "images" / split).mkdir(parents=True)
                (dataset / "labels" / split).mkdir(parents=True)
            for index in range(3):
                Image.new("RGB", (32, 32), "white").save(dataset / "images" / "val" / f"sample_{index}.jpg")
                (dataset / "labels" / "val" / f"sample_{index}.txt").write_text(
                    "1 0.5 0.5 0.5 0.5\n",
                    encoding="utf-8",
                )

            samples = collect_class_samples(dataset, class_ids=[1], per_class=2)

        self.assertEqual(len(samples), 2)
        self.assertTrue(all(sample.class_id == 1 for sample in samples))

    def test_collect_class_samples_uses_dataset_class_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "dataset"
            (dataset / "images" / "val").mkdir(parents=True)
            (dataset / "labels" / "val").mkdir(parents=True)
            dataset.joinpath("data.yaml").write_text(
                "names:\n"
                "  0: fire\n"
                "  1: smoke\n",
                encoding="utf-8",
            )
            Image.new("RGB", (32, 32), "white").save(dataset / "images" / "val" / "fire.jpg")
            Image.new("RGB", (32, 32), "white").save(dataset / "images" / "val" / "smoke.jpg")
            (dataset / "labels" / "val" / "fire.txt").write_text("0 0.5 0.5 0.5 0.5\n", encoding="utf-8")
            (dataset / "labels" / "val" / "smoke.txt").write_text("1 0.5 0.5 0.5 0.5\n", encoding="utf-8")

            samples = collect_class_samples(dataset, per_class=1)

        self.assertEqual([sample.class_name for sample in samples], ["fire", "smoke"])

    def test_copy_probe_samples_preserves_image_and_label_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "dataset"
            output = Path(tmp) / "probe"
            (dataset / "images" / "val").mkdir(parents=True)
            (dataset / "labels" / "val").mkdir(parents=True)
            image = dataset / "images" / "val" / "sample.jpg"
            label = dataset / "labels" / "val" / "sample.txt"
            Image.new("RGB", (32, 32), "white").save(image)
            label.write_text("0 0.5 0.5 0.5 0.5\n", encoding="utf-8")

            samples = collect_class_samples(dataset, class_ids=[0], per_class=1)
            manifest = copy_probe_samples(samples, output)

            self.assertEqual(len(manifest), 1)
            self.assertTrue((output / "images").joinpath(Path(manifest[0]["image"]).name).exists())
            self.assertTrue((output / "labels").joinpath(Path(manifest[0]["label"]).name).exists())


if __name__ == "__main__":
    unittest.main()

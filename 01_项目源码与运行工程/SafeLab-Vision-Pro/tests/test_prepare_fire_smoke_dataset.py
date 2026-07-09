from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.prepare_fire_smoke_dataset import build_fire_smoke_dataset, remap_fire_smoke_lines


class PrepareFireSmokeDatasetTest(unittest.TestCase):
    def test_remap_fire_smoke_lines_keeps_only_fire_and_smoke(self) -> None:
        lines = [
            "0 0.1 0.1 0.2 0.2",
            "5 0.5 0.5 0.3 0.3",
            "6 0.7 0.7 0.2 0.2",
        ]

        remapped = remap_fire_smoke_lines(lines)

        self.assertEqual(remapped, ["0 0.5 0.5 0.3 0.3", "1 0.7 0.7 0.2 0.2"])

    def test_build_fire_smoke_dataset_copies_only_positive_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            output = root / "output"
            for split in ["train", "val", "test"]:
                (source / "images" / split).mkdir(parents=True)
                (source / "labels" / split).mkdir(parents=True)

            Image.new("RGB", (32, 32), "white").save(source / "images" / "train" / "fire.jpg")
            (source / "labels" / "train" / "fire.txt").write_text(
                "5 0.5 0.5 0.3 0.3\n0 0.1 0.1 0.2 0.2\n",
                encoding="utf-8",
            )
            Image.new("RGB", (32, 32), "white").save(source / "images" / "train" / "person.jpg")
            (source / "labels" / "train" / "person.txt").write_text(
                "0 0.5 0.5 0.3 0.3\n",
                encoding="utf-8",
            )

            summary = build_fire_smoke_dataset(source, output)

            self.assertEqual(summary["total_images"], 1)
            self.assertEqual(summary["class_counts"], {"fire": 1, "smoke": 0})
            self.assertTrue((output / "images" / "train" / "fire.jpg").exists())
            self.assertEqual(
                (output / "labels" / "train" / "fire.txt").read_text(encoding="utf-8").strip(),
                "0 0.5 0.5 0.3 0.3",
            )
            self.assertFalse((output / "images" / "train" / "person.jpg").exists())


if __name__ == "__main__":
    unittest.main()

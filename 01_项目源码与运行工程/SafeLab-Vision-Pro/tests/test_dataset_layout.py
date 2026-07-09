from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.validate_dataset_layout import validate_dataset_layout


class DatasetLayoutTest(unittest.TestCase):
    def test_valid_dataset_skeleton_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "datasets" / "safelab"
            labels = root / "models" / "labels.txt"
            labels.parent.mkdir(parents=True)
            labels.write_text("person\nhelmet\n", encoding="utf-8")
            for split in ("train", "val", "test"):
                (dataset / "images" / split).mkdir(parents=True)
                (dataset / "labels" / split).mkdir(parents=True)
            (dataset / "data.yaml").write_text(
                "path: dataset\ntrain: images/train\nval: images/val\nnames:\n  0: person\n  1: helmet\n",
                encoding="utf-8",
            )

            errors = validate_dataset_layout(dataset, labels)

        self.assertEqual(errors, [])

    def test_invalid_label_values_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "datasets" / "safelab"
            labels = root / "models" / "labels.txt"
            labels.parent.mkdir(parents=True)
            labels.write_text("person\n", encoding="utf-8")
            for split in ("train", "val", "test"):
                (dataset / "images" / split).mkdir(parents=True)
                (dataset / "labels" / split).mkdir(parents=True)
            (dataset / "images" / "train" / "bad.jpg").write_text("placeholder", encoding="utf-8")
            (dataset / "labels" / "train" / "bad.txt").write_text("2 0.5 0.5 1.2 0.1\n", encoding="utf-8")
            (dataset / "data.yaml").write_text(
                "path: dataset\ntrain: images/train\nval: images/val\nnames:\n  0: person\n",
                encoding="utf-8",
            )

            errors = validate_dataset_layout(dataset, labels)

        self.assertTrue(any("invalid class id" in error for error in errors))
        self.assertTrue(any("out of range" in error for error in errors))


if __name__ == "__main__":
    unittest.main()

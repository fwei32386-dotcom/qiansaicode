from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.merge_yolo_predictions import merge_prediction_labels, parse_class_ids


class MergeYoloPredictionsTest(unittest.TestCase):
    def test_parse_class_ids_accepts_comma_separated_values(self) -> None:
        self.assertEqual(parse_class_ids("5, 6"), {5, 6})

    def test_merge_prediction_labels_uses_secondary_for_selected_classes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            primary = root / "primary"
            secondary = root / "secondary"
            output = root / "merged"
            primary.mkdir()
            secondary.mkdir()

            (primary / "sample.txt").write_text(
                "0 0.1 0.1 0.2 0.2 0.90\n"
                "5 0.2 0.2 0.2 0.2 0.80\n"
                "6 0.3 0.3 0.2 0.2 0.70\n",
                encoding="utf-8",
            )
            (secondary / "sample.txt").write_text(
                "5 0.4 0.4 0.2 0.2 0.60\n"
                "6 0.5 0.5 0.2 0.2 0.65\n"
                "2 0.6 0.6 0.2 0.2 0.95\n",
                encoding="utf-8",
            )

            merge_prediction_labels(primary, secondary, output, {5, 6})

            merged = (output / "sample.txt").read_text(encoding="utf-8").splitlines()

        self.assertEqual(
            merged,
            [
                "0 0.1 0.1 0.2 0.2 0.90",
                "5 0.4 0.4 0.2 0.2 0.60",
                "6 0.5 0.5 0.2 0.2 0.65",
            ],
        )


if __name__ == "__main__":
    unittest.main()

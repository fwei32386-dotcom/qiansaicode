from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.filter_yolo_predictions import filter_prediction_labels


class FilterYoloPredictionsTest(unittest.TestCase):
    def test_filter_prediction_labels_applies_class_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            (source / "sample.txt").write_text(
                "4 0.5 0.5 0.2 0.2 0.49\n"
                "4 0.5 0.5 0.2 0.2 0.51\n"
                "5 0.5 0.5 0.2 0.2 0.40\n",
                encoding="utf-8",
            )

            filter_prediction_labels(source, output, thresholds={4: 0.5, 5: 0.45})

            lines = (output / "sample.txt").read_text(encoding="utf-8").splitlines()

        self.assertEqual(lines, ["4 0.5 0.5 0.2 0.2 0.51"])


if __name__ == "__main__":
    unittest.main()

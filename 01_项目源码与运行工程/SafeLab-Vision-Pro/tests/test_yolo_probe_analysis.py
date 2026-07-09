from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.analyze_yolo_probe import evaluate_probe, yolo_to_xyxy


class YoloProbeAnalysisTest(unittest.TestCase):
    def test_yolo_to_xyxy_converts_normalized_box(self) -> None:
        box = yolo_to_xyxy([0.5, 0.5, 0.25, 0.5], width=200, height=100)

        self.assertEqual(box, [75.0, 25.0, 125.0, 75.0])

    def test_evaluate_probe_counts_tp_fp_and_fn_by_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            labels = root / "labels"
            predictions = root / "predictions" / "labels"
            images.mkdir(parents=True)
            labels.mkdir()
            predictions.mkdir(parents=True)

            # A tiny valid PNG header is enough for Pillow to read dimensions.
            from PIL import Image

            Image.new("RGB", (100, 100), "white").save(images / "sample.jpg")
            labels.joinpath("sample.txt").write_text(
                "1 0.500000 0.500000 0.200000 0.200000\n"
                "2 0.200000 0.200000 0.100000 0.100000\n",
                encoding="utf-8",
            )
            predictions.joinpath("sample.txt").write_text(
                "1 0.500000 0.500000 0.200000 0.200000 0.900000\n"
                "2 0.800000 0.800000 0.100000 0.100000 0.800000\n"
                "3 0.100000 0.100000 0.100000 0.100000 0.700000\n",
                encoding="utf-8",
            )

            result = evaluate_probe(images, labels, predictions)

        by_class = {row["class_id"]: row for row in result["metrics"]}
        self.assertEqual(by_class[1]["tp"], 1)
        self.assertEqual(by_class[1]["fp"], 0)
        self.assertEqual(by_class[1]["fn"], 0)
        self.assertEqual(by_class[2]["tp"], 0)
        self.assertEqual(by_class[2]["fp"], 1)
        self.assertEqual(by_class[2]["fn"], 1)
        self.assertEqual(by_class[3]["tp"], 0)
        self.assertEqual(by_class[3]["fp"], 1)
        self.assertEqual(by_class[3]["fn"], 0)

    def test_evaluate_probe_uses_custom_class_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / "images"
            labels = root / "labels"
            predictions = root / "predictions" / "labels"
            images.mkdir(parents=True)
            labels.mkdir()
            predictions.mkdir(parents=True)

            from PIL import Image

            Image.new("RGB", (100, 100), "white").save(images / "sample.jpg")
            labels.joinpath("sample.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
            predictions.joinpath("sample.txt").write_text("0 0.5 0.5 0.2 0.2 0.9\n", encoding="utf-8")

            result = evaluate_probe(images, labels, predictions, class_names={0: "fire", 1: "smoke"})

        self.assertEqual(result["metrics"][0]["class_name"], "fire")
        self.assertEqual(result["metrics"][1]["class_name"], "smoke")


if __name__ == "__main__":
    unittest.main()

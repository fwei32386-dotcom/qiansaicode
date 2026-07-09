from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from tools.scan_yolo_thresholds import ThresholdScanConfig, scan_thresholds


class ScanYoloThresholdsTest(unittest.TestCase):
    def test_scan_thresholds_finds_passing_configuration(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_dir = root / "images"
            truth_dir = root / "truth"
            pred_dir = root / "pred"
            image_dir.mkdir()
            truth_dir.mkdir()
            pred_dir.mkdir()
            Image.new("RGB", (100, 100)).save(image_dir / "sample.jpg")
            (truth_dir / "sample.txt").write_text("5 0.5 0.5 0.2 0.2\n", encoding="utf-8")
            (pred_dir / "sample.txt").write_text(
                "5 0.5 0.5 0.2 0.2 0.90\n"
                "5 0.1 0.1 0.1 0.1 0.20\n",
                encoding="utf-8",
            )

            result = scan_thresholds(
                image_dir,
                truth_dir,
                pred_dir,
                ThresholdScanConfig(class_thresholds={5: [0.0, 0.5]}, target_precision=0.9, target_recall=0.9),
            )

        self.assertTrue(result["best"]["qualified"])
        self.assertEqual(result["best"]["thresholds"], {5: 0.5})
        self.assertEqual(result["best"]["metrics"]["fire"]["precision"], 1.0)
        self.assertEqual(result["best"]["metrics"]["fire"]["recall"], 1.0)

    def test_scan_thresholds_scans_classes_independently(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_dir = root / "images"
            truth_dir = root / "truth"
            pred_dir = root / "pred"
            image_dir.mkdir()
            truth_dir.mkdir()
            pred_dir.mkdir()
            Image.new("RGB", (100, 100)).save(image_dir / "sample.jpg")
            (truth_dir / "sample.txt").write_text("5 0.5 0.5 0.2 0.2\n6 0.4 0.4 0.2 0.2\n", encoding="utf-8")
            (pred_dir / "sample.txt").write_text(
                "5 0.5 0.5 0.2 0.2 0.90\n"
                "6 0.4 0.4 0.2 0.2 0.80\n",
                encoding="utf-8",
            )

            result = scan_thresholds(
                image_dir,
                truth_dir,
                pred_dir,
                ThresholdScanConfig(class_thresholds={5: [0.1, 0.2, 0.3], 6: [0.1, 0.2, 0.3]}),
            )

        self.assertEqual(result["candidate_count"], 6)

    def test_scan_thresholds_uses_custom_class_names(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_dir = root / "images"
            truth_dir = root / "truth"
            pred_dir = root / "pred"
            image_dir.mkdir()
            truth_dir.mkdir()
            pred_dir.mkdir()
            Image.new("RGB", (100, 100)).save(image_dir / "sample.jpg")
            (truth_dir / "sample.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
            (pred_dir / "sample.txt").write_text("0 0.5 0.5 0.2 0.2 0.90\n", encoding="utf-8")

            result = scan_thresholds(
                image_dir,
                truth_dir,
                pred_dir,
                ThresholdScanConfig(class_thresholds={0: [0.5]}),
                class_names={0: "fire"},
            )

        self.assertIn("fire", result["best"]["metrics"])
        self.assertNotIn("person", result["best"]["metrics"])


if __name__ == "__main__":
    unittest.main()

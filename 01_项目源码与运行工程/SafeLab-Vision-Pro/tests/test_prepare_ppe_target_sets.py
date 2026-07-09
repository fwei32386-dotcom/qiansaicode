from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.prepare_ppe_target_sets import (
    build_ppe_target_sets,
    parse_class_counts,
    scene_tag_for_name,
)


def write_sample(root: Path, split: str, stem: str, label: str) -> None:
    (root / "images" / split).mkdir(parents=True, exist_ok=True)
    (root / "labels" / split).mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), "white").save(root / "images" / split / f"{stem}.jpg")
    (root / "labels" / split / f"{stem}.txt").write_text(label, encoding="utf-8")


class PreparePpeTargetSetsTest(unittest.TestCase):
    def test_scene_tag_for_name_identifies_target_scenes(self) -> None:
        self.assertEqual(scene_tag_for_name("hardhat_vest_v3_0001"), "construction")
        self.assertEqual(scene_tag_for_name("ppe_dataset_yolov8_PP02img1021"), "lab_ppe")
        self.assertEqual(scene_tag_for_name("css-data_2009_000277"), "css_generic")

    def test_parse_class_counts_accepts_overrides(self) -> None:
        self.assertEqual(parse_class_counts("0:2, 4:3"), {0: 2, 4: 3})

    def test_build_ppe_target_sets_prefers_target_scenes_and_avoids_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            acceptance = root / "acceptance"
            hard = root / "hard"
            source.mkdir(parents=True)
            (source / "data.yaml").write_text(
                "names:\n  0: person\n  1: helmet\n  2: vest\n  3: goggles\n  4: gloves\n",
                encoding="utf-8",
            )
            write_sample(source, "val", "css-data_2009_generic_person", "0 0.5 0.5 0.5 0.5\n")
            write_sample(source, "val", "ppe_dataset_yolov8_lab_person", "0 0.5 0.5 0.5 0.5\n")
            write_sample(source, "train", "hardhat_vest_v3_train_vest", "2 0.5 0.5 0.1 0.1\n")
            write_sample(source, "train", "ppe_dataset_yolov8_train_goggles", "3 0.5 0.5 0.1 0.1\n")

            summary = build_ppe_target_sets(
                source,
                acceptance,
                hard,
                acceptance_counts={0: 1},
                hard_counts={2: 1, 3: 1},
            )

            acceptance_images = {path.name for path in (acceptance / "images" / "test").glob("*.jpg")}
            hard_images = {path.name for path in (hard / "images" / "train").glob("*.jpg")}

        self.assertIn("ppe_dataset_yolov8_lab_person.jpg", acceptance_images)
        self.assertNotIn("css-data_2009_generic_person.jpg", acceptance_images)
        self.assertTrue(acceptance_images.isdisjoint(hard_images))
        self.assertEqual(summary["acceptance"]["images"], 1)
        self.assertEqual(summary["hard"]["images"], 2)


if __name__ == "__main__":
    unittest.main()

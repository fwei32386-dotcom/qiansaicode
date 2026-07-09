from __future__ import annotations

import argparse
import unittest
from pathlib import Path

from tools.train_yolo_candidate import build_train_kwargs


class TrainYoloCandidateTest(unittest.TestCase):
    def test_build_train_kwargs_keeps_windows_safe_defaults(self) -> None:
        args = argparse.Namespace(
            data=Path("data.yaml"),
            epochs=5,
            imgsz=416,
            batch=16,
            device="0",
            workers=0,
            cache=False,
            project="D:/runs",
            name="candidate",
            optimizer=None,
            lr0=None,
            lrf=None,
            freeze=None,
        )

        kwargs = build_train_kwargs(args)

        self.assertEqual(kwargs["workers"], 0)
        self.assertEqual(kwargs["patience"], 5)
        self.assertNotIn("optimizer", kwargs)
        self.assertNotIn("lr0", kwargs)
        self.assertNotIn("freeze", kwargs)

    def test_build_train_kwargs_accepts_conservative_finetune_options(self) -> None:
        args = argparse.Namespace(
            data=Path("data.yaml"),
            epochs=20,
            imgsz=416,
            batch=16,
            device="0",
            workers=0,
            cache=False,
            project="D:/runs",
            name="candidate",
            optimizer="AdamW",
            lr0=0.001,
            lrf=0.1,
            freeze=10,
        )

        kwargs = build_train_kwargs(args)

        self.assertEqual(kwargs["optimizer"], "AdamW")
        self.assertEqual(kwargs["lr0"], 0.001)
        self.assertEqual(kwargs["lrf"], 0.1)
        self.assertEqual(kwargs["freeze"], 10)
        self.assertEqual(kwargs["patience"], 20)


if __name__ == "__main__":
    unittest.main()

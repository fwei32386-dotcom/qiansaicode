from __future__ import annotations

import unittest

from unittest.mock import patch

from tools.run_board_rknn_image_samples import build_detection_command, parse_args


class BoardRknnImageSamplesTest(unittest.TestCase):
    def test_build_detection_command_sets_uint8_input_and_debug_stats(self) -> None:
        command = build_detection_command(
            binary="/root/app/rknn_runtime/safelab_rknn_detect",
            model="/root/app/models/model.rknn",
            remote_blob="/root/app/reports/sample.rgb",
            remote_jsonl="/root/app/reports/sample.jsonl",
            frame_id=7,
            frame_width=1280,
            frame_height=720,
            input_type="uint8",
            pass_through=False,
            confidence_threshold=0.25,
            dump_output_stats=True,
        )

        self.assertIn("--input-type uint8", command)
        self.assertIn("--conf-threshold 0.25", command)
        self.assertIn("--dump-output-stats", command)
        self.assertNotIn("--pass-through", command)

    def test_parse_args_accepts_alternate_board_model(self) -> None:
        with patch(
            "sys.argv",
            [
                "run_board_rknn_image_samples.py",
                "--model",
                "/root/SafeLab-Vision-Pro/models/rknn/fp.rknn",
            ],
        ):
            args = parse_args()

        self.assertEqual(args.model, "/root/SafeLab-Vision-Pro/models/rknn/fp.rknn")

    def test_parse_args_defaults_to_fp_rknn_model(self) -> None:
        with patch("sys.argv", ["run_board_rknn_image_samples.py"]):
            args = parse_args()

        self.assertTrue(args.model.endswith("safelab_yolov8n_fire_smoke_v3_fp.rknn"))
        self.assertFalse(args.debug_variants)


if __name__ == "__main__":
    unittest.main()

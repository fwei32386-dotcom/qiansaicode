from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.run_board_dual_model_image import BoardModelSpec, build_detection_command, merge_jsonl_files


class RunBoardDualModelImageTest(unittest.TestCase):
    def test_build_detection_command_sets_label_preset_and_threshold(self) -> None:
        spec = BoardModelSpec(
            key="ppe",
            model="/root/models/ppe.rknn",
            label_preset="ppe",
            confidence_threshold=0.31,
        )

        command = build_detection_command(
            binary="/root/bin/safelab_rknn_detect",
            spec=spec,
            remote_blob="/root/run/frame.rgb",
            remote_jsonl="/root/run/ppe.jsonl",
            frame_id=12,
            frame_width=1280,
            frame_height=720,
            input_type="uint8",
        )

        self.assertIn("--model /root/models/ppe.rknn", command)
        self.assertIn("--frame-id 12", command)
        self.assertIn("--label-preset ppe", command)
        self.assertIn("--conf-threshold 0.31", command)
        self.assertIn("--output /root/run/ppe.jsonl", command)

    def test_merge_jsonl_files_keeps_all_detection_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "ppe.jsonl"
            second = root / "fire_smoke.jsonl"
            output = root / "combined.jsonl"
            first.write_text(json.dumps({"frame_id": 1, "class_name": "person"}) + "\n", encoding="utf-8")
            second.write_text(json.dumps({"frame_id": 1, "class_name": "smoke"}) + "\n", encoding="utf-8")

            count = merge_jsonl_files([first, second], output)

            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(count, 2)
        self.assertEqual([record["class_name"] for record in records], ["person", "smoke"])


if __name__ == "__main__":
    unittest.main()

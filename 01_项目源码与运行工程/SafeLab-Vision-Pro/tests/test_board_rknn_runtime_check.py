from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BoardRknnRuntimeCheckTest(unittest.TestCase):
    def test_board_rknn_runtime_check_covers_model_runtime_and_build_env(self) -> None:
        text = (ROOT / "tools" / "board_rknn_runtime_check.sh").read_text(encoding="utf-8")

        self.assertTrue(text.startswith("#!/bin/sh"))
        self.assertIn("safelab_yolov8n_fire_smoke_v3.rknn", text)
        self.assertIn("librknnrt.so", text)
        self.assertIn("rknn_common_test", text)
        self.assertIn("rknn_api.h", text)
        self.assertIn("gcc", text)

    def test_board_rknn_runtime_check_reports_dynamic_build_state(self) -> None:
        text = (ROOT / "tools" / "board_rknn_runtime_check.sh").read_text(encoding="utf-8")

        self.assertIn("JSON_REPORT_PATH", text)
        self.assertIn("header_status=", text)
        self.assertIn("compiler_status=", text)
        self.assertIn("cross_compile_required", text)
        self.assertIn("safelab_binary_status", text)
        self.assertIn("safelab_binary_contract", text)
        self.assertIn("board_binary_present", text)
        self.assertIn("safelab_rknn_detect --contract", text)
        self.assertNotIn("build_state: waiting_for_rknn_api_header_and_cross_compiler", text)

    def test_readme_documents_one_command_rknn_check_scope(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("sh tools/board_rknn_runtime_check.sh", readme)
        self.assertIn("rknn_api.h", readme)
        self.assertIn("/usr/lib/librknnrt.so", readme)
        self.assertIn("rknn_common_test", readme)
        self.assertIn("models/rknn", readme)
        self.assertIn("models/labels.txt", readme)
        self.assertIn("test_images", readme)
        self.assertIn("reports/board_rknn_runtime_check.json", readme)

    def test_rknn_runtime_skeleton_documents_cross_compile_need(self) -> None:
        readme = (ROOT / "rknn_runtime" / "README.md").read_text(encoding="utf-8")
        source = (ROOT / "rknn_runtime" / "safelab_rknn_detect.cpp").read_text(encoding="utf-8")
        postprocess = (ROOT / "rknn_runtime" / "yolov8_postprocess.cpp").read_text(encoding="utf-8")
        header = (ROOT / "rknn_runtime" / "yolov8_postprocess.hpp").read_text(encoding="utf-8")
        makefile = (ROOT / "rknn_runtime" / "Makefile").read_text(encoding="utf-8")

        self.assertIn("rknn_api.h", readme)
        self.assertIn("safelab_rknn_detect", source)
        self.assertIn("decode_yolov8_channel_major", postprocess)
        self.assertIn("detection_to_json", header)
        self.assertIn("class-aware NMS", readme)
        self.assertIn("CXX", makefile)
        self.assertIn("--contract", source)
        self.assertIn("--raw", source)
        self.assertIn("SAFELAB_WITH_RKNN", source)
        self.assertIn("rknn_outputs_get", source)
        self.assertIn("WITH_RKNN", makefile)

    def test_sync_script_preserves_board_rknn_assets(self) -> None:
        text = (ROOT / "tools" / "sync_to_board.ps1").read_text(encoding="utf-8")

        self.assertIn(".safelab_preserve", text)
        self.assertIn("models/rknn", text)
        self.assertIn("models/labels.txt", text)
        self.assertIn("test_images", text)

    def test_rknn_detect_contract_cli_outputs_detection_json(self) -> None:
        compiler = shutil.which("g++")
        if compiler is None:
            self.skipTest("g++ is not available on this host")

        with tempfile.TemporaryDirectory() as tmp:
            output_binary = Path(tmp) / "safelab_rknn_detect"
            subprocess.run(
                [
                    compiler,
                    "-std=c++17",
                    "-O2",
                    "-Wall",
                    "-Wextra",
                    "-o",
                    str(output_binary),
                    str(ROOT / "rknn_runtime" / "safelab_rknn_detect.cpp"),
                    str(ROOT / "rknn_runtime" / "yolov8_postprocess.cpp"),
                ],
                check=True,
                cwd=ROOT,
            )
            result = subprocess.run(
                [str(output_binary), "--contract"],
                check=True,
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        payload = json.loads(result.stdout.strip())
        self.assertEqual(payload["source_type"], "camera")
        self.assertEqual(payload["class_name"], "person")
        self.assertEqual(payload["model_name"], "safelab_yolov8n_rknn_contract_probe")
        self.assertIn("bbox", payload)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dashboard.input_source import build_input_source_state, resolve_input_source, save_input_source


class DashboardInputSourceTest(unittest.TestCase):
    def test_missing_runtime_file_uses_video_config_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_video_config(root)
            runtime = root / "data" / "runtime" / "input_source.json"

            state = build_input_source_state(config, runtime)

        self.assertEqual(state["input_source"]["selected_source"], "camera_ov13855")
        self.assertEqual(state["input_source"]["label"], "摄像头输入")
        self.assertTrue(state["input_source"]["requires_restart"])
        self.assertEqual(
            [item["id"] for item in state["available_input_sources"]],
            ["camera_ov13855", "board_file_demo"],
        )

    def test_hdmi_capture_is_rejected_because_board_has_no_capture_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_video_config(root)
            runtime = root / "data" / "runtime" / "input_source.json"
            save_input_source("camera_ov13855", config, runtime)

            with self.assertRaises(ValueError):
                save_input_source("hdmi_capture", config, runtime)
            payload = json.loads(runtime.read_text(encoding="utf-8"))

        self.assertEqual(payload["selected_source"], "camera_ov13855")

    def test_file_input_source_is_available_and_saveable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_video_config(root)
            runtime = root / "data" / "runtime" / "input_source.json"

            saved = save_input_source("file_demo", config, runtime)
            state = build_input_source_state(config, runtime)

        self.assertEqual(saved["input_source"]["selected_source"], "file_demo")
        self.assertEqual(saved["input_source"]["label"], "本地输入")
        self.assertEqual(saved["input_source"]["source_type"], "file")
        self.assertNotIn("file_demo", [item["id"] for item in state["available_input_sources"]])

    def test_board_file_input_source_can_store_runtime_board_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_video_config(root)
            runtime = root / "data" / "runtime" / "input_source.json"

            save_input_source(
                "board_file_demo",
                config,
                runtime,
                source_overrides={
                    "board_path": "/root/safelab_media/current_demo.mp4",
                    "path": "data/runtime/board_media/current_demo.mp4",
                    "width": "362",
                    "height": "398",
                    "media_type": "video",
                },
            )
            resolved = resolve_input_source(config, runtime)
            payload = json.loads(runtime.read_text(encoding="utf-8"))

        self.assertEqual(payload["selected_source"], "board_file_demo")
        self.assertEqual(payload["source_type"], "board_file")
        self.assertEqual(payload["board_path"], "/root/safelab_media/current_demo.mp4")
        self.assertEqual(payload["path"], "data/runtime/board_media/current_demo.mp4")
        self.assertEqual(payload["width"], 362)
        self.assertEqual(payload["height"], 398)
        self.assertEqual(payload["media_type"], "video")
        self.assertEqual(resolved["source_config"]["board_path"], "/root/safelab_media/current_demo.mp4")
        self.assertEqual(resolved["source_config"]["width"], "362")
        self.assertEqual(resolved["source_config"]["height"], "398")
        self.assertEqual(resolved["source_config"]["media_type"], "video")

    def test_resaving_same_board_file_source_preserves_uploaded_media_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_video_config(root)
            runtime = root / "data" / "runtime" / "input_source.json"
            save_input_source(
                "board_file_demo",
                config,
                runtime,
                source_overrides={
                    "board_path": "/root/safelab_media/current_demo.mp4",
                    "path": "data/runtime/board_media/current_demo.mp4",
                    "width": "362",
                    "height": "398",
                    "media_type": "video",
                },
            )

            save_input_source("board_file_demo", config, runtime)
            payload = json.loads(runtime.read_text(encoding="utf-8"))

        self.assertEqual(payload["board_path"], "/root/safelab_media/current_demo.mp4")
        self.assertEqual(payload["path"], "data/runtime/board_media/current_demo.mp4")
        self.assertEqual(payload["media_type"], "video")
        self.assertEqual(payload["width"], 362)
        self.assertEqual(payload["height"], 398)

    def test_resolve_input_source_includes_selected_source_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_video_config(root)
            runtime = root / "data" / "runtime" / "input_source.json"
            save_input_source("file_demo", config, runtime)

            resolved = resolve_input_source(config, runtime)

        self.assertEqual(resolved["input_source"]["selected_source"], "file_demo")
        self.assertEqual(resolved["source_config"]["source_type"], "file")
        self.assertEqual(resolved["source_config"]["path"], "video/demo.mp4")

    def test_file_input_source_can_store_runtime_path_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_video_config(root)
            runtime = root / "data" / "runtime" / "input_source.json"

            save_input_source("file_demo", config, runtime, source_overrides={"path": "data/runtime/local_media/a.mp4"})
            resolved = resolve_input_source(config, runtime)
            payload = json.loads(runtime.read_text(encoding="utf-8"))

        self.assertEqual(payload["path"], "data/runtime/local_media/a.mp4")
        self.assertEqual(resolved["source_config"]["path"], "data/runtime/local_media/a.mp4")

    def test_unknown_input_source_is_rejected_without_overwriting_existing_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_video_config(root)
            runtime = root / "data" / "runtime" / "input_source.json"
            save_input_source("camera_ov13855", config, runtime)

            with self.assertRaises(ValueError):
                save_input_source("bad_source", config, runtime)

            payload = json.loads(runtime.read_text(encoding="utf-8"))

        self.assertEqual(payload["selected_source"], "camera_ov13855")


def _write_video_config(root: Path) -> Path:
    config = root / "video_config.yaml"
    config.write_text(
        "\n".join(
            [
                "video_sources:",
                "  default: camera_ov13855",
                "  camera_ov13855:",
                "    source_type: camera",
                "    device: /dev/video-camera0",
                "    source_name: ov13855_video11",
                "  file_demo:",
                "    source_type: file",
                "    path: video/demo.mp4",
                "    source_name: local_demo_video",
                "  board_file_demo:",
                "    source_type: board_file",
                "    board_path: /root/safelab_media/current_demo.mp4",
                "    source_name: rk_local_video",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return config


if __name__ == "__main__":
    unittest.main()

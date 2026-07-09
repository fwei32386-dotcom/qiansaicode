from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dashboard.voice_feedback import handle_voice_feedback


class VoiceFeedbackTest(unittest.TestCase):
    def test_simulated_voice_can_switch_scene_and_write_speech_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = handle_voice_feedback(
                "实验室模式",
                source="test_serial",
                voice_commands_path=root / "events" / "voice_commands.jsonl",
                speech_output_path=root / "events" / "speech_output.jsonl",
                xiaoduo_dialog_path=root / "events" / "xiaoduo_dialog.jsonl",
                xiaoduo_state_path=root / "runtime" / "xiaoduo_state.json",
                model_detection_path=root / "runtime" / "model_detection.json",
                scene_mode_path=root / "runtime" / "scene_mode.json",
                ai_explanations_path=root / "events" / "ai.jsonl",
                actions_path=root / "events" / "actions.jsonl",
                detections_path=root / "detections.jsonl",
            )

            scene = json.loads((root / "runtime" / "scene_mode.json").read_text(encoding="utf-8"))
            voice_rows = _read_jsonl(root / "events" / "voice_commands.jsonl")
            speech_rows = _read_jsonl(root / "events" / "speech_output.jsonl")
            state = json.loads((root / "runtime" / "xiaoduo_state.json").read_text(encoding="utf-8"))

        self.assertEqual(result["command"]["command"], "set_lab_mode")
        self.assertEqual(scene["mode"], "lab")
        self.assertEqual(scene["required_ppe"], ["goggles", "gloves"])
        self.assertEqual(voice_rows[0]["source"], "test_serial")
        self.assertEqual(voice_rows[0]["raw_text"], "实验室模式")
        self.assertEqual(speech_rows[0]["text"], "已切换实验室模式。")
        self.assertEqual(speech_rows[0]["speech_source"], "voice_feedback")
        self.assertEqual(state["last_spoken_text"], "已切换实验室模式。")

    def test_start_detection_voice_command_enables_model_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_detection = root / "runtime" / "model_detection.json"

            handle_voice_feedback(
                "开始检测",
                voice_commands_path=root / "events" / "voice_commands.jsonl",
                speech_output_path=root / "events" / "speech_output.jsonl",
                xiaoduo_dialog_path=root / "events" / "xiaoduo_dialog.jsonl",
                xiaoduo_state_path=root / "runtime" / "xiaoduo_state.json",
                model_detection_path=model_detection,
                scene_mode_path=root / "runtime" / "scene_mode.json",
                ai_explanations_path=root / "events" / "ai.jsonl",
                actions_path=root / "events" / "actions.jsonl",
                detections_path=root / "detections.jsonl",
            )
            saved = json.loads(model_detection.read_text(encoding="utf-8"))

        self.assertTrue(saved["enabled"])
        self.assertEqual(saved["interval_frames"], 75)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    unittest.main()

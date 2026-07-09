from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.voice_feedback import handle_voice_feedback


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate LD3320 voice input and write SafeLab voice feedback records.")
    parser.add_argument("text", help="例如：小多、开始检测、当前状态、工地模式、实验室模式")
    parser.add_argument("--source", default="cli_simulated_serial")
    parser.add_argument("--speak", action="store_true", help="尝试调用本机/板卡语音播报程序；默认只记录播报请求。")
    parser.add_argument("--project-root", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.project_root)
    result = handle_voice_feedback(
        args.text,
        source=args.source,
        speak=args.speak,
        voice_commands_path=root / "data" / "events" / "voice_commands.jsonl",
        speech_output_path=root / "data" / "events" / "speech_output.jsonl",
        xiaoduo_dialog_path=root / "data" / "events" / "xiaoduo_dialog.jsonl",
        xiaoduo_state_path=root / "data" / "runtime" / "xiaoduo_state.json",
        model_detection_path=root / "data" / "runtime" / "model_detection.json",
        scene_mode_path=root / "data" / "runtime" / "scene_mode.json",
        ai_explanations_path=root / "data" / "events" / "ai_explanations.jsonl",
        actions_path=root / "data" / "events" / "alarm_actions.jsonl",
        detections_path=root / "reports" / "live_pipeline" / "live_dual_model_work" / "detections_window.jsonl",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

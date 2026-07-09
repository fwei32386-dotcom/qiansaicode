from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interaction.deepseek_voice_session import handle_voice_deepseek_command


def main() -> int:
    parser = argparse.ArgumentParser(description="Handle recognized voice text as a DeepSeek interaction request.")
    parser.add_argument("text", help="Recognized voice text, such as 呼叫DeepSeek or 为什么报警.")
    parser.add_argument("--events", default=str(ROOT / "data" / "events" / "events.jsonl"))
    parser.add_argument("--actions", default=str(ROOT / "data" / "events" / "alarm_actions.jsonl"))
    parser.add_argument("--config", default=str(ROOT / "configs" / "deepseek_config.json"))
    parser.add_argument("--ai-output", default=str(ROOT / "data" / "events" / "ai_explanations.jsonl"))
    parser.add_argument("--speech-log", default=str(ROOT / "data" / "events" / "speech_output.jsonl"))
    parser.add_argument("--voice-log", default=str(ROOT / "data" / "events" / "voice_commands.jsonl"))
    parser.add_argument("--source", default="voice")
    parser.add_argument("--speak", action="store_true", help="Try real speech output instead of dry-run logging.")
    args = parser.parse_args()

    # 这里接收的是语音识别后的文本，后续可替换为真实麦克风 ASR 输出。
    result = handle_voice_deepseek_command(
        args.text,
        events_path=args.events,
        actions_path=args.actions,
        config_path=args.config,
        ai_output_path=args.ai_output,
        speech_log_path=args.speech_log,
        voice_log_path=args.voice_log,
        source=args.source,
        dry_run=not args.speak,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

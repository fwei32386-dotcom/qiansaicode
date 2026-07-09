from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interaction.ai_speech_bridge import speak_latest_ai_explanation


def main() -> int:
    parser = argparse.ArgumentParser(description="Record the latest AI explanation as a speech output request.")
    parser.add_argument("--ai-explanations", default=str(ROOT / "data" / "events" / "ai_explanations.jsonl"))
    parser.add_argument("--log", default=str(ROOT / "data" / "events" / "speech_output.jsonl"))
    parser.add_argument("--speak", action="store_true", help="Try to call espeak instead of dry-run logging only.")
    args = parser.parse_args()

    # 默认 dry-run，保证 Windows 和无音频板端也能留下可验收的播报记录。
    record = speak_latest_ai_explanation(args.ai_explanations, args.log, dry_run=not args.speak)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

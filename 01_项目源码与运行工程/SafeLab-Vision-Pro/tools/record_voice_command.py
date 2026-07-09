from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interaction.voice_command import write_voice_command_record


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a SafeLab voice command from UART/module text.")
    parser.add_argument("text")
    parser.add_argument("--source", default="manual")
    parser.add_argument("--output", default=str(ROOT / "data" / "events" / "voice_commands.jsonl"))
    args = parser.parse_args()
    print(json.dumps(write_voice_command_record(args.text, args.output, args.source), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

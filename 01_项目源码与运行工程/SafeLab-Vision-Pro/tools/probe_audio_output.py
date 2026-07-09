from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interaction.speech_output import probe_audio_devices, speak_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe SafeLab audio output and optionally record a speech request.")
    parser.add_argument("--text", default="")
    parser.add_argument("--speak", action="store_true")
    parser.add_argument("--log", default=str(ROOT / "data" / "events" / "speech_output.jsonl"))
    args = parser.parse_args()
    output = speak_text(args.text, args.log, dry_run=not args.speak) if args.text else probe_audio_devices().to_dict()
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

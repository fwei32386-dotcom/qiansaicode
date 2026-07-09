from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cloud.deepseek_client import explain_events_to_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate optional DeepSeek explanations for SafeLab events.")
    parser.add_argument("--events", default=str(ROOT / "data" / "events" / "events.jsonl"))
    parser.add_argument("--actions", default=str(ROOT / "data" / "events" / "alarm_actions.jsonl"))
    parser.add_argument("--output", default=str(ROOT / "data" / "events" / "ai_explanations.jsonl"))
    parser.add_argument("--config", default=str(ROOT / "configs" / "deepseek_config.json"))
    parser.add_argument("--max-events", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(explain_events_to_jsonl(args.events, args.actions, args.output, args.config, args.max_events), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

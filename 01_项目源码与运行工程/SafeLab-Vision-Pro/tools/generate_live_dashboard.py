from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.live_dashboard import write_live_dashboard


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the SafeLab live-style dashboard.")
    parser.add_argument("--events", default=str(ROOT / "data" / "events" / "events.jsonl"))
    parser.add_argument("--actions", default=str(ROOT / "data" / "events" / "alarm_actions.jsonl"))
    parser.add_argument("--actuator", default=str(ROOT / "data" / "events" / "actuator_log.jsonl"))
    parser.add_argument("--ai-explanations", default=str(ROOT / "data" / "events" / "ai_explanations.jsonl"))
    parser.add_argument("--health", default=str(ROOT / "reports" / "health_check.json"))
    parser.add_argument("--html", default=str(ROOT / "reports" / "live_dashboard.html"))
    parser.add_argument("--state", default=str(ROOT / "reports" / "live_dashboard_state.json"))
    args = parser.parse_args()

    output = write_live_dashboard(
        events_path=args.events,
        actions_path=args.actions,
        actuator_path=args.actuator,
        ai_explanations_path=args.ai_explanations,
        health_path=args.health,
        output_path=args.html,
        state_path=args.state,
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

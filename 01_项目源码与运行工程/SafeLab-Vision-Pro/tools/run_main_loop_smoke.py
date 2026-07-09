from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.main_loop import run_mock_main_loop


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the SafeLab runtime main loop with mock frames.")
    parser.add_argument("--frames", type=int, default=8)
    parser.add_argument("--events-dir", default=str(ROOT / "data" / "events"))
    parser.add_argument("--summary", default=str(ROOT / "reports" / "main_loop_summary.json"))
    args = parser.parse_args()

    result = run_mock_main_loop(args.frames, args.events_dir, args.summary)
    payload = result.to_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["events"] >= 2 and payload["watchdog_healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

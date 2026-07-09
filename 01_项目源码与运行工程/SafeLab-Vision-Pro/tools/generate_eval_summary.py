from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def generate_eval_summary(
    csv_path: str | Path = "reports/replay_event_report.csv",
    output_path: str | Path = "reports/eval_summary.json",
) -> dict[str, Any]:
    rows = _read_rows(csv_path)
    alarm_rows = [row for row in rows if row.get("should_alarm") == "True"]
    closed_rows = [row for row in rows if row.get("stage") == "closed"]
    suspicious_rows = [row for row in rows if row.get("stage") == "suspicious"]

    event_keys = sorted({row.get("event_key", "") for row in rows if row.get("event_key")})
    first_alarm_by_key: dict[str, dict[str, str]] = {}
    duplicate_alarm_count = 0
    for row in alarm_rows:
        key = row.get("event_key", "")
        if key in first_alarm_by_key:
            duplicate_alarm_count += 1
        else:
            first_alarm_by_key[key] = row

    summary = {
        "timeline_rows": len(rows),
        "event_keys": event_keys,
        "suspicious_count": len(suspicious_rows),
        "alarm_count": len(alarm_rows),
        "unique_alarm_count": len(first_alarm_by_key),
        "duplicate_alarm_count": duplicate_alarm_count,
        "closed_count": len(closed_rows),
        "first_alarm_frame": _first_int(alarm_rows, "frame_id"),
        "first_closed_frame": _first_int(closed_rows, "frame_id"),
        "alarm_event_keys": sorted(first_alarm_by_key),
    }

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate evaluation summary from replay CSV.")
    parser.add_argument("--csv", default="reports/replay_event_report.csv")
    parser.add_argument("--output", default="reports/eval_summary.json")
    args = parser.parse_args()

    summary = generate_eval_summary(args.csv, args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _first_int(rows: list[dict[str, str]], key: str) -> int | None:
    if not rows:
        return None
    return int(float(rows[0][key]))


if __name__ == "__main__":
    raise SystemExit(main())


from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.async_event_bus import AsyncEventBus


def benchmark_event_bus(
    event_count: int = 10,
    maxsize: int = 3,
    csv_path: str | Path = ROOT / "reports" / "event_bus_trace.csv",
    summary_path: str | Path = ROOT / "reports" / "event_bus_summary.json",
) -> dict[str, Any]:
    bus = AsyncEventBus(maxsize=maxsize)
    rows: list[dict[str, Any]] = []

    for index in range(1, event_count + 1):
        started = time.perf_counter()
        event = bus.publish("risk_event", {"event_id": f"E_BUS_{index:04d}", "risk_level": "high"})
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        stats = bus.stats()
        rows.append(
            {
                "step": index,
                "operation": "publish",
                "sequence": event.sequence,
                "pending_count": stats.pending_count,
                "dropped_count": stats.dropped_count,
                "elapsed_ms": round(elapsed_ms, 4),
            }
        )

    drained = bus.drain()
    for event in drained:
        stats = bus.stats()
        rows.append(
            {
                "step": event.sequence,
                "operation": "drain",
                "sequence": event.sequence,
                "pending_count": stats.pending_count,
                "dropped_count": stats.dropped_count,
                "elapsed_ms": 0.0,
            }
        )

    _write_csv(rows, csv_path)
    stats = bus.stats()
    summary = {
        "event_count": event_count,
        "maxsize": maxsize,
        "published_count": stats.published_count,
        "consumed_count": stats.consumed_count,
        "dropped_count": stats.dropped_count,
        "pending_count": stats.pending_count,
        "latest_only_protected": stats.dropped_count == max(event_count - maxsize, 0),
        "report_csv": str(csv_path),
    }
    output = Path(summary_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark latest-only async event bus behavior.")
    parser.add_argument("--events", type=int, default=10)
    parser.add_argument("--maxsize", type=int, default=3)
    parser.add_argument("--csv", default=str(ROOT / "reports" / "event_bus_trace.csv"))
    parser.add_argument("--summary", default=str(ROOT / "reports" / "event_bus_summary.json"))
    args = parser.parse_args()

    summary = benchmark_event_bus(args.events, args.maxsize, args.csv, args.summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _write_csv(rows: list[dict[str, Any]], csv_path: str | Path) -> Path:
    output = Path(csv_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["step", "operation", "sequence", "pending_count", "dropped_count", "elapsed_ms"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output


if __name__ == "__main__":
    raise SystemExit(main())

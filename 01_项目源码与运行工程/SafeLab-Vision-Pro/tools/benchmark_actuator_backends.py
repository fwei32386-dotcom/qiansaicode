from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actuator.backends import ActuatorPinConfig, create_actuator_backend
from runtime.interfaces import AlarmAction


def benchmark_actuator_backends(
    csv_path: str | Path = ROOT / "reports" / "actuator_backends_trace.csv",
    summary_path: str | Path = ROOT / "reports" / "actuator_backends_summary.json",
    log_path: str | Path = ROOT / "data" / "events" / "actuator_backend_check.jsonl",
) -> dict[str, Any]:
    action = AlarmAction(
        event_id="ACT_BACKEND_CHECK",
        voice_text="Safety alarm backend check.",
        led_color="red",
        buzzer=True,
        relay=False,
        snapshot=True,
        log=True,
        cooldown_ms=20000,
    )
    output_log = Path(log_path)
    if output_log.exists():
        output_log.unlink()

    rows: list[dict[str, Any]] = []
    for backend_name in ["mock", "shell", "gpio"]:
        backend = create_actuator_backend(
            backend_name,  # type: ignore[arg-type]
            output_log,
            ActuatorPinConfig(led_red=17, led_yellow=22, buzzer=18, relay=27),
        )
        record = backend.execute(action)
        rows.append(
            {
                "backend": record["backend"],
                "event_id": record["event_id"],
                "led_color": record["led"]["color"],
                "buzzer": record["buzzer"]["enabled"],
                "relay": record["relay"]["enabled"],
                "executed": record.get("executed", True),
                "detail": record.get("detail", "jsonl mock execution record"),
            }
        )

    _write_csv(rows, csv_path)
    summary = {
        "backend_count": len(rows),
        "backends": [row["backend"] for row in rows],
        "hardware_safe": all(row["backend"] == "mock" or row["executed"] is False for row in rows),
        "report_csv": str(csv_path),
        "actuator_log": str(output_log),
    }
    output = Path(summary_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate actuator backend contract evidence.")
    parser.add_argument("--csv", default=str(ROOT / "reports" / "actuator_backends_trace.csv"))
    parser.add_argument("--summary", default=str(ROOT / "reports" / "actuator_backends_summary.json"))
    parser.add_argument("--log", default=str(ROOT / "data" / "events" / "actuator_backend_check.jsonl"))
    args = parser.parse_args()

    summary = benchmark_actuator_backends(args.csv, args.summary, args.log)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["backend_count"] == 3 and summary["hardware_safe"] else 1


def _write_csv(rows: list[dict[str, Any]], csv_path: str | Path) -> Path:
    output = Path(csv_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["backend", "event_id", "led_color", "buzzer", "relay", "executed", "detail"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output


if __name__ == "__main__":
    raise SystemExit(main())

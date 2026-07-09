from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.fallback_manager import FallbackManager
from runtime.interfaces import HealthStatus
from runtime.watchdog import Watchdog


def generate_runtime_resilience_report(
    fallback_path: str | Path = ROOT / "reports" / "fallback_summary.json",
    watchdog_path: str | Path = ROOT / "reports" / "watchdog_summary.json",
    health_path: str | Path = ROOT / "reports" / "health_check.json",
) -> dict[str, str]:
    fallback_output = Path(fallback_path)
    watchdog_output = Path(watchdog_path)
    fallback_output.parent.mkdir(parents=True, exist_ok=True)
    watchdog_output.parent.mkdir(parents=True, exist_ok=True)

    health = _load_health(health_path)
    decision = FallbackManager().decide(health)
    fallback_output.write_text(
        json.dumps({"health": health.to_dict(), "decision": decision.to_dict()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    watchdog = Watchdog(timeout_ms=1000.0)
    watchdog.heartbeat("capture_worker", timestamp=10.0)
    watchdog.heartbeat("inference_worker", timestamp=9.7)
    watchdog.heartbeat("event_worker", timestamp=8.0)
    watchdog_summary = watchdog.summary(["capture_worker", "inference_worker", "event_worker"], now=10.2)
    watchdog_output.write_text(json.dumps(watchdog_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"fallback": str(fallback_output), "watchdog": str(watchdog_output)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate runtime fallback and watchdog evidence reports.")
    parser.add_argument("--fallback", default=str(ROOT / "reports" / "fallback_summary.json"))
    parser.add_argument("--watchdog", default=str(ROOT / "reports" / "watchdog_summary.json"))
    parser.add_argument("--health", default=str(ROOT / "reports" / "health_check.json"))
    args = parser.parse_args()

    outputs = generate_runtime_resilience_report(args.fallback, args.watchdog, args.health)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


def _load_health(path: str | Path) -> HealthStatus:
    payload: dict[str, object] = {}
    health_file = Path(path)
    if health_file.exists():
        payload = json.loads(health_file.read_text(encoding="utf-8"))
    return HealthStatus(
        camera=str(payload.get("camera", "present")),
        hdmi_capture=str(payload.get("hdmi_capture", "missing")),
        rknn_model=str(payload.get("rknn_model", "missing")),
        database=str(payload.get("database", "ok")),
        gpio=str(payload.get("gpio", "missing")),
        audio=str(payload.get("audio", "missing")),
        storage_free_mb=payload.get("storage_free_mb", 53895),  # type: ignore[arg-type]
        fallback_mode="shell_only+mock_detection",
        python=str(payload.get("python", "missing")),
        v4l2_ctl=str(payload.get("v4l2_ctl", "ok")),
        media_ctl=str(payload.get("media_ctl", "ok")),
        ov13855=str(payload.get("ov13855", "not_ready")),
        preferred_camera=str(payload.get("preferred_camera", payload.get("preferred_video21", "missing"))),
    )


if __name__ == "__main__":
    raise SystemExit(main())

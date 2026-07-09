from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]


def run_camera_live_preview_benchmark(
    status_url: str = "http://127.0.0.1:8090/status",
    duration_seconds: float = 8.0,
    sample_interval_seconds: float = 0.5,
    output_path: str | Path = ROOT / "reports" / "camera_live_preview_benchmark.json",
) -> dict[str, object]:
    samples: list[dict[str, object]] = []
    start = time.time()
    while time.time() - start < duration_seconds:
        sample_started = time.time()
        try:
            with urlopen(status_url, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            payload["sample_ok"] = True
        except Exception as exc:  # pragma: no cover - depends on local service availability
            payload = {
                "sample_ok": False,
                "last_error": str(exc),
                "frame_id": None,
                "estimated_fps": 0,
                "last_frame_age_seconds": None,
                "frame_bytes": 0,
                "stream_config": {},
            }
        payload["sample_time"] = round(time.time(), 3)
        samples.append(payload)
        elapsed = time.time() - sample_started
        time.sleep(max(sample_interval_seconds - elapsed, 0))

    ok_samples = [sample for sample in samples if sample.get("sample_ok")]
    fps_values = [float(sample.get("estimated_fps") or 0) for sample in ok_samples]
    age_values = [
        float(sample["last_frame_age_seconds"])
        for sample in ok_samples
        if sample.get("last_frame_age_seconds") is not None
    ]
    byte_values = [int(sample.get("frame_bytes") or 0) for sample in ok_samples]
    frame_ids = [int(sample["frame_id"]) for sample in ok_samples if sample.get("frame_id") is not None]
    config = ok_samples[-1].get("stream_config", {}) if ok_samples else {}
    target_fps = float(config.get("target_fps") or 0) if isinstance(config, dict) else 0
    average_fps = _avg(fps_values)
    max_age = max(age_values) if age_values else None

    summary = {
        "status_url": status_url,
        "duration_seconds": duration_seconds,
        "sample_interval_seconds": sample_interval_seconds,
        "sample_count": len(samples),
        "ok_sample_count": len(ok_samples),
        "stream_config": config,
        "target_fps": target_fps,
        "average_reported_fps": round(average_fps, 3),
        "min_reported_fps": round(min(fps_values), 3) if fps_values else 0,
        "max_reported_fps": round(max(fps_values), 3) if fps_values else 0,
        "average_frame_age_seconds": round(_avg(age_values), 3) if age_values else None,
        "max_frame_age_seconds": round(max_age, 3) if max_age is not None else None,
        "average_jpeg_kb": round(_avg(byte_values) / 1024, 2) if byte_values else 0,
        "frame_id_delta": (frame_ids[-1] - frame_ids[0]) if len(frame_ids) >= 2 else 0,
        "status": _status(ok_samples, average_fps, max_age, target_fps),
        "samples": samples,
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _avg(values: list[float] | list[int]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _status(ok_samples: list[dict[str, object]], average_fps: float, max_age: float | None, target_fps: float) -> str:
    if not ok_samples:
        return "unavailable"
    if any(sample.get("last_error") for sample in ok_samples):
        return "error"
    if max_age is not None and max_age > 2.0:
        return "stale"
    if target_fps and average_fps < target_fps * 0.75:
        return "below_target_fps"
    return "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the local SafeLab live camera preview status endpoint.")
    parser.add_argument("--status-url", default="http://127.0.0.1:8090/status")
    parser.add_argument("--duration", type=float, default=8.0)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--output", default=str(ROOT / "reports" / "camera_live_preview_benchmark.json"))
    args = parser.parse_args()

    summary = run_camera_live_preview_benchmark(
        status_url=args.status_url,
        duration_seconds=args.duration,
        sample_interval_seconds=args.interval,
        output_path=args.output,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

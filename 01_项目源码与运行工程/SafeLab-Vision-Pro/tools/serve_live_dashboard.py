from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.live_server import LiveDashboardConfig, LiveDashboardServer


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the SafeLab realtime dashboard over HTTP and SSE.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--events", default=str(ROOT / "data" / "events" / "events.jsonl"))
    parser.add_argument("--actions", default=str(ROOT / "data" / "events" / "alarm_actions.jsonl"))
    parser.add_argument("--actuator", default=str(ROOT / "data" / "events" / "actuator_log.jsonl"))
    parser.add_argument("--ai-explanations", default=str(ROOT / "data" / "events" / "ai_explanations.jsonl"))
    parser.add_argument("--deepseek-config", default=str(ROOT / "configs" / "deepseek_config.json"))
    parser.add_argument("--health", default=str(ROOT / "reports" / "health_check.json"))
    parser.add_argument("--video-config", default=str(ROOT / "configs" / "video_config.yaml"))
    parser.add_argument("--input-source", default=str(ROOT / "data" / "runtime" / "input_source.json"))
    parser.add_argument("--model-detection", default=str(ROOT / "data" / "runtime" / "model_detection.json"))
    parser.add_argument("--scene-mode", default=str(ROOT / "data" / "runtime" / "scene_mode.json"))
    parser.add_argument("--local-media-dir", default=str(ROOT / "data" / "runtime" / "local_media"))
    parser.add_argument("--max-items", type=int, default=20)
    parser.add_argument("--refresh-seconds", type=float, default=1.0)
    parser.add_argument("--once", action="store_true", help="Validate configuration and print one state snapshot without serving.")
    args = parser.parse_args()

    config = LiveDashboardConfig(
        events_path=Path(args.events),
        actions_path=Path(args.actions),
        actuator_path=Path(args.actuator),
        ai_explanations_path=Path(args.ai_explanations),
        deepseek_config_path=Path(args.deepseek_config),
        health_path=Path(args.health),
        video_config_path=Path(args.video_config),
        input_source_path=Path(args.input_source),
        model_detection_path=Path(args.model_detection),
        scene_mode_path=Path(args.scene_mode),
        local_media_dir=Path(args.local_media_dir),
        max_items=args.max_items,
        refresh_seconds=args.refresh_seconds,
    )
    if args.once:
        probe = LiveDashboardServer(("127.0.0.1", 0), config)
        try:
            print(json.dumps({"status": "ready", "state": probe.build_state()}, ensure_ascii=False, indent=2))
        finally:
            probe.server_close()
        return 0

    server = LiveDashboardServer((args.host, args.port), config)
    url = f"http://{args.host}:{server.server_port}/"
    print(json.dumps({"status": "serving", "url": url}, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        time.sleep(0.05)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

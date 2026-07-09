from __future__ import annotations

import json
import os
import posixpath
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import paramiko

from cloud.deepseek_client import explain_new_events_to_jsonl
from dashboard.input_source import save_input_source
from dashboard.live_dashboard import build_live_dashboard_state, resolve_detection_image_path
from dashboard.model_detection import save_model_detection
from dashboard.risk_voice_alarm import BoardSpeaker, RiskVoiceAnnouncer
from dashboard.scene_mode import save_scene_mode
from dashboard.voice_feedback import handle_voice_feedback, known_voice_commands


@dataclass(frozen=True)
class LiveDashboardConfig:
    events_path: Path = Path("data/events/events.jsonl")
    actions_path: Path = Path("data/events/alarm_actions.jsonl")
    actuator_path: Path = Path("data/events/actuator_log.jsonl")
    ai_explanations_path: Path = Path("data/events/ai_explanations.jsonl")
    voice_commands_path: Path = Path("data/events/voice_commands.jsonl")
    speech_output_path: Path = Path("data/events/speech_output.jsonl")
    xiaoduo_dialog_path: Path = Path("data/events/xiaoduo_dialog.jsonl")
    deepseek_config_path: Path = Path("configs/deepseek_config.json")
    detections_path: Path = Path("reports/live_pipeline/live_dual_model_work/detections_window.jsonl")
    bridge_summary_path: Path = Path("reports/live_pipeline/live_dual_model/bridge_summary.json")
    health_path: Path = Path("reports/health_check.json")
    video_config_path: Path = Path("configs/video_config.yaml")
    input_source_path: Path = Path("data/runtime/input_source.json")
    camera_snapshot_path: Path = Path("reports/board_camera_preview.jpg")
    model_detection_path: Path = Path("data/runtime/model_detection.json")
    scene_mode_path: Path = Path("data/runtime/scene_mode.json")
    xiaoduo_state_path: Path = Path("data/runtime/xiaoduo_state.json")
    local_media_dir: Path = Path("data/runtime/local_media")
    board_media_dir: Path = Path("data/runtime/board_media")
    board_host: str = os.getenv("SAFELAB_BOARD_HOST", "192.168.0.232")
    board_username: str = os.getenv("SAFELAB_BOARD_USER", "root")
    board_password: str = os.getenv("SAFELAB_BOARD_PASSWORD", "root")
    board_remote_video_path: str = "/root/safelab_media/current_demo.mp4"
    board_remote_image_path: str = "/root/safelab_media/current_demo.jpg"
    risk_voice_enabled: bool = True
    risk_voice_interval_seconds: float = 5.0
    risk_voice_same_violation_cooldown_seconds: float = 20.0
    risk_voice_active_ttl_seconds: float = 60.0
    max_items: int = 20
    refresh_seconds: float = 1.0


class LiveDashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], config: LiveDashboardConfig):
        self.config = config
        self.risk_voice_announcer = self._build_risk_voice_announcer(config)
        super().__init__(server_address, LiveDashboardRequestHandler)

    def build_state(self) -> dict[str, Any]:
        state = build_live_dashboard_state(
            events_path=self.config.events_path,
            actions_path=self.config.actions_path,
            actuator_path=self.config.actuator_path,
            ai_explanations_path=self.config.ai_explanations_path,
            voice_commands_path=self.config.voice_commands_path,
            speech_output_path=self.config.speech_output_path,
            xiaoduo_dialog_path=self.config.xiaoduo_dialog_path,
            xiaoduo_state_path=self.config.xiaoduo_state_path,
            detections_path=self.config.detections_path,
            health_path=self.config.health_path,
            video_config_path=self.config.video_config_path,
            input_source_path=self.config.input_source_path,
            model_detection_path=self.config.model_detection_path,
            scene_mode_path=self.config.scene_mode_path,
            bridge_summary_path=self.config.bridge_summary_path,
            max_items=self.config.max_items,
        )
        state["known_voice_commands"] = known_voice_commands()
        if self.risk_voice_announcer is not None:
            state["risk_voice_alarm"] = self.risk_voice_announcer.maybe_announce(state.get("latest_events", []))
        return state

    def _build_risk_voice_announcer(self, config: LiveDashboardConfig) -> RiskVoiceAnnouncer | None:
        if not config.risk_voice_enabled:
            return None
        speaker = BoardSpeaker(
            host=config.board_host,
            username=config.board_username,
            password=config.board_password,
            log_path=config.speech_output_path,
        )
        return RiskVoiceAnnouncer(
            speaker=speaker,
            interval_seconds=config.risk_voice_interval_seconds,
            same_violation_cooldown_seconds=config.risk_voice_same_violation_cooldown_seconds,
            active_ttl_seconds=config.risk_voice_active_ttl_seconds,
            async_mode=True,
        )


class LiveDashboardRequestHandler(BaseHTTPRequestHandler):
    server: LiveDashboardServer

    def handle(self) -> None:
        try:
            super().handle()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send_html()
            return
        if path == "/state.json":
            self._send_json(self.server.build_state())
            return
        if path == "/board_camera_preview.jpg":
            self._send_file(self.server.config.camera_snapshot_path, "image/jpeg")
            return
        if path == "/detection-image":
            self._send_detection_image()
            return
        if path == "/events":
            self._send_sse()
            return
        if path == "/healthz":
            self._send_json({"status": "ok"})
            return
        self.send_error(404, "not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/input-source":
            self._handle_input_source_update()
            return
        if path == "/model-detection":
            self._handle_model_detection_update()
            return
        if path == "/scene-mode":
            self._handle_scene_mode_update()
            return
        if path == "/voice-command":
            self._handle_voice_command()
            return
        if path == "/local-media":
            self._handle_local_media_upload()
            return
        if path == "/board-local-media":
            self._handle_board_local_media_upload()
            return
        if path == "/ai-followup":
            self._handle_ai_followup()
            return
        self.send_error(404, "not found")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json_status(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404, "not found")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_detection_image(self) -> None:
        try:
            query = parse_qs(urlparse(self.path).query)
            raw_path = query.get("path", [""])[0]
            if not raw_path:
                raise ValueError("missing detection image path")
            image_path = resolve_detection_image_path(raw_path)
        except ValueError as exc:
            self._send_json_status(400, {"error": str(exc)})
            return
        content_type = _content_type_for_image(image_path)
        self._send_file(image_path, content_type)

    def _handle_ai_followup(self) -> None:
        try:
            result = explain_new_events_to_jsonl(
                events_path=self.server.config.events_path,
                actions_path=self.server.config.actions_path,
                output_path=self.server.config.ai_explanations_path,
                config_path=self.server.config.deepseek_config_path,
                max_events=5,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._send_json_status(500, {"error": str(exc)})
            return
        self._send_json_status(200, {"ai_followup": result, "state": self.server.build_state()})

    def _handle_input_source_update(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw) if raw else {}
            selected_source = str(payload.get("selected_source", ""))
            state = save_input_source(
                selected_source,
                self.server.config.video_config_path,
                self.server.config.input_source_path,
            )
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json_status(400, {"error": str(exc)})
            return
        # Source changes are intentionally save-and-restart; the running stream is not hot-switched.
        self._send_json_status(200, {**state, "message": "saved; restart runtime to apply input source"})

    def _handle_model_detection_update(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw) if raw else {}
            interval_frames = payload.get("interval_frames", payload.get("interval_seconds", 75))
            state = save_model_detection(
                payload.get("enabled", True),
                interval_frames,
                self.server.config.model_detection_path,
            )
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json_status(400, {"error": str(exc)})
            return
        self._send_json_status(200, {**state, "message": "model detection updated"})

    def _handle_scene_mode_update(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw) if raw else {}
            state = save_scene_mode(payload.get("mode", "construction"), self.server.config.scene_mode_path)
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json_status(400, {"error": str(exc)})
            return
        self._send_json_status(200, {**state, "message": "scene mode updated"})

    def _handle_voice_command(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw) if raw else {}
            result = handle_voice_feedback(
                payload.get("raw_text", payload.get("token", "")),
                source=str(payload.get("source", "web_simulated_serial")),
                speak=bool(payload.get("speak", False)),
                voice_commands_path=self.server.config.voice_commands_path,
                speech_output_path=self.server.config.speech_output_path,
                xiaoduo_dialog_path=self.server.config.xiaoduo_dialog_path,
                xiaoduo_state_path=self.server.config.xiaoduo_state_path,
                model_detection_path=self.server.config.model_detection_path,
                scene_mode_path=self.server.config.scene_mode_path,
                ai_explanations_path=self.server.config.ai_explanations_path,
                actions_path=self.server.config.actions_path,
                detections_path=self.server.config.detections_path,
            )
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            self._send_json_status(400, {"error": str(exc)})
            return
        self._send_json_status(200, {"voice_feedback": result, "state": self.server.build_state()})

    def _handle_local_media_upload(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                raise ValueError("local media upload is empty")
            filename = parse_qs(urlparse(self.path).query).get("filename", ["local_media.mp4"])[0]
            target = self.server.config.local_media_dir / _safe_media_filename(filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.rfile.read(length))
            state = save_input_source(
                "file_demo",
                self.server.config.video_config_path,
                self.server.config.input_source_path,
                source_overrides={"path": str(target)},
            )
        except (ValueError, OSError) as exc:
            self._send_json_status(400, {"error": str(exc)})
            return
        self._send_json_status(200, {**state, "file_path": str(target), "message": "local media uploaded"})

    def _handle_board_local_media_upload(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                raise ValueError("board local media upload is empty")
            filename = parse_qs(urlparse(self.path).query).get("filename", ["board_media.mp4"])[0]
            media_type = _media_type_for_filename(filename)
            target = self.server.config.board_media_dir / _safe_media_filename(filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.rfile.read(length))
            local_upload = _normalize_board_media(target, media_type)
            dimensions = _probe_image_dimensions(local_upload) if media_type == "image" else _probe_video_dimensions(local_upload)
            remote_path = (
                self.server.config.board_remote_image_path
                if media_type == "image"
                else self.server.config.board_remote_video_path
            )
            upload_summary = upload_file_to_board(
                local_path=local_upload,
                host=self.server.config.board_host,
                username=self.server.config.board_username,
                password=self.server.config.board_password,
                remote_path=remote_path,
            )
            overrides = {
                "path": str(local_upload),
                "board_path": str(upload_summary["remote_path"]),
                "media_type": media_type,
            }
            if dimensions:
                overrides.update({"width": str(dimensions[0]), "height": str(dimensions[1])})
            state = save_input_source(
                "board_file_demo",
                self.server.config.video_config_path,
                self.server.config.input_source_path,
                source_overrides=overrides,
            )
        except (ValueError, OSError, RuntimeError, paramiko.SSHException) as exc:
            self._send_json_status(400, {"error": str(exc)})
            return
        self._send_json_status(
            200,
            {
                **state,
                "file_path": str(local_upload),
                "board_path": str(upload_summary["remote_path"]),
                "media_type": media_type,
                "message": "board local media uploaded",
            },
        )

    def _send_html(self) -> None:
        body = _render_server_html().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        for _ in range(3):
            payload = json.dumps(self.server.build_state(), ensure_ascii=False)
            try:
                self.wfile.write(f"event: state\ndata: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return
            time.sleep(self.server.config.refresh_seconds)


def _safe_media_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".avi", ".jpeg", ".jpg", ".mkv", ".mov", ".mp4", ".png", ".webm"}:
        suffix = ".mp4"
    stem = Path(filename).stem or "local_media"
    safe_stem = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in stem)[:48]
    return f"current_{safe_stem or 'local_media'}{suffix}"


def _media_type_for_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".jpeg", ".jpg", ".png"}:
        return "image"
    if suffix in {".avi", ".mkv", ".mov", ".mp4", ".webm"}:
        return "video"
    raise ValueError(f"unsupported local media type: {suffix or filename}")


def _normalize_board_media(path: Path, media_type: str) -> Path:
    if media_type != "image":
        return path
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        return path
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("OpenCV is required to convert uploaded images for board detection") from exc
    image = cv2.imdecode(np.frombuffer(path.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("uploaded image cannot be decoded")
    output = path.with_suffix(".jpg")
    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        raise RuntimeError("uploaded image cannot be encoded as JPEG")
    output.write_bytes(encoded.tobytes())
    return output


def _content_type_for_image(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".bmp":
        return "image/bmp"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"


def upload_file_to_board(
    *,
    local_path: str | Path,
    host: str,
    username: str,
    password: str,
    remote_path: str,
) -> dict[str, str]:
    local = Path(local_path)
    if not local.exists():
        raise RuntimeError(f"local media does not exist: {local}")
    remote_dir = posixpath.dirname(remote_path) or "/root"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            username=username,
            password=password,
            timeout=10,
            banner_timeout=10,
            auth_timeout=10,
            look_for_keys=False,
            allow_agent=False,
        )
        _, stdout, stderr = client.exec_command(f"mkdir -p {remote_dir}", timeout=20)
        mkdir_error = stderr.read().decode("utf-8", errors="replace").strip()
        mkdir_code = stdout.channel.recv_exit_status()
        if mkdir_code != 0:
            raise RuntimeError(f"failed to create board media dir: {mkdir_error}")
        sftp = client.open_sftp()
        try:
            sftp.put(str(local), remote_path)
        finally:
            sftp.close()
    finally:
        client.close()
    return {"remote_path": remote_path}


def _probe_video_dimensions(path: str | Path) -> tuple[int, int] | None:
    try:
        import cv2  # type: ignore[import-not-found]

        capture = cv2.VideoCapture(str(path))
        try:
            if not capture.isOpened():
                return None
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            if width > 0 and height > 0:
                return width, height
            return None
        finally:
            capture.release()
    except Exception:
        return None


def _probe_image_dimensions(path: str | Path) -> tuple[int, int] | None:
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]

        image = cv2.imdecode(np.frombuffer(Path(path).read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return None
        height, width = image.shape[:2]
        return int(width), int(height)
    except Exception:
        return None


def run_live_dashboard_server(host: str, port: int, config: LiveDashboardConfig) -> LiveDashboardServer:
    server = LiveDashboardServer((host, port), config)
    thread = threading.Thread(target=server.serve_forever, name="safelab-live-dashboard", daemon=True)
    thread.start()
    return server


def _render_server_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SafeLab-Vision Pro 视觉风险认知中枢 | 实时演示看板</title>
  <style>
    * { box-sizing: border-box; }
    :root {
      --bg: #f5f7fb;
      --rail: #ffffff;
      --panel: #ffffff;
      --panel-2: #1b140d;
      --panel-strong: #f8fbff;
      --line: #d8e0ea;
      --muted: #64748b;
      --text: #172033;
      --gold: #d99a19;
      --cyan: #2563eb;
      --green: #0f9f6e;
      --red: #dc2626;
    }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      background: #f5f7fb;
      font-family: "Segoe UI", Tahoma, sans-serif;
      letter-spacing: 0;
      overflow-x: hidden;
    }
    button { font: inherit; }
    .shell {
      display: grid;
      grid-template-columns: 224px 1fr;
      min-height: 100vh;
      transition: grid-template-columns .18s ease;
    }
    .shell.rail-collapsed { grid-template-columns: 68px 1fr; }
    .rail {
      background: var(--rail);
      border-right: 1px solid var(--line);
      padding: 14px 10px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      box-shadow: 8px 0 24px rgba(15,23,42,.05);
    }
    .brand {
      min-height: 44px;
      display: grid;
      grid-template-columns: 34px 1fr 30px;
      gap: 8px;
      align-items: center;
    }
    .brand-mark, .nav-icon {
      width: 34px;
      height: 34px;
      border-radius: 7px;
      display: grid;
      place-items: center;
      background: #eef4ff;
      color: var(--cyan);
      font-weight: 700;
    }
    .brand-title { min-width: 0; }
    .brand-title strong { display: block; font-size: 14px; }
    .brand-title span { color: var(--muted); font-size: 11px; }
    .rail-toggle {
      width: 30px;
      height: 30px;
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--text);
      background: #f8fafc;
      cursor: pointer;
    }
    .nav { display: grid; gap: 6px; }
    .nav-item {
      min-height: 42px;
      border: 0;
      border-radius: 7px;
      color: var(--text);
      background: transparent;
      display: grid;
      grid-template-columns: 34px 1fr;
      gap: 10px;
      align-items: center;
      text-align: left;
      cursor: pointer;
    }
    .nav-item.active { background: #eaf2ff; color: #0f3f8f; }
    .nav-item.active .nav-icon { background: var(--cyan); color: #fff; }
    .nav-label { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .shell.rail-collapsed .brand-title,
    .shell.rail-collapsed .nav-label { display: none; }
    .shell.rail-collapsed .brand { grid-template-columns: 34px; justify-content: center; }
    .shell.rail-collapsed .rail-toggle { margin-left: 2px; }
    .content { padding: 18px; min-width: 0; }
    .topbar {
      min-height: 64px;
      display: flex;
      gap: 14px;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }
    h1 { margin: 0; font-size: 28px; line-height: 1.05; }
    .subtitle { margin-top: 5px; color: var(--muted); font-size: 13px; }
    .top-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
    .product-kicker { color: var(--green); font-size: 12px; font-weight: 700; margin-bottom: 6px; }
    .ops-strip { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 14px; }
    .ops-chip {
      min-height: 30px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 10px;
      border: 1px solid #c7d7fe;
      border-radius: 7px;
      color: #1e3a8a;
      background: #eff6ff;
      font-size: 12px;
      font-weight: 700;
    }
    .ops-chip.ready { border-color: #bbf7d0; background: #f0fdf4; color: #166534; }
    .ops-chip.critical { border-color: #fed7aa; background: #fff7ed; color: #9a3412; }
    .segmented {
      display: inline-grid;
      grid-template-columns: repeat(2, minmax(84px, 1fr));
      gap: 4px;
      padding: 4px;
      background: #eef2f7;
      border: 1px solid var(--line);
      border-radius: 7px;
    }
    .source-button {
      min-height: 34px;
      border: 0;
      border-radius: 5px;
      color: var(--muted);
      background: transparent;
      cursor: pointer;
    }
    .source-button.active { background: var(--cyan); color: #fff; font-weight: 700; }
    .model-control {
      min-height: 34px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 8px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fff;
      color: var(--muted);
      font-size: 12px;
    }
    .model-control input[type="number"] { width: 52px; border: 1px solid var(--line); border-radius: 5px; padding: 3px 5px; }
    .pill {
      min-height: 32px;
      display: inline-flex;
      align-items: center;
      padding: 5px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      background: #fff;
      font-size: 12px;
    }
    .workspace {
      display: block;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-width: 0;
      box-shadow: 0 18px 40px rgba(15,23,42,.08);
    }
    .view { display: none; }
    .view.active-view { display: block; }
    .panel h2 { margin: 0 0 10px; font-size: 15px; }
    .video-stage {
      aspect-ratio: 16 / 9;
      min-height: 250px;
      min-width: 0;
      max-width: 100%;
      border: 1px solid #3d5063;
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(85,199,255,.12), transparent 28%),
        repeating-linear-gradient(0deg, #07090b 0, #07090b 14px, #0c1014 15px);
      display: grid;
      place-items: center;
      color: #6f7e8e;
      font-weight: 700;
      overflow: hidden;
      position: relative;
    }
    .video-stage::after {
      content: "视频画面 / 风险叠加 / 告警框";
      position: absolute;
      left: 12px;
      bottom: 10px;
      padding: 5px 9px;
      border-radius: 999px;
      background: rgba(7,9,11,.72);
      color: #dce6ea;
      font-size: 12px;
      font-weight: 600;
    }
    .video-stage img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }
    .detection-overlay { position: absolute; inset: 0; pointer-events: none; z-index: 3; }
    .detection-box { position: absolute; border: 2px solid #38bdf8; border-radius: 4px; box-shadow: 0 0 0 1px rgba(8,13,19,.5), 0 10px 24px rgba(15,23,42,.2); }
    .detection-box.fire, .detection-box.smoke { border-color: #ef4444; }
    .detection-box.helmet, .detection-box.vest, .detection-box.goggles, .detection-box.gloves { border-color: #22c55e; }
    .detection-label { position: absolute; left: 0; top: -24px; max-width: 180px; padding: 3px 6px; border-radius: 4px; background: rgba(8,13,19,.82); color: #fff; font-size: 12px; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .detection-thumb { position: relative; width: min(260px, 100%); aspect-ratio: 16 / 9; margin: 8px 0; overflow: hidden; border: 1px solid var(--line); border-radius: 7px; background: #0f172a; }
    .detection-thumb img { width: 100%; height: 100%; object-fit: contain; display: block; }
    .detection-thumb .detection-overlay { z-index: 2; }
    .video-placeholder {
      position: absolute;
      color: #dce6ea;
      font-weight: 700;
      z-index: 1;
    }
    .stage-hud { position: absolute; top: 12px; right: 12px; display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
    .stage-hud span { padding: 5px 8px; border-radius: 6px; background: rgba(8,13,19,.76); border: 1px solid rgba(238,245,248,.16); color: #dcefff; font-size: 12px; }
    .metrics {
      display: grid;
      grid-template-columns: repeat(5, minmax(90px, 1fr));
      gap: 8px;
      margin-top: 10px;
    }
    .metric {
      min-height: 62px;
      background: #f8fafc;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 9px;
      color: var(--muted);
      font-size: 12px;
    }
    .metric strong { display: block; margin-top: 4px; color: var(--text); font-size: 22px; }
    .ai-panel { background: #fffaf0; border-color: #f3d7a5; }
    .panel-heading {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .action-button {
      border: 1px solid #b7d5ff;
      background: #eff6ff;
      color: #1d4ed8;
      border-radius: 7px;
      padding: 8px 12px;
      font-weight: 700;
      cursor: pointer;
      white-space: nowrap;
    }
    .action-button:disabled {
      cursor: wait;
      opacity: .62;
    }
    .ai-latest {
      min-height: 148px;
      border-left: 3px solid var(--gold);
      padding: 10px 12px;
      background: rgba(214,180,91,.08);
      border-radius: 6px;
    }
    .ai-latest strong { color: var(--gold); }
    .muted { color: var(--muted); font-size: 13px; }
    .notice { color: var(--green); min-height: 18px; font-size: 12px; }
    .danger { color: var(--red); }
    .list { display: grid; gap: 8px; }
    .row {
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 9px;
      background: #f8fafc;
      font-size: 13px;
    }
    .row .meta { color: var(--muted); font-size: 12px; margin-bottom: 4px; }
    .reason-lines { display: grid; gap: 5px; line-height: 1.55; }
    .reason-title { font-weight: 700; color: var(--text); }
    .reason-line strong { color: var(--muted); margin-right: 4px; }
    .level-high, .level-emergency { color: var(--red); font-weight: 700; }
    .level-warning { color: var(--gold); font-weight: 700; }
    .section-note { color: var(--muted); font-size: 12px; margin-top: -5px; margin-bottom: 10px; }
    #panel-local-media .section-note, #runtime { display: none; }
    .evidence-dock { display: grid; grid-template-columns: repeat(3, minmax(90px, 1fr)); gap: 8px; margin-top: 10px; }
    .evidence-dock div { border: 1px solid var(--line); border-radius: 7px; padding: 8px; background: #f8fafc; color: var(--muted); font-size: 12px; }
    .evidence-dock strong { display: block; color: var(--text); margin-bottom: 3px; }
    .local-media-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 14px; align-items: start; }
    .local-input-column, .local-result-column { min-width: 0; }
    .local-preview-stage, .local-result-stage { position: relative; width: 100%; aspect-ratio: 16 / 9; border: 1px solid var(--line); border-radius: 8px; background: #0f172a; overflow: hidden; }
    .local-result-stage { display: grid; place-items: center; }
    .local-media-preview { width: 100%; height: 100%; border: 0; background: #0f172a; display: block; object-fit: contain; }
    .file-picker { display: grid; gap: 10px; padding: 12px; border: 1px dashed #94a3b8; border-radius: 8px; background: #f8fafc; }
    .action-button {
      min-height: 34px;
      border: 1px solid #c7d7fe;
      border-radius: 7px;
      color: #1e3a8a;
      background: #eff6ff;
      cursor: pointer;
      font-weight: 700;
    }
    .action-button:hover { background: #dbeafe; }
    .side-stack { display: grid; gap: 14px; }
    @media (max-width: 980px) {
      .shell, .shell.rail-collapsed { grid-template-columns: 1fr; }
      .rail { position: sticky; top: 0; z-index: 2; flex-direction: row; overflow-x: auto; max-width: 100vw; }
      .brand { min-width: 180px; }
      .nav { display: flex; flex: 0 0 auto; }
      .nav-item { min-width: 46px; }
      .workspace { grid-template-columns: 1fr; }
      .local-media-grid { grid-template-columns: 1fr; }
      .metrics { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
      .shell.rail-collapsed .brand-title,
      .shell.rail-collapsed .nav-label { display: block; }
    }
    @media (max-width: 520px) {
      .rail { flex-direction: column; gap: 8px; overflow-x: hidden; }
      .brand { min-width: 0; width: 100%; }
      .nav { width: 100%; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); }
      .nav-item { min-width: 0; grid-template-columns: 1fr; justify-items: center; }
      .nav-label { display: none !important; }
      .content { padding: 14px; }
      .topbar { align-items: flex-start; flex-direction: column; }
      .top-actions { justify-content: flex-start; width: 100%; }
      .segmented { width: 100%; grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .source-button { min-width: 0; white-space: normal; line-height: 1.25; }
      .panel { padding: 12px; }
      .video-stage { min-height: 180px; aspect-ratio: 16 / 10; }
      .stage-hud { left: 10px; right: 10px; justify-content: flex-start; }
      .stage-hud span { max-width: 100%; overflow: hidden; text-overflow: ellipsis; }
      .evidence-dock { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell" id="shell">
    <aside class="rail">
      <div class="brand">
        <div class="brand-mark">S</div>
        <div class="brand-title"><strong>SafeLab-Vision Pro</strong><span>智能证据链</span></div>
        <button class="rail-toggle" id="rail-toggle" title="折叠菜单" type="button">&lt;</button>
      </div>
      <nav class="nav" aria-label="SafeLab 功能区">
        <button class="nav-item active" data-panel-target="panel-live" type="button"><span class="nav-icon">实</span><span class="nav-label">实时</span></button>
        <button class="nav-item" data-panel-target="panel-ai" type="button"><span class="nav-icon">智</span><span class="nav-label">智能说明</span></button>
        <button class="nav-item" data-panel-target="panel-events" type="button"><span class="nav-icon">警</span><span class="nav-label">事件</span></button>
        <button class="nav-item" data-panel-target="panel-detections" type="button"><span class="nav-icon">检</span><span class="nav-label">检测记录</span></button>
        <button class="nav-item" data-panel-target="panel-evidence" type="button"><span class="nav-icon">证</span><span class="nav-label">证据</span></button>
        <button class="nav-item" data-panel-target="panel-reports" type="button"><span class="nav-icon">报</span><span class="nav-label">报告</span></button>
        <button class="nav-item" data-panel-target="panel-local-media" type="button"><span class="nav-icon">片</span><span class="nav-label">本地媒体</span></button>
      </nav>
    </aside>
    <main class="content">
      <header class="topbar">
        <div>
          <div class="product-kicker">RK3588 NPU · 低延迟模式 · 最新帧优先</div>
          <h1>SafeLab-Vision Pro</h1>
          <div class="subtitle">视觉风险认知中枢 · 摄像头输入、本地输入、检测结果与警报闭环。</div>
        </div>
        <div class="top-actions">
          <div class="segmented" id="source-selector" aria-label="输入源">
            <button class="source-button" data-source-id="camera_ov13855" type="button">摄像头输入</button>
            <button class="source-button" data-source-id="board_file_demo" type="button">本地视频</button>
          </div>
          <div class="segmented" id="scene-selector" aria-label="场景模式">
            <button class="source-button" data-scene-mode="construction" type="button">工地</button>
            <button class="source-button" data-scene-mode="lab" type="button">实验室</button>
          </div>
          <label class="model-control"><input id="model-detection-toggle" type="checkbox" checked>开启模型检测</label>
          <label class="model-control">检测间隔 <input id="model-detection-interval" type="number" min="1" max="900" step="5" value="75"> 帧</label>
          <span class="pill" id="scene-pill">场景：加载中</span>
          <span class="pill" id="risk-pill">风险：加载中</span>
          <span class="pill" id="updated">正在连接</span>
        </div>
      </header>
      <div class="ops-strip" id="panel-settings" aria-label="系统能力">
        <span class="ops-chip ready">RK3588 NPU</span>
        <span class="ops-chip ready">低延迟模式</span>
        <span class="ops-chip">摄像头输入</span>
        <span class="ops-chip">本地输入</span>
        <span class="ops-chip" id="scene-requirements">场景检查项：加载中</span>
        <span class="ops-chip critical">最新帧优先</span>
      </div>
      <div class="notice" id="source-message"></div>
      <div class="workspace">
        <section class="panel view active-view" id="panel-live" data-view="panel-live">
          <h2>实时视频与检测框</h2>
          <div class="section-note">视觉输入、目标框、危险区域与规则结果同屏叠加。</div>
          <div class="video-stage" id="video-stage">
            <img id="camera-preview" src="http://127.0.0.1:8090/stream.mjpg" alt="板端 OV13855 摄像头画面">
            <div class="detection-overlay" id="detection-overlay"></div>
            <span class="video-placeholder" id="video-fallback" style="display:none">等待板端摄像头预览图</span>
            <div class="stage-hud"><span>摄像头输入</span><span>风险叠加</span><span>危险区域</span></div>
          </div>
          <div class="metrics" id="metrics"></div>
          <div class="evidence-dock" aria-label="证据链">
            <div><strong>证据链</strong>事件、动作、执行器联动</div>
            <div><strong>事件生命线</strong>从可疑到闭环</div>
            <div><strong>端侧闭环</strong>检测、警报、记录</div>
          </div>
        </section>
        <div class="side-stack">
          <section class="panel view ai-panel" id="panel-ai" data-view="panel-ai">
            <div class="panel-heading">
              <h2>智能说明 / 风险判定</h2>
              <button class="action-button" id="ai-followup-button" type="button">生成智能说明</button>
            </div>
            <div class="section-note">AI 摘要与现场处置建议。</div>
            <div id="ai"></div>
          </section>
          <section class="panel view" id="panel-events" data-view="panel-events">
            <h2>事件生命线</h2>
            <div class="section-note">风险时间线</div>
            <div id="events"></div>
          </section>
          <section class="panel view" id="panel-detections" data-view="panel-detections">
            <h2>检测记录</h2>
            <div class="section-note">模型原始检测流水</div>
            <div id="detections"></div>
          </section>
          <section class="panel view" id="panel-evidence" data-view="panel-evidence">
            <h2>证据链</h2>
            <div class="section-note">告警证据链</div>
            <div id="actions"></div>
          </section>
          <section class="panel view" id="panel-reports" data-view="panel-reports">
            <h2>执行器记录</h2>
            <div id="actuator"></div>
          </section>
          <section class="panel view" id="panel-local-media" data-view="panel-local-media">
            <h2>本地视频检测</h2>
            <div class="section-note">本地视频和本地图片放在同一个入口；选择后自动上传板卡并启动双模型检测。</div>
            <div class="local-media-grid">
              <div class="local-input-column">
                <div class="file-picker">
                  <label for="local-media-file"><strong>选择本地视频或图片并上传到板卡</strong></label>
                  <input id="local-media-file" type="file" accept="video/*,image/*">
                  <div class="muted" id="local-media-name">尚未选择媒体文件</div>
                </div>
                <div class="local-preview-stage">
                  <video id="local-video-preview" class="local-media-preview" controls muted playsinline></video>
                  <img id="local-image-preview" class="local-media-preview" alt="本地图片预览" style="display:none">
                </div>
              </div>
              <div class="local-result-column">
                <div class="local-result-stage" id="local-result-stage">
                  <img id="local-detection-frame-preview" class="local-media-preview" alt="识别结果图" style="display:none">
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
      <div id="runtime" class="muted" style="margin-top:12px"></div>
    </main>
  </div>
  <script>
    const AI_FOLLOWUP_INTERVAL_MS = 30000;
    const shell = document.getElementById("shell");
    const railToggle = document.getElementById("rail-toggle");
    railToggle.addEventListener("click", () => {
      shell.classList.toggle("rail-collapsed");
      railToggle.textContent = shell.classList.contains("rail-collapsed") ? ">" : "<";
    });
    let latestDashboardState = null;
    let aiFollowupInFlight = false;
    let lastAiFollowupAt = 0;
    setupDashboardInteractions();
    setupLocalOverlayRedraw();
    function text(value) { return value === undefined || value === null ? "" : String(value); }
    function esc(value) {
      return text(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}[c]));
    }
    function render(state) {
      latestDashboardState = state;
      document.getElementById("updated").textContent = "最近刷新 " + new Date().toLocaleTimeString();
      const status = state.status || {};
      const counts = state.counts || {};
      document.getElementById("risk-pill").textContent = "风险：" + statusText(status.risk_state || "idle");
      document.getElementById("risk-pill").className = "pill " + esc(status.risk_state || "idle");
      document.getElementById("runtime").textContent =
        `运行 ${statusText(status.fallback_mode)} | 摄像头 ${statusText(status.camera)} | OV13855 ${statusText(status.ov13855)} | Python ${statusText(status.python)}`;
      renderSourceButtons(state.input_source || {});
      renderModelDetection(state.model_detection || {});
      renderSceneMode(state.scene_mode || {});
      refreshCameraPreview();
      renderDetectionOverlay(state.latest_detections || [], state.input_source || {});
      document.getElementById("metrics").innerHTML = [
        ["事件", counts.events || 0],
        ["检测", counts.detections || 0],
        ["动作", counts.actions || 0],
        ["执行记录", counts.actuator_records || 0],
        ["智能说明", counts.ai_explanations || 0],
        ["高风险", counts.high_risk_events || 0],
      ].map(([k, v]) => `<div class="metric">${esc(k)}<strong>${esc(v)}</strong></div>`).join("");
      document.getElementById("events").innerHTML = eventList(state.latest_events || []);
      document.getElementById("detections").innerHTML = detectionList(state.latest_detections || []);
      document.getElementById("ai").innerHTML = aiPanel(state.latest_ai_explanations || []);
      document.getElementById("actions").innerHTML = actionList(state.latest_actions || []);
      document.getElementById("actuator").innerHTML = actuatorList(state.latest_actuator_records || []);
      requestAnimationFrame(syncDetectionThumbs);
      maybeRequestAiFollowup(state);
    }
    function renderSourceButtons(source) {
      document.querySelectorAll("[data-source-id]").forEach(button => {
        button.classList.toggle("active", button.dataset.sourceId === source.selected_source);
      });
    }
    function sourcePanelForSource(sourceId) {
      return sourceId === "file_demo" || sourceId === "board_file_demo" ? "panel-local-media" : "panel-live";
    }
    function sourceForPanel(panelId) {
      if (panelId === "panel-local-media") {
        return "board_file_demo";
      }
      return "camera_ov13855";
    }
    function currentPanelId() {
      const active = document.querySelector("[data-view].active-view");
      return active ? active.dataset.view : "panel-live";
    }
    function syncSourceButtonsForPanel(panelId) {
      renderSourceButtons({ selected_source: sourceForPanel(panelId) });
    }
    function renderModelDetection(modelDetection) {
      const toggle = document.getElementById("model-detection-toggle");
      const interval = document.getElementById("model-detection-interval");
      if (!toggle || !interval) return;
      toggle.checked = modelDetection.enabled !== false;
      interval.value = String(Math.round(Number(modelDetection.interval_frames || 75)));
    }
    function renderSceneMode(sceneMode) {
      const mode = sceneMode.mode || "construction";
      document.querySelectorAll("[data-scene-mode]").forEach(button => {
        button.classList.toggle("active", button.dataset.sceneMode === mode);
      });
      const label = sceneMode.label || (mode === "lab" ? "实验室" : "工地");
      const requirements = sceneMode.required_ppe_labels || [];
      const requirementText = requirements.length ? requirements.join(" / ") : "未配置";
      const scenePill = document.getElementById("scene-pill");
      const sceneRequirements = document.getElementById("scene-requirements");
      if (scenePill) scenePill.textContent = `场景：${label}`;
      if (sceneRequirements) sceneRequirements.textContent = `场景检查项：${requirementText}`;
    }
    function statusText(value) {
      const raw = text(value);
      const lower = raw.toLowerCase();
      const labels = { alarm: "告警", watching: "观察中", idle: "空闲", high: "高风险", emergency: "紧急", warning: "预警", present: "已连接", ok: "正常", not_ready: "未就绪", missing: "缺失", unknown: "未知", "shell_only+mock_detection": "模拟检测", shell_only: "仅外壳运行" };
      return labels[lower] || raw;
    }
    function setupDashboardInteractions() {
      document.querySelectorAll("[data-panel-target]").forEach(button => {
        button.addEventListener("click", () => activatePanel(button.dataset.panelTarget));
      });
      const localMediaInput = document.getElementById("local-media-file");
      if (localMediaInput) localMediaInput.addEventListener("change", event => {
        previewLocalMedia(event);
        const file = event.target.files && event.target.files[0];
        if (file) uploadBoardLocalMedia(file);
      });
      const modelToggle = document.getElementById("model-detection-toggle");
      const modelInterval = document.getElementById("model-detection-interval");
      if (modelToggle) modelToggle.addEventListener("change", saveModelDetection);
      if (modelInterval) modelInterval.addEventListener("change", saveModelDetection);
      const aiFollowupButton = document.getElementById("ai-followup-button");
      if (aiFollowupButton) aiFollowupButton.addEventListener("click", requestAiFollowup);
      document.getElementById("source-selector").addEventListener("click", async event => {
        const button = event.target.closest("button[data-source-id]");
        if (!button) return;
        activatePanel(sourcePanelForSource(button.dataset.sourceId));
        await saveSource(button.dataset.sourceId);
      });
      document.getElementById("scene-selector").addEventListener("click", async event => {
        const button = event.target.closest("button[data-scene-mode]");
        if (!button) return;
        await saveSceneMode(button.dataset.sceneMode);
      });
    }
    function activatePanel(panelId) {
      if (!showView(panelId)) return;
      document.querySelectorAll("[data-panel-target]").forEach(button => {
        button.classList.toggle("active", button.dataset.panelTarget === panelId);
      });
      const target = document.getElementById(panelId);
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      if (panelId === "panel-ai") maybeRequestAiFollowup(latestDashboardState);
    }
    function showView(panelId) {
      const target = document.getElementById(panelId);
      if (!target) return false;
      document.querySelectorAll("[data-view]").forEach(panel => {
        panel.classList.toggle("active-view", panel.dataset.view === panelId);
      });
      return true;
    }
    function previewLocalMedia(event) {
      const file = event.target.files && event.target.files[0];
      const video = document.getElementById("local-video-preview");
      const image = document.getElementById("local-image-preview");
      const detectionFrame = document.getElementById("local-detection-frame-preview");
      const name = document.getElementById("local-media-name");
      if (!file || !video || !image) return;
      if (detectionFrame) {
        detectionFrame.removeAttribute("src");
        detectionFrame.style.display = "none";
      }
      const resultStage = document.getElementById("local-result-stage");
      if (resultStage) resultStage.classList.remove("has-result");
      const previewUrl = URL.createObjectURL(file);
      if (file.type.startsWith("image/")) {
        video.removeAttribute("src");
        video.style.display = "none";
        image.src = previewUrl;
        image.style.display = "block";
        redrawLocalDetectionOverlay();
      } else {
        image.removeAttribute("src");
        image.style.display = "none";
        video.src = previewUrl;
        video.style.display = "block";
        video.load();
        redrawLocalDetectionOverlay();
      }
      if (name) name.textContent = "已选择：" + file.name;
    }
    function setupLocalOverlayRedraw() {
      const video = document.getElementById("local-video-preview");
      const image = document.getElementById("local-image-preview");
      const detectionFrame = document.getElementById("local-detection-frame-preview");
      if (video) {
        video.addEventListener("loadedmetadata", redrawLocalDetectionOverlay);
        video.addEventListener("play", redrawLocalDetectionOverlay);
        video.addEventListener("seeked", redrawLocalDetectionOverlay);
        video.addEventListener("timeupdate", redrawLocalDetectionOverlay);
      }
      if (image) image.addEventListener("load", redrawLocalDetectionOverlay);
      if (detectionFrame) detectionFrame.addEventListener("load", redrawLocalDetectionOverlay);
      window.addEventListener("resize", redrawLocalDetectionOverlay);
    }
    function redrawLocalDetectionOverlay() {
      if (!latestDashboardState) return;
      requestAnimationFrame(() => renderDetectionOverlay(
        latestDashboardState.latest_detections || [],
        latestDashboardState.input_source || {}
      ));
    }
    async function uploadLocalMedia(file) {
      const message = document.getElementById("source-message");
      if (message) {
        message.textContent = "正在上传本地媒体并切换输入源...";
        message.className = "notice";
      }
      try {
        const response = await fetch(`/local-media?filename=${encodeURIComponent(file.name)}`, {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          body: file
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "本地媒体上传失败");
        latestDashboardState = { ...(latestDashboardState || {}), input_source: payload.input_source || {} };
        resetInputSourceVisualState(selectedSource);
        renderSourceButtons(payload.input_source || {});
        activatePanel("panel-local-media");
        if (message) {
          message.textContent = "本地媒体已接入，双模型检测将切到本地输入。";
          message.className = "notice";
        }
      } catch (error) {
        if (message) {
          message.textContent = text(error.message || error);
          message.className = "notice danger";
        }
      }
    }
    async function uploadBoardLocalMedia(file) {
      const message = document.getElementById("source-message");
      const localName = document.getElementById("local-media-name");
      const mediaKind = file.type.startsWith("image/") ? "图片" : "视频";
      if (message) {
        message.textContent = `正在上传${mediaKind}到 RK3588 板卡...`;
        message.className = "notice";
      }
      if (localName) localName.textContent = `正在上传${mediaKind}到板卡...`;
      try {
        const response = await fetch(`/board-local-media?filename=${encodeURIComponent(file.name)}`, {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          body: file
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "上传到板卡失败");
        latestDashboardState = { ...(latestDashboardState || {}), input_source: payload.input_source || {} };
        renderSourceButtons(payload.input_source || {});
        activatePanel("panel-local-media");
        if (message) {
          message.textContent = `${mediaKind}已上传到板卡，双模型检测将使用板端本地媒体。`;
          message.className = "notice";
        }
        if (localName) localName.textContent = "板卡文件：" + (payload.board_path || "/root/safelab_media/current_demo.mp4") + "，正在播放检测。";
      } catch (error) {
        if (message) {
          message.textContent = text(error.message || error);
          message.className = "notice danger";
        }
        if (localName) localName.textContent = "上传到板卡失败";
      }
    }
    function maybeRequestAiFollowup(state) {
      if (!state || currentPanelId() !== "panel-ai" || aiFollowupInFlight) return;
      const events = state.latest_events || [];
      if (!events.length) return;
      const latestEvent = events[events.length - 1] || {};
      const latestEventId = text(latestEvent.event_id);
      if (!latestEventId) return;
      const explainedIds = new Set((state.latest_ai_explanations || []).map(row => text(row.event_id)));
      if (explainedIds.has(latestEventId)) return;
      const now = Date.now();
      if (lastAiFollowupAt && now - lastAiFollowupAt < AI_FOLLOWUP_INTERVAL_MS) return;
      lastAiFollowupAt = now;
      requestAiFollowup({ automatic: true });
    }
    async function requestAiFollowup(options = {}) {
      const message = document.getElementById("source-message");
      const button = document.getElementById("ai-followup-button");
      aiFollowupInFlight = true;
      if (button) button.disabled = true;
      if (message) {
        message.textContent = options.automatic ? "正在根据最新事件生成智能说明..." : "正在生成智能说明...";
        message.className = "notice";
      }
      try {
        const response = await fetch("/ai-followup", { method: "POST" });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "智能说明生成失败");
        if (payload.state) render(payload.state);
        const written = ((payload.ai_followup || {}).explanations_written || 0);
        if (message) {
          message.textContent = written ? "智能说明已更新。" : "暂无新的告警事件需要说明。";
          message.className = "notice";
        }
      } catch (error) {
        if (message) {
          message.textContent = text(error.message || error);
          message.className = "notice danger";
        }
      } finally {
        aiFollowupInFlight = false;
        if (button) button.disabled = false;
      }
    }
    async function saveSource(selectedSource) {
      const message = document.getElementById("source-message");
      message.textContent = "正在保存输入源...";
      message.className = "notice";
      try {
        const response = await fetch("/input-source", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ selected_source: selectedSource })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "输入源保存失败");
        renderSourceButtons(payload.input_source || {});
        activatePanel(sourcePanelForSource(selectedSource));
        message.textContent = `${esc((payload.input_source || {}).label)} 已保存，重启运行时后生效。`;
      } catch (error) {
        message.textContent = text(error.message || error);
        message.className = "notice danger";
      }
    }
    function resetInputSourceVisualState(selectedSource) {
      const cameraOverlay = document.getElementById("detection-overlay");
      if (cameraOverlay) cameraOverlay.innerHTML = "";
      const localFrame = document.getElementById("local-detection-frame-preview");
      const localStage = document.getElementById("local-result-stage");
      clearLocalYoloResult(localFrame, localStage);
      if (selectedSource === "camera_ov13855") restoreCameraStreamPreview();
    }
    async function saveModelDetection() {
      const toggle = document.getElementById("model-detection-toggle");
      const interval = document.getElementById("model-detection-interval");
      if (!toggle || !interval) return;
      const message = document.getElementById("source-message");
      try {
        const response = await fetch("/model-detection", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: toggle.checked, interval_frames: Number(interval.value || 75) })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "模型检测配置保存失败");
        renderModelDetection(payload.model_detection || {});
        if (message) {
          message.textContent = toggle.checked ? "模型检测已开启，检测间隔已更新。" : "模型检测已暂停。";
          message.className = "notice";
        }
      } catch (error) {
        if (message) {
          message.textContent = text(error.message || error);
          message.className = "notice danger";
        }
      }
    }
    async function saveSceneMode(mode) {
      const message = document.getElementById("source-message");
      if (message) {
        message.textContent = "正在切换场景模式...";
        message.className = "notice";
      }
      try {
        const response = await fetch("/scene-mode", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "场景模式保存失败");
        renderSceneMode(payload.scene_mode || {});
        if (message) {
          const requirements = (payload.scene_mode || {}).required_ppe_labels || [];
          message.textContent = `已切换到${(payload.scene_mode || {}).label}，检查项：${requirements.join(" / ")}`;
          message.className = "notice";
        }
      } catch (error) {
        if (message) {
          message.textContent = text(error.message || error);
          message.className = "notice danger";
        }
      }
    }
    function detectionList(rows) {
      if (!rows.length) return '<p class="muted">暂无检测记录。</p>';
      return `<div class="list">${rows.slice().reverse().map(r => `
        <div class="row">
          <div class="meta">帧 ${esc(r.frame_id)} | ${esc(detectionClassText(r.class_name))} | 置信度 ${esc(confidenceText(r.confidence))}</div>
          ${detectionThumb(r)}
          <div>${esc(r.model_name || "模型")}</div>
        </div>`).join("")}</div>`;
    }
    function detectionThumb(record) {
      if (!record.image_url) return "";
      return `<div class="detection-thumb">
        <img src="${esc(record.image_url)}" alt="${esc(detectionClassText(record.class_name))}">
        <div class="detection-overlay" data-thumb-bbox="${esc(JSON.stringify(record.bbox || []))}" data-thumb-class="${esc(record.class_name || "")}" data-thumb-label="${esc(detectionLabel(record))}"></div>
      </div>`;
    }
    function detectionClassText(value) {
      const labels = { person: "人员", helmet: "安全帽", vest: "反光背心", goggles: "护目镜", gloves: "防护手套", fire: "火焰", smoke: "烟雾" };
      return labels[text(value)] || text(value);
    }
    function confidenceText(value) {
      const numberValue = Number(value);
      return Number.isFinite(numberValue) ? numberValue.toFixed(2) : text(value);
    }
    function bboxText(value) {
      return Array.isArray(value) && value.length === 4 ? `框 ${value.map(v => Math.round(Number(v))).join(",")}` : "";
    }
    function renderDetectionOverlay(rows, source) {
      const latestRows = latestFrameDetections(rowsForActiveSource(rows, source));
      const cameraOverlay = document.getElementById("detection-overlay");
      if (cameraOverlay) cameraOverlay.innerHTML = "";
      const usesLocalPreview = source.selected_source === "file_demo" || source.selected_source === "board_file_demo";
      const boardLiveFrame = (latestDashboardState || {}).board_live_frame || {};
      const activeLiveFrame = (latestDashboardState || {}).active_live_frame || {};
      const boardFrameRows = source.selected_source === "board_file_demo" && boardLiveFrame.frame_id
        ? latestRows.filter(r => Number(r.frame_id) === Number(boardLiveFrame.frame_id))
        : latestRows;
      const cameraFrameRows = source.selected_source === "camera_ov13855" && activeLiveFrame.source_type === "camera" && activeLiveFrame.frame_id
        ? latestRows.filter(r => Number(r.frame_id) === Number(activeLiveFrame.frame_id))
        : latestRows;
      const latestDetectionFrame = latestRows.length ? latestRows[0] : null;
      if (usesLocalPreview) {
        const localRows = source.selected_source === "board_file_demo" ? boardFrameRows : latestRows;
        syncLocalDetectionFramePreview(source, localRows, boardLiveFrame);
        return;
      }
      const cameraDetectionFrame = syncCameraDetectionFramePreview(source, latestDetectionFrame);
      let targetMedia = cameraDetectionFrame || document.getElementById("camera-preview");
      const overlayRows = source.selected_source === "camera_ov13855" ? latestRows : cameraFrameRows;
      drawDetectionBoxes(cameraOverlay, targetMedia, overlayRows);
    }
    function syncCameraDetectionFramePreview(source, latestDetectionFrame) {
      const image = document.getElementById("camera-preview");
      if (!image || source.selected_source !== "camera_ov13855") return null;
      restoreCameraStreamPreview();
      return image;
    }
    function syncLocalDetectionFramePreview(source, latestRows, boardLiveFrame) {
      const detectionFrame = document.getElementById("local-detection-frame-preview");
      const resultStage = document.getElementById("local-result-stage");
      if (!detectionFrame) return null;
      const usesLocalPreview = source.selected_source === "file_demo" || source.selected_source === "board_file_demo";
      if (!usesLocalPreview || !latestRows.length) {
        clearLocalYoloResult(detectionFrame, resultStage);
        return null;
      }
      const frameUrl = (
        source.selected_source === "board_file_demo" && boardLiveFrame && boardLiveFrame.image_url
          ? boardLiveFrame.image_url
          : latestRows[0].image_url
      );
      if (!usesLocalPreview || !frameUrl) {
        clearLocalYoloResult(detectionFrame, resultStage);
        return null;
      }
      const signature = localYoloResultSignature(frameUrl, latestRows);
      if (detectionFrame.dataset.renderSignature !== signature) {
        clearLocalYoloResult(detectionFrame, resultStage);
        renderLocalYoloResultImage(detectionFrame, resultStage, frameUrl, latestRows, signature);
        return null;
      }
      return boardDetectionFrameReady(detectionFrame) ? detectionFrame : null;
    }
    function clearLocalYoloResult(detectionFrame, resultStage) {
      if (detectionFrame) {
        detectionFrame.removeAttribute("src");
        detectionFrame.style.display = "none";
        detectionFrame.dataset.renderSignature = "";
      }
      if (resultStage) resultStage.classList.remove("has-result");
    }
    function localYoloResultSignature(frameUrl, rows) {
      return `${frameUrl}|${JSON.stringify(rows.map(r => [r.frame_id, r.class_name, r.confidence, r.bbox]))}`;
    }
    function renderLocalYoloResultImage(detectionFrame, resultStage, frameUrl, rows, signature) {
      const sourceImage = new Image();
      sourceImage.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = sourceImage.naturalWidth || sourceImage.width;
        canvas.height = sourceImage.naturalHeight || sourceImage.height;
        const context = canvas.getContext("2d");
        if (!context || !canvas.width || !canvas.height) return;
        context.drawImage(sourceImage, 0, 0, canvas.width, canvas.height);
        rows.forEach(row => drawYoloBoxOnCanvas(context, row, canvas.width, canvas.height));
        detectionFrame.src = canvas.toDataURL("image/jpeg", 0.9);
        detectionFrame.dataset.renderSignature = signature;
        detectionFrame.style.display = "block";
        if (resultStage) resultStage.classList.add("has-result");
      };
      sourceImage.onerror = () => clearLocalYoloResult(detectionFrame, resultStage);
      sourceImage.src = frameUrl;
    }
    function drawYoloBoxOnCanvas(context, record, naturalWidth, naturalHeight) {
      const box = normalizedBox(record.bbox || [], naturalWidth, naturalHeight);
      if (!box) return;
      const left = (box.left / 100) * naturalWidth;
      const top = (box.top / 100) * naturalHeight;
      const width = (box.width / 100) * naturalWidth;
      const height = (box.height / 100) * naturalHeight;
      const lineWidth = Math.max(2, Math.round(Math.min(naturalWidth, naturalHeight) * 0.006));
      const color = record.class_name === "fire" || record.class_name === "smoke" ? "#ef4444" : "#22c55e";
      context.lineWidth = lineWidth;
      context.strokeStyle = color;
      context.strokeRect(left, top, width, height);
      const label = detectionLabel(record);
      if (label) {
        context.font = `${Math.max(16, lineWidth * 7)}px Segoe UI, sans-serif`;
        const metrics = context.measureText(label);
        const labelHeight = Math.max(24, lineWidth * 10);
        const labelTop = Math.max(0, top - labelHeight);
        context.fillStyle = color;
        context.fillRect(left, labelTop, metrics.width + 14, labelHeight);
        context.fillStyle = "#ffffff";
        context.fillText(label, left + 7, labelTop + labelHeight - 7);
      }
    }
    function boardDetectionFrameReady(detectionFrame) {
      return Boolean(detectionFrame && detectionFrame.complete && detectionFrame.naturalWidth && detectionFrame.naturalHeight);
    }
    function rowsForActiveSource(rows, source) {
      const expectedType = source.selected_source === "board_file_demo" ? "board_file" : source.selected_source === "file_demo" ? "file" : "camera";
      return rows.filter(r => !r.source_type || r.source_type === expectedType);
    }
    function latestFrameDetections(rows) {
      const valid = rows.filter(r => Array.isArray(r.bbox) && r.bbox.length === 4);
      if (!valid.length) return [];
      const latestFrame = Math.max(...valid.map(r => Number(r.frame_id) || 0));
      return valid.filter(r => Number(r.frame_id) === latestFrame);
    }
    function drawDetectionBoxes(overlay, media, rows) {
      if (!overlay || !media) return;
      if (!rows.length) {
        overlay.innerHTML = "";
        return;
      }
      const natural = mediaNaturalSize(media);
      if (!natural) {
        overlay.innerHTML = "";
        return;
      }
      const fit = mediaContentFit(media, natural.width, natural.height);
      overlay.innerHTML = rows.map(r => detectionBoxHtml(r, natural.width, natural.height, undefined, fit)).join("");
    }
    function mediaNaturalSize(media) {
      const tagName = (media.tagName || "").toLowerCase();
      if (tagName === "video") {
        return media.videoWidth && media.videoHeight ? { width: media.videoWidth, height: media.videoHeight } : null;
      }
      const width = media.naturalWidth || media.clientWidth;
      const height = media.naturalHeight || media.clientHeight;
      return width && height ? { width, height } : null;
    }
    function mediaContentFit(media, naturalWidth, naturalHeight) {
      const width = media.clientWidth || media.parentElement?.clientWidth || 1;
      const height = media.clientHeight || media.parentElement?.clientHeight || 1;
      const scale = Math.min(width / naturalWidth, height / naturalHeight);
      const renderedWidth = naturalWidth * scale;
      const renderedHeight = naturalHeight * scale;
      return {
        left: ((width - renderedWidth) / 2 / width) * 100,
        top: ((height - renderedHeight) / 2 / height) * 100,
        width: (renderedWidth / width) * 100,
        height: (renderedHeight / height) * 100,
      };
    }
    function detectionBoxHtml(record, naturalWidth, naturalHeight, labelOverride, fit) {
      const box = normalizedBox(record.bbox || [], naturalWidth, naturalHeight, fit);
      if (!box) return "";
      return `<div class="detection-box ${esc(record.class_name || "")}" style="left:${box.left}%;top:${box.top}%;width:${box.width}%;height:${box.height}%">
        <span class="detection-label">${esc(labelOverride || detectionLabel(record))}</span>
      </div>`;
    }
    function normalizedBox(bbox, naturalWidth, naturalHeight, fit) {
      if (!Array.isArray(bbox) || bbox.length !== 4) return null;
      const values = bbox.map(Number);
      if (values.some(value => !Number.isFinite(value))) return null;
      const [x1, y1, x2, y2] = values;
      const area = fit || { left: 0, top: 0, width: 100, height: 100 };
      return {
        left: clampPercent(area.left + (x1 / naturalWidth) * area.width),
        top: clampPercent(area.top + (y1 / naturalHeight) * area.height),
        width: clampPercent(((x2 - x1) / naturalWidth) * area.width),
        height: clampPercent(((y2 - y1) / naturalHeight) * area.height),
      };
    }
    function clampPercent(value) {
      return Math.max(0, Math.min(100, value));
    }
    function detectionLabel(record) {
      return `${detectionClassText(record.class_name)} ${confidenceText(record.confidence)}`.trim();
    }
    function syncDetectionThumbs() {
      document.querySelectorAll("[data-thumb-bbox]").forEach(overlay => {
        const image = overlay.parentElement ? overlay.parentElement.querySelector("img") : null;
        if (!image || !image.naturalWidth || !image.naturalHeight) return;
        let bbox = [];
        try { bbox = JSON.parse(overlay.dataset.thumbBbox || "[]"); } catch (error) { bbox = []; }
        const record = { bbox, class_name: overlay.dataset.thumbClass || "", confidence: "" };
        const label = overlay.dataset.thumbLabel || detectionClassText(record.class_name);
        const fit = mediaContentFit(image, image.naturalWidth, image.naturalHeight);
        overlay.innerHTML = detectionBoxHtml(record, image.naturalWidth, image.naturalHeight, label, fit);
      });
    }
    function eventList(rows) {
      if (!rows.length) return '<p class="muted">暂无风险事件。</p>';
      return `<div class="list">${rows.slice().reverse().map(r => `
        <div class="row">
          <div class="meta">帧 ${esc(r.frame_id)} | ${esc(eventTypeText(r.event_type))} | <span class="level-${esc(r.risk_level)}">${esc(statusText(r.risk_level))}</span></div>
          ${renderReasonLines(r.reasons || [])}
        </div>`).join("")}</div>`;
    }
    function eventTypeText(value) {
      const labels = { smoke: "烟雾", fire: "火焰", ppe_violation: "防护违规", forbidden_intrusion: "禁区入侵" };
      return labels[text(value)] || text(value);
    }
    function translateReasons(reasons) {
      return reasons.map(translateReason).join("；");
    }
    function renderReasonLines(reasons) {
      const translated = translateReasons(reasons);
      const missing = firstMatch(translated, /缺失防护=([^；]+)/);
      const suppressed = firstMatch(translated, /被抑制规则=([^；]+)/);
      const duration = firstMatch(translated, /连续\\s*\\d+\\s*帧(?:出现|触发|检测到[^；]*)/);
      if (translated.includes("规则 R001：危险区域缺少安全帽") || missing || suppressed) {
        const lines = [`<div class="reason-title">${esc(ppeViolationTitle(missing))}</div>`];
        if (missing) lines.push(`<div class="reason-line"><strong>缺失防护：</strong>${esc(cleanReasonText(missing))}</div>`);
        if (suppressed) lines.push(`<div class="reason-line"><strong>关联风险：</strong>${esc(cleanRelatedRisks(suppressed))}</div>`);
        if (duration) lines.push(`<div class="reason-line"><strong>持续状态：</strong>${esc(duration.replace("出现", "触发"))}</div>`);
        return `<div class="reason-lines">${lines.join("")}</div>`;
      }
      return `<div class="reason-lines">${translated.split("；").filter(Boolean).map(item => `<div class="reason-line">${esc(stripBoundingBox(item))}</div>`).join("")}</div>`;
    }
    function firstMatch(value, pattern) {
      const match = text(value).match(pattern);
      return match ? match[1] || match[0] : "";
    }
    function cleanRelatedRisks(value) {
      return cleanReasonText(value).split(",").map(item => item.replace(/R\\d{3}：/g, "").replace(/ 在危险区域内/g, "").trim()).filter(Boolean).join("；");
    }
    function cleanReasonText(value) {
      return stripBoundingBox(value).replace(/\\s+/g, " ").trim();
    }
    function ppeViolationTitle(missing) {
      const missingText = cleanReasonText(missing || "").replace(/\\s*,\\s*/g, "、");
      if (missingText) return `防护违规：人员缺少${missingText}。`;
      return "危险区域防护违规：人员未佩戴安全帽。";
    }
    function stripBoundingBox(value) {
      return text(value).replace(/R\\d{3}:\\d+,\\d+,\\d+,\\d+/g, "").trim();
    }
    function translateReason(reason) {
      let value = text(reason);
      value = value.replace(/smoke appeared for 3 consecutive frames/g, "连续 3 帧检测到烟雾");
      value = value.replace(/fire appeared for 3 consecutive frames/g, "连续 3 帧检测到火焰");
      value = value.replace(/fire detected by vision model/g, "视觉模型检测到火焰");
      value = value.replace(/rule SCENE_LAB_GOGGLES:/g, "实验室护目镜规则：");
      value = value.replace(/rule R004: goggles missing in welding zone/g, "规则 R004：焊接区域缺少护目镜");
      value = value.replace(/rule R001: helmet missing in danger zone/g, "规则 R001：危险区域缺少安全帽");
      value = value.replace(/person intrusion in danger zone/g, "人员进入危险区域");
      value = value.replace(/\bSCENE_LAB_GOGGLES:(?:board_file|camera|file|本地媒体):[0-9,]+/g, "");
      value = value.replace(/scene_mode=lab/g, "场景=实验室");
      value = value.replace(/scene_mode=construction/g, "场景=工地");
      value = value.replace(/source_type=board_file/g, "输入源=本地媒体");
      value = value.replace(/source_type=camera/g, "输入源=摄像头");
      value = value.replace(/source_type=file/g, "输入源=本地文件");
      value = value.replace(/ppe_violation/g, "防护违规");
      value = value.replace(/forbidden_intrusion/g, "禁区入侵");
      value = value.replace(/suppressed_rules=/g, "被抑制规则=");
      value = value.replace(/zone=welding_zone/g, "区域=焊接区域");
      value = value.replace(/zone=danger_zone/g, "区域=危险区域");
      value = value.replace(/zone=normal_zone/g, "区域=普通区域");
      value = value.replace(/missing_ppe=/g, "缺失防护=");
      value = value.replace(/board_file/g, "本地媒体");
      value = value.replace(/\bfallback\b/g, "本地兜底");
      value = value.replace(/\bhigh\b/g, "高风险");
      value = value.replace(/\bemergency\b/g, "紧急");
      value = value.replace(/\bwarning\b/g, "预警");
      value = value.replace(/helmet missing/g, "缺少安全帽");
      value = value.replace(/vest missing/g, "缺少反光背心");
      value = value.replace(/goggles missing/g, "缺少护目镜");
      value = value.replace(/gloves missing/g, "缺少防护手套");
      value = value.replace(/in danger zone/g, "在危险区域内");
      value = value.replace(/danger_zone/g, "危险区域");
      value = value.replace(/welding_zone/g, "焊接区域");
      value = value.replace(/normal_zone/g, "普通区域");
      value = value.replace(/helmet/g, "安全帽").replace(/vest/g, "反光背心").replace(/goggles/g, "护目镜").replace(/gloves/g, "防护手套");
      value = value.replace(/R(\\d{3}):(\\d+),(\\d+),(\\d+),(\\d+)/g, "");
      value = value.replace(/R(\\d{3}):/g, "R$1：");
      value = value.replace(/appeared for 3 consecutive frames/g, "连续 3 帧出现");
      return value;
    }
    function aiSourceText(value) {
      const labels = { fallback: "本地兜底", deepseek: "DeepSeek 智能分析", none: "暂无来源" };
      return labels[text(value)] || translateReason(value);
    }
    function aiPanel(rows) {
      if (!rows.length) return '<div class="ai-latest"><strong>暂无智能说明。</strong><p class="muted">生成 AI 说明后，这里会显示最新解释和处置建议。</p></div>';
      const latest = rows[rows.length - 1] || {};
      const history = rows.slice(-4, -1).reverse();
      return `
        <div class="ai-latest">
          <strong>${esc(aiSourceText(latest.source || "AI"))} | ${esc(latest.event_id || "最新")}</strong>
          <p>${esc(translateVoice(latest.summary || latest.voice_text || "暂无摘要。"))}</p>
          <p class="muted">${esc(translateVoice(latest.recommendation || latest.voice_text || ""))}</p>
        </div>
        <div class="list" style="margin-top:10px">${history.map(r => `<div class="row"><div class="meta">${esc(r.event_id)} | ${esc(aiSourceText(r.source))}</div>${esc(translateVoice(r.summary || r.voice_text || ""))}</div>`).join("")}</div>`;
    }
    function actionList(rows) {
      if (!rows.length) return '<p class="muted">暂无告警动作。</p>';
      return `<div class="list">${rows.slice(-4).reverse().map(r => `
        <div class="row"><div class="meta">${esc(r.event_id)} | 灯光 ${esc(colorText(r.led_color))} | 蜂鸣 ${esc(booleanText(r.buzzer))}</div>${esc(translateVoice(r.voice_text || ""))}</div>`).join("")}</div>`;
    }
    function actuatorList(rows) {
      if (!rows.length) return '<p class="muted">暂无执行器记录。</p>';
      return `<div class="list">${rows.slice(-4).reverse().map(r => `
        <div class="row"><div class="meta">${esc(r.event_id)} | ${esc(r.backend)}</div>灯光 ${esc(colorText((r.led || {}).color))} | 蜂鸣 ${esc(booleanText((r.buzzer || {}).enabled))} | 继电器 ${esc(booleanText((r.relay || {}).enabled))}</div>`).join("")}</div>`;
    }
    function actuatorList(rows) {
      if (!rows.length) return '<p class="muted">暂无喇叭播报记录。</p>';
      return `<div class="list">${rows.slice(-6).reverse().map(r => {
        const speaker = r.speaker || {};
        const played = speaker.executed ? "已播报" : "播报失败";
        const device = speaker.device ? ` | ${esc(speaker.device)}` : "";
        return `<div class="row"><div class="meta">${esc(r.event_id || "speaker")} | 喇叭播报 | ${played}${device}</div>${esc(translateVoice(r.voice_text || ""))}</div>`;
      }).join("")}</div>`;
    }
    function colorText(value) {
      const labels = { red: "红色", yellow: "黄色", green: "绿色" };
      return labels[text(value)] || text(value);
    }
    function booleanText(value) {
      return value === true || value === "true" ? "开启" : value === false || value === "false" ? "关闭" : text(value);
    }
    function translateVoice(value) {
      let textValue = text(value);
      textValue = textValue.replace(/Fire risk detected\\. Please check the lab immediately\\.?/g, "检测到火焰风险，请立即复核现场。");
      textValue = textValue.replace(/Smoke risk detected\\. Please check the lab\\.?/g, "检测到烟雾风险，请立即复核现场。");
      textValue = textValue.replace(/Goggles missing in welding zone\\. Please wear eye protection\\.?/g, "焊接区域缺少护目镜，请佩戴眼部防护。");
      textValue = textValue.replace(/Helmet missing in danger zone\\. Please correct immediately\\.?/g, "危险区域缺少安全帽，请立即纠正。");
      textValue = textValue.replace(/high风险/g, "高风险");
      return translateReason(textValue);
    }
    const CAMERA_STREAM_URL = "http://127.0.0.1:8090/stream.mjpg";
    let usingCameraSnapshotFallback = false;
    let cameraPreviewStarted = false;
    function restoreCameraStreamPreview() {
      const image = document.getElementById("camera-preview");
      const fallback = document.getElementById("video-fallback");
      if (!image || usingCameraSnapshotFallback) return;
      if (!cameraPreviewStarted) {
        refreshCameraPreview();
        return;
      }
      image.style.display = "block";
      if (fallback) fallback.style.display = "none";
      if (image.getAttribute("src") !== CAMERA_STREAM_URL) {
        image.src = CAMERA_STREAM_URL;
      }
    }
    function refreshCameraPreview() {
      const image = document.getElementById("camera-preview");
      const fallback = document.getElementById("video-fallback");
      if (!image) return;
      if (cameraPreviewStarted) return;
      cameraPreviewStarted = true;
      image.onerror = () => {
        if (!usingCameraSnapshotFallback) {
          usingCameraSnapshotFallback = true;
          image.src = "/board_camera_preview.jpg?t=" + Date.now();
          return;
        }
        image.style.display = "none";
        if (fallback) fallback.style.display = "block";
      };
      image.onload = () => {
        image.style.display = "block";
        if (fallback) fallback.style.display = "none";
      };
      image.src = CAMERA_STREAM_URL;
    }
    async function refresh() {
      const response = await fetch("/state.json?t=" + Date.now(), { cache: "no-store" });
      render(await response.json());
    }
    if (window.EventSource) {
      const stream = new EventSource("/events");
      stream.addEventListener("state", event => render(JSON.parse(event.data)));
      stream.onerror = () => setTimeout(refresh, 1000);
    }
    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""

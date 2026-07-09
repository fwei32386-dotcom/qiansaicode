from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import paramiko


JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"


def build_mock_overlay(frame_id: int, source_width: int, source_height: int) -> dict[str, Any]:
    phase = frame_id % 120
    offset = min(phase, 120 - phase) * 6
    person_x1 = int(source_width * 0.38 + offset)
    person_y1 = int(source_height * 0.22)
    person_x2 = min(person_x1 + int(source_width * 0.14), source_width - 1)
    person_y2 = min(person_y1 + int(source_height * 0.52), source_height - 1)
    vest_y1 = person_y1 + int((person_y2 - person_y1) * 0.32)
    helmet_y2 = person_y1 + int((person_y2 - person_y1) * 0.16)
    return {
        "mode": "mock_overlay",
        "frame_id": frame_id,
        "source_width": source_width,
        "source_height": source_height,
        "detections": [
            {
                "class_name": "person",
                "confidence": 0.93,
                "bbox": [person_x1, person_y1, person_x2, person_y2],
                "risk": "warning",
                "label": "person in danger_zone",
            },
            {
                "class_name": "vest",
                "confidence": 0.88,
                "bbox": [
                    person_x1 + 22,
                    vest_y1,
                    person_x2 - 18,
                    vest_y1 + int((person_y2 - person_y1) * 0.25),
                ],
                "risk": "normal",
                "label": "vest",
            },
            {
                "class_name": "helmet_missing",
                "confidence": 1.0,
                "bbox": [person_x1 + 18, person_y1, person_x2 - 18, helmet_y2],
                "risk": "high",
                "label": "helmet missing",
            },
        ],
        "events": [
            {
                "rule_id": "R001",
                "risk_level": "high",
                "event_type": "ppe_violation",
                "message": "Mock: helmet missing in danger_zone",
            }
        ],
    }


class SharedFrame:
    def __init__(self, metadata: dict[str, Any] | None = None) -> None:
        self._lock = threading.Lock()
        self.frame: bytes | None = None
        self.frame_id = 0
        self.last_error = ""
        self.started_at = time.time()
        self.last_frame_at = 0.0
        self.frame_times: deque[float] = deque(maxlen=30)
        self.metadata = metadata or {}

    def update_frame(self, frame: bytes) -> None:
        with self._lock:
            now = time.time()
            self.frame = frame
            self.frame_id += 1
            self.last_frame_at = now
            self.frame_times.append(now)
            self.last_error = ""

    def set_error(self, message: str) -> None:
        with self._lock:
            self.last_error = message

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            stale_after = float(self.metadata.get("stale_after_seconds", 2.0))
            frame_age = round(time.time() - self.last_frame_at, 3) if self.last_frame_at else None
            stale = frame_age is None or frame_age > stale_after
            estimated_fps = 0.0
            if not stale and len(self.frame_times) >= 2:
                elapsed = self.frame_times[-1] - self.frame_times[0]
                if elapsed > 0:
                    estimated_fps = (len(self.frame_times) - 1) / elapsed
            return {
                "frame": self.frame,
                "frame_id": self.frame_id,
                "frame_bytes": len(self.frame or b""),
                "last_error": self.last_error,
                "estimated_fps": round(estimated_fps, 2),
                "uptime_seconds": round(time.time() - self.started_at, 3),
                "last_frame_age_seconds": frame_age,
                "stale": stale,
                "stream_config": self.metadata,
            }


def _preview_height_for_width(source_width: int, source_height: int, preview_width: int) -> int:
    height = max(2, round(preview_width * source_height / source_width))
    return height if height % 2 == 0 else height + 1


def build_gstreamer_command(device: str, source_width: int, source_height: int, fps: int, preview_width: int) -> str:
    preview_height = _preview_height_for_width(source_width, source_height, preview_width)
    return (
        "gst-launch-1.0 -q "
        f"v4l2src device={device} "
        f"! 'video/x-raw,format=NV12,width={source_width},height={source_height},framerate=30/1' "
        "! videorate "
        f"! 'video/x-raw,framerate={fps}/1' "
        "! videoconvert "
        "! videoscale "
        f"! 'video/x-raw,width={preview_width},height={preview_height}' "
        "! jpegenc quality=75 "
        "! fdsink fd=1"
    )


def frame_reader(
    shared: SharedFrame,
    stop_event: threading.Event,
    host: str,
    username: str,
    password: str,
    command: str,
    reconnect_delay_seconds: float = 1.0,
) -> None:
    while not stop_event.is_set():
        _read_remote_stream_once(shared, stop_event, host, username, password, command)
        if not stop_event.is_set():
            time.sleep(max(0.1, reconnect_delay_seconds))


def _read_remote_stream_once(
    shared: SharedFrame,
    stop_event: threading.Event,
    host: str,
    username: str,
    password: str,
    command: str,
) -> None:
    client: paramiko.SSHClient | None = None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
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
        _, stdout, stderr = client.exec_command(command, timeout=None)
        channel = stdout.channel
        channel.settimeout(1.0)
        buffer = b""
        last_stderr_check = time.time()

        while not stop_event.is_set():
            try:
                chunk = channel.recv(65536)
            except Exception:
                chunk = b""

            if chunk:
                buffer += chunk
                buffer = _consume_jpegs(buffer, shared)
                if len(buffer) > 4_000_000:
                    buffer = buffer[-1_000_000:]
            elif channel.exit_status_ready():
                err = stderr.read().decode("utf-8", errors="replace").strip()
                shared.set_error(err or "remote gstreamer pipeline stopped")
                return
            else:
                if time.time() - last_stderr_check > 3:
                    last_stderr_check = time.time()
                time.sleep(0.02)
    except Exception as exc:  # pragma: no cover - exercised on real board
        shared.set_error(str(exc))
    finally:
        if client is not None:
            client.close()


def _consume_jpegs(buffer: bytes, shared: SharedFrame) -> bytes:
    while True:
        start = buffer.find(JPEG_SOI)
        if start < 0:
            return buffer[-1:]
        end = buffer.find(JPEG_EOI, start + 2)
        if end < 0:
            return buffer[start:]
        frame = buffer[start : end + 2]
        shared.update_frame(frame)
        buffer = buffer[end + 2 :]


def make_handler(shared: SharedFrame) -> type[BaseHTTPRequestHandler]:
    class LivePreviewHandler(BaseHTTPRequestHandler):
        server_version = "SafeLabCameraLive/1.0"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/index.html"):
                self._send_monitor_html()
            elif self.path == "/stream.mjpg":
                self._send_stream()
            elif self.path.startswith("/frame.jpg"):
                self._send_frame()
            elif self.path.startswith("/detections"):
                self._send_detections()
            elif self.path == "/status":
                self._send_status()
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def _send_monitor_html(self) -> None:
            body = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SafeLab OV13855 Live Monitor</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1220;
      --panel: #111827;
      --panel-2: #162033;
      --line: #334155;
      --muted: #94a3b8;
      --text: #e5e7eb;
      --ok: #22c55e;
      --warn: #f59e0b;
      --high: #ef4444;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, sans-serif;
      letter-spacing: 0;
    }
    header {
      height: 56px;
      padding: 0 16px;
      background: #0f172a;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .brand { display: flex; align-items: center; gap: 10px; min-width: 0; }
    .brand strong { font-size: 16px; white-space: nowrap; }
    .dot { width: 10px; height: 10px; border-radius: 999px; background: var(--warn); box-shadow: 0 0 0 3px rgba(245, 158, 11, .16); }
    .dot.ok { background: var(--ok); box-shadow: 0 0 0 3px rgba(34, 197, 94, .16); }
    .top-meta { color: var(--muted); font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    main {
      height: calc(100vh - 56px);
      padding: 12px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      gap: 12px;
    }
    .viewer {
      min-width: 0;
      min-height: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      border: 1px solid var(--line);
      background: #020617;
    }
    .toolbar {
      min-height: 46px;
      padding: 8px;
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    .toolbar-group { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
    button {
      height: 30px;
      border: 1px solid #475569;
      background: #1f2937;
      color: var(--text);
      padding: 0 10px;
      font-size: 13px;
      cursor: pointer;
    }
    button:hover { background: #263449; }
    button.active { border-color: #60a5fa; background: #1d4ed8; }
    .video-stage {
      position: relative;
      min-width: 0;
      min-height: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #000;
    }
    .frame-layer {
      position: absolute;
      inset: 0;
      display: block;
      width: 100%;
      height: 100%;
      background: #000;
    }
    body.fit-contain .frame-layer { object-fit: contain; }
    body.fit-cover .frame-layer { object-fit: cover; }
    body.fit-native .frame-layer { width: auto; height: auto; max-width: none; max-height: none; object-fit: none; }
    .overlay-layer { z-index: 2; pointer-events: none; background: transparent; }
    .overlay-box {
      position: absolute;
      border: 2px solid var(--ok);
      background: rgba(34, 197, 94, .08);
    }
    .overlay-box.warning { border-color: var(--warn); background: rgba(245, 158, 11, .10); }
    .overlay-box.high { border-color: var(--high); background: rgba(239, 68, 68, .12); }
    .overlay-label {
      position: absolute;
      left: -2px;
      top: -24px;
      max-width: 280px;
      padding: 3px 6px;
      color: #fff;
      background: rgba(15, 23, 42, .94);
      border: 1px solid currentColor;
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    aside {
      min-width: 0;
      border: 1px solid var(--line);
      background: var(--panel);
      overflow: auto;
    }
    aside h2 {
      margin: 0;
      padding: 12px;
      font-size: 15px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
    }
    .metric {
      display: grid;
      grid-template-columns: 112px minmax(0, 1fr);
      gap: 10px;
      padding: 10px 12px;
      border-bottom: 1px solid rgba(51, 65, 85, .7);
      font-size: 13px;
    }
    .metric span:first-child { color: var(--muted); }
    .metric strong { font-size: 14px; font-weight: 600; overflow-wrap: anywhere; }
    .hint, .event-list { padding: 12px; color: var(--muted); font-size: 13px; line-height: 1.5; }
    .event-item { margin-bottom: 8px; padding: 8px; border-left: 3px solid var(--high); background: rgba(239, 68, 68, .08); color: var(--text); }
    @media (max-width: 860px) {
      header { height: auto; min-height: 56px; align-items: flex-start; flex-direction: column; padding: 10px 12px; }
      main { height: auto; min-height: calc(100vh - 76px); grid-template-columns: 1fr; grid-template-rows: minmax(360px, 72vh) auto; }
      aside { max-height: none; }
      .toolbar { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body class="fit-contain">
  <header>
    <div class="brand"><span id="dot" class="dot"></span><strong>SafeLab OV13855 Live Monitor</strong></div>
    <span id="top-status" class="top-meta">connecting...</span>
  </header>
  <main>
    <section class="viewer">
      <div class="toolbar">
        <div class="toolbar-group" aria-label="view controls">
          <button class="active" type="button" data-fit="fit-contain">Fit</button>
          <button type="button" data-fit="fit-cover">Fill</button>
          <button type="button" data-fit="fit-native">Native</button>
          <button id="overlay-toggle" type="button">Mock Overlay Off</button>
        </div>
        <div class="toolbar-group">
          <button id="reload" type="button">Reconnect</button>
        </div>
      </div>
      <div class="video-stage">
        <img id="stream" class="frame-layer" src="/frame.jpg" alt="OV13855 live camera stream">
        <div id="overlay" class="frame-layer overlay-layer" aria-hidden="true"></div>
      </div>
    </section>
    <aside>
      <h2>Runtime</h2>
      <div class="metric"><span>Connection</span><strong id="state">connecting</strong></div>
      <div class="metric"><span>Frame</span><strong id="frame-id">0</strong></div>
      <div class="metric"><span>FPS</span><strong id="fps">0 FPS</strong></div>
      <div class="metric"><span>Frame Age</span><strong id="age">-</strong></div>
      <div class="metric"><span>JPEG Size</span><strong id="bytes">-</strong></div>
      <div class="metric"><span>Source</span><strong id="source-size">-</strong></div>
      <div class="metric"><span>Preview</span><strong id="preview-width">-</strong></div>
      <div class="metric"><span>Device</span><strong id="device">-</strong></div>
      <div class="metric"><span>Overlay</span><strong id="overlay-state">off</strong></div>
      <div class="metric"><span>Error</span><strong id="error">none</strong></div>
      <h2>Events</h2>
      <div id="events" class="event-list">No events yet.</div>
      <div class="hint">Frames are streamed through memory and SSH. Detection boxes stay off by default until RKNN detections are connected; mock overlay can be enabled only for UI demos.</div>
    </aside>
  </main>
  <script>
    const stream = document.getElementById('stream');
    const overlay = document.getElementById('overlay');
    const overlayToggle = document.getElementById('overlay-toggle');
    const dot = document.getElementById('dot');
    let latestStatus = null;
    let overlayEnabled = false;
    let frameRefreshMs = 100;
    const fields = {
      top: document.getElementById('top-status'),
      state: document.getElementById('state'),
      frameId: document.getElementById('frame-id'),
      fps: document.getElementById('fps'),
      age: document.getElementById('age'),
      bytes: document.getElementById('bytes'),
      sourceSize: document.getElementById('source-size'),
      previewWidth: document.getElementById('preview-width'),
      device: document.getElementById('device'),
      overlayState: document.getElementById('overlay-state'),
      events: document.getElementById('events'),
      error: document.getElementById('error')
    };

    function fmtBytes(value) {
      if (!value) return '-';
      if (value > 1024 * 1024) return `${(value / 1024 / 1024).toFixed(2)} MB`;
      return `${Math.round(value / 1024)} KB`;
    }

    document.querySelectorAll('[data-fit]').forEach((button) => {
      button.addEventListener('click', () => {
        document.body.classList.remove('fit-contain', 'fit-cover', 'fit-native');
        document.body.classList.add(button.dataset.fit);
        document.querySelectorAll('[data-fit]').forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        updateOverlay();
      });
    });

    document.getElementById('reload').addEventListener('click', () => {
      stream.src = `/frame.jpg?t=${Date.now()}`;
    });

    overlayToggle.addEventListener('click', () => {
      overlayEnabled = !overlayEnabled;
      overlayToggle.classList.toggle('active', overlayEnabled);
      fields.overlayState.textContent = overlayEnabled ? 'mock' : 'off';
      overlayToggle.textContent = overlayEnabled ? 'Mock Overlay On' : 'Mock Overlay Off';
      if (!overlayEnabled) {
        overlay.innerHTML = '';
        fields.events.textContent = 'No events yet.';
      }
    });

    function imageRect(sourceWidth, sourceHeight) {
      const stage = overlay.getBoundingClientRect();
      if (document.body.classList.contains('fit-cover')) {
        const scale = Math.max(stage.width / sourceWidth, stage.height / sourceHeight);
        const width = sourceWidth * scale;
        const height = sourceHeight * scale;
        return { left: (stage.width - width) / 2, top: (stage.height - height) / 2, width, height };
      }
      if (document.body.classList.contains('fit-native')) {
        return { left: (stage.width - sourceWidth) / 2, top: (stage.height - sourceHeight) / 2, width: sourceWidth, height: sourceHeight };
      }
      const scale = Math.min(stage.width / sourceWidth, stage.height / sourceHeight);
      const width = sourceWidth * scale;
      const height = sourceHeight * scale;
      return { left: (stage.width - width) / 2, top: (stage.height - height) / 2, width, height };
    }

    function renderOverlay(payload) {
      if (!overlayEnabled || !payload || !payload.detections) {
        overlay.innerHTML = '';
        return;
      }
      const rect = imageRect(payload.source_width, payload.source_height);
      const scaleX = rect.width / payload.source_width;
      const scaleY = rect.height / payload.source_height;
      overlay.innerHTML = payload.detections.map((item) => {
        const [x1, y1, x2, y2] = item.bbox;
        const left = rect.left + x1 * scaleX;
        const top = rect.top + y1 * scaleY;
        const width = Math.max((x2 - x1) * scaleX, 2);
        const height = Math.max((y2 - y1) * scaleY, 2);
        const risk = item.risk || 'normal';
        const label = `${item.label || item.class_name} ${(item.confidence || 0).toFixed(2)}`;
        return `<div class="overlay-box ${risk}" style="left:${left}px;top:${top}px;width:${width}px;height:${height}px"><span class="overlay-label">${label}</span></div>`;
      }).join('');
      if (payload.events && payload.events.length) {
        fields.events.innerHTML = payload.events.map((event) => `<div class="event-item"><strong>${event.risk_level}</strong> ${event.rule_id}: ${event.message}</div>`).join('');
      } else {
        fields.events.textContent = 'No events.';
      }
    }

    async function updateOverlay() {
      if (!overlayEnabled || !latestStatus) return;
      try {
        const res = await fetch(`/detections?frame_id=${latestStatus.frame_id}`, { cache: 'no-store' });
        renderOverlay(await res.json());
      } catch (err) {
        overlay.innerHTML = '';
      }
    }

    async function updateStatus() {
      try {
        const res = await fetch('/status', { cache: 'no-store' });
        const data = await res.json();
        latestStatus = data;
        const cfg = data.stream_config || {};
        const age = data.last_frame_age_seconds;
        const ok = data.frame_id > 0 && !data.last_error && (age === null || age < 2);
        dot.classList.toggle('ok', ok);
        fields.state.textContent = ok ? 'live' : 'waiting';
        fields.frameId.textContent = data.frame_id;
        fields.fps.textContent = `${data.estimated_fps || 0} FPS`;
        fields.age.textContent = age === null ? '-' : `${age}s`;
        fields.bytes.textContent = fmtBytes(data.frame_bytes);
        fields.sourceSize.textContent = cfg.source_width && cfg.source_height ? `${cfg.source_width} x ${cfg.source_height}` : '-';
        fields.previewWidth.textContent = cfg.preview_width ? `${cfg.preview_width}px` : '-';
        fields.device.textContent = cfg.device || '-';
        fields.overlayState.textContent = overlayEnabled ? 'mock' : 'off';
        fields.error.textContent = data.last_error || 'none';
        if (cfg.target_fps) frameRefreshMs = Math.max(50, Math.round(1000 / cfg.target_fps));
        fields.top.textContent = ok
          ? `live | frame ${data.frame_id} | ${data.estimated_fps || 0} FPS | age ${age}s`
          : `waiting | ${data.last_error || 'no frame yet'}`;
      } catch (err) {
        dot.classList.remove('ok');
        fields.state.textContent = 'status unavailable';
        fields.top.textContent = 'status unavailable';
      }
    }

    function refreshFrame() {
      stream.src = `/frame.jpg?t=${Date.now()}`;
    }

    function scheduleFrameRefresh() {
      refreshFrame();
      setTimeout(scheduleFrameRefresh, frameRefreshMs);
    }

    setInterval(updateStatus, 500);
    setInterval(updateOverlay, 500);
    window.addEventListener('resize', updateOverlay);
    updateStatus();
    scheduleFrameRefresh();
  </script>
</body>
</html>
""".encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self) -> None:
            body = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SafeLab OV13855 Live Preview</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1220;
      --panel: #111827;
      --panel-2: #162033;
      --line: #334155;
      --muted: #94a3b8;
      --text: #e5e7eb;
      --ok: #22c55e;
      --warn: #f59e0b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, sans-serif;
      letter-spacing: 0;
    }
    header {
      height: 56px;
      padding: 0 16px;
      background: #0f172a;
      border-bottom: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
    }
    .brand { display: flex; align-items: center; gap: 10px; min-width: 0; }
    .brand strong { font-size: 16px; white-space: nowrap; }
    .dot { width: 10px; height: 10px; border-radius: 999px; background: var(--warn); box-shadow: 0 0 0 3px rgba(245, 158, 11, .16); }
    .dot.ok { background: var(--ok); box-shadow: 0 0 0 3px rgba(34, 197, 94, .16); }
    .top-meta { color: var(--muted); font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    main {
      height: calc(100vh - 56px);
      padding: 12px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 300px;
      gap: 12px;
    }
    .viewer {
      min-width: 0;
      min-height: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      border: 1px solid var(--line);
      background: #020617;
    }
    .toolbar {
      min-height: 46px;
      padding: 8px;
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    .toolbar-group { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
    button {
      height: 30px;
      border: 1px solid #475569;
      background: #1f2937;
      color: var(--text);
      padding: 0 10px;
      font-size: 13px;
      cursor: pointer;
    }
    button:hover { background: #263449; }
    button.active { border-color: #60a5fa; background: #1d4ed8; }
    .video-stage {
      min-width: 0;
      min-height: 0;
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      background: #000;
    }
    img {
      display: block;
      width: 100%;
      height: 100%;
      background: #000;
    }
    body.fit-contain img { object-fit: contain; }
    body.fit-cover img { object-fit: cover; }
    body.fit-native img {
      width: auto;
      height: auto;
      max-width: none;
      max-height: none;
      object-fit: none;
    }
    aside {
      min-width: 0;
      border: 1px solid var(--line);
      background: var(--panel);
      overflow: auto;
    }
    aside h2 {
      margin: 0;
      padding: 12px;
      font-size: 15px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
    }
    .metric {
      display: grid;
      grid-template-columns: 110px minmax(0, 1fr);
      gap: 10px;
      padding: 10px 12px;
      border-bottom: 1px solid rgba(51, 65, 85, .7);
      font-size: 13px;
    }
    .metric span:first-child { color: var(--muted); }
    .metric strong {
      font-size: 14px;
      font-weight: 600;
      overflow-wrap: anywhere;
    }
    .hint {
      padding: 12px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    @media (max-width: 860px) {
      header { height: auto; min-height: 56px; align-items: flex-start; flex-direction: column; padding: 10px 12px; }
      main { height: auto; min-height: calc(100vh - 76px); grid-template-columns: 1fr; grid-template-rows: minmax(360px, 72vh) auto; }
      aside { max-height: none; }
      .toolbar { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body class="fit-contain">
  <header>
    <div class="brand"><span id="dot" class="dot"></span><strong>SafeLab OV13855 实时预览</strong></div>
    <span id="top-status" class="top-meta">connecting...</span>
  </header>
  <main>
    <section class="viewer">
      <div class="toolbar">
        <div class="toolbar-group" aria-label="view fit mode">
          <button class="active" type="button" data-fit="fit-contain">适配窗口</button>
          <button type="button" data-fit="fit-cover">填充画面</button>
          <button type="button" data-fit="fit-native">原始大小</button>
        </div>
        <div class="toolbar-group">
          <button id="reload" type="button">重连视频流</button>
        </div>
      </div>
      <div class="video-stage">
        <img id="stream" src="/frame.jpg" alt="OV13855 live camera stream">
      </div>
    </section>
    <aside>
      <h2>运行状态</h2>
      <div class="metric"><span>连接</span><strong id="state">connecting</strong></div>
      <div class="metric"><span>接收帧</span><strong id="frame-id">0</strong></div>
      <div class="metric"><span>估计帧率</span><strong id="fps">0 FPS</strong></div>
      <div class="metric"><span>帧延迟</span><strong id="age">-</strong></div>
      <div class="metric"><span>JPEG 大小</span><strong id="bytes">-</strong></div>
      <div class="metric"><span>源分辨率</span><strong id="source-size">-</strong></div>
      <div class="metric"><span>预览宽度</span><strong id="preview-width">-</strong></div>
      <div class="metric"><span>设备节点</span><strong id="device">-</strong></div>
      <div class="metric"><span>错误</span><strong id="error">none</strong></div>
      <div class="hint">视频流通过内存和 SSH 管道转发；这里只显示实时画面，不在板卡上逐帧保存图片。</div>
    </aside>
  </main>
  <script>
    const stream = document.getElementById('stream');
    const dot = document.getElementById('dot');
    const fields = {
      top: document.getElementById('top-status'),
      state: document.getElementById('state'),
      frameId: document.getElementById('frame-id'),
      fps: document.getElementById('fps'),
      age: document.getElementById('age'),
      bytes: document.getElementById('bytes'),
      sourceSize: document.getElementById('source-size'),
      previewWidth: document.getElementById('preview-width'),
      device: document.getElementById('device'),
      error: document.getElementById('error')
    };

    function fmtBytes(value) {
      if (!value) return '-';
      if (value > 1024 * 1024) return `${(value / 1024 / 1024).toFixed(2)} MB`;
      return `${Math.round(value / 1024)} KB`;
    }

    document.querySelectorAll('[data-fit]').forEach((button) => {
      button.addEventListener('click', () => {
        document.body.classList.remove('fit-contain', 'fit-cover', 'fit-native');
        document.body.classList.add(button.dataset.fit);
        document.querySelectorAll('[data-fit]').forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
      });
    });

    document.getElementById('reload').addEventListener('click', () => {
      stream.src = `/frame.jpg?t=${Date.now()}`;
    });

    async function updateStatus() {
      try {
        const res = await fetch('/status', { cache: 'no-store' });
        const data = await res.json();
        const cfg = data.stream_config || {};
        const age = data.last_frame_age_seconds;
        const ok = data.frame_id > 0 && !data.last_error && (age === null || age < 2);
        dot.classList.toggle('ok', ok);
        fields.state.textContent = ok ? 'live' : 'waiting';
        fields.frameId.textContent = data.frame_id;
        fields.fps.textContent = `${data.estimated_fps || 0} FPS`;
        fields.age.textContent = age === null ? '-' : `${age}s`;
        fields.bytes.textContent = fmtBytes(data.frame_bytes);
        fields.sourceSize.textContent = cfg.source_width && cfg.source_height ? `${cfg.source_width} x ${cfg.source_height}` : '-';
        fields.previewWidth.textContent = cfg.preview_width ? `${cfg.preview_width}px` : '-';
        fields.device.textContent = cfg.device || '-';
        fields.error.textContent = data.last_error || 'none';
        if (cfg.target_fps) {
          frameRefreshMs = Math.max(50, Math.round(1000 / cfg.target_fps));
        }
        fields.top.textContent = ok
          ? `live | frame ${data.frame_id} | ${data.estimated_fps || 0} FPS | age ${age}s`
          : `waiting | ${data.last_error || 'no frame yet'}`;
      } catch (err) {
        dot.classList.remove('ok');
        fields.state.textContent = 'status unavailable';
        fields.top.textContent = 'status unavailable';
      }
    }
    let frameRefreshMs = 200;

    function refreshFrame() {
      stream.src = `/frame.jpg?t=${Date.now()}`;
    }

    function scheduleFrameRefresh() {
      refreshFrame();
      setTimeout(scheduleFrameRefresh, frameRefreshMs);
    }

    setInterval(updateStatus, 500);
    updateStatus();
    scheduleFrameRefresh();
  </script>
</body>
</html>
""".encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_frame(self) -> None:
            deadline = time.time() + 2
            frame = None
            while time.time() < deadline:
                status = shared.snapshot()
                frame = status["frame"]
                if frame is not None:
                    break
                time.sleep(0.03)
            if frame is None:
                self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "no camera frame available")
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(frame)))
            self.end_headers()
            self.wfile.write(frame)

        def _send_status(self) -> None:
            status = shared.snapshot()
            status.pop("frame", None)
            body = json.dumps(status, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_detections(self) -> None:
            status = shared.snapshot()
            config = status.get("stream_config", {})
            query = parse_qs(urlparse(self.path).query)
            frame_id = int(query.get("frame_id", [status.get("frame_id", 0)])[0] or 0)
            body = json.dumps(
                build_mock_overlay(
                    frame_id=frame_id,
                    source_width=int(config.get("source_width", 4224)),
                    source_height=int(config.get("source_height", 3136)),
                ),
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_stream(self) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=safelabframe")
            self.end_headers()
            last_frame_id = -1
            while True:
                status = shared.snapshot()
                frame = status["frame"]
                frame_id = status["frame_id"]
                if frame is not None and frame_id != last_frame_id:
                    last_frame_id = frame_id
                    try:
                        self.wfile.write(b"--safelabframe\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                        self.wfile.write(frame)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        return
                time.sleep(0.03)

    return LivePreviewHandler


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve a board OV13855 camera MJPEG preview without saving frames.")
    parser.add_argument("--host", default=os.getenv("SAFELAB_BOARD_HOST", "192.168.0.232"))
    parser.add_argument("--username", default=os.getenv("SAFELAB_BOARD_USER", "root"))
    parser.add_argument("--password", default=os.getenv("SAFELAB_BOARD_PASSWORD", "root"))
    parser.add_argument("--device", default="/dev/video-camera0")
    parser.add_argument("--source-width", type=int, default=4224)
    parser.add_argument("--source-height", type=int, default=3136)
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--preview-width", type=int, default=960)
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--reconnect-delay", type=float, default=1.0)
    args = parser.parse_args()

    shared = SharedFrame(
        {
            "host": args.host,
            "device": args.device,
            "source_width": args.source_width,
            "source_height": args.source_height,
            "target_fps": args.fps,
            "preview_width": args.preview_width,
            "preview_height": _preview_height_for_width(args.source_width, args.source_height, args.preview_width),
            "reconnect_delay_seconds": args.reconnect_delay,
            "stale_after_seconds": max(2.0, args.reconnect_delay * 2),
            "transport": "ssh+gst+jpeg",
        }
    )
    stop_event = threading.Event()
    command = build_gstreamer_command(
        args.device,
        args.source_width,
        args.source_height,
        args.fps,
        args.preview_width,
    )
    reader = threading.Thread(
        target=frame_reader,
        args=(shared, stop_event, args.host, args.username, args.password, command, args.reconnect_delay),
        daemon=True,
    )
    reader.start()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(shared))

    def stop(_signum: int, _frame: Any) -> None:
        stop_event.set()
        server.shutdown()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    print(f"Live preview: http://127.0.0.1:{args.port}/", flush=True)
    print("Frames are streamed through memory; the board is not saving per-frame preview files.", flush=True)
    print(f"Remote command: {command}", flush=True)

    try:
        server.serve_forever()
    finally:
        stop_event.set()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

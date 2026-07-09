from __future__ import annotations

import json
import time
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from dashboard.input_source import build_input_source_state
from dashboard.model_detection import build_model_detection_state
from dashboard.scene_mode import build_scene_mode_state


ROOT = Path(__file__).resolve().parents[1]
DETECTION_DISPLAY_CONFIDENCE_FLOORS = {
    "fire": 0.45,
    "smoke": 0.45,
}
AI_EXPLANATION_DISPLAY_TTL_SECONDS = 60
SPEAKER_RECORD_DISPLAY_TTL_SECONDS = 180


def write_live_dashboard(
    events_path: str | Path = "data/events/events.jsonl",
    actions_path: str | Path = "data/events/alarm_actions.jsonl",
    actuator_path: str | Path = "data/events/actuator_log.jsonl",
    ai_explanations_path: str | Path = "data/events/ai_explanations.jsonl",
    voice_commands_path: str | Path = "data/events/voice_commands.jsonl",
    speech_output_path: str | Path = "data/events/speech_output.jsonl",
    xiaoduo_dialog_path: str | Path = "data/events/xiaoduo_dialog.jsonl",
    xiaoduo_state_path: str | Path = "data/runtime/xiaoduo_state.json",
    detections_path: str | Path = "reports/live_pipeline/live_dual_model_work/detections_window.jsonl",
    health_path: str | Path = "reports/health_check.json",
    video_config_path: str | Path = "configs/video_config.yaml",
    input_source_path: str | Path = "data/runtime/input_source.json",
    model_detection_path: str | Path = "data/runtime/model_detection.json",
    scene_mode_path: str | Path = "data/runtime/scene_mode.json",
    bridge_summary_path: str | Path = "reports/live_pipeline/live_dual_model/bridge_summary.json",
    output_path: str | Path = "reports/live_dashboard.html",
    state_path: str | Path = "reports/live_dashboard_state.json",
    max_items: int = 20,
) -> dict[str, str | int]:
    state = build_live_dashboard_state(
        events_path=events_path,
        actions_path=actions_path,
        actuator_path=actuator_path,
        ai_explanations_path=ai_explanations_path,
        voice_commands_path=voice_commands_path,
        speech_output_path=speech_output_path,
        xiaoduo_dialog_path=xiaoduo_dialog_path,
        xiaoduo_state_path=xiaoduo_state_path,
        detections_path=detections_path,
        health_path=health_path,
        video_config_path=video_config_path,
        input_source_path=input_source_path,
        model_detection_path=model_detection_path,
        scene_mode_path=scene_mode_path,
        bridge_summary_path=bridge_summary_path,
        max_items=max_items,
    )
    state_output = Path(state_path)
    html_output = Path(output_path)
    state_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.parent.mkdir(parents=True, exist_ok=True)
    state_output.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    html_output.write_text(_render_html(state, state_output.name), encoding="utf-8")
    return {
        "html": str(html_output),
        "state": str(state_output),
        "events": state["counts"]["events"],
        "actions": state["counts"]["actions"],
        "actuator_records": state["counts"]["actuator_records"],
        "ai_explanations": state["counts"]["ai_explanations"],
        "voice_commands": state["counts"]["voice_commands"],
        "speech_outputs": state["counts"]["speech_outputs"],
        "detections": state["counts"]["detections"],
    }


def build_live_dashboard_state(
    events_path: str | Path = "data/events/events.jsonl",
    actions_path: str | Path = "data/events/alarm_actions.jsonl",
    actuator_path: str | Path = "data/events/actuator_log.jsonl",
    ai_explanations_path: str | Path = "data/events/ai_explanations.jsonl",
    voice_commands_path: str | Path = "data/events/voice_commands.jsonl",
    speech_output_path: str | Path = "data/events/speech_output.jsonl",
    xiaoduo_dialog_path: str | Path = "data/events/xiaoduo_dialog.jsonl",
    xiaoduo_state_path: str | Path = "data/runtime/xiaoduo_state.json",
    detections_path: str | Path = "reports/live_pipeline/live_dual_model_work/detections_window.jsonl",
    health_path: str | Path = "reports/health_check.json",
    video_config_path: str | Path = "configs/video_config.yaml",
    input_source_path: str | Path = "data/runtime/input_source.json",
    model_detection_path: str | Path = "data/runtime/model_detection.json",
    scene_mode_path: str | Path = "data/runtime/scene_mode.json",
    bridge_summary_path: str | Path = "reports/live_pipeline/live_dual_model/bridge_summary.json",
    max_items: int = 20,
) -> dict[str, Any]:
    events = _read_jsonl(Path(events_path))
    actions = _read_jsonl(Path(actions_path))
    actuator_records = _read_jsonl(Path(actuator_path))
    ai_explanations = _read_jsonl(Path(ai_explanations_path))
    voice_commands = _read_jsonl(Path(voice_commands_path))
    speech_outputs = _read_jsonl(Path(speech_output_path))
    xiaoduo_dialog = _read_jsonl(Path(xiaoduo_dialog_path))
    xiaoduo_state = _read_json(Path(xiaoduo_state_path))
    detections = _read_jsonl(Path(detections_path))
    health = _read_json(Path(health_path))
    latest_events = events[-max_items:]
    latest_actions = actions[-max_items:]
    recent_speaker_records = _recent_speaker_records(speech_outputs, ttl_seconds=SPEAKER_RECORD_DISPLAY_TTL_SECONDS)
    latest_actuator = recent_speaker_records[-max_items:]
    latest_ai = _recent_ai_explanations(ai_explanations, ttl_seconds=AI_EXPLANATION_DISPLAY_TTL_SECONDS)[-max_items:]
    latest_voice_commands = voice_commands[-max_items:]
    latest_speech_outputs = speech_outputs[-max_items:]
    latest_xiaoduo_dialog = xiaoduo_dialog[-max_items:]
    latest_detections = _enrich_detections(detections[-max_items:])
    bridge_summary = _read_json(Path(bridge_summary_path))
    board_live_frame = _board_live_frame(bridge_summary)
    active_live_frame = _active_live_frame(bridge_summary)
    source_state = build_input_source_state(video_config_path, input_source_path)
    model_detection_state = build_model_detection_state(model_detection_path)
    scene_mode_state = build_scene_mode_state(scene_mode_path)
    state = {
        "counts": {
            "events": len(events),
            "actions": len(actions),
            "actuator_records": len(recent_speaker_records),
            "ai_explanations": len(ai_explanations),
            "voice_commands": len(voice_commands),
            "speech_outputs": len(speech_outputs),
            "xiaoduo_dialog": len(xiaoduo_dialog),
            "detections": len(detections),
            "high_risk_events": sum(1 for event in events if event.get("risk_level") in ("high", "emergency")),
        },
        "health": health,
        "latest_events": latest_events,
        "latest_actions": latest_actions,
        "latest_actuator_records": latest_actuator,
        "latest_ai_explanations": latest_ai,
        "latest_voice_commands": latest_voice_commands,
        "latest_speech_outputs": latest_speech_outputs,
        "latest_xiaoduo_dialog": latest_xiaoduo_dialog,
        "xiaoduo_state": xiaoduo_state,
        "latest_detections": latest_detections,
        "board_live_frame": board_live_frame,
        "active_live_frame": active_live_frame,
        "status": _status(events, health),
    }
    state.update(source_state)
    state.update(model_detection_state)
    state.update(scene_mode_state)
    return state


def _recent_ai_explanations(rows: list[dict[str, Any]], *, ttl_seconds: int) -> list[dict[str, Any]]:
    cutoff = time.time() - ttl_seconds
    recent: list[dict[str, Any]] = []
    for row in rows:
        timestamp = row.get("timestamp")
        if timestamp is None:
            recent.append(row)
            continue
        try:
            if float(timestamp) >= cutoff:
                recent.append(row)
        except (TypeError, ValueError):
            recent.append(row)
    return recent


def _recent_speaker_records(rows: list[dict[str, Any]], *, ttl_seconds: int) -> list[dict[str, Any]]:
    cutoff = time.time() - ttl_seconds
    recent: list[dict[str, Any]] = []
    for row in rows:
        if row.get("speech_source") != "risk_voice_alarm":
            continue
        timestamp = _safe_float(row.get("timestamp"))
        if timestamp is not None and timestamp < cutoff:
            continue
        recent.append(_speaker_record_to_actuator(row))
    return recent


def _speaker_record_to_actuator(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": row.get("event_id") or "speaker",
        "timestamp": row.get("timestamp"),
        "backend": "speaker",
        "voice_text": row.get("text", ""),
        "speaker": {
            "enabled": True,
            "executed": bool(row.get("executed")),
            "device": row.get("device", ""),
            "detail": row.get("detail", ""),
        },
    }


def _safe_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _board_live_frame(bridge_summary: dict[str, Any]) -> dict[str, Any]:
    if bridge_summary.get("source_type") != "board_file":
        return {}
    return _active_live_frame(bridge_summary)


def _active_live_frame(bridge_summary: dict[str, Any]) -> dict[str, Any]:
    source_type = str(bridge_summary.get("source_type", ""))
    if source_type not in {"camera", "file", "board_file"}:
        return {}
    frame = bridge_summary.get("frame")
    if not isinstance(frame, dict):
        return {}
    frame_path = frame.get("frame_path")
    if not frame_path:
        return {}
    item = {
        "source_type": source_type,
        "source_key": str(bridge_summary.get("source_key", "")),
        "frame_path": str(frame_path),
        "image_url": "/detection-image?path=" + quote(str(frame_path), safe=""),
    }
    try:
        item["frame_id"] = int(bridge_summary.get("detection_frame_id", 0) or 0)
    except (TypeError, ValueError):
        pass
    return item


def _enrich_detections(detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for detection in detections:
        if not _should_show_detection(detection):
            continue
        item = dict(detection)
        image_path = _detection_image_path(item)
        if image_path:
            item["image_url"] = "/detection-image?path=" + quote(str(image_path), safe="")
        enriched.append(item)
    return enriched


def _should_show_detection(detection: dict[str, Any]) -> bool:
    class_name = str(detection.get("class_name", ""))
    confidence_floor = DETECTION_DISPLAY_CONFIDENCE_FLOORS.get(class_name)
    if confidence_floor is None:
        return True
    try:
        confidence = float(detection.get("confidence", 0.0))
    except (TypeError, ValueError):
        return False
    return confidence >= confidence_floor


def _detection_image_path(detection: dict[str, Any]) -> str:
    for key in ("image_path", "source_image", "frame_path"):
        value = detection.get(key)
        if value:
            return str(value)
    return ""


def resolve_detection_image_path(path_value: str | Path) -> Path:
    path = Path(str(path_value))
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _status(events: list[dict[str, Any]], health: dict[str, Any]) -> dict[str, str]:
    if any(event.get("risk_level") in ("high", "emergency") for event in events[-5:]):
        risk_state = "alarm"
    elif events:
        risk_state = "watching"
    else:
        risk_state = "idle"
    return {
        "risk_state": risk_state,
        "fallback_mode": str(health.get("fallback_mode", "unknown")),
        "camera": str(health.get("camera", "unknown")),
        "ov13855": str(health.get("ov13855", "unknown")),
        "python": str(health.get("python", "unknown")),
    }


def _render_html(initial_state: dict[str, Any], state_filename: str) -> str:
    initial_json = json.dumps(initial_state, ensure_ascii=False)
    template = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SafeLab-Vision Pro 视觉风险认知中枢 | SafeLab 实时演示看板</title>
  <style>
    * { box-sizing: border-box; }
    :root { --bg:#f5f7fb; --rail:#ffffff; --panel:#ffffff; --panel-strong:#f8fbff; --line:#d8e0ea; --muted:#64748b; --text:#172033; --gold:#d99a19; --blue:#2563eb; --green:#0f9f6e; --red:#dc2626; --amber:#b7791f; }
    body { margin:0; min-height:100vh; color:var(--text); background:#f5f7fb; font-family:"Segoe UI",Tahoma,sans-serif; letter-spacing:0; overflow-x:hidden; }
    button { font:inherit; }
    .shell { display:grid; grid-template-columns:224px 1fr; min-height:100vh; transition:grid-template-columns .18s ease; }
    .shell.rail-collapsed { grid-template-columns:68px 1fr; }
    .rail { background:var(--rail); border-right:1px solid var(--line); padding:14px 10px; display:flex; flex-direction:column; gap:12px; box-shadow:8px 0 24px rgba(15,23,42,.05); }
    .brand { min-height:44px; display:grid; grid-template-columns:34px 1fr 30px; gap:8px; align-items:center; }
    .brand-mark,.nav-icon { width:34px; height:34px; border-radius:7px; display:grid; place-items:center; background:#eef4ff; color:var(--blue); font-weight:700; }
    .brand-title strong { display:block; font-size:14px; } .brand-title span { color:var(--muted); font-size:11px; }
    .rail-toggle { width:30px; height:30px; border:1px solid var(--line); border-radius:6px; color:var(--text); background:#f8fafc; cursor:pointer; }
    .nav { display:grid; gap:6px; }
    .nav-item { min-height:42px; border:0; border-radius:7px; color:var(--text); background:transparent; display:grid; grid-template-columns:34px 1fr; gap:10px; align-items:center; text-align:left; cursor:pointer; }
    .nav-item.active { background:#eaf2ff; color:#0f3f8f; } .nav-item.active .nav-icon { background:var(--blue); color:#fff; }
    .nav-label { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .shell.rail-collapsed .brand-title,.shell.rail-collapsed .nav-label { display:none; }
    .shell.rail-collapsed .brand { grid-template-columns:34px; justify-content:center; }
    .content { padding:18px; min-width:0; }
    .topbar { min-height:64px; display:flex; gap:14px; justify-content:space-between; align-items:center; margin-bottom:14px; }
    h1 { margin:0; font-size:28px; line-height:1.05; } h2 { margin:0 0 10px; font-size:15px; }
    .subtitle,.muted { color:var(--muted); font-size:13px; } .subtitle { margin-top:5px; }
    .top-actions { display:flex; gap:10px; align-items:center; flex-wrap:wrap; justify-content:flex-end; }
    .product-kicker { color:var(--green); font-size:12px; font-weight:700; margin-bottom:6px; }
    .ops-strip { display:flex; flex-wrap:wrap; gap:8px; margin:10px 0 14px; }
    .ops-chip { min-height:30px; display:inline-flex; align-items:center; gap:6px; padding:5px 10px; border:1px solid #c7d7fe; border-radius:7px; color:#1e3a8a; background:#eff6ff; font-size:12px; font-weight:700; }
    .ops-chip.critical { border-color:#fed7aa; background:#fff7ed; color:#9a3412; }
    .ops-chip.ready { border-color:#bbf7d0; background:#f0fdf4; color:#166534; }
    .segmented { display:inline-grid; grid-template-columns:repeat(2,minmax(84px,1fr)); gap:4px; padding:4px; background:#eef2f7; border:1px solid var(--line); border-radius:7px; }
    .source-button { min-height:34px; border:0; border-radius:5px; color:var(--muted); background:transparent; }
    .source-button.active { background:var(--blue); color:#fff; font-weight:700; }
    .pill { min-height:32px; display:inline-flex; align-items:center; padding:5px 10px; border:1px solid var(--line); border-radius:999px; color:var(--muted); background:#fff; font-size:12px; }
    .workspace { display:block; }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; min-width:0; box-shadow:0 18px 40px rgba(15,23,42,.08); }
    .view { display:none; }
    .view.active-view { display:block; }
    .video-stage { aspect-ratio:16/9; min-height:250px; min-width:0; max-width:100%; border:1px solid #3d5063; border-radius:8px; background:linear-gradient(135deg,rgba(74,163,255,.13),transparent 30%),repeating-linear-gradient(0deg,#07090b 0,#07090b 14px,#0c1014 15px); display:grid; place-items:center; color:#6f7e8e; font-weight:700; overflow:hidden; position:relative; }
    .video-stage img { width:100%; height:100%; object-fit:cover; display:block; }
    .detection-overlay { position:absolute; inset:0; pointer-events:none; z-index:3; }
    .detection-box { position:absolute; border:2px solid #38bdf8; border-radius:4px; box-shadow:0 0 0 1px rgba(8,13,19,.5),0 10px 24px rgba(15,23,42,.2); }
    .detection-box.fire,.detection-box.smoke { border-color:#ef4444; }
    .detection-box.helmet,.detection-box.vest,.detection-box.goggles,.detection-box.gloves { border-color:#22c55e; }
    .detection-label { position:absolute; left:0; top:-24px; max-width:180px; padding:3px 6px; border-radius:4px; background:rgba(8,13,19,.82); color:#fff; font-size:12px; line-height:1.2; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .detection-thumb { position:relative; width:min(260px,100%); aspect-ratio:16/9; margin:8px 0; overflow:hidden; border:1px solid var(--line); border-radius:7px; background:#0f172a; }
    .detection-thumb img { width:100%; height:100%; object-fit:contain; display:block; }
    .detection-thumb .detection-overlay { z-index:2; }
    .video-caption { position:absolute; left:12px; bottom:10px; padding:5px 9px; border-radius:999px; background:rgba(7,9,11,.72); color:#dce6ea; font-size:12px; font-weight:600; }
    .stage-hud { position:absolute; top:12px; right:12px; display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end; }
    .stage-hud span { padding:5px 8px; border-radius:6px; background:rgba(8,13,19,.76); border:1px solid rgba(238,245,248,.16); color:#dcefff; font-size:12px; }
    .metrics { display:grid; grid-template-columns:repeat(5,minmax(90px,1fr)); gap:8px; margin-top:10px; }
    .metric,.row { background:#f8fafc; border:1px solid var(--line); border-radius:7px; padding:9px; }
    .metric { min-height:62px; color:var(--muted); font-size:12px; } .metric strong { display:block; margin-top:4px; color:var(--text); font-size:22px; }
    .ai-panel { background:#fffaf0; border-color:#f3d7a5; }
    .ai-latest { min-height:148px; border-left:3px solid var(--gold); padding:10px 12px; background:rgba(214,180,91,.08); border-radius:6px; }
    .ai-latest strong { color:var(--gold); }
    .list { display:grid; gap:8px; } .row { font-size:13px; } .row .meta { color:var(--muted); font-size:12px; margin-bottom:4px; }
    .reason-lines { display:grid; gap:5px; line-height:1.55; }
    .reason-title { font-weight:700; color:var(--text); }
    .reason-line strong { color:var(--muted); margin-right:4px; }
    .level-high,.level-emergency { color:var(--red); font-weight:700; } .level-warning { color:var(--gold); font-weight:700; }
    .notice { color:var(--green); min-height:18px; font-size:12px; }
    .danger { color:var(--red); }
    .section-note { color:var(--muted); font-size:12px; margin-top:-5px; margin-bottom:10px; }
    #panel-local-media .section-note, #runtime { display:none; }
    .evidence-dock { display:grid; grid-template-columns:repeat(3,minmax(90px,1fr)); gap:8px; margin-top:10px; }
    .evidence-dock div { border:1px solid var(--line); border-radius:7px; padding:8px; background:#f8fafc; color:var(--muted); font-size:12px; }
    .local-media-grid { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:14px; align-items:start; }
    .local-input-column,.local-result-column { min-width:0; }
    .local-preview-stage,.local-result-stage { position:relative; width:100%; aspect-ratio:16/9; border:1px solid var(--line); border-radius:8px; background:#0f172a; overflow:hidden; }
    .local-result-stage { display:grid; place-items:center; }
    .local-media-preview { width:100%; height:100%; border:0; background:#0f172a; display:block; object-fit:contain; }
    .file-picker { display:grid; gap:10px; padding:12px; border:1px dashed #94a3b8; border-radius:8px; background:#f8fafc; }
    .evidence-dock strong { display:block; color:var(--text); margin-bottom:3px; }
    .side-stack { display:grid; gap:14px; }
    @media (max-width:980px) { .shell,.shell.rail-collapsed { grid-template-columns:1fr; } .rail { position:sticky; top:0; z-index:2; flex-direction:row; overflow-x:auto; max-width:100vw; } .brand { min-width:180px; } .nav { display:flex; flex:0 0 auto; } .nav-item { min-width:46px; } .workspace { grid-template-columns:1fr; } .local-media-grid { grid-template-columns:1fr; } .metrics { grid-template-columns:repeat(2,minmax(120px,1fr)); } .shell.rail-collapsed .brand-title,.shell.rail-collapsed .nav-label { display:block; } }
    @media (max-width:520px) { .rail { flex-direction:column; gap:8px; overflow-x:hidden; } .brand { min-width:0; width:100%; } .nav { width:100%; display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); } .nav-item { min-width:0; grid-template-columns:1fr; justify-items:center; } .nav-label { display:none !important; } .content { padding:14px; } .topbar { align-items:flex-start; flex-direction:column; } .top-actions { justify-content:flex-start; width:100%; } .segmented { width:100%; grid-template-columns:repeat(2,minmax(0,1fr)); } .source-button { min-width:0; white-space:normal; line-height:1.25; } .panel { padding:12px; } .video-stage { min-height:180px; aspect-ratio:16/10; } .stage-hud { left:10px; right:10px; justify-content:flex-start; } .stage-hud span { max-width:100%; overflow:hidden; text-overflow:ellipsis; } .evidence-dock { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <div class="shell" id="shell">
    <aside class="rail">
      <div class="brand">
        <div class="brand-mark">S</div>
        <div class="brand-title"><strong>SafeLab-Vision Pro</strong><span>AI 证据链</span></div>
        <button class="rail-toggle" id="rail-toggle" title="折叠菜单" type="button">&lt;</button>
      </div>
      <nav class="nav" aria-label="SafeLab 功能区">
        <button class="nav-item active" data-panel-target="panel-live" type="button"><span class="nav-icon">实</span><span class="nav-label">实时</span></button>
        <button class="nav-item" data-panel-target="panel-ai" type="button"><span class="nav-icon">AI</span><span class="nav-label">智能说明</span></button>
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
          <div class="subtitle">视觉风险认知中枢 · SafeLab 实时演示看板 · 板端画面、AI 说明、风险事件与告警证据链。</div>
        </div>
        <div class="top-actions">
          <div class="segmented" id="source-selector" aria-label="输入源">
            <button class="source-button" data-source-id="camera_ov13855" type="button">摄像头输入</button>
            <button class="source-button" data-source-id="board_file_demo" type="button">本地视频</button>
          </div>
          <span class="pill" id="risk-pill">风险：加载中</span>
          <span class="pill" id="updated">等待数据</span>
        </div>
      </header>
      <div class="ops-strip" id="panel-settings" aria-label="系统能力">
        <span class="ops-chip ready">RK3588 NPU</span>
        <span class="ops-chip ready">低延迟模式</span>
        <span class="ops-chip">摄像头输入</span>
        <span class="ops-chip">本地输入</span>
        <span class="ops-chip critical">最新帧优先</span>
      </div>
      <div class="notice" id="source-message"></div>
      <div class="workspace">
        <section class="panel view active-view" id="panel-live" data-view="panel-live">
          <h2>实时视频与检测框</h2>
          <div class="section-note">视觉输入、目标框、危险 ROI 与规则结果同屏叠加。</div>
          <div class="video-stage">
            <img id="camera-preview" src="http://127.0.0.1:8090/frame.jpg" alt="板端相机画面">
            <div class="detection-overlay" id="detection-overlay"></div>
            <div class="stage-hud"><span>摄像头输入</span><span>风险叠加</span><span>危险区域</span></div>
            <span class="video-caption">板端相机画面</span>
            <span id="video-fallback" style="display:none">等待板端相机预览图</span>
          </div>
          <div class="metrics" id="metrics"></div>
          <div class="evidence-dock" aria-label="证据链">
            <div><strong>证据链</strong>事件、动作、执行器联动</div>
            <div><strong>事件生命线</strong>从可疑到闭环</div>
            <div><strong>端侧闭环</strong>检测、警报、记录</div>
          </div>
        </section>
        <div class="side-stack">
          <section class="panel view ai-panel" id="panel-ai" data-view="panel-ai"><h2>智能说明 / 风险判定</h2><div class="section-note">AI 摘要与现场处置建议。</div><div id="ai"></div></section>
          <section class="panel view" id="panel-events" data-view="panel-events"><h2>事件生命线</h2><div class="section-note">风险时间线</div><div id="events"></div></section>
          <section class="panel view" id="panel-detections" data-view="panel-detections"><h2>检测记录</h2><div class="section-note">模型原始检测流水</div><div id="detections"></div></section>
          <section class="panel view" id="panel-evidence" data-view="panel-evidence"><h2>证据链</h2><div class="section-note">告警证据链</div><div id="actions"></div></section>
          <section class="panel view" id="panel-reports" data-view="panel-reports"><h2>执行器记录</h2><div id="actuator"></div></section>
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
    const INITIAL_STATE = __INITIAL_JSON__;
    const STATE_URL = "__STATE_URL__";
    const CAMERA_LIVE_FRAME_URL = "http://127.0.0.1:8090/frame.jpg";
    const CAMERA_SNAPSHOT_URL = "board_camera_preview.jpg";
    let usingCameraSnapshotFallback = false;
    const shell = document.getElementById("shell");
    const railToggle = document.getElementById("rail-toggle");
    railToggle.addEventListener("click", () => {
      shell.classList.toggle("rail-collapsed");
      railToggle.textContent = shell.classList.contains("rail-collapsed") ? ">" : "<";
    });
    let latestDashboardState = null;
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
      document.getElementById("runtime").textContent =
        `运行 ${statusText(status.fallback_mode)} | 相机 ${statusText(status.camera)} | OV13855 ${statusText(status.ov13855)} | Python ${statusText(status.python)}`;
      renderSourceButtons(state.input_source || {});
      refreshCameraPreview();
      renderDetectionOverlay(state.latest_detections || [], state.input_source || {});
      document.getElementById("metrics").innerHTML = [
        ["事件", counts.events || 0],
        ["检测", counts.detections || 0],
        ["动作", counts.actions || 0],
        ["执行记录", counts.actuator_records || 0],
        ["AI 说明", counts.ai_explanations || 0],
        ["高风险", counts.high_risk_events || 0],
      ].map(([k, v]) => `<div class="metric">${esc(k)}<strong>${esc(v)}</strong></div>`).join("");
      document.getElementById("events").innerHTML = eventList(state.latest_events || []);
      document.getElementById("detections").innerHTML = detectionList(state.latest_detections || []);
      document.getElementById("ai").innerHTML = aiPanel(state.latest_ai_explanations || []);
      document.getElementById("actions").innerHTML = actionList(state.latest_actions || []);
      document.getElementById("actuator").innerHTML = actuatorList(state.latest_actuator_records || []);
      requestAnimationFrame(syncDetectionThumbs);
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
    function setupDashboardInteractions() {
      document.querySelectorAll("[data-panel-target]").forEach(button => {
        button.addEventListener("click", () => activatePanel(button.dataset.panelTarget));
      });
      const localMediaInput = document.getElementById("local-media-file");
      if (localMediaInput) localMediaInput.addEventListener("change", previewLocalMedia);
      document.getElementById("source-selector").addEventListener("click", event => {
        const button = event.target.closest("button[data-source-id]");
        if (!button) return;
        activatePanel(sourcePanelForSource(button.dataset.sourceId));
        renderSourceButtons({ selected_source: button.dataset.sourceId });
        const message = document.getElementById("source-message");
        if (message) message.textContent = button.textContent.trim() + " 已选中";
      });
    }
    function activatePanel(panelId) {
      if (!showView(panelId)) return;
      document.querySelectorAll("[data-panel-target]").forEach(button => {
        button.classList.toggle("active", button.dataset.panelTarget === panelId);
      });
      const target = document.getElementById(panelId);
      target.scrollIntoView({ behavior: "smooth", block: "start" });
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
    function statusText(value) {
      const raw = text(value);
      const lower = raw.toLowerCase();
      const labels = { alarm: "告警", watching: "观察中", idle: "空闲", high: "高风险", emergency: "紧急", warning: "预警", present: "已连接", ok: "正常", not_ready: "未就绪", missing: "缺失", unknown: "未知", "shell_only+mock_detection": "Shell+模拟检测" };
      return labels[lower] || raw;
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
      restoreCameraLivePreview();
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
        <div class="row"><div class="meta">帧 ${esc(r.frame_id)} | ${esc(eventTypeText(r.event_type))} | <span class="level-${esc(r.risk_level)}">${esc(statusText(r.risk_level))}</span></div>${renderReasonLines(r.reasons || [])}</div>`).join("")}</div>`;
    }
    function aiPanel(rows) {
      if (!rows.length) return '<div class="ai-latest"><strong>暂无 AI 说明。</strong><p class="muted">生成 AI 说明后，这里会自动显示最新解释。</p></div>';
      const latest = rows[rows.length - 1] || {};
      return `<div class="ai-latest"><strong>${esc(aiSourceText(latest.source || "AI"))} | ${esc(latest.event_id || "最新")}</strong><p>${esc(translateVoice(latest.summary || latest.voice_text || "暂无摘要。"))}</p><p class="muted">${esc(translateVoice(latest.recommendation || latest.voice_text || ""))}</p></div>`;
    }
    function actionList(rows) {
      if (!rows.length) return '<p class="muted">暂无告警动作。</p>';
      return `<div class="list">${rows.slice(-4).reverse().map(r => `<div class="row"><div class="meta">${esc(r.event_id)} | 灯光 ${esc(colorText(r.led_color))} | 蜂鸣 ${esc(booleanText(r.buzzer))}</div>${esc(translateVoice(r.voice_text || ""))}</div>`).join("")}</div>`;
    }
    function actuatorList(rows) {
      if (!rows.length) return '<p class="muted">暂无执行器记录。</p>';
      return `<div class="list">${rows.slice(-4).reverse().map(r => `<div class="row"><div class="meta">${esc(r.event_id)} | ${esc(r.backend)}</div>灯光 ${esc(colorText((r.led || {}).color))} | 蜂鸣 ${esc(booleanText((r.buzzer || {}).enabled))} | 继电器 ${esc(booleanText((r.relay || {}).enabled))}</div>`).join("")}</div>`;
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
    function eventTypeText(value) {
      const labels = { smoke: "烟雾", fire: "火焰", ppe_violation: "防护违规" };
      return labels[text(value)] || text(value);
    }
    function colorText(value) {
      const labels = { red: "红色", yellow: "黄色", green: "绿色" };
      return labels[text(value)] || text(value);
    }
    function booleanText(value) {
      return value === true || value === "true" ? "开启" : value === false || value === "false" ? "关闭" : text(value);
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
    function translateVoice(value) {
      let textValue = text(value);
      textValue = textValue.replace(/Fire risk detected\\. Please check the lab immediately\\.?/g, "检测到火焰风险，请立即复核现场。");
      textValue = textValue.replace(/Smoke risk detected\\. Please check the lab\\.?/g, "检测到烟雾风险，请立即复核现场。");
      textValue = textValue.replace(/Goggles missing in welding zone\\. Please wear eye protection\\.?/g, "焊接区域缺少护目镜，请佩戴眼部防护。");
      textValue = textValue.replace(/Helmet missing in danger zone\\. Please correct immediately\\.?/g, "危险区域缺少安全帽，请立即纠正。");
      textValue = textValue.replace(/smoke 风险等级为 high，原因：连续 3 帧检测到烟雾。/g, "烟雾风险等级为高，原因：连续 3 帧检测到烟雾。");
      textValue = textValue.replace(/smoke 风险等级为 high，原因：smoke appeared for 3 consecutive frames。/g, "烟雾风险等级为高，原因：连续 3 帧检测到烟雾。");
      textValue = textValue.replace(/high风险/g, "高风险");
      return translateReason(textValue);
    }
    function restoreCameraLivePreview() {
      const image = document.getElementById("camera-preview");
      const fallback = document.getElementById("video-fallback");
      if (!image || usingCameraSnapshotFallback) return;
      image.style.display = "block";
      if (fallback) fallback.style.display = "none";
      if (!image.getAttribute("src") || image.getAttribute("src").startsWith("/detection-image")) {
        image.src = CAMERA_LIVE_FRAME_URL + "?t=" + Date.now();
      }
    }
    function refreshCameraPreview() {
      const image = document.getElementById("camera-preview");
      if (!image || image.style.display === "none") return;
      const fallback = document.getElementById("video-fallback");
      // Prefer the in-memory live stream; fall back to the last pulled board snapshot for offline review.
      image.onerror = () => {
        if (!usingCameraSnapshotFallback) {
          usingCameraSnapshotFallback = true;
          image.src = CAMERA_SNAPSHOT_URL + "?t=" + Date.now();
          return;
        }
        image.style.display = "none";
        if (fallback) fallback.style.display = "block";
      };
      image.onload = () => {
        image.style.display = "block";
        if (fallback) fallback.style.display = "none";
      };
      const source = usingCameraSnapshotFallback ? CAMERA_SNAPSHOT_URL : CAMERA_LIVE_FRAME_URL;
      image.src = source + "?t=" + Date.now();
    }
    async function refresh() {
      try {
        const response = await fetch(STATE_URL + "?t=" + Date.now(), { cache: "no-store" });
        if (response.ok) render(await response.json());
        else render(INITIAL_STATE);
      } catch (error) {
        render(INITIAL_STATE);
      }
    }
    render(INITIAL_STATE);
    setInterval(refresh, 1000);
    refresh();
  </script>
</body>
</html>
"""
    return template.replace("__INITIAL_JSON__", initial_json).replace("__STATE_URL__", escape(state_filename))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"parse_error": line})
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

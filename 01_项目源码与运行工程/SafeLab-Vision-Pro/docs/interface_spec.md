# Interface Spec

All modules must pass structured objects instead of temporary dictionaries.

## VideoFrame

```json
{
  "frame_id": 123,
  "source_type": "camera",
  "timestamp": 1710000000.123,
  "width": 1280,
  "height": 720,
  "source_name": "ov13855_video21"
}
```

`frame` is an in-memory OpenCV BGR image object and is not written to JSON logs.

Allowed `source_type` values:

```text
camera, hdmi, file, mock
```

## Detection

```json
{
  "frame_id": 123,
  "source_type": "camera",
  "class_name": "person",
  "confidence": 0.91,
  "bbox": [100, 150, 300, 620],
  "center": [200, 385],
  "area": 94000,
  "model_name": "safelab_yolo_rknn",
  "infer_time_ms": 22.8
}
```

Allowed `class_name` values:

```text
person, helmet, vest, goggles, gloves, fire, smoke
```

Common YOLO/RKNN postprocess outputs should be adapted before they enter the
rule engine:

```text
[x1, y1, x2, y2, confidence, class_id] -> Detection
{"bbox": [...], "score": 0.91, "class_id": 0} -> Detection
```

The stable label order is:

```text
0 person, 1 helmet, 2 vest, 3 goggles, 4 gloves, 5 fire, 6 smoke
```

Use `ai_engine/detection_adapter.py` for this conversion so the downstream
PPE association, zone rules, temporal logic, and alarms do not depend on a
specific model runtime.

## PersonTrack

```json
{
  "track_id": 1,
  "frame_id": 123,
  "bbox": [100, 150, 300, 620],
  "zone_id": "danger_zone",
  "has_helmet": false,
  "has_vest": true,
  "has_goggles": true,
  "has_gloves": false,
  "ppe_status": "helmet_missing",
  "risk_state": "suspicious",
  "hit_count": 3,
  "miss_count": 0,
  "last_update_ts": 1710000000.233
}
```

## FireSmokeTrack

```json
{
  "track_id": 10,
  "frame_id": 223,
  "class_name": "smoke",
  "bbox": [400, 120, 700, 360],
  "confidence": 0.76,
  "appear_count": 4,
  "area_history": [3200, 3600, 4200],
  "state": "confirmed",
  "risk_level": "high"
}
```

## TrackManager

`TrackManager` assigns stable `track_id` values to person detections across frames using lightweight bbox IoU matching. It emits `PersonTrack` records for risk logic and reports.

```json
{
  "track_id": 1,
  "frame_id": 3,
  "zone_id": "danger_zone",
  "ppe_status": "helmet_goggles_gloves_missing",
  "risk_state": "confirmed",
  "hit_count": 3,
  "miss_count": 0
}
```

`risk_state` becomes `confirmed` after the configured consecutive hit count.

## ROIRegion

`ROIManager` converts risky tracks or risk bboxes into bounded regions for low-latency inference. The ROI bbox is always in full-frame coordinates and must be clipped to the source frame size. Detections produced on cropped ROI images must be mapped back to full-frame coordinates before entering the rule engine.

```json
{
  "roi_id": "ROI_F12_T1_80_70_340_620",
  "frame_id": 12,
  "bbox": [80, 70, 340, 620],
  "source_bbox": [100, 120, 300, 520],
  "frame_width": 1280,
  "frame_height": 720,
  "reason": "track:1:confirmed:helmet_missing",
  "margin_ratio": 0.2,
  "source_track_id": 1
}
```

## RiskEvent

```json
{
  "event_id": "E20260509_0001",
  "frame_id": 123,
  "source_type": "camera",
  "event_type": "ppe_violation",
  "risk_score": 72,
  "risk_level": "high",
  "reasons": [
    "person entered danger zone",
    "helmet missing",
    "duration exceeded 3 seconds"
  ],
  "bbox": [100, 150, 300, 620],
  "need_alarm": true,
  "need_snapshot": true,
  "need_log": true,
  "timestamp": 1710000000.333,
  "rule_id": "R001",
  "action_hint": {
    "voice": "Helmet missing in danger zone.",
    "led": "red",
    "buzzer": true,
    "snapshot": true,
    "log": true
  }
}
```

Allowed `event_type` values:

```text
ppe_violation, forbidden_intrusion, smoke, fire
```

Allowed `risk_level` values:

```text
normal, notice, warning, high, emergency
```

## AlarmAction

```json
{
  "event_id": "E20260509_0001",
  "voice_text": "Helmet missing in danger zone.",
  "led_color": "red",
  "buzzer": true,
  "relay": false,
  "snapshot": true,
  "log": true,
  "cooldown_ms": 20000
}
```

## Evidence Log

`EventLogger` writes append-only JSONL evidence and mirrors the same records into
SQLite for structured event review:

```text
data/events/events.jsonl
data/events/alarm_actions.jsonl
data/events/alarm_log.db
```

The SQLite database contains:

```text
events(event_id, frame_id, source_type, event_type, risk_score, risk_level, timestamp, payload_json)
alarm_actions(event_id, voice_text, led_color, buzzer, relay, snapshot, log, cooldown_ms, payload_json)
```

`payload_json` preserves the full interface payload so SQLite queries and JSONL
replay stay consistent.

## Actuator Backend

Alarm execution uses a replaceable backend contract. `mock` writes JSONL evidence,
`shell` records planned shell actions without touching hardware, and `gpio`
records pin mapping intent until physical wiring is confirmed.

```json
{
  "event_id": "E20260509_0001",
  "backend": "gpio",
  "led": {"enabled": true, "color": "red"},
  "buzzer": {"enabled": true},
  "relay": {"enabled": false},
  "executed": false,
  "pin_config": {
    "led_red": 17,
    "led_yellow": 22,
    "buzzer": 18,
    "relay": 27
  }
}
```

Allowed backend values:

```text
mock, shell, gpio
```

## TimelineEvent

```json
{
  "event_id": "E20260509_0001",
  "stage": "confirmed",
  "timestamp": 1710000000.520,
  "detail": "3 consecutive smoke frames confirmed risk",
  "frame_id": 203
}
```

## Contract Rules

- Keep `frame_id`, `source_type`, and `timestamp` through the whole pipeline.
- `VideoFrame.frame` is internal runtime data. Logs and reports should store metadata, snapshots, or derived detections instead.
- Every `RiskEvent` must include at least one human-readable reason.
- `rule_id` and `action_hint` are optional. Rule DSL events should provide them so alarm actions can follow configured policies.
- Track lifecycle states use `normal`, `suspicious`, `confirmed`, `alarmed`, `recovered`, and `closed`.
- Interface changes must update this file and `tests/test_interface_contract.py`.

## HealthStatus

```json
{
  "camera": "present",
  "hdmi_capture": "missing",
  "rknn_model": "missing",
  "database": "ok",
  "gpio": "missing",
  "audio": "missing",
  "storage_free_mb": 53895,
  "fallback_mode": "shell_only+mock_detection",
  "python": "missing",
  "v4l2_ctl": "ok",
  "media_ctl": "ok",
  "ov13855": "ready",
  "preferred_camera": "ok"
}
```

Allowed `fallback_mode` values:

```text
none, shell_only, mock_detection, shell_only+mock_detection
```

## Runtime Scheduling

`FrameScheduler` decides whether the current latest frame should be processed.
It keeps normal scenes low frequency, raises suspicious scenes to high frequency,
and can switch to ROI mode when a risk area is already known.

```json
{
  "frame_id": 8,
  "runtime_state": "suspicious",
  "should_process": true,
  "mode": "roi",
  "reason": "suspicious state uses every 1 frame(s)"
}
```

Allowed `runtime_state` values:

```text
normal, suspicious, alarmed
```

Allowed scheduler `mode` values:

```text
full_frame, roi
```

## Async Event Bus

`AsyncEventBus` is used for non-blocking side effects such as logging, snapshots,
alarm execution, and dashboard pushes. It uses a bounded latest-only queue:
when the queue is full, the oldest pending event is dropped instead of blocking
the frame path.

```json
{
  "topic": "risk_event",
  "sequence": 12,
  "payload": {
    "event_id": "E20260509_0001",
    "risk_level": "high"
  }
}
```

Runtime bus stats:

```json
{
  "published_count": 10,
  "consumed_count": 3,
  "dropped_count": 7,
  "pending_count": 0
}
```

## Fallback Decision

`FallbackManager` converts device health into a deterministic runtime mode.
This keeps the system runnable when Python, camera, model, or hardware outputs
are missing.

```json
{
  "mode": "shell_only+mock_detection",
  "can_run_pipeline": true,
  "use_mock_detection": true,
  "use_shell_tools": true,
  "reasons": [
    "python runtime missing; use shell-only board checks",
    "ov13855 sensor not ready; use mock detection input",
    "rknn model missing; use mock detection input"
  ]
}
```

## Watchdog

`Watchdog` records worker heartbeats and marks stale or missing workers.

```json
{
  "timeout_ms": 1000.0,
  "healthy": false,
  "workers": [
    {"name": "capture_worker", "age_ms": 200.0, "healthy": true, "detail": "heartbeat fresh"},
    {"name": "event_worker", "age_ms": 2200.0, "healthy": false, "detail": "heartbeat stale"}
  ]
}
```

## Runtime Main Loop

`RuntimeMainLoop` wires the non-model runtime modules into a long-running path:

```text
VideoSource -> LatestFrameBuffer -> FrameScheduler -> Detector
-> RuleDslEngine -> AlarmManager -> EventLogger / AsyncEventBus
-> PipelineProfiler -> Watchdog
```

The mock main-loop smoke report stores:

```json
{
  "frames_read": 8,
  "frames_processed": 5,
  "frames_skipped": 3,
  "events": 2,
  "actions": 2,
  "watchdog_healthy": true
}
```

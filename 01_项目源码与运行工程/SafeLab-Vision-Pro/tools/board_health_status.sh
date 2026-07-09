#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
EVENT_DIR="$ROOT_DIR/data/events"
JSON_PATH="$REPORT_DIR/health_check.json"
TEXT_PATH="$REPORT_DIR/health_check.txt"

mkdir -p "$REPORT_DIR" "$EVENT_DIR"
: > "$TEXT_PATH"

log() {
    echo "$1" | tee -a "$TEXT_PATH"
}

json_escape() {
    echo "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

status_ok_missing() {
    if command -v "$1" >/dev/null 2>&1; then
        echo "ok"
    else
        echo "missing"
    fi
}

write_probe() {
    dir="$1"
    probe="$dir/.health_status_write_test"
    if [ -d "$dir" ] && echo ok > "$probe" 2>/dev/null; then
        rm -f "$probe"
        echo "ok"
    else
        echo "fail"
    fi
}

camera_status="missing"
camera_detail="no /dev/video nodes"
set -- /dev/video*
if [ "$1" != "/dev/video*" ]; then
    camera_status="present"
    camera_detail="$*"
fi

ov13855_status="unknown"
if command -v dmesg >/dev/null 2>&1; then
    if dmesg 2>/dev/null | grep -Eiq "Detected OV.*855 sensor|m00_b_ov13855|ov13855 .*Detected"; then
        ov13855_status="ready"
    elif dmesg 2>/dev/null | grep -Eiq "ov13855"; then
        ov13855_status="driver_seen"
        if dmesg 2>/dev/null | grep -Eiq "Unexpected sensor id\\(000000\\)|get remote sensor_sd failed"; then
            ov13855_status="not_ready"
        fi
    else
        ov13855_status="not_seen"
    fi
fi

preferred_camera="missing"
if [ -e /dev/video-camera0 ]; then
    preferred_camera="ok"
elif [ -e /dev/video11 ]; then
    preferred_camera="ok"
fi

python_status="missing"
if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
    python_status="ok"
fi

v4l2_status="$(status_ok_missing v4l2-ctl)"
media_status="$(status_ok_missing media-ctl)"
tar_status="$(status_ok_missing tar)"
storage_status="$(write_probe "$REPORT_DIR")"
events_status="$(write_probe "$EVENT_DIR")"
rknn_model_path="${SAFELAB_RKNN_MODEL:-$ROOT_DIR/models/rknn/safelab_yolov8n_fire_smoke_v3.rknn}"
rknn_model_status="missing"
if [ -f "$rknn_model_path" ]; then
    rknn_model_status="ok"
fi
rknn_runtime_status="missing"
if [ -f /usr/lib/librknnrt.so ]; then
    rknn_runtime_status="ok"
fi
rknn_common_test_status="$(status_ok_missing rknn_common_test)"
aplay_status="$(status_ok_missing aplay)"
arecord_status="$(status_ok_missing arecord)"
amixer_status="$(status_ok_missing amixer)"
audio_status="missing"
audio_capture_status="missing"
audio_playback_status="missing"
audio_card="missing"
if [ -f /proc/asound/cards ] && grep -q "rockchipnau8822" /proc/asound/cards 2>/dev/null; then
    audio_card="rockchipnau8822"
fi
if [ "$aplay_status" = "ok" ] && aplay -l 2>/dev/null | grep -q "rockchipnau8822"; then
    audio_playback_status="ok"
fi
if [ "$arecord_status" = "ok" ] && arecord -l 2>/dev/null | grep -q "rockchipnau8822"; then
    audio_capture_status="ok"
fi
if [ "$audio_card" = "rockchipnau8822" ] && [ "$audio_capture_status" = "ok" ] && [ "$audio_playback_status" = "ok" ]; then
    audio_status="ok"
fi
rk_inference_probe="unknown"
if [ -f "$REPORT_DIR/board_rknn_runtime_check.txt" ]; then
    if grep -q "RKNN runtime check completed." "$REPORT_DIR/board_rknn_runtime_check.txt" 2>/dev/null; then
        rk_inference_probe="ok"
    elif grep -q "RKNN runtime check failed" "$REPORT_DIR/board_rknn_runtime_check.txt" 2>/dev/null; then
        rk_inference_probe="fail"
    fi
fi

storage_free_mb="unknown"
if command -v df >/dev/null 2>&1; then
    storage_free_mb="$(df -m "$ROOT_DIR" 2>/dev/null | awk 'NR==2 {print $4}')"
fi

fallback_mode="none"
if [ "$python_status" = "missing" ]; then
    fallback_mode="shell_only"
fi
if [ "$camera_status" = "missing" ] || [ "$preferred_camera" = "missing" ] || [ "$ov13855_status" = "not_ready" ]; then
    if [ "$fallback_mode" = "none" ]; then
        fallback_mode="mock_detection"
    else
        fallback_mode="${fallback_mode}+mock_detection"
    fi
fi

log "SafeLab-Vision Pro Health Status"
log "Root: $ROOT_DIR"
log "JSON: $JSON_PATH"
log "camera: $camera_status"
log "ov13855: $ov13855_status"
log "preferred_camera: $preferred_camera"
log "python: $python_status"
log "v4l2_ctl: $v4l2_status"
log "media_ctl: $media_status"
log "rknn_model: $rknn_model_status"
log "rknn_runtime: $rknn_runtime_status"
log "rknn_common_test: $rknn_common_test_status"
log "rk_inference_probe: $rk_inference_probe"
log "audio: $audio_status"
log "audio_card: $audio_card"
log "audio_capture: $audio_capture_status"
log "audio_playback: $audio_playback_status"
log "storage_free_mb: $storage_free_mb"
log "fallback_mode: $fallback_mode"

cat > "$JSON_PATH" <<JSON
{
  "camera": "$camera_status",
  "camera_detail": "$(json_escape "$camera_detail")",
  "ov13855": "$ov13855_status",
  "preferred_camera": "$preferred_camera",
  "preferred_video21": "$preferred_camera",
  "python": "$python_status",
  "v4l2_ctl": "$v4l2_status",
  "media_ctl": "$media_status",
  "rknn_model": "$rknn_model_status",
  "rknn_model_path": "$(json_escape "$rknn_model_path")",
  "rknn_runtime": "$rknn_runtime_status",
  "rknn_common_test": "$rknn_common_test_status",
  "rk_inference_probe": "$rk_inference_probe",
  "audio": "$audio_status",
  "audio_card": "$audio_card",
  "audio_capture": "$audio_capture_status",
  "audio_playback": "$audio_playback_status",
  "aplay": "$aplay_status",
  "arecord": "$arecord_status",
  "amixer": "$amixer_status",
  "tar": "$tar_status",
  "reports_writable": "$storage_status",
  "events_writable": "$events_status",
  "storage_free_mb": "$storage_free_mb",
  "fallback_mode": "$fallback_mode"
}
JSON

echo "Health status JSON: $JSON_PATH"
exit 0

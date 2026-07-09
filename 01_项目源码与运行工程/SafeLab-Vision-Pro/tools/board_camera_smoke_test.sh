#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
REPORT_PATH="$REPORT_DIR/board_camera_smoke_test.txt"
OUTPUT_PATH="$REPORT_DIR/board_camera_smoke_frame.raw"
DEVICE="${1:-/dev/video-camera0}"
FALLBACK_DEVICE="/dev/video11"
FAILURES=0

mkdir -p "$REPORT_DIR"
: > "$REPORT_PATH"

log() {
    echo "$1" | tee -a "$REPORT_PATH"
}

fail() {
    log "[FAIL] $1"
    FAILURES=$((FAILURES + 1))
}

ok() {
    log "[OK] $1"
}

if [ ! -e "$DEVICE" ] && [ -e "$FALLBACK_DEVICE" ]; then
    DEVICE="$FALLBACK_DEVICE"
fi

log "SafeLab-Vision Pro Board Camera Smoke Test"
log "Root: $ROOT_DIR"
log "Device: $DEVICE"
log "Report: $REPORT_PATH"
log "Output: $OUTPUT_PATH"
log ""

if [ ! -e "$DEVICE" ]; then
    fail "camera device does not exist: $DEVICE"
elif ! command -v v4l2-ctl >/dev/null 2>&1; then
    fail "v4l2-ctl is missing"
else
    log "== Device Format =="
    v4l2-ctl -d "$DEVICE" --all 2>&1 | tee -a "$REPORT_PATH"

    log ""
    log "== Capture Probe =="
    rm -f "$OUTPUT_PATH"
    CAPTURE_CMD="v4l2-ctl -d '$DEVICE' --stream-mmap=3 --stream-count=1 --stream-to='$OUTPUT_PATH'"
    if command -v timeout >/dev/null 2>&1; then
        sh -c "timeout 8 $CAPTURE_CMD" >> "$REPORT_PATH" 2>&1
        capture_status=$?
    else
        sh -c "$CAPTURE_CMD" >> "$REPORT_PATH" 2>&1 &
        capture_pid=$!
        sleep 8
        if kill -0 "$capture_pid" 2>/dev/null; then
            kill "$capture_pid" 2>/dev/null || true
            capture_status=124
        else
            wait "$capture_pid"
            capture_status=$?
        fi
    fi
    if [ "$capture_status" -eq 0 ]; then
        if [ -s "$OUTPUT_PATH" ]; then
            size="$(wc -c < "$OUTPUT_PATH" | tr -d ' ')"
            ok "captured raw frame stream ($size bytes)"
        else
            fail "capture output file is empty"
        fi
    else
        fail "v4l2 capture failed or timed out"
    fi
fi

log ""
if [ "$FAILURES" -eq 0 ]; then
    log "Camera smoke test passed."
    exit 0
fi

log "Camera smoke test failed: $FAILURES issue(s)."
exit 1

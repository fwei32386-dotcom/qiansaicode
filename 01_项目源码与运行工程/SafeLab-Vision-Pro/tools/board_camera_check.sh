#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
REPORT_PATH="$REPORT_DIR/board_camera_check.txt"
SNAPSHOT_PATH="$REPORT_DIR/board_camera_probe.raw"
PREFERRED_DEVICE="${SAFELAB_CAMERA_DEVICE:-/dev/video-camera0}"
FALLBACK_DEVICE="/dev/video11"
FAILURES=0
WARNINGS=0

mkdir -p "$REPORT_DIR"
: > "$REPORT_PATH"

log() {
    echo "$1" | tee -a "$REPORT_PATH"
}

ok() {
    log "[OK] $1"
}

warn() {
    log "[WARN] $1"
    WARNINGS=$((WARNINGS + 1))
}

fail() {
    log "[FAIL] $1"
    FAILURES=$((FAILURES + 1))
}

run_and_log() {
    title="$1"
    shift
    log ""
    log "== $title =="
    "$@" 2>&1 | tee -a "$REPORT_PATH"
}

log "SafeLab-Vision Pro Board Camera Check"
log "Root: $ROOT_DIR"
log "Report: $REPORT_PATH"
log "Preferred device: $PREFERRED_DEVICE"
log "Fallback device: $FALLBACK_DEVICE"
log ""

log "== Video Nodes =="
set -- /dev/video*
if [ "$1" = "/dev/video*" ]; then
    fail "No /dev/video* nodes found"
else
    for node in "$@"; do
        if [ -e "$node" ]; then
            log "$node"
        fi
    done
fi

PROBE_DEVICE=""
if [ -e "$PREFERRED_DEVICE" ]; then
    ok "$PREFERRED_DEVICE exists"
    PROBE_DEVICE="$PREFERRED_DEVICE"
elif [ -e "$FALLBACK_DEVICE" ]; then
    warn "$PREFERRED_DEVICE not found; using fallback $FALLBACK_DEVICE"
    PROBE_DEVICE="$FALLBACK_DEVICE"
else
    warn "$PREFERRED_DEVICE not found and fallback $FALLBACK_DEVICE is missing"
fi

log ""
log "== Kernel Camera Clues =="
if command -v dmesg >/dev/null 2>&1; then
    dmesg 2>/dev/null | grep -Ei "ov13855|rkisp|rkcif|mipi|csi|camera|v4l2|video[0-9]+" | tail -n 80 | tee -a "$REPORT_PATH"
    if dmesg 2>/dev/null | grep -Eiq "ov13855"; then
        ok "dmesg contains ov13855"
    else
        warn "dmesg does not contain ov13855"
    fi
else
    warn "dmesg unavailable"
fi

log ""
log "== Tool Availability =="
if command -v v4l2-ctl >/dev/null 2>&1; then
    ok "v4l2-ctl available"
else
    warn "v4l2-ctl unavailable; install v4l-utils for deeper camera validation"
fi

if command -v media-ctl >/dev/null 2>&1; then
    ok "media-ctl available"
else
    warn "media-ctl unavailable; media graph cannot be dumped"
fi

if command -v fswebcam >/dev/null 2>&1; then
    ok "fswebcam available"
else
    warn "fswebcam unavailable; JPEG snapshot probe skipped"
fi

if command -v v4l2-ctl >/dev/null 2>&1; then
    run_and_log "v4l2-ctl --list-devices" v4l2-ctl --list-devices

    if [ -n "$PROBE_DEVICE" ]; then
        run_and_log "v4l2 formats for $PROBE_DEVICE" v4l2-ctl -d "$PROBE_DEVICE" --list-formats-ext
        log ""
        log "== Raw Frame Probe =="
        rm -f "$SNAPSHOT_PATH"
        if v4l2-ctl -d "$PROBE_DEVICE" --stream-mmap=3 --stream-count=1 --stream-to="$SNAPSHOT_PATH" >> "$REPORT_PATH" 2>&1; then
            if [ -s "$SNAPSHOT_PATH" ]; then
                ok "Captured one raw frame to $SNAPSHOT_PATH"
            else
                warn "Raw frame probe command ran but output file is empty"
            fi
        else
            warn "Raw frame probe failed on $PREFERRED_DEVICE"
        fi
    fi
fi

if command -v media-ctl >/dev/null 2>&1; then
    run_and_log "media-ctl device list" media-ctl -p
fi

if command -v fswebcam >/dev/null 2>&1 && [ -n "$PROBE_DEVICE" ]; then
    JPEG_PATH="$REPORT_DIR/board_camera_probe.jpg"
    log ""
    log "== JPEG Snapshot Probe =="
    if fswebcam -d "$PROBE_DEVICE" -r 1280x720 --no-banner "$JPEG_PATH" >> "$REPORT_PATH" 2>&1; then
        if [ -s "$JPEG_PATH" ]; then
            ok "Captured JPEG snapshot to $JPEG_PATH"
        else
            warn "fswebcam ran but JPEG output is empty"
        fi
    else
        warn "fswebcam snapshot failed on $PREFERRED_DEVICE"
    fi
fi

log ""
log "== Summary =="
log "Failures: $FAILURES"
log "Warnings: $WARNINGS"

if [ "$FAILURES" -eq 0 ]; then
    log "Camera check completed."
    exit 0
fi

log "Camera check failed: $FAILURES issue(s)."
exit 1

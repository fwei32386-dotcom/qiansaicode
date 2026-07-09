#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
REPORT_PATH="$REPORT_DIR/board_ov13855_diagnose.txt"
DEVICE="${SAFELAB_CAMERA_DEVICE:-/dev/video-camera0}"
FALLBACK_DEVICE="/dev/video11"
RAW_PATH="$REPORT_DIR/board_ov13855_probe.raw"
CAMERA_REQUIRED="${SAFELAB_CAMERA_REQUIRED:-0}"
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

camera_issue() {
    if [ "$CAMERA_REQUIRED" = "1" ]; then
        fail "$1"
    else
        warn "$1"
    fi
}

section() {
    log ""
    log "== $1 =="
}

run_cmd() {
    title="$1"
    shift
    section "$title"
    "$@" 2>&1 | tee -a "$REPORT_PATH"
}

pick_device() {
    if [ -e "$DEVICE" ]; then
        echo "$DEVICE"
    elif [ -e "$FALLBACK_DEVICE" ]; then
        echo "$FALLBACK_DEVICE"
    else
        echo "$DEVICE"
    fi
}

log "SafeLab-Vision Pro OV13855 Diagnosis"
log "Root: $ROOT_DIR"
log "Report: $REPORT_PATH"
log "Preferred device: $DEVICE"
log "Fallback device: $FALLBACK_DEVICE"
log "Probe device: $(pick_device)"
log "Camera required: $CAMERA_REQUIRED"

section "Diagnosis Verdict"
if command -v dmesg >/dev/null 2>&1 && dmesg 2>/dev/null | grep -q "Unexpected sensor id(000000)"; then
    camera_issue "OV13855 driver probed I2C address but read sensor id 000000"
    log "Likely causes: camera module not seated, wrong module/adapter, sensor power rails missing, reset/pwdn pin wrong, or device-tree pin/regulator mismatch."
    if [ "$CAMERA_REQUIRED" != "1" ]; then
        log "Current mode treats this as non-blocking because SAFELAB_CAMERA_REQUIRED is not 1."
    fi
elif command -v dmesg >/dev/null 2>&1 && dmesg 2>/dev/null | grep -Eiq "Detected OV.*855 sensor|m00_b_ov13855|ov13855 .*Detected"; then
    ok "OV13855 detect message found"
else
    warn "No conclusive OV13855 detect message found"
fi

if [ -e "$(pick_device)" ]; then
    ok "probe video node exists: $(pick_device)"
else
    camera_issue "probe video node missing: $(pick_device)"
fi

section "Immediate Hardware Checklist"
log "Current no-camera development mode:"
log "- Leave SAFELAB_CAMERA_REQUIRED unset or set to 0."
log "- The board acceptance path can continue with mock/file detections."
log "When the camera is physically connected:"
log "- Run SAFELAB_CAMERA_REQUIRED=1 sh tools/board_ov13855_diagnose.sh"
log ""
log "1. Power off the board before reseating the camera ribbon cable."
log "2. Confirm the ribbon orientation and that the FPC latch is fully locked."
log "3. Confirm the module is actually OV13855 and matches the ELF 2 camera connector pinout."
log "4. Confirm AVDD/DOVDD/DVDD and reset/pwdn lines are provided by board/device-tree."
log "5. Reboot and rerun: sh tools/board_ov13855_diagnose.sh"

section "Kernel OV13855 Clues"
if command -v dmesg >/dev/null 2>&1; then
    dmesg 2>/dev/null | grep -Ei "ov13855|sensor id|rkcif|rkisp|mipi|csi|dphy|regulator|power-gpios|pinctrl|remote sensor|terminal sensor" | tail -n 140 | tee -a "$REPORT_PATH"
else
    warn "dmesg unavailable"
fi

section "Device Nodes"
if ls /dev/video* >/dev/null 2>&1; then
    ls -l /dev/video* 2>&1 | tee -a "$REPORT_PATH"
else
    fail "no /dev/video* nodes"
fi
if ls /dev/v4l-subdev* >/dev/null 2>&1; then
    ls -l /dev/v4l-subdev* 2>&1 | tee -a "$REPORT_PATH"
else
    warn "no /dev/v4l-subdev* nodes"
fi
if ls /dev/media* >/dev/null 2>&1; then
    ls -l /dev/media* 2>&1 | tee -a "$REPORT_PATH"
else
    warn "no /dev/media* nodes"
fi

section "I2C Clues"
if [ -d /sys/bus/i2c/devices ]; then
    find /sys/bus/i2c/devices -maxdepth 2 \( -name name -o -name modalias -o -name uevent \) 2>/dev/null |
        while read -r file; do
            if grep -Eiq "ov13855|0036|camera|sensor" "$file" 2>/dev/null; then
                echo "--- $file" | tee -a "$REPORT_PATH"
                cat "$file" 2>&1 | tee -a "$REPORT_PATH"
            fi
        done
    if [ -e /sys/bus/i2c/devices/3-0036/name ]; then
        ok "I2C device 3-0036 exists: $(cat /sys/bus/i2c/devices/3-0036/name 2>/dev/null)"
    else
        warn "I2C device 3-0036 not found in sysfs"
    fi
else
    warn "/sys/bus/i2c/devices missing"
fi
if command -v i2cdetect >/dev/null 2>&1; then
    run_cmd "i2cdetect bus 3" i2cdetect -y 3
else
    warn "i2cdetect unavailable"
fi

section "Device Tree Camera Clues"
if [ -d /proc/device-tree ]; then
    find /proc/device-tree -maxdepth 6 -type f 2>/dev/null |
        grep -Ei "ov13855|camera|cam|csi|mipi|dphy|rkisp|rkcif|pwdn|reset|power|avdd|dovdd|dvdd" |
        head -n 160 |
        while read -r file; do
            echo "$file" | tee -a "$REPORT_PATH"
        done
else
    warn "/proc/device-tree missing"
fi

if command -v v4l2-ctl >/dev/null 2>&1; then
    run_cmd "v4l2 list devices" v4l2-ctl --list-devices
    if [ -e "$(pick_device)" ]; then
        run_cmd "v4l2 all for $(pick_device)" v4l2-ctl -d "$(pick_device)" --all
        run_cmd "v4l2 formats for $(pick_device)" v4l2-ctl -d "$(pick_device)" --list-formats-ext
        section "Raw Capture Probe"
        rm -f "$RAW_PATH"
        if timeout 8 v4l2-ctl -d "$(pick_device)" --stream-mmap=3 --stream-count=1 --stream-to="$RAW_PATH" >> "$REPORT_PATH" 2>&1; then
            if [ -s "$RAW_PATH" ]; then
                ok "raw capture produced data: $RAW_PATH ($(wc -c < "$RAW_PATH" | tr -d ' ') bytes)"
            else
                camera_issue "raw capture command returned success but output is empty"
            fi
        else
            camera_issue "raw capture failed or timed out"
        fi
    fi
else
    warn "v4l2-ctl unavailable"
fi

if command -v media-ctl >/dev/null 2>&1; then
    run_cmd "media graph" media-ctl -p
else
    warn "media-ctl unavailable"
fi

section "Summary"
log "Failures: $FAILURES"
log "Warnings: $WARNINGS"
if [ "$FAILURES" -eq 0 ]; then
    log "OV13855 diagnosis completed without hard failures."
    exit 0
fi

log "OV13855 diagnosis found $FAILURES hard issue(s)."
exit 1

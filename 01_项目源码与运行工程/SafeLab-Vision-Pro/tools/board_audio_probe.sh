#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
REPORT_PATH="$REPORT_DIR/board_audio_probe.txt"
WAV_PATH="$REPORT_DIR/board_mic_probe.wav"
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

has_cmd() {
    command -v "$1" >/dev/null 2>&1
}

log "SafeLab Board Audio Probe"
log "Root: $ROOT_DIR"
log "Report: $REPORT_PATH"
log "WAV: $WAV_PATH"
log ""

log "== ALSA Cards =="
if [ -f /proc/asound/cards ]; then
    cat /proc/asound/cards | tee -a "$REPORT_PATH"
    if grep -q "rockchipnau8822" /proc/asound/cards 2>/dev/null; then
        ok "rockchipnau8822 card present"
    else
        fail "rockchipnau8822 card missing"
    fi
else
    fail "/proc/asound/cards missing"
fi

log ""
log "== Tools =="
for tool in aplay arecord amixer; do
    if has_cmd "$tool"; then
        ok "$tool present"
    else
        fail "$tool missing"
    fi
done

log ""
log "== Playback Devices =="
if has_cmd aplay; then
    aplay -l 2>&1 | tee -a "$REPORT_PATH"
    if aplay -l 2>/dev/null | grep -q "rockchipnau8822"; then
        ok "rockchipnau8822 playback device present"
    else
        fail "rockchipnau8822 playback device missing"
    fi
fi

log ""
log "== Capture Devices =="
if has_cmd arecord; then
    arecord -l 2>&1 | tee -a "$REPORT_PATH"
    if arecord -l 2>/dev/null | grep -q "rockchipnau8822"; then
        ok "rockchipnau8822 capture device present"
    else
        fail "rockchipnau8822 capture device missing"
    fi
fi

log ""
log "== Device Nodes =="
for node in /dev/snd/pcmC1D0c /dev/snd/pcmC1D0p /dev/snd/controlC1; do
    if [ -e "$node" ]; then
        ok "$node present"
    else
        warn "$node missing"
    fi
done

log ""
log "== Mixer Snapshot =="
if has_cmd amixer; then
    amixer -c rockchipnau8822 2>&1 | sed -n '1,160p' | tee -a "$REPORT_PATH"
fi

log ""
log "== Built-in MIC Record Probe =="
if has_cmd arecord; then
    rm -f "$WAV_PATH"
    if arecord -D hw:rockchipnau8822,0 -d 2 -f cd -t wav "$WAV_PATH" >> "$REPORT_PATH" 2>&1; then
        ok "built-in MIC capture command completed"
    else
        warn "built-in MIC capture command returned non-zero; checking captured WAV evidence"
    fi
    if [ -f "$WAV_PATH" ]; then
        bytes="$(wc -c < "$WAV_PATH" | tr -d ' ')"
        log "mic_wav_bytes: $bytes"
        if [ "$bytes" -gt 100000 ]; then
            ok "built-in MIC wav file has expected size"
        else
            warn "built-in MIC wav file is small"
        fi
    else
        fail "built-in MIC wav file missing"
    fi
fi

log ""
log "Failures: $FAILURES"
log "Warnings: $WARNINGS"
if [ "$FAILURES" -eq 0 ]; then
    log "Audio probe completed."
    exit 0
fi

log "Audio probe failed."
exit 1

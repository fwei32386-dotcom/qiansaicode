#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
REPORT_PATH="$REPORT_DIR/board_set_time.txt"

mkdir -p "$REPORT_DIR"
: > "$REPORT_PATH"

log() {
    echo "$1" | tee -a "$REPORT_PATH"
}

log "SafeLab-Vision Pro Board Set Time"
log "Report: $REPORT_PATH"
log ""

if [ "$#" -ne 1 ]; then
    log "Usage:"
    log "  sh tools/board_set_time.sh 'YYYY-MM-DD HH:MM:SS'"
    log ""
    log "Example:"
    log "  sh tools/board_set_time.sh '2026-05-12 14:30:00'"
    exit 2
fi

TARGET_TIME="$1"

case "$TARGET_TIME" in
    ????-??-??\ ??:??:??)
        ;;
    *)
        log "[FAIL] invalid time format: $TARGET_TIME"
        log "Expected: YYYY-MM-DD HH:MM:SS"
        exit 2
        ;;
esac

if ! command -v date >/dev/null 2>&1; then
    log "[FAIL] date command unavailable"
    exit 1
fi

log "Before: $(date)"
if date -s "$TARGET_TIME" >/dev/null 2>&1; then
    log "After: $(date)"
    log "Time set successfully."
    exit 0
fi

log "[FAIL] date -s failed"
exit 1

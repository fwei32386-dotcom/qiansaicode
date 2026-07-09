#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
REPORT_PATH="$REPORT_DIR/board_time_check.txt"
MIN_VALID_YEAR=2024
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

log "SafeLab-Vision Pro Board Time Check"
log "Report: $REPORT_PATH"
log ""

if ! command -v date >/dev/null 2>&1; then
    fail "date command unavailable"
else
    CURRENT_DATE="$(date)"
    CURRENT_YEAR="$(date +%Y 2>/dev/null || echo 0)"
    CURRENT_EPOCH="$(date +%s 2>/dev/null || echo 0)"
    log "Current date: $CURRENT_DATE"
    log "Current year: $CURRENT_YEAR"
    log "Current epoch: $CURRENT_EPOCH"

    case "$CURRENT_YEAR" in
        ''|*[!0-9]*)
            fail "current year is not numeric"
            ;;
        *)
            if [ "$CURRENT_YEAR" -lt "$MIN_VALID_YEAR" ]; then
                fail "system time is too old; logs and reports will have wrong timestamps"
            else
                log "[OK] system year is plausible"
            fi
            ;;
    esac
fi

log ""
log "Manual time set example:"
log "  date -s '2026-05-12 14:30:00'"
log ""
log "After setting time, run:"
log "  sh tools/board_time_check.sh"

log ""
if [ "$FAILURES" -eq 0 ]; then
    log "Time check passed."
    exit 0
fi

log "Time check failed: $FAILURES issue(s)."
exit 1

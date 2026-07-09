#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
EVENT_DIR="$ROOT_DIR/data/events"
REPORT_PATH="$REPORT_DIR/board_ops_report.txt"
FAILURES=0

mkdir -p "$REPORT_DIR" "$EVENT_DIR"
: > "$REPORT_PATH"

log() {
    echo "$1" | tee -a "$REPORT_PATH"
}

run_step() {
    title="$1"
    shift
    tmp="$REPORT_DIR/.board_ops_step_output"
    log ""
    log "== $title =="
    "$@" > "$tmp" 2>&1
    status=$?
    cat "$tmp" | tee -a "$REPORT_PATH"
    rm -f "$tmp"
    if [ "$status" -eq 0 ]; then
        log "[OK] $title"
    else
        log "[FAIL] $title"
        FAILURES=$((FAILURES + 1))
    fi
}

log "SafeLab-Vision Pro Board Ops"
log "Root: $ROOT_DIR"
log "Report: $REPORT_PATH"

run_step "Board health check" sh "$ROOT_DIR/tools/board_health_check.sh"
run_step "Board health status" sh "$ROOT_DIR/tools/board_health_status.sh"
run_step "Board camera check" sh "$ROOT_DIR/tools/board_camera_check.sh"
run_step "Board OV13855 diagnosis" sh "$ROOT_DIR/tools/board_ov13855_diagnose.sh"
run_step "Board time check" sh "$ROOT_DIR/tools/board_time_check.sh"
run_step "Board audio probe" sh "$ROOT_DIR/tools/board_audio_probe.sh"
run_step "Board RKNN runtime check" sh "$ROOT_DIR/tools/board_rknn_runtime_check.sh"
run_step "Board GPIO contract check" sh "$ROOT_DIR/tools/board_gpio_contract_check.sh"
run_step "Board health status after RKNN check" sh "$ROOT_DIR/tools/board_health_status.sh"
run_step "Board smoke test" sh "$ROOT_DIR/tools/board_smoke_test.sh"
run_step "Board acceptance summary" sh "$ROOT_DIR/tools/board_acceptance_summary.sh"

log ""
log "== Log Overview =="
sh "$ROOT_DIR/tools/board_log_tools.sh" summary 2>&1 | tee -a "$REPORT_PATH"
sh "$ROOT_DIR/tools/board_log_tools.sh" tail 3 2>&1 | tee -a "$REPORT_PATH"

log "== Storage Snapshot =="
if command -v df >/dev/null 2>&1; then
    df -h "$ROOT_DIR" 2>/dev/null | tee -a "$REPORT_PATH"
else
    log "df unavailable"
fi

log ""
if [ "$FAILURES" -eq 0 ]; then
    log "Board ops completed successfully."
    exit 0
fi

log "Board ops completed with $FAILURES issue(s)."
exit 1

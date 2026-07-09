#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
EVENT_DIR="$ROOT_DIR/data/events"
RUNTIME_DIR="$ROOT_DIR/data/runtime"
STATUS_TXT="$REPORT_DIR/runtime_status.txt"
STATUS_JSON="$REPORT_DIR/runtime_status.json"
STATUS_REPORT="$REPORT_DIR/status_safelab_report.txt"
PID_FILE="$RUNTIME_DIR/safelab.pid"

mkdir -p "$REPORT_DIR" "$EVENT_DIR" "$RUNTIME_DIR"
: > "$STATUS_REPORT"

log() {
    echo "$1" | tee -a "$STATUS_REPORT"
}

json_value() {
    key="$1"
    file="$REPORT_DIR/health_check.json"
    if [ -f "$file" ]; then
        sed -n "s/.*\"$key\": \"\\([^\"]*\\)\".*/\\1/p" "$file" | head -n 1
    else
        echo "unknown"
    fi
}

count_lines() {
    file="$1"
    if [ -f "$file" ]; then
        wc -l < "$file" | tr -d ' '
    else
        echo 0
    fi
}

log "SafeLab-Vision Pro Status"
log "Root: $ROOT_DIR"
log "Report: $STATUS_REPORT"
log ""

if [ -f "$PID_FILE" ]; then
    log "runtime marker: present ($(cat "$PID_FILE" 2>/dev/null || echo unknown))"
else
    log "runtime marker: missing"
fi

if [ -f "$STATUS_TXT" ]; then
    log ""
    log "== Last Runtime Status =="
    cat "$STATUS_TXT" | tee -a "$STATUS_REPORT"
else
    log "runtime_status.txt: missing"
fi

log ""
log "== Health Snapshot =="
if [ -x "$ROOT_DIR/tools/board_health_status.sh" ] || [ -f "$ROOT_DIR/tools/board_health_status.sh" ]; then
    sh "$ROOT_DIR/tools/board_health_status.sh" >/dev/null 2>&1 || true
fi
log "python: $(json_value python)"
log "fallback_mode: $(json_value fallback_mode)"
log "camera: $(json_value camera)"
log "ov13855: $(json_value ov13855)"
log "preferred_video21: $(json_value preferred_video21)"
log "v4l2_ctl: $(json_value v4l2_ctl)"
log "media_ctl: $(json_value media_ctl)"

log ""
log "== Evidence Logs =="
log "events.jsonl: $(count_lines "$EVENT_DIR/events.jsonl") line(s)"
log "alarm_actions.jsonl: $(count_lines "$EVENT_DIR/alarm_actions.jsonl") line(s)"
log "actuator_log.jsonl: $(count_lines "$EVENT_DIR/actuator_log.jsonl") line(s)"

log ""
log "== Recent Events =="
if [ -f "$EVENT_DIR/events.jsonl" ]; then
    tail -n 3 "$EVENT_DIR/events.jsonl" | tee -a "$STATUS_REPORT"
else
    log "missing"
fi

log ""
log "== Reports =="
for file in \
    "$STATUS_JSON" \
    "$REPORT_DIR/health_check.json" \
    "$REPORT_DIR/board_camera_check.txt" \
    "$REPORT_DIR/board_rule_contract_report.txt" \
    "$REPORT_DIR/live_dashboard.html" \
    "$REPORT_DIR/final_acceptance_report.html"; do
    if [ -f "$file" ]; then
        log "$(basename "$file"): present ($(wc -c < "$file" | tr -d ' ') bytes)"
    else
        log "$(basename "$file"): missing"
    fi
done

log ""
log "Status check completed."
exit 0

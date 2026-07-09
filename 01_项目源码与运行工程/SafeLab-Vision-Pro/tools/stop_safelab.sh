#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
EVENT_DIR="$ROOT_DIR/data/events"
RUNTIME_DIR="$ROOT_DIR/data/runtime"
STATUS_TXT="$REPORT_DIR/runtime_status.txt"
STATUS_JSON="$REPORT_DIR/runtime_status.json"
STOP_REPORT="$REPORT_DIR/stop_safelab_report.txt"
PID_FILE="$RUNTIME_DIR/safelab.pid"
ARCHIVE="${1:-}"

mkdir -p "$REPORT_DIR" "$EVENT_DIR" "$RUNTIME_DIR"
: > "$STOP_REPORT"

log() {
    echo "$1" | tee -a "$STOP_REPORT"
}

json_escape() {
    echo "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

count_lines() {
    file="$1"
    if [ -f "$file" ]; then
        wc -l < "$file" | tr -d ' '
    else
        echo 0
    fi
}

write_stopped_status() {
    stopped_at="$(date 2>/dev/null || echo unknown_time)"
    events_count="$(count_lines "$EVENT_DIR/events.jsonl")"
    actions_count="$(count_lines "$EVENT_DIR/alarm_actions.jsonl")"
    actuator_count="$(count_lines "$EVENT_DIR/actuator_log.jsonl")"
    {
        echo "SafeLab-Vision Pro Runtime Status"
        echo "Root: $ROOT_DIR"
        echo "State: stopped"
        echo "Mode: stopped"
        echo "Detail: runtime marker cleared; evidence logs preserved"
        echo "Started/Updated: $stopped_at"
        echo ""
        echo "Evidence:"
        echo "  events: $events_count"
        echo "  actions: $actions_count"
        echo "  actuator_records: $actuator_count"
    } > "$STATUS_TXT"
    cat > "$STATUS_JSON" <<JSON
{
  "state": "stopped",
  "mode": "stopped",
  "detail": "runtime marker cleared; evidence logs preserved",
  "root": "$(json_escape "$ROOT_DIR")",
  "updated_at": "$(json_escape "$stopped_at")",
  "evidence": {
    "events": $events_count,
    "actions": $actions_count,
    "actuator_records": $actuator_count
  }
}
JSON
}

log "SafeLab-Vision Pro Stop"
log "Root: $ROOT_DIR"
log "Report: $STOP_REPORT"

if [ "$ARCHIVE" = "--archive" ]; then
    log ""
    log "== Archive Logs =="
    sh "$ROOT_DIR/tools/board_log_tools.sh" archive | tee -a "$STOP_REPORT"
fi

if [ -f "$PID_FILE" ]; then
    rm -f "$PID_FILE"
    log "runtime marker removed"
else
    log "runtime marker already missing"
fi

write_stopped_status
log "Runtime status: $STATUS_TXT"
log "Runtime JSON: $STATUS_JSON"
log "SafeLab runtime stopped."
exit 0

#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
EVENT_DIR="$ROOT_DIR/data/events"
RUNTIME_DIR="$ROOT_DIR/data/runtime"
STATUS_TXT="$REPORT_DIR/runtime_status.txt"
STATUS_JSON="$REPORT_DIR/runtime_status.json"
START_REPORT="$REPORT_DIR/start_safelab_report.txt"
PID_FILE="$RUNTIME_DIR/safelab.pid"
FAILURES=0

mkdir -p "$REPORT_DIR" "$EVENT_DIR" "$RUNTIME_DIR"
: > "$START_REPORT"

log() {
    echo "$1" | tee -a "$START_REPORT"
}

json_escape() {
    echo "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
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

run_step() {
    title="$1"
    shift
    tmp="$REPORT_DIR/.start_safelab_step_output"
    log ""
    log "== $title =="
    "$@" > "$tmp" 2>&1
    status=$?
    cat "$tmp" | tee -a "$START_REPORT"
    rm -f "$tmp"
    if [ "$status" -eq 0 ]; then
        log "[OK] $title"
    else
        log "[FAIL] $title"
        FAILURES=$((FAILURES + 1))
    fi
}

run_optional_step() {
    title="$1"
    shift
    tmp="$REPORT_DIR/.start_safelab_step_output"
    log ""
    log "== $title =="
    "$@" > "$tmp" 2>&1
    status=$?
    cat "$tmp" | tee -a "$START_REPORT"
    rm -f "$tmp"
    if [ "$status" -eq 0 ]; then
        log "[OK] $title"
    else
        log "[WARN] $title completed with issue(s); fallback runtime can still start"
    fi
}

write_runtime_status() {
    state="$1"
    mode="$2"
    detail="$3"
    started_at="$(date 2>/dev/null || echo unknown_time)"
    events_count=0
    actions_count=0
    actuator_count=0
    if [ -f "$EVENT_DIR/events.jsonl" ]; then events_count="$(wc -l < "$EVENT_DIR/events.jsonl" | tr -d ' ')"; fi
    if [ -f "$EVENT_DIR/alarm_actions.jsonl" ]; then actions_count="$(wc -l < "$EVENT_DIR/alarm_actions.jsonl" | tr -d ' ')"; fi
    if [ -f "$EVENT_DIR/actuator_log.jsonl" ]; then actuator_count="$(wc -l < "$EVENT_DIR/actuator_log.jsonl" | tr -d ' ')"; fi

    {
        echo "SafeLab-Vision Pro Runtime Status"
        echo "Root: $ROOT_DIR"
        echo "State: $state"
        echo "Mode: $mode"
        echo "Detail: $detail"
        echo "Started/Updated: $started_at"
        echo "PID file: $PID_FILE"
        echo ""
        echo "Health:"
        echo "  python: $(json_value python)"
        echo "  fallback_mode: $(json_value fallback_mode)"
        echo "  camera: $(json_value camera)"
        echo "  ov13855: $(json_value ov13855)"
        echo "  preferred_video21: $(json_value preferred_video21)"
        echo ""
        echo "Evidence:"
        echo "  events: $events_count"
        echo "  actions: $actions_count"
        echo "  actuator_records: $actuator_count"
    } > "$STATUS_TXT"

    cat > "$STATUS_JSON" <<JSON
{
  "state": "$(json_escape "$state")",
  "mode": "$(json_escape "$mode")",
  "detail": "$(json_escape "$detail")",
  "root": "$(json_escape "$ROOT_DIR")",
  "updated_at": "$(json_escape "$started_at")",
  "pid_file": "$(json_escape "$PID_FILE")",
  "health": {
    "python": "$(json_escape "$(json_value python)")",
    "fallback_mode": "$(json_escape "$(json_value fallback_mode)")",
    "camera": "$(json_escape "$(json_value camera)")",
    "ov13855": "$(json_escape "$(json_value ov13855)")",
    "preferred_video21": "$(json_escape "$(json_value preferred_video21)")"
  },
  "evidence": {
    "events": $events_count,
    "actions": $actions_count,
    "actuator_records": $actuator_count
  }
}
JSON
}

log "SafeLab-Vision Pro Start"
log "Root: $ROOT_DIR"
log "Report: $START_REPORT"

if [ "$ROOT_DIR" != "/root/SafeLab-Vision-Pro" ]; then
    log "[WARN] expected board root is /root/SafeLab-Vision-Pro"
fi

run_step "Board health status" sh "$ROOT_DIR/tools/board_health_status.sh"
run_optional_step "Board camera check" sh "$ROOT_DIR/tools/board_camera_check.sh"
run_step "Board smoke test" sh "$ROOT_DIR/tools/board_smoke_test.sh"
run_step "Board log summary" sh "$ROOT_DIR/tools/board_log_tools.sh" summary

fallback_mode="$(json_value fallback_mode)"
python_status="$(json_value python)"
mode="$fallback_mode"
detail="shell fallback runtime active"
if [ "$python_status" = "ok" ]; then
    detail="python runtime available; real runtime start hook is reserved for RKNN integration"
fi

echo "$$" > "$PID_FILE"
write_runtime_status "running" "$mode" "$detail"

log ""
log "Runtime status: $STATUS_TXT"
log "Runtime JSON: $STATUS_JSON"
if [ "$FAILURES" -eq 0 ]; then
    log "SafeLab fallback runtime started."
    exit 0
fi

log "SafeLab runtime start completed with $FAILURES issue(s)."
exit 1

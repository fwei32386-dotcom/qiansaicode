#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
EVENT_DIR="$ROOT_DIR/data/events"
TIMELINE_DIR="$EVENT_DIR/timelines"
REPORT_PATH="$REPORT_DIR/board_acceptance_summary.txt"

mkdir -p "$REPORT_DIR" "$EVENT_DIR"
: > "$REPORT_PATH"

log() {
    echo "$1" | tee -a "$REPORT_PATH"
}

count_lines() {
    file="$1"
    if [ -f "$file" ]; then
        wc -l < "$file" | tr -d ' '
    else
        echo 0
    fi
}

status_from_health() {
    key="$1"
    file="$REPORT_DIR/health_check.json"
    if [ -f "$file" ]; then
        sed -n "s/.*\"$key\": \"\\([^\"]*\\)\".*/\\1/p" "$file" | head -n 1
    else
        echo "unknown"
    fi
}

contains() {
    file="$1"
    pattern="$2"
    if grep -q "$pattern" "$file" 2>/dev/null; then
        echo "yes"
    else
        echo "no"
    fi
}

file_state() {
    file="$1"
    if [ -f "$file" ]; then
        echo "present ($(wc -c < "$file" | tr -d ' ') bytes)"
    else
        echo "missing"
    fi
}

archive_state() {
    file="$1"
    if [ -f "$file" ]; then
        echo "present ($(wc -c < "$file" | tr -d ' ') bytes)"
        if command -v tar >/dev/null 2>&1; then
            tar -tzf "$file" 2>/dev/null | wc -l | awk '{print "entries: "$1}'
        fi
    else
        echo "missing"
    fi
}

log "SafeLab-Vision Pro Board Acceptance Summary"
log "Root: $ROOT_DIR"
log "Created: $(date 2>/dev/null || echo unknown_time)"
log ""

log "== Board Runtime =="
log "python: $(status_from_health python)"
log "fallback_mode: $(status_from_health fallback_mode)"
log "camera: $(status_from_health camera)"
log "ov13855: $(status_from_health ov13855)"
log "preferred_video21: $(status_from_health preferred_video21)"
log "v4l2_ctl: $(status_from_health v4l2_ctl)"
log "media_ctl: $(status_from_health media_ctl)"
log "rknn_model: $(status_from_health rknn_model)"
log "rknn_runtime: $(status_from_health rknn_runtime)"
log "rknn_common_test: $(status_from_health rknn_common_test)"
log "rk_inference_probe: $(status_from_health rk_inference_probe)"
log "storage_free_mb: $(status_from_health storage_free_mb)"
log ""

log "== Rule Coverage =="
log "model labels include goggles: $(contains "$ROOT_DIR/configs/model_config.yaml" "goggles")"
log "model labels include gloves: $(contains "$ROOT_DIR/configs/model_config.yaml" "gloves")"
log "danger_zone configured: $(contains "$ROOT_DIR/configs/semantic_map.json" "danger_zone")"
log "welding_zone configured: $(contains "$ROOT_DIR/configs/semantic_map.json" "welding_zone")"
log "operation_zone configured: $(contains "$ROOT_DIR/configs/semantic_map.json" "operation_zone")"
log "helmet rule configured: $(contains "$ROOT_DIR/configs/rule_dsl.json" "helmet")"
log "goggles rule configured: $(contains "$ROOT_DIR/configs/rule_dsl.json" "goggles")"
log "gloves rule configured: $(contains "$ROOT_DIR/configs/rule_dsl.json" "gloves")"
log ""

events="$EVENT_DIR/events.jsonl"
actions="$EVENT_DIR/alarm_actions.jsonl"
alarm_db="$EVENT_DIR/alarm_log.db"
actuator="$EVENT_DIR/actuator_log.jsonl"
timeline="$TIMELINE_DIR/board_rule_timeline.json"

log "== Evidence Logs =="
log "events.jsonl lines: $(count_lines "$events")"
log "alarm_actions.jsonl lines: $(count_lines "$actions")"
log "alarm_log.db: $(file_state "$alarm_db")"
log "actuator_log.jsonl lines: $(count_lines "$actuator")"
log "timeline: $(file_state "$timeline")"
log "helmet event present: $(contains "$events" "R001")"
log "goggles event present: $(contains "$events" "R004")"
log "gloves event present: $(contains "$events" "R005")"
log "smoke temporal event present: $(contains "$events" "3 consecutive frames")"
log "duplicate_alarm_count zero evidence: $(contains "$timeline" "\"duplicate_alarm_count\": 0")"
log ""

log "== Reports =="
for file in \
    "$REPORT_DIR/board_health_check.txt" \
    "$REPORT_DIR/health_check.json" \
    "$REPORT_DIR/board_camera_check.txt" \
    "$REPORT_DIR/board_ov13855_diagnose.txt" \
    "$REPORT_DIR/board_rknn_runtime_check.txt" \
    "$REPORT_DIR/board_rknn_common_test_output.txt" \
    "$REPORT_DIR/board_time_check.txt" \
    "$REPORT_DIR/board_rule_contract_report.txt" \
    "$REPORT_DIR/board_log_summary.txt" \
    "$REPORT_DIR/board_competition_mode.txt"; do
    log "$(basename "$file"): $(file_state "$file")"
done
log "board_demo_export.tar.gz: $(archive_state "$REPORT_DIR/board_demo_export.tar.gz")"
log ""

log "== Acceptance Verdict =="
issues=0
if [ "$(count_lines "$events")" -lt 4 ]; then issues=$((issues + 1)); log "[FAIL] expected at least 4 board events"; fi
if [ "$(count_lines "$actions")" -lt 4 ]; then issues=$((issues + 1)); log "[FAIL] expected at least 4 alarm actions"; fi
if [ "$(count_lines "$actuator")" -lt 4 ]; then issues=$((issues + 1)); log "[FAIL] expected at least 4 actuator records"; fi
if [ "$(contains "$events" "R004")" != "yes" ]; then issues=$((issues + 1)); log "[FAIL] missing goggles event evidence"; fi
if [ "$(contains "$events" "R005")" != "yes" ]; then issues=$((issues + 1)); log "[FAIL] missing gloves event evidence"; fi
if [ "$(contains "$timeline" "\"duplicate_alarm_count\": 0")" != "yes" ]; then issues=$((issues + 1)); log "[FAIL] missing duplicate alarm suppression evidence"; fi
if [ "$(status_from_health rknn_model)" = "ok" ] && [ "$(status_from_health rk_inference_probe)" = "ok" ]; then
    log "[OK] RKNN model and single-image runtime probe are verified"
else
    log "[INFO] RKNN model/runtime probe is not fully verified yet"
fi
if [ -f "$REPORT_DIR/board_demo_export.tar.gz" ]; then
    log "[OK] export archive exists"
else
    log "[INFO] export archive is not present yet; competition mode creates it after this summary step"
fi
if [ "$(status_from_health fallback_mode)" != "shell_only+mock_detection" ]; then
    log "[WARN] fallback mode is not shell_only+mock_detection"
fi

if [ "$issues" -eq 0 ]; then
    log "PASS: board shell-only acceptance evidence is complete."
    exit 0
fi

log "FAIL: board acceptance has $issues issue(s)."
exit 1

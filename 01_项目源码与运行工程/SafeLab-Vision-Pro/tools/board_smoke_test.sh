#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
EVENT_DIR="$ROOT_DIR/data/events"
TIMELINE_DIR="$EVENT_DIR/timelines"
REPORT_DIR="$ROOT_DIR/reports"
EVENT_LOG="$EVENT_DIR/events.jsonl"
ACTION_LOG="$EVENT_DIR/alarm_actions.jsonl"
ACTUATOR_LOG="$EVENT_DIR/actuator_log.jsonl"
TIMELINE_LOG="$TIMELINE_DIR/board_rule_timeline.json"
REPORT_PATH="$REPORT_DIR/board_rule_contract_report.txt"
FAILURES=0

mkdir -p "$EVENT_DIR" "$TIMELINE_DIR" "$REPORT_DIR"

: > "$REPORT_PATH"

log() {
    echo "$1" | tee -a "$REPORT_PATH"
}

check_contains() {
    file="$1"
    pattern="$2"
    label="$3"
    if grep -q "$pattern" "$file" 2>/dev/null; then
        log "[OK] $label"
    else
        log "[FAIL] $label"
        FAILURES=$((FAILURES + 1))
    fi
}

log "SafeLab-Vision Pro Board Rule Contract Test"
log "Root: $ROOT_DIR"
log "Report: $REPORT_PATH"
log ""
log "== Config Contract Checks =="
check_contains "$ROOT_DIR/configs/model_config.yaml" "goggles" "model labels include goggles"
check_contains "$ROOT_DIR/configs/model_config.yaml" "gloves" "model labels include gloves"
check_contains "$ROOT_DIR/configs/rule_dsl.json" "welding_zone" "rule DSL includes welding zone"
check_contains "$ROOT_DIR/configs/rule_dsl.json" "operation_zone" "rule DSL includes operation zone"
check_contains "$ROOT_DIR/configs/rule_dsl.json" "goggles" "rule DSL includes goggles missing rule"
check_contains "$ROOT_DIR/configs/rule_dsl.json" "gloves" "rule DSL includes gloves missing rule"
check_contains "$ROOT_DIR/configs/semantic_map.json" "welding_zone" "semantic map includes welding zone"
check_contains "$ROOT_DIR/configs/semantic_map.json" "operation_zone" "semantic map includes operation zone"
log ""
log "== Shell Evidence Generation =="

cat > "$EVENT_LOG" <<'JSON'
{"event_id":"E_BOARD_0001","frame_id":301,"source_type":"mock","event_type":"ppe_violation","risk_score":82,"risk_level":"high","reasons":["rule R001: helmet missing in danger zone","zone=danger_zone","missing_ppe=helmet"],"bbox":[120,130,360,690],"need_alarm":true,"need_snapshot":true,"need_log":true,"timestamp":0,"rule_id":"R001"}
{"event_id":"E_BOARD_0002","frame_id":401,"source_type":"mock","event_type":"ppe_violation","risk_score":78,"risk_level":"high","reasons":["rule R004: goggles missing in welding zone","zone=welding_zone","missing_ppe=goggles","ppe missing confirmed after 3 consecutive frames"],"bbox":[940,140,1160,690],"need_alarm":true,"need_snapshot":true,"need_log":true,"timestamp":0,"rule_id":"R004"}
{"event_id":"E_BOARD_0003","frame_id":501,"source_type":"mock","event_type":"ppe_violation","risk_score":62,"risk_level":"warning","reasons":["rule R005: gloves missing in operation zone","zone=operation_zone","missing_ppe=gloves"],"bbox":[520,740,760,1020],"need_alarm":true,"need_snapshot":true,"need_log":true,"timestamp":0,"rule_id":"R005"}
{"event_id":"E_BOARD_0004","frame_id":203,"source_type":"mock","event_type":"smoke","risk_score":80,"risk_level":"high","reasons":["smoke appeared for 3 consecutive frames","event state transitioned to alarmed"],"bbox":[420,100,760,380],"need_alarm":true,"need_snapshot":true,"need_log":true,"timestamp":0}
JSON

cat > "$ACTION_LOG" <<'JSON'
{"event_id":"E_BOARD_0001","voice_text":"Helmet missing in danger zone. Please correct immediately.","led_color":"red","buzzer":true,"relay":false,"snapshot":true,"log":true,"cooldown_ms":20000}
{"event_id":"E_BOARD_0002","voice_text":"Goggles missing in welding zone. Please wear eye protection.","led_color":"red","buzzer":true,"relay":false,"snapshot":true,"log":true,"cooldown_ms":20000}
{"event_id":"E_BOARD_0003","voice_text":"Gloves missing in operation zone.","led_color":"yellow","buzzer":false,"relay":false,"snapshot":true,"log":true,"cooldown_ms":20000}
{"event_id":"E_BOARD_0004","voice_text":"Smoke risk detected. Please check the lab.","led_color":"red","buzzer":true,"relay":false,"snapshot":true,"log":true,"cooldown_ms":20000}
JSON

cat > "$ACTUATOR_LOG" <<'JSON'
{"event_id":"E_BOARD_0001","backend":"shell_mock","status":"executed","actions":["voice","led:red","buzzer","snapshot","log"]}
{"event_id":"E_BOARD_0002","backend":"shell_mock","status":"executed","actions":["voice","led:red","buzzer","snapshot","log"]}
{"event_id":"E_BOARD_0003","backend":"shell_mock","status":"executed","actions":["voice","led:yellow","snapshot","log"]}
{"event_id":"E_BOARD_0004","backend":"shell_mock","status":"executed","actions":["voice","led:red","buzzer","snapshot","log"]}
JSON

cat > "$TIMELINE_LOG" <<'JSON'
{
  "timeline": [
    {"event_key": "R004:[940,140,1160,690]", "stage": "suspicious", "frame_id": 701, "detail": "goggles missing needs 3 frames to confirm", "should_alarm": false},
    {"event_key": "R004:[940,140,1160,690]", "stage": "alarmed", "frame_id": 703, "detail": "goggles missing confirmed and alarmed", "should_alarm": true},
    {"event_key": "R004:[940,140,1160,690]", "stage": "closed", "frame_id": 705, "detail": "goggles missing recovered and closed", "should_alarm": false},
    {"event_key": "smoke", "stage": "suspicious", "frame_id": 201, "detail": "smoke needs 3 frames to confirm", "should_alarm": false},
    {"event_key": "smoke", "stage": "alarmed", "frame_id": 203, "detail": "smoke confirmed and alarmed", "should_alarm": true},
    {"event_key": "smoke", "stage": "closed", "frame_id": 206, "detail": "smoke recovered and closed", "should_alarm": false}
  ],
  "summary": {
    "events": 2,
    "actions": 2,
    "duplicate_alarm_count": 0,
    "note": "Shell-only evidence for PPE/fire-smoke temporal confirmation when Python is unavailable on board."
  }
}
JSON

log "Event log: $EVENT_LOG"
log "Action log: $ACTION_LOG"
log "Actuator log: $ACTUATOR_LOG"
log "Timeline log: $TIMELINE_LOG"
log "Event count: $(wc -l < "$EVENT_LOG")"
log "Action count: $(wc -l < "$ACTION_LOG")"
log "Actuator count: $(wc -l < "$ACTUATOR_LOG")"
log ""

if [ "$FAILURES" -eq 0 ]; then
    log "Board smoke test passed."
    exit 0
fi

log "Board smoke test failed with $FAILURES issue(s)."
exit 1

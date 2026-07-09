#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
EVENT_DIR="$ROOT_DIR/data/events"
REPORT_PATH="$REPORT_DIR/board_health_check.txt"
FAILURES=0

mkdir -p "$REPORT_DIR" "$EVENT_DIR"
: > "$REPORT_PATH"

log() {
    echo "$1" | tee -a "$REPORT_PATH"
}

check_ok() {
    log "[OK] $1"
}

check_fail() {
    log "[FAIL] $1"
    FAILURES=$((FAILURES + 1))
}

check_exists() {
    if [ -e "$ROOT_DIR/$1" ]; then
        check_ok "$1 exists"
    else
        check_fail "$1 missing"
    fi
}

check_writable_dir() {
    dir="$ROOT_DIR/$1"
    probe="$dir/.health_check_write_test"
    if [ -d "$dir" ] && echo "ok" > "$probe" 2>/dev/null; then
        rm -f "$probe"
        check_ok "$1 is writable"
    else
        check_fail "$1 is not writable"
    fi
}

log "SafeLab-Vision Pro Board Health Check"
log "Root: $ROOT_DIR"
log "Report: $REPORT_PATH"
log ""

log "== Required Directories =="
check_exists "configs"
check_exists "data"
check_exists "data/mock_scenarios"
check_exists "data/events"
check_exists "reports"
check_exists "tools"
log ""

log "== Required Files =="
check_exists "README.md"
check_exists "main.py"
check_exists "configs/semantic_map.json"
check_exists "configs/rule_dsl.json"
check_exists "configs/evaluation_cases.json"
check_exists "configs/video_config.yaml"
check_exists "configs/alarm_policy.yaml"
check_exists "configs/risk_policy.yaml"
check_exists "tools/board_camera_check.sh"
check_exists "tools/board_camera_smoke_test.sh"
check_exists "tools/board_ov13855_diagnose.sh"
check_exists "tools/board_health_status.sh"
check_exists "tools/board_smoke_test.sh"
check_exists "tools/start_safelab.sh"
check_exists "tools/status_safelab.sh"
check_exists "tools/stop_safelab.sh"
check_exists "demo/board_competition_mode.sh"
check_exists "tools/generate_config_audit.py"
check_exists "tools/generate_scenario_catalog.py"
log ""

log "== Write Checks =="
check_writable_dir "data/events"
check_writable_dir "reports"
log ""

log "== System Info =="
if command -v uname >/dev/null 2>&1; then
    log "Kernel: $(uname -a)"
else
    log "Kernel: unavailable"
fi

if command -v date >/dev/null 2>&1; then
    log "Date: $(date)"
fi

if command -v df >/dev/null 2>&1; then
    log ""
    log "Disk:"
    df -h "$ROOT_DIR" 2>/dev/null | tee -a "$REPORT_PATH"
else
    log "Disk: df unavailable"
fi

if command -v free >/dev/null 2>&1; then
    log ""
    log "Memory:"
    free -m 2>/dev/null | tee -a "$REPORT_PATH"
elif [ -r /proc/meminfo ]; then
    log ""
    log "Memory:"
    grep -E 'MemTotal|MemFree|MemAvailable' /proc/meminfo | tee -a "$REPORT_PATH"
else
    log "Memory: unavailable"
fi

log ""
log "Network:"
if command -v ip >/dev/null 2>&1; then
    ip -4 addr show 2>/dev/null | tee -a "$REPORT_PATH"
elif command -v ifconfig >/dev/null 2>&1; then
    ifconfig 2>/dev/null | tee -a "$REPORT_PATH"
else
    log "IP tools unavailable"
fi

log ""
if [ "$FAILURES" -eq 0 ]; then
    log "Health check passed."
    exit 0
fi

log "Health check failed: $FAILURES issue(s)."
exit 1

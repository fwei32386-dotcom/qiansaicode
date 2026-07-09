#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
REPORT_PATH="$REPORT_DIR/board_gpio_contract_check.txt"
CONFIG_PATH="${SAFELAB_GPIO_CONFIG:-$ROOT_DIR/configs/gpio_pin_config.json}"
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

log "SafeLab GPIO Contract Check"
log "Root: $ROOT_DIR"
log "Config: $CONFIG_PATH"
log ""

if [ -d /sys/class/gpio ]; then
    ok "/sys/class/gpio present"
    ls /sys/class/gpio 2>/dev/null | sed 's/^/gpio_entry: /' | tee -a "$REPORT_PATH"
else
    fail "/sys/class/gpio missing"
fi

if [ -f "$CONFIG_PATH" ]; then
    ok "GPIO config present"
else
    fail "GPIO config missing"
fi

log ""
log "== Planned Signals =="
for signal in led_red led_yellow led_green buzzer relay button_mute button_reset button_snapshot; do
    if grep -q "\"$signal\"" "$CONFIG_PATH" 2>/dev/null; then
        ok "signal declared: $signal"
    else
        fail "signal missing from config: $signal"
    fi
done

if grep -q '"enabled"[[:space:]]*:[[:space:]]*true' "$CONFIG_PATH" 2>/dev/null; then
    warn "GPIO real writes are enabled in config; verify wiring before running actuator backend"
else
    ok "GPIO real writes disabled until wiring is confirmed"
fi

log ""
log "Failures: $FAILURES"
log "Warnings: $WARNINGS"
if [ "$FAILURES" -eq 0 ]; then
    log "GPIO contract check completed."
    exit 0
fi

log "GPIO contract check failed."
exit 1

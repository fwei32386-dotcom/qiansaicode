#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
EVENT_DIR="$ROOT_DIR/data/events"
REPORT_DIR="$ROOT_DIR/reports"
ARCHIVE_DIR="$EVENT_DIR/archive"
REPORT_PATH="$REPORT_DIR/board_log_summary.txt"
ACTION="${1:-summary}"

mkdir -p "$EVENT_DIR" "$REPORT_DIR"

log() {
    echo "$1" | tee -a "$REPORT_PATH"
}

usage() {
    echo "Usage:"
    echo "  sh tools/board_log_tools.sh summary"
    echo "  sh tools/board_log_tools.sh tail [lines]"
    echo "  sh tools/board_log_tools.sh archive"
}

log_file_summary() {
    file="$1"
    name="$(basename "$file")"
    if [ -f "$file" ]; then
        log "$name: $(wc -l < "$file") line(s), $(wc -c < "$file") byte(s)"
    else
        log "$name: missing"
    fi
}

summary() {
    : > "$REPORT_PATH"
    log "SafeLab-Vision Pro Board Log Summary"
    log "Report: $REPORT_PATH"
    log ""
    log_file_summary "$EVENT_DIR/events.jsonl"
    log_file_summary "$EVENT_DIR/alarm_actions.jsonl"
    log_file_summary "$EVENT_DIR/alarm_log.db"
    log_file_summary "$EVENT_DIR/actuator_log.jsonl"
}

tail_logs() {
    lines="${1:-5}"
    case "$lines" in
        ''|*[!0-9]*)
            echo "tail lines must be numeric"
            exit 2
            ;;
    esac
    for file in "$EVENT_DIR/events.jsonl" "$EVENT_DIR/alarm_actions.jsonl" "$EVENT_DIR/alarm_log.db" "$EVENT_DIR/actuator_log.jsonl"; do
        echo ""
        echo "== $(basename "$file") =="
        if [ -f "$file" ]; then
            tail -n "$lines" "$file"
        else
            echo "missing"
        fi
    done
}

archive_logs() {
    mkdir -p "$ARCHIVE_DIR"
    stamp="$(date +%Y%m%d_%H%M%S 2>/dev/null || echo unknown_time)"
    moved=0
    for file in "$EVENT_DIR/events.jsonl" "$EVENT_DIR/alarm_actions.jsonl" "$EVENT_DIR/alarm_log.db" "$EVENT_DIR/actuator_log.jsonl"; do
        if [ -f "$file" ]; then
            mv "$file" "$ARCHIVE_DIR/${stamp}_$(basename "$file")"
            moved=$((moved + 1))
        fi
    done
    echo "Archived $moved log file(s) to $ARCHIVE_DIR"
}

case "$ACTION" in
    summary)
        summary
        ;;
    tail)
        tail_logs "${2:-5}"
        ;;
    archive)
        archive_logs
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        echo "Unknown action: $ACTION"
        usage
        exit 2
        ;;
esac

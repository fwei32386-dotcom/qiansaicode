#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
EVENT_DIR="$ROOT_DIR/data/events"
EXPORT_ROOT="$REPORT_DIR/board_demo_export"
REPORT_PATH="$REPORT_DIR/board_competition_mode.txt"
FAILURES=0

mkdir -p "$REPORT_DIR" "$EVENT_DIR"
: > "$REPORT_PATH"

log() {
    echo "$1" | tee -a "$REPORT_PATH"
}

run_step() {
    title="$1"
    shift
    tmp="$REPORT_DIR/.competition_step_output"
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

copy_if_exists() {
    src="$1"
    dst="$2"
    if [ -e "$src" ]; then
        mkdir -p "$(dirname "$dst")"
        cp -R "$src" "$dst"
        log "[COPY] $src -> $dst"
    else
        log "[SKIP] $src missing"
    fi
}

reset_demo_logs() {
    sh "$ROOT_DIR/tools/board_log_tools.sh" archive
    rm -f "$EVENT_DIR/events.jsonl" "$EVENT_DIR/alarm_actions.jsonl" "$EVENT_DIR/alarm_log.db" "$EVENT_DIR/actuator_log.jsonl"
    mkdir -p "$EVENT_DIR"
    log "Demo logs reset."
}

export_demo() {
    rm -rf "$EXPORT_ROOT"
    mkdir -p "$EXPORT_ROOT"
    log ""
    log "== Export Demo Evidence =="
    copy_if_exists "$ROOT_DIR/README.md" "$EXPORT_ROOT/README.md"
    copy_if_exists "$ROOT_DIR/docs/interface_spec.md" "$EXPORT_ROOT/docs/interface_spec.md"
    copy_if_exists "$ROOT_DIR/configs/semantic_map.json" "$EXPORT_ROOT/configs/semantic_map.json"
    copy_if_exists "$ROOT_DIR/configs/rule_dsl.json" "$EXPORT_ROOT/configs/rule_dsl.json"
    copy_if_exists "$ROOT_DIR/configs/video_config.yaml" "$EXPORT_ROOT/configs/video_config.yaml"
    copy_if_exists "$ROOT_DIR/data/events/events.jsonl" "$EXPORT_ROOT/data/events/events.jsonl"
    copy_if_exists "$ROOT_DIR/data/events/alarm_actions.jsonl" "$EXPORT_ROOT/data/events/alarm_actions.jsonl"
    copy_if_exists "$ROOT_DIR/data/events/alarm_log.db" "$EXPORT_ROOT/data/events/alarm_log.db"
    copy_if_exists "$ROOT_DIR/data/events/actuator_log.jsonl" "$EXPORT_ROOT/data/events/actuator_log.jsonl"
    copy_if_exists "$ROOT_DIR/data/events/timelines" "$EXPORT_ROOT/data/events/timelines"
    copy_if_exists "$ROOT_DIR/data/events/raw" "$EXPORT_ROOT/data/events/raw"
    copy_if_exists "$ROOT_DIR/data/events/marked" "$EXPORT_ROOT/data/events/marked"
    copy_if_exists "$ROOT_DIR/reports/board_health_check.txt" "$EXPORT_ROOT/reports/board_health_check.txt"
    copy_if_exists "$ROOT_DIR/reports/health_check.json" "$EXPORT_ROOT/reports/health_check.json"
    copy_if_exists "$ROOT_DIR/reports/health_check.txt" "$EXPORT_ROOT/reports/health_check.txt"
    copy_if_exists "$ROOT_DIR/reports/board_camera_check.txt" "$EXPORT_ROOT/reports/board_camera_check.txt"
    copy_if_exists "$ROOT_DIR/reports/board_ov13855_diagnose.txt" "$EXPORT_ROOT/reports/board_ov13855_diagnose.txt"
    copy_if_exists "$ROOT_DIR/reports/board_rknn_runtime_check.txt" "$EXPORT_ROOT/reports/board_rknn_runtime_check.txt"
    copy_if_exists "$ROOT_DIR/reports/board_rknn_common_test_output.txt" "$EXPORT_ROOT/reports/board_rknn_common_test_output.txt"
    copy_if_exists "$ROOT_DIR/reports/board_time_check.txt" "$EXPORT_ROOT/reports/board_time_check.txt"
    copy_if_exists "$ROOT_DIR/reports/board_log_summary.txt" "$EXPORT_ROOT/reports/board_log_summary.txt"
    copy_if_exists "$ROOT_DIR/reports/board_rule_contract_report.txt" "$EXPORT_ROOT/reports/board_rule_contract_report.txt"
    copy_if_exists "$ROOT_DIR/reports/board_acceptance_summary.txt" "$EXPORT_ROOT/reports/board_acceptance_summary.txt"
    copy_if_exists "$ROOT_DIR/reports/board_ops_report.txt" "$EXPORT_ROOT/reports/board_ops_report.txt"
    copy_if_exists "$ROOT_DIR/reports/smoke_temporal_ablation.csv" "$EXPORT_ROOT/reports/smoke_temporal_ablation.csv"
    copy_if_exists "$ROOT_DIR/reports/state_machine_ablation.csv" "$EXPORT_ROOT/reports/state_machine_ablation.csv"
    copy_if_exists "$ROOT_DIR/reports/ablation_summary.json" "$EXPORT_ROOT/reports/ablation_summary.json"
    copy_if_exists "$ROOT_DIR/reports/pipeline_latency.csv" "$EXPORT_ROOT/reports/pipeline_latency.csv"
    copy_if_exists "$ROOT_DIR/reports/pipeline_latency_summary.json" "$EXPORT_ROOT/reports/pipeline_latency_summary.json"
    copy_if_exists "$REPORT_PATH" "$EXPORT_ROOT/reports/board_competition_mode.txt"

    manifest="$EXPORT_ROOT/manifest.txt"
    {
        echo "SafeLab-Vision Pro Board Demo Export"
        echo "Root: $ROOT_DIR"
        echo "Created: $(date 2>/dev/null || echo unknown_time)"
        echo "Failures: $FAILURES"
        echo ""
        echo "Files:"
        find "$EXPORT_ROOT" -type f | sort
    } > "$manifest"

    archive="$REPORT_DIR/board_demo_export.tar.gz"
    rm -f "$archive"
    if tar -czf "$archive" -C "$REPORT_DIR" "board_demo_export" >> "$REPORT_PATH" 2>&1; then
        log "[OK] Export archive: $archive"
    else
        log "[FAIL] Export archive failed"
        FAILURES=$((FAILURES + 1))
    fi
}

usage() {
    echo "Usage:"
    echo "  sh demo/board_competition_mode.sh run"
    echo "  sh demo/board_competition_mode.sh reset"
    echo "  sh demo/board_competition_mode.sh export"
}

ACTION="${1:-run}"

case "$ACTION" in
    run)
        log "SafeLab-Vision Pro Board Competition Mode"
        log "Root: $ROOT_DIR"
        log "Report: $REPORT_PATH"
        reset_demo_logs
        run_step "Board health check" sh "$ROOT_DIR/tools/board_health_check.sh"
        run_step "Board health status" sh "$ROOT_DIR/tools/board_health_status.sh"
        run_step "Board camera check" sh "$ROOT_DIR/tools/board_camera_check.sh"
        run_step "Board OV13855 diagnosis" sh "$ROOT_DIR/tools/board_ov13855_diagnose.sh"
        run_step "Board time check" sh "$ROOT_DIR/tools/board_time_check.sh"
        run_step "Board RKNN runtime check" sh "$ROOT_DIR/tools/board_rknn_runtime_check.sh"
        run_step "Board health status after RKNN check" sh "$ROOT_DIR/tools/board_health_status.sh"
        run_step "Board smoke test" sh "$ROOT_DIR/tools/board_smoke_test.sh"
        run_step "Board log summary" sh "$ROOT_DIR/tools/board_log_tools.sh" summary
        run_step "Board acceptance summary" sh "$ROOT_DIR/tools/board_acceptance_summary.sh"
        export_demo
        run_step "Board acceptance summary after export" sh "$ROOT_DIR/tools/board_acceptance_summary.sh"
        export_demo
        ;;
    reset)
        log "SafeLab-Vision Pro Board Competition Reset"
        reset_demo_logs
        ;;
    export)
        log "SafeLab-Vision Pro Board Competition Export"
        export_demo
        ;;
    -h|--help|help)
        usage
        exit 0
        ;;
    *)
        echo "Unknown action: $ACTION"
        usage
        exit 2
        ;;
esac

log ""
if [ "$FAILURES" -eq 0 ]; then
    log "Competition mode completed successfully."
    exit 0
fi

log "Competition mode completed with $FAILURES issue(s)."
exit 1

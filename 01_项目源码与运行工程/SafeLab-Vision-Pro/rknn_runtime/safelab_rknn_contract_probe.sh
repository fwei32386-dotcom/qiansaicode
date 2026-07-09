#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
OUTPUT_PATH="${1:-$REPORT_DIR/rknn_detection_contract.jsonl}"
REPORT_PATH="$REPORT_DIR/rknn_detection_contract_check.txt"

mkdir -p "$REPORT_DIR" "$(dirname "$OUTPUT_PATH")"
: > "$REPORT_PATH"

log() {
    echo "$1" | tee -a "$REPORT_PATH"
}

log "SafeLab RKNN Detection Contract Probe"
log "Root: $ROOT_DIR"
log "Output: $OUTPUT_PATH"
log ""

cat > "$OUTPUT_PATH" <<'JSON'
{"frame_id":1,"source_type":"camera","class_name":"person","confidence":0.91,"bbox":[10,20,110,220],"center":[60,120],"area":20000,"model_name":"safelab_yolov8n_rknn_contract_probe","infer_time_ms":0.0}
JSON

failures=0
for key in frame_id source_type class_name confidence bbox center area model_name infer_time_ms; do
    if grep -q "\"$key\"" "$OUTPUT_PATH"; then
        log "[OK] field present: $key"
    else
        log "[FAIL] field missing: $key"
        failures=$((failures + 1))
    fi
done

if grep -q '"class_name":"person"' "$OUTPUT_PATH" && grep -q '"source_type":"camera"' "$OUTPUT_PATH"; then
    log "[OK] Detection JSON contract probe is ready"
else
    log "[FAIL] Detection JSON contract probe has invalid label/source"
    failures=$((failures + 1))
fi

log ""
log "Failures: $failures"
if [ "$failures" -eq 0 ]; then
    exit 0
fi
exit 1

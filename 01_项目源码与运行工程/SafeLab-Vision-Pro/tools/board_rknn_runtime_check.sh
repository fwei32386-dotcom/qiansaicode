#!/bin/sh
set -u

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
REPORT_PATH="$REPORT_DIR/board_rknn_runtime_check.txt"
JSON_REPORT_PATH="$REPORT_DIR/board_rknn_runtime_check.json"
MODEL_PATH="${SAFELAB_RKNN_MODEL:-$ROOT_DIR/models/rknn/safelab_yolov8n_fire_smoke_v3.rknn}"
LABELS_PATH="${SAFELAB_LABELS:-$ROOT_DIR/models/labels.txt}"
TEST_IMAGE_DIR="${SAFELAB_TEST_IMAGES:-$ROOT_DIR/test_images}"
PROBE_OUTPUT="$REPORT_DIR/board_rknn_common_test_output.txt"
CONTRACT_OUTPUT="$REPORT_DIR/rknn_detection_contract.jsonl"
BINARY_PATH="$ROOT_DIR/rknn_runtime/safelab_rknn_detect"
BINARY_CONTRACT_OUTPUT="$REPORT_DIR/rknn_binary_contract.jsonl"
FAILURES=0
WARNINGS=0
PROBE_STATUS="skipped"
PROBE_FPS="unknown"
PROBE_ELAPSE_MS="unknown"
CONTRACT_STATUS="missing"
BINARY_STATUS="missing"
BINARY_CONTRACT_STATUS="missing"
MODEL_STATUS="missing"
LABELS_STATUS="missing"
TEST_IMAGES_STATUS="missing"
RUNTIME_STATUS="missing"
HEADER_STATUS="missing"
COMPILER_STATUS="missing"
BUILD_STATE="unknown"
HEADER_PATH=""
COMPILER_PATH=""
header_status="$HEADER_STATUS"
compiler_status="$COMPILER_STATUS"

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

check_file() {
    label="$1"
    path="$2"
    if [ -f "$path" ]; then
        size="$(wc -c < "$path" | tr -d ' ')"
        ok "$label: $path ($size bytes)"
        return 0
    else
        fail "$label missing: $path"
        return 1
    fi
}

tool_status() {
    tool="$1"
    if command -v "$tool" >/dev/null 2>&1; then
        ok "$tool: $(command -v "$tool")"
    else
        warn "$tool missing"
    fi
}

log "SafeLab-Vision Pro Board RKNN Runtime Check"
log "Root: $ROOT_DIR"
log "Report: $REPORT_PATH"
log "JSON report: $JSON_REPORT_PATH"
log "Probe output: $PROBE_OUTPUT"
log ""

log "== Runtime Files =="
if check_file "RKNN model" "$MODEL_PATH"; then
    MODEL_STATUS="ok"
fi
if check_file "Labels" "$LABELS_PATH"; then
    LABELS_STATUS="ok"
fi
if [ -d "$TEST_IMAGE_DIR" ]; then
    count="$(find "$TEST_IMAGE_DIR" -maxdepth 1 -type f 2>/dev/null | wc -l | tr -d ' ')"
    ok "test_images: $TEST_IMAGE_DIR ($count files)"
    TEST_IMAGES_STATUS="ok"
else
    warn "test image directory missing: $TEST_IMAGE_DIR"
fi

log ""
log "== RKNN Runtime =="
if [ -f /usr/lib/librknnrt.so ]; then
    ok "/usr/lib/librknnrt.so present"
    RUNTIME_STATUS="ok"
else
    fail "/usr/lib/librknnrt.so missing"
fi
tool_status rknn_common_test

log ""
log "== Build Environment =="
tool_status gcc
tool_status g++
tool_status cc
tool_status make
tool_status cmake

if find /usr/include /usr/local/include "$ROOT_DIR" -name rknn_api.h 2>/dev/null | head -n 1 | grep -q .; then
    HEADER_PATH="$(find /usr/include /usr/local/include "$ROOT_DIR" -name rknn_api.h 2>/dev/null | head -n 1)"
    HEADER_STATUS="ok"
    header_status="$HEADER_STATUS"
    ok "rknn_api.h: $HEADER_PATH"
else
    warn "rknn_api.h missing; board cannot build RKNN C/C++ examples without SDK headers"
fi
for compiler in g++ c++ aarch64-buildroot-linux-gnu-g++ aarch64-linux-gnu-g++; do
    if command -v "$compiler" >/dev/null 2>&1; then
        COMPILER_PATH="$(command -v "$compiler")"
        COMPILER_STATUS="ok"
        compiler_status="$COMPILER_STATUS"
        break
    fi
done
if [ "$COMPILER_STATUS" = "ok" ]; then
    ok "C++ compiler usable for local build: $COMPILER_PATH"
elif [ "$HEADER_STATUS" = "ok" ]; then
    warn "C++ compiler missing; cross_compile_required"
else
    warn "C++ compiler missing; header_and_cross_compile_required"
fi

log ""
log "== SafeLab RKNN Binary =="
if [ -f "$BINARY_PATH" ]; then
    size="$(wc -c < "$BINARY_PATH" | tr -d ' ')"
    BINARY_STATUS="present"
    ok "safelab_rknn_detect: $BINARY_PATH ($size bytes)"
    chmod +x "$BINARY_PATH" 2>/dev/null || true
    : > "$BINARY_CONTRACT_OUTPUT"
    # A contract run proves the uploaded aarch64 binary can execute on this board
    # and still emits the Detection JSON consumed by the Python rule pipeline.
    if "$BINARY_PATH" --contract > "$BINARY_CONTRACT_OUTPUT" 2>> "$REPORT_PATH"; then
        if grep -q '"model_name":"safelab_yolov8n_rknn_contract_probe"' "$BINARY_CONTRACT_OUTPUT" 2>/dev/null; then
            BINARY_CONTRACT_STATUS="ok"
            ok "safelab_rknn_detect contract: $BINARY_CONTRACT_OUTPUT"
        else
            BINARY_CONTRACT_STATUS="invalid_json"
            warn "safelab_rknn_detect contract output missing expected model_name"
        fi
    else
        BINARY_CONTRACT_STATUS="fail"
        warn "safelab_rknn_detect --contract failed"
    fi
else
    warn "safelab_rknn_detect binary missing: $BINARY_PATH"
fi

log ""
log "== Optional rknn_common_test Probe =="
first_image="$(find "$TEST_IMAGE_DIR" -maxdepth 1 -type f \( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' \) 2>/dev/null | head -n 1)"
if command -v rknn_common_test >/dev/null 2>&1 && [ -f "$MODEL_PATH" ] && [ -n "$first_image" ]; then
    log "model: $MODEL_PATH"
    log "image: $first_image"
    : > "$PROBE_OUTPUT"
    if timeout 30 rknn_common_test "$MODEL_PATH" "$first_image" 1 > "$PROBE_OUTPUT" 2>&1; then
        cat "$PROBE_OUTPUT" | tee -a "$REPORT_PATH"
        PROBE_STATUS="ok"
        PROBE_LINE="$(grep -E "Elapse Time" "$PROBE_OUTPUT" 2>/dev/null | head -n 1)"
        if [ -n "$PROBE_LINE" ]; then
            PROBE_ELAPSE_MS="$(echo "$PROBE_LINE" | sed -n 's/.*Elapse Time = *\([0-9.]*\)ms.*/\1/p')"
            PROBE_FPS="$(echo "$PROBE_LINE" | sed -n 's/.*FPS = *\([0-9.]*\).*/\1/p')"
        fi
    else
        cat "$PROBE_OUTPUT" | tee -a "$REPORT_PATH"
        PROBE_STATUS="fail"
        warn "rknn_common_test probe failed"
    fi
else
    warn "rknn_common_test probe skipped"
fi

log ""
log "== Integration State =="
if [ -x "$ROOT_DIR/rknn_runtime/safelab_rknn_contract_probe.sh" ] || [ -f "$ROOT_DIR/rknn_runtime/safelab_rknn_contract_probe.sh" ]; then
    if sh "$ROOT_DIR/rknn_runtime/safelab_rknn_contract_probe.sh" "$CONTRACT_OUTPUT" >/dev/null 2>&1; then
        CONTRACT_STATUS="ok"
        ok "Detection JSON contract probe: $CONTRACT_OUTPUT"
    else
        CONTRACT_STATUS="fail"
        warn "Detection JSON contract probe failed"
    fi
else
    warn "Detection JSON contract probe missing"
fi
if [ "$PROBE_STATUS" = "ok" ]; then
    log "model_runtime_state: model_load_and_single_image_probe_ok"
else
    log "model_runtime_state: $PROBE_STATUS"
fi
log "probe_elapsed_ms: $PROBE_ELAPSE_MS"
log "probe_fps: $PROBE_FPS"
log "detection_json_contract: $CONTRACT_STATUS"
log "safelab_binary_status: $BINARY_STATUS"
log "safelab_binary_contract: $BINARY_CONTRACT_STATUS"
if [ "$BINARY_CONTRACT_STATUS" = "ok" ]; then
    log "system_integration_state: safelab_rknn_detect_binary_ready"
else
    log "system_integration_state: waiting_for_safelab_rknn_detect_postprocess_and_detection_json"
fi
header_status="$HEADER_STATUS"
compiler_status="$COMPILER_STATUS"
if [ "$BINARY_CONTRACT_STATUS" = "ok" ]; then
    BUILD_STATE="board_binary_present"
elif [ "$HEADER_STATUS" = "ok" ] && [ "$COMPILER_STATUS" = "ok" ]; then
    BUILD_STATE="ready_for_board_build"
elif [ "$HEADER_STATUS" = "ok" ]; then
    BUILD_STATE="cross_compile_required"
elif [ "$COMPILER_STATUS" = "ok" ]; then
    BUILD_STATE="waiting_for_rknn_api_header"
else
    BUILD_STATE="waiting_for_rknn_api_header_and_cross_compiler"
fi
log "header_status: $HEADER_STATUS"
log "compiler_status: $COMPILER_STATUS"
log "build_state: $BUILD_STATE"

# Keep a machine-readable report beside the human-readable log so tests,
# dashboards, and pull scripts can consume board readiness without parsing text.
cat > "$JSON_REPORT_PATH" <<EOF
{
  "root": "$ROOT_DIR",
  "model_path": "$MODEL_PATH",
  "model_status": "$MODEL_STATUS",
  "labels_path": "$LABELS_PATH",
  "labels_status": "$LABELS_STATUS",
  "test_image_dir": "$TEST_IMAGE_DIR",
  "test_images_status": "$TEST_IMAGES_STATUS",
  "librknnrt_status": "$RUNTIME_STATUS",
  "rknn_common_test_status": "$PROBE_STATUS",
  "rknn_api_header_status": "$HEADER_STATUS",
  "rknn_api_header_path": "$HEADER_PATH",
  "compiler_status": "$COMPILER_STATUS",
  "compiler_path": "$COMPILER_PATH",
  "probe_elapsed_ms": "$PROBE_ELAPSE_MS",
  "probe_fps": "$PROBE_FPS",
  "detection_json_contract": "$CONTRACT_STATUS",
  "safelab_binary_status": "$BINARY_STATUS",
  "safelab_binary_contract": "$BINARY_CONTRACT_STATUS",
  "safelab_binary_path": "$BINARY_PATH",
  "build_state": "$BUILD_STATE",
  "failures": $FAILURES,
  "warnings": $WARNINGS
}
EOF

log ""
log "== Summary =="
log "Failures: $FAILURES"
log "Warnings: $WARNINGS"

if [ "$FAILURES" -eq 0 ]; then
    log "RKNN runtime check completed."
    exit 0
fi

log "RKNN runtime check failed: $FAILURES issue(s)."
exit 1

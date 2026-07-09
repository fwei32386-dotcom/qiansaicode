#!/usr/bin/env bash
set -euo pipefail

PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOARD_HOST="${BOARD_HOST:-192.168.0.232}"
BOARD_USER="${BOARD_USER:-root}"
BOARD_PROJECT="${BOARD_PROJECT:-/root/SafeLab-Vision-Pro}"
LOCAL_BINARY="$PACK_DIR/rknn_runtime/safelab_rknn_detect"
REMOTE_BINARY="$BOARD_PROJECT/rknn_runtime/safelab_rknn_detect"
REMOTE_MODEL="$BOARD_PROJECT/models/rknn/safelab_yolov8n_fire_smoke_v3.rknn"
REMOTE_SAMPLE="$BOARD_PROJECT/reports/rknn_image_samples/sample_01_rgb_u8.rgb"
REMOTE_OUTPUT="$BOARD_PROJECT/reports/rknn_image_samples/debug_sample_01.jsonl"

"$PACK_DIR/build_in_ubuntu.sh"

echo "[deploy] Copy updated RKNN binary to board"
ssh "$BOARD_USER@$BOARD_HOST" "mkdir -p '$BOARD_PROJECT/rknn_runtime' '$BOARD_PROJECT/reports/rknn_image_samples'"
scp "$LOCAL_BINARY" "$BOARD_USER@$BOARD_HOST:$REMOTE_BINARY"

echo "[deploy] Run one debug inference on the board"
# The debug flags print RKNN tensor attributes and per-channel output statistics.
ssh "$BOARD_USER@$BOARD_HOST" "
  chmod +x '$REMOTE_BINARY' &&
  '$REMOTE_BINARY' \
    --model '$REMOTE_MODEL' \
    --image '$REMOTE_SAMPLE' \
    --frame-id 1 \
    --frame-width 640 \
    --frame-height 640 \
    --input-type uint8 \
    --conf-threshold 0.25 \
    --dump-output-stats \
    --output '$REMOTE_OUTPUT'
"

echo "[deploy] Debug output JSONL: $REMOTE_OUTPUT"

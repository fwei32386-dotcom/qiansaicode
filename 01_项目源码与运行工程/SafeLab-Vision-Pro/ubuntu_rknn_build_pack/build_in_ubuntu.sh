#!/usr/bin/env bash
set -euo pipefail

PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLCHAIN_ARCHIVE="$PACK_DIR/toolchain/aarch64-buildroot-linux-gnu_sdk-buildroot.tar.gz"
TOOLCHAIN_DIR="$PACK_DIR/toolchains/aarch64-buildroot-linux-gnu_sdk-buildroot"
RUNTIME_DIR="$PACK_DIR/rknn_runtime"
RKNN_INCLUDE_DIR="$PACK_DIR/rknn_sdk_2.3.2/include"
RKNN_LIB_DIR="$PACK_DIR/rknn_sdk_2.3.2/lib/aarch64"

echo "[1/4] Prepare Buildroot cross toolchain"
mkdir -p "$PACK_DIR/toolchains"
if [ ! -d "$TOOLCHAIN_DIR" ]; then
  tar -xzf "$TOOLCHAIN_ARCHIVE" -C "$PACK_DIR/toolchains"
fi

cd "$TOOLCHAIN_DIR"
if [ -f ./relocate-sdk.sh ]; then
  ./relocate-sdk.sh
fi
export PATH="$TOOLCHAIN_DIR/bin:$PATH"

echo "[2/4] Check compiler"
aarch64-buildroot-linux-gnu-g++ --version

echo "[3/4] Build safelab_rknn_detect"
cd "$RUNTIME_DIR"
make clean
make WITH_RKNN=1 \
  CXX=aarch64-buildroot-linux-gnu-g++ \
  RKNN_INCLUDE_DIR="$RKNN_INCLUDE_DIR" \
  RKNN_LIB_DIR="$RKNN_LIB_DIR"

echo "[4/4] Verify output"
file "$RUNTIME_DIR/safelab_rknn_detect"
ls -lh "$RUNTIME_DIR/safelab_rknn_detect"
echo
echo "Build OK: $RUNTIME_DIR/safelab_rknn_detect"

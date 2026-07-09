# RKNN Cross Compile on Ubuntu

Purpose: build `rknn_runtime/safelab_rknn_detect` for the RK3588 Buildroot board when the board has `/usr/lib/librknnrt.so` and `rknn_api.h`, but no board-side `g++`.

Current board facts:

```text
OS: Buildroot 2021.11
CPU: aarch64
/usr/lib/librknnrt.so: present
/usr/local/include/rknn_api.h: present
gcc/g++/apt/opkg: missing
```

## 1. Prepare the Ubuntu SDK

Run these commands inside Ubuntu or WSL Ubuntu. Do not use the SDK directory extracted by Windows `tar`, because the Buildroot SDK contains Linux symlinks and Linux host binaries.

```sh
mkdir -p ~/toolchains
tar -xzf /mnt/d/ELFrk3588/06-常用工具/01-编译工具安装脚本/aarch64-buildroot-linux-gnu_sdk-buildroot.tar.gz -C ~/toolchains

cd ~/toolchains/aarch64-buildroot-linux-gnu_sdk-buildroot
if [ -f ./relocate-sdk.sh ]; then
  ./relocate-sdk.sh
fi

export PATH="$PWD/bin:$PATH"
aarch64-buildroot-linux-gnu-g++ --version
```

Expected: the compiler prints a GCC version. If the command is missing, the SDK extraction or `PATH` is wrong.

## 2. Build SafeLab RKNN Runtime

```sh
cd /mnt/d/ELFrk3588/SafeLab-Vision-Pro/rknn_runtime

make clean
make WITH_RKNN=1 \
  CXX=aarch64-buildroot-linux-gnu-g++ \
  RKNN_INCLUDE_DIR=/mnt/d/ELFrk3588/rknn_sdk_2.3.2/include \
  RKNN_LIB_DIR=/mnt/d/ELFrk3588/rknn_sdk_2.3.2/lib/aarch64
```

Expected output:

```text
rknn_runtime/safelab_rknn_detect
```

## 3. Upload to Board

```sh
scp safelab_rknn_detect root@192.168.0.232:/root/SafeLab-Vision-Pro/rknn_runtime/
```

## 4. Verify on Board

```sh
ssh root@192.168.0.232 '
  cd /root/SafeLab-Vision-Pro &&
  chmod +x rknn_runtime/safelab_rknn_detect &&
  sh tools/board_rknn_runtime_check.sh &&
  rknn_runtime/safelab_rknn_detect --contract
'
```

Expected:

```text
reports/board_rknn_runtime_check.txt
reports/board_rknn_runtime_check.json
reports/board_rknn_common_test_output.txt
reports/rknn_detection_contract.jsonl
```

The JSON report should show:

```json
{
  "rknn_api_header_status": "ok",
  "librknnrt_status": "ok",
  "build_state": "cross_compile_required"
}
```

After the binary is uploaded, a future script update may report `ready_for_board_build` or `board_binary_present` depending on the acceptance gate used.

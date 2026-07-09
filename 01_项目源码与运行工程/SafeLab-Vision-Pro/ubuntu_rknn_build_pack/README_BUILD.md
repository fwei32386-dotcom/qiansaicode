# SafeLab RKNN Ubuntu Build Pack

这个文件夹是给 Ubuntu 编译 `safelab_rknn_detect` 用的最小包。

## 内容

- `rknn_runtime/`：C++ 源码和 Makefile
- `rknn_sdk_2.3.2/`：`rknn_api.h` 和 `librknnrt.so`
- `toolchain/aarch64-buildroot-linux-gnu_sdk-buildroot.tar.gz`：Buildroot aarch64 交叉编译 SDK
- `build_in_ubuntu.sh`：Ubuntu 一键编译脚本

## Ubuntu 里执行

进入这个文件夹后运行：

```bash
chmod +x build_in_ubuntu.sh
./build_in_ubuntu.sh
```

成功后生成：

```text
rknn_runtime/safelab_rknn_detect
```

`file rknn_runtime/safelab_rknn_detect` 应显示 `ELF 64-bit` 和 `aarch64`。

## 上传板端

```bash
scp rknn_runtime/safelab_rknn_detect root@192.168.0.232:/root/SafeLab-Vision-Pro/rknn_runtime/
```

板端验证：

```bash
ssh root@192.168.0.232 '
  cd /root/SafeLab-Vision-Pro &&
  chmod +x rknn_runtime/safelab_rknn_detect &&
  sh tools/board_rknn_runtime_check.sh &&
  rknn_runtime/safelab_rknn_detect --contract
'
```

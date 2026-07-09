# SafeLab RKNN 调试版构建说明

这版修复了板端图片推理的一个关键疑点：默认输入改为 `UINT8 + pass_through=0`。
旧版把普通 RGB 字节声明成 `INT8`，会导致 RKNN SDK 在输入边界错误解释图像，表现为模型能运行但检测结果为空。

## 在 Ubuntu 里重编并部署

```bash
cd ~/ubuntu_rknn_build_pack
chmod +x build_in_ubuntu.sh deploy_debug_to_board.sh
./deploy_debug_to_board.sh
```

脚本会完成三件事：

1. 交叉编译 `rknn_runtime/safelab_rknn_detect`
2. 上传新二进制到 `root@192.168.0.232:/root/SafeLab-Vision-Pro/rknn_runtime/`
3. 用 `sample_01_rgb_u8.rgb` 跑一次带 tensor 统计的调试推理

## 回到 Windows 继续批量测试

```powershell
cd D:\ELFrk3588\SafeLab-Vision-Pro
python tools\run_board_rknn_image_samples.py
```

结果会写入：

```text
reports/rknn_image_samples/summary.json
```

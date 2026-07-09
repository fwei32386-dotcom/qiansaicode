# 重新导出非量化 RKNN 模型

当前板端 INT8 RKNN 的输出统计显示：

```text
ch0-ch3 box channels: non-zero
ch4-ch10 class channels: all zero
```

这说明 YOLOv8 的坐标和类别分数共用一个 INT8 输出量化尺度时，`0-1` 的类别分数被 `0-640` 的坐标范围压没了。先导出非量化 RKNN，确认真实图片检测链路。

## Ubuntu 里执行

进入传到 Ubuntu 的 `rknn_transfer_package`：

```bash
cd ~/rknn_transfer_package
python3 convert_onnx_to_rknn_fp.py
```

生成文件：

```text
models/rknn/safelab_yolov8n_fire_smoke_v3_fp.rknn
```

## 传到板卡

如果 Ubuntu 能连板卡：

```bash
scp models/rknn/safelab_yolov8n_fire_smoke_v3_fp.rknn root@192.168.0.232:/root/SafeLab-Vision-Pro/models/rknn/
```

如果 Ubuntu 不能连板卡，就先把 `.rknn` 复制回 Windows，再让我从 Windows 上传。

## Windows 侧复测

```powershell
python tools\run_board_rknn_image_samples.py --model /root/SafeLab-Vision-Pro/models/rknn/safelab_yolov8n_fire_smoke_v3_fp.rknn
```

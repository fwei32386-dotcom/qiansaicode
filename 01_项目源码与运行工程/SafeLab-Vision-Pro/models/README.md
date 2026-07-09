# 模型目录

完整版提交包已经包含当前演示链路使用的模型文件。

目录用途：

```text
models/checkpoints/    PyTorch 训练权重
models/onnx/           ONNX 导出文件
models/rknn/           RK3588 板端 RKNN 文件
```

当前标签文件：

```text
models/labels.txt
models/ppe_labels.txt
models/model_manifest.json
```

板端默认模型路径：

```text
/root/safelab_deploy_current/models/safelab_ppe_hybrid_int8.rknn
/root/safelab_deploy_current/models/safelab_fire_smoke_fp.rknn
```

为了匹配默认启动参数，`models/rknn/` 中保留了两个部署默认名：

```text
safelab_ppe_hybrid_int8.rknn
safelab_fire_smoke_fp.rknn
```

如果板端模型文件名变化，请修改启动参数或配置文件。

<<<<<<< HEAD
# SafeLab Vision Pro 完整版提交包

项目名称：基于 RK3588 的多模态实验室安全巡检与智能告警系统

本目录是比赛提交用完整版，包含项目代码、网页端、RK3588 板端运行代码、模型文件、技术文档和演示视频。

## 目录

```text
01_项目源码与运行工程/
  SafeLab-Vision-Pro/        完整源码、网页端、测试、配置、模型文件
02_技术文档与设计文件/        技术文档 PDF
03_演示视频/                  演示视频
04_提交说明/                  运行说明和材料清单
05_附录_交接说明/              队内交接材料，非主体材料
```

## 运行入口

进入源码目录：

```powershell
cd .\01_项目源码与运行工程\SafeLab-Vision-Pro
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python tools/serve_live_dashboard.py --host 127.0.0.1 --port 60331
```

网页地址：

```text
http://127.0.0.1:60331/
```

## 模型

模型文件已放入：

```text
01_项目源码与运行工程/SafeLab-Vision-Pro/models/
```

其中 RK3588 演示链路默认使用：

```text
models/rknn/safelab_ppe_hybrid_int8.rknn
models/rknn/safelab_fire_smoke_fp.rknn
```


# qiansaicode
use for qiansai
>>>>>>> e3bc4b807782e3d143c84f38a260f6dd39999ff2

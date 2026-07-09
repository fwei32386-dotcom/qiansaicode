# SafeLab Vision Pro 完整版提交包

项目名称：基于 RK3588 的多模态实验室安全巡检与智能告警系统

本仓库为比赛提交用完整版，包含项目代码、网页端、RK3588 板端运行代码、模型文件、技术文档、演示视频和提交说明。

## 目录

```text
01_项目源码与运行工程/
  SafeLab-Vision-Pro/        完整源码、网页端、测试、配置、模型文件

02_技术文档与设计文件/        技术文档 PDF

03_演示视频/                  演示视频

04_提交说明/                  运行说明和材料清单
运行入口
进入源码目录：
cd .\01_项目源码与运行工程\SafeLab-Vision-Pro
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python tools/serve_live_dashboard.py --host 127.0.0.1 --port 60331
网页地址：
http://127.0.0.1:60331/
模型
模型文件已放入：
01_项目源码与运行工程/SafeLab-Vision-Pro/models/
其中 RK3588 演示链路默认使用：
models/rknn/safelab_ppe_hybrid_int8.rknn
models/rknn/safelab_fire_smoke_fp.rknn
提交说明
材料清单：
04_提交说明/材料清单.md
运行说明：
04_提交说明/运行说明.md
说明
本仓库仅用于竞赛/项目提交材料归档。

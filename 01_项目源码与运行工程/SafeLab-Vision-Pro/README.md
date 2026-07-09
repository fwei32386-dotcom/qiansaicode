# SafeLab-Vision Pro

关键词：边缘智能、双场景安全、闭环告警。

SafeLab-Vision Pro 是一套面向实验室与工地场景的安全视觉检测系统。项目运行在 RK3588 边缘板卡上，使用双模型检测人员防护与火烟风险，并通过网页端展示视频画面、检测框、事件记录、智能报告和语音告警。

## 主要功能

- 摄像头输入与本地图片/视频输入。
- PPE 检测：人员、安全帽、反光背心、护目镜、手套。
- 火烟检测：火焰、烟雾。
- 场景模式：
  - 工地：重点检查安全帽、反光背心。
  - 实验室：重点检查护目镜、手套。
- 检测结果叠加到视频画面，并记录事件、检测帧和告警信息。
- 支持将媒体上传到 RK3588 后在板端运行识别。
- 支持网页端查看风险时间线、检测记录、智能说明和高风险事件。

## 目录说明

```text
dashboard/              Web 控制台与本地服务
tools/                  启动、同步、检测桥接、报告生成工具
safety_brain/           PPE 关联、规则引擎、时序判断
runtime/                回放与运行逻辑
rknn_runtime/           RKNN 板端运行相关代码
configs/                视频、模型、规则配置
models/                 标签和模型放置说明，权重文件不随仓库提交
demo_assets/            演示视频、截图、答辩材料占位目录
docs/                   接口、部署、方案与验收文档
handoff/                队友交接材料
tests/                  单元测试
```

## 环境准备

推荐使用 Python 3.10。

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

RK3588 板卡连接参数建议写入环境变量：

```powershell
$env:SAFELAB_BOARD_HOST="192.168.0.232"
$env:SAFELAB_BOARD_USER="root"
$env:SAFELAB_BOARD_PASSWORD="root"
```

也可以复制 `.env.example` 后按本机环境填写。

## 启动网页端

```powershell
python tools/serve_live_dashboard.py --host 127.0.0.1 --port 60331
```

浏览器打开：

```text
http://127.0.0.1:60331/
```

网页端可以切换摄像头输入、本地输入、场景模式和模型检测频率。摄像头链路需要板卡在线，本地媒体链路需要先选择图片或视频。

## 启动摄像头预览

```powershell
python tools/start_board_camera_live_preview.py `
  --host $env:SAFELAB_BOARD_HOST `
  --username $env:SAFELAB_BOARD_USER `
  --password $env:SAFELAB_BOARD_PASSWORD
```

默认摄像头设备为 `/dev/video-camera0`。如果板卡设备名不同，使用 `--device` 指定。

## 启动双模型检测桥接

```powershell
python tools/run_live_dual_model_bridge.py `
  --host $env:SAFELAB_BOARD_HOST `
  --username $env:SAFELAB_BOARD_USER `
  --password $env:SAFELAB_BOARD_PASSWORD
```

桥接程序会读取网页端当前输入源，把检测结果写入 `data/events/` 和 `reports/live_pipeline/`。网页会读取这些结果并刷新画面叠框、事件和检测记录。

## 模型文件

仓库不提交 `.pt`、`.onnx`、`.rknn` 等大模型文件。队友拿到项目后，把模型放到以下目录：

```text
models/rknn/
models/onnx/
models/checkpoints/
```

当前板端默认路径：

```text
/root/safelab_deploy_current/models/safelab_ppe_hybrid_int8.rknn
/root/safelab_deploy_current/models/safelab_fire_smoke_fp.rknn
```

如果模型文件名变化，请同步修改启动参数或配置文件。

## 演示材料

把答辩视频、截图、三张工地测试图片和实验室演示视频放到 `demo_assets/`。如果视频超过 GitHub 单文件限制，建议上传到 GitHub Release、Gitee 附件或网盘，并在 `demo_assets/README.md` 填写链接。

## 测试

```powershell
python -m unittest tests.test_rule_dsl_engine tests.test_live_dashboard tests.test_dashboard_input_source -v
```

完整测试可以运行：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

部分板卡测试需要 RK3588 在线、模型路径存在、摄像头可用。

## 开源说明

本发布包只保留项目代码、配置、文档和轻量标签文件。训练数据、缓存、日志、运行记录和模型权重已从仓库包中排除，避免仓库过大或误传敏感文件。

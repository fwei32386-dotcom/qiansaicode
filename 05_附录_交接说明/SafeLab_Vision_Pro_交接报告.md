# SafeLab Vision Pro 项目交接报告

交接日期：2026-06-14  
项目目录：`D:\ELFrk3588\SafeLab-Vision-Pro`  
板卡地址：`192.168.0.232`  
板卡项目路径：`/root/SafeLab-Vision-Pro`

## 1. 当前结论

SafeLab Vision Pro 目前已经完成了演示网页、报告页、板端 RKNN 二进制编译、板端模型推理验证、测试图片可视化结果输出等关键工作。当前最重要的成果是：RKNN 推理已经不是前端模拟，而是板卡上真实运行 `safelab_rknn_detect` 后生成检测 JSON，再由 Windows 侧脚本汇总和可视化。

当前板端 RKNN 链路状态：

- 板端 RKNN 二进制可以运行。
- FP RKNN 模型可以加载并推理。
- 测试图片检测有真实输出。
- 后处理可以产生类别、置信度、检测框。
- 已生成可视化检测效果页，可用于演示或继续集成到主网页。

## 2. 已完成工作

### 2.1 演示网页和报告页

已经完成项目展示网页的主要设计调整，包括：

- 首页和报告库进行了中文化处理。
- 报告库从工程文件列表调整为更适合评委查看的材料入口。
- 实时演示看板 `live_dashboard.html` 已经具备较完整的展示效果，包括实时画面区域、AI 说明、风险时间线、事件统计等。
- 已确认本地静态服务可通过 `http://127.0.0.1:8766/` 查看页面。

主要相关文件：

| 文件 | 作用 |
| --- | --- |
| `index.html` | 项目首页和演示入口 |
| `live_dashboard.html` | SafeLab 实时演示看板 |
| `reports/index.html` 或报告库相关页面 | 报告材料入口 |
| `tools/generate_report_index.py` | 生成/更新报告库页面 |
| `tools/localize_report_pages.py` | 报告页面中文化辅助脚本 |

### 2.2 Ubuntu 交叉编译包

已经整理出用于 Ubuntu 编译 RKNN 板端二进制的目录：

`D:\ELFrk3588\SafeLab-Vision-Pro\ubuntu_rknn_build_pack`

该目录已传入 Ubuntu 使用，并成功编译出 ARM aarch64 可执行文件。

主要相关文件：

| 文件 | 作用 |
| --- | --- |
| `ubuntu_rknn_build_pack\build_in_ubuntu.sh` | Ubuntu 侧一键编译脚本 |
| `ubuntu_rknn_build_pack\rknn_runtime\safelab_rknn_detect.cpp` | 板端 RKNN 推理主程序源码 |
| `ubuntu_rknn_build_pack\rknn_runtime\yolov8_postprocess.cpp` | YOLOv8 输出后处理 |
| `ubuntu_rknn_build_pack\rknn_runtime\yolov8_postprocess.hpp` | 后处理头文件 |
| `ubuntu_rknn_build_pack\rknn_runtime\Makefile` | 交叉编译配置 |
| `ubuntu_rknn_build_pack\deploy_debug_to_board.sh` | 编译后向板卡部署调试二进制 |
| `ubuntu_rknn_build_pack\README_BUILD.md` | Ubuntu 编译说明 |
| `ubuntu_rknn_build_pack\README_DEBUG.md` | 调试部署说明 |

Ubuntu 编译成功后的输出示例：

```bash
Build OK: /home/cedric/ubuntu_rknn_build_pack/rknn_runtime/safelab_rknn_detect
```

生成的二进制特征：

- ELF 64-bit
- ARM aarch64
- 动态链接
- 可在 RK3588 板端运行

### 2.3 板端 RKNN 二进制

板端二进制已部署到：

`/root/SafeLab-Vision-Pro/rknn_runtime/safelab_rknn_detect`

已执行过的验证命令：

```bash
cd /root/SafeLab-Vision-Pro
chmod +x rknn_runtime/safelab_rknn_detect
rknn_runtime/safelab_rknn_detect --contract
sh tools/board_rknn_runtime_check.sh
```

验证结果要点：

- `--contract` 可以输出检测 JSON。
- `board_rknn_runtime_check.sh` 运行完成。
- RKNN runtime 存在。
- `rknn_common_test` 存在。
- 模型加载和单图 probe 通过。
- 检测 JSON contract 通过。

注意：板卡上没有完整 C++ 本地编译环境，`gcc/g++/cmake` 缺失属于预期情况。当前采用 Ubuntu 交叉编译，再部署到板卡运行。

### 2.4 RKNN 模型问题定位与修复

排查过程中发现旧 INT8 RKNN 模型存在输出量化问题：

- 输出张量中坐标通道范围约为 0-640。
- 类别置信度通道范围约为 0-1。
- INT8 量化时两类数值共用输出 scale，导致类别分数通道被压缩，出现检测结果异常。

解决方案：

- 改用 FP RKNN 模型。
- 新模型输出为 FP16，类别通道可以保留有效分数。
- 板端实际检测恢复正常。

新增/相关文件：

| 文件 | 作用 |
| --- | --- |
| `rknn_transfer_package\convert_onnx_to_rknn_fp.py` | ONNX 转 FP RKNN 的转换脚本 |
| `rknn_transfer_package\README_FP_RKNN.md` | FP RKNN 转换和部署说明 |

板卡当前使用模型：

`/root/SafeLab-Vision-Pro/models/rknn/safelab_yolov8n_fire_smoke_v3_fp.rknn`

注意：Windows 项目目录 `models\rknn` 当前没有实际 `.rknn` 模型文件，真实可用模型在 Ubuntu/板卡侧完成并部署。后续建议把最终 FP RKNN 模型也备份回 Windows 项目目录，避免交接遗漏。

### 2.5 RKNN 推理程序增强

`safelab_rknn_detect.cpp` 已增强为更适合调试和验收的版本。

已加入能力：

- `--contract`：输出固定 JSON contract，用于接口验证。
- `--input-type`：指定输入类型。
- `--pass-through`：用于输入数据调试。
- `--conf-threshold`：设置检测置信度阈值。
- `--dump-output-stats`：输出 RKNN 输入/输出张量统计，便于定位模型输出异常。
- 默认使用 uint8 输入路径，适配当前 FP RKNN 模型。

主要相关文件：

| 文件 | 作用 |
| --- | --- |
| `rknn_runtime\safelab_rknn_detect.cpp` | Windows 项目内 RKNN 推理源码 |
| `ubuntu_rknn_build_pack\rknn_runtime\safelab_rknn_detect.cpp` | Ubuntu 编译包内同步源码 |
| `rknn_runtime\yolov8_postprocess.cpp` | YOLOv8 后处理实现 |
| `tests\test_yolov8_postprocess.py` | 后处理单元测试 |

### 2.6 板端测试图片批量验证

新增 Windows 侧脚本，用来把测试图片转成 640x640 RGB 输入，上传到板卡，调用板端 RKNN 二进制，再拉回 JSON 结果。

主要文件：

`tools\run_board_rknn_image_samples.py`

默认行为：

- 使用 FP RKNN 模型。
- 使用 `rgb_u8` 输入。
- 运行 6 张样例图。
- 汇总输出到 `reports\rknn_image_samples\summary.json`。

最近一次验证结果：

- 样例数：6
- 失败数：0
- 全部有检测输出
- 总检测框数：25

检测结果包括：

| 样例 | 检测结果摘要 |
| --- | --- |
| PPE frame1087 | goggles，置信度约 0.676 |
| PPE frame1088 | goggles，置信度约 0.683 |
| hardhat_000010 | 多个 helmet / vest |
| hardhat_000021 | 多个 helmet / vest |
| D-Fire AoF07718 | fire / smoke |
| D-Fire AoF07719 | fire / smoke |

测试输出目录：

`reports\rknn_image_samples`

关键输出文件：

| 文件 | 作用 |
| --- | --- |
| `reports\rknn_image_samples\summary.json` | 批量检测汇总结果 |
| `reports\rknn_image_samples\sample_*.jsonl` | 单图检测 JSON 输出 |
| `reports\rknn_image_samples\sample_*_rgb_u8.rgb` | 上传给板卡的 RGB 输入 |

### 2.7 检测效果可视化页面

已新增可视化生成脚本：

`tools\generate_rknn_image_preview.py`

作用：

- 读取 `summary.json`。
- 在原始测试图上绘制检测框、类别和置信度。
- 生成 HTML 效果页，方便演示和交接。

输出页面：

`reports\rknn_image_samples\rknn_image_samples_preview.html`

本地访问方式：

```powershell
cd D:\ELFrk3588\SafeLab-Vision-Pro
python -m http.server 8766 --bind 127.0.0.1
```

浏览器打开：

`http://127.0.0.1:8766/reports/rknn_image_samples/rknn_image_samples_preview.html`

输出图片：

| 文件 | 作用 |
| --- | --- |
| `preview_01_ppe_dataset_yolov8_frame1087_*.jpg` | PPE 样例 1 可视化 |
| `preview_02_ppe_dataset_yolov8_frame1088_*.jpg` | PPE 样例 2 可视化 |
| `preview_03_hardhat_vest_v3_000010.jpg` | 安全帽/反光衣样例 1 |
| `preview_04_hardhat_vest_v3_000021.jpg` | 安全帽/反光衣样例 2 |
| `preview_05_dfire_kaggle_AoF07718.jpg` | 火焰/烟雾样例 1 |
| `preview_06_dfire_kaggle_AoF07719.jpg` | 火焰/烟雾样例 2 |

### 2.8 自动化测试

已运行并通过：

```powershell
cd D:\ELFrk3588\SafeLab-Vision-Pro
python -m unittest tests.test_board_rknn_image_samples tests.test_yolov8_postprocess
```

结果：

```text
Ran 6 tests in 0.001s
OK
```

相关测试文件：

| 文件 | 作用 |
| --- | --- |
| `tests\test_board_rknn_image_samples.py` | 批量板端样例脚本测试 |
| `tests\test_yolov8_postprocess.py` | YOLOv8 后处理测试 |
| `tests\test_board_rknn_runtime_check.py` | 板端 RKNN runtime 检查脚本测试 |

## 3. 重要命令汇总

### 3.1 Windows 本地启动网页

```powershell
cd D:\ELFrk3588\SafeLab-Vision-Pro
python -m http.server 8766 --bind 127.0.0.1
```

首页：

`http://127.0.0.1:8766/index.html`

实时看板：

`http://127.0.0.1:8766/live_dashboard.html`

RKNN 实测效果页：

`http://127.0.0.1:8766/reports/rknn_image_samples/rknn_image_samples_preview.html`

### 3.2 Ubuntu 编译 RKNN 二进制

```bash
cd ~/ubuntu_rknn_build_pack
sh build_in_ubuntu.sh
```

编译产物：

`~/ubuntu_rknn_build_pack/rknn_runtime/safelab_rknn_detect`

### 3.3 部署二进制到板卡

如果 Ubuntu 能连通板卡：

```bash
cd ~/ubuntu_rknn_build_pack
scp rknn_runtime/safelab_rknn_detect root@192.168.0.232:/root/SafeLab-Vision-Pro/rknn_runtime/safelab_rknn_detect
```

如果 Ubuntu 不能连通板卡，可以手动把文件复制到板卡对应路径。

### 3.4 板卡 RKNN runtime 验证

```bash
ssh root@192.168.0.232 '
  cd /root/SafeLab-Vision-Pro &&
  chmod +x rknn_runtime/safelab_rknn_detect &&
  rknn_runtime/safelab_rknn_detect --contract &&
  sh tools/board_rknn_runtime_check.sh
'
```

### 3.5 Windows 侧跑板端图片样例

```powershell
cd D:\ELFrk3588\SafeLab-Vision-Pro
python tools\run_board_rknn_image_samples.py
python tools\generate_rknn_image_preview.py
```

## 4. 当前关键文件清单

### 4.1 RKNN 和板端相关

| 路径 | 说明 |
| --- | --- |
| `rknn_runtime\safelab_rknn_detect.cpp` | RKNN 推理主程序 |
| `rknn_runtime\yolov8_postprocess.cpp` | YOLOv8 后处理 |
| `rknn_runtime\yolov8_postprocess.hpp` | YOLOv8 后处理接口 |
| `tools\board_rknn_runtime_check.sh` | 板端 RKNN runtime 检查 |
| `tools\run_board_rknn_image_samples.py` | Windows 调用板卡批量跑图 |
| `tools\generate_rknn_image_preview.py` | 检测结果可视化 |
| `rknn_transfer_package\convert_onnx_to_rknn_fp.py` | FP RKNN 转换脚本 |
| `rknn_transfer_package\README_FP_RKNN.md` | FP RKNN 说明 |

### 4.2 Ubuntu 交叉编译包

| 路径 | 说明 |
| --- | --- |
| `ubuntu_rknn_build_pack\build_in_ubuntu.sh` | Ubuntu 一键编译 |
| `ubuntu_rknn_build_pack\deploy_debug_to_board.sh` | 部署调试二进制 |
| `ubuntu_rknn_build_pack\rknn_runtime\*` | 编译所需 RKNN runtime 源码 |
| `ubuntu_rknn_build_pack\rknn_sdk_2.3.2` | RKNN SDK |
| `ubuntu_rknn_build_pack\toolchain` | 交叉编译工具链 |

### 4.3 报告和演示输出

| 路径 | 说明 |
| --- | --- |
| `reports\rknn_image_samples\summary.json` | 板端图片检测汇总 |
| `reports\rknn_image_samples\rknn_image_samples_preview.html` | 真实检测效果页 |
| `reports\rknn_image_samples\preview_*.jpg` | 绘制检测框后的图片 |
| `live_dashboard.html` | 实时演示看板 |
| `index.html` | 项目入口页 |

### 4.4 测试

| 路径 | 说明 |
| --- | --- |
| `tests\test_board_rknn_image_samples.py` | 批量跑图脚本测试 |
| `tests\test_yolov8_postprocess.py` | 后处理测试 |
| `tests\test_board_rknn_runtime_check.py` | 板端 runtime 检查测试 |

## 5. 还没做 / 后续建议

### 5.1 把 FP RKNN 模型回收进 Windows 项目目录

当前 Windows 项目目录：

`models\rknn`

里面没有最终使用的 `.rknn` 模型文件。建议从板卡或 Ubuntu 把以下模型复制回 Windows：

`safelab_yolov8n_fire_smoke_v3_fp.rknn`

建议目标路径：

`D:\ELFrk3588\SafeLab-Vision-Pro\models\rknn\safelab_yolov8n_fire_smoke_v3_fp.rknn`

这样后续交接和归档更完整。

### 5.2 将真实检测效果集成到首页

目前真实检测效果页是独立页面：

`reports\rknn_image_samples\rknn_image_samples_preview.html`

建议下一步把它接入首页或报告库，例如新增入口：

- “板端 RKNN 实测效果”
- “真实模型检测结果”
- “评委演示结果”

这样评委不需要知道内部路径。

### 5.3 摄像头实时流与 RKNN 推理还没有完全闭环

当前已经验证：

- 图片输入到 RKNN 推理可行。
- Web 演示页可展示实时看板。

还需要继续确认：

- 摄像头实时帧是否能稳定进入 RKNN 推理程序。
- RKNN 推理输出是否能实时进入事件总线/看板。
- 实时画面中的检测框是否来自当前帧的真实推理结果。

### 5.4 板卡服务化启动还需整理

当前更多是命令行验证。后续建议整理成板卡一键启动脚本或 systemd 服务：

- 启动摄像头采集。
- 启动 RKNN 推理。
- 启动事件/告警链路。
- 启动 Web 数据同步。

### 5.5 模型精度还需要更大样本验证

目前 6 张图片样例已经证明链路跑通，但不代表最终模型精度充分。建议后续补充：

- 更多火焰/烟雾样本。
- 更多 PPE 样本。
- 暗光、强光、遮挡、远距离场景。
- 误检和漏检统计。
- 最终评委演示固定样例包。

### 5.6 Git/版本归档需要补齐

当前 `D:\ELFrk3588\SafeLab-Vision-Pro` 不是 git 仓库，无法通过 commit 记录追踪变更。建议交接前至少做一次文件夹压缩归档，或初始化 git 仓库保存当前状态。

建议归档内容：

- `SafeLab-Vision-Pro`
- `ubuntu_rknn_build_pack`
- 板端最终二进制
- FP RKNN 模型
- `reports\rknn_image_samples`
- 本交接报告

## 6. 下一位接手人的推荐顺序

1. 先打开 `reports\rknn_image_samples\rknn_image_samples_preview.html`，确认真实检测效果。
2. 再 SSH 到板卡，运行 `safelab_rknn_detect --contract` 和 `board_rknn_runtime_check.sh`，确认板端状态。
3. 把 FP RKNN 模型从板卡/Ubuntu 回收进 Windows 项目目录。
4. 把真实检测效果页接入首页和报告库。
5. 做摄像头实时流到 RKNN 推理的闭环。
6. 最后整理一键启动和评委演示流程。

## 7. 当前状态一句话总结

项目已经从“网页展示和工程框架”推进到了“板卡真实 RKNN 模型能跑、能出检测结果、能生成可视化效果”的阶段。剩下最关键的工作是把这个真实 RKNN 推理链路接入实时摄像头和主演示网页，形成完整的现场演示闭环。

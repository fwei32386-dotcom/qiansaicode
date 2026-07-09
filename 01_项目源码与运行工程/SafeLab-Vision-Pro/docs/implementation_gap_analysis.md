# SafeLab-Vision Pro Implementation Gap Analysis

Source document:

```text
D:\ELFrk3588\SafeLab-Vision_Pro_最强版三人分工统一接口与实现指导(1).docx
```

Extracted text snapshot:

```text
docs/implementation_gap_analysis_source.txt
```

Scope note: GPIO LED, buzzer, and relay physical control are intentionally paused. GPIO contract files may remain as placeholders, but GPIO hardware bring-up is not part of the current work.

## Requirement Status Table

| Area | Word-plan requirement | Current evidence | Status | Next action |
| --- | --- | --- | --- | --- |
| Unified interfaces | Freeze `VideoFrame`, `Detection`, `RiskEvent`, `AlarmAction`, `TimelineEvent`, `HealthStatus`. | `docs/interface_spec.md`, `runtime/interfaces.py`, `tests/test_interface_contract.py`. | Done | Keep updating interface spec before field changes. |
| Mock closed loop | Use mock data to connect Detection -> RiskEvent -> AlarmAction -> logs before hardware is ready. | `main.py`, `tools/run_smoke_test.py`, `tools/board_smoke_test.sh`, `tests/test_json_pipeline.py`. | Done | Keep mock path as fallback for demos. |
| Rule DSL | Configurable YAML/JSON rules for lab zones, PPE, smoke/fire, risk score, and actions. | `configs/rule_dsl.json`, `safety_brain/rule_dsl_engine.py`, `tests/test_rule_dsl_engine.py`. | Done | Add new site rules only through config and tests. |
| PPE and semantic map | Person/PPE association, danger zones, goggles/gloves support. | `safety_brain/ppe_association.py`, `safety_brain/scene_graph.py`, `configs/semantic_map.json`. | Mostly done | Verify with full test suite once pytest is available. |
| Smoke/fire temporal logic | Single-frame smoke/fire must not alarm; consecutive frames confirm. | `safety_brain/smoke_fire_temporal.py`, `tools/replay_detection_file.py`, `tests/test_replay_runner.py`. | Done | Keep replay scenarios for regressions. |
| Event state machine | Avoid repeated main alarms, snapshots, and logs for same event. | `safety_brain/event_state_machine.py`, `runtime/replay_runner.py`, `tests/test_event_timeline.py`. | Done | Verify cooldown behavior in full tests. |
| Latest-only runtime | Latest frame buffer, maxsize=1 queue behavior, no old-frame buildup. | `runtime/latest_frame_buffer.py`, `runtime/async_event_bus.py`, `tests/test_latest_frame_buffer_benchmark.py`, `tests/test_async_event_bus.py`. | Done | Run benchmark scripts after dependency setup. |
| Adaptive scheduling and ROI | Frame scheduler and ROI manager with benchmark evidence. | `runtime/frame_scheduler.py`, `ai_engine/roi_manager.py`, `tools/benchmark_frame_scheduler.py`, `tools/benchmark_roi_manager.py`. | Done | Regenerate reports before demo. |
| Detection JSON replay | RKNN/native detector JSONL can enter Python rule pipeline. | `tools/replay_detection_jsonl.py`, `tests/test_rknn_detection_jsonl_replay.py`. | Done | Re-run after real `safelab_rknn_detect` binary exists. |
| Dashboard | Local/browser dashboard can show events, actions, reports. | `dashboard/live_dashboard.py`, `dashboard/live_server.py`, `tools/serve_live_dashboard.py`, dashboard tests. | Done | Use generated reports for demo entry. |
| Evidence chain | Events, actions, raw/marked snapshots, timelines, risk curve, reports, SQLite alarm database. | `evidence/`, `data/events/`, `reports/`, `tools/generate_report_index.py`. | Done | Refresh reports after full test/evaluation run. |
| SQLite logging | Word plan asks for SQLite `alarm_log.db`. | `evidence/event_logger.py`, `tests/test_event_logger_sqlite.py`, `docs/interface_spec.md`. | Done | Keep JSONL and SQLite payloads consistent. |
| Cloud/AI explanation | Optional cloud explanation path for event explanation. | `cloud/deepseek_client.py`, `tools/generate_ai_explanations.py`, `tests/test_ai_interaction.py`. | Done for host/cloud fallback | Keep DeepSeek in cloud or host-side service; the RK3588 board should consume JSONL explanation results instead of running a large LLM locally. |
| AI explanation -> speech output bridge | Convert the latest DeepSeek/fallback `voice_text` into a speech output record. | `interaction/ai_speech_bridge.py`, `tools/speak_latest_ai_explanation.py`, `data/events/speech_output.jsonl`. | Done | Use dry-run logging by default; add real `espeak`/audio execution only when the board audio stack is ready. |
| Real microphone or voice module ASR input | Convert board microphone audio or voice-module output into recognized command text for `tools/voice_deepseek_session.py`. | `docs/voice_module_asr_handoff.md`; board probe found working `rockchip-nau8822` MIC capture, `/dev/ttyS9`, no `/dev/ttyUSB0` or `/dev/ttyACM0`, and no board-side Python/ASR tool. | Paused | Do not implement yet. Resume with either host-side ASR bridge or UART listener after owner approval. |
| Board RKNN runtime check | One command checks `rknn_api.h`, `/usr/lib/librknnrt.so`, model, labels, test images, `rknn_common_test`, Detection JSON contract, and report output. | `tools/board_rknn_runtime_check.sh`, `tests/test_board_rknn_runtime_check.py`, `reports/board_rknn_runtime_check.json`. | Done | Keep re-running after RKNN binary changes. |
| RKNN C++ binary | Compile `safelab_rknn_detect` and emit Detection JSON. | Source exists in `rknn_runtime/`; board report shows `build_state=cross_compile_required`. | Cross-compile blocked | Run Ubuntu cross-build using Buildroot SDK. |
| Board compiler | Board-side `g++` or installable compiler. | Board is Buildroot 2021.11 with no `gcc/g++/apt/opkg`. | Blocked | Use Ubuntu host cross-compiler. |
| GPIO hardware actions | LED, buzzer, relay physical control. | `actuator/` and GPIO contract scripts exist. | Not doing | Keep mock/shell backends only for this stage. |
| Board one-key mode | One command self-check, run, reset, export demo evidence. | `demo/board_competition_mode.sh`, `tools/board_ops.sh`, README commands. | Done | Re-run on board after RKNN JSON report update. |
| Final acceptance report | Summarize completion, blockers, demo outputs. | `tools/generate_final_acceptance_report.py`. | Done | Update generator if SQLite/GPIO scope changes. |

## Immediate Non-GPIO Work Queue

1. Refresh local reports: run smoke, replay, batch evaluation, ablation, latency, AI explanation, dashboard/report-index generators before the final demo.
2. Prepare Ubuntu cross-compile execution using `docs/rknn_cross_compile_ubuntu.md`.
3. After Ubuntu cross-compile, upload `safelab_rknn_detect` and re-run `sh tools/board_rknn_runtime_check.sh`.
4. On the board, keep DeepSeek optional and remote: run `tools/generate_ai_explanations.py` on Windows/host or a cloud service, sync `data/events/ai_explanations.jsonl`, then run `python tools/speak_latest_ai_explanation.py` where Python/audio is available.

## Current State Summary

| Status | Items |
| --- | --- |
| Completed | Interfaces, mock Detection -> RiskEvent -> AlarmAction loop, DSL rules, PPE association, semantic map, smoke/fire temporal confirmation, event state machine, latest-only runtime, async event bus, ROI scheduling, JSONL/SQLite evidence, dashboards, replay/evaluation reports, board shell checks, RKNN runtime readiness check, DeepSeek fallback explanations, AI-to-speech log bridge. |
| Missing | Real end-to-end camera/RKNN inference into `safelab_rknn_detect`, real audio playback validation on board, freshly regenerated final reports after the latest AI bridge change. |
| Not doing GPIO | Physical LED, buzzer, and relay bring-up. Mock/shell/GPIO-intent records remain, but no live pin driving is in scope. |
| Cross-compile blocked | `safelab_rknn_detect` with RKNN SDK linkage still needs Ubuntu/WSL Ubuntu cross-compilation using the Buildroot SDK. |
| Immediately fillable | Run local report refresh commands, generate DeepSeek fallback explanations, record latest AI voice text, regenerate live dashboard and report index. |

## Ubuntu Cross-Compile Checklist

This remains blocked on a Linux host environment, not on board runtime files.

```sh
mkdir -p ~/toolchains
tar -xzf /mnt/d/ELFrk3588/06-常用工具/01-编译工具安装脚本/aarch64-buildroot-linux-gnu_sdk-buildroot.tar.gz -C ~/toolchains
cd ~/toolchains/aarch64-buildroot-linux-gnu_sdk-buildroot
if [ -f ./relocate-sdk.sh ]; then ./relocate-sdk.sh; fi
export PATH="$PWD/bin:$PATH"
aarch64-buildroot-linux-gnu-g++ --version

cd /mnt/d/ELFrk3588/SafeLab-Vision-Pro/rknn_runtime
make clean
make WITH_RKNN=1 \
  CXX=aarch64-buildroot-linux-gnu-g++ \
  RKNN_INCLUDE_DIR=/mnt/d/ELFrk3588/rknn_sdk_2.3.2/include \
  RKNN_LIB_DIR=/mnt/d/ELFrk3588/rknn_sdk_2.3.2/lib/aarch64
```

Board upload and verification:

```sh
scp safelab_rknn_detect root@192.168.0.232:/root/SafeLab-Vision-Pro/rknn_runtime/
ssh root@192.168.0.232 'cd /root/SafeLab-Vision-Pro && sh tools/board_rknn_runtime_check.sh'
```

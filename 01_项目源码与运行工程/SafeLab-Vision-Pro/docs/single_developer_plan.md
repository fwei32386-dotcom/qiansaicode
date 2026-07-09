# SafeLab-Vision Pro Single Developer Plan

This project is implemented by one developer. The original three-role document
remains the binding project contract. Its role split is kept as module
boundaries and execution order, not as separate people.

## Working Rule

Follow this order:

1. Keep interfaces stable.
2. Keep board-side shell fallback working.
3. Build one runnable path before adding stronger features.
4. Do not block on missing camera, Python, model, or GPIO hardware.
5. When a field, module, report, or acceptance item appears in the original
   implementation guide, preserve it unless the project owner explicitly removes
   it.

## Current Single-Developer Priority

This priority list maps to the original document stages:

- Stage 0: interface freeze and mock data.
- Stage 1: unified video input.
- Stage 3-5: risk cognition, alarm lifecycle, evidence chain.
- Stage 7: device self-check and competition mode.

Stage 2 NPU/model work is intentionally deferred only because the current task
scope says not to consider YOLO yet.

1. Board fallback path
   - health check
   - health status JSON
   - camera probe
   - board smoke test
   - competition mode export

2. Unified video input
   - `VideoFrame`
   - camera/file/mock sources
   - latest-only frame buffer

3. Risk cognition
   - PPE association
   - semantic map
   - rule DSL
   - smoke/fire temporal confirmation
   - event state machine

4. Evidence and demo
   - event logs
   - alarm actions
   - dashboards
   - replay reports
   - board demo export

5. Hardware integration later
   - connect OV13855 or another camera
   - verify V4L2/media graph
   - add real capture backend
   - add real actuator backend

## Board Commands

```sh
cd /root/SafeLab-Vision-Pro
sh tools/board_health_check.sh
sh tools/board_health_status.sh
sh tools/board_camera_check.sh
sh tools/board_smoke_test.sh
sh demo/board_competition_mode.sh run
```

## Windows Commands

```powershell
python tools\validate_config.py
python tools\run_batch_evaluation.py
python tools\run_video_runtime_smoke.py
powershell -ExecutionPolicy Bypass -File tools\sync_to_board.ps1 -RemoteRoot /root
```

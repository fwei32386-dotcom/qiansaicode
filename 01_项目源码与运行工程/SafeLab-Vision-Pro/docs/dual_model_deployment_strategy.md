# Dual-Model Deployment Strategy

## Decision

Use the conservative deployment plan confirmed on 2026-07-01:

- PPE/person model: lightweight YOLO route, preferably YOLOv8n first, or a small YOLOv8s only if PPE recall remains weak.
- Fire/smoke model: YOLOv8s specialist.
- Scene rules decide which PPE items are required.
- The RK3588 board model must not be replaced until a candidate passes offline acceptance, ONNX export, RKNN conversion, board runtime check, and FPS evidence.

## Why Two Models

PPE and fire/smoke are different visual tasks:

- PPE detection is person-centric: person, helmet, vest, goggles, gloves, and later mask or protective suit.
- Fire/smoke detection is scene-centric: fire and smoke can appear without a person and have unstable shapes.

Splitting them prevents fire/smoke tuning from degrading PPE detections, and prevents PPE tuning from weakening fire/smoke recall.

## Scene Rule Mapping

Construction mode:

- Required PPE: helmet, vest.
- Optional extensions: gloves, goggles.
- Fire/smoke model remains active for environmental risk.

Lab mode:

- Required PPE: gloves, goggles, mask, protective suit when those classes are available.
- Current stable classes support gloves and goggles.
- Fire/smoke model remains active for environmental risk.

## Runtime Scheduling

Default RK3588 scheduling target:

- Run the PPE model when a person is present or at a lower periodic rate.
- Run the fire/smoke model globally at a low periodic rate.
- Raise the processing rate after suspicious detections.
- Use ROI inference where the existing scheduler and ROI manager can reduce repeated full-frame work.

## Promotion Gate

A candidate can be promoted only when all applicable checks pass:

1. Offline fixed probe acceptance.
2. Per-class threshold scan.
3. ONNX export.
4. RKNN conversion.
5. RK3588 runtime probe.
6. Detection JSON contract validation.
7. FPS evidence with rollback path.

## Current Status

- The deployed board path remains the current single RKNN model:
  `/root/SafeLab-Vision-Pro/models/rknn/safelab_yolov8n_fire_smoke_v3.rknn`
- The current board model should remain untouched until a new candidate passes the full promotion gate.
- A fire/smoke YOLOv8s specialist is currently being trained as the second-model candidate:
  `D:\ELFrk3588\yolo_training_runs\safelab_fire_smoke_yolov8s_640_15e`

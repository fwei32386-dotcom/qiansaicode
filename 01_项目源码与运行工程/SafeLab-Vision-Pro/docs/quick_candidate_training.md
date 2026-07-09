# Quick Candidate Training

## Environment Finding

This Windows training environment has a usable GPU:

- GPU: NVIDIA GeForce RTX 4060 Laptop GPU
- Torch: CUDA available

Important: Ultralytics training stalled when using dataloader workers greater than zero. Use `workers=0` on this machine.

## Quick Subsets

Generated quick subsets:

- `D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_ppe_quick_vest_gloves`
- `D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_fire_smoke_quick`
- `D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_fire_smoke_tinycheck`

Tiny smoke-check subset:

- train images: 80
- val images: 20
- test images: 20

## Smoke-Test Result

The following command completed successfully:

```powershell
Set-Location -LiteralPath 'D:\ELFrk3588\SafeLab-Vision-Pro\资料'
.\.venv-yolo\Scripts\python.exe tools\train_yolo_candidate.py --data D:/ELFrk3588/SafeLab-Vision-Pro/datasets/safelab_fire_smoke_tinycheck/data.yaml --name fire_smoke_tinycheck_yolov8n_1e --epochs 1 --imgsz 320 --batch 8 --workers 0
```

Output model:

`D:\ELFrk3588\yolo_training_runs\fire_smoke_tinycheck_yolov8n_1e\weights\best.pt`

This 1-epoch run is only an environment check, not a quality candidate.

Probe result:

- `reports/yolo_probe_current/fire_smoke_tinycheck_1e_iou_metrics.csv`
- The probe confirms class-name mapping works for the 2-class fire/smoke dataset.
- The 1-epoch tiny model produced no valid detections at confidence 0.25, which is expected for a smoke test and should not be used as a deployment candidate.

## Next Candidate Commands

Fire/smoke quick candidate:

```powershell
Set-Location -LiteralPath 'D:\ELFrk3588\SafeLab-Vision-Pro\资料'
.\.venv-yolo\Scripts\python.exe tools\train_yolo_candidate.py --data D:/ELFrk3588/SafeLab-Vision-Pro/datasets/safelab_fire_smoke_quick/data.yaml --name fire_smoke_quick_yolov8n_5e --epochs 5 --imgsz 416 --batch 16 --workers 0
```

PPE quick candidate:

```powershell
Set-Location -LiteralPath 'D:\ELFrk3588\SafeLab-Vision-Pro\资料'
.\.venv-yolo\Scripts\python.exe tools\train_yolo_candidate.py --data D:/ELFrk3588/SafeLab-Vision-Pro/datasets/safelab_ppe_quick_vest_gloves/data.yaml --name ppe_quick_vest_gloves_yolov8n_5e --epochs 5 --imgsz 416 --batch 16 --workers 0
```

After each candidate, run `tools/run_yolo_probe.py` on the relevant dataset and compare against current baseline reports.

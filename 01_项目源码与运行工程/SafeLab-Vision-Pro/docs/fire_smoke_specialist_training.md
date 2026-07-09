# Fire/Smoke Specialist Training

## Dataset

Generated dataset:

`D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_fire_smoke`

Summary:

- train images: 32015
- val images: 5539
- test images: 4073
- fire boxes: 41747
- smoke boxes: 27105

The labels are remapped from the 7-class SafeLab dataset:

- original class `5 fire` -> specialist class `0 fire`
- original class `6 smoke` -> specialist class `1 smoke`

## Recommended First Training Candidate

Use the current 7-class model as the starting point only if class head transfer is acceptable in Ultralytics. Otherwise start from `yolov8n.pt`.

Conservative first run:

```powershell
cd D:\ELFrk3588\SafeLab-Vision-Pro\资料
.\.venv-yolo\Scripts\python.exe -c "from ultralytics import YOLO; m=YOLO('yolov8n.pt'); m.train(data='D:/ELFrk3588/SafeLab-Vision-Pro/datasets/safelab_fire_smoke/data.yaml', epochs=20, imgsz=640, batch=16, device=0, project='runs/detect/models/checkpoints', name='safelab_fire_smoke_yolov8n_20e')"
```

## Acceptance Check

After training, run:

```powershell
cd D:\ELFrk3588\SafeLab-Vision-Pro\资料
.\.venv-yolo\Scripts\python.exe tools\run_yolo_probe.py --dataset D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_fire_smoke --model runs\detect\models\checkpoints\safelab_fire_smoke_yolov8n_20e\weights\best.pt --output-dir D:\ELFrk3588\fire_smoke_probe_ascii --per-class 20 --conf 0.25 --conf 0.15
```

Then compare fire/smoke precision and recall against:

`reports/yolo_probe_current/summary/conf250/iou_metrics.csv`

## Notes

This specialist model is a candidate, not yet a deployment decision. If it improves fire/smoke but is too slow on RK3588, run it at lower frequency or only in fire-risk zones.

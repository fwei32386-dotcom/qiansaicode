# PPE Specialist Training

## Dataset

Existing dataset:

`D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_ppe`

Summary:

- train images: 38356
- val images: 8207
- test images: 4392
- person boxes: 25123
- helmet boxes: 107691
- vest boxes: 10324
- goggles boxes: 4208
- gloves boxes: 7477

The PPE dataset keeps five classes:

- `0 person`
- `1 helmet`
- `2 vest`
- `3 goggles`
- `4 gloves`

## Current Risk

The PPE dataset is heavily imbalanced. Helmet boxes dominate the dataset, while goggles, gloves, and vest are much less common. This matches the current probe result where gloves and vest recall are weaker than helmet.

## Recommended First Training Candidate

Train a PPE-only model before changing the 7-class model:

```powershell
cd D:\ELFrk3588\SafeLab-Vision-Pro\资料
.\.venv-yolo\Scripts\python.exe -c "from ultralytics import YOLO; m=YOLO('yolov8n.pt'); m.train(data='D:/ELFrk3588/SafeLab-Vision-Pro/datasets/safelab_ppe/data.yaml', epochs=20, imgsz=640, batch=16, device=0, project='runs/detect/models/checkpoints', name='safelab_ppe_yolov8n_balanced_20e')"
```

## Data Improvement Direction

Before training larger models, improve the weak PPE classes:

1. Review `reports/yolo_probe_current/cleaning_plan_conf250.html`.
2. Fix missing or loose vest/gloves labels.
3. Add hard negative examples for gloves and vest.
4. Add more small/occluded gloves examples.
5. Avoid simply lowering confidence threshold; it increases false positives.

## Acceptance Check

After training, run:

```powershell
cd D:\ELFrk3588\SafeLab-Vision-Pro\资料
.\.venv-yolo\Scripts\python.exe tools\run_yolo_probe.py --dataset D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_ppe --model runs\detect\models\checkpoints\safelab_ppe_yolov8n_balanced_20e\weights\best.pt --output-dir D:\ELFrk3588\ppe_probe_ascii --per-class 20 --conf 0.25 --conf 0.15
```

Compare PPE precision/recall against:

`reports/yolo_probe_current/summary/conf250/iou_metrics.csv`

## Deployment Note

If the PPE specialist beats the 7-class model but is too expensive to run every frame on RK3588, use it as an ROI model on person regions or run it every 2-3 frames.

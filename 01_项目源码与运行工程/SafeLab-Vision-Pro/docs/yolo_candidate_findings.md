# YOLO Candidate Findings

## Current Answer

The model is not limited to one object per image. YOLO can detect multiple boxes in one image. The current issue is class quality: some classes have weak recall or too many false positives.

## Baseline Snapshot

Baseline probe: `reports/yolo_probe_current/summary/conf250/iou_metrics.csv`

| class | precision | recall | note |
| --- | ---: | ---: | --- |
| person | 0.83 | 0.92 | usable |
| helmet | 0.80 | 0.96 | usable |
| vest | 0.94 | 0.68 | recall weak |
| goggles | 0.83 | 1.00 | sample is small |
| gloves | 0.84 | 0.64 | recall weak |
| fire | 0.52 | 0.65 | precision and recall both weak |
| smoke | 0.80 | 0.53 | recall weak |

## Quick Candidate Tests

All candidates used YOLOv8n, `imgsz=416`, `workers=0`, and 5 epochs. These are quick direction tests, not final training runs.

Fire/smoke specialist:

- Train output: `D:\ELFrk3588\yolo_training_runs\fire_smoke_quick_yolov8n_5e\weights\best.pt`
- Ultralytics val at epoch 5: P 0.488, R 0.352, mAP50 0.360
- Probe at conf 0.25:
  - fire: P 0.446, R 0.322
  - smoke: P 0.409, R 0.340
- Finding: this short specialist run is worse than the current main model. It proves the training path works, but it is not a deployment candidate.

PPE vest/gloves specialist:

- Train output: `D:\ELFrk3588\yolo_training_runs\ppe_quick_vest_gloves_yolov8n_5e\weights\best.pt`
- Ultralytics val at epoch 5: P 0.701, R 0.672, mAP50 0.681
- Same-subset probe at conf 0.25 compared with the current main model:

| class | baseline P | baseline R | candidate P | candidate R | finding |
| --- | ---: | ---: | ---: | ---: | --- |
| vest | 0.768 | 0.558 | 0.568 | 0.675 | recall improves, false positives rise |
| gloves | 0.800 | 0.543 | 0.735 | 0.357 | worse recall |

Finding: this candidate is not better overall. It suggests vest can be improved by targeted data, but the current quick training harms precision and gloves recall.

## Recommendation

Do not replace the current main model with either quick candidate.

Recommended next path:

1. Keep the current 7-class model as the deployment baseline.
2. Clean and rebalance the weak classes first: fire/smoke boundaries, vest, gloves, and small PPE boxes.
3. Train longer on cleaned data, then compare on the same probe set before exporting ONNX/RKNN.
4. Consider two YOLO models only after a specialist model beats the main model on its target classes. A second model adds RK3588 inference cost and more threshold/NMS tuning, so it should earn its place with metrics.
5. For hard-hat GitHub data, add it as extra training data only after checking license and label mapping. It should improve helmet variety, but it will not directly fix vest/gloves/fire/smoke.

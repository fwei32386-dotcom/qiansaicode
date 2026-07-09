# Model Candidate Comparison

## Candidates

Use the same probe tooling to compare these candidates:

1. Current 7-class baseline:
   - `runs/detect/models/checkpoints/safelab_yolov8n_full_fire_smoke_v3/weights/best.pt`
2. PPE specialist:
   - train from `datasets/safelab_ppe/data.yaml`
3. Fire/smoke specialist:
   - train from `datasets/safelab_fire_smoke/data.yaml`

## Decision Gates

Do not accept a new model only because one class improves. Compare per-class precision and recall.

Suggested minimum gates for the next iteration:

| Area | Metric target |
| --- | --- |
| PPE person/helmet/goggles | preserve precision and recall near current baseline |
| PPE vest | improve recall over current sampled `0.68` |
| PPE gloves | improve recall over current sampled `0.64` |
| fire | improve precision over current sampled `0.52` and recall over `0.65` |
| smoke | improve recall over current sampled `0.53` |

## RK3588 Runtime Choice

If both specialist models improve their domains:

- run a single improved 7-class model if accuracy is acceptable and latency is best;
- otherwise run two specialists at lower frequency or with ROI scheduling;
- for PPE, prefer person ROI or every 2-3 frames;
- for fire/smoke, prefer scene-wide lower-frequency inference plus temporal confirmation.

## Required Reports

Each candidate should produce:

- `iou_metrics.csv`
- `iou_report.html`
- `review_priority_conf250.csv`
- training `results.csv`
- model export path for ONNX/RKNN conversion

This keeps model selection based on evidence rather than visual impressions.

# YOLO Model Improvement Plan

## Goal

Improve the current `safelab_yolov8n_full_fire_smoke_v3` model without blindly changing class weights or weakening confidence thresholds.

## Evidence

The current probe report is under `reports/yolo_probe_current`.

At `conf=0.25`, the sampled IoU@0.5 result shows:

| Class | Precision | Recall | Main issue |
| --- | ---: | ---: | --- |
| vest | 0.94 | 0.68 | missed PPE |
| gloves | 0.84 | 0.64 | missed small PPE |
| fire | 0.52 | 0.65 | fire/smoke confusion and false positives |
| smoke | 0.80 | 0.53 | missed smoke |

Lowering confidence to `0.15` does not solve the issue. It mainly increases false positives.

## Review Artifacts

- `reports/yolo_probe_current/review_page.html`: visual review page.
- `reports/yolo_probe_current/review_priority_conf250.csv`: prioritized problem samples.
- `reports/yolo_probe_current/cleaning_plan_conf250.csv`: conservative cleaning plan.
- `reports/yolo_probe_current/cleaning_plan_conf250.html`: visual cleaning plan.

## Recommended Workflow

1. Open `review_page.html` and inspect the 22 priority samples.
2. Fill the `decision` column in `cleaning_plan_conf250.csv` with one of:
   - `keep`
   - `relabel`
   - `remove`
   - `add_negative`
3. For fire/smoke boundary cases:
   - relabel fire-only samples that are actually smoke;
   - split mixed fire/smoke boxes when both are visible;
   - remove unclear rain/fog/reflection samples from positive fire/smoke training;
   - keep those unclear samples as negatives if they represent deployment distractors.
4. For gloves/vest cases:
   - inspect whether boxes are missing, too loose, or too small;
   - add tight boxes for missed PPE;
   - keep hard occlusion cases if labels are correct.
5. Build a curated dataset copy after decisions are reviewed.
6. Train two candidates:
   - improved 7-class single model;
   - split candidate: PPE model plus fire/smoke model.
7. Compare candidates with the same `tools/run_yolo_probe.py` command before RKNN conversion.

## Training Direction

Do not start with aggressive class weighting. Use this order:

1. label cleanup;
2. hard-example augmentation;
3. low-learning-rate fine-tuning from the current best model;
4. only then consider class-specific sampling or split models.

This avoids improving one class while silently damaging the others.

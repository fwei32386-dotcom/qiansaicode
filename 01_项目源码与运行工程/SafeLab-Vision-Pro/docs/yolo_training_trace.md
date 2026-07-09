# YOLO Training Trace

## Acceptance Target

Temporary engineering target for "qualified":

- Keep the model as a 7-class detector: `person`, `helmet`, `vest`, `goggles`, `gloves`, `fire`, `smoke`.
- On the fixed probe set, target precision and recall should be around 0.70 or higher for key deployment classes.
- A candidate is not acceptable if it improves one weak class but clearly regresses important existing classes.

This target is intentionally stricter than "the training loss went down". Deployment qualification must come from the same probe comparison.

## 2026-07-01: weak5 From Current 20 Epochs

Purpose:

- Improve weak classes while starting from the current best 7-class model instead of COCO `yolov8n.pt`.
- Dataset: `D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_weak5_quick`
- Initial model: `runs/detect/models/checkpoints/safelab_yolov8n_full_fire_smoke_v3/weights/best.pt`
- Output model: `D:\ELFrk3588\yolo_training_runs\safelab_weak5_from_current_20e\weights\best.pt`

Training evidence:

- Args: `reports/yolo_probe_current/safelab_weak5_from_current_20e_args.yaml`
- Results: `reports/yolo_probe_current/safelab_weak5_from_current_20e_results.csv`
- Epoch 20 training-val summary: P 0.809, R 0.738, mAP50 0.781

Fixed probe at confidence 0.25:

- Baseline: `reports/yolo_probe_current/safelab_baseline_p30_conf250_iou_metrics.csv`
- Candidate: `reports/yolo_probe_current/safelab_weak5_from_current_20e_conf250_iou_metrics.csv`

| class | baseline P | baseline R | candidate P | candidate R | decision |
| --- | ---: | ---: | ---: | ---: | --- |
| person | 0.667 | 0.840 | 0.629 | 0.815 | regressed |
| helmet | 0.810 | 0.889 | 0.744 | 0.856 | regressed |
| vest | 0.784 | 0.702 | 0.675 | 0.912 | recall improved, precision regressed |
| goggles | 0.861 | 0.969 | 0.800 | 1.000 | acceptable but precision lower |
| gloves | 0.770 | 0.644 | 0.573 | 0.699 | recall improved slightly, precision too low |
| fire | 0.614 | 0.683 | 0.594 | 0.603 | regressed |
| smoke | 0.750 | 0.571 | 0.568 | 0.595 | recall slightly better, precision too low |

Conclusion:

- This candidate is not qualified for replacement.
- The direction is useful for vest recall, but the learning rate/optimizer setup was too aggressive for a conservative fine-tune.
- Next run should use explicit optimizer and lower learning rate, with settings written to `args.yaml`.

## Next Run

Use a conservative fine-tune from the current model:

```powershell
.\.venv-yolo\Scripts\python.exe tools\train_yolo_candidate.py --data D:/ELFrk3588/SafeLab-Vision-Pro/datasets/safelab_weak5_quick/data.yaml --model D:/ELFrk3588/SafeLab-Vision-Pro/资料/runs/detect/models/checkpoints/safelab_yolov8n_full_fire_smoke_v3/weights/best.pt --name safelab_weak5_from_current_lowlr_30e --epochs 30 --imgsz 416 --batch 16 --workers 0 --optimizer AdamW --lr0 0.001 --lrf 0.1
```

Expected purpose:

- Keep person/helmet/fire/smoke closer to baseline.
- Improve vest/gloves recall without a large precision collapse.

## 2026-07-01: weak5 From Current Low-LR 30 Epochs

Purpose:

- Repeat the weak5 fine-tune with explicit conservative optimizer settings.
- Initial model: `runs/detect/models/checkpoints/safelab_yolov8n_full_fire_smoke_v3/weights/best.pt`
- Output model: `D:\ELFrk3588\yolo_training_runs\safelab_weak5_from_current_lowlr_30e\weights\best.pt`

Training evidence:

- Args: `reports/yolo_probe_current/safelab_weak5_from_current_lowlr_30e_args.yaml`
- Results: `reports/yolo_probe_current/safelab_weak5_from_current_lowlr_30e_results.csv`
- Explicit settings confirmed in args: `optimizer=AdamW`, `lr0=0.001`, `lrf=0.1`, `workers=0`
- Epoch 30 training-val summary: P 0.791, R 0.745, mAP50 0.780

Fixed probe at confidence 0.25:

- Candidate: `reports/yolo_probe_current/safelab_weak5_from_current_lowlr_30e_conf250_iou_metrics.csv`

| class | baseline P | baseline R | low-lr P | low-lr R | decision |
| --- | ---: | ---: | ---: | ---: | --- |
| person | 0.667 | 0.840 | 0.644 | 0.802 | regressed |
| helmet | 0.810 | 0.889 | 0.783 | 0.850 | slightly regressed |
| vest | 0.784 | 0.702 | 0.650 | 0.912 | recall improved, precision regressed |
| goggles | 0.861 | 0.969 | 0.838 | 0.969 | close to baseline |
| gloves | 0.770 | 0.644 | 0.486 | 0.699 | precision too low |
| fire | 0.614 | 0.683 | 0.521 | 0.587 | regressed |
| smoke | 0.750 | 0.571 | 0.479 | 0.548 | regressed |

Conclusion:

- This candidate is not qualified for replacement.
- Lower learning rate did not solve the precision collapse for gloves/fire/smoke.
- Continuing to add epochs on the same weak5 subset is unlikely to reach qualification.

Next action:

- Build a review set from false positives and false negatives for `gloves`, `fire`, and `smoke`.
- Use the review set to decide whether labels are wrong, boundaries are ambiguous, or negative examples are missing.
- Retrain only after this data issue is addressed.

Review set generated:

- CSV: `reports/yolo_probe_current/safelab_lowlr_30e_review_priority.csv`
- Enriched CSV with source image and label paths: `reports/yolo_probe_current/safelab_lowlr_30e_review_enriched.csv`
- HTML: `reports/yolo_probe_current/safelab_lowlr_30e_review_page.html`
- Items: 102 priority samples
- Main review reasons:
  - `vest:1` appears in 20 rows
  - `gloves:1` appears in 18 rows
  - `smoke:1` appears in 18 rows
  - `fire:1` appears in 12 rows
- Source split: all 102 rows are from `val`
- Most common source prefixes:
  - `sh17`: 33 rows
  - `Fire and Smoke Dataset`: 24 rows
  - `dfire`: 17 rows
  - `ppe`: 14 rows
  - `hardhat`: 11 rows

This is now the gating artifact before the next training run. The model is not yet qualified; training should continue only after these samples are reviewed or converted into a cleaner follow-up dataset.

## 2026-07-01: Per-Class Threshold Check

Purpose:

- Check whether the low-lr 30e candidate can be made qualified by class-specific thresholds without retraining.
- Tool: `tools/filter_yolo_predictions.py`
- Thresholds tested on existing predictions: `vest=0.45`, `gloves=0.45`, `fire=0.45`, `smoke=0.45`
- Evidence: `reports/yolo_probe_current/safelab_lowlr_30e_filtered_weak045_iou_metrics.csv`

Result at fixed probe:

| class | P | R | finding |
| --- | ---: | ---: | --- |
| vest | 0.780 | 0.807 | usable tradeoff |
| gloves | 0.681 | 0.644 | still below target precision |
| fire | 0.744 | 0.460 | precision improves, recall too low |
| smoke | 0.750 | 0.429 | precision improves, recall too low |

Conclusion:

- Thresholding alone cannot make the model qualified.
- Fire/smoke need cleaner labels or additional hard examples, not just threshold tuning.
- Vest can likely use a higher deployment threshold after the model is otherwise qualified.

## 2026-07-01: mixed7 Balanced Dataset

Purpose:

- The weak5 subset improved vest recall but shifted the model away from baseline behavior.
- Build a 7-class mixed subset so person/helmet/goggles remain represented while weak classes are still sampled more evenly than the full dataset.

Dataset:

- Path: `D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_mixed7_quick`
- Builder: `tools/prepare_balanced_yolo_subset.py --classes 0,1,2,3,4,5,6 --per-class 700`
- Summary evidence: `reports/yolo_probe_current/safelab_mixed7_quick_dataset_summary.json`

Distribution:

| class | boxes |
| --- | ---: |
| person | 3160 |
| helmet | 6606 |
| vest | 2632 |
| goggles | 1162 |
| gloves | 2597 |
| fire | 2396 |
| smoke | 1511 |

Next run:

- Fine-tune from the current baseline model on mixed7 with explicit low learning rate.
- Compare against the same fixed probe before considering replacement.

## 2026-07-01: mixed7 From Current Low-LR 20 Epochs

Purpose:

- Test whether a 7-class balanced subset avoids the weak5 precision collapse while still improving weak classes.
- Initial model: `runs/detect/models/checkpoints/safelab_yolov8n_full_fire_smoke_v3/weights/best.pt`
- Output model: `D:\ELFrk3588\yolo_training_runs\safelab_mixed7_from_current_lowlr_20e\weights\best.pt`

Training evidence:

- Args: `reports/yolo_probe_current/safelab_mixed7_from_current_lowlr_20e_args.yaml`
- Results: `reports/yolo_probe_current/safelab_mixed7_from_current_lowlr_20e_results.csv`
- Epoch 20 training-val summary: P 0.790, R 0.706, mAP50 0.762

Fixed probe at confidence 0.25:

- Candidate: `reports/yolo_probe_current/safelab_mixed7_from_current_lowlr_20e_conf250_iou_metrics.csv`

| class | baseline P | baseline R | mixed7 P | mixed7 R | decision |
| --- | ---: | ---: | ---: | ---: | --- |
| person | 0.667 | 0.840 | 0.638 | 0.827 | slightly regressed |
| helmet | 0.810 | 0.889 | 0.747 | 0.869 | regressed |
| vest | 0.784 | 0.702 | 0.662 | 0.789 | recall improves, precision regresses |
| goggles | 0.861 | 0.969 | 0.698 | 0.938 | regressed |
| gloves | 0.770 | 0.644 | 0.662 | 0.644 | precision better than weak5, still below baseline |
| fire | 0.614 | 0.683 | 0.565 | 0.619 | regressed |
| smoke | 0.750 | 0.571 | 0.512 | 0.524 | regressed |

Conclusion:

- This candidate is not qualified for replacement.
- Mixed7 reduced the gloves precision collapse compared with weak5, but it still does not beat the baseline.
- Fire/smoke remain the main blocker; further training without cleaning fire/smoke samples is unlikely to reach qualification.

## 2026-07-01: mixed7 From Current Freeze10 Low-LR 20 Epochs

Purpose:

- Test whether freezing earlier layers keeps the baseline behavior more stable than full fine-tuning.
- Initial model: `runs/detect/models/checkpoints/safelab_yolov8n_full_fire_smoke_v3/weights/best.pt`
- Output model: `D:\ELFrk3588\yolo_training_runs\safelab_mixed7_from_current_freeze10_lowlr_20e\weights\best.pt`

Training evidence:

- Args: `reports/yolo_probe_current/safelab_mixed7_from_current_freeze10_lowlr_20e_args.yaml`
- Results: `reports/yolo_probe_current/safelab_mixed7_from_current_freeze10_lowlr_20e_results.csv`
- Epoch 20 training-val summary: P 0.804, R 0.710, mAP50 0.779
- Important args: `optimizer=AdamW`, `lr0=0.001`, `lrf=0.1`, `freeze=10`, `workers=0`

Fixed probe at confidence 0.25:

- Candidate: `reports/yolo_probe_current/safelab_mixed7_from_current_freeze10_lowlr_20e_conf250_iou_metrics.csv`

| class | baseline P | baseline R | mixed7 P | mixed7 R | freeze10 P | freeze10 R | decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| person | 0.667 | 0.840 | 0.638 | 0.827 | 0.627 | 0.852 | recall improves, precision regresses |
| helmet | 0.810 | 0.889 | 0.747 | 0.869 | 0.747 | 0.869 | still below baseline |
| vest | 0.784 | 0.702 | 0.662 | 0.789 | 0.662 | 0.825 | recall improves, precision regresses |
| goggles | 0.861 | 0.969 | 0.698 | 0.938 | 0.714 | 0.938 | slightly better than mixed7, below baseline |
| gloves | 0.770 | 0.644 | 0.662 | 0.644 | 0.676 | 0.658 | slight improvement over mixed7 |
| fire | 0.614 | 0.683 | 0.565 | 0.619 | 0.646 | 0.667 | better than mixed7, near baseline |
| smoke | 0.750 | 0.571 | 0.512 | 0.524 | 0.700 | 0.667 | better recall than baseline, lower precision |

Threshold scan:

| config | useful result | blocker |
| --- | --- | --- |
| all030 | gloves P 0.734, fire P/R 0.714/0.635, smoke P/R 0.765/0.619 | vest P 0.687, goggles P 0.725 |
| ppe035_vest040_glove030_fire025 | vest P/R 0.804/0.719 | person P 0.694, gloves R 0.644, fire/smoke P below 0.70/0.75 |
| ppe040_vest045_glove035_fire025 | helmet P/R 0.837/0.804, vest P/R 0.848/0.684, goggles P/R 0.829/0.906 | vest/gloves recall falls below target |
| all040 | helmet/goggles/vest precision pass 0.80 | gloves/fire/smoke recall falls too far |

Threshold evidence:

- `reports/yolo_probe_current/safelab_mixed7_freeze10_threshold_all030_iou_metrics.csv`
- `reports/yolo_probe_current/safelab_mixed7_freeze10_threshold_ppe035_vest040_glove030_fire025_iou_metrics.csv`
- `reports/yolo_probe_current/safelab_mixed7_freeze10_threshold_ppe040_vest045_glove035_fire025_iou_metrics.csv`
- `reports/yolo_probe_current/safelab_mixed7_freeze10_threshold_all040_iou_metrics.csv`

Conclusion:

- Freeze10 is the best direction tested so far for fire/smoke stability, but it is still not qualified for replacement.
- Per-class thresholds can recover precision for helmet/vest/goggles, but they cannot simultaneously keep enough recall for gloves/fire/smoke.
- Next work should focus on cleaning/reviewing hard samples for gloves, fire, and smoke before another training run.

## 2026-07-01: Alignment With Master SafeLab Plan

Source plan:

- `D:\ELFrk3588\SafeLab-Vision_Pro_最强版三人分工统一接口与实现指导(1).docx`

Model-related requirements extracted from the plan:

- Do not build a plain YOLO demo; the model must support the chain `visual input -> RKNN/NPU inference -> Detection -> risk cognition -> alarm evidence -> automatic evaluation`.
- Keep the stable `Detection` contract in `docs/interface_spec.md`, including label order `person, helmet, vest, goggles, gloves, fire, smoke`.
- Produce CSV/HTML/JSON evidence under `reports/` for model and latency decisions.
- When the model is unstable, allowed controls are local scenario data supplementation, threshold tuning, and temporal confirmation tuning.
- Do not replace the deployed model unless the candidate passes a repeatable acceptance gate.

Acceptance gate added:

- Tool: `tools/yolo_acceptance_report.py`
- Baseline report:
  - `reports/yolo_probe_current/safelab_baseline_acceptance_report.md`
  - `reports/yolo_probe_current/safelab_baseline_acceptance_report.json`
- Freeze10 report:
  - `reports/yolo_probe_current/safelab_freeze10_acceptance_report.md`
  - `reports/yolo_probe_current/safelab_freeze10_acceptance_report.json`

Current gate result:

| candidate | qualified | passing classes | failing classes |
| --- | --- | --- | --- |
| baseline | false | helmet, vest, goggles | person precision, gloves recall, fire precision/recall, smoke recall |
| freeze10 | false | helmet, goggles | person precision, vest precision, gloves precision/recall, fire precision/recall, smoke recall |

Decision:

- Keep baseline as the deployment reference for now.
- Do not promote freeze10 to the deployed model.
- Continue improvement according to the master plan: clean or supplement local hard samples first, then run low-learning-rate fine-tuning, then rerun the same acceptance report before RKNN conversion.

## 2026-07-01: Cleaning Decision Gate

Purpose:

- Follow the master plan by turning hard-sample review decisions into a reproducible curated dataset before more training.
- Prevent unreviewed or guessed labels from entering the next fine-tuning run.

Artifacts:

- Workflow: `docs/yolo_cleaning_decision_workflow.md`
- Tool: `tools/apply_yolo_cleaning_decisions.py`
- Test: `tests/test_apply_yolo_cleaning_decisions.py`
- Input plan: `reports/yolo_probe_current/safelab_hard_sample_cleaning_plan.csv`

Verification:

- `python -m unittest discover -s tests -p "test_apply_yolo_cleaning_decisions.py" -v`
- `python -m unittest discover -s tests -p "test_yolo*.py" -v`
- Real cleaning plan build was attempted without `--allow-unreviewed` and correctly failed with:
  - `CleaningDecisionError: 102 rows are unreviewed`

Decision:

- Do not start another training run from the 102 hard samples until their `decision` values are reviewed.
- Once reviewed, build `D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_curated_from_cleaning_plan`, train from the baseline with low learning rate, then rerun the fixed probe and acceptance gate.

## 2026-07-01: Baseline + Freeze10 Fire/Smoke Ensemble Probe

Purpose:

- Test whether a two-model deployment shortcut can reach the acceptance gate before manual hard-sample review.
- Use baseline predictions for classes `0..4` and freeze10 predictions for `5 fire` and `6 smoke`.

Artifacts:

- Merge tool: `tools/merge_yolo_predictions.py`
- Test: `tests/test_merge_yolo_predictions.py`
- Probe metrics: `reports/yolo_probe_current/safelab_ensemble_baseline_freeze10_fire_smoke_conf250_iou_metrics.csv`
- Acceptance report: `reports/yolo_probe_current/safelab_ensemble_baseline_freeze10_fire_smoke_acceptance_report.md`
- Acceptance JSON: `reports/yolo_probe_current/safelab_ensemble_baseline_freeze10_fire_smoke_acceptance_report.json`

Result:

| class | P | R | status |
| --- | ---: | ---: | --- |
| person | 0.667 | 0.840 | fail: precision below 0.70 |
| helmet | 0.810 | 0.889 | pass |
| vest | 0.784 | 0.702 | pass |
| goggles | 0.861 | 0.969 | pass |
| gloves | 0.770 | 0.644 | fail: recall below 0.70 |
| fire | 0.646 | 0.667 | fail: precision/recall below 0.70 |
| smoke | 0.700 | 0.667 | fail: recall below 0.70 |

Decision:

- The ensemble is better than baseline for fire/smoke balance, but it still does not pass the acceptance gate.
- Do not deploy the ensemble as a replacement.
- This confirms that model fusion alone is not enough; the next improvement step remains hard-sample review, local data supplementation, and low-learning-rate retraining.

## 2026-07-01: Fast Per-Class Threshold Scan

Purpose:

- Determine whether deployment threshold tuning can reach the SafeLab acceptance gate without more training.
- Replace the initial slow full-grid threshold scan with independent per-class threshold search.

Tooling:

- Tool: `tools/scan_yolo_thresholds.py`
- Test: `tests/test_scan_yolo_thresholds.py`
- Summary: `reports/yolo_probe_current/safelab_threshold_scan_summary.md`

Evidence:

- Baseline threshold scan: `reports/yolo_probe_current/safelab_baseline_threshold_scan_conf150_rerun.json`
- Freeze10 threshold scan: `reports/yolo_probe_current/safelab_freeze10_threshold_scan_conf150.json`
- Ensemble threshold scan: `reports/yolo_probe_current/safelab_ensemble_threshold_scan_conf150.json`

Best result by threshold tuning:

| class | best P | best R | status |
| --- | ---: | ---: | --- |
| person | 0.744 | 0.827 | pass |
| helmet | 0.717 | 0.895 | pass |
| vest | 0.712 | 0.737 | pass |
| goggles | 0.816 | 0.969 | pass |
| gloves | 0.738 | 0.658 | fail: recall |
| fire | 0.714 | 0.635 | fail: recall |
| smoke | 0.700 | 0.667 | fail: recall |

Decision:

- Threshold tuning is useful for deployment, but it cannot make the model qualified by itself.
- The remaining blockers are recall for `gloves`, `fire`, and `smoke`.
- Continue with hard-sample review/local data supplementation before the next training run.

## 2026-07-01: Hard-Recall7 Fine-Tune Attempt

Purpose:

- Test whether a balanced 7-class subset with extra `gloves`, `fire`, and `smoke` samples can improve the remaining recall blockers without dropping other SafeLab classes.
- Keep the deployed baseline unchanged until a candidate passes the same acceptance gate.

Dataset:

- Dataset: `D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_hard_recall7`
- Summary: `reports/yolo_probe_current/safelab_hard_recall7_subset_summary.json`
- Class distribution summary: `reports/yolo_probe_current/safelab_hard_recall7_dataset_summary.json`
- Total images: 8695
- Split: train 5905, val 1457, test 1333
- Box distribution: person 3030, helmet 5107, vest 1964, goggles 995, gloves 3655, fire 3817, smoke 2471

Training:

- Base model: `safelab_yolov8n_full_fire_smoke_v3/weights/best.pt`
- Candidate: `D:\ELFrk3588\yolo_training_runs\safelab_hard_recall7_freeze10_lowlr_20e\weights\best.pt`
- Frozen layers: 10
- Epochs: 20
- Image size: 416
- Batch: 16
- Optimizer: AdamW
- Learning rate: `lr0=0.001`, `lrf=0.1`
- Training args: `reports/yolo_probe_current/safelab_hard_recall7_freeze10_lowlr_20e_args.yaml`
- Training curve: `reports/yolo_probe_current/safelab_hard_recall7_freeze10_lowlr_20e_results.csv`

Training validation final epoch:

| epoch | P | R | mAP50 | mAP50-95 |
| ---: | ---: | ---: | ---: | ---: |
| 20 | 0.816 | 0.722 | 0.783 | 0.453 |

Fixed probe at confidence 0.25:

- Metrics: `reports/yolo_probe_current/safelab_hard_recall7_freeze10_lowlr_20e_conf250_iou_metrics.csv`
- Acceptance report: `reports/yolo_probe_current/safelab_hard_recall7_freeze10_lowlr_20e_acceptance_report.md`
- Acceptance JSON: `reports/yolo_probe_current/safelab_hard_recall7_freeze10_lowlr_20e_acceptance_report.json`

| class | P | R | status |
| --- | ---: | ---: | --- |
| person | 0.633 | 0.852 | fail: precision below 0.70 |
| helmet | 0.757 | 0.876 | pass |
| vest | 0.667 | 0.772 | fail: precision below 0.70 |
| goggles | 0.861 | 0.969 | pass |
| gloves | 0.653 | 0.671 | fail: precision/recall below 0.70 |
| fire | 0.526 | 0.635 | fail: precision/recall below 0.70 |
| smoke | 0.629 | 0.524 | fail: precision/recall below 0.70 |

Threshold scan:

- Scan output: `reports/yolo_probe_current/safelab_hard_recall7_freeze10_lowlr_20e_threshold_scan_conf150.json`
- Selected thresholds: person 0.40, helmet 0.20, vest 0.30, goggles 0.15, gloves 0.30, fire 0.30, smoke 0.20

| class | best P | best R | status |
| --- | ---: | ---: | --- |
| person | 0.705 | 0.827 | pass |
| helmet | 0.730 | 0.882 | pass |
| vest | 0.745 | 0.719 | pass |
| goggles | 0.838 | 0.969 | pass |
| gloves | 0.697 | 0.630 | fail |
| fire | 0.638 | 0.587 | fail |
| smoke | 0.615 | 0.571 | fail |

Decision:

- Do not promote this candidate. It does not pass the acceptance gate and is weaker than the prior baseline/ensemble path for `fire` and `smoke`.
- More epochs with the same data recipe are unlikely to be enough because the failure is class-specific and persists after threshold tuning.
- Next training should use reviewed hard-sample cleaning decisions and added local scenario samples for `gloves`, `fire`, and `smoke`, then rerun the same fixed probe and acceptance report.

## 2026-07-01: YOLOv8s 640 Hard-Recall7 Capacity Attempt

Purpose:

- Test whether a larger YOLOv8s model at the same 640 image size used by the fixed probe can improve the weak classes.
- Keep the deployed baseline unchanged until the candidate passes the acceptance gate.

Training:

- Dataset: `D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_hard_recall7`
- Base model: `yolov8s.pt`
- Candidate: `D:\ELFrk3588\yolo_training_runs\safelab_hard_recall7_yolov8s_640_30e\weights\best.pt`
- Epochs: 30
- Image size: 640
- Batch: 8
- Optimizer: AdamW
- Learning rate: `lr0=0.001`, `lrf=0.1`
- Training args: `reports/yolo_probe_current/safelab_hard_recall7_yolov8s_640_30e_args.yaml`
- Training curve: `reports/yolo_probe_current/safelab_hard_recall7_yolov8s_640_30e_results.csv`

Training validation final epoch:

| epoch | P | R | mAP50 | mAP50-95 |
| ---: | ---: | ---: | ---: | ---: |
| 30 | 0.762 | 0.707 | 0.741 | 0.413 |

Fixed probe at confidence 0.25:

- Metrics: `reports/yolo_probe_current/safelab_hard_recall7_yolov8s_640_30e_conf250_iou_metrics.csv`
- Acceptance report: `reports/yolo_probe_current/safelab_hard_recall7_yolov8s_640_30e_acceptance_report.md`
- Acceptance JSON: `reports/yolo_probe_current/safelab_hard_recall7_yolov8s_640_30e_acceptance_report.json`

| class | P | R | status |
| --- | ---: | ---: | --- |
| person | 0.619 | 0.802 | fail: precision below 0.70 |
| helmet | 0.726 | 0.830 | pass |
| vest | 0.611 | 0.772 | fail: precision below 0.70 |
| goggles | 0.789 | 0.938 | pass |
| gloves | 0.617 | 0.685 | fail: precision/recall below 0.70 |
| fire | 0.596 | 0.540 | fail: precision/recall below 0.70 |
| smoke | 0.548 | 0.405 | fail: precision/recall below 0.70 |

Threshold scan:

- Scan output: `reports/yolo_probe_current/safelab_hard_recall7_yolov8s_640_30e_threshold_scan_conf150.json`
- Selected thresholds: person 0.40, helmet 0.20, vest 0.35, goggles 0.15, gloves 0.35, fire 0.20, smoke 0.25

| class | best P | best R | status |
| --- | ---: | ---: | --- |
| person | 0.713 | 0.765 | pass |
| helmet | 0.704 | 0.856 | pass |
| vest | 0.750 | 0.737 | pass |
| goggles | 0.721 | 0.969 | pass |
| gloves | 0.701 | 0.644 | fail: recall |
| fire | 0.561 | 0.587 | fail |
| smoke | 0.548 | 0.405 | fail |

Decision:

- Do not promote this candidate. Capacity and 640 training improved the overall training validation curve, but the fixed probe still fails.
- YOLOv8s plus threshold tuning can make `person`, `helmet`, `vest`, and `goggles` pass, but it still does not solve `gloves`, `fire`, and `smoke`.
- Next model work should not be another blind epoch increase. It should focus on reviewed hard-sample cleaning, local scenario supplementation, and a fire/smoke-specialized candidate or two-model deployment experiment.

## 2026-07-01: Fire/Smoke YOLOv8s Specialist Attempt

Purpose:

- Validate the confirmed conservative dual-model plan:
  - PPE/person model remains lightweight.
  - Fire/smoke uses a YOLOv8s specialist.
- Do not replace the RK3588 board model before offline acceptance, ONNX export, RKNN conversion, board runtime check, and FPS evidence.

Strategy:

- Deployment strategy doc: `docs/dual_model_deployment_strategy.md`
- Dataset: `D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_fire_smoke`
- Classes: `0 fire`, `1 smoke`
- Candidate: `D:\ELFrk3588\yolo_training_runs\safelab_fire_smoke_yolov8s_640_15e\weights\best.pt`
- Base model: `yolov8s.pt`
- Epochs: 15
- Image size: 640
- Batch: 8
- Optimizer: AdamW
- Training args: `reports/yolo_probe_current/safelab_fire_smoke_yolov8s_640_15e_args.yaml`
- Training curve: `reports/yolo_probe_current/safelab_fire_smoke_yolov8s_640_15e_results.csv`

Training validation final epoch:

| epoch | P | R | mAP50 | mAP50-95 |
| ---: | ---: | ---: | ---: | ---: |
| 15 | 0.752 | 0.630 | 0.713 | 0.403 |

Fire/smoke probe at confidence 0.25:

- Probe size: 80 samples per class from `safelab_fire_smoke`
- Metrics: `reports/yolo_probe_current/safelab_fire_smoke_yolov8s_640_15e_p80_conf250_iou_metrics.csv`
- Acceptance report: `reports/yolo_probe_current/safelab_fire_smoke_yolov8s_640_15e_acceptance_report.md`
- Acceptance JSON: `reports/yolo_probe_current/safelab_fire_smoke_yolov8s_640_15e_acceptance_report.json`

| class | P | R | status |
| --- | ---: | ---: | --- |
| fire | 0.650 | 0.657 | fail: precision/recall below 0.70 |
| smoke | 0.742 | 0.589 | fail: recall below 0.70 |

Threshold scan:

- Scan output: `reports/yolo_probe_current/safelab_fire_smoke_yolov8s_640_15e_threshold_scan_conf150.json`
- Selected thresholds: fire 0.25, smoke 0.20

| class | best P | best R | status |
| --- | ---: | ---: | --- |
| fire | 0.650 | 0.657 | fail |
| smoke | 0.673 | 0.625 | fail |

Decision:

- Do not promote this fire/smoke specialist yet.
- The specialist is directionally useful for the dual-model strategy, but 15 epochs are not enough to pass `P >= 0.70` and `R >= 0.70` for both fire and smoke.
- Next fire/smoke work should continue from this candidate with more epochs and hard negative/label-boundary cleaning before RKNN conversion.

# YOLO Cleaning Decision Workflow

Source plan:

- SafeLab-Vision Pro master DOCX.
- Absolute file: `D:\ELFrk3588\SafeLab-Vision_Pro_master_plan.docx` in this note refers to the original root-level Chinese-named DOCX supplied by the user.

Purpose:

- Convert reviewed hard samples into a reproducible curated YOLO dataset.
- Avoid training on unreviewed or guessed labels.
- Keep every model-improvement step traceable through CSV, generated datasets, tests, and git commits.

Inputs:

- Cleaning plan: `reports/yolo_probe_current/safelab_hard_sample_cleaning_plan.csv`
- Review pack: `reports/yolo_probe_current/safelab_hard_sample_review_pack`
- Original dataset: `D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab`

Decision values:

| decision | meaning | dataset action |
| --- | --- | --- |
| `keep` | source label is acceptable | copy source image and label |
| `remove` | sample should not be used for retraining | skip source image and label |
| `add_negative` | image is a useful distractor but should have no target boxes | copy image and write an empty label file |
| `relabel` | label must be manually corrected first | copy image and use `review_label` path from the CSV |
| `unreviewed` | no human decision yet | blocked by default |

Build command after review:

```powershell
.\.venv-yolo\Scripts\python.exe tools\apply_yolo_cleaning_decisions.py `
  --plan-csv reports\yolo_probe_current\safelab_hard_sample_cleaning_plan.csv `
  --output-dataset D:\ELFrk3588\SafeLab-Vision-Pro\datasets\safelab_curated_from_cleaning_plan
```

Expected behavior before review:

- The command must fail with `CleaningDecisionError: 102 rows are unreviewed`.
- This is intentional and prevents accidental training on unreviewed hard samples.

Next training gate after review:

1. Build the curated dataset from reviewed decisions.
2. Train a low-learning-rate candidate from the current baseline.
3. Run the fixed probe with `tools/run_yolo_probe.py`.
4. Run `tools/yolo_acceptance_report.py`.
5. Replace or convert a model only when the acceptance report says `qualified: true`.

Rollback:

- Revert the git commit that introduced a bad cleaning plan or curated dataset.
- Delete the generated curated dataset directory and rebuild from the previous reviewed CSV.

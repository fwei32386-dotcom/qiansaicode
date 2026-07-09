# Dataset Sources

SafeLab-Vision Pro currently targets five detection classes:

```text
person
helmet
vest
fire
smoke
```

## Recommended Search Direction

Use public datasets only as the first training baseline. Final accuracy should be improved with images from the real deployment environment after the camera is available.

### PPE: person, helmet, vest

Look for datasets with YOLO annotations and clear PPE labels:

- Kaggle PPE / safety helmet / safety vest datasets
- Roboflow Universe PPE detection datasets
- SH17 safety helmet and PPE style datasets
- Construction safety datasets containing person, helmet, vest

Selection checklist:

- Has bounding boxes, not only classification labels
- Includes people with and without PPE
- Includes helmet and vest as separate classes
- Has enough negative examples where person exists but PPE is absent
- Allows project use under its license

### Fire and Smoke

Look for object detection datasets, not only image classification datasets:

- D-Fire style fire/smoke detection datasets
- Roboflow fire and smoke object detection datasets
- Kaggle fire/smoke YOLO datasets
- Fire and smoke YOLOv9/YOLOv8 datasets with bounding boxes
- Open fire/smoke detection datasets with bounding boxes

Selection checklist:

- Fire and smoke are separately labeled
- Contains small and distant smoke targets
- Contains non-fire red/orange objects as negative examples
- Contains fog, steam, bright lights, and reflections if possible

## Dataset Merge Rules

When combining datasets, normalize class ids to:

```text
0 person
1 helmet
2 vest
3 fire
4 smoke
```

Do not keep source-specific ids. Every YOLO label file must use the class ids above.

## Current Local Layout

```text
datasets/safelab/
  data.yaml
  images/train/
  images/val/
  images/test/
  labels/train/
  labels/val/
  labels/test/
```

Large image and label files are intentionally ignored by `.gitignore`.

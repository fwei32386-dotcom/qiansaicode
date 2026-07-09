# Model Readiness Checklist

Use this checklist before starting training.

## Dataset

- [ ] Data license allows project use
- [ ] Images are sorted into train/val/test
- [ ] Labels are YOLO detection labels
- [ ] Class ids match `datasets/safelab/data.yaml`
- [ ] No empty or corrupt image files
- [ ] Negative examples are included
- [ ] Similar frames are not split across train and val

## Annotation

- [ ] Helmet boxes are tight and separate from person boxes
- [ ] Vest boxes are tight and separate from person boxes
- [ ] Fire and smoke are separate classes
- [ ] Ambiguous fog/steam/reflection cases are handled consistently
- [ ] A small sample has been manually reviewed

## Training

- [ ] Baseline model selected
- [ ] Training command saved
- [ ] Validation metrics saved
- [ ] Failure examples reviewed

## Export

- [ ] Best PT model exported to ONNX
- [ ] ONNX file copied to `models/onnx`
- [ ] Labels copied to `models/labels.txt`
- [ ] Calibration images copied to `models/calibration/images`

## RKNN

- [ ] RKNN-Toolkit2 environment prepared on Ubuntu
- [ ] ONNX converted to RKNN
- [ ] RKNN copied to `models/rknn`
- [ ] Board inference smoke test planned

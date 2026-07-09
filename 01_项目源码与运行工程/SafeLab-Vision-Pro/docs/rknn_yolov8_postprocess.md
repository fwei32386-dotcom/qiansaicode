# RKNN YOLOv8 Postprocess

This project uses the RKNN model output as detector input only. Risk decisions
must still go through the SafeLab rule pipeline.

## Current Board Model

```text
model: /root/SafeLab-Vision-Pro/models/rknn/safelab_yolov8n_fire_smoke_v3.rknn
input:  [1, 640, 640, 3] NHWC INT8
output: [1, 11, 8400] INT8
labels: person, helmet, vest, goggles, gloves, fire, smoke
```

The 11 channels are:

```text
0 cx
1 cy
2 width
3 height
4 person
5 helmet
6 vest
7 goggles
8 gloves
9 fire
10 smoke
```

## Required Steps

1. Dequantize RKNN INT8 output:

```text
float_value = (int8_value - zero_point) * scale
```

For the current model document:

```text
output0 zero_point = -128
output0 scale = 2.560589
```

2. Decode `[1, 11, 8400]` as YOLOv8 channel-major output.
3. For every anchor, take the highest class score.
4. Filter by confidence threshold.
5. Convert `cx, cy, w, h` in 640x640 letterboxed input space back to original frame coordinates.
6. Run class-aware NMS.
7. Convert `[x1, y1, x2, y2, confidence, class_id]` to project `Detection` objects through `ai_engine/detection_adapter.py`.

## Windows Reference

The Windows reference implementation is:

```text
ai_engine/yolov8_postprocess.py
```

It is intentionally pure Python so the behavior can be tested before writing
the board C/C++ RKNN Runtime version.

Run:

```bash
python -m unittest tests.test_yolov8_postprocess
```

## Next Board Implementation

The board C/C++ program should reproduce the same steps:

```text
RKNN init
image load or camera frame
letterbox to 640x640
NHWC INT8 input
rknn_run
read output0
dequantize
YOLOv8 decode
NMS
print or write Detection JSON
```

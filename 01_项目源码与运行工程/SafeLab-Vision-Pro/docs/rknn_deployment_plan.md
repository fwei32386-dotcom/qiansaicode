# RKNN Deployment Plan

The deployment path is:

```text
Windows YOLOv8 training
  -> best.pt
  -> ONNX
  -> Ubuntu RKNN-Toolkit2 conversion
  -> RKNN model
  -> RK3588 inference
```

## Ubuntu Conversion Role

Use Ubuntu x86_64 for RKNN conversion because Rockchip's RKNN-Toolkit2 is designed for that workflow.

Inputs:

```text
models/onnx/safelab_yolov8n.onnx
models/labels.txt
models/calibration/images/
```

Output:

```text
models/rknn/safelab_yolov8n.rknn
```

## Calibration Images

Use representative images from the deployment domain:

```text
models/calibration/images/
```

Recommended first calibration set:

- 100 to 300 images
- includes normal scenes
- includes PPE violations
- includes smoke/fire examples
- includes difficult negatives such as reflections, fog, steam, red warning lights

## Board Deployment

The final board package should include:

```text
models/rknn/safelab_yolov8n.rknn
models/labels.txt
configs/model_config.yaml
```

The RK3588 should only run inference and rule logic. It should not train models.

Current board status:

```text
/root/SafeLab-Vision-Pro/models/rknn/safelab_yolov8n_fire_smoke_v3.rknn exists
/root/SafeLab-Vision-Pro/models/labels.txt exists
/root/SafeLab-Vision-Pro/test_images exists
/usr/lib/librknnrt.so exists
/usr/bin/rknn_common_test exists
```

The current acceptance probe has loaded the RKNN model and one test image with
`rknn_common_test`, reporting about 75 ms per inference, or about 13 FPS. This
means the model/runtime layer is no longer simply "missing". The remaining RKNN
work is:

```text
compile safelab_rknn_detect with rknn_api.h
implement RKNN init/input/output extraction
apply YOLOv8 postprocess and NMS
write Detection JSON compatible with runtime/interfaces.py
feed those detections into the existing rule engine
```

Use this shell-only board check to refresh RKNN evidence:

```sh
sh tools/board_rknn_runtime_check.sh
```

The C++ runtime build entry is:

```sh
cd rknn_runtime
make CXX=/path/to/aarch64-linux-g++ \
     RKNN_SDK=/path/to/rknpu2/runtime/Linux/librknn_api \
     RKNN_LIB_DIR=/path/to/rknpu2/runtime/Linux/librknn_api/aarch64
```

## Integration Contract

The model runtime must output `Detection` objects compatible with:

```text
runtime/interfaces.py
```

Required fields:

```text
frame_id
source_type
class_name
confidence
bbox
center
area
model_name
infer_time_ms
```

## YOLOv8 Postprocess

The current RKNN model output is documented in:

```text
docs/rknn_yolov8_postprocess.md
```

Use the Windows reference implementation before writing the board C/C++ runtime:

```text
ai_engine/yolov8_postprocess.py
```

The required bridge is:

```text
RKNN output0 [1, 11, 8400]
-> dequantize
-> YOLOv8 decode
-> NMS
-> [x1, y1, x2, y2, confidence, class_id]
-> ai_engine/detection_adapter.py
-> runtime.interfaces.Detection
```

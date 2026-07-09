# RKNN Runtime Source Skeleton

This directory is reserved for the board-side C/C++ RKNN runtime.

Current board findings:

```text
/usr/lib/librknnrt.so exists
/usr/bin/rknn_common_test exists
gcc/g++ are missing on the board
rknn_api.h is missing on the board
```

So the next real build should happen with a Buildroot or Rockchip cross toolchain
that provides `rknn_api.h` and links against `librknnrt.so`.

Planned executable:

```text
safelab_rknn_detect
```

Current verified board status:

```text
models/rknn/safelab_yolov8n_fire_smoke_v3.rknn exists
models/labels.txt exists
test_images/ exists
rknn_common_test can load the model and one image
measured probe: about 75 ms / 13 FPS on one board run
```

Initial scope:

```text
load RKNN model
load one image from test_images
letterbox to 640x640
run RKNN
decode YOLOv8 output [1, 11, 8400]
write Detection JSON
```

Implemented now:

```text
YOLOv8 channel-major decode helper
INT8 dequantize helper
class-aware NMS helper
Detection JSON formatter
native safelab_rknn_detect contract CLI
```

The current native CLI can emit Detection JSONL without RKNN SDK headers:

```sh
make
./safelab_rknn_detect --contract
./safelab_rknn_detect --raw 10,20,110,220,0.91,0 --output detections.jsonl
```

This keeps the C++ output contract testable before `rknn_api.h` is available.
The later RKNN runner should feed real decoded boxes into the same
`Detection JSON` writer.

Replay the generated JSONL through the rule pipeline:

```sh
python tools/replay_detection_jsonl.py detections.jsonl
```

Still waiting for SDK/toolchain:

```text
rknn_api.h
aarch64 cross compiler or board-side g++
image loader / letterbox implementation
RKNN init/run/output extraction
```

Build entry:

```sh
make
```

Cross-build entry once the Rockchip SDK/toolchain is available:

```sh
make \
  WITH_RKNN=1 \
  CXX=/path/to/aarch64-linux-g++ \
  RKNN_SDK=/path/to/rknpu2/runtime/Linux/librknn_api \
  RKNN_LIB_DIR=/path/to/rknpu2/runtime/Linux/librknn_api/aarch64
```

Board-side acceptance command:

```sh
sh tools/board_rknn_runtime_check.sh
```

That command does not require Python. It records whether the model, labels,
`librknnrt.so`, `rknn_common_test`, and a one-image RKNN probe are available.

The Python reference for the postprocess is:

```text
ai_engine/yolov8_postprocess.py
ai_engine/detection_adapter.py
```

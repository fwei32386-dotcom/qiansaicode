# SafeLab Dual RKNN Conversion

This package keeps the old 7-class RKNN path untouched and converts the two new candidate models to separate RKNN files.

## Input ONNX Files

Place these files in `models/onnx/`:

- `safelab_ppe_rehearsal_hard_v1_yolov8n_640_20e.onnx`
- `safelab_fire_smoke_rehearsal_hard_v1_yolov8s_640_20e.onnx`

Class labels:

- PPE: `models/labels_ppe.txt`
- Fire/smoke: `models/labels_fire_smoke.txt`

## Convert In Ubuntu VM

From the VM terminal:

```bash
cd /path/to/rknn_transfer_package
python3 convert_dual_onnx_to_rknn_fp.py --list-models
python3 convert_dual_onnx_to_rknn_fp.py --model all
```

Expected outputs:

```text
models/rknn/safelab_ppe_rehearsal_hard_v1_yolov8n_640_20e_fp.rknn
models/rknn/safelab_fire_smoke_rehearsal_hard_v1_yolov8s_640_20e_fp.rknn
```

The default build is FP/non-quantized because the previous INT8 path compressed YOLOv8 class scores too aggressively. Use `--quantize` only after FP inference is validated.

## INT8 Quantization

To build INT8 candidates without overwriting the FP files:

```bash
python3 convert_dual_onnx_to_rknn_fp.py --model all --quantize
```

This uses `calibration.txt`, `w8a8`, `mmse`, `channel` quantization, and RKNN auto-hybrid by default to reduce accuracy loss. Expected outputs:

```text
models/rknn/safelab_ppe_rehearsal_hard_v1_yolov8n_640_20e_int8.rknn
models/rknn/safelab_fire_smoke_rehearsal_hard_v1_yolov8s_640_20e_int8.rknn
```

If the Ubuntu VM runs out of memory during MMSE, use:

```bash
python3 convert_dual_onnx_to_rknn_fp.py --model all --quantize --quantized-algorithm normal
```

This keeps calibration and auto-hybrid enabled while using the lower-memory quantizer.

## Board Deployment Rule

Do not overwrite the current board RKNN model. Upload the two new RKNN files under new names, run FPS/runtime checks, verify Detection JSON, then decide whether to switch the runtime scheduler.

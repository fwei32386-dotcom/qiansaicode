# Windows Training Plan

The RK3588 board is for inference only. Training should run on Windows, Ubuntu, or a cloud machine with a GPU.

## Environment

Recommended:

```text
Windows 10/11
Python 3.10 or 3.11 for Ultralytics compatibility
NVIDIA GPU + CUDA if available
```

Create a training environment outside the board runtime:

```powershell
python -m venv .venv-yolo
.\.venv-yolo\Scripts\activate
pip install -U pip
pip install ultralytics
```

## Dataset

Put YOLO-format data under:

```text
datasets/safelab/
  images/train/
  images/val/
  labels/train/
  labels/val/
  data.yaml
```

Full model class order must match:

```text
0 person
1 helmet
2 vest
3 goggles
4 gloves
5 fire
6 smoke
```

PPE-only model class order must match:

```text
0 person
1 helmet
2 vest
3 goggles
4 gloves
```

## First Deployment Training

For RK3588 deployment, use YOLOv8n as the default model. It is smaller, faster, and easier to deploy on the board than larger YOLOv8 variants.

For the current PPE-only stage, use:

```powershell
yolo detect train model=yolov8n.pt data=datasets/safelab_ppe/data.yaml imgsz=640 epochs=50 batch=16 project=models/checkpoints name=safelab_ppe_yolov8n
```

For the full safety model:

```powershell
yolo detect train model=yolov8n.pt data=datasets/safelab/data.yaml imgsz=640 epochs=50 batch=16 project=models/checkpoints name=safelab_yolov8n
```

If GPU memory is limited, reduce batch:

```powershell
yolo detect train model=yolov8n.pt data=datasets/safelab/data.yaml imgsz=640 epochs=50 batch=8 project=models/checkpoints name=safelab_yolov8n
```

If accuracy is not enough later, improve the dataset first, then consider a larger reference model only for comparison. The deployed board model remains YOLOv8n unless real RK3588 tests prove another model is acceptable.

```text
YOLOv8n deployment model -> ONNX -> RKNN -> RK3588
```

## Validation

```powershell
yolo detect val model=models/checkpoints/safelab_yolov8n/weights/best.pt data=datasets/safelab/data.yaml imgsz=640
```

Important metrics:

- mAP50 and mAP50-95
- per-class precision and recall
- false alarms for smoke/fire
- missed helmet/vest cases

## Export ONNX

```powershell
yolo export model=models/checkpoints/safelab_yolov8n/weights/best.pt format=onnx imgsz=640 opset=12 simplify=True
```

Copy the exported ONNX model to:

```text
models/onnx/safelab_yolov8n.onnx
```

Then convert it to RKNN on Ubuntu.

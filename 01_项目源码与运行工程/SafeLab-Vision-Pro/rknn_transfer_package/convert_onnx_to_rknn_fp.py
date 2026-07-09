from __future__ import annotations

from pathlib import Path

from rknn.api import RKNN


ROOT = Path(__file__).resolve().parent
ONNX_MODEL = ROOT / "models" / "onnx" / "best.onnx"
OUTPUT_MODEL = ROOT / "models" / "rknn" / "safelab_yolov8n_fire_smoke_v3_fp.rknn"


def main() -> int:
    OUTPUT_MODEL.parent.mkdir(parents=True, exist_ok=True)
    rknn = RKNN(verbose=True)

    # Keep preprocessing consistent with our ONNX reference: RGB input normalized
    # by 255. Disabling quantization avoids compressing 0-1 class scores into the
    # same INT8 output scale as 0-640 box coordinates.
    ret = rknn.config(
        mean_values=[[0, 0, 0]],
        std_values=[[255, 255, 255]],
        target_platform="rk3588",
        quantized_dtype="asymmetric_quantized-8",
    )
    if ret != 0:
        raise RuntimeError(f"rknn.config failed: {ret}")

    ret = rknn.load_onnx(model=str(ONNX_MODEL), inputs=["images"], input_size_list=[[1, 3, 640, 640]])
    if ret != 0:
        raise RuntimeError(f"rknn.load_onnx failed: {ret}")

    ret = rknn.build(do_quantization=False)
    if ret != 0:
        raise RuntimeError(f"rknn.build failed: {ret}")

    ret = rknn.export_rknn(str(OUTPUT_MODEL))
    if ret != 0:
        raise RuntimeError(f"rknn.export_rknn failed: {ret}")

    print(f"RKNN FP model exported: {OUTPUT_MODEL}")
    rknn.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

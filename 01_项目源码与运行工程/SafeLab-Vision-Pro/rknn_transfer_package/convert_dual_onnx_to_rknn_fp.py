from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ModelSpec:
    key: str
    description: str
    onnx_path: Path
    output_path: Path
    labels_path: Path
    output_channels: int

    def output_for(self, *, quantized: bool, output_suffix: str | None = None) -> Path:
        if not quantized:
            return self.output_path
        suffix = output_suffix or "int8"
        return self.output_path.with_name(self.output_path.name.replace("_fp.rknn", f"_{suffix}.rknn"))


MODEL_SPECS = {
    "ppe": ModelSpec(
        key="ppe",
        description="PPE/person YOLOv8n: person, helmet, vest, goggles, gloves",
        onnx_path=ROOT / "models" / "onnx" / "safelab_ppe_rehearsal_hard_v1_yolov8n_640_20e.onnx",
        output_path=ROOT / "models" / "rknn" / "safelab_ppe_rehearsal_hard_v1_yolov8n_640_20e_fp.rknn",
        labels_path=ROOT / "models" / "labels_ppe.txt",
        output_channels=9,
    ),
    "fire_smoke": ModelSpec(
        key="fire_smoke",
        description="Fire/smoke YOLOv8s: fire, smoke",
        onnx_path=ROOT / "models" / "onnx" / "safelab_fire_smoke_rehearsal_hard_v1_yolov8s_640_20e.onnx",
        output_path=ROOT / "models" / "rknn" / "safelab_fire_smoke_rehearsal_hard_v1_yolov8s_640_20e_fp.rknn",
        labels_path=ROOT / "models" / "labels_fire_smoke.txt",
        output_channels=6,
    ),
}


def _load_rknn_class():
    try:
        from rknn.api import RKNN
    except ImportError as exc:
        raise SystemExit(
            "Missing rknn-toolkit2 Python package. Run this script in the Ubuntu VM "
            "environment where `from rknn.api import RKNN` works."
        ) from exc
    return RKNN


def _validate_spec(spec: ModelSpec) -> None:
    missing = [path for path in [spec.onnx_path, spec.labels_path] if not path.exists()]
    if missing:
        missing_text = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Required file(s) missing for {spec.key}:\n{missing_text}")


def convert_model(
    spec: ModelSpec,
    *,
    do_quantization: bool,
    calibration_path: Path,
    quantized_algorithm: str,
    quantized_hybrid_level: int,
    auto_hybrid_cos_thresh: float,
    auto_hybrid: bool,
    output_suffix: str | None,
    verbose: bool,
) -> Path:
    _validate_spec(spec)
    output_path = spec.output_for(quantized=do_quantization, output_suffix=output_suffix)
    if do_quantization and not calibration_path.exists():
        raise FileNotFoundError(f"Calibration dataset missing: {calibration_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    RKNN = _load_rknn_class()
    rknn = RKNN(verbose=verbose)
    try:
        # Match the ONNX reference preprocessing: RGB input normalized by 255.
        # Quantized builds use MMSE/channel calibration and auto-hybrid by default
        # to reduce accuracy loss on YOLOv8 class score outputs.
        ret = rknn.config(
            mean_values=[[0, 0, 0]],
            std_values=[[255, 255, 255]],
            target_platform="rk3588",
            quantized_dtype="w8a8",
            quantized_algorithm=quantized_algorithm,
            quantized_method="channel",
            quantized_hybrid_level=quantized_hybrid_level,
            auto_hybrid_cos_thresh=auto_hybrid_cos_thresh,
        )
        if ret != 0:
            raise RuntimeError(f"{spec.key}: rknn.config failed: {ret}")

        ret = rknn.load_onnx(
            model=str(spec.onnx_path),
            inputs=["images"],
            input_size_list=[[1, 3, 640, 640]],
        )
        if ret != 0:
            raise RuntimeError(f"{spec.key}: rknn.load_onnx failed: {ret}")

        build_kwargs = {"do_quantization": do_quantization}
        if do_quantization:
            build_kwargs.update({"dataset": str(calibration_path), "auto_hybrid": auto_hybrid})
        ret = rknn.build(**build_kwargs)
        if ret != 0:
            raise RuntimeError(f"{spec.key}: rknn.build failed: {ret}")

        ret = rknn.export_rknn(str(output_path))
        if ret != 0:
            raise RuntimeError(f"{spec.key}: rknn.export_rknn failed: {ret}")
    finally:
        rknn.release()

    print(f"{spec.key}: exported {output_path}")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert SafeLab dual-model ONNX files to FP RKNN.")
    parser.add_argument(
        "--model",
        choices=[*MODEL_SPECS.keys(), "all"],
        default="all",
        help="Model to convert. Defaults to all.",
    )
    parser.add_argument(
        "--quantize",
        action="store_true",
        help="Build INT8 RKNN with calibration.txt. Output uses *_int8.rknn and does not overwrite FP.",
    )
    parser.add_argument(
        "--calibration",
        type=Path,
        default=ROOT / "calibration.txt",
        help="Calibration dataset file for INT8 quantization.",
    )
    parser.add_argument(
        "--no-auto-hybrid",
        action="store_true",
        help="Disable RKNN auto-hybrid during INT8 quantization.",
    )
    parser.add_argument(
        "--quantized-algorithm",
        choices=["normal", "mmse", "kl_divergence"],
        default="mmse",
        help="Quantization algorithm. MMSE is more accuracy-oriented but uses much more memory.",
    )
    parser.add_argument(
        "--quantized-hybrid-level",
        type=int,
        default=0,
        help="RKNN quantized_hybrid_level passed to rknn.config. Use 2 for the PPE mixed-precision candidate.",
    )
    parser.add_argument(
        "--auto-hybrid-cos-thresh",
        type=float,
        default=0.98,
        help="RKNN auto_hybrid_cos_thresh passed to rknn.config.",
    )
    parser.add_argument(
        "--output-suffix",
        help="Custom suffix for quantized output. Example: int8_normal_hybrid_level2.",
    )
    parser.add_argument("--quiet", action="store_true", help="Disable verbose RKNN toolkit logging.")
    parser.add_argument("--list-models", action="store_true", help="Print configured models and exit.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.list_models:
        for spec in MODEL_SPECS.values():
            print(f"{spec.key}: {spec.description}")
            print(f"  onnx:   {spec.onnx_path}")
            print(f"  labels: {spec.labels_path}")
            print(f"  output: {spec.output_path}")
            print(f"  int8 output: {spec.output_for(quantized=True)}")
            print(f"  int8 custom suffix example: {spec.output_for(quantized=True, output_suffix='int8_normal_hybrid_level2')}")
            print(f"  output channels: {spec.output_channels}")
        return 0

    selected = MODEL_SPECS.values() if args.model == "all" else [MODEL_SPECS[args.model]]
    for spec in selected:
        convert_model(
            spec,
            do_quantization=args.quantize,
            calibration_path=args.calibration,
            quantized_algorithm=args.quantized_algorithm,
            quantized_hybrid_level=args.quantized_hybrid_level,
            auto_hybrid_cos_thresh=args.auto_hybrid_cos_thresh,
            auto_hybrid=not args.no_auto_hybrid,
            output_suffix=args.output_suffix,
            verbose=not args.quiet,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

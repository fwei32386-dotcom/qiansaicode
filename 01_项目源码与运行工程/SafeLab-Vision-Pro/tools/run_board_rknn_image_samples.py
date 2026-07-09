from __future__ import annotations

import json
import argparse
import time
from pathlib import Path

import paramiko
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = [
    "ppe_dataset_yolov8_frame1087_jpg.rf.7d2f3a0c87e487eacb954d3fbee20682.jpg",
    "ppe_dataset_yolov8_frame1088_jpg.rf.8bdb76c599908bc8e6d80085c4f84ed4.jpg",
    "hardhat_vest_v3_000010.jpg",
    "hardhat_vest_v3_000021.jpg",
    "dfire_kaggle_AoF07718.jpg",
    "dfire_kaggle_AoF07719.jpg",
]


def build_detection_command(
    *,
    binary: str,
    model: str,
    remote_blob: str,
    remote_jsonl: str,
    frame_id: int,
    frame_width: int,
    frame_height: int,
    input_type: str,
    pass_through: bool,
    confidence_threshold: float,
    dump_output_stats: bool,
) -> str:
    command = (
        f"{binary} --model {model} --image {remote_blob} "
        f"--frame-id {frame_id} --frame-width {frame_width} --frame-height {frame_height} "
        f"--input-type {input_type} --conf-threshold {confidence_threshold:g} --output {remote_jsonl}"
    )
    if pass_through:
        command += " --pass-through"
    if dump_output_stats:
        command += " --dump-output-stats"
    return command


def make_letterbox_blob(image_path: Path, output_path: Path, variant: str = "rgb_u8") -> tuple[int, int]:
    image = Image.open(image_path).convert("RGB")
    source_w, source_h = image.size
    scale = min(640 / source_w, 640 / source_h)
    resized_w = max(1, round(source_w * scale))
    resized_h = max(1, round(source_h * scale))
    resized = image.resize((resized_w, resized_h), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (640, 640), (114, 114, 114))
    # Keep the same letterbox geometry that the C++ postprocess assumes.
    canvas.paste(resized, ((640 - resized_w) // 2, (640 - resized_h) // 2))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if variant == "rgb_i8":
        raw = bytes((value - 128) % 256 for value in canvas.tobytes())
    elif variant == "bgr_u8":
        raw = canvas.convert("RGB").tobytes()
        raw = bytes(channel for offset in range(0, len(raw), 3) for channel in (raw[offset + 2], raw[offset + 1], raw[offset]))
    elif variant == "bgr_i8":
        raw_rgb = canvas.convert("RGB").tobytes()
        raw = bytes(
            (channel - 128) % 256
            for offset in range(0, len(raw_rgb), 3)
            for channel in (raw_rgb[offset + 2], raw_rgb[offset + 1], raw_rgb[offset])
        )
    else:
        raw = canvas.tobytes()
    output_path.write_bytes(raw)
    return source_w, source_h


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run several preprocessed image blobs through board RKNN detector.")
    parser.add_argument("--host", default="192.168.0.232")
    parser.add_argument("--username", default="root")
    parser.add_argument("--password", default="root")
    parser.add_argument(
        "--model",
        default="/root/SafeLab-Vision-Pro/models/rknn/safelab_yolov8n_fire_smoke_v3_fp.rknn",
    )
    parser.add_argument("--binary", default="/root/SafeLab-Vision-Pro/rknn_runtime/safelab_rknn_detect")
    parser.add_argument("--debug-variants", action="store_true", help="also run int8/BGR variants for RKNN boundary debugging")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    host = args.host
    username = args.username
    password = args.password
    local_dir = ROOT / "reports" / "rknn_image_samples"
    remote_dir = "/root/SafeLab-Vision-Pro/reports/rknn_image_samples"
    model = args.model
    binary = args.binary
    source_dir = ROOT / "rknn_transfer_package" / "test_images"

    prepared: list[dict[str, object]] = []
    variants = [{"name": "rgb_u8", "blob_variant": "rgb_u8", "input_type": "uint8", "pass_through": False}]
    if args.debug_variants:
        variants.extend(
            [
                {"name": "rgb_i8", "blob_variant": "rgb_i8", "input_type": "int8", "pass_through": False},
                {"name": "rgb_i8_passthrough", "blob_variant": "rgb_i8", "input_type": "int8", "pass_through": True},
                {"name": "bgr_u8", "blob_variant": "bgr_u8", "input_type": "uint8", "pass_through": False},
            ]
        )
    run_index = 0
    for sample_index, name in enumerate(SAMPLES, start=1):
        image_path = source_dir / name
        for variant in variants:
            run_index += 1
            blob_path = local_dir / f"sample_{sample_index:02d}_{variant['name']}.rgb"
            width, height = make_letterbox_blob(image_path, blob_path, str(variant["blob_variant"]))
            prepared.append(
                {
                    "index": run_index,
                    "sample_index": sample_index,
                    "variant": variant["name"],
                    "input_type": variant["input_type"],
                    "pass_through": variant["pass_through"],
                    "name": name,
                    "image_path": str(image_path),
                    "blob_path": str(blob_path),
                    "width": width,
                    "height": height,
                }
            )

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        username=username,
        password=password,
        timeout=10,
        banner_timeout=10,
        auth_timeout=10,
        look_for_keys=False,
        allow_agent=False,
    )
    client.exec_command(f"mkdir -p {remote_dir}")[1].channel.recv_exit_status()
    sftp = client.open_sftp()

    results: list[dict[str, object]] = []
    try:
        for item in prepared:
            remote_blob = f"{remote_dir}/sample_{item['sample_index']:02d}_{item['variant']}.rgb"
            remote_jsonl = f"{remote_dir}/sample_{item['sample_index']:02d}_{item['variant']}.jsonl"
            sftp.put(str(item["blob_path"]), remote_blob)
            command = build_detection_command(
                binary=binary,
                model=model,
                remote_blob=remote_blob,
                remote_jsonl=remote_jsonl,
                frame_id=int(item["index"]),
                frame_width=int(item["width"]),
                frame_height=int(item["height"]),
                input_type=str(item["input_type"]),
                pass_through=bool(item["pass_through"]),
                confidence_threshold=0.25,
                dump_output_stats=True,
            )
            started = time.perf_counter()
            stdin, stdout, stderr = client.exec_command(command, timeout=60)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            code = stdout.channel.recv_exit_status()
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            local_jsonl = local_dir / f"sample_{item['index']:02d}.jsonl"
            detections: list[dict[str, object]] = []
            if code == 0:
                try:
                    sftp.get(remote_jsonl, str(local_jsonl))
                    for line in local_jsonl.read_text(encoding="utf-8").splitlines():
                        if line.strip():
                            detections.append(json.loads(line))
                except OSError:
                    pass
            results.append(
                {
                    **item,
                    "remote_blob": remote_blob,
                    "remote_jsonl": remote_jsonl,
                    "exit_code": code,
                    "elapsed_ms": elapsed_ms,
                    "stdout": out.strip(),
                    "stderr": err.strip(),
                    "detections": detections,
                    "detection_count": len(detections),
                }
            )
    finally:
        sftp.close()
        client.close()

    summary_path = local_dir / "summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": str(summary_path), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

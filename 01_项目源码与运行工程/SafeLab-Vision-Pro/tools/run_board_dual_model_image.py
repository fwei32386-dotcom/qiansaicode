from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import paramiko

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_board_rknn_image_samples import make_letterbox_blob


@dataclass(frozen=True)
class BoardModelSpec:
    key: str
    model: str
    label_preset: str
    confidence_threshold: float


def build_detection_command(
    *,
    binary: str,
    spec: BoardModelSpec,
    remote_blob: str,
    remote_jsonl: str,
    frame_id: int,
    frame_width: int,
    frame_height: int,
    input_type: str,
) -> str:
    return (
        f"{binary} --model {spec.model} --image {remote_blob} "
        f"--frame-id {frame_id} --frame-width {frame_width} --frame-height {frame_height} "
        f"--input-type {input_type} --label-preset {spec.label_preset} "
        f"--conf-threshold {spec.confidence_threshold:g} --output {remote_jsonl}"
    )


def merge_jsonl_files(paths: Iterable[str | Path], output_path: str | Path) -> int:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as out:
        for path_like in paths:
            path = Path(path_like)
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    out.write(line.rstrip() + "\n")
                    count += 1
    return count


def run_board_dual_model_image(
    *,
    image_path: str | Path,
    output_jsonl: str | Path,
    host: str = "192.168.0.232",
    username: str = "root",
    password: str = "root",
    binary: str = "/root/safelab_deploy_current/bin/safelab_rknn_detect",
    ppe_model: str = "/root/safelab_deploy_current/models/safelab_ppe_hybrid_int8.rknn",
    fire_smoke_model: str = "/root/safelab_deploy_current/models/safelab_fire_smoke_fp.rknn",
    remote_dir: str = "/root/safelab_deploy_current/run",
    local_work_dir: str | Path = ROOT / "reports" / "live_pipeline" / "board_dual_model",
    ppe_confidence_threshold: float = 0.25,
    fire_smoke_confidence_threshold: float = 0.25,
    input_type: str = "uint8",
    frame_id: int = 1,
) -> dict[str, object]:
    image = Path(image_path)
    work = Path(local_work_dir)
    work.mkdir(parents=True, exist_ok=True)
    blob_path = work / f"{image.stem}_letterbox.rgb"
    width, height = make_letterbox_blob(image, blob_path, "rgb_u8")

    specs = [
        BoardModelSpec("ppe", ppe_model, "ppe", ppe_confidence_threshold),
        BoardModelSpec("fire_smoke", fire_smoke_model, "fire_smoke", fire_smoke_confidence_threshold),
    ]

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

    local_jsonls: list[Path] = []
    runs: list[dict[str, object]] = []
    try:
        client.exec_command(f"mkdir -p {remote_dir}")[1].channel.recv_exit_status()
        sftp = client.open_sftp()
        try:
            remote_blob = f"{remote_dir}/{image.stem}_letterbox.rgb"
            sftp.put(str(blob_path), remote_blob)
            for spec in specs:
                remote_jsonl = f"{remote_dir}/{image.stem}_{spec.key}.jsonl"
                local_jsonl = work / f"{image.stem}_{spec.key}.jsonl"
                command = build_detection_command(
                    binary=binary,
                    spec=spec,
                    remote_blob=remote_blob,
                    remote_jsonl=remote_jsonl,
                    frame_id=frame_id,
                    frame_width=width,
                    frame_height=height,
                    input_type=input_type,
                )
                started = time.perf_counter()
                _, stdout, stderr = client.exec_command(command, timeout=90)
                out = stdout.read().decode("utf-8", errors="replace")
                err = stderr.read().decode("utf-8", errors="replace")
                code = stdout.channel.recv_exit_status()
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                detections = 0
                if code == 0:
                    try:
                        sftp.get(remote_jsonl, str(local_jsonl))
                    except OSError:
                        local_jsonl.write_text("", encoding="utf-8")
                    detections = sum(1 for line in local_jsonl.read_text(encoding="utf-8").splitlines() if line.strip())
                    local_jsonls.append(local_jsonl)
                runs.append(
                    {
                        "key": spec.key,
                        "command": command,
                        "exit_code": code,
                        "elapsed_ms": elapsed_ms,
                        "detections": detections,
                        "local_jsonl": str(local_jsonl),
                        "remote_jsonl": remote_jsonl,
                        "stdout": out.strip(),
                        "stderr": err.strip(),
                    }
                )
        finally:
            sftp.close()
    finally:
        client.close()

    merged_count = merge_jsonl_files(local_jsonls, output_jsonl)
    summary = {
        "image_path": str(image),
        "output_jsonl": str(Path(output_jsonl)),
        "frame_id": frame_id,
        "frame_width": width,
        "frame_height": height,
        "detections": merged_count,
        "runs": runs,
    }
    summary_path = work / f"{image.stem}_dual_model_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PPE and fire/smoke RKNN models on one image through the RK3588 board.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--output-jsonl", default=str(ROOT / "reports" / "live_pipeline" / "dual_model_detections.jsonl"))
    parser.add_argument("--host", default="192.168.0.232")
    parser.add_argument("--username", default="root")
    parser.add_argument("--password", default="root")
    parser.add_argument("--binary", default="/root/safelab_deploy_current/bin/safelab_rknn_detect")
    parser.add_argument("--ppe-model", default="/root/safelab_deploy_current/models/safelab_ppe_hybrid_int8.rknn")
    parser.add_argument("--fire-smoke-model", default="/root/safelab_deploy_current/models/safelab_fire_smoke_fp.rknn")
    parser.add_argument("--remote-dir", default="/root/safelab_deploy_current/run")
    parser.add_argument("--local-work-dir", default=str(ROOT / "reports" / "live_pipeline" / "board_dual_model"))
    parser.add_argument("--ppe-conf", type=float, default=0.25)
    parser.add_argument("--fire-smoke-conf", type=float, default=0.25)
    parser.add_argument("--frame-id", type=int, default=1)
    args = parser.parse_args()

    summary = run_board_dual_model_image(
        image_path=args.image,
        output_jsonl=args.output_jsonl,
        host=args.host,
        username=args.username,
        password=args.password,
        binary=args.binary,
        ppe_model=args.ppe_model,
        fire_smoke_model=args.fire_smoke_model,
        remote_dir=args.remote_dir,
        local_work_dir=args.local_work_dir,
        ppe_confidence_threshold=args.ppe_conf,
        fire_smoke_confidence_threshold=args.fire_smoke_conf,
        frame_id=args.frame_id,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import os
import posixpath
import shlex
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import paramiko

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.model_detection import build_model_detection_state, save_model_detection
from tools.live_dual_model_sources import ActiveFrameSource, build_active_frame_source
from tools.publish_detection_jsonl_to_dashboard import publish_detection_jsonl, reset_dashboard_events
from tools.run_board_dual_model_image import BoardModelSpec, build_detection_command, merge_jsonl_files, run_board_dual_model_image


def append_jsonl_to_window(
    source_jsonl: str | Path,
    window_jsonl: str | Path,
    *,
    max_frames: int,
) -> dict[str, int]:
    if max_frames < 1:
        raise ValueError("max_frames must be >= 1")

    records = _read_detection_records(Path(window_jsonl))
    records.extend(_read_detection_records(Path(source_jsonl)))

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    frame_order: list[int] = []
    for record in records:
        frame_id = int(record["frame_id"])
        if frame_id not in grouped:
            frame_order.append(frame_id)
        grouped[frame_id].append(record)

    kept_frames = frame_order[-max_frames:]
    output = Path(window_jsonl)
    output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with output.open("w", encoding="utf-8") as f:
        for frame_id in kept_frames:
            for record in grouped[frame_id]:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1
    return {"frames": len(kept_frames), "detections": written}


def reset_detection_window(work_dir: str | Path) -> list[str]:
    work = Path(work_dir)
    removed: list[str] = []
    for target in (work / "detections_window.jsonl",):
        if target.exists():
            target.unlink()
            removed.append(str(target))
    return removed


def annotate_detection_jsonl_source_image(
    detection_jsonl: str | Path,
    frame_path: str | Path,
    *,
    source_type: str | None = None,
    source_key: str | None = None,
) -> int:
    path = Path(detection_jsonl)
    if not path.exists():
        return 0
    records = _read_detection_records(path)
    written = 0
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            record.setdefault("source_image", str(Path(frame_path)))
            if source_type:
                record["source_type"] = source_type
            if source_key:
                record["source_key"] = source_key
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
    return written


def read_model_detection_runtime(path: str | Path) -> tuple[bool, int]:
    state = build_model_detection_state(path)["model_detection"]
    return bool(state["enabled"]), int(state["interval_frames"])


def should_process_camera_frame(
    *,
    current_camera_frame_id: int,
    last_processed_camera_frame_id: int | None,
    interval_frames: int,
) -> bool:
    if interval_frames < 1:
        raise ValueError("interval_frames must be >= 1")
    if last_processed_camera_frame_id is None:
        return True
    if current_camera_frame_id < last_processed_camera_frame_id:
        return True
    return current_camera_frame_id - last_processed_camera_frame_id >= interval_frames


def fetch_camera_status(status_url: str, timeout_seconds: float = 2.0) -> dict[str, Any]:
    with urlopen(status_url, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_frame(frame_url: str, output_path: str | Path, timeout_seconds: float = 5.0) -> dict[str, object]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(frame_url, timeout=timeout_seconds) as response:
        body = response.read()
    output.write_bytes(body)
    return {"frame_path": str(output), "bytes": len(body)}


class LocalVideoFrameReader:
    def __init__(self, source: ActiveFrameSource) -> None:
        if source.path is None:
            raise ValueError("local video source is missing path")
        if not source.path.exists():
            raise FileNotFoundError(str(source.path))
        import cv2  # type: ignore[import-not-found]

        self._cv2 = cv2
        self.source = source
        self._capture = cv2.VideoCapture(str(source.path))
        if not self._capture.isOpened():
            raise RuntimeError(f"failed to open local video: {source.path}")
        self._frame_id = 0

    def close(self) -> None:
        self._capture.release()

    def capture_interval_frame(self, *, interval_frames: int, output_dir: str | Path) -> dict[str, Any]:
        if interval_frames < 1:
            raise ValueError("interval_frames must be >= 1")
        frame = None
        reads = interval_frames if self._frame_id else 1
        for _ in range(reads):
            ok, frame = self._capture.read()
            if not ok:
                self._capture.set(self._cv2.CAP_PROP_POS_FRAMES, 0)
                self._frame_id = 0
                ok, frame = self._capture.read()
                if not ok:
                    raise RuntimeError(f"local video has no readable frames: {self.source.path}")
            self._frame_id += 1
        output = Path(output_dir) / f"{self.source.key}_{self._frame_id:06d}.jpg"
        output.parent.mkdir(parents=True, exist_ok=True)
        if not _write_jpeg_frame(self._cv2, output, frame):
            raise RuntimeError(f"failed to write local video frame: {output}")
        height, width = frame.shape[:2]
        return {
            "frame_path": str(output),
            "frame_id": self._frame_id,
            "width": int(width),
            "height": int(height),
            "source_path": str(self.source.path),
        }


def build_board_file_local_fallback_source(source: ActiveFrameSource) -> ActiveFrameSource:
    if source.path is None:
        raise ValueError("board_file source has no local fallback path")
    return ActiveFrameSource(
        key=source.key,
        source_type="file",
        label=source.label,
        path=source.path,
        source_name=source.source_name,
        fps=source.fps,
        width=source.width,
        height=source.height,
        media_type=source.media_type,
    )


def _write_jpeg_frame(cv2_module: Any, output_path: str | Path, frame: Any) -> bool:
    # OpenCV's imwrite can mangle non-ASCII Windows paths; Python writes the bytes safely.
    ok, encoded = cv2_module.imencode(".jpg", frame)
    if not ok:
        return False
    Path(output_path).write_bytes(encoded.tobytes())
    return True


def run_captured_frame_once(
    *,
    frame_path: str | Path,
    detection_frame_id: int,
    frame_id: int,
    source_key: str,
    source_type: str,
    work_dir: str | Path,
    events_dir: str | Path,
    reports_dir: str | Path,
    host: str,
    username: str,
    password: str,
    ppe_confidence_threshold: float,
    fire_smoke_confidence_threshold: float,
    max_window_frames: int,
    binary: str = "/root/safelab_deploy_current/bin/safelab_rknn_detect",
    ppe_model: str = "/root/safelab_deploy_current/models/safelab_ppe_hybrid_int8.rknn",
    fire_smoke_model: str = "/root/safelab_deploy_current/models/safelab_fire_smoke_fp.rknn",
    remote_dir: str = "/root/safelab_deploy_current/run",
    input_type: str = "uint8",
    extra_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    work = Path(work_dir)
    reports = Path(reports_dir)
    current_jsonl = work / "detections" / f"frame_{detection_frame_id:06d}.jsonl"
    window_jsonl = work / "detections_window.jsonl"

    detect_summary = run_board_dual_model_image(
        image_path=frame_path,
        output_jsonl=current_jsonl,
        host=host,
        username=username,
        password=password,
        binary=binary,
        ppe_model=ppe_model,
        fire_smoke_model=fire_smoke_model,
        remote_dir=remote_dir,
        local_work_dir=work / "board_dual_model",
        ppe_confidence_threshold=ppe_confidence_threshold,
        fire_smoke_confidence_threshold=fire_smoke_confidence_threshold,
        input_type=input_type,
        frame_id=detection_frame_id,
    )
    detections = int(detect_summary["detections"])
    if detections > 0:
        annotate_detection_jsonl_source_image(
            current_jsonl,
            frame_path,
            source_type=source_type,
            source_key=source_key,
        )
        window_summary = append_jsonl_to_window(current_jsonl, window_jsonl, max_frames=max_window_frames)
        publish_summary = publish_detection_jsonl(
            window_jsonl,
            events_dir=events_dir,
            reports_dir=reports,
            reset=True,
            repeat_frames=1,
        )
    else:
        window_jsonl.parent.mkdir(parents=True, exist_ok=True)
        window_jsonl.touch(exist_ok=True)
        publish_summary = publish_detection_jsonl(
            window_jsonl,
            events_dir=events_dir,
            reports_dir=reports,
            reset=True,
            repeat_frames=1,
        )
        window_summary = summarize_detection_window(window_jsonl)

    summary = {
        "enabled": True,
        "frame_id": frame_id,
        "detection_frame_id": detection_frame_id,
        "source_key": source_key,
        "source_type": source_type,
        "frame": {"frame_path": str(Path(frame_path)), "bytes": Path(frame_path).stat().st_size},
        "detections": detections,
        "window": window_summary,
        "published": publish_summary,
        "ppe_confidence_threshold": ppe_confidence_threshold,
        "fire_smoke_confidence_threshold": fire_smoke_confidence_threshold,
        "updated_at": time.time(),
    }
    if extra_summary:
        summary.update(extra_summary)
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "bridge_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def run_board_file_frame_once(
    *,
    source: ActiveFrameSource,
    detection_frame_id: int,
    frame_id: int,
    work_dir: str | Path,
    events_dir: str | Path,
    reports_dir: str | Path,
    host: str,
    username: str,
    password: str,
    binary: str,
    ppe_model: str,
    fire_smoke_model: str,
    remote_dir: str,
    ppe_confidence_threshold: float,
    fire_smoke_confidence_threshold: float,
    max_window_frames: int,
    input_type: str = "uint8",
) -> dict[str, Any]:
    if not source.board_path:
        raise ValueError("board_file source is missing board_path")
    work = Path(work_dir)
    reports = Path(reports_dir)
    current_jsonl = work / "detections" / f"frame_{detection_frame_id:06d}.jsonl"
    window_jsonl = work / "detections_window.jsonl"
    frame_path = work / "frames" / f"{source.key}_{detection_frame_id:06d}.jpg"
    frame_path.parent.mkdir(parents=True, exist_ok=True)

    remote_prefix = f"{remote_dir.rstrip('/')}/{source.key}_{detection_frame_id:06d}"
    remote_blob = f"{remote_prefix}.rgb"
    remote_preview = f"{remote_prefix}.jpg"
    frame_width = int(source.width or 640)
    frame_height = int(source.height or 640)
    frame_index = max(0, detection_frame_id - 1)
    specs = [
        BoardModelSpec("ppe", ppe_model, "ppe", ppe_confidence_threshold),
        BoardModelSpec("fire_smoke", fire_smoke_model, "fire_smoke", fire_smoke_confidence_threshold),
    ]

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    local_jsonls: list[Path] = []
    runs: list[dict[str, Any]] = []
    try:
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
        _run_board_command(client, f"mkdir -p {shlex.quote(remote_dir)} {shlex.quote(posixpath.dirname(remote_preview))}")
        _run_board_command(
            client,
            _build_board_media_extract_command(
                media_path=source.board_path,
                media_type=source.media_type or "video",
                frame_index=frame_index,
                remote_blob=remote_blob,
                remote_preview=remote_preview,
            ),
            timeout=60,
        )
        sftp = client.open_sftp()
        try:
            try:
                sftp.get(remote_preview, str(frame_path))
            except OSError:
                frame_path.write_bytes(b"")
            for spec in specs:
                remote_jsonl = f"{remote_prefix}_{spec.key}.jsonl"
                local_jsonl = work / "detections" / f"frame_{detection_frame_id:06d}_{spec.key}.jsonl"
                local_jsonl.parent.mkdir(parents=True, exist_ok=True)
                command = build_detection_command(
                    binary=binary,
                    spec=spec,
                    remote_blob=remote_blob,
                    remote_jsonl=remote_jsonl,
                    frame_id=detection_frame_id,
                    frame_width=frame_width,
                    frame_height=frame_height,
                    input_type=input_type,
                )
                started = time.perf_counter()
                code, out, err = _run_board_command(client, command, timeout=90, check=False)
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
                        "stdout": out,
                        "stderr": err,
                    }
                )
        finally:
            sftp.close()
    finally:
        client.close()

    detections = merge_jsonl_files(local_jsonls, current_jsonl)
    if detections > 0:
        annotate_detection_jsonl_source_image(
            current_jsonl,
            frame_path,
            source_type="board_file",
            source_key=source.key,
        )
        window_summary = append_jsonl_to_window(current_jsonl, window_jsonl, max_frames=max_window_frames)
        publish_summary = publish_detection_jsonl(
            window_jsonl,
            events_dir=events_dir,
            reports_dir=reports,
            reset=True,
            repeat_frames=1,
        )
    else:
        window_jsonl.parent.mkdir(parents=True, exist_ok=True)
        window_jsonl.touch(exist_ok=True)
        publish_summary = publish_detection_jsonl(
            window_jsonl,
            events_dir=events_dir,
            reports_dir=reports,
            reset=True,
            repeat_frames=1,
        )
        window_summary = summarize_detection_window(window_jsonl)

    summary = {
        "enabled": True,
        "frame_id": frame_id,
        "detection_frame_id": detection_frame_id,
        "source_key": source.key,
        "source_type": source.source_type,
        "frame": {"frame_path": str(frame_path), "bytes": frame_path.stat().st_size if frame_path.exists() else 0},
        "detections": detections,
        "window": window_summary,
        "published": publish_summary,
        "ppe_confidence_threshold": ppe_confidence_threshold,
        "fire_smoke_confidence_threshold": fire_smoke_confidence_threshold,
        "updated_at": time.time(),
        "board_media": {
            "board_path": source.board_path,
            "media_type": source.media_type or "video",
            "frame_id": detection_frame_id,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "remote_blob": remote_blob,
            "remote_preview": remote_preview,
        },
        "runs": runs,
    }
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "bridge_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _build_board_media_extract_command(
    *,
    media_path: str,
    media_type: str,
    frame_index: int,
    remote_blob: str,
    remote_preview: str,
) -> str:
    if media_type == "image":
        return (
            f"cp {shlex.quote(media_path)} {shlex.quote(remote_preview)}"
            " && "
            "gst-launch-1.0 -q "
            f"filesrc location={shlex.quote(remote_preview)} ! jpegdec ! videoconvert ! videoscale ! "
            f"video/x-raw,format=RGB,width=640,height=640 ! filesink location={shlex.quote(remote_blob)} sync=false"
        )
    select_filter = f"select=eq(n\\,{frame_index})"
    # The board ffmpeg build is tiny and lacks scale/pad filters, so ffmpeg only
    # extracts one JPEG frame; GStreamer then converts that JPEG into RKNN RGB.
    remote_frame = f"{posixpath.splitext(remote_preview)[0]}_extract.jpg"
    return (
        f"rm -f {shlex.quote(remote_frame)}"
        " && ("
        "ffmpeg -y -v error "
        f"-i {shlex.quote(media_path)} -vf {shlex.quote(select_filter)} -frames:v 1 {shlex.quote(remote_frame)}"
        "; "
        f"test -s {shlex.quote(remote_frame)} || "
        f"ffmpeg -y -v error -i {shlex.quote(media_path)} -frames:v 1 {shlex.quote(remote_frame)}"
        ") && "
        f"cp {shlex.quote(remote_frame)} {shlex.quote(remote_preview)}"
        " && "
        "gst-launch-1.0 -q "
        f"filesrc location={shlex.quote(remote_frame)} ! jpegdec ! videoconvert ! videoscale ! "
        f"video/x-raw,format=RGB,width=640,height=640 ! filesink location={shlex.quote(remote_blob)} sync=false"
    )


def _run_board_command(
    client: paramiko.SSHClient,
    command: str,
    *,
    timeout: int = 30,
    check: bool = True,
) -> tuple[int, str, str]:
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    if check and code != 0:
        raise RuntimeError(f"board command failed ({code}): {err or out or command}")
    return code, out, err


def summarize_detection_window(window_jsonl: str | Path) -> dict[str, int]:
    records = _read_detection_records(Path(window_jsonl))
    frame_ids = {int(record["frame_id"]) for record in records}
    return {"frames": len(frame_ids), "detections": len(records)}


def run_bridge_once(
    *,
    frame_url: str,
    status_url: str,
    frame_id: int,
    work_dir: str | Path,
    model_detection_path: str | Path,
    events_dir: str | Path,
    reports_dir: str | Path,
    host: str,
    username: str,
    password: str,
    ppe_confidence_threshold: float,
    fire_smoke_confidence_threshold: float,
    max_window_frames: int,
    camera_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enabled, interval_frames = read_model_detection_runtime(model_detection_path)
    camera_status = camera_status or fetch_camera_status(status_url)
    camera_frame_id = int(camera_status.get("frame_id", frame_id) or frame_id)
    work = Path(work_dir)
    frame_path = work / "frames" / f"frame_{camera_frame_id:06d}.jpg"

    if not enabled:
        reset_dashboard_events(events_dir)
        return {
            "enabled": False,
            "interval_frames": interval_frames,
            "frame_id": frame_id,
            "camera_frame_id": camera_frame_id,
            "detections": 0,
            "message": "model detection disabled",
        }

    fetch_summary = fetch_frame(frame_url, frame_path)
    return run_captured_frame_once(
        frame_path=frame_path,
        detection_frame_id=camera_frame_id,
        frame_id=frame_id,
        source_key="camera_ov13855",
        source_type="camera",
        work_dir=work_dir,
        events_dir=events_dir,
        reports_dir=reports_dir,
        host=host,
        username=username,
        password=password,
        ppe_confidence_threshold=ppe_confidence_threshold,
        fire_smoke_confidence_threshold=fire_smoke_confidence_threshold,
        max_window_frames=max_window_frames,
        extra_summary={
            "interval_frames": interval_frames,
            "camera_frame_id": camera_frame_id,
            "camera_status": {
                "frame_id": camera_frame_id,
                "estimated_fps": camera_status.get("estimated_fps"),
                "last_frame_age_seconds": camera_status.get("last_frame_age_seconds"),
            },
            "frame": fetch_summary,
        },
    )


def _read_detection_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid detection JSONL") from exc
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge live camera frames into the RK3588 dual-model detection dashboard.")
    parser.add_argument("--frame-url", default="http://127.0.0.1:8090/frame.jpg")
    parser.add_argument("--status-url", default="http://127.0.0.1:8090/status")
    parser.add_argument("--video-config", default=str(ROOT / "configs" / "video_config.yaml"))
    parser.add_argument("--input-source", default=str(ROOT / "data" / "runtime" / "input_source.json"))
    parser.add_argument("--model-detection", default=str(ROOT / "data" / "runtime" / "model_detection.json"))
    parser.add_argument("--events-dir", default=str(ROOT / "data" / "events"))
    parser.add_argument("--reports-dir", default=str(ROOT / "reports" / "live_pipeline" / "live_dual_model"))
    parser.add_argument("--work-dir", default=str(ROOT / "reports" / "live_pipeline" / "live_dual_model_work"))
    parser.add_argument("--host", default=os.getenv("SAFELAB_BOARD_HOST", "192.168.0.232"))
    parser.add_argument("--username", default=os.getenv("SAFELAB_BOARD_USER", "root"))
    parser.add_argument("--password", default=os.getenv("SAFELAB_BOARD_PASSWORD", "root"))
    parser.add_argument("--binary", default="/root/safelab_deploy_current/bin/safelab_rknn_detect")
    parser.add_argument("--ppe-model", default="/root/safelab_deploy_current/models/safelab_ppe_hybrid_int8.rknn")
    parser.add_argument("--fire-smoke-model", default="/root/safelab_deploy_current/models/safelab_fire_smoke_fp.rknn")
    parser.add_argument("--remote-dir", default="/root/safelab_deploy_current/run")
    parser.add_argument("--ppe-conf", type=float, default=0.20)
    parser.add_argument("--fire-smoke-conf", type=float, default=0.45)
    parser.add_argument("--max-window-frames", type=int, default=3)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-iterations", type=int, default=0)
    parser.add_argument("--ensure-enabled", action="store_true")
    args = parser.parse_args()

    if args.ensure_enabled:
        save_model_detection(True, 75, args.model_detection)

    frame_id = 1
    iterations = 0
    last_processed_camera_frame_id: int | None = None
    active_source_key: str | None = None
    local_reader: LocalVideoFrameReader | None = None
    board_file_frame_id = 0
    while True:
        camera_status: dict[str, Any] | None = None
        try:
            source = build_active_frame_source(
                video_config_path=args.video_config,
                input_source_path=args.input_source,
                camera_frame_url=args.frame_url,
                camera_status_url=args.status_url,
            )
            if source.key != active_source_key:
                if local_reader is not None:
                    local_reader.close()
                    local_reader = None
                last_processed_camera_frame_id = None
                board_file_frame_id = 0
                reset_dashboard_events(args.events_dir)
                reset_detection_window(args.work_dir)
                active_source_key = source.key

            enabled, interval_frames = read_model_detection_runtime(args.model_detection)
            if not enabled:
                reset_dashboard_events(args.events_dir)
                summary = {
                    "enabled": False,
                    "interval_frames": interval_frames,
                    "frame_id": frame_id,
                    "source_key": source.key,
                    "source_type": source.source_type,
                    "detections": 0,
                    "message": "model detection disabled",
                    "updated_at": time.time(),
                }
            elif source.source_type == "camera":
                while not args.once:
                    refreshed = build_active_frame_source(
                        video_config_path=args.video_config,
                        input_source_path=args.input_source,
                        camera_frame_url=args.frame_url,
                        camera_status_url=args.status_url,
                    )
                    if refreshed.key != source.key:
                        source = refreshed
                        break
                    _, interval_frames = read_model_detection_runtime(args.model_detection)
                    camera_status = fetch_camera_status(args.status_url)
                    current_camera_frame_id = int(camera_status.get("frame_id", 0) or 0)
                    if should_process_camera_frame(
                        current_camera_frame_id=current_camera_frame_id,
                        last_processed_camera_frame_id=last_processed_camera_frame_id,
                        interval_frames=interval_frames,
                    ):
                        break
                    time.sleep(0.2)
                if source.source_type != "camera":
                    continue
                summary = run_bridge_once(
                    frame_url=args.frame_url,
                    status_url=args.status_url,
                    frame_id=frame_id,
                    work_dir=args.work_dir,
                    model_detection_path=args.model_detection,
                    events_dir=args.events_dir,
                    reports_dir=args.reports_dir,
                    host=args.host,
                    username=args.username,
                    password=args.password,
                    ppe_confidence_threshold=args.ppe_conf,
                    fire_smoke_confidence_threshold=args.fire_smoke_conf,
                    max_window_frames=args.max_window_frames,
                    camera_status=camera_status,
                )
            elif source.source_type == "file":
                if local_reader is None:
                    local_reader = LocalVideoFrameReader(source)
                captured = local_reader.capture_interval_frame(
                    interval_frames=interval_frames,
                    output_dir=Path(args.work_dir) / "frames",
                )
                summary = run_captured_frame_once(
                    frame_path=captured["frame_path"],
                    detection_frame_id=int(captured["frame_id"]),
                    frame_id=frame_id,
                    source_key=source.key,
                    source_type=source.source_type,
                    work_dir=args.work_dir,
                    events_dir=args.events_dir,
                    reports_dir=args.reports_dir,
                    host=args.host,
                    username=args.username,
                    password=args.password,
                    ppe_confidence_threshold=args.ppe_conf,
                    fire_smoke_confidence_threshold=args.fire_smoke_conf,
                    max_window_frames=args.max_window_frames,
                    extra_summary={"interval_frames": interval_frames, "local_video": captured},
                )
            else:
                board_file_frame_id += max(1, interval_frames)
                try:
                    summary = run_board_file_frame_once(
                        source=source,
                        detection_frame_id=board_file_frame_id,
                        frame_id=frame_id,
                        work_dir=args.work_dir,
                        events_dir=args.events_dir,
                        reports_dir=args.reports_dir,
                        host=args.host,
                        username=args.username,
                        password=args.password,
                        binary=args.binary,
                        ppe_model=args.ppe_model,
                        fire_smoke_model=args.fire_smoke_model,
                        remote_dir=args.remote_dir,
                        ppe_confidence_threshold=args.ppe_conf,
                        fire_smoke_confidence_threshold=args.fire_smoke_conf,
                        max_window_frames=args.max_window_frames,
                        input_type="uint8",
                    )
                except RuntimeError as exc:
                    fallback_source = build_board_file_local_fallback_source(source)
                    if local_reader is None or local_reader.source.path != fallback_source.path:
                        if local_reader is not None:
                            local_reader.close()
                        local_reader = LocalVideoFrameReader(fallback_source)
                    captured = local_reader.capture_interval_frame(
                        interval_frames=interval_frames,
                        output_dir=Path(args.work_dir) / "frames",
                    )
                    summary = run_captured_frame_once(
                        frame_path=captured["frame_path"],
                        detection_frame_id=int(captured["frame_id"]),
                        frame_id=frame_id,
                        source_key=source.key,
                        source_type=source.source_type,
                        work_dir=args.work_dir,
                        events_dir=args.events_dir,
                        reports_dir=args.reports_dir,
                        host=args.host,
                        username=args.username,
                        password=args.password,
                        ppe_confidence_threshold=args.ppe_conf,
                        fire_smoke_confidence_threshold=args.fire_smoke_conf,
                        max_window_frames=args.max_window_frames,
                        binary=args.binary,
                        ppe_model=args.ppe_model,
                        fire_smoke_model=args.fire_smoke_model,
                        remote_dir=args.remote_dir,
                        input_type="uint8",
                        extra_summary={
                            "interval_frames": interval_frames,
                            "local_video": captured,
                            "board_extract_error": str(exc),
                            "board_media": {
                                "board_path": source.board_path,
                                "media_type": source.media_type or "video",
                                "fallback": "local_frame_extract",
                            },
                        },
                    )
        except Exception as exc:
            summary = {"enabled": True, "frame_id": frame_id, "error": str(exc), "updated_at": time.time()}
            reports = Path(args.reports_dir)
            reports.mkdir(parents=True, exist_ok=True)
            (reports / "bridge_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(summary, ensure_ascii=False), flush=True)
            if args.once:
                return 1
        else:
            print(json.dumps(summary, ensure_ascii=False), flush=True)
            if summary.get("enabled") and "camera_frame_id" in summary:
                last_processed_camera_frame_id = int(summary["camera_frame_id"])

        frame_id += 1
        iterations += 1
        if args.once or (args.max_iterations and iterations >= args.max_iterations):
            break

        enabled, _ = read_model_detection_runtime(args.model_detection)
        if not enabled:
            time.sleep(1.0)
        elif local_reader is not None or active_source_key == "board_file_demo":
            time.sleep(0.1)
    if local_reader is not None:
        local_reader.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

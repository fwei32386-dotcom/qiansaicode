# Camera DDR Inference Pipeline

This project should not save every camera frame before inference.

The intended board-side path is:

```text
OV13855 / RKISP
-> capture worker
-> VideoFrame.frame in DDR memory
-> LatestFrameBuffer keeps only the newest frame
-> YOLO/RKNN detector reads the newest frame
-> Detection objects
-> RuleDslEngine / PPE association / temporal state
-> RiskEvent / AlarmAction / evidence logs
```

## Runtime Policy

- Camera frames are runtime memory data, not JSON evidence.
- `VideoFrame.frame` holds the decoded frame object or board memory-backed image.
- `VideoFrame.to_dict()` removes `frame`, so logs keep metadata only.
- `LatestFrameBuffer` stores one newest `VideoFrame`.
- If capture is faster than inference, old frames are overwritten.
- The detector must prefer the latest frame over queued old frames, because low latency matters more than processing every frame.
- Snapshots are saved only when a confirmed `RiskEvent` requires evidence.

## Why This Matters

For safety detection, delayed alarms are worse than skipped normal frames.

If the camera runs at 30 FPS and RKNN inference can only process 8-15 FPS, a normal FIFO queue would build latency. After several seconds, the system would be detecting old images. The latest-frame buffer avoids this by dropping stale frames.

## Mapping To RKNN

The future RKNN detector should implement the existing detector contract:

```text
detect(frame: VideoFrame) -> list[Detection]
```

The detector receives `frame.frame`, runs preprocessing, RKNN inference, and postprocessing, then returns normalized `Detection` records using the stable 7-class labels:

```text
person, helmet, vest, goggles, gloves, fire, smoke
```

The rule system does not care whether detections came from mock JSON, ONNX, or RKNN, as long as the `Detection` interface is respected.

## Verification

Run:

```bash
python tools/benchmark_latest_frame_buffer.py
```

Expected report:

```text
reports/latest_frame_buffer_summary.json
```

The report should show:

```text
frame_storage_policy = in_memory_only
captures_written_to_disk = 0
old_frames_dropped = true
detector_uses_newest_frame = true
```

## No-Camera Board Mode

The board can still be validated when the physical OV13855 module is not
connected. In this mode:

```sh
sh tools/board_ops.sh
```

continues to check the project layout, rule contract, RKNN model/runtime probe,
logs, and reports. OV13855 sensor-id or raw-capture failures are non-blocking by
default because the rule pipeline can still run with mock/file detections.

When the camera is physically connected, switch to strict camera validation:

```sh
SAFELAB_CAMERA_REQUIRED=1 sh tools/board_ov13855_diagnose.sh
sh tools/board_camera_preview.sh snapshot
```

Only after strict camera diagnosis passes should real camera frames be wired
into the RKNN detector path.

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from actuator.alarm_manager import AlarmManager
from ai_engine.roi_manager import ROIManager
from evidence.event_logger import EventLogger
from runtime.async_event_bus import AsyncEventBus
from runtime.frame_scheduler import FrameScheduler, RuntimeState
from runtime.interfaces import Detection, RiskEvent, VideoFrame
from runtime.latest_frame_buffer import LatestFrameBuffer
from runtime.pipeline_profiler import PipelineProfiler
from runtime.watchdog import Watchdog
from safety_brain.rule_dsl_engine import RuleDslEngine
from safety_brain.ppe_association import associate_ppe
from video.video_source import MockVideoSource, VideoSource, VideoSourceConfig
from safety_brain.scene_graph import SceneGraph
from safety_brain.track_manager import TrackManager


class Detector(Protocol):
    def detect(self, frame: VideoFrame) -> list[Detection]:
        ...


@dataclass(frozen=True)
class MainLoopResult:
    frames_read: int
    frames_processed: int
    frames_skipped: int
    events: int
    actions: int
    dropped_frames: int
    bus_dropped: int
    watchdog_healthy: bool
    profiler: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "frames_read": self.frames_read,
            "frames_processed": self.frames_processed,
            "frames_skipped": self.frames_skipped,
            "events": self.events,
            "actions": self.actions,
            "dropped_frames": self.dropped_frames,
            "bus_dropped": self.bus_dropped,
            "watchdog_healthy": self.watchdog_healthy,
            "profiler": self.profiler,
        }


class MockRuntimeDetector:
    def detect(self, frame: VideoFrame) -> list[Detection]:
        if frame.frame_id == 5:
            return [
                _detection(frame, "person", [940, 140, 1160, 690], 0.95),
                _detection(frame, "helmet", [990, 145, 1090, 245], 0.87),
                _detection(frame, "vest", [980, 330, 1125, 590], 0.89),
                _detection(frame, "gloves", [1115, 435, 1190, 525], 0.81),
            ]
        if frame.frame_id == 6:
            return [
                _detection(frame, "person", [520, 740, 760, 1020], 0.94),
                _detection(frame, "helmet", [585, 745, 695, 815], 0.86),
                _detection(frame, "vest", [570, 835, 720, 965], 0.90),
                _detection(frame, "goggles", [595, 775, 690, 820], 0.82),
            ]
        return []


class RuntimeMainLoop:
    def __init__(
        self,
        source: VideoSource,
        detector: Detector,
        output_dir: str | Path = "data/events",
        scheduler: FrameScheduler | None = None,
        event_bus: AsyncEventBus | None = None,
    ) -> None:
        self.source = source
        self.detector = detector
        self.buffer = LatestFrameBuffer()
        self.scheduler = scheduler or FrameScheduler(normal_interval=5, suspicious_interval=1, alarmed_interval=2)
        self.event_bus = event_bus or AsyncEventBus(maxsize=8)
        self.profiler = PipelineProfiler()
        self.watchdog = Watchdog(timeout_ms=1000.0)
        self.rule_engine = RuleDslEngine.from_files()
        self.track_manager = TrackManager(SceneGraph.from_json("configs/semantic_map.json"))
        self.roi_manager = ROIManager()
        self.alarm_manager = AlarmManager()
        self.logger = EventLogger(output_dir)
        self.runtime_state: RuntimeState = "normal"

    def run(self, max_frames: int = 12) -> MainLoopResult:
        frames_read = 0
        frames_processed = 0
        frames_skipped = 0
        events_count = 0
        actions_count = 0

        while frames_read < max_frames:
            with self.profiler.stage("read_frame_ms"):
                frame = self.source.read()
            if frame is None:
                break
            frames_read += 1
            self.watchdog.heartbeat("capture_worker")
            self.buffer.put(frame)

            latest = self.buffer.get_latest()
            if latest is None:
                continue

            decision = self.scheduler.decide(latest, self.runtime_state, has_roi=self.runtime_state != "normal")
            if not decision.should_process:
                frames_skipped += 1
                continue

            frames_processed += 1
            self.watchdog.heartbeat("inference_worker")
            with self.profiler.stage("detect_ms"):
                detections = self.detector.detect(latest)
            with self.profiler.stage("rule_eval_ms"):
                events = self.rule_engine.evaluate(detections)
            with self.profiler.stage("track_update_ms"):
                tracks = self.track_manager.update(associate_ppe(detections), timestamp=latest.timestamp)
            with self.profiler.stage("roi_update_ms"):
                rois = self.roi_manager.build_rois_from_tracks(latest, tracks)
                self.roi_manager.summarize(latest, rois)
            if events:
                self.runtime_state = "suspicious"

            with self.profiler.stage("action_build_ms"):
                actions = [self.alarm_manager.build_action(event) for event in events]

            self.watchdog.heartbeat("event_worker")
            for event in events:
                self.event_bus.publish("risk_event", event.to_dict())
                self.logger.log_event(event.to_dict())
            for action in actions:
                self.event_bus.publish("alarm_action", action.to_dict())
                self.logger.log_action(action.to_dict())

            events_count += len(events)
            actions_count += len(actions)

        self.event_bus.drain()
        bus_stats = self.event_bus.stats()
        watchdog_summary = self.watchdog.summary(
            ["capture_worker", "inference_worker", "event_worker"],
        )
        return MainLoopResult(
            frames_read=frames_read,
            frames_processed=frames_processed,
            frames_skipped=frames_skipped,
            events=events_count,
            actions=actions_count,
            dropped_frames=self.buffer.dropped_count,
            bus_dropped=bus_stats.dropped_count,
            watchdog_healthy=bool(watchdog_summary["healthy"]),
            profiler=self.profiler.summary(),
        )


def run_mock_main_loop(
    frame_count: int = 8,
    output_dir: str | Path = "data/events",
    summary_path: str | Path = "reports/main_loop_summary.json",
) -> MainLoopResult:
    source = MockVideoSource(
        VideoSourceConfig(
            source_type="mock",
            source_name="mock_main_loop",
            width=1280,
            height=720,
        ),
        frame_count=frame_count,
    )
    loop = RuntimeMainLoop(source=source, detector=MockRuntimeDetector(), output_dir=output_dir)
    result = loop.run(max_frames=frame_count)
    output = Path(summary_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _detection(frame: VideoFrame, class_name: str, bbox: list[int], confidence: float) -> Detection:
    x1, y1, x2, y2 = bbox
    return Detection(
        frame_id=frame.frame_id,
        source_type=frame.source_type,
        class_name=class_name,  # type: ignore[arg-type]
        confidence=confidence,
        bbox=bbox,
        center=[(x1 + x2) // 2, (y1 + y2) // 2],
        area=max(x2 - x1, 0) * max(y2 - y1, 0),
        model_name="mock_runtime_detector",
        infer_time_ms=0.1,
    )

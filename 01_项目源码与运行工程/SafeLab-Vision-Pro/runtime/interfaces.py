from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


ClassName = Literal["person", "helmet", "vest", "goggles", "gloves", "fire", "smoke"]
SourceType = Literal["camera", "hdmi", "file", "mock"]
RiskLevel = Literal["normal", "notice", "warning", "high", "emergency"]
EventType = Literal["ppe_violation", "forbidden_intrusion", "smoke", "fire"]
TrackState = Literal["normal", "suspicious", "confirmed", "alarmed", "recovered", "closed"]
FallbackMode = Literal["none", "shell_only", "mock_detection", "shell_only+mock_detection"]


@dataclass(frozen=True)
class VideoFrame:
    frame_id: int
    source_type: SourceType
    timestamp: float
    width: int
    height: int
    source_name: str
    frame: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("frame", None)
        return payload


@dataclass(frozen=True)
class Detection:
    frame_id: int
    source_type: SourceType
    class_name: ClassName
    confidence: float
    bbox: list[int]
    center: list[int]
    area: int
    model_name: str
    infer_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PersonTrack:
    track_id: int
    frame_id: int
    bbox: list[int]
    zone_id: str | None
    has_helmet: bool
    has_vest: bool
    has_goggles: bool
    has_gloves: bool
    ppe_status: str
    risk_state: TrackState
    hit_count: int
    miss_count: int
    last_update_ts: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ROIRegion:
    roi_id: str
    frame_id: int
    bbox: list[int]
    source_bbox: list[int]
    frame_width: int
    frame_height: int
    reason: str
    margin_ratio: float
    source_track_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FireSmokeTrack:
    track_id: int
    frame_id: int
    class_name: Literal["fire", "smoke"]
    bbox: list[int]
    confidence: float
    appear_count: int
    area_history: list[int]
    state: TrackState
    risk_level: RiskLevel

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RiskEvent:
    event_id: str
    frame_id: int
    source_type: SourceType
    event_type: EventType
    risk_score: int
    risk_level: RiskLevel
    reasons: list[str]
    bbox: list[int]
    need_alarm: bool
    need_snapshot: bool
    need_log: bool
    timestamp: float
    rule_id: str | None = None
    action_hint: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TimelineEvent:
    event_id: str
    stage: Literal["suspicious", "confirmed", "alarmed", "recovered", "closed"]
    timestamp: float
    detail: str
    frame_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AlarmAction:
    event_id: str
    voice_text: str
    led_color: str
    buzzer: bool
    relay: bool
    snapshot: bool
    log: bool
    cooldown_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HealthStatus:
    camera: str
    hdmi_capture: str
    rknn_model: str
    database: str
    gpio: str
    audio: str
    storage_free_mb: int | str
    fallback_mode: FallbackMode
    python: str | None = None
    v4l2_ctl: str | None = None
    media_ctl: str | None = None
    ov13855: str | None = None
    preferred_camera: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

from __future__ import annotations

import time
from dataclasses import dataclass

from runtime.interfaces import PersonTrack, TrackState
from safety_brain.ppe_association import PersonPPE
from safety_brain.scene_graph import SceneGraph


@dataclass
class _TrackMemory:
    track_id: int
    bbox: list[int]
    zone_id: str | None
    missing_ppe: list[str]
    hit_count: int
    miss_count: int
    last_update_ts: float
    last_frame_id: int


class TrackManager:
    def __init__(
        self,
        scene_graph: SceneGraph,
        match_iou_threshold: float = 0.25,
        confirm_hits: int = 3,
        max_misses: int = 2,
    ) -> None:
        self.scene_graph = scene_graph
        self.match_iou_threshold = match_iou_threshold
        self.confirm_hits = confirm_hits
        self.max_misses = max_misses
        self._next_track_id = 1
        self._tracks: dict[int, _TrackMemory] = {}

    def update(self, people: list[PersonPPE], timestamp: float | None = None) -> list[PersonTrack]:
        now = timestamp if timestamp is not None else time.time()
        matched_track_ids: set[int] = set()
        outputs: list[PersonTrack] = []

        for person in people:
            track = self._match_track(person.person.bbox, matched_track_ids)
            if track is None:
                track = self._create_track(person, now)
            else:
                self._update_track(track, person, now)
            matched_track_ids.add(track.track_id)
            outputs.append(self._to_person_track(track, person))

        for track_id, track in list(self._tracks.items()):
            if track_id in matched_track_ids:
                continue
            track.miss_count += 1
            if track.miss_count > self.max_misses:
                del self._tracks[track_id]

        return outputs

    @property
    def active_count(self) -> int:
        return len(self._tracks)

    def _match_track(self, bbox: list[int], used_track_ids: set[int]) -> _TrackMemory | None:
        best_track: _TrackMemory | None = None
        best_iou = 0.0
        for track in self._tracks.values():
            if track.track_id in used_track_ids:
                continue
            score = _bbox_iou(track.bbox, bbox)
            if score > best_iou:
                best_iou = score
                best_track = track
        if best_track and best_iou >= self.match_iou_threshold:
            return best_track
        return None

    def _create_track(self, person: PersonPPE, timestamp: float) -> _TrackMemory:
        zone = self.scene_graph.find_zone(person.person.center)
        track = _TrackMemory(
            track_id=self._next_track_id,
            bbox=list(person.person.bbox),
            zone_id=zone.zone_id if zone else None,
            missing_ppe=person.missing_ppe,
            hit_count=1,
            miss_count=0,
            last_update_ts=timestamp,
            last_frame_id=person.person.frame_id,
        )
        self._tracks[track.track_id] = track
        self._next_track_id += 1
        return track

    def _update_track(self, track: _TrackMemory, person: PersonPPE, timestamp: float) -> None:
        zone = self.scene_graph.find_zone(person.person.center)
        track.bbox = list(person.person.bbox)
        track.zone_id = zone.zone_id if zone else None
        track.missing_ppe = person.missing_ppe
        track.hit_count += 1
        track.miss_count = 0
        track.last_update_ts = timestamp
        track.last_frame_id = person.person.frame_id

    def _to_person_track(self, track: _TrackMemory, person: PersonPPE) -> PersonTrack:
        missing = person.missing_ppe
        return PersonTrack(
            track_id=track.track_id,
            frame_id=person.person.frame_id,
            bbox=list(person.person.bbox),
            zone_id=track.zone_id,
            has_helmet=person.has_helmet,
            has_vest=person.has_vest,
            has_goggles=person.has_goggles,
            has_gloves=person.has_gloves,
            ppe_status=_ppe_status(missing),
            risk_state=_risk_state(missing, track.hit_count, self.confirm_hits),
            hit_count=track.hit_count,
            miss_count=track.miss_count,
            last_update_ts=track.last_update_ts,
        )


def _ppe_status(missing: list[str]) -> str:
    if not missing:
        return "ok"
    return "_".join(missing) + "_missing"


def _risk_state(missing: list[str], hit_count: int, confirm_hits: int) -> TrackState:
    if not missing:
        return "normal"
    if hit_count >= confirm_hits:
        return "confirmed"
    return "suspicious"


def _bbox_iou(a: list[int], b: list[int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(inter_x2 - inter_x1, 0)
    inter_h = max(inter_y2 - inter_y1, 0)
    inter_area = inter_w * inter_h
    area_a = max(ax2 - ax1, 0) * max(ay2 - ay1, 0)
    area_b = max(bx2 - bx1, 0) * max(by2 - by1, 0)
    union = area_a + area_b - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union

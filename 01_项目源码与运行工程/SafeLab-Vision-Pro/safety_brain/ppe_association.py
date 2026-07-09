from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from runtime.interfaces import Detection


@dataclass(frozen=True)
class PersonPPE:
    person: Detection
    has_helmet: bool
    has_vest: bool
    has_goggles: bool
    has_gloves: bool

    @property
    def missing_ppe(self) -> list[str]:
        missing: list[str] = []
        if not self.has_helmet:
            missing.append("helmet")
        if not self.has_vest:
            missing.append("vest")
        if not self.has_goggles:
            missing.append("goggles")
        if not self.has_gloves:
            missing.append("gloves")
        return missing


def associate_ppe(detections: list[Detection]) -> list[PersonPPE]:
    persons = [d for d in detections if d.class_name == "person"]
    if not persons:
        persons = _infer_people_from_ppe_items(detections)
    assigned_helmets = _assign_objects_to_people(
        persons,
        [d for d in detections if d.class_name == "helmet"],
        vertical_min=0.0,
        vertical_max=0.45,
    )
    assigned_vests = _assign_objects_to_people(
        persons,
        [d for d in detections if d.class_name == "vest"],
        vertical_min=0.30,
        vertical_max=0.95,
    )
    assigned_goggles = _assign_objects_to_people(
        persons,
        [d for d in detections if d.class_name == "goggles"],
        vertical_min=0.05,
        vertical_max=0.45,
    )
    assigned_gloves = _assign_objects_to_people(
        persons,
        [d for d in detections if d.class_name == "gloves"],
        vertical_min=0.35,
        vertical_max=0.90,
        horizontal_margin=0.25,
    )
    return [
        PersonPPE(
            person=person,
            has_helmet=index in assigned_helmets,
            has_vest=index in assigned_vests,
            has_goggles=index in assigned_goggles,
            has_gloves=index in assigned_gloves,
        )
        for index, person in enumerate(persons)
    ]


def _infer_people_from_ppe_items(detections: list[Detection]) -> list[Detection]:
    ppe_items = [d for d in detections if d.class_name in ("helmet", "vest", "goggles", "gloves")]
    if not ppe_items:
        return []

    x1 = min(item.bbox[0] for item in ppe_items)
    y1 = min(item.bbox[1] for item in ppe_items)
    x2 = max(item.bbox[2] for item in ppe_items)
    y2 = max(item.bbox[3] for item in ppe_items)
    width = max(x2 - x1, 1)
    height = max(y2 - y1, 1)
    inferred = [
        int(round(x1 - width * 0.35)),
        int(round(y1 - height * 0.10)),
        int(round(x2 + width * 0.35)),
        int(round(y2 + height * 1.15)),
    ]
    inferred_width = max(inferred[2] - inferred[0], 1)
    inferred_height = max(inferred[3] - inferred[1], 1)
    strongest = max(ppe_items, key=lambda item: item.confidence)
    return [
        Detection(
            frame_id=strongest.frame_id,
            source_type=strongest.source_type,
            class_name="person",
            confidence=min(strongest.confidence, 0.50),
            bbox=inferred,
            center=[(inferred[0] + inferred[2]) // 2, (inferred[1] + inferred[3]) // 2],
            area=inferred_width * inferred_height,
            model_name=f"{strongest.model_name}+ppe_person_fallback",
            infer_time_ms=strongest.infer_time_ms,
        )
    ]


def _assign_objects_to_people(
    persons: list[Detection],
    objects: list[Detection],
    vertical_min: float,
    vertical_max: float,
    horizontal_margin: float = 0.0,
) -> set[int]:
    assignments: set[int] = set()
    for obj in objects:
        candidates: list[tuple[float, int]] = []
        for index, person in enumerate(persons):
            distance = _object_region_distance(
                person,
                obj,
                vertical_min=vertical_min,
                vertical_max=vertical_max,
                horizontal_margin=horizontal_margin,
            )
            if distance is not None:
                candidates.append((distance, index))
        if candidates:
            _, best_index = min(candidates)
            assignments.add(best_index)
    return assignments


def _object_region_distance(
    person: Detection,
    obj: Detection,
    vertical_min: float,
    vertical_max: float,
    horizontal_margin: float,
) -> float | None:
    px1, py1, px2, py2 = person.bbox
    width = max(px2 - px1, 1)
    height = max(py2 - py1, 1)
    region_x1 = px1 - width * horizontal_margin
    region_x2 = px2 + width * horizontal_margin
    region_y1 = py1 + height * vertical_min
    region_y2 = py1 + height * vertical_max
    cx, cy = obj.center
    if not (region_x1 <= cx <= region_x2 and region_y1 <= cy <= region_y2):
        return None
    region_cx = (region_x1 + region_x2) / 2
    region_cy = (region_y1 + region_y2) / 2
    return hypot((cx - region_cx) / width, (cy - region_cy) / height)

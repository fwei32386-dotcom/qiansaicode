from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Zone:
    zone_id: str
    name: str
    risk_weight: int
    polygon: list[list[int]]


class SceneGraph:
    def __init__(self, zones: list[Zone]) -> None:
        self.zones = zones

    @classmethod
    def from_json(cls, path: str | Path) -> "SceneGraph":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        zones = [
            Zone(
                zone_id=str(item["zone_id"]),
                name=str(item.get("name", item["zone_id"])),
                risk_weight=int(item.get("risk_weight", 0)),
                polygon=[[int(x), int(y)] for x, y in item["polygon"]],
            )
            for item in payload.get("zones", [])
        ]
        return cls(zones)

    def find_zone(self, point: list[int]) -> Zone | None:
        for zone in self.zones:
            if _point_in_polygon(point, zone.polygon):
                return zone
        return None


def _point_in_polygon(point: list[int], polygon: list[list[int]]) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1) + xi
        if intersects:
            inside = not inside
        j = i
    return inside


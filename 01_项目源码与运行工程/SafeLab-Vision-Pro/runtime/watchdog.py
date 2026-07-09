from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class WatchdogStatus:
    name: str
    age_ms: float | None
    healthy: bool
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "age_ms": None if self.age_ms is None else round(self.age_ms, 3),
            "healthy": self.healthy,
            "detail": self.detail,
        }


@dataclass
class Watchdog:
    timeout_ms: float = 1000.0
    _heartbeats: dict[str, float] = field(default_factory=dict)

    def heartbeat(self, name: str, timestamp: float | None = None) -> None:
        self._heartbeats[name] = timestamp if timestamp is not None else time.monotonic()

    def status(self, name: str, now: float | None = None) -> WatchdogStatus:
        current = now if now is not None else time.monotonic()
        last = self._heartbeats.get(name)
        if last is None:
            return WatchdogStatus(name=name, age_ms=None, healthy=False, detail="no heartbeat received")
        age_ms = (current - last) * 1000.0
        healthy = age_ms <= self.timeout_ms
        detail = "heartbeat fresh" if healthy else "heartbeat stale"
        return WatchdogStatus(name=name, age_ms=age_ms, healthy=healthy, detail=detail)

    def summary(self, names: list[str], now: float | None = None) -> dict[str, object]:
        statuses = [self.status(name, now).to_dict() for name in names]
        return {
            "timeout_ms": self.timeout_ms,
            "healthy": all(bool(item["healthy"]) for item in statuses),
            "workers": statuses,
        }

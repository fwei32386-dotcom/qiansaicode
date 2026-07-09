from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class BusEvent:
    topic: str
    payload: dict[str, Any]
    sequence: int


@dataclass(frozen=True)
class BusStats:
    published_count: int
    consumed_count: int
    dropped_count: int
    pending_count: int


class AsyncEventBus:
    """Small latest-only event queue for non-blocking side effects."""

    def __init__(self, maxsize: int = 1) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self.maxsize = maxsize
        self._queue: deque[BusEvent] = deque()
        self._lock = Lock()
        self._sequence = 0
        self._published_count = 0
        self._consumed_count = 0
        self._dropped_count = 0

    def publish(self, topic: str, payload: dict[str, Any]) -> BusEvent:
        with self._lock:
            self._sequence += 1
            event = BusEvent(topic=topic, payload=dict(payload), sequence=self._sequence)
            if len(self._queue) >= self.maxsize:
                self._queue.popleft()
                self._dropped_count += 1
            self._queue.append(event)
            self._published_count += 1
            return event

    def drain(self, limit: int | None = None) -> list[BusEvent]:
        events: list[BusEvent] = []
        with self._lock:
            while self._queue and (limit is None or len(events) < limit):
                events.append(self._queue.popleft())
            self._consumed_count += len(events)
        return events

    def stats(self) -> BusStats:
        with self._lock:
            return BusStats(
                published_count=self._published_count,
                consumed_count=self._consumed_count,
                dropped_count=self._dropped_count,
                pending_count=len(self._queue),
            )

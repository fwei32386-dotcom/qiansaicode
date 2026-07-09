from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from statistics import mean
from typing import Iterator


@dataclass
class PipelineProfiler:
    _stages: dict[str, list[float]] = field(default_factory=dict)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.record(name, (time.perf_counter() - start) * 1000.0)

    def record(self, name: str, elapsed_ms: float) -> None:
        self._stages.setdefault(name, []).append(elapsed_ms)

    def latest(self) -> dict[str, float]:
        return {name: values[-1] for name, values in self._stages.items() if values}

    def summary(self) -> dict[str, dict[str, float] | dict[str, int]]:
        return {
            "average_ms": {
                name: round(mean(values), 4) for name, values in sorted(self._stages.items()) if values
            },
            "max_ms": {
                name: round(max(values), 4) for name, values in sorted(self._stages.items()) if values
            },
            "count": {name: len(values) for name, values in sorted(self._stages.items())},
        }

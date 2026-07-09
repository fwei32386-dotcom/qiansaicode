from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from runtime.async_event_bus import AsyncEventBus
from tools.benchmark_event_bus import benchmark_event_bus


class AsyncEventBusTest(unittest.TestCase):
    def test_event_bus_drops_oldest_when_full(self) -> None:
        bus = AsyncEventBus(maxsize=2)
        bus.publish("risk_event", {"event_id": "E1"})
        bus.publish("risk_event", {"event_id": "E2"})
        bus.publish("risk_event", {"event_id": "E3"})

        events = bus.drain()
        stats = bus.stats()

        self.assertEqual([event.payload["event_id"] for event in events], ["E2", "E3"])
        self.assertEqual(stats.published_count, 3)
        self.assertEqual(stats.consumed_count, 2)
        self.assertEqual(stats.dropped_count, 1)
        self.assertEqual(stats.pending_count, 0)

    def test_event_bus_drain_limit_keeps_pending_events(self) -> None:
        bus = AsyncEventBus(maxsize=3)
        for index in range(3):
            bus.publish("alarm_action", {"index": index})

        drained = bus.drain(limit=1)

        self.assertEqual(len(drained), 1)
        self.assertEqual(bus.stats().pending_count, 2)

    def test_event_bus_benchmark_report_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            summary = benchmark_event_bus(
                event_count=5,
                maxsize=2,
                csv_path=tmp_path / "event_bus.csv",
                summary_path=tmp_path / "event_bus_summary.json",
            )
            with (tmp_path / "event_bus.csv").open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))

        self.assertEqual(summary["published_count"], 5)
        self.assertEqual(summary["consumed_count"], 2)
        self.assertEqual(summary["dropped_count"], 3)
        self.assertTrue(summary["latest_only_protected"])
        self.assertGreater(len(rows), 5)


if __name__ == "__main__":
    unittest.main()

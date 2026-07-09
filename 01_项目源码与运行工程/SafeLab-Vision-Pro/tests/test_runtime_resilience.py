from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.fallback_manager import FallbackManager
from runtime.interfaces import HealthStatus
from runtime.watchdog import Watchdog
from tools.generate_runtime_resilience_report import generate_runtime_resilience_report


class RuntimeResilienceTest(unittest.TestCase):
    def test_fallback_manager_selects_shell_mock_mode(self) -> None:
        health = HealthStatus(
            camera="present",
            hdmi_capture="missing",
            rknn_model="missing",
            database="ok",
            gpio="missing",
            audio="missing",
            storage_free_mb=53895,
            fallback_mode="shell_only+mock_detection",
            python="missing",
            v4l2_ctl="ok",
            media_ctl="ok",
            ov13855="not_ready",
            preferred_camera="missing",
        )

        decision = FallbackManager().decide(health)

        self.assertEqual(decision.mode, "shell_only+mock_detection")
        self.assertTrue(decision.use_shell_tools)
        self.assertTrue(decision.use_mock_detection)
        self.assertTrue(decision.can_run_pipeline)

    def test_watchdog_detects_stale_worker(self) -> None:
        watchdog = Watchdog(timeout_ms=1000.0)
        watchdog.heartbeat("capture", timestamp=10.0)
        watchdog.heartbeat("inference", timestamp=8.0)

        capture = watchdog.status("capture", now=10.5)
        inference = watchdog.status("inference", now=10.5)
        missing = watchdog.status("event", now=10.5)

        self.assertTrue(capture.healthy)
        self.assertFalse(inference.healthy)
        self.assertFalse(missing.healthy)
        self.assertEqual(missing.detail, "no heartbeat received")

    def test_runtime_resilience_report_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outputs = generate_runtime_resilience_report(
                root / "fallback.json",
                root / "watchdog.json",
                root / "missing_health.json",
            )
            fallback = json.loads(Path(outputs["fallback"]).read_text(encoding="utf-8"))
            watchdog = json.loads(Path(outputs["watchdog"]).read_text(encoding="utf-8"))

        self.assertEqual(fallback["decision"]["mode"], "shell_only+mock_detection")
        self.assertFalse(watchdog["healthy"])
        self.assertEqual(len(watchdog["workers"]), 3)

    def test_runtime_resilience_report_uses_camera_ready_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            health_path = root / "health.json"
            health_path.write_text(
                json.dumps(
                    {
                        "camera": "present",
                        "python": "missing",
                        "ov13855": "ready",
                        "preferred_camera": "ok",
                        "v4l2_ctl": "ok",
                        "media_ctl": "ok",
                    }
                ),
                encoding="utf-8",
            )
            outputs = generate_runtime_resilience_report(
                root / "fallback.json",
                root / "watchdog.json",
                health_path,
            )
            fallback = json.loads(Path(outputs["fallback"]).read_text(encoding="utf-8"))

        self.assertEqual(fallback["health"]["ov13855"], "ready")
        self.assertEqual(fallback["health"]["preferred_camera"], "ok")
        self.assertNotIn("ov13855 sensor not ready", " ".join(fallback["decision"]["reasons"]))


if __name__ == "__main__":
    unittest.main()

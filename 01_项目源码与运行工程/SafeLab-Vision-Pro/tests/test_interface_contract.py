from __future__ import annotations

import unittest

from runtime.interfaces import (
    AlarmAction,
    Detection,
    FireSmokeTrack,
    HealthStatus,
    PersonTrack,
    ROIRegion,
    RiskEvent,
    TimelineEvent,
    VideoFrame,
)


class InterfaceContractTest(unittest.TestCase):
    def test_video_frame_contract_excludes_frame_payload(self) -> None:
        """Camera pixels stay in DDR/runtime memory and are not serialized to logs."""
        frame = VideoFrame(
            frame_id=1,
            source_type="camera",
            timestamp=1.0,
            width=1280,
            height=720,
            source_name="ov13855_video21",
            frame=object(),
        )

        self.assertEqual(
            set(frame.to_dict()),
            {
                "frame_id",
                "source_type",
                "timestamp",
                "width",
                "height",
                "source_name",
            },
        )

    def test_detection_contract(self) -> None:
        detection = Detection(
            frame_id=1,
            source_type="mock",
            class_name="person",
            confidence=0.9,
            bbox=[0, 0, 10, 10],
            center=[5, 5],
            area=100,
            model_name="test",
            infer_time_ms=1.0,
        )

        self.assertEqual(
            set(detection.to_dict()),
            {
                "frame_id",
                "source_type",
                "class_name",
                "confidence",
                "bbox",
                "center",
                "area",
                "model_name",
                "infer_time_ms",
            },
        )

    def test_person_track_contract(self) -> None:
        track = PersonTrack(
            track_id=1,
            frame_id=1,
            bbox=[0, 0, 10, 10],
            zone_id="danger_zone",
            has_helmet=False,
            has_vest=True,
            has_goggles=True,
            has_gloves=False,
            ppe_status="helmet_missing",
            risk_state="suspicious",
            hit_count=3,
            miss_count=0,
            last_update_ts=1.0,
        )

        self.assertEqual(track.to_dict()["ppe_status"], "helmet_missing")
        self.assertIn("last_update_ts", track.to_dict())

    def test_roi_region_contract(self) -> None:
        roi = ROIRegion(
            roi_id="ROI_F1_T1_80_70_340_620",
            frame_id=1,
            bbox=[80, 70, 340, 620],
            source_bbox=[100, 120, 300, 520],
            frame_width=1280,
            frame_height=720,
            reason="track:1:confirmed:helmet_missing",
            margin_ratio=0.2,
            source_track_id=1,
        )

        payload = roi.to_dict()
        self.assertEqual(payload["frame_id"], 1)
        self.assertEqual(payload["source_track_id"], 1)
        self.assertEqual(payload["bbox"], [80, 70, 340, 620])

    def test_fire_smoke_track_contract(self) -> None:
        track = FireSmokeTrack(
            track_id=10,
            frame_id=203,
            class_name="smoke",
            bbox=[0, 0, 10, 10],
            confidence=0.83,
            appear_count=3,
            area_history=[100, 150, 210],
            state="confirmed",
            risk_level="high",
        )

        payload = track.to_dict()
        self.assertEqual(payload["class_name"], "smoke")
        self.assertEqual(payload["area_history"], [100, 150, 210])

    def test_risk_event_contract(self) -> None:
        event = RiskEvent(
            event_id="E1",
            frame_id=1,
            source_type="mock",
            event_type="ppe_violation",
            risk_score=72,
            risk_level="high",
            reasons=["helmet missing"],
            bbox=[0, 0, 10, 10],
            need_alarm=True,
            need_snapshot=True,
            need_log=True,
            timestamp=1.0,
        )

        payload = event.to_dict()
        self.assertTrue(payload["reasons"])
        self.assertEqual(payload["frame_id"], 1)
        self.assertEqual(payload["source_type"], "mock")
        self.assertIn("rule_id", payload)
        self.assertIn("action_hint", payload)

    def test_timeline_event_contract(self) -> None:
        event = TimelineEvent(
            event_id="E1",
            stage="alarmed",
            timestamp=1.0,
            detail="risk confirmed and alarmed",
            frame_id=203,
        )

        payload = event.to_dict()
        self.assertEqual(payload["stage"], "alarmed")
        self.assertEqual(payload["frame_id"], 203)

    def test_alarm_action_contract(self) -> None:
        action = AlarmAction(
            event_id="E1",
            voice_text="test",
            led_color="red",
            buzzer=True,
            relay=False,
            snapshot=True,
            log=True,
            cooldown_ms=20000,
        )

        self.assertEqual(action.to_dict()["cooldown_ms"], 20000)

    def test_health_status_contract(self) -> None:
        status = HealthStatus(
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

        payload = status.to_dict()
        self.assertEqual(payload["fallback_mode"], "shell_only+mock_detection")
        self.assertEqual(payload["storage_free_mb"], 53895)
        self.assertIn("preferred_camera", payload)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from dashboard.live_dashboard import build_live_dashboard_state, write_live_dashboard


class LiveDashboardTest(unittest.TestCase):
    def test_live_dashboard_state_and_html_are_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.jsonl"
            actions = root / "actions.jsonl"
            actuator = root / "actuator.jsonl"
            ai = root / "ai.jsonl"
            detections = root / "detections.jsonl"
            detection_image = root / "detection.jpg"
            health = root / "health.json"
            video_config = _write_video_config(root)
            input_source = root / "runtime" / "input_source.json"
            events.write_text(json.dumps(_event()) + "\n", encoding="utf-8")
            actions.write_text(json.dumps(_action()) + "\n", encoding="utf-8")
            actuator.write_text(json.dumps(_actuator()) + "\n", encoding="utf-8")
            ai.write_text(json.dumps(_ai()) + "\n", encoding="utf-8")
            detection_image.write_bytes(b"fake-jpeg")
            detections.write_text(json.dumps(_detection(detection_image)) + "\n", encoding="utf-8")
            health.write_text(json.dumps({"fallback_mode": "shell_only+mock_detection", "ov13855": "not_ready"}), encoding="utf-8")

            output = write_live_dashboard(
                events_path=events,
                actions_path=actions,
                actuator_path=actuator,
                ai_explanations_path=ai,
                detections_path=detections,
                health_path=health,
                video_config_path=video_config,
                input_source_path=input_source,
                output_path=root / "live.html",
                state_path=root / "state.json",
            )
            html = Path(output["html"]).read_text(encoding="utf-8")
            state = json.loads(Path(output["state"]).read_text(encoding="utf-8"))

        self.assertIn("SafeLab \u5b9e\u65f6\u6f14\u793a\u770b\u677f", html)
        self.assertIn("SafeLab-Vision Pro", html)
        self.assertIn("视觉风险认知中枢", html)
        self.assertIn("RK3588 NPU", html)
        self.assertIn("低延迟模式", html)
        self.assertIn("摄像头输入", html)
        self.assertIn("本地输入", html)
        self.assertNotIn("采集卡输入", html)
        self.assertIn("事件生命线", html)
        self.assertIn("证据链", html)
        self.assertIn("最新帧优先", html)
        self.assertIn("rail-toggle", html)
        self.assertIn("AI \u8bf4\u660e", html)
        self.assertIn("检测记录", html)
        self.assertIn('data-source-id="camera_ov13855"', html)
        self.assertNotIn('data-source-id="hdmi_capture"', html)
        self.assertNotIn('data-source-id="file_demo"', html)
        self.assertIn('data-source-id="board_file_demo"', html)
        self.assertNotIn('id="board-local-media-file"', html)
        self.assertIn("选择本地视频或图片并上传到板卡", html)
        self.assertNotIn("RK本地视频", html)
        self.assertIn("board_camera_preview.jpg", html)
        self.assertIn("translateReason", html)
        self.assertIn("translateVoice", html)
        self.assertIn("喇叭播报", html)
        self.assertIn("暂无喇叭播报记录", html)
        self.assertIn("colorText(r.led_color)", html)
        self.assertIn("booleanText(r.buzzer)", html)
        self.assertIn("检测到火焰风险，请立即复核现场。", html)
        self.assertIn("检测到烟雾风险，请立即复核现场。", html)
        self.assertIn("\u677f\u7aef\u76f8\u673a\u753b\u9762", html)
        self.assertIn("state.json", html)
        self.assertIn("setInterval(refresh, 1000)", html)
        self.assertNotIn("setInterval(refresh, 5000)", html)
        self.assertIn('data-panel-target="panel-live"', html)
        self.assertIn('id="detection-overlay"', html)
        self.assertNotIn('id="local-detection-overlay"', html)
        self.assertIn("function renderDetectionOverlay", html)
        self.assertIn("let latestDashboardState = null", html)
        self.assertIn("function setupLocalOverlayRedraw", html)
        self.assertIn('video.addEventListener("loadedmetadata", redrawLocalDetectionOverlay)', html)
        self.assertIn('video.addEventListener("timeupdate", redrawLocalDetectionOverlay)', html)
        self.assertIn("function mediaNaturalSize", html)
        self.assertIn("detection-thumb", html)
        self.assertIn('id="panel-ai"', html)
        self.assertIn("setupDashboardInteractions", html)
        self.assertIn("activatePanel", html)
        self.assertIn("sourcePanelForSource", html)
        self.assertIn("sourceForPanel", html)
        self.assertIn("syncSourceButtonsForPanel", html)
        self.assertIn("activatePanel(sourcePanelForSource(button.dataset.sourceId))", html)
        self.assertIn("scrollIntoView", html)
        self.assertIn("source-message", html)
        self.assertIn('data-view="panel-live"', html)
        self.assertIn('data-view="panel-local-media"', html)
        self.assertIn('id="local-media-file"', html)
        self.assertIn('accept="video/*,image/*"', html)
        self.assertEqual(html.count('type="file"'), 1)
        self.assertIn('id="local-video-preview"', html)
        self.assertIn('id="local-image-preview"', html)
        self.assertIn('id="local-detection-frame-preview"', html)
        self.assertIn('class="local-input-column"', html)
        self.assertIn('class="local-result-column"', html)
        self.assertIn('class="local-result-stage"', html)
        self.assertNotIn('id="local-result-placeholder"', html)
        self.assertLess(html.index('id="local-video-preview"'), html.index('id="local-detection-frame-preview"'))
        self.assertIn("syncLocalDetectionFramePreview", html)
        self.assertIn("restoreCameraLivePreview", html)
        self.assertIn("function boardDetectionFrameReady", html)
        self.assertIn("function renderLocalYoloResultImage", html)
        self.assertIn("function drawYoloBoxOnCanvas", html)
        self.assertIn('canvas.toDataURL("image/jpeg", 0.9)', html)
        self.assertIn('const usesLocalPreview = source.selected_source === "file_demo" || source.selected_source === "board_file_demo"', html)
        self.assertIn("syncLocalDetectionFramePreview(source,", html)
        self.assertNotIn("image.src = latestDetectionFrame.image_url", html)
        self.assertIn("if (usesLocalPreview) {", html)
        self.assertIn("return;", html)
        self.assertIn("source.selected_source === \"board_file_demo\"", html)
        self.assertIn("选择本地视频或图片并上传到板卡", html)
        self.assertIn("本地视频检测", html)
        self.assertIn(".local-media-grid { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:14px;", html)
        self.assertNotIn(".local-result-stage.has-result .local-result-placeholder", html)
        self.assertIn("#panel-local-media .section-note, #runtime { display:none; }", html)
        self.assertNotIn("接入方式", html)
        self.assertNotIn("本地图片文件", html)
        self.assertNotIn("minmax(260px,.75fr)", html)
        self.assertIn("showView", html)
        self.assertIn("previewLocalMedia", html)
        self.assertIn("eventTypeText(r.event_type)", html)
        self.assertIn("renderReasonLines(r.reasons || [])", html)
        self.assertIn("ppeViolationTitle(missing)", html)
        self.assertIn("防护违规：人员缺少${missingText}。", html)
        self.assertIn("危险区域防护违规：人员未佩戴安全帽。", html)
        self.assertIn("缺失防护", html)
        self.assertIn("关联风险", html)
        self.assertIn("持续状态", html)
        self.assertIn("reason-lines", html)
        self.assertIn("连续 3 帧检测到火焰", html)
        self.assertIn("连续 3 帧检测到烟雾", html)
        self.assertIn("被抑制规则=", html)
        self.assertIn("危险区域内", html)
        self.assertIn("缺失防护=", html)
        self.assertNotIn("命中框", html)
        self.assertIn("background:#f5f7fb", html)
        self.assertNotIn("DeepSeek Evidence", html)
        self.assertNotIn("VIDEO STREAM PLACEHOLDER", html)
        self.assertNotIn("risk overlay", html)
        self.assertEqual(state["counts"]["events"], 1)
        self.assertEqual(state["counts"]["detections"], 1)
        self.assertEqual(state["latest_detections"][0]["class_name"], "helmet")
        self.assertIn("/detection-image?path=", state["latest_detections"][0]["image_url"])
        self.assertEqual(state["counts"]["ai_explanations"], 1)
        self.assertEqual(state["input_source"]["selected_source"], "camera_ov13855")
        self.assertEqual(state["status"]["risk_state"], "alarm")
        self.assertEqual(output["actions"], 1)

    def test_live_dashboard_handles_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = build_live_dashboard_state(
                events_path=Path(tmp) / "missing_events.jsonl",
                actions_path=Path(tmp) / "missing_actions.jsonl",
                actuator_path=Path(tmp) / "missing_actuator.jsonl",
                ai_explanations_path=Path(tmp) / "missing_ai.jsonl",
                detections_path=Path(tmp) / "missing_detections.jsonl",
                health_path=Path(tmp) / "missing_health.json",
                video_config_path=Path(tmp) / "missing_video_config.yaml",
                input_source_path=Path(tmp) / "missing_input_source.json",
            )

        self.assertEqual(state["counts"]["events"], 0)
        self.assertEqual(state["counts"]["detections"], 0)
        self.assertEqual(state["status"]["risk_state"], "idle")

    def test_live_dashboard_only_displays_recent_ai_explanations_for_one_minute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ai = root / "ai.jsonl"
            now = time.time()
            rows = [
                {**_ai(), "event_id": "OLD", "timestamp": now - 61},
                {**_ai(), "event_id": "FRESH", "timestamp": now - 59},
            ]
            ai.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

            state = build_live_dashboard_state(
                events_path=root / "missing_events.jsonl",
                actions_path=root / "missing_actions.jsonl",
                actuator_path=root / "missing_actuator.jsonl",
                ai_explanations_path=ai,
                detections_path=root / "missing_detections.jsonl",
                health_path=root / "missing_health.json",
                video_config_path=root / "missing_video_config.yaml",
                input_source_path=root / "missing_input_source.json",
            )

        self.assertEqual(state["counts"]["ai_explanations"], 2)
        self.assertEqual([row["event_id"] for row in state["latest_ai_explanations"]], ["FRESH"])

    def test_live_dashboard_shows_only_recent_speaker_outputs_as_actuator_records_for_three_minutes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            actuator = root / "actuator.jsonl"
            speech = root / "speech_output.jsonl"
            now = time.time()
            actuator.write_text(json.dumps(_actuator(), ensure_ascii=False) + "\n", encoding="utf-8")
            rows = [
                {
                    "timestamp": now - 181,
                    "speech_source": "risk_voice_alarm",
                    "text": "旧播报",
                    "executed": True,
                    "device": "plughw:1,0",
                },
                {
                    "timestamp": now - 179,
                    "speech_source": "risk_voice_alarm",
                    "text": "警报，防护违规：人员缺少安全帽。",
                    "executed": True,
                    "device": "plughw:1,0",
                },
            ]
            speech.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")

            state = build_live_dashboard_state(
                events_path=root / "missing_events.jsonl",
                actions_path=root / "missing_actions.jsonl",
                actuator_path=actuator,
                ai_explanations_path=root / "missing_ai.jsonl",
                speech_output_path=speech,
                detections_path=root / "missing_detections.jsonl",
                health_path=root / "missing_health.json",
                video_config_path=root / "missing_video_config.yaml",
                input_source_path=root / "missing_input_source.json",
            )

        self.assertEqual(state["counts"]["actuator_records"], 1)
        self.assertEqual(len(state["latest_actuator_records"]), 1)
        self.assertEqual(state["latest_actuator_records"][0]["backend"], "speaker")
        self.assertEqual(state["latest_actuator_records"][0]["voice_text"], "警报，防护违规：人员缺少安全帽。")
        self.assertTrue(state["latest_actuator_records"][0]["speaker"]["executed"])

    def test_live_dashboard_hides_low_confidence_fire_smoke_detections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "frame.jpg"
            detections = root / "detections.jsonl"
            image.write_bytes(b"fake-jpeg")
            records = [
                _detection_record(image, "helmet", 0.85),
                _detection_record(image, "fire", 0.26),
                _detection_record(image, "smoke", 0.44),
                _detection_record(image, "smoke", 0.45),
            ]
            detections.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

            state = build_live_dashboard_state(
                events_path=root / "missing_events.jsonl",
                actions_path=root / "missing_actions.jsonl",
                actuator_path=root / "missing_actuator.jsonl",
                ai_explanations_path=root / "missing_ai.jsonl",
                detections_path=detections,
                health_path=root / "missing_health.json",
                video_config_path=root / "missing_video_config.yaml",
                input_source_path=root / "missing_input_source.json",
            )

        self.assertEqual(state["counts"]["detections"], 4)
        self.assertEqual(
            [(item["class_name"], item["confidence"]) for item in state["latest_detections"]],
            [("helmet", 0.85), ("smoke", 0.45)],
        )

    def test_live_dashboard_uses_current_board_frame_for_board_video_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_detection_image = root / "old_detection.jpg"
            current_frame = root / "current_board_frame.jpg"
            detections = root / "detections.jsonl"
            bridge_summary = root / "bridge_summary.json"
            video_config = _write_video_config(root)
            input_source = root / "runtime" / "input_source.json"
            old_detection_image.write_bytes(b"old")
            current_frame.write_bytes(b"current")
            detections.write_text(
                json.dumps(_detection_record(old_detection_image, "helmet", 0.85, frame_id=7)) + "\n",
                encoding="utf-8",
            )
            bridge_summary.write_text(
                json.dumps(
                    {
                        "source_type": "board_file",
                        "detection_frame_id": 9,
                        "frame": {"frame_path": str(current_frame)},
                    }
                ),
                encoding="utf-8",
            )
            input_source.parent.mkdir(parents=True, exist_ok=True)
            input_source.write_text(
                json.dumps(
                    {
                        "selected_source": "board_file_demo",
                        "source_type": "board_file",
                        "board_path": "/root/safelab_media/current_demo.mp4",
                    }
                ),
                encoding="utf-8",
            )

            state = build_live_dashboard_state(
                events_path=root / "missing_events.jsonl",
                actions_path=root / "missing_actions.jsonl",
                actuator_path=root / "missing_actuator.jsonl",
                ai_explanations_path=root / "missing_ai.jsonl",
                detections_path=detections,
                health_path=root / "missing_health.json",
                video_config_path=video_config,
                input_source_path=input_source,
                bridge_summary_path=bridge_summary,
            )

        self.assertEqual(state["board_live_frame"]["frame_id"], 9)
        self.assertIn("/detection-image?path=", state["board_live_frame"]["image_url"])
        self.assertIn("current_board_frame.jpg", state["board_live_frame"]["image_url"])
        self.assertEqual(state["latest_detections"][0]["frame_id"], 7)

    def test_live_dashboard_exposes_current_camera_frame_for_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current_frame = root / "current_camera_frame.jpg"
            bridge_summary = root / "bridge_summary.json"
            video_config = _write_video_config(root)
            input_source = root / "runtime" / "input_source.json"
            current_frame.write_bytes(b"current")
            bridge_summary.write_text(
                json.dumps(
                    {
                        "source_key": "camera_ov13855",
                        "source_type": "camera",
                        "detection_frame_id": 42,
                        "frame": {"frame_path": str(current_frame)},
                    }
                ),
                encoding="utf-8",
            )
            input_source.parent.mkdir(parents=True, exist_ok=True)
            input_source.write_text(
                json.dumps({"selected_source": "camera_ov13855", "source_type": "camera"}),
                encoding="utf-8",
            )

            state = build_live_dashboard_state(
                events_path=root / "missing_events.jsonl",
                actions_path=root / "missing_actions.jsonl",
                actuator_path=root / "missing_actuator.jsonl",
                ai_explanations_path=root / "missing_ai.jsonl",
                detections_path=root / "missing_detections.jsonl",
                health_path=root / "missing_health.json",
                video_config_path=video_config,
                input_source_path=input_source,
                bridge_summary_path=bridge_summary,
            )

        self.assertEqual(state["active_live_frame"]["source_type"], "camera")
        self.assertEqual(state["active_live_frame"]["source_key"], "camera_ov13855")
        self.assertEqual(state["active_live_frame"]["frame_id"], 42)
        self.assertIn("current_camera_frame.jpg", state["active_live_frame"]["image_url"])


def _event() -> dict[str, object]:
    return {
        "event_id": "E1",
        "frame_id": 1,
        "event_type": "smoke",
        "risk_level": "high",
        "risk_score": 80,
        "reasons": ["smoke appeared for 3 consecutive frames"],
    }


def _action() -> dict[str, object]:
    return {
        "event_id": "E1",
        "voice_text": "Smoke risk detected.",
        "led_color": "red",
        "buzzer": True,
        "cooldown_ms": 20000,
    }


def _actuator() -> dict[str, object]:
    return {
        "event_id": "E1",
        "backend": "mock",
        "led": {"color": "red"},
        "buzzer": {"enabled": True},
        "relay": {"enabled": False},
    }


def _ai() -> dict[str, object]:
    return {
        "event_id": "E1",
        "source": "fallback",
        "summary": "Smoke risk detected.",
        "recommendation": "Check the lab.",
    }


def _detection(image_path: Path) -> dict[str, object]:
    return _detection_record(image_path, "helmet", 0.85)


def _detection_record(image_path: Path, class_name: str, confidence: float, frame_id: int = 7) -> dict[str, object]:
    return {
        "frame_id": frame_id,
        "source_type": "file",
        "class_name": class_name,
        "confidence": confidence,
        "bbox": [10, 20, 80, 120],
        "model_name": "safelab_ppe_hybrid_int8",
        "source_image": str(image_path),
    }


def _write_video_config(root: Path) -> Path:
    config = root / "video_config.yaml"
    config.write_text(
        "\n".join(
            [
                "video_sources:",
                "  default: camera_ov13855",
                "  camera_ov13855:",
                "    source_type: camera",
                "    device: /dev/video-camera0",
                "    source_name: ov13855_video11",
                "  file_demo:",
                "    source_type: file",
                "    path: video/demo.mp4",
                "    source_name: local_demo_video",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return config


if __name__ == "__main__":
    unittest.main()

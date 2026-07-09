from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request
from urllib.request import urlopen

from dashboard.live_server import LiveDashboardConfig, run_live_dashboard_server


class LiveDashboardServerTest(unittest.TestCase):
    def test_http_state_and_sse_are_served(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.jsonl"
            actions = root / "actions.jsonl"
            actuator = root / "actuator.jsonl"
            ai = root / "ai.jsonl"
            detections = root / "detections.jsonl"
            detection_image = root / "detection.jpg"
            health = root / "health.json"
            camera_snapshot = root / "board_camera_preview.jpg"
            video_config = _write_video_config(root)
            input_source = root / "runtime" / "input_source.json"
            model_detection = root / "runtime" / "model_detection.json"
            scene_mode = root / "runtime" / "scene_mode.json"
            voice_commands = root / "events" / "voice_commands.jsonl"
            speech_output = root / "events" / "speech_output.jsonl"
            xiaoduo_dialog = root / "events" / "xiaoduo_dialog.jsonl"
            xiaoduo_state = root / "runtime" / "xiaoduo_state.json"
            local_media_dir = root / "runtime" / "local_media"
            events.write_text(json.dumps(_event()) + "\n", encoding="utf-8")
            actions.write_text(json.dumps(_action()) + "\n", encoding="utf-8")
            actuator.write_text(json.dumps(_actuator()) + "\n", encoding="utf-8")
            ai.write_text(json.dumps(_ai()) + "\n", encoding="utf-8")
            detection_image.write_bytes(b"fake-detection-jpeg")
            detections.write_text(json.dumps(_detection(detection_image)) + "\n", encoding="utf-8")
            health.write_text(json.dumps({"fallback_mode": "shell_only", "camera": "ok"}), encoding="utf-8")
            camera_snapshot.write_bytes(b"fake-jpeg")

            server = run_live_dashboard_server(
                "127.0.0.1",
                0,
                LiveDashboardConfig(
                    events_path=events,
                    actions_path=actions,
                    actuator_path=actuator,
                    ai_explanations_path=ai,
                    detections_path=detections,
                    health_path=health,
                    video_config_path=video_config,
                    input_source_path=input_source,
                    camera_snapshot_path=camera_snapshot,
                    model_detection_path=model_detection,
                    scene_mode_path=scene_mode,
                    voice_commands_path=voice_commands,
                    speech_output_path=speech_output,
                    xiaoduo_dialog_path=xiaoduo_dialog,
                    xiaoduo_state_path=xiaoduo_state,
                    local_media_dir=local_media_dir,
                    refresh_seconds=0.01,
                ),
            )
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                html = urlopen(base + "/", timeout=5).read().decode("utf-8")
                snapshot = urlopen(base + "/board_camera_preview.jpg", timeout=5).read()
                state = json.loads(urlopen(base + "/state.json", timeout=5).read().decode("utf-8"))
                detection_image_body = urlopen(base + state["latest_detections"][0]["image_url"], timeout=5).read()
                post = Request(
                    base + "/input-source",
                    data=json.dumps({"selected_source": "board_file_demo"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                source_payload = json.loads(urlopen(post, timeout=5).read().decode("utf-8"))
                model_post = Request(
                    base + "/model-detection",
                    data=json.dumps({"enabled": False, "interval_frames": 90}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                model_payload = json.loads(urlopen(model_post, timeout=5).read().decode("utf-8"))
                with patch("dashboard.live_server.upload_file_to_board", return_value={"remote_path": "/root/safelab_media/current_demo.mp4"}) as board_upload:
                    board_media_post = Request(
                        base + "/board-local-media?filename=clip.mp4",
                        data=b"fake-video-bytes",
                        headers={"Content-Type": "application/octet-stream"},
                        method="POST",
                    )
                    board_media_payload = json.loads(urlopen(board_media_post, timeout=5).read().decode("utf-8"))
                    board_upload_called_with = board_upload.call_args.kwargs
                with patch("dashboard.live_server.upload_file_to_board", return_value={"remote_path": "/root/safelab_media/current_demo.jpg"}) as image_upload:
                    board_image_post = Request(
                        base + "/board-local-media?filename=photo.jpg",
                        data=_tiny_jpeg_bytes(),
                        headers={"Content-Type": "application/octet-stream"},
                        method="POST",
                    )
                    board_image_payload = json.loads(urlopen(board_image_post, timeout=5).read().decode("utf-8"))
                    board_image_called_with = image_upload.call_args.kwargs
                scene_post = Request(
                    base + "/scene-mode",
                    data=json.dumps({"mode": "lab"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                scene_payload = json.loads(urlopen(scene_post, timeout=5).read().decode("utf-8"))
                voice_post = Request(
                    base + "/voice-command",
                    data=json.dumps({"raw_text": "当前状态", "source": "test_web_serial"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                voice_payload = json.loads(urlopen(voice_post, timeout=5).read().decode("utf-8"))
                saved_model_detection = json.loads(model_detection.read_text(encoding="utf-8"))
                saved_scene_mode = json.loads(scene_mode.read_text(encoding="utf-8"))
                saved_voice = [json.loads(line) for line in voice_commands.read_text(encoding="utf-8").splitlines()]
                saved_speech = [json.loads(line) for line in speech_output.read_text(encoding="utf-8").splitlines()]
                saved_xiaoduo = json.loads(xiaoduo_state.read_text(encoding="utf-8"))
                saved_source = json.loads(input_source.read_text(encoding="utf-8"))
                saved_source_path_exists = Path(saved_source["path"]).exists()
                with urlopen(base + "/events", timeout=5) as response:
                    stream = (
                        response.readline().decode("utf-8")
                        + response.readline().decode("utf-8")
                        + response.readline().decode("utf-8")
                    )
            finally:
                server.shutdown()
                server.server_close()

        self.assertIn("视觉风险认知中枢", html)
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
        self.assertIn("智能说明", html)
        self.assertIn('id="ai-followup-button"', html)
        self.assertIn("/ai-followup", html)
        self.assertIn("requestAiFollowup", html)
        self.assertIn("maybeRequestAiFollowup", html)
        self.assertIn('panelId === "panel-ai"', html)
        self.assertIn("const AI_FOLLOWUP_INTERVAL_MS = 30000", html)
        self.assertIn("now - lastAiFollowupAt < AI_FOLLOWUP_INTERVAL_MS", html)
        self.assertIn('data-source-id="camera_ov13855"', html)
        self.assertNotIn('data-source-id="hdmi_capture"', html)
        self.assertNotIn('data-source-id="file_demo"', html)
        self.assertIn('data-source-id="board_file_demo"', html)
        self.assertIn("/board-local-media", html)
        self.assertNotIn('id="board-local-media-file"', html)
        self.assertIn("选择本地视频或图片并上传到板卡", html)
        self.assertNotIn("RK本地视频", html)
        self.assertIn('id="camera-preview"', html)
        self.assertIn('id="detection-overlay"', html)
        self.assertNotIn('id="local-detection-overlay"', html)
        self.assertIn("function renderDetectionOverlay", html)
        self.assertIn("let latestDashboardState = null", html)
        self.assertIn("function setupLocalOverlayRedraw", html)
        self.assertIn('video.addEventListener("loadedmetadata", redrawLocalDetectionOverlay)', html)
        self.assertIn('video.addEventListener("timeupdate", redrawLocalDetectionOverlay)', html)
        self.assertIn("function mediaNaturalSize", html)
        self.assertIn("detection-thumb", html)
        self.assertIn("setInterval(refresh, 1000)", html)
        self.assertNotIn("setInterval(refresh, 5000)", html)
        self.assertIn("http://127.0.0.1:8090/stream.mjpg", html)
        self.assertIn("board_camera_preview.jpg", html)
        self.assertNotIn("等待视频画面", html)
        self.assertIn("object-fit: contain", html)
        self.assertIn('id="model-detection-toggle"', html)
        self.assertIn('id="model-detection-interval"', html)
        self.assertIn("/model-detection", html)
        self.assertIn('id="scene-selector"', html)
        self.assertIn("/scene-mode", html)
        self.assertIn("检测记录", html)
        self.assertIn('id="detections"', html)
        self.assertIn("场景检查项", html)
        self.assertIn('data-panel-target="panel-live"', html)
        self.assertIn('id="panel-ai"', html)
        self.assertIn("setupDashboardInteractions", html)
        self.assertNotIn('id="panel-voice"', html)
        self.assertNotIn("/voice-command", html)
        self.assertNotIn("语音模拟", html)
        self.assertNotIn("模拟语音输入", html)
        self.assertNotIn("真实喇叭播报", html)
        self.assertNotIn("发送模拟语音", html)
        self.assertIn("activatePanel", html)
        self.assertIn("sourcePanelForSource", html)
        self.assertIn("sourceForPanel", html)
        self.assertIn("syncSourceButtonsForPanel", html)
        self.assertIn("activatePanel(sourcePanelForSource(button.dataset.sourceId))", html)
        self.assertIn("scrollIntoView", html)
        self.assertIn("source-message", html)
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
        self.assertIn("function boardDetectionFrameReady", html)
        self.assertIn("function renderLocalYoloResultImage", html)
        self.assertIn("function drawYoloBoxOnCanvas", html)
        self.assertIn('canvas.toDataURL("image/jpeg", 0.9)', html)
        self.assertIn('const usesLocalPreview = source.selected_source === "file_demo" || source.selected_source === "board_file_demo"', html)
        self.assertIn("syncLocalDetectionFramePreview(source,", html)
        self.assertIn("if (usesLocalPreview) {", html)
        self.assertIn("return;", html)
        self.assertNotIn("if (boardName)", html)
        self.assertIn("source.selected_source === \"board_file_demo\"", html)
        self.assertIn("选择本地视频或图片并上传到板卡", html)
        self.assertIn("本地视频检测", html)
        self.assertIn(".local-media-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 14px;", html)
        self.assertNotIn(".local-result-stage.has-result .local-result-placeholder", html)
        self.assertIn("#panel-local-media .section-note, #runtime { display: none; }", html)
        self.assertNotIn("接入方式", html)
        self.assertNotIn("本地图片文件", html)
        self.assertNotIn("minmax(260px, .75fr)", html)
        self.assertIn("showView", html)
        self.assertIn("previewLocalMedia", html)
        self.assertIn("translateVoice(r.voice_text || \"\")", html)
        self.assertIn("colorText(r.led_color)", html)
        self.assertIn("booleanText(r.buzzer)", html)
        self.assertIn("检测到火焰风险，请立即复核现场。", html)
        self.assertIn("检测到烟雾风险，请立即复核现场。", html)
        self.assertIn("eventTypeText(r.event_type)", html)
        self.assertIn("renderReasonLines(r.reasons || [])", html)
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
        self.assertIn("background: #f5f7fb", html)
        self.assertNotIn("DeepSeek Evidence", html)
        self.assertNotIn("VIDEO STREAM PLACEHOLDER", html)
        self.assertNotIn("risk overlay", html)
        self.assertEqual(snapshot, b"fake-jpeg")
        self.assertEqual(detection_image_body, b"fake-detection-jpeg")
        self.assertEqual(state["counts"]["events"], 1)
        self.assertEqual(state["counts"]["detections"], 1)
        self.assertEqual(state["latest_detections"][0]["class_name"], "smoke")
        self.assertIn("/detection-image?path=", state["latest_detections"][0]["image_url"])
        self.assertEqual(state["status"]["risk_state"], "alarm")
        self.assertEqual(state["input_source"]["selected_source"], "camera_ov13855")
        self.assertNotIn("file_demo", [item["id"] for item in state["available_input_sources"]])
        self.assertIn("board_file_demo", [item["id"] for item in state["available_input_sources"]])
        self.assertNotIn("hdmi_capture", [item["id"] for item in state["available_input_sources"]])
        self.assertEqual(source_payload["input_source"]["selected_source"], "board_file_demo")
        self.assertFalse(model_payload["model_detection"]["enabled"])
        self.assertEqual(model_payload["model_detection"]["interval_frames"], 90)
        self.assertFalse(saved_model_detection["enabled"])
        self.assertEqual(board_media_payload["input_source"]["selected_source"], "board_file_demo")
        self.assertEqual(board_media_payload["input_source"]["board_path"], "/root/safelab_media/current_demo.mp4")
        self.assertEqual(board_media_payload["input_source"]["media_type"], "video")
        self.assertEqual(board_upload_called_with["remote_path"], "/root/safelab_media/current_demo.mp4")
        self.assertTrue(Path(board_upload_called_with["local_path"]).exists())
        self.assertEqual(board_image_payload["input_source"]["selected_source"], "board_file_demo")
        self.assertEqual(board_image_payload["input_source"]["board_path"], "/root/safelab_media/current_demo.jpg")
        self.assertEqual(board_image_payload["input_source"]["media_type"], "image")
        self.assertEqual(board_image_called_with["remote_path"], "/root/safelab_media/current_demo.jpg")
        self.assertEqual(scene_payload["scene_mode"]["mode"], "lab")
        self.assertEqual(scene_payload["scene_mode"]["required_ppe"], ["goggles", "gloves"])
        self.assertEqual(saved_scene_mode["mode"], "lab")
        self.assertEqual(voice_payload["voice_feedback"]["command"]["command"], "status")
        self.assertIn("当前模型检测", voice_payload["voice_feedback"]["spoken_text"])
        self.assertEqual(saved_voice[0]["source"], "test_web_serial")
        self.assertEqual(saved_voice[0]["raw_text"], "当前状态")
        self.assertIn("当前模型检测", saved_speech[0]["text"])
        self.assertEqual(saved_xiaoduo["last_command"], "status")
        self.assertEqual(saved_source["selected_source"], "board_file_demo")
        self.assertEqual(saved_source["media_type"], "image")
        self.assertTrue(saved_source_path_exists)
        self.assertTrue(source_payload["input_source"]["requires_restart"])
        self.assertIn("event: state", stream)
        self.assertIn('"counts"', stream)

    def test_ai_followup_endpoint_appends_explanation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.jsonl"
            actions = root / "actions.jsonl"
            ai = root / "ai.jsonl"
            config = root / "deepseek_config.json"
            events.write_text(json.dumps(_event(), ensure_ascii=False) + "\n", encoding="utf-8")
            actions.write_text(json.dumps(_action(), ensure_ascii=False) + "\n", encoding="utf-8")
            config.write_text(json.dumps({"enabled": True, "api_key": ""}), encoding="utf-8")
            server = run_live_dashboard_server(
                "127.0.0.1",
                0,
                LiveDashboardConfig(
                    events_path=events,
                    actions_path=actions,
                    ai_explanations_path=ai,
                    deepseek_config_path=config,
                    refresh_seconds=0.01,
                ),
            )
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                post = Request(base + "/ai-followup", data=b"", method="POST")
                payload = json.loads(urlopen(post, timeout=5).read().decode("utf-8"))
                state = json.loads(urlopen(base + "/state.json", timeout=5).read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()

            rows = [json.loads(line) for line in ai.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(payload["ai_followup"]["events_seen"], 1)
        self.assertEqual(payload["ai_followup"]["explanations_written"], 1)
        self.assertEqual(rows[0]["event_id"], "E1")
        self.assertEqual(rows[0]["source"], "fallback")
        self.assertEqual(state["counts"]["ai_explanations"], 1)


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
    return {
        "frame_id": 9,
        "source_type": "file",
        "class_name": "smoke",
        "confidence": 0.84,
        "bbox": [1, 2, 30, 40],
        "model_name": "safelab_fire_smoke_fp",
        "source_image": str(image_path),
    }


def _tiny_jpeg_bytes() -> bytes:
    return base64.b64decode(
        "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
        "2wBDAf//////////////////////////////////////////////////////////////////////////////////////"
        "wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/"
        "9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/"
        "9oACAEDAQE/ASP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/ASP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/"
        "9oACAEBAAY/Al//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IV//2gAMAwEAAgADAAAAEP/EFBQRAQAAAAAAAAAAAAAAAAAAABH/"
        "2gAIAQMBAT8QH//EFBQRAQAAAAAAAAAAAAAAAAAAABH/2gAIAQIBAT8QH//EFBABAQAAAAAAAAAAAAAAAAAAARD/"
        "2gAIAQEAAT8QH//Z"
    )


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
                "  board_file_demo:",
                "    source_type: board_file",
                "    board_path: /root/safelab_media/current_demo.mp4",
                "    source_name: rk_local_video",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return config


if __name__ == "__main__":
    unittest.main()

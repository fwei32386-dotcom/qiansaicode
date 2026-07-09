from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dashboard.model_detection import build_model_detection_state, save_model_detection
from dashboard.scene_mode import build_scene_mode_state, save_scene_mode
from interaction.speech_output import speak_text


DEFAULT_VOICE_COMMANDS = Path("data/events/voice_commands.jsonl")
DEFAULT_SPEECH_OUTPUT = Path("data/events/speech_output.jsonl")
DEFAULT_XIAODUO_DIALOG = Path("data/events/xiaoduo_dialog.jsonl")
DEFAULT_XIAODUO_STATE = Path("data/runtime/xiaoduo_state.json")


@dataclass(frozen=True)
class VoiceCommandSpec:
    text: str
    token: str
    command_id: str
    action_type: str
    spoken_text: str
    aliases: tuple[str, ...] = ()
    scene_mode: str | None = None
    focus: str | None = None


VOICE_COMMANDS: tuple[VoiceCommandSpec, ...] = (
    VoiceCommandSpec("小多", "xiaoduo", "wake_xiaoduo", "assistant", "我在。", ("xiao duo", "shoudao", "tts_frame")),
    VoiceCommandSpec("开始检测", "kaishijiance", "start_detection", "runtime", "检测已开启。", ("kai shi jian ce",)),
    VoiceCommandSpec("停止检测", "tingzhijiance", "stop_detection", "runtime", "检测已停止。", ("ting zhi jian ce",)),
    VoiceCommandSpec("当前状态", "dangqianzhuangtai", "status", "query", "正在查询当前状态。", ("dang qian zhuang tai",)),
    VoiceCommandSpec("为什么报警", "weishenmebaojing", "explain_alarm", "query", "正在分析报警原因。", ("wei shen me bao jing",)),
    VoiceCommandSpec("静音提示", "jingyintishi", "mute_prompt", "speech", "普通提示已静音。", ("jing yin ti shi",)),
    VoiceCommandSpec("恢复提示", "huifutishi", "unmute_prompt", "speech", "普通提示已恢复。", ("hui fu ti shi",)),
    VoiceCommandSpec("实验室模式", "shiyanshimoshi", "set_lab_mode", "scene", "已切换实验室模式。", ("shi yan shi mo shi",), scene_mode="lab"),
    VoiceCommandSpec("工地模式", "gongdimoshi", "set_site_mode", "scene", "已切换工地模式。", ("gong di mo shi",), scene_mode="construction"),
    VoiceCommandSpec("当前场景", "dangqianchangjing", "current_scene", "query", "正在查询当前场景。", ("dang qian chang jing",)),
    VoiceCommandSpec("生成报告", "shengchengbaogao", "generate_report", "report", "已收到生成报告请求。", ("sheng cheng bao gao",)),
    VoiceCommandSpec("查看烟雾", "chakanyanwu", "inspect_smoke", "ai", "正在查看烟雾风险。", ("cha kan yan wu",), focus="smoke"),
    VoiceCommandSpec("查看火焰", "chakanhuoyan", "inspect_fire", "ai", "正在查看火焰风险。", ("cha kan huo yan",), focus="fire"),
    VoiceCommandSpec("查看安全帽", "chakananquanmao", "inspect_helmet", "ai", "正在查看安全帽检测结果。", ("cha kan an quan mao",), focus="helmet"),
    VoiceCommandSpec("查看反光背心", "chakanfanguangbeixin", "inspect_vest", "ai", "正在查看反光背心检测结果。", ("cha kan fan guang bei xin",), focus="vest"),
    VoiceCommandSpec("查看危险区域", "chakanweixianquyu", "inspect_danger_zone", "ai", "正在查看危险区域。", ("cha kan wei xian qu yu",), focus="danger_zone"),
)


def known_voice_commands() -> list[dict[str, str]]:
    return [{"text": item.text, "token": item.token, "command_id": item.command_id} for item in VOICE_COMMANDS]


def handle_voice_feedback(
    raw_text: object,
    *,
    source: str = "simulated_serial",
    speak: bool = False,
    voice_commands_path: str | Path = DEFAULT_VOICE_COMMANDS,
    speech_output_path: str | Path = DEFAULT_SPEECH_OUTPUT,
    xiaoduo_dialog_path: str | Path = DEFAULT_XIAODUO_DIALOG,
    xiaoduo_state_path: str | Path = DEFAULT_XIAODUO_STATE,
    model_detection_path: str | Path = "data/runtime/model_detection.json",
    scene_mode_path: str | Path = "data/runtime/scene_mode.json",
    ai_explanations_path: str | Path = "data/events/ai_explanations.jsonl",
    actions_path: str | Path = "data/events/alarm_actions.jsonl",
    detections_path: str | Path = "reports/live_pipeline/live_dual_model_work/detections_window.jsonl",
) -> dict[str, Any]:
    raw = str(raw_text or "").strip()
    command = command_for_token(raw)
    web_result = _apply_web_feedback(command, model_detection_path, scene_mode_path, xiaoduo_state_path)
    spoken_text = _spoken_text(command, model_detection_path, scene_mode_path, ai_explanations_path, actions_path, detections_path)
    timestamp = time.time()
    command_record = {
        "timestamp": timestamp,
        "source": source,
        "raw_text": raw,
        "text": command.text,
        "token": command.token,
        "command": command.command_id,
        "action_type": command.action_type,
        "handled": command.command_id != "unknown",
        "web_result": web_result,
    }
    _append_jsonl(Path(voice_commands_path), command_record)
    speech_record = speak_text(
        spoken_text,
        log_path=speech_output_path,
        dry_run=not speak,
    )
    speech_record["speech_source"] = "voice_feedback"
    _rewrite_last_jsonl_record(Path(speech_output_path), speech_record)
    dialog_record = {
        "timestamp": timestamp,
        "assistant_name": "小多",
        "command": command_record,
        "spoken_text": spoken_text,
        "speech_record": speech_record,
        "web_result": web_result,
    }
    _append_jsonl(Path(xiaoduo_dialog_path), dialog_record)
    _write_xiaoduo_state(
        Path(xiaoduo_state_path),
        {
            "last_command": command.command_id,
            "last_raw_text": raw,
            "last_spoken_text": spoken_text,
            "last_source": source,
        },
    )
    return {**dialog_record, "known_commands": known_voice_commands()}


def command_for_token(raw_token: str) -> VoiceCommandSpec:
    normalized = _normalize(raw_token)
    for command in VOICE_COMMANDS:
        keys = (command.text, command.token, command.command_id, *command.aliases)
        if normalized in {_normalize(key) for key in keys}:
            return command
    return VoiceCommandSpec(raw_token.strip() or "未识别", raw_token.strip(), "unknown", "unknown", "未识别该语音指令。")


def _apply_web_feedback(
    command: VoiceCommandSpec,
    model_detection_path: str | Path,
    scene_mode_path: str | Path,
    xiaoduo_state_path: str | Path,
) -> dict[str, Any]:
    if command.scene_mode:
        return {"type": "scene_mode", **save_scene_mode(command.scene_mode, scene_mode_path)}
    if command.command_id in {"start_detection", "stop_detection"}:
        interval_frames = build_model_detection_state(model_detection_path)["model_detection"]["interval_frames"]
        enabled = command.command_id == "start_detection"
        return {"type": "model_detection", **save_model_detection(enabled, interval_frames, model_detection_path)}
    if command.command_id == "mute_prompt":
        return {"type": "prompt_state", "xiaoduo_state": _write_xiaoduo_state(Path(xiaoduo_state_path), {"prompt_muted": True})}
    if command.command_id == "unmute_prompt":
        return {"type": "prompt_state", "xiaoduo_state": _write_xiaoduo_state(Path(xiaoduo_state_path), {"prompt_muted": False})}
    if command.command_id == "generate_report":
        return {"type": "report_state", "xiaoduo_state": _write_xiaoduo_state(Path(xiaoduo_state_path), {"report_requested": True, "report_requested_at": time.time()})}
    if command.focus:
        return {"type": "inspection_focus", "xiaoduo_state": _write_xiaoduo_state(Path(xiaoduo_state_path), {"last_inspection_focus": command.focus})}
    return {"type": "none"}


def _spoken_text(
    command: VoiceCommandSpec,
    model_detection_path: str | Path,
    scene_mode_path: str | Path,
    ai_explanations_path: str | Path,
    actions_path: str | Path,
    detections_path: str | Path,
) -> str:
    if command.command_id == "status":
        model = build_model_detection_state(model_detection_path)["model_detection"]
        scene = build_scene_mode_state(scene_mode_path)["scene_mode"]
        detection_text = "开启" if model["enabled"] else "关闭"
        return f"当前模型检测{detection_text}，检测间隔为{model['interval_frames']}帧，当前场景是{scene['label']}。"
    if command.command_id == "current_scene":
        scene = build_scene_mode_state(scene_mode_path)["scene_mode"]
        return f"当前场景是{scene['label']}，检查项是{'、'.join(scene['required_ppe_labels'])}。"
    if command.command_id == "explain_alarm":
        return _latest_alarm_text(Path(ai_explanations_path), Path(actions_path))
    if command.focus:
        return _latest_detection_text(command.focus, Path(detections_path), command.spoken_text)
    return command.spoken_text


def _latest_alarm_text(ai_explanations_path: Path, actions_path: Path) -> str:
    for row in (_latest_jsonl(ai_explanations_path), _latest_jsonl(actions_path)):
        for key in ("voice_text", "summary", "recommendation", "message"):
            value = str(row.get(key, "")).strip()
            if value:
                return value[:90]
    return "暂时没有找到报警原因，请查看网页告警记录。"


def _latest_detection_text(focus: str, detections_path: Path, fallback: str) -> str:
    rows = _read_jsonl(detections_path)
    matches = [row for row in rows if str(row.get("class_name", "")) == focus]
    if not matches:
        return fallback
    latest = matches[-1]
    confidence = latest.get("confidence", "")
    label = {
        "smoke": "烟雾",
        "fire": "火焰",
        "helmet": "安全帽",
        "vest": "反光背心",
        "goggles": "护目镜",
        "gloves": "手套",
        "danger_zone": "危险区域",
    }.get(focus, focus)
    return f"最近一次{label}检测置信度为{confidence}，已同步到网页记录。"


def _write_xiaoduo_state(path: Path, update: dict[str, Any]) -> dict[str, Any]:
    state = _read_json(path)
    state.update(update)
    state["assistant_name"] = "小多"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _rewrite_last_jsonl_record(path: Path, record: dict[str, Any]) -> None:
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return
    lines[-1] = json.dumps(record, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _latest_jsonl(path: Path) -> dict[str, Any]:
    rows = _read_jsonl(path)
    return rows[-1] if rows else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _normalize(value: str) -> str:
    return "".join(ch for ch in value.strip().lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


COMMAND_MAP = {
    "开始检测": "start_detection",
    "启动检测": "start_detection",
    "停止检测": "stop_detection",
    "静音报警": "mute_alarm",
    "恢复报警": "unmute_alarm",
    "复位报警": "reset_alarm",
    "当前状态": "status",
    "为什么报警": "explain_alarm",
    "呼叫DeepSeek": "call_deepseek",
    "呼叫deepseek": "call_deepseek",
    "DeepSeek": "call_deepseek",
    "deepseek": "call_deepseek",
    "小安同学为什么报警": "call_deepseek",
    "生成报告": "generate_report",
    "手动截图": "snapshot",
    "截图": "snapshot",
}


@dataclass(frozen=True)
class VoiceCommand:
    raw_text: str
    command: str
    timestamp: float
    source: str = "mic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "command": self.command,
            "timestamp": self.timestamp,
            "source": self.source,
        }


def parse_voice_command(raw_text: str, source: str = "mic") -> VoiceCommand:
    text = raw_text.strip()
    return VoiceCommand(raw_text=text, command=COMMAND_MAP.get(text, "unknown"), timestamp=time.time(), source=source)


def command_to_system_action(command: VoiceCommand) -> dict[str, Any]:
    actions = {
        "start_detection": {"type": "runtime", "target_state": "running", "voice": "检测已开始。"},
        "stop_detection": {"type": "runtime", "target_state": "stopped", "voice": "检测已停止。"},
        "mute_alarm": {"type": "alarm", "muted": True, "voice": "报警已静音。"},
        "unmute_alarm": {"type": "alarm", "muted": False, "voice": "报警播报已恢复。"},
        "reset_alarm": {"type": "alarm", "reset": True, "voice": "报警状态已复位。"},
        "status": {"type": "query", "query": "status", "voice": "正在查询当前状态。"},
        "explain_alarm": {"type": "query", "query": "latest_explanation", "voice": "正在生成报警解释。"},
        "call_deepseek": {"type": "ai", "query": "latest_alarm_explanation", "voice": "正在呼叫 DeepSeek 分析最新告警。"},
        "generate_report": {"type": "report", "report": "summary", "voice": "正在生成报告摘要。"},
        "snapshot": {"type": "evidence", "snapshot": True, "voice": "已收到截图指令。"},
    }
    return {
        "command": command.to_dict(),
        "action": actions.get(command.command, {"type": "unknown", "voice": "未识别该语音指令。"}),
    }


def write_voice_command_record(
    raw_text: str,
    output_path: str | Path = "data/events/voice_commands.jsonl",
    source: str = "mic",
) -> dict[str, Any]:
    record = command_to_system_action(parse_voice_command(raw_text, source=source))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record

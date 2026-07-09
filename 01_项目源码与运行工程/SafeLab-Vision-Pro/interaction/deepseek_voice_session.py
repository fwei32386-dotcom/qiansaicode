from __future__ import annotations

from pathlib import Path
from typing import Any

from cloud.deepseek_client import explain_events_to_jsonl
from interaction.ai_speech_bridge import speak_latest_ai_explanation
from interaction.voice_command import command_to_system_action, parse_voice_command, write_voice_command_record


def handle_voice_deepseek_command(
    raw_text: str,
    events_path: str | Path = "data/events/events.jsonl",
    actions_path: str | Path = "data/events/alarm_actions.jsonl",
    config_path: str | Path = "configs/deepseek_config.json",
    ai_output_path: str | Path = "data/events/ai_explanations.jsonl",
    speech_log_path: str | Path = "data/events/speech_output.jsonl",
    voice_log_path: str | Path = "data/events/voice_commands.jsonl",
    source: str = "mic",
    dry_run: bool = True,
) -> dict[str, Any]:
    command = parse_voice_command(raw_text, source=source)
    action = command_to_system_action(command)
    voice_record = write_voice_command_record(raw_text, voice_log_path, source=source)

    if command.command not in {"call_deepseek", "explain_alarm"}:
        return {
            "command": command.to_dict(),
            "action": action["action"],
            "voice_record": voice_record,
            "handled": False,
            "detail": "voice command does not request DeepSeek",
        }

    # DeepSeek 作为智能解释层运行在语音侧链路，不改变主报警决策。
    ai_summary = explain_events_to_jsonl(
        events_path=events_path,
        actions_path=actions_path,
        output_path=ai_output_path,
        config_path=config_path,
        max_events=1,
    )
    speech_record = speak_latest_ai_explanation(ai_output_path, speech_log_path, dry_run=dry_run)
    return {
        "command": command.to_dict(),
        "action": action["action"],
        "voice_record": voice_record,
        "ai_summary": ai_summary,
        "speech_record": speech_record,
        "handled": True,
    }

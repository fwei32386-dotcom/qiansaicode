from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cloud.deepseek_client import explain_events_to_jsonl, explain_new_events_to_jsonl
from interaction.ai_speech_bridge import speak_latest_ai_explanation
from interaction.deepseek_voice_session import handle_voice_deepseek_command
from interaction.voice_command import command_to_system_action, parse_voice_command, write_voice_command_record


ROOT = Path(__file__).resolve().parents[1]


class AIInteractionTest(unittest.TestCase):
    def test_deepseek_explanations_fallback_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.jsonl"
            actions = root / "actions.jsonl"
            config = root / "deepseek_config.json"
            output = root / "ai.jsonl"
            events.write_text(json.dumps(_event(), ensure_ascii=False) + "\n", encoding="utf-8")
            actions.write_text(json.dumps(_action(), ensure_ascii=False) + "\n", encoding="utf-8")
            config.write_text(json.dumps({"enabled": True, "api_key": ""}), encoding="utf-8")
            summary = explain_events_to_jsonl(events, actions, output, config)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(summary["explanations_written"], 1)
        self.assertEqual(rows[0]["source"], "fallback")
        self.assertIn("recommendation", rows[0])
        self.assertIn("voice_text", rows[0])

    def test_fallback_explanation_localizes_internal_english_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.jsonl"
            config = root / "deepseek_config.json"
            output = root / "ai.jsonl"
            event = {
                **_event(),
                "source_type": "board_file",
                "event_type": "ppe_violation",
                "risk_level": "high",
                "reasons": [
                    "rule SCENE_LAB_GOGGLES: 实验室人员缺少护目镜; scene_mode=lab; 区域=危险区域; "
                    "zone=normal_zone; 缺失防护=护目镜, 防护手套; "
                    "SCENE_LAB_GOGGLES:board_file:0,0 连续 3 帧出现"
                ],
            }
            events.write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")
            config.write_text(json.dumps({"enabled": True, "api_key": ""}), encoding="utf-8")

            explain_events_to_jsonl(events, root / "missing_actions.jsonl", output, config)
            row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])

        visible_text = f"{row['summary']} {row['recommendation']} {row['voice_text']}"
        self.assertIn("防护违规", visible_text)
        self.assertIn("高风险", visible_text)
        self.assertIn("区域=普通区域", visible_text)
        for token in ["ppe_violation", " high", "rule ", "scene_mode", "board_file", "SCENE_LAB_GOGGLES", "normal_zone", "zone="]:
            self.assertNotIn(token, visible_text)

    def test_deepseek_followup_appends_only_new_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.jsonl"
            actions = root / "actions.jsonl"
            config = root / "deepseek_config.json"
            output = root / "ai.jsonl"
            first = _event()
            second = {**_event(), "event_id": "E2", "event_type": "fire"}
            events.write_text(
                json.dumps(first, ensure_ascii=False) + "\n" + json.dumps(second, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            actions.write_text(json.dumps(_action(), ensure_ascii=False) + "\n", encoding="utf-8")
            config.write_text(json.dumps({"enabled": True, "api_key": ""}), encoding="utf-8")
            output.write_text(json.dumps({"event_id": "E1", "summary": "old"}, ensure_ascii=False) + "\n", encoding="utf-8")

            summary = explain_new_events_to_jsonl(events, actions, output, config)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(summary["events_seen"], 2)
        self.assertEqual(summary["new_events"], 1)
        self.assertEqual(summary["explanations_written"], 1)
        self.assertEqual([row["event_id"] for row in rows], ["E1", "E2"])
        self.assertEqual(rows[0]["summary"], "old")

    def test_deepseek_followup_reads_sqlite_alarm_log_when_jsonl_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.jsonl"
            actions = root / "alarm_actions.jsonl"
            config = root / "deepseek_config.json"
            output = root / "ai.jsonl"
            _write_alarm_log_db(root / "alarm_log.db", _event(), _action())
            config.write_text(json.dumps({"enabled": True, "api_key": ""}), encoding="utf-8")

            summary = explain_new_events_to_jsonl(events, actions, output, config)
            self.assertTrue(output.exists())
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(summary["events_seen"], 1)
        self.assertEqual(summary["new_events"], 1)
        self.assertEqual(rows[0]["event_id"], "E1")
        self.assertEqual(rows[0]["source"], "fallback")

    def test_voice_command_maps_fixed_commands(self) -> None:
        command = parse_voice_command("为什么报警", source="test")
        action = command_to_system_action(command)
        self.assertEqual(command.command, "explain_alarm")
        self.assertEqual(action["action"]["query"], "latest_explanation")
        self.assertEqual(action["action"]["voice"], "正在生成报警解释。")

    def test_voice_command_record_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "voice.jsonl"
            record = write_voice_command_record("当前状态", output, source="test")
            rows = output.read_text(encoding="utf-8").splitlines()

        self.assertEqual(record["command"]["command"], "status")
        self.assertEqual(record["action"]["query"], "status")
        self.assertEqual(len(rows), 1)

    def test_latest_ai_explanation_can_be_recorded_as_speech_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ai = root / "ai_explanations.jsonl"
            speech = root / "speech_output.jsonl"
            ai.write_text(
                "\n".join(
                    [
                        json.dumps({"event_id": "E1", "voice_text": "旧告警，不播报"}, ensure_ascii=False),
                        json.dumps({"event_id": "E2", "source": "fallback", "voice_text": "检测到高风险，请立即复核现场。"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            record = speak_latest_ai_explanation(ai, speech, dry_run=True)
            rows = [json.loads(line) for line in speech.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(record["event_id"], "E2")
        self.assertEqual(record["text"], "检测到高风险，请立即复核现场。")
        self.assertEqual(rows[0]["event_id"], "E2")
        self.assertEqual(rows[0]["speech_source"], "ai_explanation")

    def test_speak_latest_ai_explanation_tool_writes_speech_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ai = root / "ai.jsonl"
            speech = root / "speech.jsonl"
            ai.write_text(json.dumps({"event_id": "E3", "voice_text": "请立即处理高风险告警。"}, ensure_ascii=False) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "speak_latest_ai_explanation.py"),
                    "--ai-explanations",
                    str(ai),
                    "--log",
                    str(speech),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            payload = json.loads(result.stdout)
            rows = [json.loads(line) for line in speech.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["event_id"], "E3")
        self.assertEqual(rows[0]["text"], "请立即处理高风险告警。")

    def test_voice_can_wake_deepseek_and_speak_latest_alarm_explanation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.jsonl"
            actions = root / "actions.jsonl"
            config = root / "deepseek_config.json"
            ai = root / "ai.jsonl"
            speech = root / "speech.jsonl"
            voice = root / "voice.jsonl"
            events.write_text(json.dumps(_event(), ensure_ascii=False) + "\n", encoding="utf-8")
            actions.write_text(json.dumps(_action(), ensure_ascii=False) + "\n", encoding="utf-8")
            config.write_text(json.dumps({"enabled": True, "api_key": ""}), encoding="utf-8")

            result = handle_voice_deepseek_command(
                "呼叫DeepSeek",
                events_path=events,
                actions_path=actions,
                config_path=config,
                ai_output_path=ai,
                speech_log_path=speech,
                voice_log_path=voice,
                source="test",
                dry_run=True,
            )
            ai_rows = [json.loads(line) for line in ai.read_text(encoding="utf-8").splitlines()]
            speech_rows = [json.loads(line) for line in speech.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(result["command"]["command"], "call_deepseek")
        self.assertEqual(result["ai_summary"]["explanations_written"], 1)
        self.assertEqual(ai_rows[0]["source"], "fallback")
        self.assertEqual(speech_rows[0]["speech_source"], "ai_explanation")
        self.assertEqual(speech_rows[0]["event_id"], "E1")

    def test_voice_deepseek_session_tool_runs_from_recognized_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.jsonl"
            actions = root / "actions.jsonl"
            config = root / "deepseek_config.json"
            ai = root / "ai.jsonl"
            speech = root / "speech.jsonl"
            voice = root / "voice.jsonl"
            events.write_text(json.dumps(_event(), ensure_ascii=False) + "\n", encoding="utf-8")
            actions.write_text(json.dumps(_action(), ensure_ascii=False) + "\n", encoding="utf-8")
            config.write_text(json.dumps({"enabled": True, "api_key": ""}), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "voice_deepseek_session.py"),
                    "为什么报警",
                    "--events",
                    str(events),
                    "--actions",
                    str(actions),
                    "--config",
                    str(config),
                    "--ai-output",
                    str(ai),
                    "--speech-log",
                    str(speech),
                    "--voice-log",
                    str(voice),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 0)
        self.assertTrue(payload["handled"])
        self.assertEqual(payload["command"]["command"], "explain_alarm")
        self.assertEqual(payload["speech_record"]["event_id"], "E1")


def _event() -> dict[str, object]:
    return {
        "event_id": "E1",
        "frame_id": 10,
        "source_type": "camera",
        "event_type": "ppe_violation",
        "risk_score": 80,
        "risk_level": "high",
        "reasons": ["危险区域内人员未佩戴安全帽"],
    }


def _action() -> dict[str, object]:
    return {
        "event_id": "E1",
        "voice_text": "PPE violation detected.",
        "led_color": "red",
        "buzzer": True,
    }


def _write_alarm_log_db(path: Path, event: dict[str, object], action: dict[str, object]) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "create table events (id integer primary key autoincrement, event_id text not null, frame_id integer, source_type text, event_type text, risk_score integer, risk_level text, timestamp real, payload_json text not null)"
        )
        conn.execute(
            "create table alarm_actions (id integer primary key autoincrement, event_id text not null, voice_text text, led_color text, buzzer integer, relay integer, snapshot integer, log integer, cooldown_ms integer, payload_json text not null)"
        )
        conn.execute(
            "insert into events (event_id, frame_id, source_type, event_type, risk_score, risk_level, timestamp, payload_json) values (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event["event_id"],
                event.get("frame_id"),
                event.get("source_type"),
                event.get("event_type"),
                event.get("risk_score"),
                event.get("risk_level"),
                event.get("timestamp", 0.0),
                json.dumps(event, ensure_ascii=False),
            ),
        )
        conn.execute(
            "insert into alarm_actions (event_id, voice_text, led_color, buzzer, relay, snapshot, log, cooldown_ms, payload_json) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                action["event_id"],
                action.get("voice_text"),
                action.get("led_color"),
                int(bool(action.get("buzzer"))),
                int(bool(action.get("relay", False))),
                int(bool(action.get("snapshot", True))),
                int(bool(action.get("log", True))),
                action.get("cooldown_ms", 20000),
                json.dumps(action, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    unittest.main()

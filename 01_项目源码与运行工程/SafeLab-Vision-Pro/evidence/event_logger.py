from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class EventLogger:
    def __init__(self, output_dir: str | Path = "data/events") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.output_dir / "events.jsonl"
        self.actions_path = self.output_dir / "alarm_actions.jsonl"
        self.db_path = self.output_dir / "alarm_log.db"
        self._ensure_db()

    def log_event(self, payload: dict[str, Any]) -> None:
        self._append_jsonl(self.events_path, payload)
        self._insert_event(payload)

    def log_action(self, payload: dict[str, Any]) -> None:
        self._append_jsonl(self.actions_path, payload)
        self._insert_action(payload)

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _ensure_db(self) -> None:
        # SQLite mirrors the JSONL evidence stream so board demos can query
        # structured event/action history without giving up append-only logs.
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                create table if not exists events (
                    id integer primary key autoincrement,
                    event_id text not null,
                    frame_id integer,
                    source_type text,
                    event_type text,
                    risk_score integer,
                    risk_level text,
                    timestamp real,
                    payload_json text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists alarm_actions (
                    id integer primary key autoincrement,
                    event_id text not null,
                    voice_text text,
                    led_color text,
                    buzzer integer,
                    relay integer,
                    snapshot integer,
                    log integer,
                    cooldown_ms integer,
                    payload_json text not null
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _insert_event(self, payload: dict[str, Any]) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                insert into events (
                    event_id, frame_id, source_type, event_type, risk_score,
                    risk_level, timestamp, payload_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(payload.get("event_id", "")),
                    payload.get("frame_id"),
                    payload.get("source_type"),
                    payload.get("event_type"),
                    payload.get("risk_score"),
                    payload.get("risk_level"),
                    payload.get("timestamp"),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _insert_action(self, payload: dict[str, Any]) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                insert into alarm_actions (
                    event_id, voice_text, led_color, buzzer, relay, snapshot,
                    log, cooldown_ms, payload_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(payload.get("event_id", "")),
                    payload.get("voice_text"),
                    payload.get("led_color"),
                    self._bool_to_int(payload.get("buzzer")),
                    self._bool_to_int(payload.get("relay")),
                    self._bool_to_int(payload.get("snapshot")),
                    self._bool_to_int(payload.get("log")),
                    payload.get("cooldown_ms"),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _bool_to_int(value: Any) -> int:
        return 1 if bool(value) else 0

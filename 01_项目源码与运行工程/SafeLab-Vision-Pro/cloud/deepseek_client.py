from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://api.deepseek.com"

EVENT_TYPE_LABELS = {
    "ppe_violation": "防护违规",
    "forbidden_intrusion": "禁区入侵",
    "fire": "火焰风险",
    "smoke": "烟雾风险",
    "risk": "安全风险",
}

RISK_LEVEL_LABELS = {
    "emergency": "紧急",
    "high": "高风险",
    "warning": "预警",
    "medium": "中风险",
    "low": "低风险",
    "idle": "空闲",
    "unknown": "未知",
}

INTERNAL_TEXT_REPLACEMENTS = (
    ("rule SCENE_LAB_GOGGLES:", "实验室护目镜规则："),
    ("rule R004: goggles missing in welding zone", "规则 R004：焊接区域缺少护目镜"),
    ("rule R001: helmet missing in danger zone", "规则 R001：危险区域缺少安全帽"),
    ("ppe_violation", "防护违规"),
    ("forbidden_intrusion", "禁区入侵"),
    ("scene_mode=lab", "场景=实验室"),
    ("scene_mode=construction", "场景=工地"),
    ("zone=normal_zone", "区域=普通区域"),
    ("normal_zone", "普通区域"),
    ("source_type=board_file", "输入源=本地媒体"),
    ("source_type=camera", "输入源=摄像头"),
    ("source_type=file", "输入源=本地文件"),
    ("board_file", "本地媒体"),
    ("danger_zone", "危险区域"),
    ("welding_zone", "焊接区域"),
    ("missing_ppe=", "缺失防护="),
    ("suppressed_rules=", "关联风险="),
    ("helmet", "安全帽"),
    ("vest", "反光背心"),
    ("goggles", "护目镜"),
    ("gloves", "防护手套"),
    ("fire appeared for 3 consecutive frames", "连续 3 帧检测到火焰"),
    ("smoke appeared for 3 consecutive frames", "连续 3 帧检测到烟雾"),
)


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    model: str = "deepseek-chat"
    base_url: str = DEFAULT_BASE_URL
    timeout_s: float = 8.0
    max_tokens: int = 240
    temperature: float = 0.2
    enabled: bool = True


class DeepSeekClient:
    def __init__(self, config: DeepSeekConfig) -> None:
        self.config = config

    def explain_event(self, event: dict[str, Any], action: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.config.enabled:
            return _fallback_explanation(event, "deepseek disabled")
        if not self.config.api_key:
            return _fallback_explanation(event, "DEEPSEEK_API_KEY missing")
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 SafeLab-Vision Pro 的安全告警解释助手。"
                        "只解释结构化边缘安全事件，不改变报警决策。"
                        "输出 JSON，字段为 summary、recommendation、voice_text。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "event": _compact_event(event),
                            "action": action or {},
                            "voice_text_limit": "45 Chinese characters",
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            response = self._post_chat_completions(payload)
            content = response["choices"][0]["message"]["content"]
            return _normalize_explanation(event, json.loads(content), "deepseek")
        except Exception as exc:  # pragma: no cover - network failures vary by environment
            return _fallback_explanation(event, f"deepseek request failed: {exc}")

    def _post_chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.config.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=self.config.timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))


def load_deepseek_config(path: str | Path = "configs/deepseek_config.json") -> DeepSeekConfig:
    raw: dict[str, Any] = {}
    config_path = Path(path)
    if config_path.exists():
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    return DeepSeekConfig(
        api_key=str(raw.get("api_key") or os.environ.get("DEEPSEEK_API_KEY", "")),
        model=str(raw.get("model", "deepseek-chat")),
        base_url=str(raw.get("base_url", DEFAULT_BASE_URL)),
        timeout_s=float(raw.get("timeout_s", 8.0)),
        max_tokens=int(raw.get("max_tokens", 240)),
        temperature=float(raw.get("temperature", 0.2)),
        enabled=bool(raw.get("enabled", True)),
    )


def explain_events_to_jsonl(
    events_path: str | Path = "data/events/events.jsonl",
    actions_path: str | Path = "data/events/alarm_actions.jsonl",
    output_path: str | Path = "data/events/ai_explanations.jsonl",
    config_path: str | Path = "configs/deepseek_config.json",
    max_events: int = 5,
) -> dict[str, Any]:
    events = _read_event_records(Path(events_path))
    actions = _read_action_records(Path(actions_path))
    action_by_event = {str(action.get("event_id")): action for action in actions}
    client = DeepSeekClient(load_deepseek_config(config_path))
    explanations = [client.explain_event(event, action_by_event.get(str(event.get("event_id")))) for event in events[-max_events:]]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for explanation in explanations:
            f.write(json.dumps(explanation, ensure_ascii=False) + "\n")
    return {
        "events_seen": len(events),
        "explanations_written": len(explanations),
        "output": str(output),
        "source": "deepseek" if any(item.get("source") == "deepseek" for item in explanations) else "fallback",
    }


def explain_new_events_to_jsonl(
    events_path: str | Path = "data/events/events.jsonl",
    actions_path: str | Path = "data/events/alarm_actions.jsonl",
    output_path: str | Path = "data/events/ai_explanations.jsonl",
    config_path: str | Path = "configs/deepseek_config.json",
    max_events: int = 5,
) -> dict[str, Any]:
    events = _read_event_records(Path(events_path))
    actions = _read_action_records(Path(actions_path))
    output = Path(output_path)
    existing = _read_jsonl(output)
    explained_ids = {str(item.get("event_id")) for item in existing if item.get("event_id")}
    new_events = _select_new_events(events, explained_ids, max_events=max_events)
    if not new_events:
        return {
            "events_seen": len(events),
            "new_events": 0,
            "explanations_written": 0,
            "output": str(output),
            "source": "none",
        }

    action_by_event = {str(action.get("event_id")): action for action in actions if action.get("event_id")}
    client = DeepSeekClient(load_deepseek_config(config_path))
    explanations = [
        client.explain_event(event, action_by_event.get(str(event.get("event_id"))))
        for event in new_events
    ]
    _append_jsonl(output, explanations)
    return {
        "events_seen": len(events),
        "new_events": len(new_events),
        "explanations_written": len(explanations),
        "output": str(output),
        "source": "deepseek" if any(item.get("source") == "deepseek" for item in explanations) else "fallback",
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _read_event_records(path: Path) -> list[dict[str, Any]]:
    rows = _read_jsonl(path)
    if rows:
        return rows
    return _read_alarm_log_table(path.parent / "alarm_log.db", "events")


def _read_action_records(path: Path) -> list[dict[str, Any]]:
    rows = _read_jsonl(path)
    if rows:
        return rows
    return _read_alarm_log_table(path.parent / "alarm_log.db", "alarm_actions")


def _read_alarm_log_table(db_path: Path, table: str) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            records = conn.execute(f"select * from {table} order by id").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []

    rows: list[dict[str, Any]] = []
    for record in records:
        try:
            payload = json.loads(record["payload_json"])
        except (KeyError, TypeError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        for key in record.keys():
            if key not in {"id", "payload_json"} and key not in payload:
                payload[key] = record[key]
        rows.append(payload)
    return rows


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _select_new_events(
    events: list[dict[str, Any]],
    explained_ids: set[str],
    *,
    max_events: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for event in events:
        event_id = str(event.get("event_id") or event.get("id") or "")
        if not event_id or event_id in explained_ids:
            continue
        selected.append(event)
    return selected[-max_events:]


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    keys = ["event_id", "frame_id", "source_type", "event_type", "risk_score", "risk_level", "reasons", "rule_id", "timestamp"]
    return {key: event.get(key) for key in keys if key in event}


def _normalize_explanation(event: dict[str, Any], parsed: dict[str, Any], source: str) -> dict[str, Any]:
    fallback = _fallback_explanation(event, "")
    return {
        "event_id": str(event.get("event_id", "")),
        "timestamp": time.time(),
        "source": source,
        "summary": str(parsed.get("summary") or fallback["summary"]),
        "recommendation": str(parsed.get("recommendation") or fallback["recommendation"]),
        "voice_text": str(parsed.get("voice_text") or fallback["voice_text"])[:80],
        "error": "",
    }


def _fallback_explanation(event: dict[str, Any], error: str) -> dict[str, Any]:
    reasons = event.get("reasons") or []
    reason_text = _localize_reason_text("；".join(str(reason) for reason in reasons)) or "系统检测到安全风险"
    level = _risk_level_label(event.get("risk_level", "unknown"))
    event_type = _event_type_label(event.get("event_type", "risk"))
    return {
        "event_id": str(event.get("event_id", "")),
        "timestamp": time.time(),
        "source": "fallback",
        "summary": f"{event_type}，风险等级为{level}。原因：{reason_text}。",
        "recommendation": "请现场人员立即复核风险区域，并按安全规程处理。",
        "voice_text": f"检测到{level}{event_type}，请立即复核现场。",
        "error": error,
    }


def _event_type_label(value: object) -> str:
    raw = str(value or "risk")
    return EVENT_TYPE_LABELS.get(raw, raw)


def _risk_level_label(value: object) -> str:
    raw = str(value or "unknown")
    return RISK_LEVEL_LABELS.get(raw, raw)


def _localize_reason_text(value: str) -> str:
    text = value.strip()
    for source, target in INTERNAL_TEXT_REPLACEMENTS:
        text = text.replace(source, target)
    text = re.sub(r"\bSCENE_LAB_GOGGLES:(?:本地媒体|camera|file):[\d,]+", "", text)
    text = re.sub(r"\bR(\d{3}):\d+,\d+,\d+,\d+", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.replace("; ", "；").replace(" ;", "；").replace(";", "；")
    text = text.replace(" high", " 高风险").replace("=high", "=高风险")
    text = text.strip(" ；，,")
    return text

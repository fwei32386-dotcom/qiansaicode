from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from interaction.speech_output import speak_text


def speak_latest_ai_explanation(
    ai_explanations_path: str | Path = "data/events/ai_explanations.jsonl",
    speech_log_path: str | Path = "data/events/speech_output.jsonl",
    dry_run: bool = True,
) -> dict[str, Any]:
    explanations = _read_jsonl(Path(ai_explanations_path))
    if not explanations:
        return {
            "event_id": "",
            "text": "",
            "speech_source": "ai_explanation",
            "executed": False,
            "detail": "no AI explanation available",
        }

    # 语音播报只消费最新解释，避免历史告警重新生成时被重复播报。
    latest = explanations[-1]
    text = str(latest.get("voice_text") or latest.get("summary") or "").strip()
    if not text:
        text = "检测到安全风险，请立即复核现场。"

    record = speak_text(text, speech_log_path, dry_run=dry_run)
    record.update(
        {
            "event_id": str(latest.get("event_id", "")),
            "speech_source": "ai_explanation",
            "ai_source": str(latest.get("source", "")),
        }
    )
    _rewrite_last_jsonl_record(Path(speech_log_path), record)
    return record


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _rewrite_last_jsonl_record(path: Path, record: dict[str, Any]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    if lines:
        lines[-1] = json.dumps(record, ensure_ascii=False)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from runtime.interfaces import AlarmAction, RiskEvent


def write_alarm_dashboard(
    events: list[RiskEvent],
    actions: list[AlarmAction],
    actuator_records: list[dict[str, Any]],
    output_path: str | Path = "reports/alarm_dashboard.html",
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render(events, actions, actuator_records), encoding="utf-8")
    return path


def _render(
    events: list[RiskEvent],
    actions: list[AlarmAction],
    actuator_records: list[dict[str, Any]],
) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>SafeLab 告警复盘</title>
  <style>
    body {{ margin: 0; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; color: #172026; background: #f7f8fa; }}
    header {{ padding: 20px 28px; background: #111827; color: white; }}
    main {{ padding: 24px 28px; }}
    .summary {{ display: grid; grid-template-columns: repeat(3, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }}
    .metric {{ background: white; border: 1px solid #d8dee4; padding: 14px; border-radius: 6px; }}
    .metric strong {{ display: block; font-size: 26px; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; margin: 12px 0 24px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 9px; text-align: left; font-size: 14px; vertical-align: top; }}
    th {{ background: #eef1f4; }}
    .high, .emergency {{ color: #b42318; font-weight: bold; }}
    .warning {{ color: #b54708; font-weight: bold; }}
    .notice {{ color: #175cd3; font-weight: bold; }}
  </style>
</head>
<body>
  <header>
    <h1>SafeLab 告警复盘</h1>
  </header>
  <main>
    <section class="summary">
      <div class="metric">事件<strong>{len(events)}</strong></div>
      <div class="metric">动作<strong>{len(actions)}</strong></div>
      <div class="metric">执行器记录<strong>{len(actuator_records)}</strong></div>
    </section>
    <h2>风险事件</h2>
    {_events_table(events)}
    <h2>告警动作</h2>
    {_actions_table(actions)}
    <h2>执行器执行记录</h2>
    {_actuator_table(actuator_records)}
  </main>
</body>
</html>
"""


def _events_table(events: list[RiskEvent]) -> str:
    rows = ["<tr><th>ID</th><th>类型</th><th>等级</th><th>分数</th><th>原因</th></tr>"]
    rows.extend(
        f"<tr><td>{escape(e.event_id)}</td><td>{escape(e.event_type)}</td>"
        f"<td class=\"{escape(e.risk_level)}\">{escape(e.risk_level)}</td><td>{e.risk_score}</td>"
        f"<td>{escape('; '.join(_translate_reason(reason) for reason in e.reasons))}</td></tr>"
        for e in events
    )
    return "<table>" + "".join(rows) + "</table>"


def _actions_table(actions: list[AlarmAction]) -> str:
    rows = ["<tr><th>事件</th><th>语音</th><th>灯光</th><th>蜂鸣</th><th>冷却时间</th></tr>"]
    rows.extend(
        f"<tr><td>{escape(a.event_id)}</td><td>{escape(_translate_voice(a.voice_text))}</td>"
        f"<td>{escape(a.led_color)}</td><td>{a.buzzer}</td><td>{a.cooldown_ms}</td></tr>"
        for a in actions
    )
    return "<table>" + "".join(rows) + "</table>"


def _actuator_table(records: list[dict[str, Any]]) -> str:
    rows = ["<tr><th>事件</th><th>语音</th><th>灯光</th><th>蜂鸣</th><th>后端</th></tr>"]
    rows.extend(
        f"<tr><td>{escape(str(r.get('event_id', '')))}</td>"
        f"<td>{escape(_translate_voice(str(r.get('voice', {}).get('text', ''))))}</td>"
        f"<td>{escape(str(r.get('led', {}).get('color', '')))}</td>"
        f"<td>{escape(str(r.get('buzzer', {}).get('enabled', False)))}</td>"
        f"<td>{escape(str(r.get('backend', '')))}</td></tr>"
        for r in records
    )
    return "<table>" + "".join(rows) + "</table>"


def _translate_reason(reason: str) -> str:
    value = reason
    replacements = {
        "smoke appeared for 3 consecutive frames": "连续 3 帧检测到烟雾",
        "fire detected by vision model": "视觉模型检测到火焰",
        "rule R004: goggles missing in welding zone": "规则 R004：焊接区域缺少护目镜",
        "rule R001: helmet missing in danger zone": "规则 R001：危险区域缺少安全帽",
        "person intrusion in danger zone": "人员进入危险区域",
        "zone=welding_zone": "区域=焊接区域",
        "zone=danger_zone": "区域=危险区域",
        "missing_ppe=": "缺失防护=",
        "helmet": "安全帽",
        "vest": "反光背心",
        "goggles": "护目镜",
        "gloves": "手套",
        "appeared for 3 consecutive frames": "连续 3 帧出现",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


def _translate_voice(voice: str) -> str:
    replacements = {
        "Smoke risk detected. Please check the lab.": "检测到烟雾风险，请立即复核现场。",
        "Goggles missing in welding zone. Please wear eye protection.": "焊接区域缺少护目镜，请佩戴眼部防护。",
        "Helmet missing in danger zone. Please correct immediately.": "危险区域缺少安全帽，请立即纠正。",
    }
    return replacements.get(voice, voice)

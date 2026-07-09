from __future__ import annotations

from html import escape
from pathlib import Path

from runtime.interfaces import AlarmAction, Detection, RiskEvent


def write_html_report(
    detections: list[Detection],
    events: list[RiskEvent],
    actions: list[AlarmAction],
    output_path: str | Path = "reports/latest_report.html",
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render(detections, events, actions), encoding="utf-8")
    return path


def _render(
    detections: list[Detection],
    events: list[RiskEvent],
    actions: list[AlarmAction],
) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>SafeLab 检测报告</title>
  <style>
    body {{ font-family: "Microsoft YaHei", "Segoe UI", sans-serif; margin: 24px; color: #1f2933; }}
    h1, h2 {{ margin-bottom: 8px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
    th, td {{ border: 1px solid #d0d7de; padding: 8px; text-align: left; font-size: 14px; }}
    th {{ background: #f6f8fa; }}
    .high, .emergency {{ color: #b42318; font-weight: bold; }}
    .warning {{ color: #b54708; font-weight: bold; }}
  </style>
</head>
<body>
  <h1>SafeLab 检测报告</h1>
  <p>检测: {len(detections)} | 事件: {len(events)} | 动作: {len(actions)}</p>
  <h2>检测结果</h2>
  {_detection_table(detections)}
  <h2>风险事件</h2>
  {_event_table(events)}
  <h2>告警动作</h2>
  {_action_table(actions)}
</body>
</html>
"""


def _detection_table(items: list[Detection]) -> str:
    rows = [
        "<tr><th>帧 ID</th><th>来源</th><th>类别</th><th>置信度</th><th>位置框</th><th>推理耗时</th></tr>"
    ]
    rows.extend(
        f"<tr><td>{d.frame_id}</td><td>{escape(d.source_type)}</td><td>{escape(d.class_name)}</td>"
        f"<td>{d.confidence:.2f}</td><td>{escape(str(d.bbox))}</td><td>{d.infer_time_ms:.2f}</td></tr>"
        for d in items
    )
    return "<table>" + "".join(rows) + "</table>"


def _event_table(items: list[RiskEvent]) -> str:
    rows = [
        "<tr><th>事件 ID</th><th>类型</th><th>分数</th><th>等级</th><th>原因</th><th>位置框</th></tr>"
    ]
    rows.extend(
        f"<tr><td>{escape(e.event_id)}</td><td>{escape(e.event_type)}</td><td>{e.risk_score}</td>"
        f"<td class=\"{escape(e.risk_level)}\">{escape(e.risk_level)}</td>"
        f"<td>{escape('; '.join(e.reasons))}</td><td>{escape(str(e.bbox))}</td></tr>"
        for e in items
    )
    return "<table>" + "".join(rows) + "</table>"


def _action_table(items: list[AlarmAction]) -> str:
    rows = [
        "<tr><th>事件 ID</th><th>语音</th><th>灯光</th><th>蜂鸣</th><th>截图</th><th>冷却时间</th></tr>"
    ]
    rows.extend(
        f"<tr><td>{escape(a.event_id)}</td><td>{escape(a.voice_text)}</td><td>{escape(a.led_color)}</td>"
        f"<td>{a.buzzer}</td><td>{a.snapshot}</td><td>{a.cooldown_ms}</td></tr>"
        for a in items
    )
    return "<table>" + "".join(rows) + "</table>"

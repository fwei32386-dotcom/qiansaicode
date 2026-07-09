from __future__ import annotations

from html import escape
from pathlib import Path

from runtime.interfaces import Detection, RiskEvent


class SnapshotManager:
    def __init__(
        self,
        raw_dir: str | Path = "data/events/raw",
        marked_dir: str | Path = "data/events/marked",
    ) -> None:
        self.raw_dir = Path(raw_dir)
        self.marked_dir = Path(marked_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.marked_dir.mkdir(parents=True, exist_ok=True)

    def save_event_snapshot(
        self,
        event: RiskEvent,
        detections: list[Detection],
        width: int = 960,
        height: int = 760,
    ) -> dict[str, str]:
        raw_path = self.raw_dir / f"{event.event_id}_raw.svg"
        marked_path = self.marked_dir / f"{event.event_id}_marked.svg"
        raw_path.write_text(_render_raw_placeholder(event, width, height), encoding="utf-8")
        marked_path.write_text(_render_marked_snapshot(event, detections, width, height), encoding="utf-8")
        return {"raw": str(raw_path), "marked": str(marked_path)}


def _render_raw_placeholder(event: RiskEvent, width: int, height: int) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f8fafc"/>
  <text x="32" y="48" font-family="Arial" font-size="24" fill="#111827">SafeLab Raw Snapshot Placeholder</text>
  <text x="32" y="86" font-family="Arial" font-size="16" fill="#475467">event_id={escape(event.event_id)} frame_id={event.frame_id}</text>
  <text x="32" y="116" font-family="Arial" font-size="16" fill="#475467">source={escape(event.source_type)} type={escape(event.event_type)}</text>
</svg>
"""


def _render_marked_snapshot(
    event: RiskEvent,
    detections: list[Detection],
    width: int,
    height: int,
) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#fbfcfd"/>
  <text x="28" y="38" font-family="Arial" font-size="24" font-weight="700" fill="#111827">SafeLab Marked Evidence</text>
  <text x="28" y="68" font-family="Arial" font-size="15" fill="#475467">{escape(event.event_id)} | {escape(event.event_type)} | {escape(event.risk_level)} | score {event.risk_score}</text>
  {_detection_svg(detections)}
  {_event_box_svg(event)}
  {_reasons_svg(event)}
</svg>
"""


def _detection_svg(detections: list[Detection]) -> str:
    colors = {
        "person": "#111827",
        "helmet": "#16a34a",
        "vest": "#f59e0b",
        "smoke": "#6b7280",
        "fire": "#dc2626",
    }
    parts: list[str] = []
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox
        color = colors.get(detection.class_name, "#111827")
        parts.append(
            f'<rect x="{x1}" y="{y1}" width="{x2 - x1}" height="{y2 - y1}" '
            f'fill="none" stroke="{color}" stroke-width="3" opacity="0.8"/>'
        )
        parts.append(
            f'<text x="{x1}" y="{max(y1 - 6, 96)}" font-family="Arial" font-size="15" fill="{color}">'
            f'{escape(detection.class_name)} {detection.confidence:.2f}</text>'
        )
    return "\n  ".join(parts)


def _event_box_svg(event: RiskEvent) -> str:
    x1, y1, x2, y2 = event.bbox
    color = "#b42318" if event.risk_level in ("high", "emergency") else "#b54708"
    return (
        f'<rect x="{x1}" y="{y1}" width="{x2 - x1}" height="{y2 - y1}" '
        f'fill="none" stroke="{color}" stroke-width="6" stroke-dasharray="10 6"/>'
    )


def _reasons_svg(event: RiskEvent) -> str:
    y = 700
    lines = [
        f'<text x="28" y="{y}" font-family="Arial" font-size="16" font-weight="700" fill="#111827">Reasons</text>'
    ]
    for index, reason in enumerate(event.reasons[:4], start=1):
        lines.append(
            f'<text x="28" y="{y + index * 22}" font-family="Arial" font-size="15" fill="#344054">{index}. {escape(reason)}</text>'
        )
    return "\n  ".join(lines)

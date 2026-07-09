from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REPLACEMENTS = {
    "SafeLab Live Dashboard": "SafeLab 实时演示看板",
    "SafeLab Alarm Dashboard": "SafeLab 告警复盘",
    "SafeLab-Vision Pro Report": "SafeLab 检测报告",
    "SafeLab Final Acceptance Report": "SafeLab 最终验收报告",
    "SafeLab Config Audit": "SafeLab 配置审计",
    "Risk Events": "风险事件",
    "Alarm Actions": "告警动作",
    "AI Explanation": "AI 说明",
    "Actuator Records": "执行器记录",
    "Runtime": "运行状态",
    "Metrics": "指标",
    "Detections": "检测结果",
    "Events": "事件",
    "Actions": "动作",
    "High Risk": "高风险",
    "Mock Actuator Records": "执行器记录",
    "Mock Actuator Execution": "执行器执行记录",
    "Acceptance Checks": "验收检查项",
    "Evidence Digest": "证据摘要",
    "Remaining Blockers": "剩余待确认项",
    "Next Actions": "后续动作",
    "Completion": "验收完成度",
    "Board path:": "板端路径：",
    "last refresh": "最近刷新",
    "waiting for data": "等待数据",
    "no events yet": "暂无事件",
    "no actions yet": "暂无动作",
    "no AI explanations yet": "暂无 AI 说明",
    "no actuator records yet": "暂无执行器记录",
    "Smoke risk detected. Please check the lab.": "检测到烟雾风险，请立即复核现场。",
    "Goggles missing in welding zone. Please wear eye protection.": "焊接区域缺少护目镜，请佩戴眼部防护。",
    "Helmet missing in danger zone. Please correct immediately.": "危险区域缺少安全帽，请立即纠正。",
    "smoke appeared for 3 consecutive frames": "连续 3 帧检测到烟雾",
    "fire detected by vision model": "视觉模型检测到火焰",
    "rule R004: goggles missing in welding zone": "规则 R004：焊接区域缺少护目镜",
    "rule R001: helmet missing in danger zone": "规则 R001：危险区域缺少安全帽",
    "zone=welding_zone": "区域=焊接区域",
    "zone=danger_zone": "区域=危险区域",
    "missing_ppe=": "缺失防护=",
    "helmet": "安全帽",
    "vest": "反光背心",
    "goggles": "护目镜",
    "gloves": "手套",
    "<th>Event</th>": "<th>事件</th>",
    "<th>Voice</th>": "<th>语音</th>",
    "<th>LED</th>": "<th>灯光</th>",
    "<th>Buzzer</th>": "<th>蜂鸣</th>",
    "<th>Cooldown</th>": "<th>冷却时间</th>",
    "<th>Backend</th>": "<th>后端</th>",
    "<th>Type</th>": "<th>类型</th>",
    "<th>Level</th>": "<th>等级</th>",
    "<th>Score</th>": "<th>分数</th>",
    "<th>Reasons</th>": "<th>原因</th>",
}


def localize_report_pages(reports_dir: str | Path = ROOT / "reports") -> list[str]:
    reports_dir = Path(reports_dir)
    changed: list[str] = []
    for path in reports_dir.glob("*.html"):
        original = path.read_text(encoding="utf-8", errors="replace")
        localized = original.replace('<html lang="en">', '<html lang="zh-CN">')
        for old, new in REPLACEMENTS.items():
            localized = localized.replace(old, new)
        if localized != original:
            path.write_text(localized, encoding="utf-8")
            changed.append(str(path))
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Localize generated SafeLab report HTML pages.")
    parser.add_argument("--reports-dir", default=str(ROOT / "reports"))
    args = parser.parse_args()
    for item in localize_report_pages(args.reports_dir):
        print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

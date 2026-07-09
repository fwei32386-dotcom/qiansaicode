from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REPORT_GROUPS = {
    "仪表盘": [
        "alarm_dashboard.html",
        "live_dashboard.html",
        "board_camera_preview.html",
        "replay_alarm_dashboard.html",
        "scene_visualization.html",
        "risk_curve.html",
    ],
    "报告": [
        "latest_report.html",
        "replay_latest_report.html",
        "project_status.html",
        "project_status.md",
        "final_acceptance_report.html",
        "config_audit.html",
        "scenario_catalog.html",
    ],
    "评估数据": [
        "batch_eval_report.csv",
        "batch_eval_summary.json",
        "replay_event_report.csv",
        "replay_timeline.json",
        "pipeline_latency.csv",
        "pipeline_latency_summary.json",
        "frame_scheduler_trace.csv",
        "frame_scheduler_summary.json",
        "event_bus_trace.csv",
        "event_bus_summary.json",
        "fallback_summary.json",
        "watchdog_summary.json",
        "main_loop_summary.json",
        "camera_live_preview_benchmark.json",
        "latest_frame_buffer_summary.json",
        "track_manager_trace.csv",
        "track_manager_summary.json",
        "roi_manager_trace.csv",
        "roi_manager_summary.json",
        "actuator_backends_trace.csv",
        "actuator_backends_summary.json",
        "live_dashboard_state.json",
        "runtime_status.json",
        "runtime_status.txt",
        "start_safelab_report.txt",
        "status_safelab_report.txt",
        "stop_safelab_report.txt",
        "board_connection_check.txt",
        "board_connection_check.json",
        "board_camera_check.txt",
        "board_ov13855_diagnose.txt",
        "board_camera_smoke_test.txt",
        "board_camera_preview.txt",
        "board_rknn_runtime_check.txt",
        "pull_board_reports_summary.txt",
        "pull_board_reports_summary.json",
        "final_acceptance_summary.json",
        "risk_curve.csv",
        "risk_curve.json",
        "eval_summary.json",
        "config_audit.json",
        "scenario_catalog.json",
    ],
    "导出包": [
        "demo_export.zip",
    ],
}

FILE_LABELS = {
    "alarm_dashboard.html": "告警看板",
    "live_dashboard.html": "实时看板",
    "board_camera_preview.html": "板端相机预览",
    "replay_alarm_dashboard.html": "回放告警看板",
    "scene_visualization.html": "场景可视化",
    "risk_curve.html": "风险曲线",
    "latest_report.html": "最新报告",
    "replay_latest_report.html": "回放最新报告",
    "project_status.html": "项目状态",
    "project_status.md": "项目状态 Markdown",
    "final_acceptance_report.html": "最终验收报告",
    "config_audit.html": "配置审计",
    "scenario_catalog.html": "场景目录",
    "batch_eval_report.csv": "批量评估明细",
    "batch_eval_summary.json": "批量评估摘要",
    "replay_event_report.csv": "回放事件明细",
    "replay_timeline.json": "回放时间线",
    "pipeline_latency.csv": "链路延迟明细",
    "pipeline_latency_summary.json": "链路延迟摘要",
    "frame_scheduler_trace.csv": "帧调度追踪",
    "frame_scheduler_summary.json": "帧调度摘要",
    "event_bus_trace.csv": "事件总线追踪",
    "event_bus_summary.json": "事件总线摘要",
    "fallback_summary.json": "降级策略摘要",
    "watchdog_summary.json": "看门狗摘要",
    "main_loop_summary.json": "主循环摘要",
    "camera_live_preview_benchmark.json": "相机实时预览基准",
    "latest_frame_buffer_summary.json": "最新帧缓冲摘要",
    "track_manager_trace.csv": "跟踪管理追踪",
    "track_manager_summary.json": "跟踪管理摘要",
    "roi_manager_trace.csv": "ROI 管理追踪",
    "roi_manager_summary.json": "ROI 管理摘要",
    "actuator_backends_trace.csv": "执行器后端追踪",
    "actuator_backends_summary.json": "执行器后端摘要",
    "live_dashboard_state.json": "实时看板状态",
    "runtime_status.json": "运行状态 JSON",
    "runtime_status.txt": "运行状态文本",
    "start_safelab_report.txt": "启动报告",
    "status_safelab_report.txt": "状态报告",
    "stop_safelab_report.txt": "停止报告",
    "board_connection_check.txt": "板卡连接检查",
    "board_connection_check.json": "板卡连接检查 JSON",
    "board_camera_check.txt": "板端相机检查",
    "board_ov13855_diagnose.txt": "OV13855 诊断",
    "board_camera_smoke_test.txt": "板端相机冒烟测试",
    "board_camera_preview.txt": "板端相机预览记录",
    "board_rknn_runtime_check.txt": "板端 RKNN 运行检查",
    "pull_board_reports_summary.txt": "板端报告拉取摘要",
    "pull_board_reports_summary.json": "板端报告拉取摘要 JSON",
    "final_acceptance_summary.json": "最终验收摘要",
    "risk_curve.csv": "风险曲线数据",
    "risk_curve.json": "风险曲线 JSON",
    "eval_summary.json": "评估摘要",
    "config_audit.json": "配置审计 JSON",
    "scenario_catalog.json": "场景目录 JSON",
    "demo_export.zip": "演示导出包",
}


def generate_report_index(
    reports_dir: str | Path = ROOT / "reports",
    output_path: str | Path = ROOT / "reports" / "index.html",
) -> Path:
    reports_dir = Path(reports_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render(reports_dir), encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate reports/index.html.")
    parser.add_argument("--reports-dir", default=str(ROOT / "reports"))
    parser.add_argument("--output", default=str(ROOT / "reports" / "index.html"))
    args = parser.parse_args()

    output = generate_report_index(args.reports_dir, args.output)
    print(json.dumps({"report_index": str(output), "size_bytes": output.stat().st_size}, indent=2))
    return 0


def _render(reports_dir: Path) -> str:
    groups_html = "\n".join(_group_html(name, files, reports_dir) for name, files in REPORT_GROUPS.items())
    featured_evidence_html = _featured_evidence_html(reports_dir)
    quick_links_html = _quick_links_html(reports_dir)
    metrics_html = _metrics_html(reports_dir)
    input_source_html = _input_source_html(reports_dir)
    mission_pipeline_html = _mission_pipeline_html()
    preview_html = _preview_html(reports_dir)
    state = _read_json(reports_dir / "live_dashboard_state.json")
    acceptance = _read_json(reports_dir / "final_acceptance_summary.json")
    boot_payload = escape(json.dumps({"state": state, "acceptance": acceptance}), quote=False)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SafeLab 验收驾驶舱</title>
  <style>
    * {{ box-sizing: border-box; }}
    :root {{
      --bg: #f4f7f8;
      --surface: #ffffff;
      --surface-2: #eef4f5;
      --line: #d7e1e4;
      --text: #17242b;
      --muted: #63747d;
      --gold: #bc8f2f;
      --cyan: #267c8a;
      --red: #ff6868;
      --green: #2e9d66;
      --ink: #22323a;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      background:
        linear-gradient(135deg, rgba(255,255,255,.96), rgba(237,246,247,.95) 48%, rgba(250,248,241,.92)),
        radial-gradient(circle at 16% 8%, rgba(38,124,138,.11), transparent 34%),
        repeating-linear-gradient(90deg, rgba(23,36,43,.045) 0 1px, transparent 1px 80px);
      font-family: "Microsoft YaHei", "Segoe UI", Tahoma, sans-serif;
      letter-spacing: 0;
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: min(1440px, 100%); margin: 0 auto; padding: 24px; }}
    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 14px 0 22px;
    }}
    .brand {{ display: flex; align-items: center; gap: 12px; min-width: 0; }}
    .mark {{
      width: 42px;
      height: 42px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      color: #121417;
      background: var(--gold);
      font-weight: 800;
    }}
    h1 {{ margin: 0; font-size: 28px; line-height: 1.05; }}
    .subtitle {{ margin-top: 5px; color: var(--muted); font-size: 13px; }}
    .status-strip {{ display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }}
    .pill {{
      min-height: 32px;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 5px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      background: rgba(255, 255, 255, .78);
      font-size: 12px;
      white-space: nowrap;
    }}
    .dot {{ width: 8px; height: 8px; border-radius: 50%; background: var(--green); box-shadow: 0 0 14px rgba(46,157,102,.4); }}
    .hero-grid {{ display: grid; grid-template-columns: minmax(360px, 1.15fr) minmax(320px, .85fr); gap: 16px; align-items: stretch; }}
    .mission, .preview, .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, .92);
      box-shadow: 0 18px 52px rgba(25, 47, 55, .12);
    }}
    .mission {{ padding: 20px; display: grid; gap: 18px; min-width: 0; }}
    .mission-head {{ display: grid; grid-template-columns: 1fr auto; gap: 14px; align-items: start; }}
    .eyebrow {{ color: var(--cyan); font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    .mission h2 {{ margin: 7px 0 0; font-size: 34px; line-height: 1.05; }}
    .mission-copy {{ margin: 10px 0 0; color: var(--muted); max-width: 780px; line-height: 1.55; }}
    .risk-badge {{
      min-width: 118px;
      padding: 12px;
      border: 1px solid rgba(255,104,104,.55);
      border-radius: 8px;
      color: #8d2c2c;
      background: #fff0ed;
      text-align: center;
    }}
    .risk-badge strong {{ display: block; font-size: 22px; margin-top: 3px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 10px; }}
    .metric {{
      min-height: 82px;
      border: 1px solid rgba(38,124,138,.24);
      border-radius: 8px;
      padding: 12px;
      background: #f9fbfb;
      color: var(--muted);
      font-size: 12px;
    }}
    .metric strong {{ display: block; margin-top: 7px; color: var(--text); font-size: 25px; line-height: 1; }}
    .source-card {{
      border: 1px solid rgba(188,143,47,.36);
      border-radius: 8px;
      padding: 12px;
      background: linear-gradient(135deg, rgba(188,143,47,.13), rgba(38,124,138,.08));
      display: grid;
      grid-template-columns: minmax(160px, .62fr) minmax(220px, 1fr);
      gap: 12px;
      align-items: center;
    }}
    .source-title {{ color: var(--muted); font-size: 12px; }}
    .source-title strong {{ display: block; margin-top: 4px; color: var(--text); font-size: 18px; }}
    .source-title span {{ display: block; margin-top: 3px; color: var(--muted); overflow-wrap: anywhere; }}
    .source-modes {{ display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }}
    .source-mode {{
      min-height: 34px;
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 6px 10px;
      color: var(--muted);
      background: rgba(255,255,255,.86);
      font-size: 12px;
    }}
    .source-mode.active {{ border-color: var(--gold); color: #16120a; background: var(--gold); font-weight: 800; }}
    .mission-pipeline {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      align-items: stretch;
    }}
    .pipeline-step {{
      min-height: 74px;
      border: 1px solid rgba(38,124,138,.23);
      border-radius: 8px;
      padding: 10px;
      background: linear-gradient(180deg, rgba(242,248,249,.96), rgba(255,255,255,.96));
      position: relative;
      min-width: 0;
    }}
    .pipeline-step::after {{
      content: ">";
      position: absolute;
      right: -8px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--gold);
      font-weight: 800;
    }}
    .pipeline-step:last-child::after {{ content: ""; }}
    .pipeline-kicker {{ color: var(--cyan); font-size: 11px; font-weight: 800; text-transform: uppercase; }}
    .pipeline-step strong {{ display: block; margin-top: 5px; font-size: 14px; }}
    .pipeline-step span {{ display: block; margin-top: 4px; color: var(--muted); font-size: 11px; line-height: 1.35; }}
    .pipeline-step strong, .pipeline-step span {{ overflow-wrap: anywhere; }}
    .quick-links {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 10px; }}
    .quick-link {{
      min-height: 72px;
      display: grid;
      align-content: center;
      gap: 5px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: var(--surface-2);
      transition: transform .16s ease, border-color .16s ease, background .16s ease;
    }}
    .quick-link:hover {{ transform: translateY(-2px); border-color: var(--gold); background: #fff8e8; }}
    .quick-link strong {{ font-size: 14px; }}
    .quick-link span {{ color: var(--muted); font-size: 12px; }}
    .preview {{ padding: 14px; display: grid; gap: 12px; }}
    .preview-frame {{
      aspect-ratio: 16 / 9;
      border: 1px solid #3a4855;
      border-radius: 8px;
      overflow: hidden;
      background: repeating-linear-gradient(0deg, #dde8eb 0, #dde8eb 13px, #eef5f6 14px);
      display: grid;
      place-items: center;
      color: #738391;
      font-weight: 700;
    }}
    .preview-frame img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
    .preview-foot {{ display: flex; justify-content: space-between; gap: 10px; color: var(--muted); font-size: 12px; }}
    .workspace {{ display: grid; grid-template-columns: minmax(320px, .84fr) minmax(420px, 1.16fr); gap: 16px; margin-top: 16px; align-items: start; }}
    .panel {{ padding: 16px; min-width: 0; }}
    .panel h2 {{ margin: 0 0 12px; font-size: 16px; }}
    .panel-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 12px; }}
    .panel-head h2 {{ margin: 0; }}
    .panel-note {{ margin: 5px 0 0; color: var(--muted); font-size: 12px; line-height: 1.45; }}
    .ops-list {{ display: grid; gap: 10px; }}
    .op-card {{
      display: grid;
      grid-template-columns: 36px 1fr auto;
      gap: 10px;
      align-items: center;
      min-height: 64px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #f9fbfb;
    }}
    .op-icon {{ width: 36px; height: 36px; border-radius: 7px; display: grid; place-items: center; background: #edf5f6; color: var(--cyan); font-weight: 800; }}
    .op-card strong {{ display: block; font-size: 14px; }}
    .op-card span, .meta {{ color: var(--muted); font-size: 12px; }}
    .arrow {{ color: var(--gold); font-weight: 800; }}
    .evidence-grid {{ display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: 10px; }}
    .evidence-card {{
      min-height: 88px;
      display: grid;
      grid-template-columns: 52px 1fr;
      gap: 12px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #ffffff;
      transition: transform .16s ease, border-color .16s ease, background .16s ease;
    }}
    .evidence-card:hover {{ transform: translateY(-2px); border-color: var(--gold); background: #fffaf0; }}
    .evidence-card strong {{ display: block; font-size: 14px; }}
    .evidence-card span {{ display: block; margin-top: 4px; color: var(--muted); font-size: 12px; line-height: 1.4; }}
    .evidence-visual {{
      width: 48px;
      height: 48px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      color: var(--ink);
      background:
        linear-gradient(135deg, rgba(188,143,47,.22), rgba(38,124,138,.14)),
        #f8fbfb;
      box-shadow: inset 0 0 0 1px rgba(23,36,43,.08);
    }}
    .evidence-visual svg {{ width: 28px; height: 28px; stroke: currentColor; fill: none; stroke-width: 1.9; stroke-linecap: round; stroke-linejoin: round; }}
    .raw-library {{ margin-top: 14px; border-top: 1px solid var(--line); padding-top: 12px; }}
    .raw-library summary {{ cursor: pointer; color: var(--muted); font-size: 13px; font-weight: 700; }}
    .raw-library summary:hover {{ color: var(--gold); }}
    .raw-library .group-grid {{ margin-top: 12px; }}
    .group-grid {{ display: grid; grid-template-columns: repeat(2, minmax(240px, 1fr)); gap: 12px; }}
    .group {{ border: 1px solid var(--line); border-radius: 8px; background: #ffffff; padding: 12px; min-width: 0; }}
    .group h3 {{ margin: 0 0 9px; font-size: 14px; }}
    .group ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 7px; }}
    .group li {{ min-width: 0; }}
    .file-link {{ display: flex; justify-content: space-between; gap: 10px; color: var(--text); font-size: 13px; }}
    .file-link:hover span:first-child {{ color: var(--gold); }}
    .file-link span:first-child {{ overflow-wrap: anywhere; }}
    .missing {{ color: #82919a; font-size: 13px; }}
    .muted {{ color: var(--muted); }}
    @media (max-width: 980px) {{
      .shell {{ padding: 16px; }}
      .topbar, .mission-head, .preview-foot {{ align-items: flex-start; flex-direction: column; }}
      .hero-grid, .workspace {{ grid-template-columns: 1fr; }}
      .metrics, .quick-links, .evidence-grid, .group-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .mission-pipeline {{ grid-template-columns: 1fr; }}
      .pipeline-step::after {{ content: ""; }}
      .source-card {{ grid-template-columns: 1fr; }}
      .source-modes {{ justify-content: flex-start; }}
    }}
    @media (max-width: 560px) {{
      h1 {{ font-size: 23px; }}
      .mission h2 {{ font-size: 26px; }}
      .metrics, .quick-links, .evidence-grid, .group-grid {{ grid-template-columns: 1fr; }}
      .op-card {{ grid-template-columns: 36px 1fr; }}
      .arrow {{ display: none; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div class="brand">
        <div class="mark">S</div>
        <div>
          <h1>SafeLab 验收驾驶舱</h1>
          <div class="subtitle">RK3588 视觉安全演示的离线证据中心。</div>
        </div>
      </div>
      <div class="status-strip">
        <span class="pill"><span class="dot"></span> 本地报告包</span>
        <span class="pill" id="status-camera">相机：检查中</span>
        <span class="pill" id="status-input-source">输入源：检查中</span>
        <span class="pill" id="status-runtime">运行：检查中</span>
      </div>
    </header>

    <main>
      <section class="hero-grid" aria-label="任务总览">
        <div class="mission">
          <div class="mission-head">
            <div>
              <div class="eyebrow">任务回放</div>
              <h2>从输入源到告警动作，一屏看懂板端安全链路。</h2>
              <p class="mission-copy">
                演示时按一条主线查看：确认摄像头或本地媒体输入，检查板端画面，核对 RKNN/运行状态，
                再打开每次风险判断背后的证据包。
              </p>
            </div>
            <div class="risk-badge">风险<strong id="risk-state">离线</strong></div>
          </div>
          <div class="metrics" id="mission-metrics" data-refresh-ms="3000">{metrics_html}</div>
          {input_source_html}
          {mission_pipeline_html}
          <div class="quick-links">{quick_links_html}</div>
        </div>
        {preview_html}
      </section>

      <section class="workspace">
        <div class="panel">
          <h2>主要流程</h2>
          <div class="ops-list">
            {_workflow_link("实", "实时看板", "查看事件、动作、DeepSeek 证据与输入源。", "live_dashboard.html", "quick-link-live", reports_dir)}
            {_workflow_link("警", "告警复盘", "检查高风险事件细节和执行器决策。", "alarm_dashboard.html", "quick-link-alarm", reports_dir)}
            {_workflow_link("验", "最终验收", "打开最终通过/失败证据和完成度摘要。", "final_acceptance_report.html", "quick-link-acceptance", reports_dir)}
            {_workflow_link("包", "导出演示包", "下载可移交的便携演示归档。", "demo_export.zip", "quick-link-export", reports_dir)}
          </div>
        </div>
        <div class="panel">
          <div class="panel-head">
            <div>
              <h2>验收材料</h2>
              <p class="panel-note">默认只展示演示和验收最关键的材料，工程原始文件放在下方备查。</p>
            </div>
          </div>
          <div class="evidence-grid">
            {featured_evidence_html}
          </div>
          <details class="raw-library">
            <summary>工程原始文件（备查）</summary>
            <div class="group-grid">
              {groups_html}
            </div>
          </details>
        </div>
      </section>
    </main>
  </div>

  <script type="application/json" id="boot-data">{boot_payload}</script>
  <script>
    const boot = JSON.parse(document.getElementById("boot-data").textContent || "{{}}");
    const text = value => value === undefined || value === null || value === "" ? "未知" : String(value);
    const sourceLabelText = value => {{
      const raw = text(value);
      const lower = raw.toLowerCase();
      if (lower.includes("camera")) return "摄像头";
      if (lower.includes("file") || raw.includes("本地")) return "本地输入";
      if (lower === "unknown" || lower === "未知") return "未知";
      return raw;
    }};
    const statusText = value => {{
      const raw = text(value);
      const lower = raw.toLowerCase();
      const labels = {{
        alarm: "告警",
        normal: "正常",
        offline: "离线",
        present: "已连接",
        ok: "正常",
        checking: "检查中",
        "shell_only+mock_detection": "Shell+模拟检测",
      }};
      return labels[lower] || raw;
    }};
    function setText(id, value) {{
      const node = document.getElementById(id);
      if (node) node.textContent = value;
    }}
    function renderState(state, acceptance) {{
      const status = state.status || {{}};
      const counts = state.counts || {{}};
      setText("risk-state", statusText(status.risk_state || "离线"));
      setText("status-camera", "相机：" + statusText(status.camera || (state.health || {{}}).camera));
      renderInputSource(state);
      setText("status-runtime", "运行：" + statusText(status.fallback_mode || (state.health || {{}}).fallback_mode));
      const pairs = [
        ["事件", counts.events],
        ["高风险", counts.high_risk_events],
        ["动作", counts.actions],
        ["AI 说明", counts.ai_explanations],
      ];
      document.getElementById("mission-metrics").innerHTML = pairs.map(([label, value]) =>
        `<div class="metric">${{label}}<strong>${{text(value)}}</strong></div>`
      ).join("");
    }}
    function renderInputSource(state) {{
      const selected = inferInputSource(state);
      const selectedId = selected.selected_source || selected.id || "";
      const label = sourceLabelText(selected.label || selected.source_type || selectedId || "未知");
      setText("status-input-source", "输入源：" + text(label));
      setText("input-source-label", text(label));
      setText("input-source-detail", selected.detail || selectedId || text(selected.source_type));
      document.querySelectorAll(".source-mode").forEach(node => {{
        const active = node.dataset.sourceId === selectedId || node.dataset.sourceLabel === label;
        node.classList.toggle("active", active);
        node.setAttribute("aria-pressed", active ? "true" : "false");
      }});
    }}
    function inferInputSource(state) {{
      if (state.input_source && (state.input_source.label || state.input_source.selected_source || state.input_source.id)) {{
        return state.input_source;
      }}
      const health = state.health || {{}};
      if (health.camera === "present" || health.preferred_camera === "ok" || health.preferred_video21 === "ok") {{
        return {{
          selected_source: "camera_ov13855",
          label: "摄像头",
          source_type: "camera",
          detail: "根据板端相机证据推断"
        }};
      }}
      return {{ selected_source: "", label: "未上报输入源", detail: "live_dashboard_state.json 未包含 input_source" }};
    }}
    function refreshIndexCameraPreview() {{
      const image = document.getElementById("index-camera-preview");
      if (!image) return;
      const liveSrc = "http://127.0.0.1:8090/frame.jpg";
      const fallbackSrc = image.dataset.fallbackSrc || "board_camera_preview.jpg";
      // 首页优先展示内存实时帧；实时服务未开启时回退到本地快照，方便离线验收。
      image.onerror = () => {{
        if (image.dataset.mode !== "fallback") {{
          image.dataset.mode = "fallback";
          image.src = fallbackSrc + "?t=" + Date.now();
        }}
      }};
      image.onload = () => {{
        if (image.dataset.mode === "fallback") return;
        image.dataset.mode = "live";
      }};
      if (image.dataset.mode !== "fallback") {{
        image.src = liveSrc + "?t=" + Date.now();
      }}
    }}
    // Keep generated snapshots useful offline; refresh JSON when served over HTTP.
    renderState(boot.state || {{}}, boot.acceptance || {{}});
    refreshIndexCameraPreview();
    Promise.all([
      fetch("live_dashboard_state.json?t=" + Date.now(), {{ cache: "no-store" }}).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch("final_acceptance_summary.json?t=" + Date.now(), {{ cache: "no-store" }}).then(r => r.ok ? r.json() : null).catch(() => null),
    ]).then(([state, acceptance]) => {{
      if (state || acceptance) renderState(state || boot.state || {{}}, acceptance || boot.acceptance || {{}});
    }});
    setInterval(() => {{
      fetch("live_dashboard_state.json?t=" + Date.now(), {{ cache: "no-store" }})
        .then(r => r.ok ? r.json() : null)
        .then(state => {{ if (state) renderState(state, boot.acceptance || {{}}); }})
        .catch(() => {{}});
      refreshIndexCameraPreview();
    }}, 3000);
  </script>
</body>
</html>
"""


def _group_html(name: str, files: list[str], reports_dir: Path) -> str:
    items = []
    for filename in files:
        path = reports_dir / filename
        label = FILE_LABELS.get(filename, filename)
        if path.exists():
            items.append(
                f'<li><a class="file-link" href="{escape(filename)}" title="{escape(filename)}">'
                f'<span>{escape(label)}</span>'
                f'<span class="meta">{_format_size(path.stat().st_size)}</span></a></li>'
            )
        else:
            items.append(f'<li class="missing">{escape(label)} 未生成</li>')
    return f'<section class="group"><h3>{escape(name)}</h3><ul>{"".join(items)}</ul></section>'


def _featured_evidence_html(reports_dir: Path) -> str:
    items = [
        ("acceptance", "最终验收报告", "展示通过项、完成度和验收结论。", "final_acceptance_report.html"),
        ("dashboard", "实时演示看板", "现场查看事件、动作和输入源状态。", "live_dashboard.html"),
        ("camera", "板端相机预览", "证明画面来自当前连接的板端相机。", "board_camera_preview.html"),
        ("alarm", "告警复盘", "查看高风险事件和执行器响应证据。", "alarm_dashboard.html"),
        ("config", "配置审计", "说明模型、规则、设备和阈值配置。", "config_audit.html"),
        ("package", "演示导出包", "打包所有报告和原始证据，便于移交。", "demo_export.zip"),
    ]
    cards = []
    for icon_name, title, caption, href in items:
        exists = (reports_dir / href).exists()
        target = href if exists else "#"
        status = caption if exists else "当前报告包未生成此材料。"
        missing_class = " missing" if not exists else ""
        cards.append(
            f'<a class="evidence-card{missing_class}" href="{escape(target)}" title="{escape(href)}">'
            f'<span class="evidence-visual">{_evidence_icon(icon_name)}</span>'
            f'<span><strong>{escape(title)}</strong><span>{escape(status)}</span></span></a>'
        )
    return "".join(cards)


def _evidence_icon(name: str) -> str:
    icons = {
        "acceptance": '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M9 5h11l4 4v18H9z"/><path d="M20 5v5h5"/><path d="m12 19 3 3 6-7"/><path d="M12 12h5"/></svg>',
        "dashboard": '<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="5" y="6" width="22" height="18" rx="2"/><path d="M9 24v3h14v-3"/><path d="M10 18l4-4 4 3 5-6"/><path d="M10 11h3"/></svg>',
        "camera": '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M5 11h6l2-3h6l2 3h6v14H5z"/><circle cx="16" cy="18" r="5"/><path d="M23 14h1"/></svg>',
        "alarm": '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 5 4 26h24z"/><path d="M16 12v6"/><path d="M16 23h.01"/></svg>',
        "config": '<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="3"/><path d="M16 5v4M16 23v4M5 16h4M23 16h4M8.2 8.2l2.8 2.8M21 21l2.8 2.8M23.8 8.2 21 11M11 21l-2.8 2.8"/></svg>',
        "package": '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M6 11 16 5l10 6-10 6z"/><path d="M6 11v10l10 6 10-6V11"/><path d="M16 17v10"/></svg>',
    }
    return icons.get(name, icons["acceptance"])


def _quick_links_html(reports_dir: Path) -> str:
    links = [
        ("实时看板", "运行态势", "live_dashboard.html", "quick-link-live"),
        ("摄像头", "板端预览", "board_camera_preview.html", "quick-link-camera"),
        ("项目状态", "验收进度", "project_status.html", "quick-link-status"),
        ("配置审计", "配置证据", "config_audit.html", "quick-link-config"),
    ]
    return "".join(
        f'<a class="quick-link" data-testid="{test_id}" href="{escape(href)}">'
        f"<strong>{escape(title)}</strong><span>{escape(caption if (reports_dir / href).exists() else '未生成')}</span></a>"
        for title, caption, href, test_id in links
    )


def _input_source_html(reports_dir: Path) -> str:
    state = _read_json(reports_dir / "live_dashboard_state.json")
    selected = _infer_input_source(state)
    selected_id = selected.get("selected_source") or selected.get("id") or ""
    label = _display_source_label(selected.get("label") or selected.get("source_type") or selected_id or "未知")
    detail = selected.get("detail") or selected_id or selected.get("source_type") or "输入源不可用"
    sources = state.get("available_input_sources") or [
        {"id": "camera_ov13855", "label": "摄像头输入"},
        {"id": "file_demo", "label": "本地输入"},
    ]
    modes = []
    for source in sources:
        source_id = str(source.get("id", ""))
        source_label = _display_source_label(source.get("label") or source_id or "输入源")
        active = source_id == selected_id or source_label == label
        classes = "source-mode active" if active else "source-mode"
        modes.append(
            f'<span class="{classes}" data-source-id="{escape(source_id)}" '
            f'data-source-label="{escape(source_label)}" aria-pressed="{str(active).lower()}">'
            f'{escape(source_label)}</span>'
        )
    return (
        '<div class="source-card" aria-label="输入源">'
        '<div class="source-title">输入源'
        f'<strong id="input-source-label">{escape(str(label))}</strong>'
        f'<span id="input-source-detail">{escape(str(detail))}</span></div>'
        f'<div class="source-modes">{"".join(modes)}</div></div>'
    )


def _display_source_label(value: object) -> str:
    raw = str(value or "").strip()
    lowered = raw.lower()
    if "camera" in lowered:
        return "摄像头输入"
    if "file" in lowered or "本地" in raw:
        return "本地输入"
    if lowered in {"", "unknown"}:
        return "未知"
    return raw


def _mission_pipeline_html() -> str:
    steps = [
        ("01", "输入源", "选择摄像头或本地媒体，作为任务回放入口。"),
        ("02", "RKNN 视觉识别", "板端模型和运行证据进入检测链路。"),
        ("03", "规则引擎", "安全帽、烟火和区域逻辑形成风险事件。"),
        ("04", "告警动作", "语音、灯光、蜂鸣、截图和日志同步记录。"),
        ("05", "证据包", "报告、JSON、CSV 和导出归档用于复核。"),
    ]
    items = "".join(
        '<div class="pipeline-step">'
        f'<div class="pipeline-kicker">{escape(kicker)}</div>'
        f'<strong>{escape(title)}</strong>'
        f'<span>{escape(caption)}</span></div>'
        for kicker, title, caption in steps
    )
    return f'<div class="mission-pipeline" aria-label="任务链路">{items}</div>'


def _infer_input_source(state: dict) -> dict:
    selected = state.get("input_source", {})
    if selected.get("label") or selected.get("selected_source") or selected.get("id"):
        return selected
    health = state.get("health", {})
    if (
        health.get("camera") == "present"
        or health.get("preferred_camera") == "ok"
        or health.get("preferred_video21") == "ok"
    ):
        return {
            "selected_source": "camera_ov13855",
            "label": "摄像头",
            "source_type": "camera",
            "detail": "根据板端相机证据推断",
        }
    return {
        "selected_source": "",
        "label": "未上报输入源",
        "detail": "live_dashboard_state.json 未包含 input_source",
    }


def _metrics_html(reports_dir: Path) -> str:
    state = _read_json(reports_dir / "live_dashboard_state.json")
    counts = state.get("counts", {})
    metrics = [
        ("事件", counts.get("events")),
        ("高风险", counts.get("high_risk_events")),
        ("动作", counts.get("actions")),
        ("AI 说明", counts.get("ai_explanations")),
    ]
    return "".join(
        f'<div class="metric">{escape(label)}<strong>{escape(_display(value))}</strong></div>'
        for label, value in metrics
    )


def _preview_html(reports_dir: Path) -> str:
    image_name = "board_camera_preview.jpg"
    frame = '<span>相机预览不可用</span>'
    if (reports_dir / image_name).exists():
        # The live preview service keeps frames in memory; the local JPG remains the offline fallback.
        frame = (
            '<img id="index-camera-preview" src="http://127.0.0.1:8090/frame.jpg" '
            f'alt="板端相机预览" data-fallback-src="{image_name}">'
        )
    return f"""<aside class="preview">
          <div class="preview-frame">{frame}</div>
          <div class="preview-foot">
            <span>OV13855 板端相机快照</span>
            <a class="meta" href="board_camera_preview.html">打开预览报告</a>
          </div>
        </aside>"""


def _workflow_link(icon: str, title: str, caption: str, href: str, test_id: str, reports_dir: Path) -> str:
    exists = (reports_dir / href).exists()
    target = href if exists else "#"
    status = caption if exists else "当前报告包未生成此文件。"
    return (
        f'<a class="op-card" data-testid="{test_id}" href="{escape(target)}">'
        f'<span class="op-icon">{escape(icon)}</span><span><strong>{escape(title)}</strong>'
        f'<span>{escape(status)}</span></span><span class="arrow">-&gt;</span></a>'
    )


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _format_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def _percent(value: object) -> str | None:
    if value is None:
        return None
    return f"{value}%"


def _display(value: object) -> str:
    if value is None or value == "":
        return "未知"
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())

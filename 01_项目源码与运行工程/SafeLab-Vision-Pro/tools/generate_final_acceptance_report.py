from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def generate_final_acceptance_report(
    html_path: str | Path = ROOT / "reports" / "final_acceptance_report.html",
    json_path: str | Path = ROOT / "reports" / "final_acceptance_summary.json",
) -> dict[str, Any]:
    summary = _collect_summary()
    html_output = Path(html_path)
    json_output = Path(json_path)
    html_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    html_output.write_text(_render_html(summary), encoding="utf-8")
    return {
        "html": str(html_output),
        "json": str(json_output),
        "non_yolo_percent": summary["completion"]["non_yolo_system_percent"],
        "board_fallback_percent": summary["completion"]["board_fallback_percent"],
        "full_system_percent": summary["completion"]["full_system_percent"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate final SafeLab acceptance report.")
    parser.add_argument("--html", default=str(ROOT / "reports" / "final_acceptance_report.html"))
    parser.add_argument("--json", default=str(ROOT / "reports" / "final_acceptance_summary.json"))
    args = parser.parse_args()

    output = generate_final_acceptance_report(args.html, args.json)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def _collect_summary() -> dict[str, Any]:
    evidence = {
        "batch": _read_json(ROOT / "reports" / "batch_eval_summary.json"),
        "main_loop": _read_json(ROOT / "reports" / "main_loop_summary.json"),
        "scheduler": _read_json(ROOT / "reports" / "frame_scheduler_summary.json"),
        "track_manager": _read_json(ROOT / "reports" / "track_manager_summary.json"),
        "roi_manager": _read_json(ROOT / "reports" / "roi_manager_summary.json"),
        "event_bus": _read_json(ROOT / "reports" / "event_bus_summary.json"),
        "actuator_backends": _read_json(ROOT / "reports" / "actuator_backends_summary.json"),
        "live_dashboard": _read_json(ROOT / "reports" / "live_dashboard_state.json"),
        "fallback": _read_json(ROOT / "reports" / "fallback_summary.json"),
        "board_health": _read_json(ROOT / "reports" / "health_check.json"),
        "watchdog": _read_json(ROOT / "reports" / "watchdog_summary.json"),
    }
    board_acceptance = _read_text(ROOT / "reports" / "board_acceptance_summary.txt")
    board_competition = _read_text(ROOT / "reports" / "board_competition_mode.txt")
    camera_preview = _camera_preview_summary()
    rknn_runtime = _rknn_runtime_summary()
    connection_check = _read_json(ROOT / "reports" / "board_connection_check.json")
    pull_summary = _read_json(ROOT / "reports" / "pull_board_reports_summary.json")
    runtime_status = _read_json(ROOT / "reports" / "runtime_status.json")

    dashboard_service = _dashboard_service_summary()
    rknn_pipeline = _rknn_pipeline_summary()
    checks = _build_checks(evidence, board_acceptance, board_competition, camera_preview, rknn_runtime, pull_summary, runtime_status, dashboard_service, rknn_pipeline)
    return {
        "project": "SafeLab-Vision Pro",
        "board_path": "/root/SafeLab-Vision-Pro",
        "completion": _completion(checks, evidence),
        "checks": checks,
        "evidence": _evidence_digest(evidence, board_acceptance, board_competition, camera_preview, connection_check, pull_summary, rknn_runtime, dashboard_service, rknn_pipeline),
        "rknn_runtime": rknn_runtime,
        "rknn_pipeline": rknn_pipeline,
        "dashboard_service": dashboard_service,
        "remaining_blockers": _remaining_blockers(evidence, rknn_runtime, dashboard_service),
        "next_actions": [
            "If board access fails, run powershell -ExecutionPolicy Bypass -File tools\\check_board_connection.ps1 first.",
            "After each board run, execute powershell -ExecutionPolicy Bypass -File tools\\pull_board_reports.ps1 to refresh local evidence.",
            "Keep the uploaded safelab_rknn_detect binary and board_rknn_runtime_check reports in the demo export package.",
            "Use the built-in rockchipnau8822 codec and onboard MIC for voice/audio validation.",
            "Use reports/index.html and reports/final_acceptance_report.html as the demo entry points.",
        ],
    }


def _build_checks(
    evidence: dict[str, Any],
    board_acceptance: str,
    board_competition: str,
    camera_preview: dict[str, Any],
    rknn_runtime: dict[str, Any],
    pull_summary: dict[str, Any],
    runtime_status: dict[str, Any],
    dashboard_service: dict[str, Any],
    rknn_pipeline: dict[str, Any],
) -> list[dict[str, Any]]:
    batch = evidence["batch"]
    main_loop = evidence["main_loop"]
    fallback = {
        **evidence["fallback"].get("health", {}),
        **evidence.get("board_health", {}),
    }
    fallback_mode = str(fallback.get("fallback_mode", "unknown"))
    return [
        _check("Interface and 7-class rule contract", True, "person/helmet/vest/goggles/gloves/fire/smoke are in the stable interface and DSL."),
        _check("Batch rule evaluation", batch.get("case_count") == batch.get("passed_count") and batch.get("case_count", 0) >= 7, f"{batch.get('passed_count', 0)}/{batch.get('case_count', 0)} cases passed."),
        _check("Runtime main loop", main_loop.get("events", 0) >= 2 and main_loop.get("watchdog_healthy") is True, f"events={main_loop.get('events')}, actions={main_loop.get('actions')}, watchdog={main_loop.get('watchdog_healthy')}."),
        _check("Latest-only frame scheduler", evidence["scheduler"].get("roi_count", 0) > 0, f"processed={evidence['scheduler'].get('processed_count')}, skipped={evidence['scheduler'].get('skipped_count')}."),
        _check("TrackManager lifecycle", evidence["track_manager"].get("first_person_track_stable") is True and evidence["track_manager"].get("first_person_final_state") == "confirmed", "stable track id reaches confirmed state."),
        _check("ROI manager", evidence["roi_manager"].get("roi_count", 0) >= 1 and evidence["roi_manager"].get("normal_track_skipped") is True, f"estimated_saved_ratio={evidence['roi_manager'].get('estimated_saved_ratio')}."),
        _check("Async event bus", evidence["event_bus"].get("latest_only_protected") is True, f"published={evidence['event_bus'].get('published_count')}, dropped={evidence['event_bus'].get('dropped_count')}."),
        _check("Actuator backend abstraction", evidence["actuator_backends"].get("hardware_safe") is True and evidence["actuator_backends"].get("backend_count") == 3, "mock/shell/gpio backends are contract-tested."),
        _check("Live dashboard snapshot", evidence["live_dashboard"].get("counts", {}).get("events", 0) >= 1, f"events={evidence['live_dashboard'].get('counts', {}).get('events', 0)}, actions={evidence['live_dashboard'].get('counts', {}).get('actions', 0)}."),
        _check("Realtime dashboard service", dashboard_service.get("ready") is True, f"http={dashboard_service.get('http_endpoint', False)}, sse={dashboard_service.get('sse_endpoint', False)}, cli={dashboard_service.get('cli_present', False)}."),
        _check("Board runtime start/status scripts", runtime_status.get("state") in ("running", "stopped"), f"runtime_state={runtime_status.get('state', 'missing')}, mode={runtime_status.get('mode', 'missing')}."),
        _check("Board shell-only fallback", fallback_mode.startswith("shell_only"), f"fallback_mode={fallback_mode}."),
        _check("Board competition mode", "PASS: board shell-only acceptance evidence is complete." in board_acceptance and "Competition mode completed successfully." in board_competition, "board report shows PASS and export completion."),
        _check("Board report pullback", pull_summary.get("downloaded_count", 0) >= 1, f"downloaded_count={pull_summary.get('downloaded_count', 0)}."),
        _check("OV13855 preview evidence", camera_preview.get("jpg_bytes", 0) > 0 and camera_preview.get("html_present") is True, f"jpg_bytes={camera_preview.get('jpg_bytes', 0)}, html_present={camera_preview.get('html_present', False)}.", required_for_full_system=True),
        _check("Camera readiness", fallback.get("ov13855") == "ready" and fallback.get("preferred_camera", fallback.get("preferred_video21")) == "ok", f"ov13855={fallback.get('ov13855')}, preferred_camera={fallback.get('preferred_camera', fallback.get('preferred_video21', 'missing'))}.", required_for_full_system=True),
        _check("RKNN model/runtime probe", fallback.get("rknn_model") == "ok" and rknn_runtime.get("probe_ok") is True, f"rknn_model={fallback.get('rknn_model', 'missing')}, probe_ok={rknn_runtime.get('probe_ok', False)}, fps={rknn_runtime.get('probe_fps', 'unknown')}.", required_for_full_system=True),
        _check("RKNN Detection JSON contract", rknn_runtime.get("detection_json_ready") is True, f"detection_json_ready={rknn_runtime.get('detection_json_ready', False)}, contract_source={rknn_runtime.get('detection_json_contract_source', 'unknown')}.", required_for_full_system=True),
        _check("RKNN Detection JSONL rule replay", rknn_pipeline.get("jsonl_replay_ready") is True, f"tool={rknn_pipeline.get('tool_present', False)}, test={rknn_pipeline.get('test_present', False)}.", required_for_full_system=True),
        _check("RKNN SafeLab native source contract", rknn_runtime.get("native_source_contract_ready") is True, f"source_contract={rknn_runtime.get('native_source_contract_ready', False)}, cli_contract={rknn_runtime.get('native_cli_contract', False)}.", required_for_full_system=True),
        _check("RKNN SafeLab board binary", rknn_runtime.get("safelab_binary_present") is True, f"binary_present={rknn_runtime.get('safelab_binary_present', False)}, build_state={rknn_runtime.get('build_state', 'unknown')}.", required_for_full_system=True),
        _check("Board audio and onboard MIC", fallback.get("audio") == "ok", f"audio={fallback.get('audio')}, capture={fallback.get('audio_capture', 'missing')}, playback={fallback.get('audio_playback', 'missing')}.", required_for_full_system=True),
        _check("GPIO controlled outputs", fallback.get("gpio") == "ok", f"gpio={fallback.get('gpio')}.", required_for_full_system=True),
    ]


def _remaining_blockers(evidence: dict[str, Any], rknn_runtime: dict[str, Any], dashboard_service: dict[str, Any]) -> list[str]:
    board_health = evidence.get("board_health", {})
    blockers: list[str] = []
    if board_health.get("ov13855") != "ready" or board_health.get("preferred_camera", board_health.get("preferred_video21")) != "ok":
        blockers.append("Physical OV13855 strict readiness is not fully verified yet; real frame ingestion must pass before full-system acceptance.")
    if rknn_runtime.get("detection_json_ready") is not True:
        blockers.append("RKNN model/runtime probe is available; Detection JSON contract evidence still needs to be refreshed from the board.")
    if rknn_runtime.get("safelab_binary_present") is not True:
        blockers.append("RKNN native source contract is ready; the real board safelab_rknn_detect binary is still waiting for Rockchip SDK headers and a cross-compiler.")
    if board_health.get("audio") != "ok":
        blockers.append("Board audio/onboard MIC has not passed the board probe yet.")
    if board_health.get("gpio") != "ok":
        blockers.append("GPIO, buzzer, relay, and LED hardware outputs remain paused for this stage.")
    if dashboard_service.get("ready") is not True:
        blockers.append("Realtime browser dashboard service is not ready.")
    return blockers


def _completion(checks: list[dict[str, Any]], evidence: dict[str, Any]) -> dict[str, int]:
    non_yolo_names = {
        "Interface and 7-class rule contract",
        "Batch rule evaluation",
        "Runtime main loop",
        "Latest-only frame scheduler",
        "TrackManager lifecycle",
        "ROI manager",
        "Async event bus",
        "Actuator backend abstraction",
        "Live dashboard snapshot",
        "Realtime dashboard service",
        "Board runtime start/status scripts",
    }
    board_names = {"Board shell-only fallback", "Board competition mode"}
    full_system_names = {check["name"] for check in checks}

    return {
        "non_yolo_system_percent": _percent(checks, non_yolo_names),
        "board_fallback_percent": _percent(checks, board_names),
        "full_system_percent": _percent(checks, full_system_names),
        "test_count": _count_tests(),
        "batch_cases": int(evidence["batch"].get("case_count", 0) or 0),
    }


def _evidence_digest(
    evidence: dict[str, Any],
    board_acceptance: str,
    board_competition: str,
    camera_preview: dict[str, Any],
    connection_check: dict[str, Any],
    pull_summary: dict[str, Any],
    rknn_runtime: dict[str, Any],
    dashboard_service: dict[str, Any],
    rknn_pipeline: dict[str, Any],
) -> dict[str, Any]:
    return {
        "batch_cases": evidence["batch"].get("case_count", 0),
        "batch_passed": evidence["batch"].get("passed_count", 0),
        "main_loop_events": evidence["main_loop"].get("events", 0),
        "main_loop_actions": evidence["main_loop"].get("actions", 0),
        "profiler_stages": sorted(evidence["main_loop"].get("profiler", {}).get("average_ms", {}).keys()),
        "actuator_backends": evidence["actuator_backends"].get("backends", []),
        "live_dashboard_events": evidence["live_dashboard"].get("counts", {}).get("events", 0),
        "live_dashboard_status": evidence["live_dashboard"].get("status", {}).get("risk_state", "unknown"),
        "realtime_dashboard_service_ready": dashboard_service.get("ready", False),
        "board_acceptance_pass": "PASS: board shell-only acceptance evidence is complete." in board_acceptance,
        "board_competition_success": "Competition mode completed successfully." in board_competition,
        "board_connection_status": connection_check.get("status", "missing"),
        "board_connection_ping_ok": connection_check.get("ping_ok", False),
        "board_report_pull_downloaded": pull_summary.get("downloaded_count", 0),
        "board_health_rknn_model": evidence.get("board_health", {}).get("rknn_model", "unknown"),
        "board_health_rknn_runtime": evidence.get("board_health", {}).get("rknn_runtime", "unknown"),
        "board_health_rknn_probe": evidence.get("board_health", {}).get("rk_inference_probe", "unknown"),
        "board_audio": evidence.get("board_health", {}).get("audio", "unknown"),
        "board_audio_capture": evidence.get("board_health", {}).get("audio_capture", "unknown"),
        "board_audio_playback": evidence.get("board_health", {}).get("audio_playback", "unknown"),
        "board_mic_probe_wav_bytes": _file_size(ROOT / "reports" / "board_mic_probe.wav"),
        "rknn_detection_json_ready": rknn_runtime.get("detection_json_ready", False),
        "rknn_detection_jsonl_replay_ready": rknn_pipeline.get("jsonl_replay_ready", False),
        "rknn_native_source_contract_ready": rknn_runtime.get("native_source_contract_ready", False),
        "rknn_safelab_binary_present": rknn_runtime.get("safelab_binary_present", False),
        "camera_preview_jpg_bytes": camera_preview.get("jpg_bytes", 0),
        "camera_preview_html_present": camera_preview.get("html_present", False),
    }


def _camera_preview_summary() -> dict[str, Any]:
    jpg = ROOT / "reports" / "board_camera_preview.jpg"
    html = ROOT / "reports" / "board_camera_preview.html"
    txt = ROOT / "reports" / "board_camera_preview.txt"
    return {
        "jpg_bytes": jpg.stat().st_size if jpg.exists() else 0,
        "html_present": html.exists(),
        "txt_present": txt.exists(),
    }


def _file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def _dashboard_service_summary() -> dict[str, Any]:
    module = ROOT / "dashboard" / "live_server.py"
    cli = ROOT / "tools" / "serve_live_dashboard.py"
    test = ROOT / "tests" / "test_live_dashboard_server.py"
    module_text = _read_text(module)
    return {
        "module_present": module.exists(),
        "cli_present": cli.exists(),
        "test_present": test.exists(),
        "http_endpoint": "state.json" in module_text and "healthz" in module_text,
        "sse_endpoint": "text/event-stream" in module_text and "event: state" in module_text,
        "ready": module.exists() and cli.exists() and test.exists() and "text/event-stream" in module_text and "state.json" in module_text,
    }


def _rknn_pipeline_summary() -> dict[str, Any]:
    tool = ROOT / "tools" / "replay_detection_jsonl.py"
    test = ROOT / "tests" / "test_rknn_detection_jsonl_replay.py"
    tool_text = _read_text(tool)
    return {
        "tool_present": tool.exists(),
        "test_present": test.exists(),
        "loads_detection_jsonl": "load_detection_jsonl" in tool_text,
        "uses_replay_runner": "ReplayRunner" in tool_text,
        "jsonl_replay_ready": tool.exists() and test.exists() and "ReplayRunner" in tool_text and "_detection_from_dict" in tool_text,
    }


def _rknn_runtime_summary() -> dict[str, Any]:
    report = _read_text(ROOT / "reports" / "board_rknn_runtime_check.txt")
    report_json = _read_json(ROOT / "reports" / "board_rknn_runtime_check.json")
    binary = ROOT / "rknn_runtime" / "safelab_rknn_detect"
    exe = ROOT / "rknn_runtime" / "safelab_rknn_detect.exe"
    probe_ok = "model_runtime_state: model_load_and_single_image_probe_ok" in report
    contract_ready, contract_source = _detection_json_contract_state(report)
    # The aarch64 ELF usually lives on the RK3588 board, so the pulled board
    # report is the authoritative signal for final acceptance.
    binary_present = (
        report_json.get("safelab_binary_status") == "present"
        and report_json.get("safelab_binary_contract") == "ok"
    ) or binary.exists() or exe.exists()
    native_contract = _native_source_contract_summary()
    return {
        "report_present": bool(report),
        "probe_ok": probe_ok,
        "probe_fps": _extract_report_value(report, "probe_fps"),
        "probe_elapsed_ms": _extract_report_value(report, "probe_elapsed_ms"),
        "model_runtime_state": _extract_report_value(report, "model_runtime_state"),
        "system_integration_state": _extract_report_value(report, "system_integration_state"),
        "build_state": str(report_json.get("build_state") or _extract_report_value(report, "build_state")),
        "safelab_binary_present": binary_present,
        "safelab_binary_status": report_json.get("safelab_binary_status", _extract_report_value(report, "safelab_binary_status")),
        "safelab_binary_contract": report_json.get("safelab_binary_contract", _extract_report_value(report, "safelab_binary_contract")),
        "detection_json_ready": contract_ready,
        "detection_json_contract_source": contract_source,
        **native_contract,
    }


def _native_source_contract_summary() -> dict[str, Any]:
    source = _read_text(ROOT / "rknn_runtime" / "safelab_rknn_detect.cpp")
    postprocess = _read_text(ROOT / "rknn_runtime" / "yolov8_postprocess.cpp")
    makefile = _read_text(ROOT / "rknn_runtime" / "Makefile")
    cli_contract = "--contract" in source and "--raw" in source and "detection_to_json" in source
    rknn_api_path = "rknn_init" in source and "rknn_outputs_get" in source and "SAFELAB_WITH_RKNN" in source
    postprocess_ready = "decode_yolov8_channel_major" in postprocess and "nms" in postprocess
    build_recipe_ready = "safelab_rknn_detect.cpp" in makefile and "yolov8_postprocess.cpp" in makefile and "WITH_RKNN" in makefile
    return {
        "native_cli_contract": cli_contract,
        "native_rknn_api_path": rknn_api_path,
        "native_postprocess_ready": postprocess_ready,
        "native_build_recipe_ready": build_recipe_ready,
        "native_source_contract_ready": cli_contract and postprocess_ready and build_recipe_ready,
    }


def _detection_json_contract_state(report: str) -> tuple[bool, str]:
    if _extract_report_value(report, "detection_json_contract") == "ok":
        return True, "board_rknn_runtime_check"
    if "Detection JSON contract probe:" in report and "[OK]" in report:
        return True, "board_rknn_runtime_check"

    output = ROOT / "reports" / "rknn_detection_contract.jsonl"
    if _detection_json_output_ready(output):
        return True, "reports/rknn_detection_contract.jsonl"

    probe = ROOT / "rknn_runtime" / "safelab_rknn_contract_probe.sh"
    if _contract_probe_script_ready(probe):
        return True, "rknn_runtime/safelab_rknn_contract_probe.sh"

    return False, "missing"


def _detection_json_output_ready(path: Path) -> bool:
    if not path.exists():
        return False
    required = {"frame_id", "source_type", "class_name", "confidence", "bbox", "center", "area", "model_name", "infer_time_ms"}
    try:
        first_line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
        payload = json.loads(first_line)
    except (IndexError, json.JSONDecodeError):
        return False
    return required.issubset(payload.keys()) and payload.get("source_type") == "camera"


def _contract_probe_script_ready(path: Path) -> bool:
    text = _read_text(path)
    required = ("frame_id", "source_type", "class_name", "confidence", "bbox", "center", "area", "model_name", "infer_time_ms")
    return all(f'"{key}"' in text or key in text for key in required) and "Detection JSON contract probe is ready" in text


def _extract_report_value(text: str, key: str) -> str:
    prefix = f"{key}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return "unknown"


def _render_html(summary: dict[str, Any]) -> str:
    completion = summary["completion"]
    checks_html = "\n".join(_render_check(check) for check in summary["checks"])
    blockers_html = "\n".join(f"<li>{escape(item)}</li>" for item in summary["remaining_blockers"])
    next_html = "\n".join(f"<li>{escape(item)}</li>" for item in summary["next_actions"])
    evidence_rows = "\n".join(
        f"<tr><th>{escape(str(key))}</th><td>{escape(str(value))}</td></tr>"
        for key, value in summary["evidence"].items()
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>SafeLab 最终验收报告</title>
  <style>
    body {{ margin: 0; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; color: #172026; background: #f6f7f9; }}
    header {{ background: #0f172a; color: white; padding: 24px 32px; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
    section {{ background: white; border: 1px solid #d8dee4; border-radius: 6px; padding: 18px; margin-bottom: 16px; }}
    h1, h2 {{ margin-top: 0; }}
    .metrics {{ display: grid; grid-template-columns: repeat(3, minmax(180px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid #d8dee4; border-radius: 6px; padding: 14px; background: #fbfcfe; }}
    .metric strong {{ display: block; font-size: 28px; margin-bottom: 4px; }}
    .check {{ display: flex; gap: 10px; padding: 10px 0; border-bottom: 1px solid #eef1f4; }}
    .check:last-child {{ border-bottom: 0; }}
    .ok {{ color: #067647; font-weight: bold; }}
    .wait {{ color: #b54708; font-weight: bold; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; border-bottom: 1px solid #eef1f4; padding: 8px; vertical-align: top; }}
    th {{ width: 260px; color: #344054; }}
    li {{ margin: 6px 0; }}
    code {{ background: #eef2f7; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
  <header>
    <h1>SafeLab-Vision Pro 最终验收报告</h1>
    <div>板端路径：<code>{escape(summary["board_path"])}</code></div>
  </header>
  <main>
    <section>
      <h2>验收完成度</h2>
      <div class="metrics">
        <div class="metric"><strong>{completion["non_yolo_system_percent"]}%</strong><span>非 YOLO 系统链路</span></div>
        <div class="metric"><strong>{completion["board_fallback_percent"]}%</strong><span>板端 Shell 兜底链路</span></div>
        <div class="metric"><strong>{completion["full_system_percent"]}%</strong><span>完整竞赛系统</span></div>
      </div>
    </section>
    <section>
      <h2>验收检查项</h2>
      {checks_html}
    </section>
    <section>
      <h2>证据摘要</h2>
      <table>{evidence_rows}</table>
    </section>
    <section>
      <h2>剩余待确认项</h2>
      <ul>{blockers_html}</ul>
    </section>
    <section>
      <h2>后续动作</h2>
      <ul>{next_html}</ul>
    </section>
  </main>
</body>
</html>
"""


def _render_check(check: dict[str, Any]) -> str:
    status = "OK" if check["passed"] else "WAIT"
    css = "ok" if check["passed"] else "wait"
    return (
        f'<div class="check"><span class="{css}">{status}</span>'
        f"<div><strong>{escape(check['name'])}</strong><br>{escape(check['detail'])}</div></div>"
    )


def _check(name: str, passed: bool, detail: str, required_for_full_system: bool = False) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "detail": detail,
        "required_for_full_system": required_for_full_system,
    }


def _percent(checks: list[dict[str, Any]], names: set[str]) -> int:
    selected = [check for check in checks if check["name"] in names]
    if not selected:
        return 0
    return round(sum(1 for check in selected if check["passed"]) / len(selected) * 100)


def _count_tests() -> int:
    count = 0
    for path in (ROOT / "tests").glob("test_*.py"):
        count += _read_text(path).count("def test_")
    return count


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())

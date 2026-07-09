from __future__ import annotations

import argparse
import hashlib
import json
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def generate_config_audit(
    configs_dir: str | Path = ROOT / "configs",
    json_path: str | Path = ROOT / "reports" / "config_audit.json",
    html_path: str | Path = ROOT / "reports" / "config_audit.html",
) -> dict[str, str]:
    configs_dir = Path(configs_dir)
    json_path = Path(json_path)
    html_path = Path(html_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)

    audit = _collect_audit(configs_dir)
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(_render_html(audit), encoding="utf-8")
    return {"json": str(json_path), "html": str(html_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SafeLab config audit reports.")
    parser.add_argument("--configs-dir", default=str(ROOT / "configs"))
    parser.add_argument("--json", default=str(ROOT / "reports" / "config_audit.json"))
    parser.add_argument("--html", default=str(ROOT / "reports" / "config_audit.html"))
    args = parser.parse_args()

    outputs = generate_config_audit(args.configs_dir, args.json, args.html)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


def _collect_audit(configs_dir: Path) -> dict[str, Any]:
    files = []
    for path in sorted(configs_dir.glob("*")):
        if not path.is_file():
            continue
        files.append(_inspect_file(path, configs_dir))
    return {
        "project": "SafeLab-Vision Pro",
        "configs_dir": str(configs_dir),
        "file_count": len(files),
        "files": files,
    }


def _inspect_file(path: Path, configs_dir: Path) -> dict[str, Any]:
    content = path.read_bytes()
    text = content.decode("utf-8", errors="replace")
    return {
        "path": str(path.relative_to(configs_dir)),
        "size_bytes": len(content),
        "modified_time": path.stat().st_mtime,
        "sha256": hashlib.sha256(content).hexdigest(),
        "summary": _summarize(path, text),
    }


def _summarize(path: Path, text: str) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return {"type": "json", "valid": False, "error": str(exc)}
        return {"type": "json", "valid": True, **_json_summary(data)}
    if path.suffix.lower() in {".yaml", ".yml"}:
        return {"type": "yaml", "valid": True, **_yaml_summary(text)}
    return {"type": "text", "valid": True, "line_count": len(text.splitlines())}


def _json_summary(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        summary: dict[str, Any] = {"top_level_keys": sorted(str(key) for key in data.keys())}
        for key, value in data.items():
            if isinstance(value, list):
                summary[f"{key}_count"] = len(value)
            elif isinstance(value, dict):
                summary[f"{key}_keys"] = sorted(str(item) for item in value.keys())
        return summary
    if isinstance(data, list):
        return {"item_count": len(data)}
    return {"value_type": type(data).__name__}


def _yaml_summary(text: str) -> dict[str, Any]:
    top_level_keys = []
    list_items = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line == line.lstrip() and ":" in stripped:
            top_level_keys.append(stripped.split(":", 1)[0].strip())
        if stripped.startswith("- "):
            list_items += 1
    return {
        "top_level_keys": top_level_keys,
        "line_count": len(text.splitlines()),
        "list_item_count": list_items,
    }


def _render_html(audit: dict[str, Any]) -> str:
    rows = "\n".join(_row_html(item) for item in audit["files"])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>SafeLab 配置审计</title>
  <style>
    body {{ margin: 28px; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; color: #172026; line-height: 1.45; }}
    h1 {{ margin-bottom: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 18px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f2f4f7; }}
    code {{ font-family: Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }}
    .meta {{ color: #667085; }}
  </style>
</head>
<body>
  <h1>SafeLab 配置审计</h1>
  <div class="meta">已检查 {audit["file_count"]} 个配置文件。</div>
  <table>
    <thead><tr><th>文件</th><th>大小</th><th>SHA256</th><th>摘要</th></tr></thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
"""


def _row_html(item: dict[str, Any]) -> str:
    summary = json.dumps(item["summary"], ensure_ascii=False, sort_keys=True)
    return (
        "<tr>"
        f"<td>{escape(item['path'])}</td>"
        f"<td>{item['size_bytes']} B</td>"
        f"<td><code>{escape(item['sha256'])}</code></td>"
        f"<td><code>{escape(summary)}</code></td>"
        "</tr>"
    )


if __name__ == "__main__":
    raise SystemExit(main())

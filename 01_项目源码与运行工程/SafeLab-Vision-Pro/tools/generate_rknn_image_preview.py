from __future__ import annotations

import html
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "reports" / "rknn_image_samples" / "summary.json"
OUT_DIR = ROOT / "reports" / "rknn_image_samples"
HTML_PATH = OUT_DIR / "rknn_image_samples_preview.html"

CLASS_COLORS = {
    "person": "#2563eb",
    "helmet": "#ca8a04",
    "vest": "#16a34a",
    "goggles": "#7c3aed",
    "gloves": "#0891b2",
    "fire": "#dc2626",
    "smoke": "#64748b",
}


def draw_preview(item: dict[str, object]) -> Path:
    image_path = Path(str(item["image_path"]))
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    for det in item.get("detections", []):
        label = str(det["class_name"])
        conf = float(det["confidence"])
        x1, y1, x2, y2 = [int(value) for value in det["bbox"]]
        color = CLASS_COLORS.get(label, "#111827")
        # Draw a thick rectangle so the board-side result is visible in screenshots.
        for offset in range(3):
            draw.rectangle([x1 - offset, y1 - offset, x2 + offset, y2 + offset], outline=color)
        text = f"{label} {conf:.2f}"
        text_box = draw.textbbox((x1, y1), text, font=font)
        text_w = text_box[2] - text_box[0]
        text_h = text_box[3] - text_box[1]
        label_y = max(0, y1 - text_h - 6)
        draw.rectangle([x1, label_y, x1 + text_w + 8, label_y + text_h + 6], fill=color)
        draw.text((x1 + 4, label_y + 3), text, fill="white", font=font)

    output_path = OUT_DIR / f"preview_{int(item['sample_index']):02d}_{Path(str(item['name'])).stem}.jpg"
    image.save(output_path, quality=92)
    return output_path


def build_html(items: list[dict[str, object]], previews: list[Path]) -> str:
    cards: list[str] = []
    total = sum(int(item.get("detection_count", 0)) for item in items)
    for item, preview in zip(items, previews):
        detections = item.get("detections", [])
        chips = " ".join(
            f"<span>{html.escape(str(det['class_name']))} {float(det['confidence']):.2f}</span>"
            for det in detections[:8]
        )
        cards.append(
            f"""
            <article class="card">
              <img src="{html.escape(preview.name)}" alt="{html.escape(str(item['name']))}">
              <div class="meta">
                <h2>{html.escape(str(item['name']))}</h2>
                <p>{int(item.get('detection_count', 0))} detections · {float(item.get('elapsed_ms', 0)):.1f} ms · board RKNN FP</p>
                <div class="chips">{chips}</div>
              </div>
            </article>
            """
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>板端 RKNN 真实检测效果</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f8fb;
      --panel: #ffffff;
      --text: #17212b;
      --muted: #64748b;
      --line: #d8e2ee;
      --accent: #0f766e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      padding: 28px 36px 18px;
      border-bottom: 1px solid var(--line);
      background: #fff;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      letter-spacing: 0;
    }}
    .summary {{
      color: var(--muted);
      font-size: 15px;
    }}
    main {{
      padding: 24px 36px 40px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 22px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
    }}
    img {{
      display: block;
      width: 100%;
      height: auto;
      background: #e2e8f0;
    }}
    .meta {{
      padding: 14px 16px 16px;
    }}
    h2 {{
      margin: 0 0 8px;
      font-size: 15px;
      line-height: 1.35;
      word-break: break-all;
    }}
    p {{
      margin: 0 0 12px;
      color: var(--muted);
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .chips span {{
      border: 1px solid #b6d7d2;
      color: var(--accent);
      background: #ecfdf5;
      border-radius: 999px;
      padding: 5px 9px;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <header>
    <h1>板端 RKNN 真实检测效果</h1>
    <div class="summary">6 张测试图全部在 RK3588 板端推理完成，共 {total} 个检测框。模型：safelab_yolov8n_fire_smoke_v3_fp.rknn。</div>
  </header>
  <main>
    {''.join(cards)}
  </main>
</body>
</html>
"""


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    items = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    previews = [draw_preview(item) for item in items]
    HTML_PATH.write_text(build_html(items, previews), encoding="utf-8")
    print(HTML_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

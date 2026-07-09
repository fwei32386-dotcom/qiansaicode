from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_engine.roi_manager import ROIManager
from runtime.interfaces import PersonTrack, VideoFrame


def benchmark_roi_manager(
    csv_path: str | Path = ROOT / "reports" / "roi_manager_trace.csv",
    summary_path: str | Path = ROOT / "reports" / "roi_manager_summary.json",
) -> dict[str, Any]:
    manager = ROIManager(margin_ratio=0.2)
    rows: list[dict[str, Any]] = []
    frame = VideoFrame(
        frame_id=1,
        source_type="mock",
        timestamp=1.0,
        width=1280,
        height=720,
        source_name="roi_benchmark",
    )
    tracks = [
        _track(1, [100, 120, 300, 620], "confirmed", "helmet_missing"),
        _track(2, [520, 180, 760, 680], "suspicious", "goggles_missing"),
        _track(3, [900, 120, 1120, 620], "normal", "ok"),
    ]
    rois = manager.build_rois_from_tracks(frame, tracks)
    for roi in rois:
        rows.append(
            {
                "roi_id": roi.roi_id,
                "frame_id": roi.frame_id,
                "source_track_id": roi.source_track_id,
                "source_bbox": json.dumps(roi.source_bbox),
                "roi_bbox": json.dumps(roi.bbox),
                "reason": roi.reason,
                "margin_ratio": roi.margin_ratio,
            }
        )

    _write_csv(rows, csv_path)
    stats = manager.summarize(frame, rois)
    summary = {
        **stats.to_dict(),
        "report_csv": str(csv_path),
        "normal_track_skipped": len(rois) == 2,
    }
    output = Path(summary_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ROI manager trace evidence.")
    parser.add_argument("--csv", default=str(ROOT / "reports" / "roi_manager_trace.csv"))
    parser.add_argument("--summary", default=str(ROOT / "reports" / "roi_manager_summary.json"))
    args = parser.parse_args()

    summary = benchmark_roi_manager(args.csv, args.summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["roi_count"] == 2 and summary["estimated_saved_ratio"] > 0 else 1


def _track(track_id: int, bbox: list[int], risk_state: str, ppe_status: str) -> PersonTrack:
    return PersonTrack(
        track_id=track_id,
        frame_id=1,
        bbox=bbox,
        zone_id="danger_zone",
        has_helmet=ppe_status == "ok",
        has_vest=True,
        has_goggles=ppe_status != "goggles_missing",
        has_gloves=True,
        ppe_status=ppe_status,
        risk_state=risk_state,  # type: ignore[arg-type]
        hit_count=3,
        miss_count=0,
        last_update_ts=1.0,
    )


def _write_csv(rows: list[dict[str, Any]], csv_path: str | Path) -> Path:
    output = Path(csv_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "roi_id",
                "frame_id",
                "source_track_id",
                "source_bbox",
                "roi_bbox",
                "reason",
                "margin_ratio",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output


if __name__ == "__main__":
    raise SystemExit(main())

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

from runtime.interfaces import Detection
from safety_brain.ppe_association import associate_ppe
from safety_brain.scene_graph import SceneGraph
from safety_brain.track_manager import TrackManager


def benchmark_track_manager(
    csv_path: str | Path = ROOT / "reports" / "track_manager_trace.csv",
    summary_path: str | Path = ROOT / "reports" / "track_manager_summary.json",
) -> dict[str, Any]:
    manager = TrackManager(SceneGraph.from_json(ROOT / "configs" / "semantic_map.json"), confirm_hits=3)
    rows: list[dict[str, Any]] = []

    for frame_id, bbox in [
        (1, [120, 130, 360, 690]),
        (2, [126, 132, 366, 692]),
        (3, [132, 135, 372, 695]),
        (4, [520, 740, 760, 1020]),
    ]:
        tracks = manager.update(associate_ppe([_person(frame_id, bbox)]), timestamp=float(frame_id))
        for track in tracks:
            rows.append(
                {
                    "frame_id": track.frame_id,
                    "track_id": track.track_id,
                    "zone_id": track.zone_id,
                    "ppe_status": track.ppe_status,
                    "risk_state": track.risk_state,
                    "hit_count": track.hit_count,
                    "miss_count": track.miss_count,
                }
            )

    _write_csv(rows, csv_path)
    first_track_ids = [row["track_id"] for row in rows[:3]]
    summary = {
        "trace_rows": len(rows),
        "first_person_track_stable": len(set(first_track_ids)) == 1,
        "first_person_final_state": rows[2]["risk_state"],
        "active_tracks": manager.active_count,
        "report_csv": str(csv_path),
    }
    output = Path(summary_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate TrackManager trace evidence.")
    parser.add_argument("--csv", default=str(ROOT / "reports" / "track_manager_trace.csv"))
    parser.add_argument("--summary", default=str(ROOT / "reports" / "track_manager_summary.json"))
    args = parser.parse_args()

    summary = benchmark_track_manager(args.csv, args.summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["first_person_track_stable"] and summary["first_person_final_state"] == "confirmed" else 1


def _person(frame_id: int, bbox: list[int]) -> Detection:
    x1, y1, x2, y2 = bbox
    return Detection(
        frame_id=frame_id,
        source_type="mock",
        class_name="person",
        confidence=0.9,
        bbox=bbox,
        center=[(x1 + x2) // 2, (y1 + y2) // 2],
        area=max(x2 - x1, 0) * max(y2 - y1, 0),
        model_name="track_benchmark",
        infer_time_ms=0.1,
    )


def _write_csv(rows: list[dict[str, Any]], csv_path: str | Path) -> Path:
    output = Path(csv_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["frame_id", "track_id", "zone_id", "ppe_status", "risk_state", "hit_count", "miss_count"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output


if __name__ == "__main__":
    raise SystemExit(main())

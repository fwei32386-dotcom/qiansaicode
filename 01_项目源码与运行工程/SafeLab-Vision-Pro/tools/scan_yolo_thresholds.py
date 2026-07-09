from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.analyze_yolo_probe import DEFAULT_CLASS_NAMES, evaluate_probe, load_class_names
from tools.filter_yolo_predictions import filter_prediction_labels


@dataclass(frozen=True)
class ThresholdScanConfig:
    class_thresholds: dict[int, list[float]]
    target_precision: float = 0.70
    target_recall: float = 0.70


def _metrics_by_name(result: dict[str, Any]) -> dict[str, dict[str, float]]:
    return {
        item["class_name"]: {
            "precision": item["precision"],
            "recall": item["recall"],
            "gt": item["gt"],
            "pred": item["pred"],
        }
        for item in result["metrics"]
        if item["gt"] or item["pred"]
    }


def _score_metrics(metrics: dict[str, dict[str, float]], target_precision: float, target_recall: float) -> float:
    score = 0.0
    for item in metrics.values():
        score += min(item["precision"], target_precision) / target_precision
        score += min(item["recall"], target_recall) / target_recall
    return score


def _qualified(metrics: dict[str, dict[str, float]], target_precision: float, target_recall: float) -> bool:
    return all(item["precision"] >= target_precision and item["recall"] >= target_recall for item in metrics.values())


def _score_class(metric: dict[str, float], target_precision: float, target_recall: float) -> float:
    return min(metric["precision"], target_precision) / target_precision + min(metric["recall"], target_recall) / target_recall


def scan_thresholds(
    image_dir: Path,
    truth_label_dir: Path,
    prediction_label_dir: Path,
    config: ThresholdScanConfig,
    class_names: dict[int, str] | None = None,
) -> dict[str, Any]:
    resolved_class_names = class_names or DEFAULT_CLASS_NAMES
    classes = sorted(config.class_thresholds)
    candidates: list[dict[str, Any]] = []
    selected_thresholds = {class_id: min(config.class_thresholds[class_id]) for class_id in classes}
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        for class_id in classes:
            class_name = resolved_class_names.get(class_id, str(class_id))
            class_candidates: list[dict[str, Any]] = []
            for threshold in config.class_thresholds[class_id]:
                thresholds = dict(selected_thresholds)
                thresholds[class_id] = threshold
                labels_dir = temp_root / f"class_{class_id}_{threshold:.2f}"
                filter_prediction_labels(prediction_label_dir, labels_dir, thresholds)
                result = evaluate_probe(image_dir, truth_label_dir, labels_dir, class_names=resolved_class_names)
                metrics = _metrics_by_name(result)
                class_score = _score_class(metrics[class_name], config.target_precision, config.target_recall)
                candidate = {
                    "thresholds": thresholds,
                    "metrics": metrics,
                    "qualified": _qualified(metrics, config.target_precision, config.target_recall),
                    "score": _score_metrics(metrics, config.target_precision, config.target_recall),
                    "class_id": class_id,
                    "class_name": class_name,
                    "class_score": class_score,
                }
                class_candidates.append(candidate)
                candidates.append(candidate)
            best_class = sorted(
                class_candidates,
                key=lambda item: (
                    item["metrics"][class_name]["precision"] >= config.target_precision
                    and item["metrics"][class_name]["recall"] >= config.target_recall,
                    item["class_score"],
                    -item["thresholds"][class_id],
                ),
                reverse=True,
            )[0]
            selected_thresholds[class_id] = best_class["thresholds"][class_id]

        final_labels_dir = temp_root / "final_selected"
        filter_prediction_labels(prediction_label_dir, final_labels_dir, selected_thresholds)
        final_result = evaluate_probe(image_dir, truth_label_dir, final_labels_dir, class_names=resolved_class_names)
        final_metrics = _metrics_by_name(final_result)
        best = {
            "thresholds": selected_thresholds,
            "metrics": final_metrics,
            "qualified": _qualified(final_metrics, config.target_precision, config.target_recall),
            "score": _score_metrics(final_metrics, config.target_precision, config.target_recall),
        }
    return {"best": best, "candidate_count": len(candidates), "class_candidates": candidates}


def _parse_threshold_grid(value: str) -> dict[int, list[float]]:
    output: dict[int, list[float]] = {}
    for item in value.split(";"):
        if not item.strip():
            continue
        class_part, thresholds_part = item.split(":", 1)
        output[int(class_part.strip())] = [float(part.strip()) for part in thresholds_part.split(",") if part.strip()]
    return output


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan per-class confidence thresholds for a YOLO probe prediction directory.")
    parser.add_argument("--images", required=True, type=Path)
    parser.add_argument("--truth-labels", required=True, type=Path)
    parser.add_argument("--prediction-labels", required=True, type=Path)
    parser.add_argument("--grid", required=True, help="Semicolon-separated grid, e.g. '0:0.2,0.3;5:0.1,0.2'")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--data-yaml", type=Path, help="Optional dataset data.yaml for class names.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = scan_thresholds(
        args.images,
        args.truth_labels,
        args.prediction_labels,
        ThresholdScanConfig(class_thresholds=_parse_threshold_grid(args.grid)),
        class_names=load_class_names(args.data_yaml) if args.data_yaml else DEFAULT_CLASS_NAMES,
    )
    if args.output_json.exists():
        args.output_json.unlink()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(_json_ready(result), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_ready(result["best"]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_CACHE = ROOT / "datasets" / "raw" / "_kagglehub_cache"

DATASETS = {
    "ppe_sh17": {
        "source": "mugheesahmad/sh17-dataset-for-ppe-detection",
        "target": ROOT / "datasets" / "raw" / "ppe" / "sh17",
        "classes": ["person", "helmet", "safety-vest"],
        "note": "Kaggle dataset. Requires Kaggle authentication.",
    },
    "fire_smoke_dfire_kaggle": {
        "source": "sayedgamal99/smoke-fire-detection-yolo",
        "target": ROOT / "datasets" / "raw" / "fire_smoke" / "dfire_kaggle",
        "classes": ["fire", "smoke"],
        "note": "Kaggle version of D-Fire. Requires Kaggle authentication.",
    },
    "fire_smoke_object_detection_kaggle": {
        "source": "azimjaan21/fire-and-smoke-dataset-object-detection-yolo",
        "target": ROOT / "datasets" / "raw" / "fire_smoke" / "fire_and_smoke_object_detection_yolo",
        "classes": ["fire", "smoke"],
        "note": "Kaggle fire and smoke object detection dataset. Requires Kaggle authentication.",
    },
    "fire_smoke_yolov9_kaggle": {
        "source": "roscoekerby/firesmoke-detection-yolo-v9",
        "target": ROOT / "datasets" / "raw" / "fire_smoke" / "firesmoke_detection_yolo_v9",
        "classes": ["fire", "smoke"],
        "note": "Kaggle fire and smoke YOLO dataset. Requires Kaggle authentication.",
    },
    "ppe_detection_v1": {
        "source": "beyzakucuk/ppe-detection-v1",
        "target": ROOT / "datasets" / "raw" / "ppe" / "ppe_detection_v1",
        "classes": ["person", "helmet", "vest"],
        "note": "Kaggle PPE dataset. Requires Kaggle authentication.",
    },
    "ppe_construction_site_kaggle": {
        "source": "snehilsanyal/construction-site-safety-image-dataset-roboflow",
        "target": ROOT / "datasets" / "raw" / "ppe" / "construction_site_safety",
        "classes": ["person", "helmet", "vest"],
        "note": "Kaggle construction safety dataset. Requires Kaggle authentication.",
    },
    "ppe_helmet_vest_kaggle": {
        "source": "maryamborzoo/safety-helmet-and-vest",
        "target": ROOT / "datasets" / "raw" / "ppe" / "safety_helmet_and_vest",
        "classes": ["person", "helmet", "vest"],
        "note": "Kaggle safety helmet and vest dataset. Requires Kaggle authentication.",
    },
    "ppe_hardhat_vest_kaggle": {
        "source": "muhammetzahitaydn/hardhat-vest-dataset-v3",
        "target": ROOT / "datasets" / "raw" / "ppe" / "hardhat_vest_v3",
        "classes": ["person", "helmet", "vest"],
        "note": "Kaggle hardhat and vest dataset. Requires Kaggle authentication.",
    },
    "ppe_goggles_gloves_kaggle": {
        "source": "shlokraval/ppe-dataset-yolov8",
        "target": ROOT / "datasets" / "raw" / "ppe" / "ppe_dataset_yolov8",
        "classes": ["person", "helmet", "vest", "goggles", "gloves"],
        "note": "Kaggle PPE YOLOv8 dataset. Requires Kaggle authentication.",
    },
}


def download_dataset(key: str) -> dict[str, str]:
    if key not in DATASETS:
        raise ValueError(f"unknown dataset key: {key}")

    dataset = DATASETS[key]
    target = Path(dataset["target"])
    target.parent.mkdir(parents=True, exist_ok=True)
    PROJECT_CACHE.mkdir(parents=True, exist_ok=True)
    os.environ["KAGGLEHUB_CACHE"] = str(PROJECT_CACHE)
    os.environ["KAGGLEHUB_CACHE_DIR"] = str(PROJECT_CACHE)

    _ensure_kaggle_auth()

    try:
        import kagglehub
    except ImportError as exc:
        raise RuntimeError("kagglehub is not installed. Run: pip install kagglehub") from exc

    downloaded_path = Path(kagglehub.dataset_download(dataset["source"]))
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(downloaded_path, target)

    manifest = {
        "key": key,
        "source": dataset["source"],
        "target": str(target),
        "project_cache": str(PROJECT_CACHE),
        "classes": dataset["classes"],
        "note": dataset["note"],
    }
    manifest_path = ROOT / "datasets" / "raw" / "_manifests" / f"{key}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"key": key, "target": str(target), "manifest": str(manifest_path)}


def _ensure_kaggle_auth() -> None:
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    kaggle_access_token = Path.home() / ".kaggle" / "access_token"
    has_legacy_env = bool(os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"))
    has_token_env = bool(os.environ.get("KAGGLE_API_TOKEN"))
    if kaggle_json.exists() or kaggle_access_token.exists() or has_legacy_env or has_token_env:
        return
    raise RuntimeError(
        "Kaggle authentication not found. Set KAGGLE_API_TOKEN, add "
        "%USERPROFILE%\\.kaggle\\access_token, add %USERPROFILE%\\.kaggle\\kaggle.json, "
        "or set KAGGLE_USERNAME and KAGGLE_KEY, then rerun this script."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Download public datasets into datasets/raw.")
    parser.add_argument(
        "datasets",
        nargs="*",
        default=list(DATASETS),
        help=f"Dataset keys: {', '.join(DATASETS)}",
    )
    args = parser.parse_args()

    results = []
    errors = []
    for key in args.datasets:
        try:
            results.append(download_dataset(key))
        except Exception as exc:  # noqa: BLE001 - CLI should report all dataset failures.
            errors.append({"key": key, "error": str(exc)})

    payload = {"results": results, "errors": errors}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

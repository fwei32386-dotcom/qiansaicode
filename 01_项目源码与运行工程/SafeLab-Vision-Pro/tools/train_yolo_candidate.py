from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a YOLO candidate with Windows-safe defaults.")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--name", required=True)
    parser.add_argument("--project", default="D:/ELFrk3588/yolo_training_runs")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--cache", action="store_true")
    parser.add_argument("--optimizer")
    parser.add_argument("--lr0", type=float)
    parser.add_argument("--lrf", type=float)
    parser.add_argument("--freeze", type=int)
    return parser.parse_args()


def build_train_kwargs(args: argparse.Namespace) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "data": str(args.data),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": args.device,
        "workers": args.workers,
        "cache": args.cache,
        "project": args.project,
        "name": args.name,
        "exist_ok": True,
        "patience": max(5, args.epochs),
        "plots": True,
    }
    if args.optimizer is not None:
        kwargs["optimizer"] = args.optimizer
    if args.lr0 is not None:
        kwargs["lr0"] = args.lr0
    if args.lrf is not None:
        kwargs["lrf"] = args.lrf
    if args.freeze is not None:
        kwargs["freeze"] = args.freeze
    return kwargs


def main() -> int:
    from ultralytics import YOLO

    args = parse_args()
    model = YOLO(args.model)
    model.train(**build_train_kwargs(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from runtime.interfaces import Detection


def load_mock_detections(case: str) -> list[Detection]:
    if case == "ppe":
        return [
            Detection(
                frame_id=1,
                source_type="mock",
                class_name="person",
                confidence=0.94,
                bbox=[100, 120, 360, 680],
                center=[230, 400],
                area=145600,
                model_name="mock_detector",
                infer_time_ms=0.1,
            ),
            Detection(
                frame_id=1,
                source_type="mock",
                class_name="vest",
                confidence=0.88,
                bbox=[140, 330, 330, 610],
                center=[235, 470],
                area=53200,
                model_name="mock_detector",
                infer_time_ms=0.1,
            ),
        ]

    if case == "smoke":
        return [
            Detection(
                frame_id=2,
                source_type="mock",
                class_name="smoke",
                confidence=0.81,
                bbox=[420, 100, 760, 380],
                center=[590, 240],
                area=95200,
                model_name="mock_detector",
                infer_time_ms=0.1,
            )
        ]

    if case == "safe":
        return [
            Detection(
                frame_id=3,
                source_type="mock",
                class_name="person",
                confidence=0.95,
                bbox=[100, 120, 360, 680],
                center=[230, 400],
                area=145600,
                model_name="mock_detector",
                infer_time_ms=0.1,
            ),
            Detection(
                frame_id=3,
                source_type="mock",
                class_name="helmet",
                confidence=0.9,
                bbox=[160, 125, 300, 240],
                center=[230, 180],
                area=16100,
                model_name="mock_detector",
                infer_time_ms=0.1,
            ),
            Detection(
                frame_id=3,
                source_type="mock",
                class_name="vest",
                confidence=0.89,
                bbox=[140, 330, 330, 610],
                center=[235, 470],
                area=53200,
                model_name="mock_detector",
                infer_time_ms=0.1,
            ),
        ]

    raise ValueError(f"unknown mock case: {case}")


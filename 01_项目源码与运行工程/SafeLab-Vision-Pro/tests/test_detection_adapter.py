from __future__ import annotations

import unittest

from ai_engine.detection_adapter import adapt_model_outputs
from runtime.interfaces import VideoFrame


class DetectionAdapterTest(unittest.TestCase):
    def test_array_outputs_convert_to_detection_contract(self) -> None:
        frame = VideoFrame(
            frame_id=7,
            source_type="camera",
            timestamp=1.0,
            width=1280,
            height=720,
            source_name="ov13855",
            frame=object(),
        )
        detections = adapt_model_outputs(
            [[10.2, 20.6, 110.4, 220.9, 0.91, 0], [100, 120, 200, 260, 0.83, 2]],
            frame,
            model_name="rknn_stub",
            infer_time_ms=12.5,
        )

        self.assertEqual(len(detections), 2)
        self.assertEqual(detections[0].class_name, "person")
        self.assertEqual(detections[0].bbox, [10, 21, 110, 221])
        self.assertEqual(detections[0].center, [60, 121])
        self.assertEqual(detections[0].source_type, "camera")
        self.assertEqual(detections[1].class_name, "vest")

    def test_dict_outputs_filter_confidence_and_clip_bbox(self) -> None:
        frame = VideoFrame(
            frame_id=8,
            source_type="camera",
            timestamp=1.0,
            width=640,
            height=480,
            source_name="ov13855",
        )
        detections = adapt_model_outputs(
            [
                {"bbox": [-5, 10, 650, 490], "score": 0.8, "class_id": 6},
                {"bbox": [1, 1, 5, 5], "score": 0.1, "class_id": 1},
            ],
            frame,
            min_confidence=0.5,
        )

        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].class_name, "smoke")
        self.assertEqual(detections[0].bbox, [0, 10, 639, 479])

    def test_invalid_label_id_raises_clear_error(self) -> None:
        frame = VideoFrame(
            frame_id=1,
            source_type="camera",
            timestamp=1.0,
            width=640,
            height=480,
            source_name="ov13855",
        )

        with self.assertRaisesRegex(ValueError, "outside labels range"):
            adapt_model_outputs([[0, 0, 10, 10, 0.9, 99]], frame)


if __name__ == "__main__":
    unittest.main()

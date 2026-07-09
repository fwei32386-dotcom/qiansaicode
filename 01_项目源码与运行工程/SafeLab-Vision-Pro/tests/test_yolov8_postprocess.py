from __future__ import annotations

import unittest

from ai_engine.detection_adapter import adapt_model_outputs
from ai_engine.yolov8_postprocess import (
    LetterboxMeta,
    dequantize_int8,
    postprocess_yolov8_output,
)
from runtime.interfaces import VideoFrame


class Yolov8PostprocessTest(unittest.TestCase):
    def test_dequantize_int8_uses_rknn_formula(self) -> None:
        values = dequantize_int8([-128, -127, 0], zero_point=-128, scale=0.5)

        self.assertEqual(values, [0.0, 0.5, 64.0])

    def test_letterbox_meta_for_ov13855(self) -> None:
        meta = LetterboxMeta(source_width=4224, source_height=3136)

        self.assertAlmostEqual(meta.scale, 640 / 4224)
        self.assertAlmostEqual(meta.pad_x, 0.0)
        self.assertGreater(meta.pad_y, 0.0)

    def test_postprocess_filters_nms_and_converts_to_detection(self) -> None:
        output = [[0.0, 0.0, 0.0] for _ in range(11)]
        output[0] = [320.0, 322.0, 100.0]
        output[1] = [320.0, 322.0, 100.0]
        output[2] = [120.0, 118.0, 80.0]
        output[3] = [160.0, 158.0, 90.0]
        output[4] = [0.92, 0.88, 0.10]
        output[6] = [0.05, 0.04, 0.83]

        raw = postprocess_yolov8_output(
            output,
            source_width=1280,
            source_height=720,
            confidence_threshold=0.25,
            nms_iou_threshold=0.5,
        )
        frame = VideoFrame(
            frame_id=1,
            source_type="camera",
            timestamp=1.0,
            width=1280,
            height=720,
            source_name="ov13855",
        )
        detections = adapt_model_outputs(raw, frame)

        self.assertEqual(len(detections), 2)
        self.assertEqual(detections[0].class_name, "person")
        self.assertEqual(detections[1].class_name, "vest")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "rknn_transfer_package" / "convert_dual_onnx_to_rknn_fp.py"


def load_module():
    spec = importlib.util.spec_from_file_location("convert_dual_onnx_to_rknn_fp", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ConvertDualOnnxToRknnTests(unittest.TestCase):
    def test_quantized_output_suffix_is_optional_and_non_destructive(self) -> None:
        module = load_module()
        spec = module.MODEL_SPECS["ppe"]

        default_output = spec.output_for(quantized=True)
        suffixed_output = spec.output_for(
            quantized=True,
            output_suffix="int8_normal_hybrid_level2",
        )

        self.assertTrue(default_output.name.endswith("_int8.rknn"))
        self.assertTrue(suffixed_output.name.endswith("_int8_normal_hybrid_level2.rknn"))
        self.assertNotEqual(default_output, suffixed_output)


if __name__ == "__main__":
    unittest.main()

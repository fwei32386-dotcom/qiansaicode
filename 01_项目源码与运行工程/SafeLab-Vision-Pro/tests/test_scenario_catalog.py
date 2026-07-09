from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.generate_scenario_catalog import generate_scenario_catalog


class ScenarioCatalogTest(unittest.TestCase):
    def test_scenario_catalog_summarizes_scenarios_and_expected_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenarios = root / "data" / "mock_scenarios"
            configs = root / "configs"
            reports = root / "reports"
            scenarios.mkdir(parents=True)
            configs.mkdir()
            (scenarios / "sample.json").write_text(
                json.dumps(
                    {
                        "name": "sample",
                        "detections": [
                            {"frame_id": 1, "class_name": "person", "confidence": 0.9},
                            {"frame_id": 1, "class_name": "helmet", "confidence": 0.8},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (configs / "evaluation_cases.json").write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "id": "case_sample",
                                "type": "single",
                                "input": "data/mock_scenarios/sample.json",
                                "expected": {"events": 0},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            outputs = generate_scenario_catalog(
                scenarios,
                configs / "evaluation_cases.json",
                reports / "scenario_catalog.json",
                reports / "scenario_catalog.html",
            )
            catalog = json.loads(Path(outputs["json"]).read_text(encoding="utf-8"))
            html = Path(outputs["html"]).read_text(encoding="utf-8")

        self.assertEqual(catalog["scenario_count"], 1)
        self.assertEqual(catalog["scenarios"][0]["class_counts"]["person"], 1)
        self.assertEqual(catalog["scenarios"][0]["evaluation_cases"][0]["id"], "case_sample")
        self.assertIn("SafeLab Scenario Catalog", html)


if __name__ == "__main__":
    unittest.main()

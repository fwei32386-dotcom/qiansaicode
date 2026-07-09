from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.generate_config_audit import generate_config_audit


class ConfigAuditTest(unittest.TestCase):
    def test_config_audit_reports_hashes_and_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configs = root / "configs"
            reports = root / "reports"
            configs.mkdir()
            (configs / "rule_dsl.json").write_text(
                json.dumps({"rules": [{"id": "R001", "priority": 10}]}),
                encoding="utf-8",
            )
            (configs / "model_config.yaml").write_text(
                "model:\n  labels:\n    - person\n",
                encoding="utf-8",
            )

            outputs = generate_config_audit(
                configs,
                reports / "config_audit.json",
                reports / "config_audit.html",
            )
            audit = json.loads(Path(outputs["json"]).read_text(encoding="utf-8"))
            html = Path(outputs["html"]).read_text(encoding="utf-8")

        self.assertEqual(audit["file_count"], 2)
        self.assertIn("sha256", audit["files"][0])
        self.assertIn("rules_count", json.dumps(audit, ensure_ascii=False))
        self.assertIn("SafeLab \u914d\u7f6e\u5ba1\u8ba1", html)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.export_demo_package import export_demo_package
from tools.export_demo_package import _export_sources


class DemoExportTest(unittest.TestCase):
    def test_export_demo_package_writes_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = export_demo_package(Path(tmp) / "demo_export.zip")
            with zipfile.ZipFile(output) as zf:
                names = set(zf.namelist())

        self.assertIn("manifest.json", names)
        self.assertIn("README.md", names)
        self.assertIn("configs/rule_dsl.json", names)

    def test_export_sources_include_sqlite_alarm_log(self) -> None:
        self.assertIn("data/events/alarm_log.db", _export_sources())


if __name__ == "__main__":
    unittest.main()

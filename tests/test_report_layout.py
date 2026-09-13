"""Prevent report generation from restoring obsolete root-level copies."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from src.autonomous.report import write_finals


class TestReportLayout(unittest.TestCase):
    def test_reports_stay_in_the_selected_output_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.dict(os.environ, {"FYP_AUTONOMOUS_OUT": "outputs/fixture"}):
                write_finals(root)
            output = root / "outputs/fixture"
            self.assertTrue((output / "FACTS.json").is_file())
            self.assertTrue((output / "CLAIMS_LEDGER.md").is_file())
            self.assertTrue((output / "RESEARCH_SUMMARY.md").is_file())
            self.assertEqual(list(root.glob("FINAL_*")), [])
            self.assertFalse((root / "outputs/autonomous").exists())


if __name__ == "__main__":
    unittest.main()

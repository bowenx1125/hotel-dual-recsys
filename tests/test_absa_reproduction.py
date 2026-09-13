"""ABSA reproduction routing and subprocess contract (synthetic/mocked only)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_absa_agreement import _output_base
from src.autonomous.absa import run_absa_audit


class TestAbsaOutputRouting(unittest.TestCase):
    def test_script_default_output_base_is_reproduced(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FYP_AUTONOMOUS_OUT", None)
            base = _output_base(ROOT)
        self.assertEqual(base, ROOT / "outputs" / "autonomous" / "reproduced")

    def test_script_output_base_relative_env(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.dict(os.environ, {"FYP_AUTONOMOUS_OUT": "outputs/fixture/absa"}):
                base = _output_base(root)
            self.assertEqual(base, root / "outputs" / "fixture" / "absa")

    def test_script_output_base_absolute_env(self):
        with tempfile.TemporaryDirectory() as td:
            abs_base = Path(td) / "isolated"
            with patch.dict(os.environ, {"FYP_AUTONOMOUS_OUT": str(abs_base)}):
                base = _output_base(Path(td))
            self.assertEqual(base, abs_base)


class TestRunAbsaAudit(unittest.TestCase):
    def _isolated_env(self, rel: str = "outputs/fixture/absa") -> dict[str, str]:
        return {"FYP_AUTONOMOUS_OUT": rel}

    def test_verify_only_skips_subprocess(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.dict(os.environ, self._isolated_env()):
                with patch("src.autonomous.absa.subprocess.run") as mock_run:
                    out = run_absa_audit(root, verify_only=True)
            mock_run.assert_not_called()
            self.assertEqual(out["status"], "SKIPPED_VERIFY_ONLY")
            audit = json.loads(
                (root / "outputs/fixture/absa/wave1/absa_audit.json").read_text(encoding="utf-8")
            )
            self.assertEqual(audit["status"], "SKIPPED_VERIFY_ONLY")
            self.assertEqual(out["reference_type"], "weak_section_labels")
            self.assertTrue(out["independent_accuracy_not_established"])
            self.assertTrue(out["fixed_sampler_2800"])
            self.assertNotIn("HUMAN_VALIDATION_REQUIRED", out)

    def test_successful_subprocess_merges_isolated_result(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wave1 = root / "outputs/fixture/absa/wave1"
            wave1.mkdir(parents=True)
            (root / "scripts").mkdir()
            (root / "scripts/run_absa_agreement.py").write_text("# Mocked subprocess fixture\n")

            def _fake_run(cmd, cwd=None, env=None, capture_output=None, text=None):
                audit = wave1 / "absa_audit.json"
                audit.write_text(
                    json.dumps(
                        {
                            "status": "RAN",
                            "n_pairs": 2800,
                            "agreement_vs_weak_section_label": 0.81,
                            "cohens_kappa_vs_weak": 0.62,
                            "never_gold_accuracy": True,
                        }
                    ),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with patch.dict(os.environ, self._isolated_env()):
                with patch("src.autonomous.absa._absa_interpreter", return_value=Path(sys.executable)):
                    with patch("src.autonomous.absa.subprocess.run", side_effect=_fake_run) as mock_run:
                        out = run_absa_audit(root, verify_only=False)
            mock_run.assert_called_once()
            call_env = mock_run.call_args.kwargs["env"]
            self.assertEqual(call_env["FYP_AUTONOMOUS_OUT"], str(root / "outputs/fixture/absa"))
            self.assertEqual(call_env["HF_HUB_OFFLINE"], "1")
            self.assertEqual(call_env["TRANSFORMERS_OFFLINE"], "1")
            self.assertEqual(out["status"], "RAN")
            self.assertEqual(out["n_pairs"], 2800)
            facts = json.loads((root / "outputs/fixture/absa/FACTS.json").read_text(encoding="utf-8"))
            self.assertEqual(facts["waves"]["1b_absa"]["status"], "RAN")

    def test_nonzero_subprocess_rejects_stale_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wave1 = root / "outputs/fixture/absa/wave1"
            wave1.mkdir(parents=True)
            (root / "scripts").mkdir()
            (root / "scripts/run_absa_agreement.py").write_text("# Mocked subprocess fixture\n")
            stale = {
                "status": "RAN",
                "n_pairs": 999,
                "agreement_vs_weak_section_label": 0.99,
            }
            (wave1 / "absa_audit.json").write_text(json.dumps(stale), encoding="utf-8")

            with patch.dict(os.environ, self._isolated_env()):
                with patch("src.autonomous.absa._absa_interpreter", return_value=Path(sys.executable)):
                    with patch(
                        "src.autonomous.absa.subprocess.run",
                        return_value=subprocess.CompletedProcess([], 1, stdout="", stderr="boom"),
                    ):
                        out = run_absa_audit(root, verify_only=False)

            self.assertEqual(out["status"], "FAILED_SUBPROCESS")
            self.assertNotEqual(out.get("n_pairs"), 999)
            audit = json.loads((wave1 / "absa_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(audit["status"], "FAILED_SUBPROCESS")
            self.assertNotIn("n_pairs", audit)

    def test_no_canonical_autonomous_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            canonical = root / "outputs" / "autonomous" / "wave1"
            canonical.mkdir(parents=True)
            (canonical / "absa_audit.json").write_text('{"status":"RAN","n_pairs":1}', encoding="utf-8")

            with patch.dict(os.environ, self._isolated_env()):
                with patch("src.autonomous.absa._absa_interpreter", return_value=Path(sys.executable)):
                    with patch(
                        "src.autonomous.absa.subprocess.run",
                        return_value=subprocess.CompletedProcess([], 2, stdout="", stderr=""),
                    ):
                        run_absa_audit(root, verify_only=False)

            canonical_audit = json.loads((canonical / "absa_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(canonical_audit["n_pairs"], 1)


if __name__ == "__main__":
    unittest.main()

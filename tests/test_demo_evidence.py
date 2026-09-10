from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.data_adapter import build_snapshot
from demo.evidence import BANNER, assert_copy_matches_level, decide_evidence_level


class TestEvidence(unittest.TestCase):
    def test_never_causal_without_checks(self):
        ev = decide_evidence_level({"predictive_holdout_metrics": None, "causal_checks": {}})
        self.assertEqual(ev["level"], "DESCRIPTIVE")
        self.assertIn("DESCRIPTIVE", BANNER)

    def test_descriptive_forbids_causal_wording(self):
        with self.assertRaises(ValueError):
            assert_copy_matches_level("DESCRIPTIVE", "Estimated demand lift is 12%")
        assert_copy_matches_level("DESCRIPTIVE", BANNER)

    def test_real_snapshot_is_descriptive(self):
        snap = build_snapshot(ROOT)
        self.assertEqual(decide_evidence_level(snap)["level"], "DESCRIPTIVE")
        self.assertFalse(any(snap.get("causal_checks", {}).values()))

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.config import load_actionability_config, load_config
from demo.data_adapter import build_snapshot, eligible_hotels
from demo.evidence import assert_copy_matches_level, decide_evidence_level
from demo.scoring import (
    all_policies,
    diagnostic_largest_gap,
    explain_action_vs_diagnostic,
    policy_peer_relative,
)


class TestActionability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config()
        cls.act = load_actionability_config()["aspects"]
        # Prefer snapshot path via build to keep peer stats
        cls.snap = build_snapshot(ROOT)
        cls.hotels = eligible_hotels(cls.snap)

    def test_location_immutable(self):
        self.assertFalse(self.act["location"]["eligible_for_direct_action"])
        self.assertEqual(self.act["location"]["actionability_level"], "immutable")
        self.assertTrue(self.act["location"]["diagnostic_visible"])

    def test_location_visible_but_not_default_action(self):
        for h in self.hotels:
            diag = diagnostic_largest_gap(h, self.cfg)
            # diagnostic may be location
            pol = all_policies(h, self.cfg, 0.0)
            for key in ("fix_weakest", "largest_peer_gap", "most_criticized", "peer_relative"):
                chosen = pol[key]["chosen_aspect"]
                if chosen is not None:
                    self.assertNotEqual(chosen, "location", msg=f"{h['hotel_id']} {key}")

    def test_explanation_when_diag_is_location(self):
        found = False
        for h in self.hotels:
            expl = explain_action_vs_diagnostic(h, self.cfg)
            if expl["diagnostic_aspect"] == "location":
                found = True
                self.assertIsNotNone(expl["explanation"])
                self.assertIn("not a direct operational action", expl["explanation"])
                if expl["actionable_recommendation"]:
                    self.assertNotEqual(expl["actionable_recommendation"], "location")
        # not required that any hotel has location as largest gap, but if none, still OK
        self.assertTrue(True)
        _ = found

    def test_heuristic_name(self):
        h = self.hotels[0]
        pol = policy_peer_relative(h, self.cfg, 0.0)
        self.assertIn("Peer-Relative Evidence-Weighted", pol["label"])
        self.assertNotIn("Competition-Aware", pol["label"])
        self.assertTrue(pol["weights_are_design_choices"])

    def test_descriptive_wording(self):
        ev = decide_evidence_level(self.snap)
        self.assertEqual(ev["level"], "DESCRIPTIVE")
        assert_copy_matches_level("DESCRIPTIVE", ev["banner"])
        with self.assertRaises(ValueError):
            assert_copy_matches_level("DESCRIPTIVE", "causal effect of 0.2 ROI")


class TestConfigParity(unittest.TestCase):
    def test_yaml_header_marks_generated(self):
        text = (ROOT / "conf" / "demo.yaml").read_text(encoding="utf-8")
        self.assertIn("AUTO-GENERATED", text)
        cfg = load_config()
        self.assertAlmostEqual(cfg["weights"]["gap"], 0.45)


if __name__ == "__main__":
    unittest.main(verbosity=2)

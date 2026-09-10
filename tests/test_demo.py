#!/usr/bin/env python3
"""unittest suite for the provider Demo (stdlib + snapshot)."""
from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.config import load_config
from demo.data_adapter import build_snapshot, eligible_hotels, save_snapshot
from demo.evidence import BANNER, assert_copy_matches_level, decide_evidence_level
from demo.scoring import all_policies, competition_aware_scores, fnum, is_finite


class TestConfig(unittest.TestCase):
    def test_config_loads(self):
        cfg = load_config()
        self.assertGreaterEqual(len(cfg["aspects"]), 7)
        self.assertAlmostEqual(sum(cfg["weights"].values()), 1.0, places=6)


class TestDataAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = build_snapshot(ROOT)
        cls.hotels = eligible_hotels(cls.snap)

    def test_reads_real_tables(self):
        self.assertGreaterEqual(self.snap["n_hotels_in_aspect_table"], 24)
        self.assertGreaterEqual(self.snap["n_eligible_hotels"], 3)
        self.assertFalse(self.snap["synthetic"])
        self.assertIn("aspect_features", self.snap["source_file_hashes"])

    def test_schema_and_finite_numbers(self):
        h = self.hotels[0]
        for key in ("hotel_id", "hotel_url", "compset_id", "n_reviews"):
            self.assertIn(key, h)
        for a, rec in h["aspects"].items():
            for k, v in rec.items():
                if isinstance(v, float):
                    self.assertTrue(math.isfinite(v), msg=f"{h['hotel_id']} {a} {k}={v}")

    def test_missing_optional_fields_do_not_crash(self):
        # price/star may be missing; adapter must still emit the hotel
        missing_price = [h for h in self.snap["hotels"] if h.get("price") is None]
        self.assertIsInstance(missing_price, list)
        for h in self.hotels:
            self.assertIn("peer_count", h)
            self.assertTrue(h["compset_valid"])


class TestScoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = build_snapshot(ROOT)
        cls.cfg = cls.snap["config"]
        cls.hotel = eligible_hotels(cls.snap)[0]

    def test_reproducible(self):
        a = all_policies(self.hotel, self.cfg, 0.0)
        b = all_policies(self.hotel, self.cfg, 0.0)
        self.assertEqual(
            {k: v["chosen_aspect"] for k, v in a.items()},
            {k: v["chosen_aspect"] for k, v in b.items()},
        )

    def test_finite_scores(self):
        scores = competition_aware_scores(self.hotel, self.cfg, 0.3)
        for a, s in scores.items():
            self.assertTrue(is_finite(s), msg=f"{a}={s}")

    def test_intensity_is_scenario_only(self):
        s0 = all_policies(self.hotel, self.cfg, 0.0)["competition_aware"]
        self.assertTrue(s0.get("heuristic"))
        rule = s0["rule"].lower()
        self.assertTrue("not learned" in rule or "design-choice" in rule)
        self.assertIn("scenario", rule)


class TestEvidence(unittest.TestCase):
    def test_never_causal_without_checks(self):
        snap = {"predictive_holdout_metrics": None, "causal_checks": {}}
        ev = decide_evidence_level(snap)
        self.assertEqual(ev["level"], "DESCRIPTIVE")
        self.assertIn("DESCRIPTIVE", BANNER)

    def test_filename_does_not_upgrade(self):
        snap = {
            "predictive_holdout_metrics": None,
            "causal_checks": {"event_study": False},
        }
        self.assertEqual(decide_evidence_level(snap)["level"], "DESCRIPTIVE")

    def test_descriptive_forbids_causal_wording(self):
        with self.assertRaises(ValueError):
            assert_copy_matches_level("DESCRIPTIVE", "This causal effect is 0.2")
        assert_copy_matches_level("DESCRIPTIVE", BANNER)

    def test_real_snapshot_is_descriptive(self):
        snap = build_snapshot(ROOT)
        self.assertEqual(decide_evidence_level(snap)["level"], "DESCRIPTIVE")


class TestProvenance(unittest.TestCase):
    def test_hotel_compset_aspect_traceable(self):
        snap = build_snapshot(ROOT)
        h = eligible_hotels(snap)[0]
        self.assertTrue(h["hotel_id"])
        self.assertTrue(h["compset_id"])
        self.assertTrue(h["source_files"])
        pol = all_policies(h, snap["config"], 0.0)
        for p in pol.values():
            self.assertIn("rule", p)
            self.assertTrue(p["chosen_aspect"] is None or p["chosen_aspect"] in snap["aspects"])


class TestSmoke(unittest.TestCase):
    def test_end_to_end_snapshot_roundtrip(self):
        snap = build_snapshot(ROOT)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "snap.json"
            save_snapshot(snap, p)
            data = json.loads(p.read_text())
            self.assertGreaterEqual(data["n_eligible_hotels"], 3)
            h = [x for x in data["hotels"] if x["eligible"]][0]
            pol = all_policies(h, data["config"], 0.0)
            # four strategies + competition_aware alias
            self.assertGreaterEqual(len(pol), 4)
            self.assertIn("peer_relative", pol)
            self.assertIn("competition_aware", pol)

    def test_cli_scripts_exist(self):
        self.assertTrue((ROOT / "scripts" / "build_demo_snapshot.py").exists())
        self.assertTrue((ROOT / "demo" / "app.py").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

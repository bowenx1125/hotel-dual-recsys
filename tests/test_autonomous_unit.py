"""Unit tests for autonomous primitives + synthetic estimator (no 515K)."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.autonomous.common import (
    canonical_hotel_id,
    classify_period_completeness,
    fold_from_fingerprint,
    quarter_bounds,
    raw_net,
    review_fingerprint,
    smoothed_net,
)
from src.temporal.gates import classify_gate
from src.autonomous.report import synthetic_estimator_probe


class TestPeriods(unittest.TestCase):
    def test_expected_completeness(self):
        dmin, dmax = date(2015, 8, 4), date(2017, 8, 3)
        self.assertEqual(classify_period_completeness(dmin, dmax, "2015Q3"), "partial")
        self.assertEqual(classify_period_completeness(dmin, dmax, "2015Q4"), "complete")
        self.assertEqual(classify_period_completeness(dmin, dmax, "2017Q2"), "complete")
        self.assertEqual(classify_period_completeness(dmin, dmax, "2017Q3"), "partial")
        s, e = quarter_bounds("2015Q3")
        self.assertEqual(s, date(2015, 7, 1))
        self.assertEqual(e, date(2015, 9, 30))


class TestMeasurementRules(unittest.TestCase):
    def test_zero_mention_raw_nan(self):
        self.assertTrue(np.isnan(raw_net(0, 0)))
        sn, rel = smoothed_net(0, 0, 10)
        self.assertEqual(sn, 0.0)
        self.assertEqual(rel, 0.0)

    def test_shrinkage_not_empirical_bayes_in_config(self):
        cfg = json.loads((ROOT / "conf" / "autonomous_research.json").read_text())
        self.assertEqual(cfg["shrinkage"]["method"], "symmetric_beta_binomial_bayesian_shrinkage")
        self.assertNotIn("empirical_bayes", cfg["shrinkage"]["method"])

    def test_folds_deterministic_disjoint(self):
        fp1 = review_fingerprint("a", "2016-01-01", "8", "UK", "pos", "neg")
        fp2 = review_fingerprint("a", "2016-01-01", "8", "UK", "pos", "neg")
        self.assertEqual(fp1, fp2)
        self.assertEqual(fold_from_fingerprint(fp1), fold_from_fingerprint(fp2))
        # many fingerprints split both ways
        labs = {fold_from_fingerprint(review_fingerprint("a", str(i), "8", "UK", "x", "y")) for i in range(50)}
        self.assertEqual(labs, {"A", "B"})

    def test_hotel_id_format(self):
        hid = canonical_hotel_id("1 Example Street London United Kingdom")
        self.assertTrue(hid.startswith("d1_europe:"))
        self.assertEqual(len(hid.split(":")[1]), 12)
        self.assertEqual(hid, canonical_hotel_id("1 Example Street London United Kingdom"))


class TestGateExtracted(unittest.TestCase):
    def test_classify_green(self):
        green = {
            "min_hotels_with_coverage": 500, "min_valid_cells": 20000,
            "min_candidate_events": 300, "min_event_hotels": 200,
            "min_event_cities": 4, "min_event_aspects": 4,
            "min_events_exposure_gt0": 100, "min_events_exposure_eq0": 100,
            "min_frac_events_with_2pre_2post": 0.70,
        }
        m = {
            "hotels_with_enough_coverage": 1458, "valid_cells": 80686,
            "candidate_events": 5774, "event_hotels": 1288, "event_cities": 6,
            "event_aspects": 7, "events_exposure_gt0": 4894, "events_exposure_eq0": 880,
            "frac_events_2pre_2post": 1.0,
        }
        v, _ = classify_gate(m, green)
        self.assertEqual(v, "GREEN")


class TestSyntheticEstimator(unittest.TestCase):
    def test_positive_and_null(self):
        r = synthetic_estimator_probe(42)
        self.assertTrue(r["not_paper_evidence"])
        self.assertTrue(r["positive_direction_recovered"])
        self.assertTrue(r["null_no_false_effect"])


if __name__ == "__main__":
    unittest.main()

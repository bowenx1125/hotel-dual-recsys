"""Tests for temporal panel, peers, feasibility gates, wording."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from src.temporal.aspect_gate import gate_aspects, is_placeholder, smoothed_net
from src.temporal.geo_parse import hotel_id_from_address, parse_city_country


class TestPlaceholdersAndGate(unittest.TestCase):
    def test_placeholders(self):
        ph = ["no negative", "nothing", "n/a"]
        self.assertTrue(is_placeholder("No Negative", ph))
        self.assertTrue(is_placeholder("Nothing", ["nothing"]))
        self.assertFalse(is_placeholder("The room was noisy at night", ph))

    def test_no_negative_not_noise(self):
        # "No Negative" placeholder should not be gated as text in panel builder,
        # but if gated raw, ensure gate on empty after placeholder concept.
        self.assertEqual(gate_aspects(""), [])

    def test_gate_breakfast(self):
        hits = gate_aspects("Breakfast buffet was excellent")
        self.assertIn("breakfast", hits)

    def test_smoothed_shrinkage(self):
        n1, r1 = smoothed_net(1, 0, 10)
        n100, r100 = smoothed_net(100, 0, 10)
        self.assertLess(n1, n100)
        self.assertLess(r1, r100)


class TestGeoParse(unittest.TestCase):
    def test_known_cities(self):
        city, country = parse_city_country(
            "s Gravesandestraat 55 Oost 1092 AA Amsterdam Netherlands"
        )
        self.assertEqual(city, "Amsterdam")
        self.assertEqual(country, "Netherlands")

    def test_hotel_id_stable(self):
        a = "Hotel Address London United Kingdom"
        self.assertEqual(hotel_id_from_address(a), hotel_id_from_address(a))


class TestPeerDeterminism(unittest.TestCase):
    def test_no_self_cross_city(self):
        from scripts.build_geo_reference_sets import haversine_km, knn_edges

        h = pd.DataFrame([
            {"hotel_id": "a", "hotel_name": "A", "city": "X", "latitude": 51.5, "longitude": -0.1},
            {"hotel_id": "b", "hotel_name": "B", "city": "X", "latitude": 51.51, "longitude": -0.11},
            {"hotel_id": "c", "hotel_name": "C", "city": "X", "latitude": 51.52, "longitude": -0.12},
            {"hotel_id": "d", "hotel_name": "D", "city": "Y", "latitude": 48.8, "longitude": 2.3},
        ])
        e = knn_edges(h, k=2)
        self.assertEqual((e["hotel_id"] == e["peer_hotel_id"]).sum(), 0)
        # no cross city
        for row in e.itertuples():
            hc = h.set_index("hotel_id").loc[row.hotel_id, "city"]
            pc = h.set_index("hotel_id").loc[row.peer_hotel_id, "city"]
            self.assertEqual(hc, pc)
        # deterministic
        e2 = knn_edges(h, k=2)
        self.assertTrue(e.equals(e2))
        self.assertTrue(np.isfinite(haversine_km(51.5, -0.1, 51.51, -0.11)))


class TestFeasibilityGateLogic(unittest.TestCase):
    def test_classify_green(self):
        from src.temporal.gates import classify_gate

        green = {
            "min_hotels_with_coverage": 500,
            "min_valid_cells": 20000,
            "min_candidate_events": 300,
            "min_event_hotels": 200,
            "min_event_cities": 4,
            "min_event_aspects": 4,
            "min_events_exposure_gt0": 100,
            "min_events_exposure_eq0": 100,
            "min_frac_events_with_2pre_2post": 0.70,
        }
        m = {
            "hotels_with_enough_coverage": 1458,
            "valid_cells": 80686,
            "candidate_events": 5774,
            "event_hotels": 1288,
            "event_cities": 6,
            "event_aspects": 7,
            "events_exposure_gt0": 4894,
            "events_exposure_eq0": 880,
            "frac_events_2pre_2post": 1.0,
        }
        v, _ = classify_gate(m, green)
        self.assertEqual(v, "GREEN")

    def test_threshold_not_outcome_tuned_in_config(self):
        cfg = json.loads((ROOT / "conf" / "temporal_feasibility.json").read_text())
        self.assertEqual(cfg["feasibility"]["main_delta_threshold"], 0.15)


class TestNoTextLeakageSample(unittest.TestCase):
    def test_quarter_sample_columns(self):
        sample = ROOT / "outputs" / "overnight" / "temporal_panel" / "hotel_aspect_quarter_sample.csv"
        if not sample.exists():
            self.skipTest("panel sample not built")
        df = pd.read_csv(sample)
        forbidden = {"Positive_Review", "Negative_Review", "review_text", "raw_review_text"}
        self.assertTrue(forbidden.isdisjoint(set(df.columns)))
        self.assertTrue(np.isfinite(df["smoothed_net"]).all())


class TestWordingArtifacts(unittest.TestCase):
    def test_go_nogo_forbids_causal(self):
        p = ROOT / "outputs" / "overnight" / "feasibility" / "GO_NO_GO.md"
        if not p.exists():
            self.skipTest("feasibility not run")
        t = p.read_text().lower()
        self.assertIn("causal", t)
        self.assertIn("stop", t)


if __name__ == "__main__":
    unittest.main()

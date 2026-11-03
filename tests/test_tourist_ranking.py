#!/usr/bin/env python3
"""Deterministic synthetic tests for tourist-side hotel matching."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.recommendation.tourist import (
    STATUS_INSUFFICIENT,
    STATUS_OK,
    ZeroTouristWeightsError,
    rank_hotels_for_tourist,
    tourist_match_scores,
    tourist_weights_all_zero,
    uniform_tourist_weights,
    validate_tourist_weights,
)

CFG = {"aspects": ["location", "cleanliness", "breakfast", "service", "noise", "room", "value"]}


def _rec(net, rel, *, measured=True, gap=None):
    return {
        "has_measurement": measured,
        "net": net,
        "reliability": rel,
        "mention_count": 10 if measured else None,
        # gap is present on purpose: the tourist score must ignore it.
        "gap": gap,
    }


def _hotel(hid, name, city="Paris", eligible=True, **aspects):
    return {
        "hotel_id": hid,
        "hotel_name": name,
        "city": city,
        "eligible": eligible,
        "aspects": aspects,
    }


class UniformWeightTests(unittest.TestCase):
    def test_uniform_weights_equal_reliability_weighted_mean(self):
        h = _hotel(
            "h1", "A",
            cleanliness=_rec(0.6, 0.5),
            service=_rec(-0.2, 1.0),
            room=_rec(0.4, 0.5),
        )
        out = tourist_match_scores(h, uniform_tourist_weights(CFG), CFG)
        expected = (0.5 * 0.6 + 1.0 * -0.2 + 0.5 * 0.4) / (0.5 + 1.0 + 0.5)
        self.assertEqual(out["status"], STATUS_OK)
        self.assertAlmostEqual(out["score"], expected, places=12)
        self.assertEqual(out["used_aspects"], ["cleanliness", "service", "room"])
        self.assertEqual(out["strongest_aspect"], "cleanliness")
        self.assertEqual(out["weakest_aspect"], "service")

    def test_contributions_sum_to_score(self):
        h = _hotel("h1", "A", cleanliness=_rec(0.3, 0.7), noise=_rec(-0.5, 0.4), value=_rec(0.1, 0.9))
        out = tourist_match_scores(h, {"cleanliness": 2, "noise": 1, "value": 3}, CFG)
        total = sum(r["contribution"] for r in out["aspects"].values() if r["used"])
        self.assertAlmostEqual(total, out["score"], places=12)

    def test_none_weights_default_to_uniform(self):
        h = _hotel("h1", "A", cleanliness=_rec(0.3, 0.7), noise=_rec(-0.5, 0.4))
        a = tourist_match_scores(h, None, CFG)
        b = tourist_match_scores(h, uniform_tourist_weights(CFG, 3), CFG)
        self.assertAlmostEqual(a["score"], b["score"], places=12)

    def test_gap_is_ignored(self):
        base = dict(cleanliness=_rec(0.3, 0.7, gap=0.0), service=_rec(0.1, 0.5, gap=0.0))
        moved = dict(cleanliness=_rec(0.3, 0.7, gap=0.9), service=_rec(0.1, 0.5, gap=-0.9))
        a = tourist_match_scores(_hotel("h", "A", **base), None, CFG)
        b = tourist_match_scores(_hotel("h", "A", **moved), None, CFG)
        self.assertEqual(a["score"], b["score"])


class SingleAspectWeightTests(unittest.TestCase):
    def test_single_aspect_score_is_that_net(self):
        h = _hotel("h1", "A", breakfast=_rec(-0.25, 0.3), service=_rec(0.9, 1.0))
        out = tourist_match_scores(h, {"breakfast": 5}, CFG)
        self.assertAlmostEqual(out["score"], -0.25, places=12)
        self.assertEqual(out["used_aspects"], ["breakfast"])
        self.assertEqual(out["strongest_aspect"], "breakfast")
        self.assertIsNone(out["weakest_aspect"])
        self.assertFalse(out["aspects"]["service"]["used"])
        self.assertTrue(out["aspects"]["service"]["measured"])
        self.assertIsNone(out["aspects"]["service"]["contribution"])

    def test_single_aspect_reorders_ranking(self):
        hotels = [
            _hotel("a", "Good breakfast", breakfast=_rec(0.8, 0.9), service=_rec(-0.6, 0.9)),
            _hotel("b", "Good service", breakfast=_rec(-0.4, 0.9), service=_rec(0.7, 0.9)),
        ]
        by_breakfast = rank_hotels_for_tourist(hotels, "Paris", {"breakfast": 1}, CFG)
        by_service = rank_hotels_for_tourist(hotels, "Paris", {"service": 1}, CFG)
        self.assertEqual([r["hotel_id"] for r in by_breakfast], ["a", "b"])
        self.assertEqual([r["hotel_id"] for r in by_service], ["b", "a"])


class MissingMeasurementTests(unittest.TestCase):
    def test_unmeasured_and_nonfinite_aspects_are_skipped(self):
        h = _hotel(
            "h1", "A",
            cleanliness=_rec(0.5, 0.5),
            breakfast=_rec(None, None, measured=False),
            service=_rec(0.9, float("nan")),
            noise=_rec(float("inf"), 0.5),
            room=_rec(0.2, 1.5),  # reliability out of [0, 1]
        )
        out = tourist_match_scores(h, None, CFG)
        self.assertEqual(out["status"], STATUS_OK)
        self.assertEqual(out["used_aspects"], ["cleanliness"])
        self.assertFalse(out["aspects"]["breakfast"]["measured"])
        self.assertAlmostEqual(out["score"], 0.5, places=12)
        # 7 equal weights, only one measured.
        self.assertAlmostEqual(out["weight_coverage"], 1 / 7, places=12)

    def test_measured_false_ignores_stale_net(self):
        h = _hotel("h1", "A", cleanliness=_rec(0.5, 0.5), service=_rec(-0.9, 0.9, measured=False))
        out = tourist_match_scores(h, None, CFG)
        self.assertAlmostEqual(out["score"], 0.5, places=12)

    def test_zero_denominator_is_insufficient_evidence(self):
        h = _hotel("h1", "A", cleanliness=_rec(0.5, 0.0), breakfast=_rec(None, None, measured=False))
        out = tourist_match_scores(h, None, CFG)
        self.assertEqual(out["status"], STATUS_INSUFFICIENT)
        self.assertIsNone(out["score"])
        self.assertIsNone(out["strongest_aspect"])

    def test_insufficient_when_only_weighted_aspect_missing(self):
        h = _hotel("h1", "A", service=_rec(0.5, 0.8))
        out = tourist_match_scores(h, {"breakfast": 4}, CFG)
        self.assertEqual(out["status"], STATUS_INSUFFICIENT)

    def test_insufficient_hotels_listed_after_ranked_without_rank(self):
        hotels = [
            _hotel("x", "Zeta", breakfast=_rec(None, None, measured=False)),
            _hotel("y", "Alpha", cleanliness=_rec(-0.9, 0.5)),
        ]
        ranked = rank_hotels_for_tourist(hotels, "Paris", None, CFG)
        self.assertEqual([r["hotel_id"] for r in ranked], ["y", "x"])
        self.assertEqual(ranked[0]["rank"], 1)
        self.assertIsNone(ranked[1]["rank"])
        self.assertEqual(ranked[1]["status"], STATUS_INSUFFICIENT)


class ZeroWeightTests(unittest.TestCase):
    def test_all_zero_weights_refuse_scoring(self):
        h = _hotel("h1", "A", cleanliness=_rec(0.5, 0.5))
        zero = {a: 0 for a in CFG["aspects"]}
        self.assertTrue(tourist_weights_all_zero(zero))
        with self.assertRaises(ZeroTouristWeightsError):
            tourist_match_scores(h, zero, CFG)
        with self.assertRaises(ZeroTouristWeightsError):
            rank_hotels_for_tourist([h], "Paris", zero, CFG)
        with self.assertRaises(ZeroTouristWeightsError):
            rank_hotels_for_tourist([h], "Paris", {}, CFG)

    def test_invalid_weights_raise(self):
        with self.assertRaises(ValueError):
            validate_tourist_weights({"cleanliness": -1}, CFG)
        with self.assertRaises(ValueError):
            validate_tourist_weights({"cleanliness": float("nan")}, CFG)
        with self.assertRaises(ValueError):
            validate_tourist_weights({"pool": 1}, CFG)

    def test_uniform_is_not_all_zero(self):
        self.assertFalse(tourist_weights_all_zero(uniform_tourist_weights(CFG)))
        self.assertFalse(tourist_weights_all_zero(None))


class RankingOrderTests(unittest.TestCase):
    def test_ties_break_by_name_then_id(self):
        same = dict(cleanliness=_rec(0.4, 0.6))
        hotels = [
            _hotel("id-3", "Beta", **same),
            _hotel("id-2", "Alpha", **same),
            _hotel("id-1", "Alpha", **same),
            _hotel("id-0", "Gamma", cleanliness=_rec(0.5, 0.6)),
        ]
        ranked = rank_hotels_for_tourist(hotels, "Paris", None, CFG)
        self.assertEqual([r["hotel_id"] for r in ranked], ["id-0", "id-1", "id-2", "id-3"])
        self.assertEqual([r["rank"] for r in ranked], [1, 2, 3, 4])

    def test_input_order_does_not_change_result(self):
        hotels = [
            _hotel(f"h{i}", f"Hotel {i % 3}", cleanliness=_rec(round(0.1 * (i % 4), 2), 0.5))
            for i in range(9)
        ]
        a = [r["hotel_id"] for r in rank_hotels_for_tourist(hotels, "Paris", None, CFG)]
        b = [r["hotel_id"] for r in rank_hotels_for_tourist(list(reversed(hotels)), "Paris", None, CFG)]
        self.assertEqual(a, b)

    def test_only_eligible_hotels_in_requested_city(self):
        hotels = [
            _hotel("p1", "P1", city="Paris", cleanliness=_rec(0.1, 0.5)),
            _hotel("p2", "P2", city="Paris", eligible=False, cleanliness=_rec(0.9, 0.5)),
            _hotel("l1", "L1", city="London", cleanliness=_rec(0.9, 0.5)),
        ]
        ranked = rank_hotels_for_tourist(hotels, "Paris", None, CFG)
        self.assertEqual([r["hotel_id"] for r in ranked], ["p1"])

    def test_strongest_weakest_ties_follow_aspect_order(self):
        h = _hotel("h", "A", cleanliness=_rec(0.2, 0.5), service=_rec(0.2, 0.5))
        out = tourist_match_scores(h, None, CFG)
        self.assertEqual(out["strongest_aspect"], "cleanliness")
        self.assertEqual(out["weakest_aspect"], "service")


if __name__ == "__main__":
    unittest.main()

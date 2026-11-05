#!/usr/bin/env python3
"""Synthetic tests for the review-level improvement simulation."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.config import load_actionability_config, load_config
from src.recommendation.scoring import explain_action_vs_diagnostic
from src.recommendation.simulation import (
    DEFAULT_ASSUMPTIONS,
    aggregate_mentions,
    candidate_aspects,
    city_experiment,
    compare_actions,
    follow_recommendations,
    improve_hotel,
    improve_mentions,
    outcome,
    overall_balance,
    peer_nets,
    recompute_aspect,
    synthesize_mentions,
)


def _cfg() -> dict:
    cfg = load_config()
    cfg["actionability"] = load_actionability_config()
    return cfg


CFG = _cfg()
K = float(CFG["reliability_k"])


def _measured(pos: int, neg: int) -> dict:
    return recompute_aspect({"has_measurement": True}, pos, neg, 0, K, None)


def _hotel(hid: str, counts: dict, peers=(), city="Paris", n_reviews=60) -> dict:
    aspects = {}
    for a in CFG["aspects"]:
        if a in counts:
            aspects[a] = _measured(*counts[a])
        else:
            aspects[a] = {"has_measurement": False, "mention_count": 0, "net": None, "reliability": None}
    return {
        "hotel_id": hid,
        "hotel_name": hid.upper(),
        "city": city,
        "eligible": True,
        "n_reviews": n_reviews,
        "peer_ids": list(peers),
        "peer_count": len(peers),
        "aspects": aspects,
    }


def _with_peer_fields(hotels: list[dict]) -> dict:
    by_id = {h["hotel_id"]: h for h in hotels}
    for h in hotels:
        for a, rec in h["aspects"].items():
            if rec.get("has_measurement"):
                c = (rec["pos_mentions"], rec["neg_mentions"], rec["neu_mentions"])
                h["aspects"][a] = recompute_aspect(rec, *c, K, peer_nets(h, a, by_id, CFG))
    return by_id


def _city() -> tuple[list[dict], dict]:
    base = {
        "location": (20, 2), "cleanliness": (12, 3), "breakfast": (8, 8),
        "service": (15, 2), "noise": (6, 6), "room": (10, 12), "value": (5, 5),
    }
    peers_counts = [
        {a: (p + 4, max(0, n - 2)) for a, (p, n) in base.items()},
        {a: (p + 2, n) for a, (p, n) in base.items()},
        {a: (p + 6, max(0, n - 3)) for a, (p, n) in base.items()},
    ]
    ids = ["h0", "p1", "p2", "p3"]
    hotels = [_hotel("h0", base, peers=ids[1:])]
    for i, pc in enumerate(peers_counts, start=1):
        hotels.append(_hotel(ids[i], pc, peers=[x for x in ids if x != ids[i]]))
    by_id = _with_peer_fields(hotels)
    return hotels, by_id


class RecomputeTests(unittest.TestCase):
    def test_formula_matches_definition(self):
        rec = _measured(18, 9)
        self.assertAlmostEqual(rec["net"], (18 - 9) / (27 + K), places=12)
        self.assertAlmostEqual(rec["reliability"], 27 / (27 + K), places=12)
        self.assertAlmostEqual(rec["neg_rate"], 9 / 27, places=12)

    def test_peer_fields_follow_peers(self):
        hotels, by_id = _city()
        rec = hotels[0]["aspects"]["room"]
        self.assertEqual(rec["peer_n"], 3)
        self.assertAlmostEqual(rec["gap"], rec["peer_median_net"] - rec["net"], places=12)


class ImproveHotelTests(unittest.TestCase):
    def test_flips_share_of_negatives_only_on_that_aspect(self):
        hotels, by_id = _city()
        h = hotels[0]
        after = improve_hotel(h, "room", 0.5, CFG, by_id)
        r0, r1 = h["aspects"]["room"], after["aspects"]["room"]
        self.assertEqual(r1["neg_mentions"], 6)
        self.assertEqual(r1["pos_mentions"], 16)
        self.assertEqual(r1["mention_count"], r0["mention_count"])
        self.assertEqual(r1["reliability"], r0["reliability"])
        self.assertGreater(r1["net"], r0["net"])
        self.assertLess(r1["gap"], r0["gap"])
        for a in CFG["aspects"]:
            if a != "room":
                self.assertIs(after["aspects"][a], h["aspects"][a])
        self.assertEqual(h["aspects"]["room"]["neg_mentions"], 12)  # input untouched
        self.assertEqual(after["simulated_improvements"][-1]["flipped"], 6)

    def test_zero_share_changes_nothing(self):
        hotels, by_id = _city()
        after = improve_hotel(hotels[0], "room", 0.0, CFG, by_id)
        self.assertEqual(after["aspects"]["room"]["net"], hotels[0]["aspects"]["room"]["net"])

    def test_refuses_unmeasured_and_bad_share(self):
        h = _hotel("x", {"room": (3, 4)})
        with self.assertRaises(ValueError):
            improve_hotel(h, "breakfast", 0.5, CFG)
        with self.assertRaises(ValueError):
            improve_hotel(h, "room", 1.5, CFG)
        with self.assertRaises(ValueError):
            improve_hotel(h, "room", float("nan"), CFG)


class MentionRecordTests(unittest.TestCase):
    def test_records_match_counts_and_have_no_text(self):
        hotels, _ = _city()
        h = hotels[0]
        recs = synthesize_mentions(h, CFG, seed=7)
        for a in CFG["aspects"]:
            rec = h["aspects"][a]
            if not rec.get("has_measurement"):
                continue
            pos = sum(1 for r in recs if r["aspect"] == a and r["sentiment"] == "pos")
            neg = sum(1 for r in recs if r["aspect"] == a and r["sentiment"] == "neg")
            self.assertEqual((pos, neg), (rec["pos_mentions"], rec["neg_mentions"]), msg=a)
        self.assertTrue(all(set(r) == {"review_id", "aspect", "sentiment"} for r in recs))
        self.assertTrue(all(r["review_id"].startswith("sim-") for r in recs))

    def test_records_are_deterministic(self):
        hotels, _ = _city()
        self.assertEqual(synthesize_mentions(hotels[0], CFG, 3), synthesize_mentions(hotels[0], CFG, 3))

    def test_record_path_equals_count_path(self):
        hotels, by_id = _city()
        h = hotels[0]
        recs = improve_mentions(synthesize_mentions(h, CFG, 1), "room", 0.5, seed=1)
        changed = [r for r in recs if "sentiment_before" in r]
        self.assertEqual(len(changed), 6)
        self.assertTrue(all(r["aspect"] == "room" and r["sentiment"] == "pos" for r in changed))
        via_records = aggregate_mentions(recs, h, CFG, by_id)
        via_counts = improve_hotel(h, "room", 0.5, CFG, by_id)
        for a in CFG["aspects"]:
            if not h["aspects"][a].get("has_measurement"):
                continue
            for f in ("net", "gap", "percentile", "reliability", "neg_mentions"):
                self.assertAlmostEqual(via_records["aspects"][a][f], via_counts["aspects"][a][f], places=12, msg=(a, f))


class OutcomeTests(unittest.TestCase):
    def test_outcome_is_linear_in_assumptions(self):
        hotels, by_id = _city()
        h = hotels[0]
        after = improve_hotel(h, "room", 1.0, CFG, by_id)
        o = outcome(h, after, CFG, {"rating_per_net": 2.0, "revenue_pct_per_rating": 4.0})
        self.assertAlmostEqual(o["d_balance"], overall_balance(after, CFG) - overall_balance(h, CFG), places=12)
        self.assertAlmostEqual(o["d_rating"], 2.0 * o["d_balance"], places=12)
        self.assertAlmostEqual(o["d_revenue_pct"], 4.0 * o["d_rating"], places=12)
        self.assertGreater(o["d_rating"], 0)

    def test_no_change_no_gain_and_bad_assumptions_raise(self):
        hotels, _ = _city()
        o = outcome(hotels[0], hotels[0], CFG)
        self.assertEqual(o["d_rating"], 0.0)
        with self.assertRaises(ValueError):
            outcome(hotels[0], hotels[0], CFG, {"elasticity": 1})
        with self.assertRaises(ValueError):
            outcome(hotels[0], hotels[0], CFG, {"rating_per_net": -1})


class PolicyComparisonTests(unittest.TestCase):
    def test_compare_actions_excludes_location_and_marks_recommendation(self):
        hotels, by_id = _city()
        h = hotels[0]
        rows = compare_actions(h, CFG, None, by_id)
        aspects = [r["aspect"] for r in rows]
        self.assertNotIn("location", aspects)
        self.assertEqual(sorted(aspects), sorted(candidate_aspects(h, CFG)))
        self.assertEqual([r["d_rating"] for r in rows], sorted((r["d_rating"] for r in rows), reverse=True))
        rec = explain_action_vs_diagnostic(h, CFG)["actionable_recommendation"]
        self.assertEqual([r["aspect"] for r in rows if r["recommended"]], [rec])

    def test_more_negatives_means_more_gain_under_the_assumption(self):
        hotels, by_id = _city()
        rows = {r["aspect"]: r for r in compare_actions(hotels[0], CFG, None, by_id)}
        self.assertGreater(rows["room"]["d_rating"], rows["service"]["d_rating"])

    def test_follow_recommendations_accumulates(self):
        hotels, by_id = _city()
        steps = follow_recommendations(hotels[0], CFG, 3, None, by_id)
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0]["aspect"], explain_action_vs_diagnostic(hotels[0], CFG)["actionable_recommendation"])
        gains = [s["d_rating"] for s in steps]
        self.assertEqual(gains, sorted(gains))

    def test_candidates_pass_evidence_gate(self):
        h = _hotel("x", {"room": (2, 1), "service": (10, 4), "cleanliness": (6, 3)})
        self.assertEqual(candidate_aspects(h, CFG), ["cleanliness", "service"])

    def test_follow_stops_when_nothing_left_to_convert(self):
        h = _hotel("x", {"service": (12, 0)})
        steps = follow_recommendations(h, CFG, 3)
        self.assertLessEqual(len(steps), 1)
        if steps and steps[0]["aspect"]:
            self.assertTrue(steps[0]["stalled"])
            self.assertEqual(steps[0]["d_rating"], 0.0)

    def test_city_experiment_summary(self):
        hotels, by_id = _city()
        out = city_experiment(hotels, "Paris", CFG, None, by_id)
        self.assertEqual(out["n_hotels"] + out["n_abstained"], 4)
        m = out["mean_d_rating"]
        self.assertLessEqual(m["recommended"], m["oracle"] + 1e-12)
        self.assertLessEqual(m["random"], m["oracle"] + 1e-12)
        self.assertEqual(out["revenue_pct_per_rating"], DEFAULT_ASSUMPTIONS["revenue_pct_per_rating"])
        self.assertEqual(city_experiment(hotels, "London", CFG, None, by_id)["n_hotels"], 0)


if __name__ == "__main__":
    unittest.main()

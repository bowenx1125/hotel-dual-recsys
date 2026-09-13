from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.scoring import all_policies as demo_all_policies
from demo.scoring import policy_fix_weakest as demo_policy_fix_weakest
from src.recommendation.scoring import (
    ABSTAIN_CROWDING_UNAVAILABLE,
    ABSTAIN_NO_ELIGIBLE,
    actionable_aspect_ids,
    all_policies,
    criticism_metrics,
    diagnostic_largest_gap,
    eligible_aspects,
    peer_relative_scores,
    policy_fix_weakest,
    policy_largest_peer_gap_actionable,
    policy_most_criticized,
    policy_peer_relative,
    policy_reliability_aware,
)


def _actionability() -> dict:
    return {
        "location": {"eligible_for_direct_action": False, "actionability_level": "immutable"},
        "cleanliness": {"eligible_for_direct_action": True, "actionability_level": "high"},
        "service": {"eligible_for_direct_action": True, "actionability_level": "high"},
        "noise": {"eligible_for_direct_action": True, "actionability_level": "conditional"},
    }


def _base_cfg(**overrides) -> dict:
    cfg = {
        "aspects": ["location", "cleanliness", "service", "noise"],
        "min_mentions": 5,
        "min_reliability": 0.3,
        "min_measured_peers": 2,
        "reliability_k": 10.0,
        "weights": {"gap": 0.45, "criticism": 0.35, "unreliable": 0.20},
        "scenario": {"crowding_weight": 0.5, "default_intensity": 0.0},
        "actionability": {"aspects": _actionability()},
    }
    cfg.update(overrides)
    return cfg


def _aspect(
    *,
    net=0.1,
    mention_count=10,
    gap=0.05,
    neg_mentions=2,
    neg_rate=0.2,
    peer_n=3,
    peer_weakest_share=0.1,
    reliability=None,
    has_measurement=True,
) -> dict:
    rec = {
        "net": net,
        "mention_count": mention_count,
        "gap": gap,
        "neg_mentions": neg_mentions,
        "neg_rate": neg_rate,
        "peer_n": peer_n,
        "peer_weakest_share": peer_weakest_share,
        "has_measurement": has_measurement,
    }
    if reliability is not None:
        rec["reliability"] = reliability
    return rec


def _hotel(aspects: dict, **hotel_kw) -> dict:
    return {
        "hotel_id": "h1",
        "n_reviews": 100,
        "peer_count": hotel_kw.get("peer_count", 3),
        "aspects": aspects,
    }


class TestEvidenceGates(unittest.TestCase):
    def test_location_never_actionable(self):
        cfg = _base_cfg()
        hotel = _hotel(
            {
                "location": _aspect(net=-0.9, mention_count=20, gap=0.8),
                "cleanliness": _aspect(net=0.2, mention_count=10, gap=0.01),
                "service": _aspect(net=0.1, mention_count=10, gap=0.02),
                "noise": _aspect(net=0.0, mention_count=10, gap=0.03),
            }
        )
        pol = policy_fix_weakest(hotel, cfg)
        self.assertNotEqual(pol["chosen_aspect"], "location")
        self.assertIn("location", pol["excluded_aspects"])
        self.assertEqual(pol["excluded_aspects"]["location"], "not_actionable")

    def test_location_actionable_in_config_still_excluded(self):
        cfg = _base_cfg()
        cfg["actionability"]["aspects"]["location"]["eligible_for_direct_action"] = True
        hotel = _hotel({"location": _aspect(net=-0.5, mention_count=10)})
        pol = policy_fix_weakest(hotel, cfg)
        self.assertNotEqual(pol["chosen_aspect"], "location")

    def test_location_config_cannot_make_diagnostic_actionable(self):
        cfg = _base_cfg()
        cfg["actionability"]["aspects"]["location"]["eligible_for_direct_action"] = True
        hotel = _hotel(
            {
                "location": _aspect(net=-0.9, mention_count=20, gap=0.8),
                "cleanliness": _aspect(net=0.2, mention_count=10, gap=0.01),
            }
        )
        diag = diagnostic_largest_gap(hotel, cfg)
        self.assertEqual(diag["chosen_aspect"], "location")
        self.assertFalse(diag["actionable"])

    def test_unknown_aspect_excluded(self):
        cfg = _base_cfg()
        cfg["aspects"] = ["cleanliness", "mystery"]
        hotel = _hotel({"cleanliness": _aspect(), "mystery": _aspect(net=-0.4)})
        pol = policy_fix_weakest(hotel, cfg)
        self.assertIn("mystery", pol["excluded_aspects"])
        self.assertEqual(pol["excluded_aspects"]["mystery"], "unknown_aspect")

    def test_insufficient_mentions_abstains(self):
        cfg = _base_cfg()
        hotel = _hotel(
            {
                "cleanliness": _aspect(mention_count=3),
                "service": _aspect(mention_count=4),
            }
        )
        pol = policy_fix_weakest(hotel, cfg)
        self.assertIsNone(pol["chosen_aspect"])
        self.assertEqual(pol["abstention_reason"], ABSTAIN_NO_ELIGIBLE)

    def test_invalid_reliability_fail_closed(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(reliability=float("nan"))})
        pol = policy_fix_weakest(hotel, cfg)
        self.assertIsNone(pol["chosen_aspect"])

    def test_has_measurement_false_excluded(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(has_measurement=False)})
        pol = policy_fix_weakest(hotel, cfg)
        self.assertIn("cleanliness", pol["excluded_aspects"])
        self.assertEqual(pol["excluded_aspects"]["cleanliness"], "no_measurement")

    def test_negative_mention_count_invalid(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(mention_count=-1)})
        pol = policy_fix_weakest(hotel, cfg)
        self.assertIsNone(pol["chosen_aspect"])

    def test_missing_aspect_record_skipped(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(mention_count=2)})
        pol = policy_fix_weakest(hotel, cfg)
        self.assertIsNone(pol["chosen_aspect"])
        self.assertIn("service", pol["excluded_aspects"])
        self.assertEqual(pol["excluded_aspects"]["service"], "missing_aspect_record")


class TestPeerPolicies(unittest.TestCase):
    def test_largest_gap_requires_peer_evidence(self):
        cfg = _base_cfg()
        hotel = _hotel(
            {
                "cleanliness": _aspect(gap=float("nan"), peer_n=0),
                "service": _aspect(gap=0.2, peer_n=1),
            }
        )
        pol = policy_largest_peer_gap_actionable(hotel, cfg)
        self.assertIsNone(pol["chosen_aspect"])
        self.assertIn("service", pol["excluded_aspects"])

    def test_peer_relative_invalid_neg_rate(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(neg_rate=1.5)})
        pol = policy_peer_relative(hotel, cfg, 0.0)
        self.assertIsNone(pol["chosen_aspect"])
        self.assertEqual(pol["excluded_aspects"]["cleanliness"], "invalid_neg_rate")

    def test_most_criticized_requires_valid_neg_mentions(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(neg_mentions=float("nan"))})
        pol = policy_most_criticized(hotel, cfg)
        self.assertIsNone(pol["chosen_aspect"])

    def test_scenario_missing_crowding_abstains(self):
        cfg = _base_cfg()
        hotel = _hotel(
            {
                "cleanliness": _aspect(peer_weakest_share=float("nan")),
                "service": _aspect(net=0.0, peer_weakest_share=float("nan")),
            }
        )
        pol = policy_peer_relative(hotel, cfg, 0.5)
        self.assertIsNone(pol["chosen_aspect"])
        self.assertEqual(pol["abstention_reason"], ABSTAIN_CROWDING_UNAVAILABLE)
        self.assertFalse(pol["crowding_available"])


class TestDeterminism(unittest.TestCase):
    def test_tie_break_by_aspect_name(self):
        cfg = _base_cfg()
        hotel = _hotel(
            {
                "cleanliness": _aspect(net=-0.2),
                "service": _aspect(net=-0.2),
                "noise": _aspect(net=0.5),
            }
        )
        pol = policy_fix_weakest(hotel, cfg)
        self.assertEqual(pol["chosen_aspect"], "cleanliness")

    def test_reordered_inputs_same_pick(self):
        cfg = _base_cfg()
        aspects_a = {
            "noise": _aspect(net=0.3),
            "service": _aspect(net=-0.1),
            "cleanliness": _aspect(net=-0.2),
        }
        aspects_b = {
            "cleanliness": _aspect(net=-0.2),
            "noise": _aspect(net=0.3),
            "service": _aspect(net=-0.1),
        }
        pick_a = policy_fix_weakest(_hotel(aspects_a), cfg)["chosen_aspect"]
        pick_b = policy_fix_weakest(_hotel(aspects_b), cfg)["chosen_aspect"]
        self.assertEqual(pick_a, pick_b)

    def test_inputs_not_mutated(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(), "service": _aspect(net=0.0)})
        before = copy.deepcopy(hotel)
        policy_fix_weakest(hotel, cfg)
        peer_relative_scores(hotel, cfg, 0.0)
        self.assertEqual(hotel, before)


class TestScoringOutputs(unittest.TestCase):
    def test_valid_hotel_returns_evidence(self):
        cfg = _base_cfg()
        hotel = _hotel(
            {
                "cleanliness": _aspect(net=-0.3, gap=0.4, neg_mentions=5),
                "service": _aspect(net=0.1, gap=0.1, neg_mentions=1),
                "noise": _aspect(net=0.2, gap=0.05, neg_mentions=0),
            }
        )
        pol = policy_fix_weakest(hotel, cfg)
        self.assertEqual(pol["chosen_aspect"], "cleanliness")
        self.assertIsNotNone(pol["evidence"])
        self.assertIn("reliability", pol["evidence"])
        self.assertIn("actionability", pol["evidence"])

    def test_reliability_aware_comparator(self):
        cfg = _base_cfg()
        hotel = _hotel(
            {
                "cleanliness": _aspect(net=-0.1, reliability=0.9),
                "service": _aspect(net=-0.5, reliability=0.35),
            }
        )
        pol = policy_reliability_aware(hotel, cfg)
        self.assertEqual(pol["chosen_aspect"], "service")

    def test_hotel_explicit_ineligible_all_policies_abstain(self):
        cfg = _base_cfg()
        hotel = _hotel(
            {
                "cleanliness": _aspect(),
                "service": _aspect(net=0.0),
                "noise": _aspect(net=0.1),
            }
        )
        hotel["eligible"] = False
        pol = all_policies(hotel, cfg, 0.0)
        for key, result in pol.items():
            self.assertIsNone(result["chosen_aspect"], msg=key)
            for aspect, reason in result["excluded_aspects"].items():
                self.assertEqual(reason, "hotel_ineligible", msg=f"{key}:{aspect}")

    def test_all_policies_keys(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(), "service": _aspect(net=0.0)})
        pol = all_policies(hotel, cfg, 0.0)
        for key in (
            "fix_weakest",
            "largest_peer_gap",
            "most_criticized",
            "peer_relative",
            "competition_aware",
            "reliability_aware",
        ):
            self.assertIn(key, pol)
        self.assertEqual(
            pol["competition_aware"]["chosen_aspect"],
            pol["peer_relative"]["chosen_aspect"],
        )

    def test_rationale_fields(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(), "service": _aspect(net=0.0)})
        default_pol = policy_peer_relative(hotel, cfg, 0.0)
        scenario_pol = policy_peer_relative(hotel, cfg, 0.3)
        self.assertEqual(default_pol["mode"], "default")
        self.assertIn("rationale_default", default_pol)
        self.assertEqual(scenario_pol["mode"], "scenario")
        self.assertIn("rationale_scenario", scenario_pol)

    def test_finite_scores_default_mode(self):
        cfg = _base_cfg()
        hotel = _hotel(
            {
                "cleanliness": _aspect(),
                "service": _aspect(net=0.0),
                "noise": _aspect(net=0.1),
            }
        )
        scores = peer_relative_scores(hotel, cfg, 0.0)
        self.assertTrue(scores)
        for val in scores.values():
            self.assertTrue(val == val and abs(val) != float("inf"))


class TestAuditHardening(unittest.TestCase):
    def test_reliability_explicit_none_invalid(self):
        cfg = _base_cfg()
        rec = _aspect()
        rec["reliability"] = None
        hotel = _hotel({"cleanliness": rec})
        pol = policy_fix_weakest(hotel, cfg)
        self.assertIsNone(pol["chosen_aspect"])
        self.assertEqual(pol["excluded_aspects"]["cleanliness"], "insufficient_reliability")

    def test_reliability_above_one_invalid(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(reliability=1.5)})
        pol = policy_fix_weakest(hotel, cfg)
        self.assertIsNone(pol["chosen_aspect"])

    def test_bool_mention_count_invalid(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(mention_count=True)})
        pol = policy_fix_weakest(hotel, cfg)
        self.assertIsNone(pol["chosen_aspect"])

    def test_fractional_mention_count_invalid(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(mention_count=10.5)})
        pol = policy_fix_weakest(hotel, cfg)
        self.assertIsNone(pol["chosen_aspect"])

    def test_neg_exceeds_mentions_invalidates_fix_weakest(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(neg_mentions=12, mention_count=10)})
        pol = policy_fix_weakest(hotel, cfg)
        self.assertIsNone(pol["chosen_aspect"])
        self.assertEqual(pol["excluded_aspects"]["cleanliness"], "invalid_counts")

    def test_has_measurement_zero_blocks(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(has_measurement=0)})
        pol = policy_fix_weakest(hotel, cfg)
        self.assertEqual(pol["excluded_aspects"]["cleanliness"], "no_measurement")

    def test_has_measurement_string_false_blocks(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(has_measurement="false")})
        pol = policy_fix_weakest(hotel, cfg)
        self.assertEqual(pol["excluded_aspects"]["cleanliness"], "no_measurement")

    def test_peer_n_explicit_none_no_hotel_fallback(self):
        cfg = _base_cfg()
        rec = _aspect()
        rec["peer_n"] = None
        hotel = _hotel({"cleanliness": rec}, peer_count=5)
        pol = policy_largest_peer_gap_actionable(hotel, cfg)
        self.assertIn("cleanliness", pol["excluded_aspects"])

    def test_peer_n_absent_uses_peer_count(self):
        cfg = _base_cfg()
        rec = _aspect()
        rec.pop("peer_n", None)
        hotel = _hotel({"cleanliness": rec}, peer_count=3)
        pol = policy_largest_peer_gap_actionable(hotel, cfg)
        self.assertEqual(pol["chosen_aspect"], "cleanliness")

    def test_actionable_aspect_ids_excludes_unknown_and_location(self):
        act = _actionability()
        act["mystery"] = {"eligible_for_direct_action": True, "actionability_level": "high"}
        act["location"]["eligible_for_direct_action"] = True
        ids = actionable_aspect_ids(act)
        self.assertNotIn("location", ids)
        self.assertNotIn("mystery", ids)
        self.assertIn("cleanliness", ids)

    def test_scenario_low_mentions_not_crowding_abstain(self):
        cfg = _base_cfg()
        hotel = _hotel(
            {
                "cleanliness": _aspect(mention_count=2, peer_weakest_share=0.2),
                "service": _aspect(mention_count=1, peer_weakest_share=0.1),
            }
        )
        pol = policy_peer_relative(hotel, cfg, 0.8)
        self.assertIsNone(pol["chosen_aspect"])
        self.assertEqual(pol["abstention_reason"], ABSTAIN_NO_ELIGIBLE)

    def test_malformed_cfg_raises(self):
        cfg = _base_cfg(min_mentions=-1)
        hotel = _hotel({"cleanliness": _aspect()})
        with self.assertRaises(ValueError):
            policy_fix_weakest(hotel, cfg)

    def test_malformed_reliability_k_raises(self):
        cfg = _base_cfg(reliability_k=0)
        hotel = _hotel({"cleanliness": _aspect()})
        with self.assertRaises(ValueError):
            policy_fix_weakest(hotel, cfg)

    def test_malformed_weights_raise(self):
        cfg = _base_cfg(weights={"gap": -1, "criticism": 0.35, "unreliable": 0.20})
        hotel = _hotel({"cleanliness": _aspect(), "service": _aspect(net=0.0)})
        with self.assertRaises(ValueError):
            peer_relative_scores(hotel, cfg, 0.0)

    def test_nonfinite_intensity_raises(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect()})
        with self.assertRaises(ValueError):
            policy_peer_relative(hotel, cfg, float("nan"))

    def test_criticism_metrics_missing_neg_is_none(self):
        rec = _aspect()
        rec.pop("neg_mentions", None)
        hotel = _hotel({"cleanliness": rec})
        m = criticism_metrics(hotel, "cleanliness")
        self.assertIsNone(m["neg_mentions"])
        self.assertIsNone(m["neg_per_review"])

    def test_criticism_metrics_invalid_neg_is_none(self):
        hotel = _hotel({"cleanliness": _aspect(neg_mentions=float("nan"))})
        m = criticism_metrics(hotel, "cleanliness")
        self.assertIsNone(m["neg_mentions"])
        self.assertIsNone(m["neg_per_review"])


class TestCompatibilityImports(unittest.TestCase):
    def test_demo_reexport_matches_src(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(net=-0.2), "service": _aspect(net=0.0)})
        demo_pick = demo_policy_fix_weakest(hotel, cfg)["chosen_aspect"]
        src_pick = policy_fix_weakest(hotel, cfg)["chosen_aspect"]
        self.assertEqual(demo_pick, src_pick)

    def test_demo_all_policies_has_alias(self):
        cfg = _base_cfg()
        hotel = _hotel({"cleanliness": _aspect(), "service": _aspect(net=0.0)})
        pol = demo_all_policies(hotel, cfg, 0.0)
        self.assertIn("competition_aware", pol)
        self.assertIn("peer_relative", pol)


if __name__ == "__main__":
    unittest.main(verbosity=2)

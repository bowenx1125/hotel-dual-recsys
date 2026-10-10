"""P3 tests: the value vector, and the value-aware policy as a strict superset
of the shipped peer_relative rule (same gates, different ranking)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys  # noqa: E402

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.effect import learn_value  # noqa: E402
from src.effect.run_p3 import (  # noqa: E402
    extract_units, picks_from_units, single_aspect_test,
)
from src.recommendation import scoring  # noqa: E402
from src.recommendation.value_policy import (  # noqa: E402
    ACTIONABLE, load_value_vector, normalize_value, policy_value_aware,
    value_aware_scores,
)


def load_cfg() -> dict:
    cfg = json.loads((ROOT / "conf" / "demo.json").read_text(encoding="utf-8"))
    cfg["actionability"] = json.loads(
        (ROOT / "conf" / "actionability.json").read_text(encoding="utf-8")
    )["aspects"]
    return cfg


def make_hotel(hid: str = "h1", *, nets=None, gaps=None, neg_rates=None,
               mentions=12, rel=0.6) -> dict:
    nets = nets or {a: 0.2 for a in scoring.ASPECTS_DEFAULT}
    gaps = gaps or {a: 0.1 for a in scoring.ASPECTS_DEFAULT}
    neg_rates = neg_rates or {a: 0.2 for a in scoring.ASPECTS_DEFAULT}
    aspects = {}
    for a in scoring.ASPECTS_DEFAULT:
        n = int(mentions)
        aspects[a] = {
            "net": float(nets.get(a, 0.2)),
            "mention_count": n,
            "pos_mentions": int(round(n * (1 - neg_rates.get(a, 0.2)))),
            "neg_mentions": int(round(n * neg_rates.get(a, 0.2))),
            "neg_rate": float(neg_rates.get(a, 0.2)),
            "has_measurement": True,
            "reliability": rel,
            "peer_median_net": float(nets.get(a, 0.2)) + float(gaps.get(a, 0.1)),
            "peer_n": 4,
            "gap": float(gaps.get(a, 0.1)),
            "percentile": 50.0,
            "peer_weakest_share": 0.25,
            "mention_rate": 0.4,
        }
    return {
        "hotel_id": hid,
        "hotel_name": "H",
        "city": "C",
        "n_reviews": 60,
        "peer_count": 4,
        "peer_ids": ["p1", "p2", "p3", "p4"],
        "eligible": True,
        "aspects": aspects,
    }


class NormalizeValueTests(unittest.TestCase):
    def test_mean_one_over_actionable(self):
        v = {a: float(i + 1) for i, a in enumerate(ACTIONABLE)}
        nv = normalize_value(v, ACTIONABLE)
        self.assertAlmostEqual(float(np.mean([nv[a] for a in ACTIONABLE])), 1.0, places=9)

    def test_location_ignored(self):
        v = {a: 1.0 for a in ACTIONABLE}
        v["location"] = 99.0
        nv = normalize_value(v, ACTIONABLE)
        self.assertNotIn("location", nv)
        self.assertAlmostEqual(nv["service"], 1.0, places=9)

    def test_negative_clamped(self):
        v = {a: 1.0 for a in ACTIONABLE}
        v["noise"] = -5.0
        nv = normalize_value(v, ACTIONABLE, clamp_nonneg=True)
        self.assertEqual(nv["noise"], 0.0)
        self.assertTrue(all(x >= 0 for x in nv.values()))

    def test_degenerate_all_zero_falls_back_to_ones(self):
        nv = normalize_value({a: 0.0 for a in ACTIONABLE}, ACTIONABLE)
        self.assertTrue(all(abs(x - 1.0) < 1e-12 for x in nv.values()))

    def test_pure_reranking_scale_invariant(self):
        v = {a: float(i + 1) for i, a in enumerate(ACTIONABLE)}
        a1 = normalize_value(v, ACTIONABLE)
        a2 = normalize_value({k: 7.0 * x for k, x in v.items()}, ACTIONABLE)
        for k in ACTIONABLE:
            self.assertAlmostEqual(a1[k], a2[k], places=9)


class PolicyParityTests(unittest.TestCase):
    """value_aware with v == 1 must be bit-identical to the shipped rule."""

    def setUp(self):
        self.cfg = load_cfg()
        self.hotel = make_hotel()

    def test_scores_match_peer_relative_when_value_is_unity(self):
        base = scoring.peer_relative_scores(self.hotel, self.cfg, 0.0,
                                            actionable_only=True)
        got = value_aware_scores(self.hotel, self.cfg, None, 0.0,
                                 actionable_only=True)
        self.assertEqual(set(base), set(got))
        for a in base:
            self.assertAlmostEqual(base[a], got[a], places=12)

    def test_extract_units_reproduces_shipped_pick(self):
        snap = {"period": "2017Q2", "hotels": [self.hotel]}
        units = extract_units(snap, self.cfg)
        self.assertFalse(units.empty)
        pick = picks_from_units(units, None)["pick"].iloc[0]
        shipped = scoring.policy_peer_relative(self.hotel, self.cfg)["chosen_aspect"]
        self.assertEqual(pick, shipped)

    def test_eligibility_identical_to_peer_relative(self):
        base = scoring.peer_relative_scores(self.hotel, self.cfg, 0.0,
                                            actionable_only=True)
        got = value_aware_scores(self.hotel, self.cfg, {"service": 5.0}, 0.0,
                                 actionable_only=True)
        self.assertEqual(set(base), set(got),
                         "value weighting must not change the eligible set")

    def test_value_can_flip_the_ranking(self):
        # breakfast has the largest deficit; give it a tiny value -> service wins
        net = {a: 0.2 for a in scoring.ASPECTS_DEFAULT}
        gap = {a: 0.05 for a in scoring.ASPECTS_DEFAULT}
        gap["breakfast"] = 0.9
        gap["service"] = 0.8
        h = make_hotel(gaps=gap, nets=net)
        base = scoring.policy_peer_relative(h, self.cfg)["chosen_aspect"]
        self.assertEqual(base, "breakfast")
        v = {a: 1.0 for a in ACTIONABLE}
        v["breakfast"] = 0.01
        got = policy_value_aware(h, self.cfg, v)["chosen_aspect"]
        self.assertEqual(got, "service")

    def test_location_never_chosen(self):
        for v in (None, {a: 1.0 for a in ACTIONABLE},
                  {"location": 100.0, **{a: 0.001 for a in ACTIONABLE}}):
            res = policy_value_aware(self.hotel, self.cfg, v)
            self.assertNotEqual(res["chosen_aspect"], "location")

    def test_abstention_matches_peer_relative(self):
        poor = make_hotel(mentions=1, rel=0.05)
        base = scoring.policy_peer_relative(poor, self.cfg)
        got = policy_value_aware(poor, self.cfg, {a: 2.0 for a in ACTIONABLE})
        self.assertEqual(base["chosen_aspect"], got["chosen_aspect"])
        self.assertEqual(base["abstention_reason"], got["abstention_reason"])

    def test_reports_weights_are_not_design_choices(self):
        res = policy_value_aware(self.hotel, self.cfg, {a: 1.0 for a in ACTIONABLE})
        self.assertFalse(res["weights_are_design_choices"])


class OptInWiringTests(unittest.TestCase):
    """P3 must be plug-in only: off by default, byte-identical when off."""

    def setUp(self):
        self.cfg = load_cfg()
        self.hotel = make_hotel()

    def test_default_config_does_not_opt_in(self):
        self.assertFalse(self.cfg.get("use_learned_value_vector"))
        self.assertIsNone(load_value_vector(self.cfg))

    def test_all_policies_unchanged_when_off(self):
        keys = set(scoring.all_policies(self.hotel, self.cfg))
        self.assertEqual(keys, {"fix_weakest", "largest_peer_gap", "most_criticized",
                                "peer_relative", "competition_aware",
                                "reliability_aware"})
        self.assertNotIn("value_aware", keys)

    def test_missing_artifact_file_is_inert(self):
        cfg = dict(self.cfg)
        cfg["use_learned_value_vector"] = True
        cfg["value_vector_path"] = "outputs/autonomous/p3/__does_not_exist__.json"
        self.assertIsNone(load_value_vector(cfg))
        self.assertNotIn("value_aware", scoring.all_policies(self.hotel, cfg))

    def test_enabled_adds_value_aware_with_same_gates(self):
        import tempfile
        vec = {a: float(i + 1) for i, a in enumerate(scoring.ASPECTS_DEFAULT)}
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "vv.json"
            p.write_text(json.dumps({"vectors": {"conditional": vec}}), encoding="utf-8")
            cfg = dict(self.cfg)
            cfg["use_learned_value_vector"] = True
            cfg["value_vector_path"] = str(p)
            cfg["value_spec"] = "conditional"
            res = scoring.all_policies(self.hotel, cfg)
            self.assertIn("value_aware", res)
            base = res["peer_relative"]
            self.assertEqual(base["excluded_aspects"], res["value_aware"]["excluded_aspects"])
            self.assertNotEqual(res["value_aware"]["chosen_aspect"], "location")


class RidgeRecoveryTests(unittest.TestCase):
    def test_recovers_known_coefficients(self):
        rng = np.random.default_rng(7)
        n, k = 20000, 7
        X = rng.normal(size=(n, k))
        true = np.array([0.5, -0.2, 0.9, 0.0, 0.3, -0.4, 0.1])
        y = X @ true + 3.0 + rng.normal(scale=0.05, size=n)
        fit = learn_value.fit_ridge(X, y, alpha=1e-6)
        np.testing.assert_allclose(fit.coef_psd, true, atol=0.05)
        self.assertAlmostEqual(fit.intercept, 3.0, delta=0.05)

    def test_raw_and_per_sd_coefficients_relate_by_scale(self):
        rng = np.random.default_rng(11)
        X = rng.normal(size=(400, 7)) * np.array([1.0, 2.0, 0.5, 1.0, 3.0, 1.0, 2.0])
        y = X @ np.arange(1, 8) * 0.1
        fit = learn_value.fit_ridge(X, y, alpha=1.0)
        np.testing.assert_allclose(fit.coef_raw(), fit.coef_psd / fit.sd, rtol=1e-9)

    def test_predict_handles_nan_via_median(self):
        rng = np.random.default_rng(3)
        X = rng.normal(size=(300, 7))
        y = X @ np.ones(7)
        fit = learn_value.fit_ridge(X, y, alpha=1.0)
        Xn = X.copy()
        Xn[0, 0] = np.nan
        p = fit.predict(Xn)
        self.assertTrue(np.isfinite(p).all())

    def test_r2_of_its_own_fit_is_high(self):
        rng = np.random.default_rng(5)
        X = rng.normal(size=(500, 7))
        y = X @ np.array([1, 0, 0, 0, 0, 0, 0.0])
        fit = learn_value.fit_ridge(X, y, alpha=1e-6)
        self.assertGreater(learn_value.r2(y, fit.predict(X)), 0.99)

    def test_placebo_destroys_signal(self):
        rng = np.random.default_rng(9)
        X = rng.normal(size=(300, 7))
        y = X @ np.array([1, 1, 1, 0, 0, 0, 0.0])
        ys = y[rng.permutation(len(y))]
        fit = learn_value.fit_ridge(X, ys, alpha=1.0)
        self.assertLess(learn_value.r2(ys, fit.predict(X)), 0.05)


class SingleAspectProbeTests(unittest.TestCase):
    """Q3b: the outcome probe must be able to tell a real vector from a
    scrambled one. Without the scrambled-v placebo this test cannot exist --
    comparing against random-aspect picking alone is not apples-to-apples."""

    @staticmethod
    def _table(n=600, seed=0):
        rng = np.random.default_rng(seed)
        A = list(learn_value.ASPECTS)
        X = rng.normal(size=(n, len(A)))
        d = pd.DataFrame(X, columns=A)
        d["hotel_id"] = [f"h{i}" for i in range(n)]
        # only `room` carries signal
        d["y"] = 2.0 * d["room"] + rng.normal(scale=0.5, size=n)
        return d

    def test_reports_both_baselines_and_flags(self):
        r = single_aspect_test(self._table(), seed=1, reps=4, spec="conditional")
        self.assertIn("placebo_permuted_v", r["policies"])
        self.assertIn("random_uniform", r["policies"])
        self.assertIn("value_aware", r["policies"])
        self.assertIsInstance(r["beats_placebo"], bool)
        self.assertIsInstance(r["beats_random_uniform"], bool)
        self.assertIn("value_aware - placebo_permuted_v", r["contrasts"])

    def test_real_vector_beats_scrambled_on_synthetic_signal(self):
        d = self._table()
        r = single_aspect_test(d, seed=3, reps=8, spec="conditional")
        self.assertTrue(
            r["beats_placebo"],
            f"value_aware {r['policies']['value_aware']['mean_r2']:+.4f} should "
            f"beat scrambled {r['policies']['placebo_permuted_v']['mean_r2']:+.4f}")
        self.assertGreater(r["policies"]["value_aware"]["mean_r2"],
                           r["policies"]["placebo_permuted_v"]["mean_r2"])

    def test_no_signal_gives_no_edge_over_scrambled(self):
        """If y is pure noise, the vector cannot beat a scrambled vector."""
        rng = np.random.default_rng(5)
        A = list(learn_value.ASPECTS)
        d = pd.DataFrame(rng.normal(size=(400, len(A))), columns=A)
        d["hotel_id"] = [f"h{i}" for i in range(400)]
        d["y"] = rng.normal(size=400)
        r = single_aspect_test(d, seed=7, reps=8, spec="conditional")
        self.assertLess(r["policies"]["value_aware"]["mean_r2"], 0.05)
        self.assertLess(abs(r["contrasts"]["value_aware - placebo_permuted_v"]
                            ["diff"]), 0.05)


if __name__ == "__main__":
    unittest.main()

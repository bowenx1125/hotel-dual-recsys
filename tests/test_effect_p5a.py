"""Tests for P5-A (revealed interventions).

The point of these tests is not coverage, it is falsifiability: if the event
study cannot recover an effect that was injected on purpose, the null result
it reports on the real panel means nothing.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.effect import interventions as iv  # noqa: E402
from src.effect.ope import ASPECTS  # noqa: E402


def _synth(tmpdir: str, n_hotels: int = 400, n_periods: int = 8,
           seed: int = 0, effect: float = 0.0, effect_aspect: str = "service",
           jump: float = 0.6, persist: float = 0.6,
           dnet_self_boost: float = 0.0, net_noise: float = 0.05,
           score_noise: float = 0.30,
           spread_aspects: bool = False) -> tuple[Path, Path]:
    """Write a synthetic (panel, fold) pair with a known injected effect.

    Half the hotels get a persistent shift on one aspect at a random interior
    quarter; `effect` is added to the OUT-fold score at t+1, which is exactly
    what `dY = Y[t+1] - Y[t-1]` should pick up.

    The shift is applied from t0 onwards, so it never snaps back -- a shift
    that reverts would manufacture a spurious event of the opposite sign one
    quarter later.

    With `spread_aspects` the event aspect cycles through all seven aspects
    and only `effect_aspect` carries the rating effect, so a best-minus-worst
    gap is well defined (a single-aspect design makes the gap degenerate).
    """
    rng = np.random.default_rng(seed)
    periods = [f"{2015 + (i // 4)}Q{(i % 4) + 1}" for i in range(n_periods)]
    hotels = [f"h{i:04d}" for i in range(n_hotels)]
    na = len(ASPECTS)

    netA = rng.normal(0.0, net_noise, size=(n_hotels, na, n_periods))
    netB = rng.normal(0.0, net_noise, size=(n_hotels, na, n_periods))
    scoreB = 7.0 + rng.normal(0.0, score_noise, size=(n_hotels, n_periods))
    scoreA = scoreB + rng.normal(0.0, score_noise, size=(n_hotels, n_periods))

    treated = set()
    for h in range(n_hotels):
        if h % 2:
            continue
        ev_aspect = ASPECTS[h % len(ASPECTS)] if spread_aspects else effect_aspect
        ai = ASPECTS.index(ev_aspect)
        t0 = int(rng.integers(1, n_periods - 1))
        pre = netA[h, ai, t0 - 1]
        netA[h, ai, t0] = pre + jump
        netA[h, ai, t0 + 1:] = pre + persist      # permanent, never snaps back
        netB[h, ai, t0 + 1] += dnet_self_boost
        if ev_aspect == effect_aspect:
            scoreB[h, t0 + 1] += effect
        treated.add((hotels[h], t0))

    prows = []
    for hi, h in enumerate(hotels):
        for ti, per in enumerate(periods):
            for ai2, a in enumerate(ASPECTS):
                prows.append({
                    "hotel_id": h, "period": per, "aspect": a, "city": "Testville",
                    "smoothed_net_A": float(netA[hi, ai2, ti]),
                    "smoothed_net_B": float(netB[hi, ai2, ti]),
                    "measurement_reliability": 0.9,
                    "has_measurement": True, "period_complete": True,
                })
    frows = []
    for hi, h in enumerate(hotels):
        for ti, per in enumerate(periods):
            frows.append({"hotel_id": h, "period": per,
                          "mean_score_A": float(scoreA[hi, ti]),
                          "mean_score_B": float(scoreB[hi, ti])})
    ppath = Path(tmpdir) / "panel.parquet"
    fpath = Path(tmpdir) / "fold.parquet"
    pd.DataFrame(prows).to_parquet(ppath, index=False)
    pd.DataFrame(frows).to_parquet(fpath, index=False)
    return ppath, fpath


class EventRuleTests(unittest.TestCase):
    def test_detection_and_outcome_folds_must_differ(self):
        with self.assertRaises(ValueError):
            iv.build_cells("A", "A")

    def test_a_spike_that_reverts_is_not_an_event(self):
        with tempfile.TemporaryDirectory() as td:
            p, f = _synth(td, n_hotels=60, n_periods=6, jump=0.6, persist=0.0)
            cells = iv.build_cells("A", "B", panel_path=p, fold_path=f)
            ev = iv.detect_events(cells, tau=0.25)
            self.assertEqual(len(ev), 0,
                             "a one-quarter spike must not count as an intervention")

    def test_deterioration_is_the_mirror(self):
        with tempfile.TemporaryDirectory() as td:
            p, f = _synth(td, n_hotels=60, n_periods=6, jump=-0.6, persist=-0.6)
            cells = iv.build_cells("A", "B", panel_path=p, fold_path=f)
            self.assertEqual(len(iv.detect_events(cells, tau=0.25)), 0)
            self.assertGreater(len(iv.detect_events(cells, tau=0.25, sign=-1)), 0)

    def test_low_reliability_events_are_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            p, f = _synth(td, n_hotels=60, n_periods=6)
            cells = iv.build_cells("A", "B", panel_path=p, fold_path=f)
            self.assertGreater(len(iv.detect_events(cells, tau=0.25, min_rel=0.9)), 0)
            self.assertEqual(
                len(iv.detect_events(cells, tau=0.25,
                                     min_rel=float(cells["measurement_reliability"].max()) + 1)),
                0)


class RecoveryTests(unittest.TestCase):
    def test_recovers_an_injected_aspect_specific_effect(self):
        delta = 0.50
        with tempfile.TemporaryDirectory() as td:
            # events spread across all seven aspects, effect only on service,
            # so the best-minus-worst gap is well defined
            p, f = _synth(td, n_hotels=700, effect=delta,
                          effect_aspect="service", spread_aspects=True)
            cells = iv.build_cells("A", "B", panel_path=p, fold_path=f)
            hpt = iv.hotel_period_table(cells)
            ev = iv.detect_events(cells, tau=0.25)
            r = iv.estimate(hpt, ev, reps=120, seed=3, min_n=20)
        self.assertNotIn("error", r)
        got = r["att_by_aspect"]["service"]["att"]
        self.assertLess(abs(got - delta), 0.15,
                        f"injected {delta}, recovered {got}")
        self.assertEqual(r["best_aspect"], "service")
        pg = r["placebo_gap"]
        self.assertGreater(pg["ratio_observed_over_placebo"], 1.5,
                           "a real aspect-specific effect must clear the placebo")
        self.assertLess(pg["p_value"], 0.05)

    def test_recovers_zero_when_there_is_no_effect(self):
        with tempfile.TemporaryDirectory() as td:
            p, f = _synth(td, n_hotels=700, effect=0.0, seed=11, spread_aspects=True)
            cells = iv.build_cells("A", "B", panel_path=p, fold_path=f)
            hpt = iv.hotel_period_table(cells)
            ev = iv.detect_events(cells, tau=0.25)
            r = iv.estimate(hpt, ev, reps=120, seed=3, min_n=20)
        self.assertNotIn("error", r)
        worst = max(abs(v["att"]) for v in r["att_by_aspect"].values())
        self.assertLess(worst, 0.15, f"null data produced ATT {worst}")
        self.assertGreater(r["placebo_gap"]["p_value"], 0.01)

    def test_pooled_effect_tracks_the_injected_one(self):
        delta = 0.40
        with tempfile.TemporaryDirectory() as td:
            p, f = _synth(td, effect=delta)
            cells = iv.build_cells("A", "B", panel_path=p, fold_path=f)
            hpt = iv.hotel_period_table(cells)
            r = iv.estimate(hpt, iv.detect_events(cells, tau=0.25),
                            reps=120, seed=3, min_n=20)
        # every event carries the effect (spread_aspects off), so the pooled
        # ATT over event cells recovers the full delta
        self.assertLess(abs(r["pooled"]["att"] - delta), 0.12,
                        f"injected {delta}, pooled recovered {r['pooled']['att']}")

    def test_pre_trend_is_zero_when_there_is_no_anticipation(self):
        with tempfile.TemporaryDirectory() as td:
            p, f = _synth(td, effect=0.5)
            cells = iv.build_cells("A", "B", panel_path=p, fold_path=f)
            hpt = iv.hotel_period_table(cells)
            r = iv.estimate(hpt, iv.detect_events(cells, tau=0.25),
                            reps=120, seed=3, min_n=20)
        self.assertIsNotNone(r["pre_trend"]["t"])
        self.assertLess(abs(r["pre_trend"]["t"]), 3.0,
                        "treated units were not rising beforehand")


class SpecificityTests(unittest.TestCase):
    def test_detects_aspect_specific_movement(self):
        with tempfile.TemporaryDirectory() as td:
            p, f = _synth(td, dnet_self_boost=0.5)
            cells = iv.build_cells("A", "B", panel_path=p, fold_path=f)
            sp = iv.specificity(cells, iv.detect_events(cells, tau=0.25))
        self.assertGreater(sp["t"], 3.0)
        self.assertGreater(sp["share_positive"], 0.8)

    def test_flat_when_every_aspect_moves_together(self):
        with tempfile.TemporaryDirectory() as td:
            p, f = _synth(td, dnet_self_boost=0.0, net_noise=0.05)
            cells = iv.build_cells("A", "B", panel_path=p, fold_path=f)
            sp = iv.specificity(cells, iv.detect_events(cells, tau=0.25))
        self.assertLess(abs(sp["t"]), 3.0)


class PowerTests(unittest.TestCase):
    def test_mde_falls_with_sample_size(self):
        a = iv.mde(1.0, 100, 5000)
        b = iv.mde(1.0, 1000, 5000)
        self.assertGreater(a, b)

    def test_required_n_falls_with_effect_size(self):
        self.assertGreater(iv.required_n_per_arm(0.05, 1.0),
                           iv.required_n_per_arm(0.20, 1.0))

    def test_required_n_rejects_nonpositive_delta(self):
        self.assertEqual(iv.required_n_per_arm(0.0, 1.0), -1)

    def test_power_table_marks_large_effects_detectable(self):
        tbl = iv.power_table(1.0, 500, 5000)
        flags = {t["target_effect_rating_points"]: t["detectable_now"] for t in tbl}
        self.assertTrue(flags[0.50])
        self.assertFalse(flags[0.02])


if __name__ == "__main__":
    unittest.main()

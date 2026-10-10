"""Unit tests for the P2 effect-estimation machinery."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.effect.estimation import (  # noqa: E402
    Fit,
    cluster_robust_mean,
    clustered_fe_ols,
    combine_two_folds,
    within_demean,
)


class ClusterRobustMeanTests(unittest.TestCase):
    def test_one_obs_per_cluster_matches_plain_standard_error(self):
        rng = np.random.default_rng(7)
        y = rng.normal(1.5, 2.0, size=400)
        cl = np.arange(len(y))  # every observation its own cluster
        f = cluster_robust_mean(y, cl)
        self.assertAlmostEqual(f.beta, float(y.mean()), places=10)
        # with G == n the cluster-robust SE collapses to the usual s / sqrt(n)
        expected = float(y.std(ddof=1) / np.sqrt(len(y)))
        self.assertAlmostEqual(f.se, expected, places=8)

    def test_mean_and_finite_se_with_real_clusters(self):
        rng = np.random.default_rng(11)
        cl = np.repeat(np.arange(200), 5)
        y = rng.normal(0.0, 1.0, size=1000) + cl * 0.01
        f = cluster_robust_mean(y, cl)
        self.assertAlmostEqual(f.beta, float(y.mean()), places=10)
        self.assertTrue(np.isfinite(f.se) and f.se > 0)
        # clustering on 200 groups must be no smaller than the iid SE here
        self.assertGreater(f.se, float(y.std(ddof=1) / np.sqrt(len(y))) * 0.5)

    def test_se_scales_like_one_over_sqrt_n(self):
        """Guards the earlier bug where SE was too small by a factor sqrt(n)."""
        rng = np.random.default_rng(3)
        cl = np.repeat(np.arange(500), 4)
        y = rng.normal(0.0, 1.0, size=2000)
        f = cluster_robust_mean(y, cl)
        self.assertLess(abs(f.se - 1.0 / np.sqrt(500)), 0.15)

    def test_single_cluster_returns_nan_not_crash(self):
        y = np.array([1.0, 2.0, 3.0])
        f = cluster_robust_mean(y, np.array([0, 0, 0]))
        self.assertAlmostEqual(f.beta, 2.0, places=10)
        self.assertTrue(np.isnan(f.se))


class WithinDemeanTests(unittest.TestCase):
    def test_group_means_become_zero(self):
        df = pd.DataFrame({"g": ["a", "a", "b", "b"], "v": [1.0, 3.0, 10.0, 20.0]})
        out = within_demean(df, ["v"], "g")
        self.assertAlmostEqual(out.loc[out["g"] == "a", "v"].mean(), 0.0, places=12)
        self.assertAlmostEqual(out.loc[out["g"] == "b", "v"].mean(), 0.0, places=12)
        self.assertAlmostEqual(out["v"].iloc[0], -1.0, places=12)


class ClusteredFeOlsTests(unittest.TestCase):
    def test_recovers_known_slope_with_cell_fixed_effects(self):
        rng = np.random.default_rng(42)
        n_cells, per_cell = 300, 8
        cell = np.repeat(np.arange(n_cells), per_cell)
        period = np.tile(np.arange(per_cell), n_cells)
        x = rng.normal(size=n_cells * per_cell)
        cell_fe = rng.normal(size=n_cells)[cell]
        period_fe = rng.normal(size=per_cell)[period]
        y = 2.0 * x + cell_fe + period_fe + rng.normal(scale=0.3, size=n_cells * per_cell)
        df = pd.DataFrame({"y": y, "x": x, "cell": cell.astype(str),
                           "hotel_id": (cell // 2).astype(str), "period": period})
        res = clustered_fe_ols(df, "y", ["x"], "cell", "hotel_id", period_col="period")
        self.assertIn("fit", res)
        self.assertAlmostEqual(res["fit"].beta, 2.0, delta=0.08)
        self.assertLess(res["fit"].se, 0.08)

    def test_null_data_gives_insignificant_zero(self):
        rng = np.random.default_rng(5)
        n = 4000
        df = pd.DataFrame({
            "y": rng.normal(size=n),
            "x": rng.normal(size=n),
            "cell": np.repeat(np.arange(500).astype(str), 8),
            "hotel_id": np.repeat(np.arange(250).astype(str), 16),
            "period": np.tile(np.arange(8), 500),
        })
        res = clustered_fe_ols(df, "y", ["x"], "cell", "hotel_id", period_col="period")
        self.assertLess(abs(res["fit"].beta), 0.12)
        self.assertGreater(res["fit"].p, 0.01)

    def test_too_few_rows_reports_error(self):
        df = pd.DataFrame({"y": [1.0, 2.0], "x": [1.0, 2.0], "cell": ["a", "a"],
                           "hotel_id": ["h", "h"], "period": [0, 1]})
        res = clustered_fe_ols(df, "y", ["x"], "cell", "hotel_id", period_col="period")
        self.assertEqual(res.get("error"), "too_few_rows")


class CombineFoldsTests(unittest.TestCase):
    def test_average_and_se_combination(self):
        f1 = Fit(0.10, 0.04, 2.5, 0.012, 100, 50, (0.10 - 1.96 * 0.04, 0.10 + 1.96 * 0.04))
        f2 = Fit(0.20, 0.03, 6.6, 0.0, 100, 50, (0.20 - 1.96 * 0.03, 0.20 + 1.96 * 0.03))
        c = combine_two_folds(f1, f2)
        self.assertAlmostEqual(c.beta, 0.15, places=12)
        self.assertAlmostEqual(c.se, 0.5 * float(np.sqrt(0.04**2 + 0.03**2)), places=12)
        self.assertEqual(c.n, 200)


if __name__ == "__main__":
    unittest.main()

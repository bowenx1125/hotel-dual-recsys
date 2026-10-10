"""Unit tests for the P4 direct-method off-policy evaluation harness."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.effect import ope  # noqa: E402
from src.effect.estimation import clustered_fe_ols  # noqa: E402


def _frame(n_cell: int = 40, n_per: int = 6, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for c in range(n_cell):
        for t in range(n_per):
            x = rng.normal(size=len(ope.ASPECTS))
            y = 0.3 * x[ope.ASPECTS.index("service")] + rng.normal(scale=0.4)
            rows.append({"hotel_id": f"h{c:04d}", "period": f"2016Q{t % 4 + 1}",
                         "y": y, **{ope.x_col(a): x[i] for i, a in enumerate(ope.ASPECTS)}})
    return pd.DataFrame(rows)


class ActionableBlockTests(unittest.TestCase):
    def test_actionable_excludes_location_and_keeps_six(self):
        self.assertNotIn("location", ope.ACTIONABLE)
        self.assertEqual(len(ope.ACTIONABLE), 6)
        self.assertEqual(len(ope.ASPECTS), 7)

    def test_sub_vec_maps_full_gamma_onto_actionable(self):
        gamma = np.arange(7, dtype=float)  # index 0 == location
        sub = ope.sub_vec(gamma)
        self.assertEqual(len(sub), 6)
        # location carries the value 0 and must not appear
        self.assertNotIn(0.0, sub.tolist())
        self.assertEqual(sub[ope.ACTIONABLE.index("service")],
                         float(ope.ASPECTS.index("service")))

    def test_sub_cov_returns_six_by_six_block(self):
        m = np.arange(49, dtype=float).reshape(7, 7)
        sub = ope.sub_cov(m)
        self.assertEqual(sub.shape, (6, 6))
        self.assertEqual(sub[0, 0], m[ope.IDX_ACTIONABLE[0], ope.IDX_ACTIONABLE[0]])

    def test_value_of_accepts_six_dim_share_vector(self):
        gamma = np.linspace(-0.2, 0.2, 7)
        p = np.zeros(6)
        p[ope.ACTIONABLE.index("service")] = 1.0
        v = ope.value_of(p, gamma, delta=0.1)
        expected = 0.1 * gamma[ope.ASPECTS.index("service")]
        self.assertAlmostEqual(v, float(expected), places=12)

    def test_policy_value_contrast_is_action_independent_terms_free(self):
        """Two policies with identical shares must have identical value."""
        gamma = np.linspace(-0.2, 0.2, 7)
        a = np.full(6, 1 / 6)
        b = np.full(6, 1 / 6)
        self.assertAlmostEqual(ope.value_of(a, gamma, 0.12),
                               ope.value_of(b, gamma, 0.12), places=15)


class CellEqualsClusterTests(unittest.TestCase):
    def test_same_column_for_cell_and_cluster_is_supported(self):
        """Regression: passing cell_col == cluster_col used to duplicate the
        column and blow up the groupby with 'not 1-dimensional'."""
        df = _frame()
        res = clustered_fe_ols(df, "y", [ope.x_col(a) for a in ope.ASPECTS],
                               "hotel_id", "hotel_id", period_col="period")
        self.assertNotIn("error", res)
        self.assertEqual(len(res["cov_x"]), len(ope.ASPECTS))
        self.assertEqual(len(res["cov_x"][0]), len(ope.ASPECTS))

    def test_cov_x_matches_squared_standard_errors(self):
        df = _frame()
        res = clustered_fe_ols(df, "y", [ope.x_col(a) for a in ope.ASPECTS],
                               "hotel_id", "hotel_id", period_col="period")
        cov = np.asarray(res["cov_x"])
        se = np.asarray(res["se_all"][: len(ope.ASPECTS)])
        for i in range(len(ope.ASPECTS)):
            self.assertAlmostEqual(cov[i, i], se[i] ** 2, places=10)

    def test_cov_x_is_symmetric_positive_semi_definite(self):
        df = _frame()
        res = clustered_fe_ols(df, "y", [ope.x_col(a) for a in ope.ASPECTS],
                               "hotel_id", "hotel_id", period_col="period")
        cov = np.asarray(res["cov_x"])
        self.assertTrue(np.allclose(cov, cov.T))
        self.assertTrue(np.all(np.linalg.eigvalsh(cov) > -1e-10))


if __name__ == "__main__":
    unittest.main()

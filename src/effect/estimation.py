"""P2b: cross-fit continuous-treatment effect estimation.

Estimand
--------
"Does an improvement in review-perceived aspect sentiment precede an improvement
in the hotel's subsequent guest rating, when the sentiment and the rating are
measured on *disjoint sets of reviews*?"

    x  = smoothed_net_F(t) - smoothed_net_F(t-1)      aspect sentiment, fold F
    y  = mean_score_G(t+1) - mean_score_G(t)          guest rating, fold G != F

Fold membership comes from ``sha1_review_fingerprint_mod_2`` and is disjoint at
review level, so no single review contributes to both sides.  This executes
``conf/autonomous_research.json -> crossfit.rule``.

Fixed effects: hotel x aspect (cell) absorbed by within-transformation, plus
explicit period dummies.  Standard errors clustered by hotel with a small-sample
correction for the absorbed cell dummies (the shipped ``_clustered_ols`` in
``src/autonomous/infer.py`` has neither the within transform nor the
correction).

Known conservative bias: x is measured with sampling error that is independent
of y's error, i.e. classical errors-in-variables, which biases beta toward zero.
The reported betas are therefore lower bounds in magnitude.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Fit:
    beta: float
    se: float
    t: float
    p: float
    n: int
    n_clusters: int
    ci95: tuple[float, float]

    def as_dict(self, extra: dict | None = None) -> dict:
        d = {
            "beta": self.beta,
            "se": self.se,
            "t": self.t,
            "p": self.p,
            "n": self.n,
            "n_clusters": self.n_clusters,
            "ci95": [self.ci95[0], self.ci95[1]],
        }
        if extra:
            d.update(extra)
        return d


def _t_sf(t: float, df: float) -> float:
    """Two-sided Student-t survival function without SciPy dependency."""
    try:
        from scipy import stats  # type: ignore

        return float(2.0 * stats.t.sf(abs(t), df))
    except Exception:
        pass
    # Normal approximation fallback (df is large here: >1000 hotels).
    from math import erfc, sqrt

    return float(erfc(abs(t) / sqrt(2.0)))


def within_demean(df: pd.DataFrame, cols: list[str], by: str) -> pd.DataFrame:
    """Subtract group means (absorbs one dummy per group)."""
    out = df.copy()
    g = out.groupby(by, sort=False)
    for c in cols:
        out[c] = out[c] - g[c].transform("mean")
    return out


def clustered_fe_ols(
    df: pd.DataFrame,
    y_col: str,
    x_cols: list[str],
    cell_col: str,
    cluster_col: str,
    period_col: str = "period",
    n_absorbed: int | None = None,
) -> dict:
    """Two-way FE OLS: cell fixed effects (within) + period dummies, cluster SE."""
    # cell_col and cluster_col may name the same column; de-duplicate so the
    # selection never produces a 2-D grouper.
    keep = list(dict.fromkeys([y_col, *x_cols, cell_col, cluster_col, period_col]))
    d = df[keep].dropna().copy()
    if len(d) < 50:
        return {"error": "too_few_rows", "n": int(len(d))}

    periods = sorted(d[period_col].unique())
    pdum = pd.get_dummies(d[period_col], prefix="pd", drop_first=True).astype(float)
    work = pd.concat([d.reset_index(drop=True), pdum.reset_index(drop=True)], axis=1)
    dum_cols = list(pdum.columns)

    demean_cols = [y_col, *x_cols, *dum_cols]
    work = within_demean(work, demean_cols, cell_col)

    y = work[y_col].to_numpy(float)
    X = work[x_cols + dum_cols].to_numpy(float)
    n_absorbed = work[cell_col].nunique() if n_absorbed is None else n_absorbed

    n, k = X.shape
    xtx = X.T @ X
    xtx_inv = np.linalg.pinv(xtx)
    beta = xtx_inv @ (X.T @ y)
    e = y - X @ beta

    cl = work[cluster_col].to_numpy()
    meat = np.zeros((k, k))
    for g in np.unique(cl):
        idx = cl == g
        Xg = X[idx]
        eg = e[idx][:, None]
        meat += Xg.T @ (eg @ eg.T) @ Xg
    G = int(np.unique(cl).size)
    # small-sample correction: clusters + absorbed cell dummies
    denom = max(n - k - n_absorbed, 1)
    corr = (G / max(G - 1, 1)) * ((n - 1) / denom)
    var = corr * (xtx_inv @ meat @ xtx_inv)
    se = np.sqrt(np.clip(np.diag(var), 0.0, None))

    b = float(beta[0])
    s = float(se[0])
    tval = b / s if s > 0 else float("nan")
    dfree = max(G - 1, 1)
    p = _t_sf(tval, dfree) if s > 0 else float("nan")
    fit = Fit(
        beta=b,
        se=s,
        t=float(tval),
        p=float(p),
        n=int(n),
        n_clusters=G,
        ci95=(b - 1.959964 * s, b + 1.959964 * s),
    )
    return {
        "fit": fit,
        "beta_all": beta.tolist(),
        "se_all": se.tolist(),
        # Covariance of the x_cols block (X is ordered as x_cols + period dummies),
        # needed for linear combinations such as policy-value contrasts.
        "cov_x": var[: len(x_cols), : len(x_cols)].tolist(),
        "x_cols": list(x_cols),
        "n": int(n),
        "n_clusters": G,
    }


def cluster_robust_mean(y: np.ndarray, clusters: np.ndarray) -> Fit:
    """Cluster-robust mean (intercept-only OLS) with the same small-sample care."""
    y = np.asarray(y, dtype=float)
    m = float(y.mean())
    cl = np.asarray(clusters)
    G = int(np.unique(cl).size)
    n = len(y)
    if G < 2:
        return Fit(m, float("nan"), float("nan"), float("nan"), n, G, (float("nan"), float("nan")))
    # cluster-robust variance of an intercept: V = (X'X)^-1 meat (X'X)^-1 with
    # X = ones => (1/n) * sum_j (sum_{i in j} e_i)^2 * (1/n), times G/(G-1).
    ss = np.zeros(G)
    for j, g in enumerate(np.unique(cl)):
        yg = y[cl == g]
        ss[j] = (yg - m).sum()
    se = float(np.sqrt(G / (G - 1)) * np.sqrt((ss**2).sum()) / n)
    t = m / se if se > 0 else float("nan")
    p = _t_sf(t, G - 1) if se > 0 else float("nan")
    return Fit(m, se, t, p, n, G, (m - 1.959964 * se, m + 1.959964 * se))


def combine_two_folds(f1: Fit, f2: Fit) -> Fit:
    """Cross-fit combination: equal-weight average of two fold-specific fits.

    The two folds use disjoint reviews, so treating them as independent is the
    intended (and conservative) approximation.
    """
    b = 0.5 * (f1.beta + f2.beta)
    s = 0.5 * float(np.sqrt(f1.se**2 + f2.se**2))
    t = b / s if s > 0 else float("nan")
    p = _t_sf(t, max(min(f1.n_clusters, f2.n_clusters) - 1, 1)) if s > 0 else float("nan")
    return Fit(
        beta=b,
        se=s,
        t=t,
        p=p,
        n=f1.n + f2.n,
        n_clusters=min(f1.n_clusters, f2.n_clusters),
        ci95=(b - 1.959964 * s, b + 1.959964 * s),
    )

"""P3: learn an aspect VALUE vector from the only target that carries signal.

Why this module exists
----------------------
P4 established that the decision-relevant (forward) reward has no detectable
aspect-specific structure: a direct-method OPE protocol cannot separate the
best aspect from the worst one (split-sample gap 0.026 vs permutation placebo
0.022, ratio 1.20 -> AMBER_NO_DISCRIMINATION). P4b then asked which target, if
any, is predictable at all, and found exactly one: the hotel CROSS-SECTION. A
hotel's fold-A aspect profile explains its fold-B rating level (R^2 ~ 0.45),
while quarter-over-quarter changes are noise (R^2 ~ 0.001).

So the only aspect-specific coefficient this dataset can support is a
cross-sectional LEVEL coefficient v_a:

    y_i = c + sum_a v_a * x_{i,a} + eps_i

with x the hotel's mean aspect sentiment on the DETECTION fold and y its mean
reviewer score on the OUTCOME fold (disjoint reviews).

What this is, and is not
------------------------
v_a is an ASSOCIATIONAL level coefficient. It says which aspects accompany
high ratings across hotels. It does NOT say what happens if a hotel intervenes
-- there is no intervention in this data (see P4). The shipped ranking
(structurally) has no such coefficient at all: it ranks by deficit size
(gap, criticism) with aspect-agnostic design weights, so it cannot express
"a point of service is worth more than a point of breakfast". Inserting v is
the one change the evidence can justify.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.effect import ope

ROOT = ope.ROOT
ASPECTS = ope.ASPECTS
ACTIONABLE = ope.ACTIONABLE

ALPHAS = [0.1, 1.0, 10.0, 100.0, 1000.0]
Z = 1.959964


# ------------------------------------------------------------------ data build
def hotel_table(panel: pd.DataFrame, fold_df: pd.DataFrame, detect: str, out: str,
                *, min_cells: int = 5, min_reviews: int = 30) -> pd.DataFrame:
    """One row per hotel: mean aspect profile on DETECT + rating level on OUT."""
    hm = panel[f"has_measurement_{detect}"].fillna(False)
    sub = panel[hm.to_numpy() if hasattr(hm, "to_numpy") else hm]
    sn = sub.pivot_table(index=["hotel_id", "period"], columns="aspect",
                         values=f"smoothed_net_{detect}", aggfunc="first")
    sn = sn.reindex(columns=ASPECTS)
    prof = sn.groupby("hotel_id").mean()
    cells = sn.notna().groupby("hotel_id").sum().sum(axis=1)
    prof = prof[cells >= min_cells]

    rows = []
    wcol, vcol = f"score_n_{out}", f"mean_score_{out}"
    for hid, g in fold_df.groupby("hotel_id", sort=False):
        w = g[wcol].to_numpy(float)
        v = g[vcol].to_numpy(float)
        ok = np.isfinite(v) & (w > 0)
        if ok.sum() == 0:
            continue
        rows.append((hid, float(np.average(v[ok], weights=w[ok])), int(w[ok].sum())))
    tgt = pd.DataFrame(rows, columns=["hotel_id", "y", "n"]).set_index("hotel_id")
    tgt = tgt[tgt["n"] >= min_reviews]

    d = prof.join(tgt, how="inner").reset_index()
    return d.dropna(subset=["y"]).reset_index(drop=True)


def _xy(d: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    return d[ASPECTS].to_numpy(float), d["y"].to_numpy(float)


def _median(X: np.ndarray) -> np.ndarray:
    return np.nanmedian(X, axis=0)


def _prep(X: np.ndarray, med: np.ndarray) -> np.ndarray:
    return np.where(np.isfinite(X), X, med)


class ValueFit:
    """Ridge on standardized aspect levels; keeps the transform for prediction."""

    def __init__(self, coef_psd: np.ndarray, intercept: float, mu: np.ndarray,
                 sd: np.ndarray, alpha: float):
        self.coef_psd = np.asarray(coef_psd, dtype=float)
        self.intercept = float(intercept)
        self.mu = np.asarray(mu, dtype=float)
        self.sd = np.asarray(sd, dtype=float)
        self.alpha = float(alpha)

    def predict(self, X: np.ndarray) -> np.ndarray:
        Z = (_prep(X, self.mu) - self.mu) / self.sd
        return Z @ self.coef_psd + self.intercept

    def coef_raw(self) -> np.ndarray:
        """Coefficients in original smoothed_net units (per 1.0 of net)."""
        return self.coef_psd / self.sd

    def as_dict(self, aspects: list[str]) -> dict[str, float]:
        return {a: float(self.coef_psd[i]) for i, a in enumerate(aspects)}


def fit_ridge(X: np.ndarray, y: np.ndarray, alpha: float,
              mu: np.ndarray | None = None, sd: np.ndarray | None = None) -> ValueFit:
    med = _median(X) if mu is None else mu
    Xf = _prep(X, med)
    if mu is None:
        mu = Xf.mean(axis=0)
    if sd is None:
        sd = Xf.std(axis=0)
        sd = np.where(sd > 0, sd, 1.0)
    Z = (Xf - mu) / sd
    Zc = Z - Z.mean(axis=0)
    yc = y - y.mean()
    A = Zc.T @ Zc + alpha * np.eye(Z.shape[1])
    coef = np.linalg.solve(A, Zc.T @ yc)
    return ValueFit(coef, float(y.mean() - Z.mean(axis=0) @ coef), mu, sd, alpha)


def pick_alpha(X: np.ndarray, y: np.ndarray, seed: int, n_splits: int = 5) -> float:
    """Alpha by K-fold CV on the supplied rows (never on held-out data)."""
    n = len(y)
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    folds = np.array_split(idx, n_splits)
    best_a, best_s = ALPHAS[0], None
    for a in ALPHAS:
        sse, cnt = 0.0, 0
        for f in folds:
            mask = np.ones(n, dtype=bool)
            mask[f] = False
            if mask.sum() < 20 or len(f) == 0:
                continue
            fit = fit_ridge(X[mask], y[mask], a)
            e = y[f] - fit.predict(X[f])
            sse += float((e ** 2).sum())
            cnt += len(f)
        s = sse / max(cnt, 1)
        if best_s is None or s < best_s:
            best_s, best_a = s, a
    return best_a


def marginal_coefs(X: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Per-SD UNIVARIATE slope of y on each aspect (total association).

    The multivariate (conditional) coefficient answers "holding every other
    aspect sentiment fixed", which is NOT what happens when a hotel fixes one
    aspect -- improving cleanliness also moves how guests describe the room.
    The marginal slope keeps that spillover. The two disagree in sign for
    aspects whose signal is absorbed by a stronger aspect (cleanliness and
    location are both absorbed by room/service), so both are reported and the
    divergence is part of the result, not a footnote.
    """
    med = _median(X)
    Xf = _prep(X, med)
    out: dict[str, float] = {}
    for i, a in enumerate(ASPECTS):
        s = Xf[:, i]
        sd = float(s.std())
        if sd <= 0:
            out[a] = 0.0
            continue
        b = float(np.cov(s, y, bias=True)[0, 1] / (s.var() + 1e-12))
        out[a] = b * sd
    return out


def collinearity(X: np.ndarray) -> dict:
    """Correlation matrix + condition number, so sign flips can be attributed."""
    med = _median(X)
    Xf = _prep(X, med)
    C = np.corrcoef(Xf.T)
    Xc = Xf - Xf.mean(axis=0)
    return {
        "correlation": {a: {b: float(C[i, j]) for j, b in enumerate(ASPECTS)}
                        for i, a in enumerate(ASPECTS)},
        "condition_number": float(np.linalg.cond(Xc)),
        "max_abs_offdiag": float(np.max(np.abs(C - np.eye(len(ASPECTS))))),
    }


def r2(y: np.ndarray, pred: np.ndarray) -> float:
    mse = float(((y - pred) ** 2).mean())
    mse0 = float(((y - y.mean()) ** 2).mean())
    return 1.0 - mse / mse0 if mse0 > 0 else float("nan")


# ------------------------------------------------------------------ estimation
def cv_value(d: pd.DataFrame, seed: int, n_splits: int = 5) -> dict:
    """Out-of-hotel R^2 and out-of-fold predictions (alpha re-chosen per fold)."""
    X, y = _xy(d)
    n = len(y)
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    folds = np.array_split(idx, n_splits)
    preds = np.zeros(n)
    alphas = []
    for f in folds:
        mask = np.ones(n, dtype=bool)
        mask[f] = False
        if mask.sum() < 30:
            preds[f] = y.mean()
            alphas.append(None)
            continue
        a = pick_alpha(X[mask], y[mask], seed)
        fit = fit_ridge(X[mask], y[mask], a)
        preds[f] = fit.predict(X[f])
        alphas.append(a)
    return {
        "n_hotels": int(n),
        "r2_out_of_hotel": r2(y, preds),
        "rmse": float(np.sqrt(((y - preds) ** 2).mean())),
        "sd_target": float(y.std(ddof=1)),
        "corr": float(np.corrcoef(preds, y)[0, 1]),
        "alphas": alphas,
        "n_splits": n_splits,
    }


def fit_full(d: pd.DataFrame, seed: int) -> ValueFit:
    X, y = _xy(d)
    return fit_ridge(X, y, pick_alpha(X, y, seed))


def bootstrap_coefs(d: pd.DataFrame, alpha: float, boots: int, seed: int) -> dict:
    """Hotel-level bootstrap of the per-SD coefficients."""
    X, y = _xy(d)
    n = len(y)
    rng = np.random.default_rng(seed)
    draws = np.zeros((boots, len(ASPECTS)))
    for b in range(boots):
        idx = rng.integers(0, n, n)
        try:
            draws[b] = fit_ridge(X[idx], y[idx], alpha).coef_psd
        except np.linalg.LinAlgError:
            draws[b] = np.nan
    out = {}
    for i, a in enumerate(ASPECTS):
        v = draws[:, i]
        v = v[np.isfinite(v)]
        if v.size < 5:
            out[a] = {"coef": None, "se": None, "ci95": None, "t": None}
            continue
        m, s = float(v.mean()), float(v.std(ddof=1))
        out[a] = {
            "coef": m,
            "se": s,
            "ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))],
            "t": (m / s) if s > 0 else None,
            "share_positive": float(np.mean(v > 0)),
        }
    return {"n_boot": int(boots), "aspects": out}


def placebo_cv(d: pd.DataFrame, seed: int, n_splits: int = 5, reps: int = 5) -> dict:
    """Shuffle the target across hotels: a real v must collapse to R^2 ~ 0."""
    X, y = _xy(d)
    rng = np.random.default_rng(seed + 991)
    vals = []
    for _ in range(reps):
        ys = y[rng.permutation(len(y))]
        dd = d.copy()
        dd["y"] = ys
        vals.append(cv_value(dd, seed, n_splits)["r2_out_of_hotel"])
    return {
        "n_reps": reps,
        "mean_r2": float(np.mean(vals)),
        "sd_r2": float(np.std(vals, ddof=1)) if len(vals) > 1 else None,
        "max_r2": float(np.max(vals)),
    }


def half_stability(d: pd.DataFrame, seed: int, reps: int = 40) -> dict:
    """Correlation of v estimated on two DISJOINT hotel halves.

    This is the crux number for P3: if v does not reproduce across independent
    hotel samples, inserting it into the ranking buys nothing.
    """
    X, y = _xy(d)
    n = len(y)
    rng = np.random.default_rng(seed + 555)
    act_idx = [ASPECTS.index(a) for a in ACTIONABLE]
    cors_act, cors_all = [], []
    for _ in range(reps):
        perm = rng.permutation(n)
        h1, h2 = perm[: n // 2], perm[n // 2:]
        try:
            f1 = fit_ridge(X[h1], y[h1], pick_alpha(X[h1], y[h1], seed))
            f2 = fit_ridge(X[h2], y[h2], pick_alpha(X[h2], y[h2], seed + 1))
        except np.linalg.LinAlgError:
            continue
        c1, c2 = f1.coef_psd, f2.coef_psd
        if np.std(c1) == 0 or np.std(c2) == 0:
            continue
        cors_all.append(float(np.corrcoef(c1, c2)[0, 1]))
        cors_act.append(float(np.corrcoef(c1[act_idx], c2[act_idx])[0, 1]))
    if not cors_act:
        return {"error": "no_reps"}
    return {
        "n_reps": len(cors_act),
        "corr_actionable_mean": float(np.mean(cors_act)),
        "corr_actionable_sd": float(np.std(cors_act, ddof=1)) if len(cors_act) > 1 else None,
        "corr_all7_mean": float(np.mean(cors_all)),
        "share_positive": float(np.mean([c > 0 for c in cors_act])),
    }


# --------------------------------------------------------------------- driver
def estimate(d: pd.DataFrame, *, seed: int, boots: int,
             with_placebo: bool = True, with_stability: bool = True) -> dict:
    """Full estimation battery on an already-built hotel-level table."""
    if len(d) < 100:
        return {"error": "too_few_hotels", "n": int(len(d))}

    cv = cv_value(d, seed)
    fit = fit_full(d, seed)
    boot = bootstrap_coefs(d, fit.alpha, boots, seed)
    pl = placebo_cv(d, seed) if with_placebo else None
    stab = half_stability(d, seed) if with_stability else None

    X, y = _xy(d)
    in_r2 = r2(y, fit.predict(X))

    gap = cv["r2_out_of_hotel"]
    pl_r2 = pl["mean_r2"] if pl else None
    ratio = (abs(gap) / abs(pl_r2)) if pl_r2 else None

    out = {
        "n_hotels": int(len(d)),
        "alpha": fit.alpha,
        "r2_in_sample": in_r2,
        "cv": cv,
        "coef_per_sd": fit.as_dict(ASPECTS),
        "coef_marginal_per_sd": marginal_coefs(X, y),
        "coef_raw": {a: float(fit.coef_raw()[i]) for i, a in enumerate(ASPECTS)},
        "collinearity": collinearity(X),
        "bootstrap": boot,
        "target_mean": float(y.mean()),
        "target_sd": float(y.std(ddof=1)),
    }
    if pl is not None:
        out["placebo"] = pl
        out["placebo_ratio"] = ratio
    if stab is not None:
        out["half_stability"] = stab
    return out


def learn(detect: str, out: str, *, seed: int, boots: int, panel=None,
          fold_df=None, min_cells: int = 5, min_reviews: int = 30) -> dict:
    if panel is None:
        panel = pd.read_parquet(ope.PANEL)
    if fold_df is None:
        fold_df = pd.read_parquet(ope.FOLD)
    d = hotel_table(panel, fold_df, detect, out,
                    min_cells=min_cells, min_reviews=min_reviews)
    res = estimate(d, seed=seed, boots=boots)
    res["direction"] = f"{detect}->{out}"
    res["min_cells"] = min_cells
    res["min_reviews"] = min_reviews
    return res

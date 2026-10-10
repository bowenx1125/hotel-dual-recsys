"""P4: cross-fitted direct-method off-policy evaluation harness.

NOT IPS/SNIPS.
--------------
This project has no logged policy: `outputs/autonomous/wave6/policy.json`
records `no_ips_snips: true`, and reviewer rule R1 P2 states "Do not wrap
offline evaluation as IPS/SNIPS." Inverse-propensity scoring is therefore
*unavailable by construction* -- there is no behaviour policy and no action
propensity to divide by. What is implemented here is the **direct method**
(outcome regression) with cross-fitting, which needs no propensities.

Value decomposition
-------------------
Outcome model, estimated on training hotels:

    r_it = sum_a gamma_a * x_it,a + period dummies + hotel FE + eps_it

* `x_it,a` -- quarter-over-quarter change of aspect-a sentiment, measured on
  the DETECTION fold.
* `r_it`   -- quarter-ahead change of the mean reviewer score, measured on the
  OUTCOME fold (disjoint reviews -> no same-review mechanical coupling).

A counterfactual "the hotel moves aspect a by delta" is worth `gamma_a * delta`
plus terms that do not depend on the action. Every candidate policy is scored
on the SAME held-out states, so action-independent terms cancel in a contrast:

    V(pi) - V(ref) = delta * sum_a (p_a^pi - p_a^ref) * gamma_a

with `p_a^pi` the share of held-out states on which pi selects aspect a
(abstention contributes 0). The standard error comes from the hotel-clustered
covariance of gamma (delta method) and is cross-checked by a hotel-clustered
bootstrap.

The headline quantity is NOT "which policy wins" but the **discrimination
power** of the protocol: V(oracle best) - V(oracle worst) with its CI. If the
protocol cannot separate the best aspect from the worst, then any gain a
future P3 reports is indistinguishable from noise.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "data" / "processed" / "hotel_aspect_quarter_v2.parquet"
FOLD = ROOT / "data" / "processed" / "hotel_quarter_fold.parquet"
PEERS = ROOT / "data" / "processed" / "geo_reference_sets_v2.parquet"

ASPECTS = ["location", "cleanliness", "breakfast", "service", "noise", "room", "value"]
ACTIONABLE = [a for a in ASPECTS if a != "location"]

Z = 1.959964


def x_col(a: str) -> str:
    return f"x_{a}"


# Aspect share vectors and policy value contrasts live on the ACTIONABLE block
# (Location is diagnostic-only and can never be an action).
IDX_ACTIONABLE = [ASPECTS.index(a) for a in ACTIONABLE]


def sub_vec(v: np.ndarray) -> np.ndarray:
    return np.asarray(v, dtype=float)[IDX_ACTIONABLE]


def sub_cov(m: np.ndarray) -> np.ndarray:
    return np.asarray(m, dtype=float)[np.ix_(IDX_ACTIONABLE, IDX_ACTIONABLE)]


def period_ord(p: pd.Series) -> pd.Series:
    s = p.astype(str)
    return s.str.slice(0, 4).astype(int) * 4 + s.str.slice(5, 6).astype(int)


# ---------------------------------------------------------------- state panel
def fold_panel(panel: pd.DataFrame, fold: str, fold_df: pd.DataFrame,
               cfg: dict) -> pd.DataFrame:
    """Rebuild the demo-facing panel so that EVERY field comes from one fold.

    The shipped demo state is pooled, which means reviews of the outcome fold
    leak into the state used by the policy -- a mechanical channel that would
    inflate any off-policy value. Substituting a single fold removes it.
    """
    d = panel.copy()
    d["positive_mentions"] = d[f"positive_mentions_{fold}"]
    d["negative_mentions"] = d[f"negative_mentions_{fold}"]
    d["total_mentions"] = d[f"total_mentions_{fold}"]
    d["has_measurement"] = d[f"has_measurement_{fold}"]
    d["smoothed_net"] = d[f"smoothed_net_{fold}"]

    tot = d["total_mentions"].astype(float)
    pos = d["positive_mentions"].astype(float)
    neg = d["negative_mentions"].astype(float)
    raw = np.where(tot > 0, (pos - neg) / np.where(tot > 0, tot, 1.0), np.nan)
    d["raw_net"] = raw

    k = float(cfg.get("reliability_k", 10.0))
    d["measurement_reliability"] = tot / (tot + k)

    f = fold_df[["hotel_id", "period", f"mean_score_{fold}", f"score_n_{fold}"]].rename(
        columns={f"mean_score_{fold}": "mean_reviewer_score",
                 f"score_n_{fold}": "total_reviews"}
    )
    d = d.drop(columns=["mean_reviewer_score", "total_reviews"]).merge(
        f, on=["hotel_id", "period"], how="left"
    )
    d["total_reviews"] = d["total_reviews"].fillna(0).astype(int)
    d["prior_strength"] = float(cfg.get("reliability_k", 10.0))
    return d


# ------------------------------------------------------------- decision units
def build_units(panel: pd.DataFrame, fold_df: pd.DataFrame, detect: str, out: str,
                *, timing: str, min_reviews: int, periods: list[str]) -> pd.DataFrame:
    """Hotel-quarter decision units: treatments x_a (detection fold) + reward r."""
    sn = panel.pivot_table(index=["hotel_id", "period"], columns="aspect",
                           values=f"smoothed_net_{detect}", aggfunc="first")
    hm = panel.pivot_table(index=["hotel_id", "period"], columns="aspect",
                           values=f"has_measurement_{detect}", aggfunc="first")
    sn = sn.reindex(columns=ASPECTS)
    hm = hm.reindex(columns=ASPECTS).fillna(False).astype(bool)

    L = sn.reset_index()
    H = hm.reset_index()
    L["_o"] = period_ord(L["period"])
    H["_o"] = period_ord(H["period"])
    L = L.sort_values(["hotel_id", "_o"]).reset_index(drop=True)
    H = H.sort_values(["hotel_id", "_o"]).reset_index(drop=True)

    gL, gH = L.groupby("hotel_id"), H.groupby("hotel_id")
    prev_sn = gL[ASPECTS].shift(1)
    prev_hm = gH[ASPECTS].shift(1)
    prev_o = gL["_o"].shift(1)
    contiguous = (L["_o"] - prev_o == 1).fillna(False)

    for a in ASPECTS:
        L[x_col(a)] = L[a] - prev_sn[a]
        L[f"hm_{a}"] = H[a].fillna(False) & prev_hm[a].fillna(False)
    L["contiguous_lag"] = contiguous

    f = fold_df[["hotel_id", "period", f"mean_score_{out}", f"score_n_{out}"]].copy()
    f["_o"] = period_ord(f["period"])
    f = f.sort_values(["hotel_id", "_o"]).reset_index(drop=True)
    gf = f.groupby("hotel_id")
    f["ms_next"] = gf[f"mean_score_{out}"].shift(-1)
    f["n_next"] = gf[f"score_n_{out}"].shift(-1)
    f["ms_prev"] = gf[f"mean_score_{out}"].shift(1)
    f["n_prev"] = gf[f"score_n_{out}"].shift(1)
    f["o_next"] = gf["_o"].shift(-1)
    f["contiguous_next"] = (f["o_next"] - f["_o"] == 1).fillna(False)

    u = L.merge(f, on=["hotel_id", "period", "_o"], how="inner")
    u = u[u["period"].isin(periods)].copy()

    if timing == "forward":
        u = u[u["contiguous_next"]]
        u = u[(u[f"score_n_{out}"] >= min_reviews) & (u["n_next"] >= min_reviews)]
        u["y"] = u["ms_next"] - u[f"mean_score_{out}"]
    elif timing == "contemp":
        u = u[u["contiguous_lag"]]
        u = u[(u[f"score_n_{out}"] >= min_reviews) & (u["n_prev"] >= min_reviews)]
        u["y"] = u[f"mean_score_{out}"] - u["ms_prev"]
    else:
        raise ValueError(f"unknown timing {timing!r}")

    u = u[u["contiguous_lag"]]
    ok = np.ones(len(u), dtype=bool)
    for a in ASPECTS:
        ok &= u[f"hm_{a}"].fillna(False).to_numpy()
    u = u[ok]
    return u[["hotel_id", "period", "y", *[x_col(a) for a in ASPECTS]]].reset_index(drop=True)


# -------------------------------------------------------------- policy picks
def build_choices(panel_fold: pd.DataFrame, peers: pd.DataFrame, cfg: dict,
                  periods: list[str], weight_variants: dict[str, dict] | None = None,
                  value_by_hotel: dict[str, dict] | None = None
                  ) -> pd.DataFrame:
    """Run every shipped policy (+ weight variants) on each period's state.

    `value_by_hotel` maps hotel_id -> aspect value vector dict. When supplied,
    a `value_aware` column is produced using each hotel's own (already
    out-of-split) value vector, so no hotel is scored with a vector that was
    estimated on itself.
    """
    from src.recommendation.panel_adapter import build_panel_snapshot
    from src.recommendation.scoring import all_policies, peer_relative_scores
    from src.recommendation.value_policy import value_aware_scores

    rows = []
    for p in periods:
        snap = build_panel_snapshot(panel_fold, peers, cfg, period=p)
        for h in snap["hotels"]:
            rec = {"hotel_id": h["hotel_id"], "period": p}
            for name, res in all_policies(h, cfg, assumed_intensity=0.0).items():
                rec[name] = res.get("chosen_aspect")
            for vname, w in (weight_variants or {}).items():
                try:
                    sc = peer_relative_scores(h, cfg, 0.0, weights=w, actionable_only=True)
                    pick = None
                    if sc:
                        pick = sorted(sc.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
                except Exception:
                    pick = None
                rec[f"wrank_{vname}"] = pick
            if value_by_hotel is not None:
                try:
                    vv = value_by_hotel.get(h["hotel_id"])
                    sc = value_aware_scores(h, cfg, vv, 0.0, actionable_only=True)
                    rec["value_aware"] = (sorted(sc.items(),
                                                 key=lambda kv: (-kv[1], kv[0]))[0][0]
                                          if sc else None)
                except Exception:
                    rec["value_aware"] = None
            rows.append(rec)
    return pd.DataFrame(rows)


def shares(choices: pd.DataFrame, col: str) -> np.ndarray:
    """p_a over ACTIONABLE aspects for one policy column (abstention dropped)."""
    v = choices[col]
    out = np.zeros(len(ACTIONABLE))
    vc = v.value_counts(dropna=True)
    tot = float(v.notna().sum())
    if tot <= 0:
        return out
    for i, a in enumerate(ACTIONABLE):
        out[i] = float(vc.get(a, 0)) / tot
    return out


# ---------------------------------------------------------------- estimation
def fit_gamma(u: pd.DataFrame) -> dict:
    from src.effect.estimation import clustered_fe_ols

    res = clustered_fe_ols(u, "y", [x_col(a) for a in ASPECTS], "hotel_id",
                           "hotel_id", period_col="period")
    if "error" in res:
        return {"error": res["error"], "n": res.get("n", 0)}
    return {
        "gamma": np.asarray(res["beta_all"][: len(ASPECTS)], dtype=float),
        "se": np.asarray(res["se_all"][: len(ASPECTS)], dtype=float),
        "cov": np.asarray(res["cov_x"], dtype=float),
        "n": int(res["n"]),
        "n_clusters": int(res["n_clusters"]),
    }


def value_of(p: np.ndarray, gamma: np.ndarray, delta: float) -> float:
    """Value of a policy whose aspect-share vector is p (over ACTIONABLE)."""
    return float(delta * (np.asarray(p, dtype=float) @ sub_vec(gamma)))

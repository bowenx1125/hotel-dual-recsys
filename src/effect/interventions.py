"""P5-A: revealed-intervention event study.

Why this module exists
----------------------
The project's goal is "prove the algorithm increases hotel revenue". Every
estimand attempted so far sits downstream of a link the data does not
contain:

    policy -> recommended action -> MANAGER ADOPTS? -> hotel improves
           -> rating rises -> demand rises -> revenue rises

`MANAGER ADOPTS?` and `revenue` are unobserved here: the review corpus has no
adoption log, no ADR and no occupancy for these hotels, and the scraped price
sample covers a different country (Belgium) so it cannot be joined to the
panel (Paris / London / Barcelona / Milan / Vienna / Amsterdam).

P4 showed the decision-relevant forward reward cannot separate policies
(placebo ratio 1.20). P3 showed the only estimable aspect-specific quantity is
a cross-sectional LEVEL association, which is not an intervention effect.

This module does two things:

1.  Closes as much of the gap as the data allows, by treating a persistent
    jump in aspect sentiment as a REVEALED INTERVENTION and running a
    fold-pure difference-in-differences around it.
2.  Measures the remaining gap precisely enough to SPECIFY what external data
    would close it -- a minimum detectable effect and a required sample size,
    computed from the noise actually present in this panel. Point (2) is the
    deliverable that converts "we need intervention records" into "we need N
    logged interventions".

The design
----------
    event(a) at (i, t)  iff  net_a^D[t]   - net_a^D[t-1] >= tau
                        and  net_a^D[t+1] - net_a^D[t-1] >= tau * persist_frac

* `D` is the DETECTION fold; the outcome is measured on the OUT fold, so the
  reviews that define the event are disjoint from the reviews that score it
  (fold-purity, as in P2/P3/P4 -- no same-review mechanical coupling).
* Outcome `dY = Y^O[t+1] - Y^O[t-1]` spans the event, so it does not matter
  whether part of the effect lands in quarter t or in t+1.
* Control pool: hotel-quarters with no event on ANY aspect.
* Reliability floor on t-1, t and t+1: a jump measured on three reviews is
  mostly sampling noise, and noise on the pre-level manufactures fake jumps.

What it does and does not identify
----------------------------------
`ATT_a` is the rating change that FOLLOWS an observed, persistent improvement
in aspect a. It is the effect of "something happened at this hotel that shows
up in aspect a" -- NOT of "the manager acted on aspect a because we told them
to". A hotel that fixes service may also repaint the lobby; a positive ATT_a
can be hotel-wide improvement leaking into aspect a. Two guards are built in:

* SPECIFICITY -- under an aspect-specific effect, the OUT-fold sentiment of
  the event aspect must move more than the other aspects at the same
  hotel-quarter. If every aspect moves together, the event is hotel-wide.
* DETERIORATION -- the mirrored event (a persistent DROP) must give the
  mirrored sign. A design that only lights up on the positive side is
  picking up mean reversion, not interventions.

Both are reported; neither is optional.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from src.effect.ope import ACTIONABLE, ASPECTS, FOLD, PANEL, Z  # noqa: E402


# --------------------------------------------------------------------------
# data preparation
# --------------------------------------------------------------------------
def quarter_ordinal(period: pd.Series) -> pd.Series:
    """'2016Q3' -> a sortable integer (4 quarters per year)."""
    s = period.astype(str).str.strip()
    return s.str[:4].astype(int) * 4 + s.str[-1].astype(int)


def build_cells(detect: str = "A", out: str = "B",
                panel_path: Path = PANEL, fold_path: Path = FOLD) -> pd.DataFrame:
    """One row per (hotel, quarter, aspect) with the event geometry attached.

    Detection uses `smoothed_net_{detect}`; every outcome uses the `{out}`
    fold. Columns kept are the ones the event rule and the DID need.
    """
    if detect == out:
        raise ValueError("detection and outcome folds must differ (fold-purity)")
    v2 = pd.read_parquet(panel_path)
    fold = pd.read_parquet(fold_path)

    keep = ["hotel_id", "period", "aspect", "city",
            f"smoothed_net_{detect}", f"smoothed_net_{out}",
            "measurement_reliability", "has_measurement", "period_complete"]
    d = v2[[c for c in keep if c in v2.columns]].copy()
    d = d.rename(columns={f"smoothed_net_{detect}": "net_d",
                          f"smoothed_net_{out}": "net_o"})
    d["t"] = quarter_ordinal(d["period"])

    fold = fold.copy()
    fold["t"] = quarter_ordinal(fold["period"])
    score = fold.set_index(["hotel_id", "t"])[f"mean_score_{out}"]

    d = d.sort_values(["hotel_id", "aspect", "t"], kind="stable").reset_index(drop=True)
    g = d.groupby(["hotel_id", "aspect"], sort=False)
    for col in ("net_d", "net_o", "measurement_reliability", "t", "period_complete"):
        d[f"{col}_pre"] = g[col].shift(1)
        d[f"{col}_post"] = g[col].shift(-1)

    # keep only cells with a genuine contiguous t-1, t, t+1
    d = d[(d["t_pre"] == d["t"] - 1) & (d["t_post"] == d["t"] + 1)].copy()
    d = d[(d["t"] - 2).isin(set(d["t"])) | True]  # t-2 may be missing; handled below

    def at(offset: int) -> np.ndarray:
        idx = pd.MultiIndex.from_arrays([d["hotel_id"].to_numpy(),
                                         d["t"].to_numpy() + offset])
        return score.reindex(idx).to_numpy(dtype=float)

    d["Y_pre"] = at(-1)
    d["Y_post"] = at(1)
    d["Y_pre2"] = at(-2)

    d["dY"] = d["Y_post"] - d["Y_pre"]              # outcome: spans the event
    d["dY_trend"] = d["Y_pre"] - d["Y_pre2"]        # pre-trend: t-2 -> t-1
    d["jump"] = d["net_d"] - d["net_d_pre"]
    d["persist"] = d["net_d_post"] - d["net_d_pre"]
    d["dnet_self"] = d["net_o_post"] - d["net_o_pre"]   # OUT-fold, event aspect
    return d


def detect_events(cells: pd.DataFrame, tau: float = 0.25, persist_frac: float = 0.5,
                  min_rel: float = 0.30, sign: int = 1,
                  require_complete: bool = True) -> pd.DataFrame:
    """Persistent jumps (`sign=+1`) or persistent drops (`sign=-1`).

    `sign=-1` is the deterioration arm: it must not be omitted, because the
    whole design is suspect if drops do not produce the mirrored estimate.
    """
    d = cells
    m = ((sign * d["jump"] >= tau)
         & (sign * d["persist"] >= tau * persist_frac)
         & (d["measurement_reliability"] >= min_rel)
         & (d["measurement_reliability_pre"] >= min_rel)
         & (d["measurement_reliability_post"] >= min_rel)
         & d["has_measurement"].fillna(False))
    if require_complete and "period_complete_post" in d.columns:
        m &= d["period_complete_post"].fillna(False)
    cols = ["hotel_id", "t", "period", "aspect", "city", "jump", "persist",
            "dY", "dY_trend", "Y_pre", "dnet_self", "measurement_reliability"]
    return d[m][cols].copy()


def hotel_period_table(cells: pd.DataFrame) -> pd.DataFrame:
    """Collapse to one row per hotel-quarter (the outcome does not vary by aspect)."""
    return (cells.sort_values(["hotel_id", "t"])
            .groupby(["hotel_id", "t", "period"], as_index=False)
            .agg(dY=("dY", "first"), dY_trend=("dY_trend", "first"),
                 Y_pre=("Y_pre", "first"), city=("city", "first")))


# --------------------------------------------------------------------------
# estimation
# --------------------------------------------------------------------------
def _hotel_groups(hotel_ids: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
    """(unique hotel codes per row, list of positional row indices per hotel)."""
    codes, uniq = pd.factorize(hotel_ids, sort=False)
    groups = [np.flatnonzero(codes == i) for i in range(len(uniq))]
    return codes, groups


def estimate(hpt: pd.DataFrame, events: pd.DataFrame, *, min_n: int = 40,
             reps: int = 400, seed: int = 20260915,
             aspects: list[str] | None = None) -> dict:
    """DID by aspect, with a hotel-clustered bootstrap and a label-permutation
    placebo for the best-minus-worst gap.

    The placebo is not optional. A max-minus-min gap over K noisy coefficients
    is inflated by construction -- the permutation distribution (aspect labels
    shuffled across events, counts preserved) is what says how much.
    """
    asp = [a for a in (aspects or ASPECTS)]
    dY = hpt["dY"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)

    # positional index of every event row inside hpt
    key = pd.MultiIndex.from_arrays([hpt["hotel_id"], hpt["t"]])
    ev_pos = key.get_indexer(pd.MultiIndex.from_arrays([events["hotel_id"],
                                                        events["t"]]))
    # a hotel-quarter whose outcome is missing (no OUT-fold review at t-1 or
    # t+1) can be neither a treated unit nor a control
    valid = np.isfinite(dY)
    ok = (ev_pos >= 0) & valid[np.clip(ev_pos, 0, None)]
    ev_pos, ev_lab = ev_pos[ok], events["aspect"].to_numpy()[ok]

    # control = hotel-quarters with no event at all
    ctrl_mask = valid.copy()
    ctrl_mask[ev_pos] = False

    masks = {}
    for a in asp:
        m = np.zeros(len(hpt), dtype=bool)
        m[ev_pos[ev_lab == a]] = True
        if m.sum() >= min_n:
            masks[a] = m

    if not masks or ctrl_mask.sum() < min_n:
        return {"error": "too few events or controls",
                "n_events": int(len(ev_pos)), "n_control": int(ctrl_mask.sum())}

    ctrl_mean = float(dY[ctrl_mask].mean())
    sigma = float(np.nanstd(dY[ctrl_mask], ddof=1))

    att = {}
    for a, m in masks.items():
        n = int(m.sum())
        diff = float(dY[m].mean() - ctrl_mean)
        # unclustered SE is only a first look; the bootstrap below is the report
        se0 = float(np.sqrt(dY[m].var(ddof=1) / n + dY[ctrl_mask].var(ddof=1)
                            / ctrl_mask.sum()))
        att[a] = {"n": n, "att": diff, "se_unclustered": se0,
                  "t_unclustered": (diff / se0 if se0 > 0 else float("nan"))}

    # ---- hotel-clustered bootstrap -------------------------------------
    # pooled ("did anything at all help?") and pre-trend ("was it already
    # rising?") -- both must be reported alongside the per-aspect numbers,
    # because a positive pooled effect with a positive pre-trend is a trend,
    # not an intervention effect.
    trend = hpt["dY_trend"].to_numpy(dtype=float)
    treated_any = np.zeros(len(hpt), dtype=bool)
    treated_any[ev_pos] = True
    pooled_att = float(dY[treated_any].mean() - ctrl_mean)
    pretrend = float(np.nanmean(trend[treated_any]) - np.nanmean(trend[ctrl_mask]))

    _, groups = _hotel_groups(hpt["hotel_id"].to_numpy())
    nh = len(groups)
    boot: dict[str, list[float]] = {a: [] for a in masks}
    gaps: list[float] = []
    b_pooled: list[float] = []
    b_trend: list[float] = []
    for _ in range(reps):
        pick = rng.integers(0, nh, nh)
        idx = np.concatenate([groups[i] for i in pick])
        dy, cm = dY[idx], ctrl_mask[idx]
        # boolean masks re-indexed into the resampled frame
        mask_map = {a: masks[a][idx] for a in masks}
        cmean = float(np.nanmean(dy[cm])) if cm.sum() else float("nan")
        vals = []
        for a in masks:
            ma = mask_map[a]
            if ma.sum() >= min_n:
                v = float(np.nanmean(dy[ma])) - cmean
                boot[a].append(v)
                vals.append(v)
            else:
                boot[a].append(float("nan"))
        if len(vals) == len(masks) and np.isfinite(cmean):
            gaps.append(float(np.max(vals) - np.min(vals)))
        tr, pot = trend[idx], treated_any[idx]
        if pot.sum() and cm.sum():
            b_pooled.append(float(np.nanmean(dy[pot]) - np.nanmean(dy[cm])))
            b_trend.append(float(np.nanmean(tr[pot]) - np.nanmean(tr[cm])))

    for a in masks:
        b = np.array([x for x in boot[a] if np.isfinite(x)], dtype=float)
        if len(b) > 1:
            att[a]["se"] = float(b.std(ddof=1))
            att[a]["ci95"] = [float(np.quantile(b, 0.025)),
                              float(np.quantile(b, 0.975))]
            att[a]["t"] = att[a]["att"] / att[a]["se"] if att[a]["se"] > 0 else None
            att[a]["share_positive"] = float((b > 0).mean())

    def _gap(labels: np.ndarray) -> float:
        counts = np.bincount(labels, minlength=len(asp))
        sums = np.bincount(labels, weights=dY[ev_pos], minlength=len(asp))
        vals = [sums[i] / counts[i] for i in range(len(asp))
                if counts[i] >= min_n and asp[i] in masks]
        return float(max(vals) - min(vals)) if len(vals) == len(masks) else float("nan")

    codes = np.array([asp.index(a) for a in ev_lab if a in asp], dtype=int)
    obs_gap = float(max(v["att"] for v in att.values())
                    - min(v["att"] for v in att.values()))

    sims = np.array([_gap(rng.permutation(codes)) for _ in range(reps)], dtype=float)
    sims = sims[np.isfinite(sims)]
    p95 = float(np.quantile(sims, 0.95)) if len(sims) else float("nan")
    ratio = float(obs_gap / sims.mean()) if len(sims) and sims.mean() > 0 else float("nan")
    pval = float((sims >= obs_gap).mean()) if len(sims) else float("nan")

    g = np.array([x for x in gaps if np.isfinite(x)], dtype=float)
    bp = np.array([x for x in b_pooled if np.isfinite(x)], dtype=float)
    bt = np.array([x for x in b_trend if np.isfinite(x)], dtype=float)
    return {
        "tau_used": None,
        "pooled": {
            "att": pooled_att,
            "se": float(bp.std(ddof=1)) if len(bp) > 1 else None,
            "t": (pooled_att / bp.std(ddof=1)) if len(bp) > 1 and bp.std(ddof=1) > 0 else None,
            "ci95": [float(np.quantile(bp, 0.025)), float(np.quantile(bp, 0.975))]
            if len(bp) > 1 else None,
            "share_positive": float((bp > 0).mean()) if len(bp) else None,
            "n_treated": int(treated_any.sum()),
        },
        "pre_trend": {
            "diff": pretrend,
            "se": float(bt.std(ddof=1)) if len(bt) > 1 else None,
            "t": (pretrend / bt.std(ddof=1)) if len(bt) > 1 and bt.std(ddof=1) > 0 else None,
            "n": int(np.isfinite(trend[treated_any]).sum()),
        },
        "n_events": int(len(ev_pos)),
        "n_control": int(ctrl_mask.sum()),
        "control_mean_dY": ctrl_mean,
        "sigma_dY_control": sigma,
        "att_by_aspect": att,
        "gap": {
            "observed": obs_gap,
            "bootstrap_se": float(g.std(ddof=1)) if len(g) > 1 else None,
            "bootstrap_ci95": [float(np.quantile(g, 0.025)), float(np.quantile(g, 0.975))]
            if len(g) > 1 else None,
        },
        "placebo_gap": {
            "mean": float(sims.mean()) if len(sims) else None,
            "p95": p95,
            "max": float(sims.max()) if len(sims) else None,
            "reps": int(len(sims)),
            "ratio_observed_over_placebo": ratio,
            "p_value": pval,
        },
        "best_aspect": max(att, key=lambda a: att[a]["att"]),
        "worst_aspect": min(att, key=lambda a: att[a]["att"]),
    }


def specificity(cells: pd.DataFrame, events: pd.DataFrame) -> dict:
    """Does the event aspect move MORE than the others at the same hotel-quarter?

    If a "service event" is followed by every aspect improving, the effect is
    hotel-wide and `ATT_a` is not aspect-specific -- it is a renovation
    detector, not a service detector.
    """
    d = cells.copy()
    tot = d.groupby(["hotel_id", "t"])["dnet_self"].transform("sum")
    cnt = d.groupby(["hotel_id", "t"])["dnet_self"].transform("count")
    d["dnet_other"] = (tot - d["dnet_self"]) / (cnt - 1).replace(0, np.nan)
    ev = events.merge(
        d[["hotel_id", "t", "aspect", "dnet_self", "dnet_other"]],
        on=["hotel_id", "t", "aspect"], how="left", suffixes=("", "_c"))
    ev = ev.dropna(subset=["dnet_self", "dnet_other"])
    if len(ev) < 30:
        return {"error": "too few events for the specificity check", "n": int(len(ev))}
    diff = (ev["dnet_self"] - ev["dnet_other"]).to_numpy(dtype=float)
    m, se = float(diff.mean()), float(diff.std(ddof=1) / np.sqrt(len(diff)))
    return {
        "n": int(len(diff)),
        "mean_self_minus_other": m,
        "se": se,
        "t": (m / se if se > 0 else None),
        "share_positive": float((diff > 0).mean()),
    }


# --------------------------------------------------------------------------
# power / MDE -- the part that specifies the external data requirement
# --------------------------------------------------------------------------
_Z_ALPHA = 1.959964
_Z_POWER = 0.841621


def mde(sigma: float, n_treated: int, n_control: int,
        alpha: float = 0.05, power: float = 0.80) -> float:
    """Smallest two-sample difference detectable at `power`."""
    z = _Z_ALPHA + _Z_POWER
    return float(z * sigma * np.sqrt(1.0 / max(n_treated, 1) + 1.0 / max(n_control, 1)))


def required_n_per_arm(delta: float, sigma: float,
                       alpha: float = 0.05, power: float = 0.80) -> int:
    """Observations PER ARM needed to detect `delta` (two-sample, equal n)."""
    if not np.isfinite(delta) or delta <= 0:
        return -1
    z = _Z_ALPHA + _Z_POWER
    return int(np.ceil(2.0 * (z * sigma / delta) ** 2))


def power_table(sigma: float, n_treated: int, n_control: int,
                deltas: list[float] | None = None) -> list[dict]:
    """MDE at the current n, and the n that each target effect would need."""
    out = []
    for delta in (deltas or [0.02, 0.05, 0.10, 0.20, 0.50]):
        out.append({
            "target_effect_rating_points": delta,
            "n_per_arm_needed": required_n_per_arm(delta, sigma),
            "detectable_now": bool(mde(sigma, n_treated, n_control) <= delta),
        })
    return out

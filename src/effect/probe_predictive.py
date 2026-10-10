"""P4b: is there a *predictive* target that P3 could legitimately optimise?

P4 showed the decision-relevant (forward, causal-flavoured) reward carries no
detectable aspect-specific signal, so tuning the recommendation weights against
it is unfalsifiable. Prediction is a weaker but honest target: it needs no
identification, only out-of-sample skill.

This probe asks: using a fold-pure state (aspect levels and recent moves seen
on fold A only), can we predict the quarter-ahead change of the reviewer score
measured on the OTHER fold (B)? Two comparisons matter:

1. Ridge on aspect features vs. predicting zero (the natural baseline for a
   change target). Out-of-sample R^2 > 0 means there is something to learn.
2. Fold-pure state vs. POOLED state. The pooled panel puts outcome-fold reviews
   into the features, so any extra apparent skill there is the mechanical
   channel -- the same channel that inflated the self-referential Wave 5 ATT.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def _model(alpha: float):
    """Imputer + scaler + ridge, all fitted inside the fold (no train/test leak)."""
    return make_pipeline(SimpleImputer(strategy="median"),
                         StandardScaler(), Ridge(alpha=alpha))

from src.effect import ope

ROOT = ope.ROOT
OUT = ROOT / "outputs" / "autonomous" / "p4"

ALPHAS = [0.1, 1.0, 10.0, 100.0]


def build_matrix(panel: pd.DataFrame, fold_df: pd.DataFrame, detect: str, out: str,
                 periods: list[str], pooled: bool) -> pd.DataFrame:
    """Feature matrix at (hotel, t) + target = ms_OUT(t+1) - ms_OUT(t)."""
    sn_col = "smoothed_net" if pooled else f"smoothed_net_{detect}"
    hm_col = "has_measurement" if pooled else f"has_measurement_{detect}"

    sn = panel.pivot_table(index=["hotel_id", "period"], columns="aspect",
                           values=sn_col, aggfunc="first").reindex(columns=ope.ASPECTS)
    d = sn.reset_index()
    d["_o"] = ope.period_ord(d["period"])
    d = d.sort_values(["hotel_id", "_o"]).reset_index(drop=True)
    g = d.groupby("hotel_id")
    prev = g[ope.ASPECTS].shift(1)
    for a in ope.ASPECTS:
        d[f"lvl_{a}"] = d[a]
        d[f"chg_{a}"] = d[a] - prev[a]

    f = fold_df[["hotel_id", "period", f"mean_score_{out}", f"score_n_{out}"]].copy()
    f["_o"] = ope.period_ord(f["period"])
    f = f.sort_values(["hotel_id", "_o"]).reset_index(drop=True)
    gf = f.groupby("hotel_id")
    f["y"] = gf[f"mean_score_{out}"].shift(-1) - f[f"mean_score_{out}"]
    f["n_next"] = gf[f"score_n_{out}"].shift(-1)
    f["_onext"] = gf["_o"].shift(-1)
    f = f[(f["_onext"] - f["_o"] == 1)]

    m = d.merge(f[["hotel_id", "period", "y", f"score_n_{out}", "n_next"]],
                on=["hotel_id", "period"], how="inner")
    m = m[m["period"].isin(periods)]
    m = m[(m[f"score_n_{out}"] >= 5) & (m["n_next"] >= 5)]
    return m.dropna(subset=["y"]).reset_index(drop=True)


def evaluate(m: pd.DataFrame, feat: list[str], label: str, seed: int) -> dict:
    X = m[feat].to_numpy(float)
    y = m["y"].to_numpy(float)
    groups = m["hotel_id"].to_numpy()
    if len(np.unique(groups)) < 5:
        return {"error": "too_few_hotels"}

    gkf = GroupKFold(n_splits=5)
    preds = np.zeros_like(y)
    for tr, te in gkf.split(X, y, groups):
        best, best_a = None, None
        # inner split for alpha: reuse the training groups, 3-fold
        inner = GroupKFold(n_splits=3)
        scores = {}
        for a in ALPHAS:
            sse = 0.0
            cnt = 0
            for itr, ite in inner.split(X[tr], y[tr], groups[tr]):
                if len(ite) == 0:
                    continue
                mdl = _model(a)
                mdl.fit(X[tr][itr], y[tr][itr])
                e = y[tr][ite] - mdl.predict(X[tr][ite])
                sse += float((e ** 2).sum())
                cnt += len(ite)
            scores[a] = sse / max(cnt, 1)
        best_a = min(scores, key=scores.get)
        mdl = _model(best_a)
        mdl.fit(X[tr], y[tr])
        preds[te] = mdl.predict(X[te])
        best = best_a
    mse = float(((y - preds) ** 2).mean())
    mse0 = float((y ** 2).mean())          # predict zero
    mse_m = float(((y - y.mean()) ** 2).mean())  # predict the mean
    return {
        "label": label,
        "n": int(len(y)),
        "mse_model": mse,
        "mse_zero": mse0,
        "mse_mean": mse_m,
        "r2_vs_zero": 1.0 - mse / mse0,
        "r2_vs_mean": 1.0 - mse / mse_m,
        "last_alpha": best,
        "corr_pred_true": float(np.corrcoef(preds, y)[0, 1]) if len(y) > 2 else None,
    }


def hotel_level_probe(panel: pd.DataFrame, fold_df: pd.DataFrame) -> dict:
    """Cross-sectional probe: does a hotel's aspect profile (fold A) explain its
    rating LEVEL measured on disjoint reviews (fold B)?

    Quarterly *changes* are close to noise (see the panel probe). A hotel's
    sustained level is a different, much better-powered target, and it is the
    one a diagnosis->prioritisation tool actually needs. It remains
    associational: it says nothing about what happens if the hotel intervenes.
    """
    sn = panel.pivot_table(index=["hotel_id", "period"], columns="aspect",
                           values="smoothed_net_A", aggfunc="first").reindex(columns=ope.ASPECTS)
    prof = sn.groupby("hotel_id").mean()
    cnt = sn.notna().groupby("hotel_id").sum().sum(axis=1)
    prof = prof[cnt >= 5]

    sc = fold_df.groupby("hotel_id").apply(
        lambda g: np.average(g["mean_score_B"], weights=g["score_n_B"].clip(lower=0)),
        include_groups=False,
    ) if False else None
    # weighted mean reviewer score on fold B, computed explicitly (pandas 3 safe)
    rows = []
    for hid, g in fold_df.groupby("hotel_id", sort=False):
        w = g["score_n_B"].to_numpy(float)
        v = g["mean_score_B"].to_numpy(float)
        ok = np.isfinite(v) & (w > 0)
        if ok.sum() == 0:
            continue
        rows.append((hid, float(np.average(v[ok], weights=w[ok])), int(w[ok].sum())))
    tgt = pd.DataFrame(rows, columns=["hotel_id", "ms_B", "n_B"]).set_index("hotel_id")
    tgt = tgt[tgt["n_B"] >= 30]

    d = prof.join(tgt, how="inner")
    X = d[ope.ASPECTS].to_numpy(float)
    y = d["ms_B"].to_numpy(float)
    if len(d) < 50:
        return {"error": "too_few_hotels", "n": int(len(d))}

    kf = GroupKFold(n_splits=5)
    groups = np.arange(len(d))  # one row per hotel -> plain 5-fold
    preds = np.zeros_like(y)
    chosen = []
    for tr, te in kf.split(X, y, groups):
        best_a, best_s = None, None
        for a in ALPHAS:
            mdl = _model(a)
            mdl.fit(X[tr], y[tr])
            e = y[tr] - mdl.predict(X[tr])
            s = float((e ** 2).mean())
            if best_s is None or s < best_s:
                best_s, best_a = s, a
        chosen.append(best_a)
        mdl = _model(best_a)
        mdl.fit(X[tr], y[tr])
        preds[te] = mdl.predict(X[te])

    mse = float(((y - preds) ** 2).mean())
    mse_m = float(((y - y.mean()) ** 2).mean())
    return {
        "n_hotels": int(len(d)),
        "r2_vs_mean": 1.0 - mse / mse_m,
        "rmse": float(np.sqrt(mse)),
        "sd_target": float(y.std(ddof=1)),
        "corr_pred_true": float(np.corrcoef(preds, y)[0, 1]),
        "alphas": chosen,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-reviews", type=int, default=5)
    args = ap.parse_args(argv)

    panel = pd.read_parquet(ope.PANEL)
    fold_df = pd.read_parquet(ope.FOLD)
    periods = [p for p in sorted(panel.loc[panel["period_complete"], "period"].unique())
               if "2016Q1" <= p <= "2017Q1"]

    lvl = [f"lvl_{a}" for a in ope.ASPECTS]
    chg = [f"chg_{a}" for a in ope.ASPECTS]

    out = {"periods": periods, "min_reviews": args.min_reviews, "results": {}}
    for tag, pooled in (("fold_pure", False), ("pooled_state", True)):
        for detect, o in (("A", "B"), ("B", "A")):
            m = build_matrix(panel, fold_df, detect, o, periods, pooled)
            key = f"{tag}_{detect}->{o}"
            res = {}
            res["levels"] = evaluate(m, lvl, "aspect levels only", 1)
            res["levels_changes"] = evaluate(m, lvl + chg, "levels + changes", 1)
            out["results"][key] = res
            print(f"{key}: n={len(m)} "
                  f"R2(levels)={res['levels'].get('r2_vs_zero'):+.4f} "
                  f"R2(levels+chg)={res['levels_changes'].get('r2_vs_zero'):+.4f}")

    out["hotel_level"] = hotel_level_probe(panel, fold_df)
    print(f"hotel-level cross-section: {json.dumps(out['hotel_level'])}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "predictive_probe.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    fp = [v["levels_changes"]["r2_vs_zero"] for k, v in out["results"].items()
          if k.startswith("fold_pure") and "r2_vs_zero" in v["levels_changes"]]
    pp = [v["levels_changes"]["r2_vs_zero"] for k, v in out["results"].items()
          if k.startswith("pooled_state") and "r2_vs_zero" in v["levels_changes"]]
    print(json.dumps({"fold_pure_mean_r2": float(np.mean(fp)) if fp else None,
                      "pooled_mean_r2": float(np.mean(pp)) if pp else None,
                      "mechanical_inflation": (float(np.mean(pp)) - float(np.mean(fp)))
                      if fp and pp else None}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

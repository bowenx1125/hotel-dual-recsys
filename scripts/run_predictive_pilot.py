#!/usr/bin/env python3
"""Predictive pilot on temporal holdout (association only; not causal)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.temporal.io_util import atomic_write_json, atomic_write_text, load_temporal_config


def period_key(p: str) -> tuple:
    y, q = p.split("Q")
    return (int(y), int(q))


def ridge_fit(X, y, l2=1.0):
    # closed form with intercept column already in X
    xtx = X.T @ X
    xtx.flat[:: xtx.shape[0] + 1] += l2
    return np.linalg.solve(xtx, X.T @ y)


def mae(a, b):
    return float(np.mean(np.abs(a - b)))


def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def bootstrap_delta(err_a, err_b, n=500, seed=0):
    rng = np.random.default_rng(seed)
    diffs = []
    nobs = len(err_a)
    for _ in range(n):
        idx = rng.integers(0, nobs, nobs)
        diffs.append(np.mean(err_a[idx]) - np.mean(err_b[idx]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(np.mean(diffs)), float(lo), float(hi)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    root = Path(args.root)
    cfg = load_temporal_config(root)
    feas_path = root / "outputs" / "overnight" / "feasibility" / "feasibility_metrics.json"
    out = root / "outputs" / "overnight" / "predictive_pilot"
    out.mkdir(parents=True, exist_ok=True)
    figdir = out / "figures"
    figdir.mkdir(exist_ok=True)

    if feas_path.exists():
        feas = json.loads(feas_path.read_text())
        verdict = feas.get("verdict", "RED")
    else:
        verdict = "RED"
    if verdict not in cfg["predictive"]["run_if_verdict_in"] and not args.force:
        atomic_write_text(
            out / "PREDICTIVE_REPORT.md",
            f"# PREDICTIVE PILOT SKIPPED\n\nVerdict={verdict}. Gate requires GREEN/AMBER.\n",
        )
        atomic_write_json(out / "metrics.json", {"skipped": True, "verdict": verdict})
        print(json.dumps({"skipped": True, "verdict": verdict}))
        return 0

    q = pd.read_parquet(root / "data" / "processed" / "hotel_aspect_quarter.parquet")
    peers = pd.read_parquet(root / "data" / "processed" / "geo_reference_sets.parquet")
    peer_map = peers.groupby("hotel_id")["peer_hotel_id"].apply(list).to_dict()

    # hotel-period overall score panel
    hp = (
        q.drop_duplicates(["hotel_id", "period"])
        [["hotel_id", "city", "period", "mean_reviewer_score", "total_reviews"]]
        .dropna(subset=["mean_reviewer_score"])
        .copy()
    )
    # own aspect nets: pivot mean smoothed across aspects weighted by mentions
    asp = q.pivot_table(
        index=["hotel_id", "period"],
        columns="aspect",
        values="smoothed_net",
        aggfunc="first",
    ).reset_index()
    hp = hp.merge(asp, on=["hotel_id", "period"], how="left")

    periods = sorted(hp["period"].unique(), key=period_key)
    if len(periods) < 6:
        atomic_write_json(out / "metrics.json", {"skipped": True, "reason": "too_few_periods", "n": len(periods)})
        return 0
    test_periods = set(periods[-2:])
    val_periods = set(periods[-4:-2])
    train_periods = set(periods[:-4])

    # build lag features
    hp = hp.sort_values(["hotel_id", "period"])
    hp["score_lag1"] = hp.groupby("hotel_id")["mean_reviewer_score"].shift(1)
    hp["score_lag2"] = hp.groupby("hotel_id")["mean_reviewer_score"].shift(2)
    hp["own_trend"] = hp["score_lag1"] - hp["score_lag2"]

    # peer mean lag score
    score_map = {(r.hotel_id, r.period): r.mean_reviewer_score for r in hp.itertuples(index=False)}
    peer_state = []
    peer_exp = []
    for r in hp.itertuples(index=False):
        plist = peer_map.get(r.hotel_id, [])
        vals = [score_map[(p, r.period)] for p in plist if (p, r.period) in score_map]
        peer_state.append(float(np.mean(vals)) if vals else np.nan)
        # exposure proxy: share of peers with positive own_trend if available — use score rise vs lag
        # Use contemporaneous peer score relative to their lag — approximate peer improvement share
        imp = 0
        known = 0
        for p in plist:
            if (p, r.period) in score_map:
                # need previous period score
                # find previous period string
                known += 1
        peer_exp.append(np.nan)  # fill below
    hp["peer_mean_score"] = peer_state

    # peer exposure: fraction of peers whose score increased vs prior period
    prev_period = {periods[i]: periods[i - 1] for i in range(1, len(periods))}
    exps = []
    for r in hp.itertuples(index=False):
        prev = prev_period.get(r.period)
        if not prev:
            exps.append(np.nan)
            continue
        plist = peer_map.get(r.hotel_id, [])
        imp = known = 0
        for p in plist:
            if (p, r.period) in score_map and (p, prev) in score_map:
                known += 1
                if score_map[(p, r.period)] - score_map[(p, prev)] >= 0.15:
                    imp += 1
        exps.append((imp / known) if known else np.nan)
    hp["peer_exposure"] = exps

    # target: next quarter score
    hp["y_next"] = hp.groupby("hotel_id")["mean_reviewer_score"].shift(-1)
    # assign next period label for leakage checks
    next_map = {periods[i]: periods[i + 1] for i in range(len(periods) - 1)}
    hp["y_period"] = hp["period"].map(next_map)

    feat_own = ["score_lag1", "own_trend"] + [c for c in hp.columns if c in [
        "location", "cleanliness", "breakfast", "service", "noise", "room", "value"
    ]]
    # Use lag1 score and aspect nets from current period to predict next — OK if we don't use future.
    # For train rows, period in train and y_period in train∪val? Better: features at t predict score at t+1;
    # split by y_period.
    data = hp.dropna(subset=["y_next", "score_lag1"]).copy()

    def split(df):
        tr = df[df["y_period"].isin(train_periods)]
        va = df[df["y_period"].isin(val_periods)]
        te = df[df["y_period"].isin(test_periods)]
        return tr, va, te

    train, val, test = split(data)
    city_means = train.groupby(["city", "period"])["y_next"].mean()
    global_mean = float(train["y_next"].mean())

    def predict_baselines(df):
        # 1 global/city-period mean using training city-period means mapped by city & feature period? use city mean overall
        city_m = train.groupby("city")["y_next"].mean()
        p_city = df["city"].map(city_m).fillna(global_mean).to_numpy()
        p_persist = df["mean_reviewer_score"].to_numpy()  # persistence of current
        p_trend = (df["mean_reviewer_score"] + df["own_trend"].fillna(0)).to_numpy()
        return {
            "city_mean": p_city,
            "persistence": p_persist,
            "own_trend": p_trend,
        }

    def design(df, cols):
        X = df[cols].astype(float).fillna(0.0).to_numpy()
        X = np.concatenate([np.ones((len(df), 1)), X], axis=1)
        y = df["y_next"].to_numpy()
        return X, y

    results = {}
    y_te = test["y_next"].to_numpy()
    base = predict_baselines(test)
    for name, pred in base.items():
        results[name] = {"mae": mae(y_te, pred), "rmse": rmse(y_te, pred)}

    specs = {
        "own_features": feat_own,
        "own_plus_peer_state": feat_own + ["peer_mean_score"],
        "own_plus_peer_exposure": feat_own + ["peer_mean_score", "peer_exposure"],
    }
    preds_out = {"y_true": y_te.tolist()}
    for name, cols in specs.items():
        Xtr, ytr = design(train, cols)
        beta = ridge_fit(Xtr, ytr, l2=5.0)
        Xte, _ = design(test, cols)
        pred = Xte @ beta
        results[name] = {"mae": mae(y_te, pred), "rmse": rmse(y_te, pred)}
        preds_out[name] = pred.tolist()

    # city-wise MAE for best own vs peer exposure
    test = test.copy()
    test["err_persist"] = np.abs(test["y_next"] - test["mean_reviewer_score"])
    Xte, _ = design(test, specs["own_plus_peer_exposure"])
    beta = ridge_fit(*design(train, specs["own_plus_peer_exposure"]), l2=5.0)
    test["pred_peer"] = Xte @ beta
    test["err_peer"] = np.abs(test["y_next"] - test["pred_peer"])
    city_mae = test.groupby("city").agg(mae_persist=("err_persist", "mean"), mae_peer=("err_peer", "mean")).reset_index()
    city_mae.to_csv(out / "city_wise_mae.csv", index=False)

    dmean, dlo, dhi = bootstrap_delta(test["err_persist"].to_numpy(), test["err_peer"].to_numpy())
    peer_beats = results["own_plus_peer_exposure"]["mae"] < results["persistence"]["mae"]

    metrics = {
        "verdict_context": verdict,
        "target": "next_quarter_mean_reviewer_score",
        "train_periods": sorted(train_periods),
        "val_periods": sorted(val_periods),
        "test_periods": sorted(test_periods),
        "n_train": int(len(train)),
        "n_val": int(len(val)),
        "n_test": int(len(test)),
        "models": results,
        "bootstrap_mae_persist_minus_peer": {"mean": dmean, "ci95": [dlo, dhi]},
        "peer_model_improves_on_persistence": peer_beats,
        "claim_level": "predictive_association_only",
        "not_causal": True,
    }
    atomic_write_json(out / "metrics.json", metrics)
    sample = test[["hotel_id", "city", "period", "y_period", "y_next", "mean_reviewer_score"]].head(200)
    sample.to_csv(out / "predictions_sample.csv", index=False)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4))
    names = list(results.keys())
    ax.bar(names, [results[n]["mae"] for n in names], color="#4C78A8")
    ax.set_ylabel("MAE")
    ax.set_title("Temporal holdout MAE (lower better)")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(figdir / "mae_by_model.png", dpi=120)
    plt.close(fig)

    report = f"""# PREDICTIVE PILOT REPORT

## Status

Executed under feasibility verdict **{verdict}**.

## Target

Next-quarter mean reviewer score (hotel-period).

## Split (time-ordered)

- Train y-periods: {sorted(train_periods)}
- Val y-periods: {sorted(val_periods)}
- Test y-periods: {sorted(test_periods)}
- No random row split; no future features.

## Metrics (test MAE / RMSE)

```json
{json.dumps(results, indent=2)}
```

## Peer-aware vs persistence

- Bootstrap mean(MAE_persist - MAE_peer): {dmean:.4f} CI95=[{dlo:.4f}, {dhi:.4f}]
- Peer model improves on persistence: **{peer_beats}**

## Honest conclusion

This is a **predictive association** pilot only.
It does **not** establish causal peer interference.
Do **not** upgrade the Manager Demo evidence level to PREDICTIVE globally.
"""
    atomic_write_text(out / "PREDICTIVE_REPORT.md", report)
    print(json.dumps({"peer_improves": peer_beats, "models": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

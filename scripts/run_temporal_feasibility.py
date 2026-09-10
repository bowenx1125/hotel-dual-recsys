#!/usr/bin/env python3
"""Temporal feasibility audit: review-perceived changes + peer exposure support."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.temporal.gates import classify_gate
from src.temporal.io_util import atomic_write_json, atomic_write_text, load_temporal_config


def period_sort_key(p: str) -> tuple:
    # 2016Q1 or 2016-01
    if "Q" in p:
        y, q = p.split("Q")
        return (int(y), int(q))
    y, m = p.split("-")
    return (int(y), int(m))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args()
    root = Path(args.root)
    cfg = load_temporal_config(root)
    thr = float(cfg["feasibility"]["main_delta_threshold"])
    min_ment = int(cfg["feasibility"]["min_mentions_for_event"])
    min_pre = int(cfg["feasibility"]["min_pre_periods"])
    min_post = int(cfg["feasibility"]["min_post_periods"])

    q = pd.read_parquet(root / "data" / "processed" / "hotel_aspect_quarter.parquet")
    peers = pd.read_parquet(root / "data" / "processed" / "geo_reference_sets.parquet")
    out = root / "outputs" / "overnight" / "feasibility"
    figdir = out / "figures"
    tabdir = out / "tables"
    for d in (out, figdir, tabdir):
        d.mkdir(parents=True, exist_ok=True)

    # valid mention cells
    valid = q[q["total_mentions"] > 0].copy()
    # hotels with enough coverage: >=4 quarters with any reviews
    hotel_periods = q.drop_duplicates(["hotel_id", "period"])
    pph = hotel_periods.groupby("hotel_id")["period"].nunique()
    enough = set(pph[pph >= 4].index)

    # deltas per hotel-aspect
    q = q.sort_values(["hotel_id", "aspect", "period"])
    periods_sorted = sorted(q["period"].unique(), key=period_sort_key)
    period_index = {p: i for i, p in enumerate(periods_sorted)}

    # peer map
    peer_map = peers.groupby("hotel_id")["peer_hotel_id"].apply(list).to_dict()

    # index smoothed nets
    net_idx = {}
    ment_idx = {}
    for row in q.itertuples(index=False):
        key = (row.hotel_id, row.aspect, row.period)
        net_idx[key] = float(row.smoothed_net)
        ment_idx[key] = int(row.total_mentions)

    deltas = []
    for (hid, asp), g in q.groupby(["hotel_id", "aspect"]):
        g = g.sort_values("period", key=lambda s: s.map(period_sort_key))
        periods = g["period"].tolist()
        nets = g["smoothed_net"].tolist()
        ments = g["total_mentions"].tolist()
        city = g["city"].iloc[0]
        for i in range(1, len(periods)):
            # require consecutive period indices
            if period_index[periods[i]] - period_index[periods[i - 1]] != 1:
                continue
            dq = nets[i] - nets[i - 1]
            deltas.append({
                "hotel_id": hid,
                "city": city,
                "aspect": asp,
                "period": periods[i],
                "prev_period": periods[i - 1],
                "delta_q": dq,
                "mentions": ments[i],
                "prev_mentions": ments[i - 1],
                "period_pos": period_index[periods[i]],
                "n_periods_hotel_aspect": len(periods),
            })
    ddf = pd.DataFrame(deltas)
    ddf.to_csv(tabdir / "delta_q_sample.csv", index=False)

    # candidate events at main threshold
    events = []
    for thr_i in cfg["feasibility"]["delta_thresholds"]:
        pass

    cand = ddf[(ddf["delta_q"] >= thr) & (ddf["mentions"] >= min_ment)].copy()
    # edge exclusion + pre/post support
    max_pos = max(period_index.values())
    rows = []
    for row in cand.itertuples(index=False):
        pos = row.period_pos
        # not on edge: need 2 pre and 2 post in global period index
        pre_ok = pos >= min_pre
        post_ok = (max_pos - pos) >= min_post
        # hotel-aspect must have those periods present ideally
        pre_present = sum(
            1 for k in range(1, min_pre + 1)
            if (row.hotel_id, row.aspect, periods_sorted[pos - k]) in net_idx
        )
        post_present = sum(
            1 for k in range(1, min_post + 1)
            if pos + k <= max_pos and (row.hotel_id, row.aspect, periods_sorted[pos + k]) in net_idx
        )
        plist = peer_map.get(row.hotel_id, [])
        improving = 0
        peer_deltas = []
        for pid in plist:
            key = (pid, row.aspect, row.period)
            prev = (pid, row.aspect, row.prev_period)
            if key in net_idx and prev in net_idx:
                pdlt = net_idx[key] - net_idx[prev]
                peer_deltas.append(pdlt)
                if pdlt >= thr:
                    improving += 1
        peer_count = len(peer_deltas)
        exposure = (improving / peer_count) if peer_count else np.nan
        rows.append({
            **row._asdict(),
            "pre_ok_index": pre_ok,
            "post_ok_index": post_ok,
            "pre_present": pre_present,
            "post_present": post_present,
            "has_2pre_2post": pre_present >= min_pre and post_present >= min_post,
            "peer_count": peer_count,
            "improving_peer_count": improving,
            "peer_exposure": exposure,
            "mean_peer_delta": float(np.mean(peer_deltas)) if peer_deltas else np.nan,
            "max_peer_delta": float(np.max(peer_deltas)) if peer_deltas else np.nan,
            "peer_set_available": peer_count > 0,
        })
    edf = pd.DataFrame(rows)
    # final candidate: mentions, not edge-ish, peer set available optional for count but gate uses subsets
    final = edf[
        (edf["pre_ok_index"])
        & (edf["post_ok_index"])
        & (edf["peer_set_available"])
        & (edf["has_2pre_2post"])
    ].copy()
    # Also keep broader candidate set for reporting
    candidate = edf[(edf["pre_ok_index"]) & (edf["post_ok_index"]) & (edf["peer_set_available"])].copy()

    # threshold sensitivity counts
    thr_sens = {}
    for t in cfg["feasibility"]["delta_thresholds"]:
        c = ddf[(ddf["delta_q"] >= t) & (ddf["mentions"] >= min_ment)]
        thr_sens[str(t)] = int(len(c))

    metrics = {
        "main_delta_threshold": thr,
        "min_mentions_for_event": min_ment,
        "hotels_total": int(q["hotel_id"].nunique()),
        "hotels_with_enough_coverage": int(len(enough)),
        "valid_cells": int(len(valid)),
        "cities": int(q["city"].nunique()),
        "quarter_periods": int(q["period"].nunique()),
        "delta_rows": int(len(ddf)),
        "candidate_events_broad": int(len(candidate)),
        "candidate_events": int(len(final)),
        "event_hotels": int(final["hotel_id"].nunique()) if len(final) else 0,
        "event_cities": int(final["city"].nunique()) if len(final) else 0,
        "event_aspects": int(final["aspect"].nunique()) if len(final) else 0,
        "events_exposure_gt0": int(((final["peer_exposure"] > 0) & final["peer_exposure"].notna()).sum()) if len(final) else 0,
        "events_exposure_eq0": int(((final["peer_exposure"] == 0) & final["peer_exposure"].notna()).sum()) if len(final) else 0,
        "frac_events_2pre_2post": float(final["has_2pre_2post"].mean()) if len(final) else 0.0,
        "mean_peer_exposure": float(final["peer_exposure"].mean()) if len(final) else None,
        "threshold_sensitivity_raw_deltas": thr_sens,
        "terminology": {
            "change": "review-perceived aspect change",
            "not": "managerial intervention",
        },
    }

    verdict, reasons = classify_gate(metrics, cfg["feasibility"]["gate"]["green"])
    metrics["verdict"] = verdict
    metrics["verdict_reasons"] = reasons

    # tables
    if len(final):
        final.to_csv(tabdir / "candidate_events.csv", index=False)
        final.groupby("aspect").size().rename("n").reset_index().to_csv(tabdir / "events_by_aspect.csv", index=False)
        final.groupby("city").size().rename("n").reset_index().sort_values("n", ascending=False).to_csv(
            tabdir / "events_by_city.csv", index=False
        )
    pph.reset_index().rename(columns={"period": "n_periods"}).to_csv(tabdir / "periods_per_hotel.csv", index=False)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # figures
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(pph.values, bins=20, color="#4C78A8")
    ax.set_title("Valid periods per hotel")
    ax.set_xlabel("n periods")
    fig.tight_layout()
    fig.savefig(figdir / "periods_per_hotel.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    vc = valid.groupby("city")["hotel_id"].nunique().sort_values(ascending=False).head(15)
    ax.barh(vc.index[::-1], vc.values[::-1], color="#F58518")
    ax.set_title("Hotels with mention cells by city (top 15)")
    fig.tight_layout()
    fig.savefig(figdir / "aspect_coverage_by_city.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    dens = valid.groupby(["period", "aspect"]).size().reset_index(name="n")
    ax.hist(dens["n"], bins=30, color="#54A24B")
    ax.set_title("Hotel-quarter-aspect cell density (mention>0 counts by period×aspect)")
    fig.tight_layout()
    fig.savefig(figdir / "cell_density.png", dpi=120)
    plt.close(fig)

    if len(ddf):
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.hist(ddf["delta_q"].clip(-1, 1), bins=40, color="#E45756")
        ax.axvline(thr, color="black", ls="--", label=f"main thr={thr}")
        ax.set_title("Distribution of review-perceived delta_q (smoothed_net)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(figdir / "delta_q_distribution.png", dpi=120)
        plt.close(fig)

    if len(final):
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.hist(final["peer_exposure"].dropna(), bins=20, color="#B279A2")
        ax.set_title("Peer exposure among candidate events")
        fig.tight_layout()
        fig.savefig(figdir / "peer_exposure_distribution.png", dpi=120)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(7, 4))
        bya = final.groupby("aspect").size()
        ax.bar(bya.index, bya.values, color="#72B7B2")
        ax.set_title("Candidate events by aspect")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        fig.savefig(figdir / "events_by_aspect.png", dpi=120)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(7, 4))
        byc = final.groupby("city").size().sort_values(ascending=False).head(12)
        ax.barh(byc.index[::-1], byc.values[::-1], color="#FF9DA6")
        ax.set_title("Candidate events by city (top 12)")
        fig.tight_layout()
        fig.savefig(figdir / "events_by_city.png", dpi=120)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 3))
    ax.axis("off")
    ax.text(0.5, 0.6, f"FEASIBILITY VERDICT: {verdict}", ha="center", va="center", fontsize=18, fontweight="bold")
    ax.text(0.5, 0.25, "Not a causal claim", ha="center", fontsize=10)
    fig.savefig(figdir / "verdict_summary.png", dpi=120)
    plt.close(fig)

    # threshold sensitivity plot
    fig, ax = plt.subplots(figsize=(6, 4))
    xs = list(thr_sens.keys())
    ys = [thr_sens[x] for x in xs]
    ax.bar(xs, ys, color="#4C78A8")
    ax.set_title("Raw delta count by threshold (sensitivity; main gate fixed)")
    fig.tight_layout()
    fig.savefig(figdir / "threshold_sensitivity.png", dpi=120)
    plt.close(fig)

    atomic_write_json(out / "feasibility_metrics.json", metrics)

    go = f"""# GO / NO-GO

## Verdict: **{verdict}**

Main threshold fixed a priori at **{thr}** (not tuned on outcomes for gate passage).

## Gate metrics

| Metric | Value | GREEN requires |
|---|---:|---|
| Hotels with ≥4 periods | {metrics['hotels_with_enough_coverage']} | ≥500 |
| Valid hotel-quarter-aspect cells (mentions>0) | {metrics['valid_cells']} | ≥20000 |
| Candidate events (strict) | {metrics['candidate_events']} | ≥300 |
| Event hotels | {metrics['event_hotels']} | ≥200 |
| Event cities | {metrics['event_cities']} | ≥4 |
| Event aspects | {metrics['event_aspects']} | ≥4 |
| Events exposure>0 | {metrics['events_exposure_gt0']} | ≥100 |
| Events exposure=0 | {metrics['events_exposure_eq0']} | ≥100 |
| Frac with 2pre+2post | {metrics['frac_events_2pre_2post']:.3f} | ≥0.70 |

## Reasons

{chr(10).join('- ' + r for r in reasons)}

## What may proceed

- DESCRIPTIVE manager diagnosis (already)
- Measurement / peer-relative diagnosis paper track
{"- Predictive association pilot on temporal holdout" if verdict in ("GREEN", "AMBER") else "- Predictive pilot skipped under RED"}
{"- Exploratory event-study design work (not confirmatory)" if verdict == "GREEN" else "- Confirmatory event-study / causal peer-interference claims: STOP"}

## What must stop

- Causal effect / ROI / demand-lift wording
- Calling delta_q a managerial intervention
- Calling geo neighbors validated competitors
"""
    atomic_write_text(out / "GO_NO_GO.md", go)

    report = f"""# TEMPORAL FEASIBILITY REPORT

## Purpose

Assess whether review-perceived aspect changes and peer-exposure variation support further temporal research.
**Not** hunting for significant p-values. **Not** causal identification.

## Data

- Quarterly weak-labeled panel
- Geo reference sets (k=10, same city)

## Change definition

`delta_q = smoothed_net(t) - smoothed_net(t-1)` on consecutive quarters.
Term: **review-perceived aspect change**.

## Results summary

```json
{json.dumps(metrics, indent=2)}
```

## Verdict

**{verdict}**

See `GO_NO_GO.md`.
"""
    atomic_write_text(out / "TEMPORAL_FEASIBILITY_REPORT.md", report)
    print(json.dumps({"verdict": verdict, **{k: metrics[k] for k in [
        "candidate_events", "event_hotels", "event_cities", "events_exposure_gt0",
        "events_exposure_eq0", "valid_cells", "hotels_with_enough_coverage"
    ]}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

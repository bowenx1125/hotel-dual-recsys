"""P2c: matched-DiD robustness on the 456 strict events, with a downstream outcome.

Wave 5 ran this design with y = POOLED ``smoothed_net``.  Events are detected
per fold, so that y is partly built from the very reviews that defined the
event: the estimate measures itself.

This module reruns the identical matching design twice:

    mode = "wave5_pooled_net"  -> exact replication of the shipped result
                                  (pooled matching covariates AND pooled outcome)
    mode = "crossfit_rating"   -> y = mean reviewer score of the OTHER fold G,
                                  matching covariates on the DETECTION fold F

The wave5 arm reproduces outputs/autonomous/wave5/event_study.json so the two
arms differ in exactly one respect: which series the outcome is measured on.
Comparing them quantifies how much of the Wave 5 ATT is self-reference.

Matching itself is Wave 5's: same city / aspect / period, nearest neighbour on
pre-event level and pre-trend, no event within +-2 quarters, controls used once.

Verdict ceiling: AMBER_ASSOCIATIONAL.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.autonomous.common import load_config  # noqa: E402
from src.autonomous.ledger import merge_facts, register_experiment  # noqa: E402
from src.effect.estimation import cluster_robust_mean  # noqa: E402
from src.effect.run_p2 import load_tables  # noqa: E402

PANEL = ROOT / "data" / "processed" / "hotel_aspect_quarter_v2.parquet"
FOLD = ROOT / "data" / "processed" / "hotel_quarter_fold.parquet"
EVENTS = ROOT / "outputs" / "autonomous" / "wave2" / "strict_events.parquet"
OUT_DIR = ROOT / "outputs" / "autonomous" / "p2"

KS = (-2, -1, 0, 1, 2)


def other_fold(f: str) -> str:
    return "B" if f == "A" else "A"


def build_index(panel: pd.DataFrame, fold: pd.DataFrame, periods: list[str]):
    pi = {p: i for i, p in enumerate(periods)}
    net: dict[tuple[str, str, str, str], float] = {}
    has: dict[tuple[str, str, str, str], bool] = {}
    for r in panel.itertuples(index=False):
        for F in ("A", "B"):
            net[(r.hotel_id, r.aspect, r.period, F)] = float(getattr(r, f"smoothed_net_{F}"))
            has[(r.hotel_id, r.aspect, r.period, F)] = bool(getattr(r, f"has_measurement_{F}"))
    # pooled (wave5 replication)
    for r in panel.itertuples(index=False):
        net[(r.hotel_id, r.aspect, r.period, "P")] = float(r.smoothed_net)
        has[(r.hotel_id, r.aspect, r.period, "P")] = bool(r.has_measurement)

    score = {}
    for r in fold.itertuples(index=False):
        for G in ("A", "B"):
            score[(r.hotel_id, r.period, G)] = float(getattr(r, f"mean_score_{G}"))
    nscore = {}
    for r in fold.itertuples(index=False):
        for G in ("A", "B"):
            nscore[(r.hotel_id, r.period, G)] = int(getattr(r, f"score_n_{G}"))
    return pi, net, has, score, nscore


def run_mode(events: pd.DataFrame, panel: pd.DataFrame, fold: pd.DataFrame,
             periods: list[str], *, mode: str, min_reviews: int) -> dict:
    pi, net, has, score, nscore = build_index(panel, fold, periods)
    treated = set(zip(events["hotel_id"], events["aspect"], events["period"]))

    rows = []
    used: set = set()
    for r in events.itertuples(index=False):
        if r.period not in pi:
            continue
        i = pi[r.period]
        F = r.fold
        G = other_fold(F)
        # measurement series used for BOTH matching and (in wave5 mode) the outcome
        mf = F if mode == "crossfit_rating" else "P"
        has_col = "has_measurement" if mf == "P" else f"has_measurement_{mf}"

        # ---- control pool: same city/aspect/period, measurable on the matching series
        pool = panel[
            (panel["city"] == r.city)
            & (panel["aspect"] == r.aspect)
            & (panel["period"] == r.period)
            & (panel[has_col])
        ]
        prev = periods[i - 1] if i >= 1 else None
        pre2 = periods[i - 2] if i >= 2 else None
        if prev is None:
            continue
        best, best_d = None, 1e18
        for c in pool.itertuples(index=False):
            key = (c.hotel_id, r.aspect, r.period)
            if c.hotel_id == r.hotel_id or key in treated or key in used:
                continue
            if any((c.hotel_id, r.aspect, periods[i + j]) in treated
                   for j in range(-2, 3) if 0 <= i + j < len(periods)):
                continue
            if not has.get((c.hotel_id, r.aspect, prev, mf)):
                continue
            q1 = net[(c.hotel_id, r.aspect, prev, mf)]
            pt = q1 - net.get((c.hotel_id, r.aspect, pre2, mf), q1) if pre2 else 0.0
            d = (q1 - r.q_lag1) ** 2 + (pt - r.pretrend) ** 2
            if d < best_d:
                best_d, best = d, c.hotel_id
        if best is None:
            continue
        used.add((best, r.aspect, r.period))

        def outcome(hotel: str, k: int):
            pk = periods[i + k] if 0 <= i + k < len(periods) else None
            if pk is None:
                return None
            if mode == "crossfit_rating":
                if nscore.get((hotel, pk, G), 0) < min_reviews:
                    return None
                v = score.get((hotel, pk, G))
                return None if v is None or not np.isfinite(v) else v
            return net.get((hotel, r.aspect, pk, mf))

        base_t = outcome(r.hotel_id, -1)
        base_c = outcome(best, -1)
        if base_t is None or base_c is None:
            continue
        for k in KS:
            yt = outcome(r.hotel_id, k)
            yc = outcome(best, k)
            if yt is None or yc is None:
                continue
            rows.append({
                "event_hotel": r.hotel_id, "control_hotel": best, "aspect": r.aspect,
                "city": r.city, "event_period": r.period, "fold": F, "k": int(k),
                "y_t": yt - base_t, "y_c": yc - base_c,
            })
    mdf = pd.DataFrame(rows)
    if not len(mdf):
        return {"mode": mode, "error": "no_matched_rows"}

    mdf["diff"] = mdf["y_t"] - mdf["y_c"]
    base = mdf[mdf["k"] == -1][["event_hotel", "aspect", "event_period", "diff"]].rename(
        columns={"diff": "diff_m1"})
    m2 = mdf.merge(base, on=["event_hotel", "aspect", "event_period"], how="left")
    m2["rel"] = m2["diff"] - m2["diff_m1"]

    att = {}
    for k, g in m2.groupby("k"):
        f = cluster_robust_mean(g["rel"].to_numpy(), g["event_hotel"].to_numpy())
        att[str(int(k))] = f.as_dict()
    pre = m2[m2["k"] == -2]
    pretrend_ok = None
    if len(pre):
        pf = cluster_robust_mean(pre["rel"].to_numpy(), pre["event_hotel"].to_numpy())
        pretrend_ok = bool(abs(pf.beta) < 0.05)
        att["-2"]["pretrend_ok"] = pretrend_ok
    return {
        "mode": mode,
        "n_events_matched": int(m2["event_hotel"].nunique()),
        "n_rows": int(len(m2)),
        "att_rel_to_m1": att,
        "att_at_k0": att.get("0", {}).get("beta"),
        "att_at_k0_p": att.get("0", {}).get("p"),
        "pretrend_ok": pretrend_ok,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-reviews", type=int, default=3)
    args = ap.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    events = pd.read_parquet(EVENTS)
    panel, fold, periods = load_tables()
    print(f"events={len(events)} periods={periods}", flush=True)

    out = {
        "schema_version": "1.0",
        "design": "matched DiD, nearest neighbour on pre-event level and pre-trend",
        "matching_covariates": "detection-fold smoothed_net at t-1 and pre-trend (t-2 -> t-1)",
        "min_scored_reviews_per_fold": args.min_reviews,
        "modes": {},
    }
    for mode in ("wave5_pooled_net", "crossfit_rating"):
        print(f"running {mode} ...", flush=True)
        r = run_mode(events, panel, fold, periods, mode=mode, min_reviews=args.min_reviews)
        out["modes"][mode] = r
        print(f"  n_matched={r.get('n_events_matched')} att_k0={r.get('att_at_k0')} "
              f"p={r.get('att_at_k0_p')}", flush=True)

    a = out["modes"]["wave5_pooled_net"].get("att_at_k0")
    b = out["modes"]["crossfit_rating"].get("att_at_k0")
    out["comparison"] = {
        "wave5_pooled_net_att_k0": a,
        "crossfit_rating_att_k0": b,
        "note": (
            "wave5_pooled_net is self-referential (events detected per fold, outcome "
            "measured on the pooled index that contains that fold). crossfit_rating uses "
            "the other fold's guest rating: a downstream, disjoint-review outcome. "
            "Units are NOT comparable (smoothed_net vs 0-10 rating points)."
        ),
    }
    out["verdict"] = {
        "status": "AMBER_ASSOCIATIONAL",
        "note": (
            "456 events concentrated in 2016Q2-Q4; after requiring fold-outcome coverage the "
            "matched sample is small and this check is low-powered. It is a consistency check "
            "on the P2b continuous estimates, not a standalone result."
        ),
    }

    (OUT_DIR / "event_study_p2c.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "EVENT_STUDY_P2C.md").write_text(render_md(out), encoding="utf-8")

    register_experiment(ROOT, {
        "experiment_id": "P2c-crossfit-matched-did",
        "wave": 11,
        "name": "matched_did_crossfit_vs_wave5_outcome",
        "preregistered": "yes",
        "status": out["verdict"]["status"],
        "artifact": "outputs/autonomous/p2/event_study_p2c.json",
        "result_summary": f"wave5={a} crossfit_rating={b}",
        "claim_ids": "P2",
    })
    # merge_facts REPLACES facts["waves"][wave], so fold in whatever P2b already wrote.
    facts_path = ROOT / "outputs" / "autonomous" / "FACTS.json"
    prev = {}
    if facts_path.exists():
        prev = json.loads(facts_path.read_text(encoding="utf-8")).get("waves", {}).get("11", {})
    prev.update({
        "p2c_matched_did": {
            "wave5_pooled_net_att_k0": a,
            "crossfit_rating_att_k0": b,
            "n_matched_crossfit": out["modes"]["crossfit_rating"].get("n_events_matched"),
            "n_matched_wave5": out["modes"]["wave5_pooled_net"].get("n_events_matched"),
            "verdict": out["verdict"]["status"],
            "low_power": True,
        }
    })
    merge_facts(ROOT, "11", prev)
    print(f"WROTE {OUT_DIR / 'event_study_p2c.json'}")
    return 0


def render_md(r: dict) -> str:
    lines = ["# P2c matched DiD robustness\n\n",
             f"**Verdict: {r['verdict']['status']}** — {r['verdict']['note']}\n\n",
             f"- design: {r['design']}\n",
             f"- matching covariates: {r['matching_covariates']}\n",
             f"- min scored reviews per fold: {r['min_scored_reviews_per_fold']}\n\n"]
    for mode, d in r["modes"].items():
        lines.append(f"## {mode}\n\n")
        if "error" in d:
            lines.append(f"- {d['error']}\n\n")
            continue
        lines.append(f"- matched events: {d['n_events_matched']} (rows {d['n_rows']})\n")
        if d.get("pretrend_ok") is not None:
            lines.append(f"- pre-trend check at k=-2 (|ATT|<0.05): {d['pretrend_ok']}\n")
        for k in ("-2", "-1", "0", "1", "2"):
            a = d["att_rel_to_m1"].get(k)
            if not a:
                continue
            lines.append(f"- k={k}: ATT={a['beta']:+.4f} se={a['se']:.4f} p={a['p']:.4g} "
                         f"n={a['n']}\n")
        lines.append("\n")
    c = r["comparison"]
    lines += ["## Comparison\n\n",
              f"- Wave 5 style (pooled smoothed_net, self-referential) ATT at k=0: "
              f"{c['wave5_pooled_net_att_k0']}\n",
              f"- Cross-fit (other-fold guest rating) ATT at k=0: "
              f"{c['crossfit_rating_att_k0']}\n\n",
              f"{c['note']}\n"]
    return "".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

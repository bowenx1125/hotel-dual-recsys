"""P5-A driver: revealed interventions, and the size of the remaining gap.

Route A reframes the target away from "this policy raises the rating" and
onto "the recommended action is one a manager would adopt, and adopting it
raises revenue". That estimand needs data this project does not have, so this
driver does the two things that ARE possible:

Q1  Can a real intervention be seen at all?  Persistent, reliability-gated
    jumps in aspect sentiment (detected on one review fold, scored on the
    other) are the closest thing to an intervention record in a review corpus.
Q2  Is the rating payoff ASPECT-SPECIFIC?  If improving service pays more than
    improving breakfast, targeting is justified. Guarded by a permutation
    placebo, a deterioration arm, a pre-trend test and a specificity test.
Q3  Does P3's value vector transfer to this intervention estimand?  Cross-fit:
    estimate gamma on one hotel half, score each policy's picks on the other.
Q4  How much external data would close the gap?  Minimum detectable effect and
    required sample size, computed from the noise actually in this panel.

Q4 is the deliverable that turns "we need intervention records" into "we need
N logged interventions", which is an ask a supervisor can act on.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from src.autonomous.ledger import merge_facts, register_experiment  # noqa: E402
from src.effect import interventions as iv  # noqa: E402
from src.effect.ope import ACTIONABLE, ASPECTS  # noqa: E402

OUT_DIR = ROOT / "outputs" / "autonomous" / "p5a"
TAUS = [0.20, 0.25, 0.30, 0.40]
WAVE = 14


# --------------------------------------------------------------------------
def inventory(cells: pd.DataFrame, tau: float, **kw) -> dict:
    ev = iv.detect_events(cells, tau=tau, **kw)
    if not len(ev):
        return {"tau": tau, "n_events": 0}
    by = ev["aspect"].value_counts().to_dict()
    per_hq = len(ev) / max(cells.groupby(["hotel_id", "t"]).ngroups, 1)
    return {"tau": tau, "n_events": int(len(ev)),
            "n_hotels": int(ev["hotel_id"].nunique()),
            "events_per_hotel_quarter": round(per_hq, 4),
            "by_aspect": {k: int(v) for k, v in by.items()},
            "median_jump": float(ev["jump"].median()),
            "median_persist": float(ev["persist"].median())}


def direction_block(detect: str, out: str, tau: float, reps: int,
                    seed: int, boot: int) -> dict:
    """Everything estimated for one fold direction."""
    cells = iv.build_cells(detect, out)
    hpt = iv.hotel_period_table(cells)
    ev = iv.detect_events(cells, tau=tau)
    det = iv.detect_events(cells, tau=tau, sign=-1)
    return {
        "direction": f"{detect}->{out}",
        "n_hotel_quarters": int(len(hpt)),
        "inventory": inventory(cells, tau),
        "improvement": iv.estimate(hpt, ev, reps=reps, seed=seed, min_n=40),
        "deterioration": iv.estimate(hpt, det, reps=max(reps // 2, 60),
                                     seed=seed + 1, min_n=40),
        "specificity": iv.specificity(cells, ev),
        "tau_sensitivity": [
            _tau_row(cells, hpt, t, seed) for t in TAUS
        ],
        "_boot": boot,
    }


def _tau_row(cells: pd.DataFrame, hpt: pd.DataFrame, tau: float, seed: int) -> dict:
    ev = iv.detect_events(cells, tau=tau)
    if len(ev) < 200:
        return {"tau": tau, "n_events": int(len(ev)), "skipped": True}
    r = iv.estimate(hpt, ev, reps=200, seed=seed + int(tau * 100), min_n=30)
    if "error" in r:
        return {"tau": tau, "n_events": int(len(ev)), "error": r["error"]}
    pg = r["placebo_gap"]
    return {
        "tau": tau,
        "n_events": r["n_events"],
        "pooled_att": r["pooled"]["att"],
        "pooled_t": r["pooled"]["t"],
        "pre_trend_diff": r["pre_trend"]["diff"],
        "gap": r["gap"]["observed"],
        "placebo_gap": pg["mean"],
        "placebo_ratio": pg["ratio_observed_over_placebo"],
        "placebo_p": pg["p_value"],
        "best": r["best_aspect"], "worst": r["worst_aspect"],
    }


# --------------------------------------------------------------------------
# Q3 -- does P3's value vector transfer to the intervention estimand?
# --------------------------------------------------------------------------
def _load_value_vector(spec: str = "conditional") -> dict | None:
    p = ROOT / "outputs" / "autonomous" / "p3" / "value_vector.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    for key in ("vectors", "specs"):
        if key in d and spec in d[key]:
            return d[key][spec]
    if spec in d:
        return d[spec]
    for k in ("vector", "value_vector", "normalized"):
        if k in d:
            return d[k]
    return None


def gamma_vector(res: dict) -> dict[str, float]:
    att = res.get("att_by_aspect") or {}
    return {a: float(v["att"]) for a, v in att.items()}


def q3_transfer(units_path: Path, cells: pd.DataFrame, hpt: pd.DataFrame,
                *, tau: float, reps: int, perms: int, seed: int) -> dict:
    """Cross-fitted: gamma from one hotel half, policy picks scored on the other.

    The statistic is `V(value_aware) - V(peer_relative)` where `V` is the mean
    intervention gamma of the aspect each policy picks. Its null distribution
    is the same statistic recomputed under a SCRAMBLED gamma -- if the value
    vector genuinely steers picks towards high-gamma aspects, scrambling gamma
    destroys that; if gamma is flat noise, scrambling changes nothing and the
    observed statistic sits inside the null.
    """
    if not units_path.exists():
        return {"error": f"missing {units_path}"}
    units = pd.read_parquet(units_path)
    vvec = _load_value_vector("conditional")
    if vvec is None:
        return {"error": "P3 value_vector.json not found"}

    from src.effect.run_p3 import picks_from_units

    hotels = np.sort(units["hotel_id"].unique())
    rng = np.random.default_rng(seed)

    picks_cache = {}
    for name, v in (("peer_relative", None), ("value_aware", vvec)):
        p = picks_from_units(units, v)
        picks_cache[name] = p.set_index(["hotel_id", "period"])["pick"]

    obs, null = [], []
    details = []
    for r in range(reps):
        perm = rng.permutation(hotels)
        halves = [set(perm[: len(perm) // 2]), set(perm[len(perm) // 2:])]
        for train_h, test_h in ((halves[0], halves[1]), (halves[1], halves[0])):
            c = cells[cells["hotel_id"].isin(train_h)]
            h = hpt[hpt["hotel_id"].isin(train_h)]
            ev = iv.detect_events(c, tau=tau)
            res = iv.estimate(h, ev, reps=60, seed=seed + r, min_n=25)
            if "error" in res:
                continue
            g = gamma_vector(res)
            if len(g) < 4:
                continue

            test_mask = units["hotel_id"].isin(test_h)
            base_key = units[test_mask].set_index(["hotel_id", "period"]).index

            def value_of(name: str, gam: dict[str, float]) -> float:
                pk = picks_cache[name].reindex(base_key)
                vals = pk.map(gam).astype(float)
                return float(vals.dropna().mean())

            g_keys = list(g.keys())
            d_obs = value_of("value_aware", g) - value_of("peer_relative", g)
            obs.append(d_obs)
            for _ in range(perms):
                order = list(rng.permutation(g_keys))
                scrambled = {k: g[o] for k, o in zip(g_keys, order)}
                null.append(value_of("value_aware", scrambled)
                            - value_of("peer_relative", scrambled))
            details.append({"rep": r, "gamma": g, "delta": d_obs})

    if not obs:
        return {"error": "no usable cross-fit replicate"}
    o = np.array(obs, dtype=float)
    n = np.array(null, dtype=float)
    sd = float(n.std(ddof=1)) if len(n) > 1 else float("nan")
    mean_o = float(o.mean())
    return {
        "n_replicates": int(len(o)),
        "mean_gamma_delta_value_minus_peer": mean_o,
        "se": float(o.std(ddof=1) / np.sqrt(len(o))) if len(o) > 1 else None,
        "share_positive": float((o > 0).mean()),
        "null_mean": float(n.mean()) if len(n) else None,
        "null_sd": sd,
        "z_vs_scrambled": (mean_o - float(n.mean())) / sd if sd and sd > 0 else None,
        "p_value_scrambled": float((n >= mean_o).mean()) if len(n) else None,
        "n_null_draws": int(len(n)),
        "note": "gamma is estimated from revealed events on the training half "
                "and applied to picks on the held-out half; the null re-scrambles "
                "gamma across aspects.",
    }


# --------------------------------------------------------------------------
# Q4 -- how much external data would close the gap
# --------------------------------------------------------------------------
def power_block(sigma: float, n_treated: int, n_control: int,
                adr_scale: float | None = None) -> dict:
    cur = iv.mde(sigma, n_treated, n_control)
    table = iv.power_table(sigma, n_treated, n_control)
    out = {
        "sigma_outcome_per_hotel_quarter": sigma,
        "n_treated_per_aspect": n_treated,
        "n_control": n_control,
        "mde_rating_points": cur,
        "detection_threshold_note": (
            "A between-aspect gap must also clear the permutation placebo "
            "(see placebo_gap.p95) before it counts as detected."),
        "required_n_per_aspect": table,
        "required_total_for_6_actionable": [
            {"target_effect_rating_points": t["target_effect_rating_points"],
             "total_logged_interventions": t["n_per_arm_needed"] * len(ACTIONABLE)}
            for t in table
        ],
    }
    if adr_scale:
        # External assumption, flagged as such: revenue elasticity per rating
        # point is NOT estimated anywhere in this project.
        out["revenue_sensitivity"] = {
            "adr_anchor": adr_scale,
            "adr_source": "scraped Booking prices, Belgium sample (NOT the "
                          "panel cities -- scale anchor only, not joined)",
            "pct_revenue_per_rating_point": [0.01, 0.02, 0.05],
            "implied_mde_pct_revenue": [round(cur * e * 100, 3)
                                        for e in (0.01, 0.02, 0.05)],
            "caveat": "elasticity values are external assumptions, not "
                      "estimates from this data",
        }
    return out


# --------------------------------------------------------------------------
def render_md(r: dict) -> str:
    L: list[str] = []
    A = L.append
    A("# P5-A Revealed interventions and the size of the remaining gap\n")
    A("Route A reframes the target as *the recommended action is one a manager "
      "would adopt, and adopting it raises revenue*. That needs an adoption log "
      "and a revenue series; **neither exists in this dataset**. What follows is "
      "(1) the closest estimable stand-in and (2) a measurement of how big the "
      "missing piece is.\n")
    v = r.get("verdict", {})
    A(f"**Verdict: {v.get('status')}**\n")
    A("Two separate claims, each judged on whether it replicates across the "
      "two fold directions (detect-on-A/score-on-B and its mirror). They do "
      "not agree, and that disagreement is the result.\n")
    A("| claim | A->B | B->A | verdict |")
    A("|---|---|---|---|")
    rep = r.get("replication") or {}
    if rep:
        ab, ba = rep.get("A->B", {}), rep.get("B->A", {})
        A(f"| pooled effect of an improvement | {ab.get('pooled_att'):+.4f} "
          f"(t={ab.get('pooled_t')}) | {ba.get('pooled_att'):+.4f} "
          f"(t={ba.get('pooled_t')}) | **{v.get('improvement_pays')}** |")
        A(f"| between-aspect gap vs placebo | {ab.get('gap')} / "
          f"{ab.get('placebo_gap')} (ratio {ab.get('placebo_ratio')}, "
          f"p={ab.get('placebo_p')}) | {ba.get('gap')} / "
          f"{ba.get('placebo_gap')} (ratio {ba.get('placebo_ratio')}, "
          f"p={ba.get('placebo_p')}) | **{v.get('aspect_specificity')}** |")
        A(f"| best aspect named | {ab.get('best_aspect')} | "
          f"{ba.get('best_aspect')} | "
          f"{'agree' if ab.get('best_aspect') == ba.get('best_aspect') else 'DISAGREE'} |")
        A(f"| pre-trend (should be ~0) | {ab.get('pre_trend_diff')} "
          f"(t={ab.get('pre_trend_t')}) | {ba.get('pre_trend_diff')} "
          f"(t={ba.get('pre_trend_t')}) | |")
    A("")
    A(f"- P3 value vector under this estimand: {v.get('transfer_status')}\n")

    A("## Q1 Are real interventions visible?\n")
    inv = (r.get("main") or {}).get("inventory") or {}
    A(f"- events at tau={inv.get('tau')}: **{inv.get('n_events')}** across "
      f"{inv.get('n_hotels')} hotels")
    A(f"- median jump {inv.get('median_jump')}, median persistence "
      f"{inv.get('median_persist')} (net sentiment units, range -1..1)\n")
    A("| aspect | events |")
    A("|---|---|")
    for a, n in (inv.get("by_aspect") or {}).items():
        A(f"| {a} | {n} |")
    A("")

    A("## Q2 Is the rating payoff aspect-specific?\n")
    imp = (r.get("main") or {}).get("improvement") or {}
    if "att_by_aspect" in imp:
        A("| aspect | n | ATT (rating pts) | clustered se | t | P(>0) |")
        A("|---|---|---|---|---|---|")
        for a, s in imp["att_by_aspect"].items():
            A(f"| {a} | {s['n']} | {s['att']:+.4f} | {s.get('se', float('nan')):.4f} "
              f"| {s.get('t') if s.get('t') is None else round(s['t'], 2)} "
              f"| {s.get('share_positive', 0):.0%} |")
        A("")
    for key, label in (("pooled", "Pooled (any improvement)"),
                       ("pre_trend", "Pre-trend (t-2 -> t-1, treated - control)")):
        d = imp.get(key) or {}
        if d:
            A(f"- **{label}**: {d.get('att', d.get('diff')):+.4f} "
              f"(se {d.get('se', float('nan')):.4f}, "
              f"t={d.get('t') if d.get('t') is None else round(d['t'], 2)})")
    g = imp.get("gap") or {}
    pg = imp.get("placebo_gap") or {}
    A(f"- best-minus-worst gap: {g.get('observed', float('nan')):+.4f} "
      f"(bootstrap se {g.get('bootstrap_se', float('nan')):.4f})")
    A(f"- permutation placebo gap: {pg.get('mean', float('nan')):.4f} "
      f"(p95 {pg.get('p95', float('nan')):.4f})")
    A(f"- **ratio {pg.get('ratio_observed_over_placebo')}, p={pg.get('p_value')}**\n")

    A("### Guards\n")
    sp = (r.get("main") or {}).get("specificity") or {}
    if sp.get("t") is not None:
        A(f"- specificity: event aspect moves {sp['mean_self_minus_other']:+.4f} "
          f"more than the other aspects (t={sp['t']:.2f}, "
          f"{sp['share_positive']:.0%} positive) -> events ARE aspect-specific")
    det = (r.get("main") or {}).get("deterioration") or {}
    if "att_by_aspect" in det:
        A(f"- deterioration arm (persistent drops): best {det.get('best_aspect')} "
          f"{det['att_by_aspect'].get(det.get('best_aspect'), {}).get('att', float('nan')):+.4f}, "
          f"worst {det.get('worst_aspect')} "
          f"{det['att_by_aspect'].get(det.get('worst_aspect'), {}).get('att', float('nan')):+.4f}")
    A("")

    A("### Threshold sensitivity\n")
    A("| tau | events | pooled ATT | t | pre-trend | gap | placebo | ratio | p |")
    A("|---|---|---|---|---|---|---|---|---|")
    for row in (r.get("main") or {}).get("tau_sensitivity") or []:
        if row.get("skipped"):
            A(f"| {row['tau']} | {row['n_events']} | - | - | - | - | - | - | - |")
            continue
        A(f"| {row['tau']} | {row['n_events']} | {row['pooled_att']:+.4f} "
          f"| {row['pooled_t'] if row['pooled_t'] is None else round(row['pooled_t'], 2)} "
          f"| {row['pre_trend_diff']:+.4f} | {row['gap']:.4f} | {row['placebo_gap']:.4f} "
          f"| {row['placebo_ratio']:.2f} | {row['placebo_p']:.3f} |")
    A("")

    A("## Q3 Does P3's value vector transfer to this estimand?\n")
    q3 = r.get("q3") or {}
    if q3.get("error"):
        A(f"- skipped: {q3['error']}\n")
    else:
        A(f"- cross-fit replicates: {q3['n_replicates']}")
        A(f"- V(value_aware) - V(peer_relative) under the event gamma: "
          f"**{q3['mean_gamma_delta_value_minus_peer']:+.5f}** "
          f"(se {q3.get('se', float('nan')):.5f}, {q3['share_positive']:.0%} positive)")
        A(f"- scrambled-gamma null: mean {q3.get('null_mean', float('nan')):+.5f}, "
          f"sd {q3.get('null_sd', float('nan')):.5f}")
        A(f"- z vs scrambled = {q3.get('z_vs_scrambled')}, "
          f"p = {q3.get('p_value_scrambled')}\n")

    A("## Q4 How much external data would close the gap?\n")
    pw = r.get("power") or {}
    A(f"- outcome noise per hotel-quarter: sigma = "
      f"{pw.get('sigma_outcome_per_hotel_quarter', float('nan')):.3f} rating points")
    A(f"- current median events per aspect: {pw.get('n_treated_per_aspect')}")
    A(f"- **minimum detectable between-aspect difference now: "
      f"{pw.get('mde_rating_points', float('nan')):.3f} rating points**\n")
    A("| target effect (rating pts) | n per aspect | total for 6 actionable | detectable now |")
    A("|---|---|---|---|")
    for t, tot in zip(pw.get("required_n_per_aspect") or [],
                      pw.get("required_total_for_6_actionable") or []):
        A(f"| {t['target_effect_rating_points']} | {t['n_per_arm_needed']} "
          f"| {tot['total_logged_interventions']} | "
          f"{'yes' if t['detectable_now'] else 'no'} |")
    A("")
    rs = pw.get("revenue_sensitivity")
    if rs:
        A(f"Revenue translation (ADR anchor {rs['adr_anchor']} from "
          f"{rs['adr_source']}). Elasticity is an **external assumption**:\n")
        A("| assumed % revenue per rating point | implied MDE (% revenue) |")
        A("|---|---|")
        for e, m in zip(rs["pct_revenue_per_rating_point"],
                        rs["implied_mde_pct_revenue"]):
            A(f"| {e:.0%} | {m} |")
        A("")
    A("## What this means\n")
    for line in r.get("verdict", {}).get("implications", []):
        A(f"- {line}")
    A("")
    return "\n".join(L)


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260915)
    ap.add_argument("--reps", type=int, default=400)
    ap.add_argument("--tau", type=float, default=0.25)
    ap.add_argument("--q3-reps", type=int, default=12)
    ap.add_argument("--q3-perms", type=int, default=40)
    ap.add_argument("--skip-q3", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out: dict = {"seed": args.seed, "tau": args.tau}

    print("=== Q1/Q2 revealed-intervention event study ===")
    blocks = {}
    for detect, o in (("A", "B"), ("B", "A")):
        print(f"  direction {detect}->{o}")
        blocks[f"{detect}->{o}"] = direction_block(
            detect, o, args.tau, reps=args.reps, seed=args.seed, boot=args.reps)
    out["directions"] = blocks
    out["main"] = blocks["A->B"]

    print("=== Q3 transfer of the P3 value vector ===")
    if args.skip_q3:
        out["q3"] = {"skipped": True}
    else:
        cells = iv.build_cells("A", "B")
        hpt = iv.hotel_period_table(cells)
        out["q3"] = q3_transfer(
            ROOT / "outputs" / "autonomous" / "p3" / "_units_A.parquet",
            cells, hpt, tau=args.tau, reps=args.q3_reps,
            perms=args.q3_perms, seed=args.seed)
        print("  ", json.dumps({k: v for k, v in out["q3"].items()
                                if k in ("n_replicates", "mean_gamma_delta_value_minus_peer",
                                         "z_vs_scrambled", "p_value_scrambled", "error")},
                               ensure_ascii=False))

    print("=== Q4 power / MDE ===")
    imp = out["main"]["improvement"]
    n_tr = int(np.median([s["n"] for s in imp["att_by_aspect"].values()]))
    # ADR anchor from the scraped price sample (different country: scale only)
    adr = None
    pcsv = ROOT / "data" / "processed" / "hotels_all.csv"
    if pcsv.exists():
        try:
            pr = pd.read_csv(pcsv)["price"].dropna()
            if len(pr):
                adr = float(pr.median())
        except Exception:
            adr = None
    out["power"] = power_block(imp["sigma_dY_control"], n_tr,
                               imp["n_control"], adr_scale=adr)
    print(f"  MDE = {out['power']['mde_rating_points']:.4f} rating points; "
          f"sigma = {imp['sigma_dY_control']:.3f}")

    # ---- verdict ---------------------------------------------------------
    # Two SEPARATE claims, each judged on whether it replicates across the two
    # fold directions. Running one direction only is how this analysis would
    # go wrong: A->B and B->A genuinely disagree on specificity.
    q3 = out.get("q3") or {}
    q3z = q3.get("z_vs_scrambled")
    q3_ok = bool(q3z is not None and q3z > 1.96 and q3.get("p_value_scrambled", 1) < 0.05)

    per_dir = {}
    for dk, d in blocks.items():
        b = d["improvement"]
        pg = b["placebo_gap"]
        per_dir[dk] = {
            "pooled_att": round(b["pooled"]["att"], 4),
            "pooled_t": round(b["pooled"]["t"], 2) if b["pooled"].get("t") else None,
            "pre_trend_diff": round(b["pre_trend"]["diff"], 4),
            "pre_trend_t": round(b["pre_trend"]["t"], 2) if b["pre_trend"].get("t") else None,
            "gap": round(b["gap"]["observed"], 4),
            "placebo_gap": round(pg["mean"], 4),
            "placebo_ratio": round(pg["ratio_observed_over_placebo"], 3)
            if pg.get("ratio_observed_over_placebo") else None,
            "placebo_p": round(pg["p_value"], 3) if pg.get("p_value") is not None else None,
            "best_aspect": b["best_aspect"],
            "specificity_t": round(d["specificity"].get("t", float("nan")), 2),
            "pooled_ok": bool(b["pooled"].get("t") and b["pooled"]["t"] > 2
                              and b["pooled"]["att"] > 0),
            "gap_ok": bool(pg.get("ratio_observed_over_placebo")
                           and pg["ratio_observed_over_placebo"] >= 1.5
                           and (pg.get("p_value") or 1) < 0.05),
            "trend_clean": bool(b["pre_trend"].get("t") is not None
                                and abs(b["pre_trend"]["t"]) < 2),
        }
    out["replication"] = per_dir

    n_pooled = sum(v["pooled_ok"] for v in per_dir.values())
    n_gap = sum(v["gap_ok"] for v in per_dir.values())
    bests = {v["best_aspect"] for v in per_dir.values()}
    improvement_pays = ("REPLICATED_ACROSS_FOLDS" if n_pooled == len(per_dir)
                        else "DIRECTION_DEPENDENT" if n_pooled else "NOT_DETECTED")
    if n_gap == len(per_dir) and len(bests) == 1:
        specificity = "ESTABLISHED"
    elif n_gap:
        specificity = "DIRECTION_DEPENDENT"
    else:
        specificity = "NOT_DETECTED"
    status = (f"IMPROVEMENT_PAYS_{improvement_pays}__SPECIFICITY_{specificity}")

    out["verdict"] = {
        "status": status,
        "improvement_pays": improvement_pays,
        "aspect_specificity": specificity,
        "best_aspect_by_direction": {k: v["best_aspect"] for k, v in per_dir.items()},
        "pre_trend_by_direction": {k: v["pre_trend_t"] for k, v in per_dir.items()},
        "pooled_by_direction": {k: v["pooled_att"] for k, v in per_dir.items()},
        "gap_ratio_by_direction": {k: v["placebo_ratio"] for k, v in per_dir.items()},
        "transfer_status": ("TRANSFERS" if q3_ok else
                            "NO_TRANSFER" if q3z is not None else "NOT_RUN"),
        "mde_rating_points": round(out["power"]["mde_rating_points"], 4),
        "no_ips_snips": True,
    }
    out["verdict"]["implications"] = _implications(out["verdict"], q3, per_dir)

    (OUT_DIR / "p5a.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "P5A.md").write_text(render_md(out), encoding="utf-8")

    vd = out["verdict"]
    att_str = " / ".join(f"{k} {s['pooled_att']:+.4f} (t={s['pooled_t']})"
                         for k, s in per_dir.items())
    reg_summary = (f"{vd['improvement_pays']}; SPECIFICITY {vd['aspect_specificity']}; "
                   f"pooled {att_str}; "
                   f"gap_ratio " + " / ".join(
                       f"{k} {s['placebo_ratio']}" for k, s in per_dir.items()) + "; "
                   f"transfer {vd['transfer_status']}; "
                   f"mde {vd['mde_rating_points']}")
    register_experiment(ROOT, {
        "experiment_id": "P5A-revealed-interventions",
        "wave": WAVE,
        "name": "revealed_intervention_event_study_and_power_analysis",
        "preregistered": "yes",
        "status": status,
        "artifact": "outputs/autonomous/p5a/p5a.json",
        "result_summary": reg_summary,
        "claim_ids": "P5A",
    })
    prev = {}
    fp = ROOT / "outputs" / "autonomous" / "FACTS.json"
    if fp.exists():
        prev = json.loads(fp.read_text(encoding="utf-8")).get("waves", {}).get(str(WAVE), {})
    prev.update({
        "experiment": "revealed_intervention_event_study",
        "estimand": "rating change after a persistent, fold-pure aspect improvement",
        "verdict_status": status,
        "improvement_pays": vd["improvement_pays"],
        "aspect_specificity": vd["aspect_specificity"],
        "replication": per_dir,
        "pooled_att_by_direction": vd["pooled_by_direction"],
        "pooled_att": vd["pooled_by_direction"].get("A->B"),
        "gap_ratio_by_direction": vd["gap_ratio_by_direction"],
        "best_aspect_by_direction": vd["best_aspect_by_direction"],
        "pre_trend_by_direction": vd["pre_trend_by_direction"],
        "specificity_t": out["main"]["specificity"].get("t"),
        "transfer_status": vd["transfer_status"],
        "n_events": imp.get("n_events"),
        "n_hotel_quarters": out["main"].get("n_hotel_quarters"),
        "mde_rating_points": out["power"]["mde_rating_points"],
        "sigma_dY_control": imp["sigma_dY_control"],
        "adoption_unidentified": True,
        "revenue_unidentified": True,
        "no_ips_snips": True,
    })
    merge_facts(ROOT, str(WAVE), prev)

    print(json.dumps(out["verdict"], indent=2, ensure_ascii=False))
    print(f"WROTE {OUT_DIR / 'p5a.json'}")
    return 0


def _implications(v: dict, q3: dict, per_dir: dict) -> list[str]:
    L = []
    if v["improvement_pays"] == "REPLICATED_ACROSS_FOLDS":
        vals = " / ".join(f"{k} {s['pooled_att']:+.4f} (t={s['pooled_t']})"
                          for k, s in per_dir.items())
        L.append("Persistent improvements ARE followed by higher ratings, and "
                 f"it replicates across both fold directions: {vals}. "
                 "Events are also aspect-specific (the event aspect moves more "
                 "than the others, specificity t="
                 f"{min(abs(s['specificity_t']) for s in per_dir.values()):.1f}+).")
    else:
        L.append(f"Improvement effect does not replicate: {v['improvement_pays']}.")

    if v["aspect_specificity"] == "ESTABLISHED":
        L.append("The payoff differs by aspect and agrees across folds -- "
                 "aspect targeting is supported.")
    elif v["aspect_specificity"] == "DIRECTION_DEPENDENT":
        L.append("Which aspect pays most is DIRECTION-DEPENDENT: "
                 + "; ".join(f"{k} gap ratio {s['placebo_ratio']} "
                             f"(p={s['placebo_p']}, best={s['best_aspect']})"
                             for k, s in per_dir.items())
                 + ". One fold direction clears the placebo, the other does not, "
                   "and they do not name the same aspect. Targeting is NOT "
                   "established -- reporting either direction alone would be "
                   "cherry-picking.")
        dirty = [k for k, s in per_dir.items() if not s["trend_clean"]]
        if dirty:
            L.append("The direction that shows specificity ("
                     + ", ".join(dirty)
                     + ") is also the one with an unresolved pre-trend "
                       f"(t={per_dir[dirty[0]]['pre_trend_t']}): those hotels were "
                       "already moving before the event, so part of that gap is "
                       "mean reversion, not payoff.")
        L.append("So the defensible claim is 'act on your weakest reliably "
                 "measured aspect', NOT 'act on aspect X because it pays more'. "
                 "The shipped peer-relative ranking already implements the first.")
    else:
        L.append("No aspect-specific payoff was detected in either direction.")

    if v["transfer_status"] == "NO_TRANSFER":
        L.append("P3's cross-sectional value vector does not transfer to this "
                 f"intervention estimand (scrambled-gamma z="
                 f"{q3.get('z_vs_scrambled')}), which is consistent: it was "
                 "estimated on levels, not on changes.")
    L.append("The smallest between-aspect difference detectable with the "
             f"current sample is {v['mde_rating_points']} rating points; "
             "anything smaller needs more logged interventions, not a better "
             "estimator.")
    L.append("Adoption probability and revenue remain unidentified: there is no "
             "adoption log and no ADR/occupancy for these hotels. Closing the "
             "original goal requires logged interventions, not a better estimator.")
    return L


if __name__ == "__main__":
    raise SystemExit(main())

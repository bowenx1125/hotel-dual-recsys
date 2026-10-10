"""P4 driver: cross-fitted direct-method off-policy evaluation.

See src/effect/ope.py for the method and for why this is NOT IPS/SNIPS.
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
from src.effect import ope  # noqa: E402

OUT_DIR = ROOT / "outputs" / "autonomous" / "p4"
ASPECTS = ope.ASPECTS
ACTIONABLE = ope.ACTIONABLE
Z = ope.Z

REFRESH_CHOICES = False  # set by --refresh-choices

POLICY_LABEL = {
    "fix_weakest": "fix weakest aspect (diagnostic)",
    "largest_peer_gap": "largest peer gap (actionable)",
    "most_criticized": "most criticized",
    "peer_relative": "peer-relative evidence-weighted (SHIPPED)",
    "reliability_aware": "reliability-aware",
}


def _delta(u: pd.DataFrame) -> float:
    """Reference improvement size: median positive quarter-over-quarter move."""
    xs = [u[ope.x_col(a)].to_numpy() for a in ASPECTS]
    v = np.concatenate(xs)
    v = v[np.isfinite(v) & (v > 0)]
    return float(np.median(v)) if v.size else float("nan")


def cross_fit_gamma(u: pd.DataFrame, n_splits: int, seed: int) -> dict:
    """Out-of-hotel gamma: fit excluding a hotel's own split, value on it."""
    rng = np.random.default_rng(seed)
    hotels = np.sort(u["hotel_id"].unique())
    perm = rng.permutation(len(hotels))
    split = np.empty(len(hotels), dtype=int)
    for k in range(n_splits):
        split[perm[k::n_splits]] = k
    smap = dict(zip(hotels, split))
    u = u.copy()
    u["_s"] = u["hotel_id"].map(smap)

    gamma_hat = np.zeros(len(ASPECTS))
    rows = 0
    for k in range(n_splits):
        tr = u[u["_s"] != k]
        te = u[u["_s"] == k]
        if len(te) == 0 or len(tr) < 200:
            continue
        f = ope.fit_gamma(tr)
        if "error" in f:
            continue
        gamma_hat += f["gamma"] * len(te)
        rows += len(te)
    if rows == 0:
        return {"error": "no_rows"}
    return {"gamma": gamma_hat / rows, "n": int(rows)}


def hotel_positions(df: pd.DataFrame) -> tuple[np.ndarray, dict]:
    """hotel -> positional row indices, computed once (bootstrap calls it a lot)."""
    codes, uniques = pd.factorize(df["hotel_id"].to_numpy(), sort=False)
    order = np.argsort(codes, kind="stable")
    s = codes[order]
    starts = np.flatnonzero(np.r_[True, s[1:] != s[:-1]])
    ends = np.r_[starts[1:], len(s)]
    pos = {uniques[s[i]]: order[starts[i]:ends[i]] for i in range(len(starts))}
    return np.asarray(uniques), pos


def resample_units(u: pd.DataFrame, choices: pd.DataFrame, rng,
                   hotels: np.ndarray, pos_u: dict, pos_c: dict
                   ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hotel-clustered bootstrap resample (duplicated hotels get unique ids)."""
    pick = rng.integers(0, len(hotels), len(hotels))
    parts_u, parts_c = [], []
    for j, hp in enumerate(pick):
        h = hotels[hp]
        idx = pos_u.get(h)
        if idx is None or idx.size == 0:
            continue
        tag = f"{h}__{j}"
        du = u.iloc[idx].copy()
        du["hotel_id"] = tag
        parts_u.append(du)
        ci = pos_c.get(h)
        if ci is not None and ci.size:
            dc = choices.iloc[ci].copy()
            dc["hotel_id"] = tag
            parts_c.append(dc)
    if not parts_u:
        return u, choices
    return pd.concat(parts_u, ignore_index=True), pd.concat(parts_c, ignore_index=True)


def run_timing(panel: pd.DataFrame, fold_df: pd.DataFrame, peers: pd.DataFrame,
               cfg: dict, *, timing: str, periods: list[str], min_reviews: int,
               boots: int, seed: int, n_splits: int) -> dict:
    directions = []
    for detect, out in (("A", "B"), ("B", "A")):
        u = ope.build_units(panel, fold_df, detect, out, timing=timing,
                            min_reviews=min_reviews, periods=periods)
        cpath = OUT_DIR / f"_choices_{detect}_m{int(cfg.get('min_mentions', 5))}.parquet"
        if cpath.exists() and not REFRESH_CHOICES:
            ch = pd.read_parquet(cpath)
            print(f"  [{timing}] choices cache hit: {cpath.name}")
        else:
            pstate = ope.fold_panel(panel, detect, fold_df, cfg)
            ch = ope.build_choices(pstate, peers, cfg, periods,
                                   weight_variants=cfg.get("weight_grids"))
            ch.to_parquet(cpath, index=False)
        m = u.merge(ch, on=["hotel_id", "period"], how="inner")
        g = ope.fit_gamma(m)
        if "error" in g:
            return {"error": g["error"], "timing": timing, "detect": detect}
        cf = cross_fit_gamma(m, n_splits, seed)
        directions.append({
            "detect": detect, "out": out,
            "units": m, "choices": m,
            "gamma": g["gamma"], "se": g["se"], "cov": g["cov"],
            "n": int(g["n"]), "n_clusters": int(g["n_clusters"]),
            "delta": _delta(m),
            "gamma_cf": cf.get("gamma"),
        })
        print(f"  [{timing}] detect={detect} -> out={out}: n={g['n']} "
              f"clusters={g['n_clusters']} delta={directions[-1]['delta']:.4f}")

    n_dir = len(directions)
    gamma = sum(d["gamma"] for d in directions) / n_dir
    se = np.sqrt(sum(d["se"] ** 2 for d in directions)) / n_dir
    cov = sum(d["cov"] for d in directions) / (n_dir ** 2)
    gamma_cf = (sum(d["gamma_cf"] for d in directions) / n_dir
                if all(x.get("gamma_cf") is not None for x in directions) else None)
    delta = float(np.mean([d["delta"] for d in directions]))
    n = int(sum(d["n"] for d in directions) / n_dir)
    n_clusters = int(sum(d["n_clusters"] for d in directions) / n_dir)

    # policy columns -> shares, averaged over directions
    shipped = [c for c in ("fix_weakest", "largest_peer_gap", "most_criticized",
                           "peer_relative", "reliability_aware")
               if c in directions[0]["choices"].columns]
    variants = [c for c in directions[0]["choices"].columns if c.startswith("wrank_")]
    policy_cols = shipped + variants

    shares_all: dict[str, np.ndarray] = {}
    abstain: dict[str, float] = {}
    for c in policy_cols:
        ps = [ope.shares(d["choices"], c) for d in directions]
        shares_all[c] = sum(ps) / n_dir
        ab = [float(d["choices"][c].isna().mean()) for d in directions]
        abstain[c] = float(np.mean(ab))

    # synthetic references
    k = len(ACTIONABLE)
    synthetic: dict[str, np.ndarray] = {"random_uniform": np.full(k, 1.0 / k)}
    for i, a in enumerate(ACTIONABLE):
        v = np.zeros(k)
        v[i] = 1.0
        synthetic[f"always_{a}"] = v
    # oracles use the SAME gamma -> mildly optimistic; flagged in the report.
    gi = {a: gamma[i] for i, a in enumerate(ASPECTS)}
    best = max(ACTIONABLE, key=lambda a: gi[a])
    worst = min(ACTIONABLE, key=lambda a: gi[a])
    for name, a in (("oracle_best", best), ("oracle_worst", worst)):
        v = np.zeros(k)
        v[ACTIONABLE.index(a)] = 1.0
        synthetic[name] = v
    synthetic["never_act"] = np.zeros(k)

    all_p = {**shares_all, **synthetic}

    cov_a = ope.sub_cov(cov)

    def share_for(name: str, gb: np.ndarray | None = None) -> np.ndarray:
        """Share vector for any policy name (shipped / always_X / oracle / random)."""
        if name.startswith("always_"):
            v = np.zeros(len(ACTIONABLE))
            a = name[len("always_"):]
            if a in ACTIONABLE:
                v[ACTIONABLE.index(a)] = 1.0
            return v
        if name == "random_uniform":
            return np.full(len(ACTIONABLE), 1.0 / len(ACTIONABLE))
        if name == "never_act":
            return np.zeros(len(ACTIONABLE))
        if name in ("oracle_best", "oracle_worst"):
            g = gamma if gb is None else gb
            gact = ope.sub_vec(g)
            i = int(np.argmax(gact) if name == "oracle_best" else np.argmin(gact))
            v = np.zeros(len(ACTIONABLE))
            v[i] = 1.0
            return v
        return all_p[name]

    CONTRASTS = [
        ("always_service", "peer_relative"),
        ("largest_peer_gap", "peer_relative"),
        ("wrank_gap-dominant", "wrank_current-default"),
        ("peer_relative", "random_uniform"),
        ("oracle_best", "random_uniform"),
    ]
    contrasts = {}
    for a_name, b_name in CONTRASTS:
        if a_name not in all_p or b_name not in all_p:
            continue
        pa, pb = all_p[a_name], all_p[b_name]
        w = pa - pb
        d = ope.value_of(pa, gamma, delta) - ope.value_of(pb, gamma, delta)
        s = float(delta * np.sqrt(max(w @ cov_a @ w, 0.0)))
        contrasts[f"{a_name} - {b_name}"] = {
            "diff": d, "se": s,
            "t": (d / s if s > 0 else float("nan")),
            "ci95": [d - Z * s, d + Z * s],
            "significant_5pct": bool(abs(d / s) > Z) if s > 0 else False,
        }

    def val_se(p: np.ndarray) -> tuple[float, float]:
        v = ope.value_of(p, gamma, delta)
        s = float(delta * np.sqrt(max(p @ cov_a @ p, 0.0)))
        return v, s

    values = {}
    for name, p in all_p.items():
        v, s = val_se(p)
        values[name] = {
            "value": v, "se": s,
            "ci95": [v - Z * s, v + Z * s],
            "shares": {a: float(p[i]) for i, a in enumerate(ACTIONABLE)},
            "abstain_rate": abstain.get(name),
        }

    # ---- headline: honest split-sample discrimination power -----------------
    power = split_sample_power(directions, ACTIONABLE, delta, seed)
    power["optimistic_in_sample"] = {
        "best_aspect": best, "worst_aspect": worst,
        "gap": values["oracle_best"]["value"] - values["oracle_worst"]["value"],
        "se": float(delta * np.sqrt(max(
            (all_p["oracle_best"] - all_p["oracle_worst"]) @ cov_a
            @ (all_p["oracle_best"] - all_p["oracle_worst"]), 0.0))),
    }

    # ---- cross-fit agreement check -----------------------------------------
    cf_check = None
    if gamma_cf is not None:
        cf_check = {}
        for name, p in all_p.items():
            cf_check[name] = ope.value_of(p, gamma_cf, delta)
        cf_check["_max_abs_diff_vs_full"] = max(
            abs(cf_check[n] - values[n]["value"]) for n in all_p
        )

    # ---- placebo: permute reward within period ------------------------------
    rng = np.random.default_rng(seed + 7)
    placebo = []
    for d in directions:
        b = d["units"].copy()
        b["y"] = b.groupby("period")["y"].transform(
            lambda s: rng.permutation(s.to_numpy())
        )
        g = ope.fit_gamma(b)
        if "error" in g:
            continue
        gg = {a: g["gamma"][i] for i, a in enumerate(ASPECTS)}
        bb = max(ACTIONABLE, key=lambda a: gg[a])
        ww = min(ACTIONABLE, key=lambda a: gg[a])
        placebo.append(delta * (gg[bb] - gg[ww]))
    placebo_gap = float(np.mean(placebo)) if placebo else None

    # ---- cluster bootstrap cross-check --------------------------------------
    boot_se = None
    if boots > 0:
        rng = np.random.default_rng(seed + 101)
        tracked = ["peer_relative", "largest_peer_gap", "always_service",
                   "random_uniform", "oracle_best", "oracle_worst"]
        draws: dict[str, list[float]] = {n: [] for n in tracked}
        maps = [(d, *hotel_positions(d["units"]), hotel_positions(d["choices"])[1])
                for d in directions]
        for _ in range(boots):
            gs, ps = [], {n: [] for n in tracked}
            for d, hotels, pos_u, pos_c in maps:
                bu, bc = resample_units(d["units"], d["choices"], rng,
                                        hotels, pos_u, pos_c)
                g = ope.fit_gamma(bu)
                if "error" in g:
                    gs = []
                    break
                gs.append(g["gamma"])
                for name in tracked:
                    if name in policy_cols:
                        ps[name].append(ope.shares(bc, name))
            if len(gs) != len(directions):
                continue
            gb = sum(gs) / len(gs)
            for name in tracked:
                p = share_for(name, gb)
                if name in policy_cols and ps[name]:
                    p = sum(ps[name]) / len(ps[name])
                draws[name].append(ope.value_of(p, gb, delta))

        # bootstrap SE for the analytic contrasts (paired draws)
        for key, c in contrasts.items():
            a_name, b_name = (s.strip() for s in key.split(" - ", 1))
            if a_name in draws and b_name in draws:
                dif = np.asarray(draws[a_name]) - np.asarray(draws[b_name])
                c["boot_se"] = float(np.std(dif, ddof=1)) if len(dif) > 3 else None
        boot_se = {n: (float(np.std(v, ddof=1)) if len(v) > 3 else None)
                   for n, v in draws.items()}
        boot_se["_n_boot"] = int(max((len(v) for v in draws.values()), default=0))

    # ---- location-as-action violation ---------------------------------------
    loc_viol = {}
    for c in policy_cols:
        v = [float((d["choices"][c] == "location").mean()) for d in directions]
        loc_viol[c] = float(np.mean(v))

    return {
        "timing": timing,
        "periods": periods,
        "min_reviews": min_reviews,
        "n_units_per_direction": n,
        "n_hotels_per_direction": n_clusters,
        "coverage": {
            "hotels_total": int(panel["hotel_id"].nunique()),
            "hotels_eval": n_clusters,
            "hotel_share": round(n_clusters / max(panel["hotel_id"].nunique(), 1), 4),
            "min_mentions_state_fold": cfg.get("min_mentions"),
        },
        "delta_reference_improvement": delta,
        "gamma": {a: float(gamma[i]) for i, a in enumerate(ASPECTS)},
        "gamma_se": {a: float(se[i]) for i, a in enumerate(ASPECTS)},
        "gamma_cf": None if gamma_cf is None else {a: float(gamma_cf[i])
                                                   for i, a in enumerate(ASPECTS)},
        "values": values,
        "contrasts": contrasts,
        "cov_actionable": [[float(x) for x in row] for row in cov_a],
        "cross_fit_check": cf_check,
        "power_split_sample": power,
        "placebo_permutation_gap": placebo_gap,
        "bootstrap_se": boot_se,
        "location_action_violation_rate": loc_viol,
        "policies": {c: POLICY_LABEL.get(c, f"peer-relative weights: {c[6:]}") for c in policy_cols},
    }


def split_sample_power(directions: list[dict], actionable: list[str], delta: float,
                       seed: int) -> dict:
    """Honest discrimination power: pick the best aspect on one hotel half,
    value it on the other half, using the training half's gamma."""
    rng = np.random.default_rng(seed + 13)
    out = []
    for rep in range(20):
        gaps = []
        for d in directions:
            u = d["units"]
            hotels = np.sort(u["hotel_id"].unique())
            perm = rng.permutation(len(hotels))
            h1 = set(hotels[perm[: len(hotels) // 2]])
            tr = u[u["hotel_id"].isin(h1)]
            te = u[~u["hotel_id"].isin(h1)]
            g = ope.fit_gamma(tr)
            if "error" in g:
                continue
            gi = {a: g["gamma"][i] for i, a in enumerate(ASPECTS)}
            best = max(actionable, key=lambda a: gi[a])
            worst = min(actionable, key=lambda a: gi[a])
            gaps.append(delta * (gi[best] - gi[worst]))
        if gaps:
            out.append(float(np.mean(gaps)))
    if not out:
        return {"error": "no_reps"}
    return {
        "n_reps": len(out),
        "mean_gap": float(np.mean(out)),
        "sd_gap": float(np.std(out, ddof=1)) if len(out) > 1 else None,
        "p05": float(np.percentile(out, 5)),
        "p95": float(np.percentile(out, 95)),
        "share_positive": float(np.mean([g > 0 for g in out])),
    }


def render_md(r: dict) -> str:
    L = []
    A = L.append
    A("# P4 Off-Policy Evaluation (direct method, cross-fitted)\n")
    A("**Not IPS/SNIPS.** No logged policy exists in this project "
      "(`wave6/policy.json: no_ips_snips=true`; reviewer rule R1 P2). "
      "Values below come from an outcome regression (direct method) with "
      "hotel-clustered uncertainty, not from inverse propensity weighting.\n")
    for t, res in r["timings"].items():
        A(f"## Timing: {t}\n")
        if "error" in res:
            A(f"- ERROR: {res['error']}\n")
            continue
        A(f"- units/direction: **{res['n_units_per_direction']}**, "
          f"hotels/direction: **{res['n_hotels_per_direction']}**, "
          f"periods: {', '.join(res['periods'])}")
        A(f"- reference improvement delta: **{res['delta_reference_improvement']:.4f}** "
          f"(median positive quarter-over-quarter aspect move)\n")
        A("### Aspect value coefficients (rating points per 1 unit of sentiment)\n")
        A("| aspect | gamma | se |")
        A("|---|---|---|")
        for a in ASPECTS:
            A(f"| {a} | {res['gamma'][a]:+.4f} | {res['gamma_se'][a]:.4f} |")
        A("")
        A("### Policy values (rating points; abstention = 0)\n")
        A("| policy | value | se | 95% CI | abstain |")
        A("|---|---|---|---|---|")
        for name, v in res["values"].items():
            ci = f"[{v['ci95'][0]:+.4f}, {v['ci95'][1]:+.4f}]"
            ab = "—" if v["abstain_rate"] is None else f"{v['abstain_rate']:.1%}"
            A(f"| {name} | {v['value']:+.4f} | {v['se']:.4f} | {ci} | {ab} |")
        A("")
        p = res["power_split_sample"]
        A("### Policy contrasts (rating points vs the named comparator)\n")
        A("| contrast | diff | se | t | bootstrap se | 5% sig |")
        A("|---|---|---|---|---|---|")
        for k, c in res["contrasts"].items():
            bs = "—" if c.get("boot_se") is None else f"{c['boot_se']:.4f}"
            A(f"| {k} | {c['diff']:+.4f} | {c['se']:.4f} | {c['t']:+.2f} | {bs} "
              f"| {'yes' if c['significant_5pct'] else 'no'} |")
        A("")
        A("### Discrimination power (headline)\n")
        if "error" not in p:
            A(f"- split-sample best-minus-worst gap: **{p['mean_gap']:+.4f}** "
              f"(sd across {p['n_reps']} reps {p['sd_gap']:.4f}, "
              f"90% range [{p['p05']:+.4f}, {p['p95']:+.4f}])")
        o = res["power_split_sample"].get("optimistic_in_sample") or {}
        if o:
            A(f"- in-sample optimistic gap ({o['best_aspect']} vs {o['worst_aspect']}): "
              f"**{o['gap']:+.4f}** (se {o['se']:.4f}) — upper bound only")
        if res["placebo_permutation_gap"] is not None:
            A(f"- permutation placebo gap: **{res['placebo_permutation_gap']:+.4f}** "
              f"(reward shuffled within period; should be ~0)")
        cf = res["cross_fit_check"]
        if cf:
            A(f"- cross-fit vs full-sample max abs value diff: "
              f"**{cf['_max_abs_diff_vs_full']:.5f}**")
        bs = res["bootstrap_se"]
        if bs:
            A(f"- cluster-bootstrap SE (n={bs.get('_n_boot')}): "
              + ", ".join(f"{k}={v:.4f}" for k, v in bs.items()
                          if not k.startswith("_") and v is not None))
        A("")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timings", default="forward,contemp")
    ap.add_argument("--min-reviews", type=int, default=5)
    ap.add_argument("--boots", type=int, default=200)
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--refresh-choices", action="store_true")
    ap.add_argument("--min-mentions", type=int, default=5,
                    help="min mentions per aspect on the state fold (coverage knob)")
    ap.add_argument("--tag", default="", help="suffix for output filenames")
    args = ap.parse_args(argv)

    global REFRESH_CHOICES
    REFRESH_CHOICES = bool(args.refresh_choices)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(ope.PANEL)
    fold_df = pd.read_parquet(ope.FOLD)
    peers = pd.read_parquet(ope.PEERS)
    cfg = json.loads((ROOT / "conf" / "demo.json").read_text(encoding="utf-8"))
    cfg["actionability"] = json.loads(
        (ROOT / "conf" / "actionability.json").read_text(encoding="utf-8")
    )["aspects"]
    cfg["min_mentions"] = args.min_mentions

    complete = sorted(panel.loc[panel["period_complete"], "period"].unique())
    periods = [p for p in complete if "2016Q1" <= p <= "2017Q1"]
    print(f"periods: {periods}")

    timings = {}
    for t in args.timings.split(","):
        t = t.strip()
        if not t:
            continue
        print(f"=== timing={t} ===")
        timings[t] = run_timing(panel, fold_df, peers, cfg, timing=t, periods=periods,
                                min_reviews=args.min_reviews, boots=args.boots,
                                seed=args.seed, n_splits=args.splits)

    out = {
        "method": "direct_method_cross_fit",
        "is_ips_snips": False,
        "no_logged_policy": True,
        "spec": {
            "unit": "hotel x quarter",
            "treatment": "x_a = smoothed_net_DETECT(a,t) - smoothed_net_DETECT(a,t-1)",
            "reward_forward": "mean_score_OUT(t+1) - mean_score_OUT(t)",
            "reward_contemp": "mean_score_OUT(t) - mean_score_OUT(t-1)",
            "state_fold": "DETECT fold only (no outcome-fold reviews in the state)",
            "fe": "hotel fixed effects + period dummies",
            "clusters": "hotel",
            "directions": ["A->B", "B->A"],
            "timings": list(timings),
            "min_reviews": args.min_reviews,
            "seed": args.seed,
        },
        "timings": timings,
    }

    fwd = timings.get("forward", {})
    pw = fwd.get("power_split_sample", {})
    gap = pw.get("mean_gap")
    pl = fwd.get("placebo_permutation_gap")
    # A split-sample max-minus-min gap is inflated by construction (order
    # statistics). The permutation placebo is the honest yardstick: if the real
    # gap is not clearly larger than the shuffled one, the protocol has no power.
    ratio = (abs(gap) / abs(pl)) if (gap is not None and pl) else None
    if gap is None or ratio is None or ratio < 1.5:
        verdict = "AMBER_NO_DISCRIMINATION"
    else:
        verdict = "AMBER_ASSOCIATIONAL"
    out["verdict"] = {
        "status": verdict,
        "discrimination_gap": gap,
        "placebo_gap": pl,
        "placebo_ratio": ratio,
        "note": "Direct-method OPE. NOT IPS/SNIPS (no logged policy). Values are "
                "model-based; causal content bounded by the P2 finding that the "
                "leading (forward) specification is statistically indistinguishable "
                "from zero. The discrimination gap is compared against a permutation "
                "placebo because a split-sample max-minus-min gap is inflated by "
                "construction.",
    }

    suffix = f"_{args.tag}" if args.tag else ""
    (OUT_DIR / f"ope_values{suffix}.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUT_DIR / f"OPE{suffix}.md").write_text(render_md(out), encoding="utf-8")

    register_experiment(ROOT, {
        "experiment_id": "P4-direct-method-ope",
        "wave": 12,
        "name": "direct_method_cross_fit_policy_evaluation",
        "preregistered": "yes",
        "status": verdict,
        "artifact": "outputs/autonomous/p4/ope_values.json",
        "result_summary": f"discrimination_gap={gap}",
        "claim_ids": "P4",
    })

    facts_path = ROOT / "outputs" / "autonomous" / "FACTS.json"
    prev = {}
    if facts_path.exists():
        prev = json.loads(facts_path.read_text(encoding="utf-8")).get("waves", {}).get("12", {})
    prev.update({
        "experiment": "direct_method_cross_fit_policy_evaluation",
        "ope_method": "direct_method_cross_fit",
        "no_ips_snips": True,
        "no_logged_policy": True,
        "discrimination_gap": gap,
        "discrimination_sd": pw.get("sd_gap"),
        "placebo_gap": fwd.get("placebo_permutation_gap"),
        "placebo_ratio": out["verdict"]["placebo_ratio"],
        "verdict": verdict,
    })
    merge_facts(ROOT, "12", prev)

    print(f"WROTE {OUT_DIR / 'ope_values.json'}")
    print(json.dumps({"verdict": verdict, "discrimination_gap": gap,
                      "placebo_gap": fwd.get("placebo_permutation_gap")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

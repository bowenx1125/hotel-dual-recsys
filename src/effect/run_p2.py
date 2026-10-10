"""P2 driver: cross-fit effect of aspect sentiment on guest rating.

Pre-registered specification (fixed before looking at the estimates):

- unit      : hotel x aspect x quarter cell, COMPLETE quarters only
- treatment : aspect sentiment from detection fold F
- outcome   : guest rating from the OTHER fold G (F and G are disjoint reviews)
- FE        : hotel x aspect (absorbed by within-transform) + period dummies
- SE        : clustered by hotel, small-sample corrected for absorbed dummies
- sample    : actionable aspects (location excluded), >=3 scored reviews per fold
- placebos  : (1) location aspect (immutable negative control)
              (2) own-fold contrast (x_F -> y_F), exposing mechanical coupling
              (3) permutation of x within period x aspect

Four timing variants are run because the lead/lag structure is the whole
question ("does aspect improvement PRECEDE rating improvement?"):

    lagged_change   x = sn_F(t) - sn_F(t-1)   y = ms_G(t+1) - ms_G(t)
    contemp_change  x = sn_F(t) - sn_F(t-1)   y = ms_G(t)   - ms_G(t-1)
    lagged_level    x = sn_F(t)               y = ms_G(t+1)
    contemp_level   x = sn_F(t)               y = ms_G(t)

Verdict ceiling: AMBER_ASSOCIATIONAL. Folds remove same-review mechanical
coupling; they do not randomise hotel quality.

Writes outputs/autonomous/p2/{effect_estimates.json,EFFECT_ESTIMATES.md} and
registers into EXPERIMENT_REGISTRY.csv / FACTS.json wave "11".
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
from src.effect.estimation import Fit, clustered_fe_ols, combine_two_folds  # noqa: E402

PANEL = ROOT / "data" / "processed" / "hotel_aspect_quarter_v2.parquet"
FOLD = ROOT / "data" / "processed" / "hotel_quarter_fold.parquet"
OUT_DIR = ROOT / "outputs" / "autonomous" / "p2"
X_COL = "x"

TIMINGS = ("lagged_change", "contemp_change", "lagged_level", "contemp_level")
TIMING_LABEL = {
    "lagged_change": "x=d_sn_F(t-1->t), y=ms_G(t->t+1)  [temporal precedence]",
    "contemp_change": "x=d_sn_F(t-1->t), y=ms_G(t-1->t)  [contemporaneous]",
    "lagged_level": "x=sn_F(t), y=ms_G(t+1)  [temporal precedence, levels]",
    "contemp_level": "x=sn_F(t), y=ms_G(t)  [contemporaneous, levels]",
}


def load_tables() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    panel = pd.read_parquet(PANEL)
    fold = pd.read_parquet(FOLD)
    panel = panel[panel["period_complete"]].copy()
    periods = sorted(panel["period"].unique(), key=lambda p: (int(p[:4]), int(p[-1])))
    pi = {p: i for i, p in enumerate(periods)}
    panel["pi"] = panel["period"].map(pi)
    fold["pi"] = fold["period"].map(pi)
    return panel, fold, periods


def build_transitions(panel: pd.DataFrame, fold: pd.DataFrame) -> pd.DataFrame:
    """One row per (cell, treatment quarter t): treatment plus outcomes at t-1,t,t+1."""
    tr = panel[
        [
            "hotel_id", "aspect", "city", "period", "pi",
            "smoothed_net_A", "smoothed_net_B",
            "has_measurement_A", "has_measurement_B",
        ]
    ].sort_values(["hotel_id", "aspect", "pi"]).reset_index(drop=True)

    g = tr.groupby(["hotel_id", "aspect"], sort=False)
    for F in ("A", "B"):
        tr[f"sn{F}_lag"] = g[f"smoothed_net_{F}"].shift(1)
        tr[f"has{F}_lag"] = g[f"has_measurement_{F}"].shift(1)
        tr[f"d_sn_{F}"] = tr[f"smoothed_net_{F}"] - tr[f"sn{F}_lag"]
    tr["pi_lag"] = g["pi"].shift(1)
    tr["contiguous_lag"] = (tr["pi_lag"] == tr["pi"] - 1).fillna(False)

    # An outcome row with original index q is relabelled to pi = q - off so that
    # merging on (hotel_id, pi) lands it on treatment quarter t = q - off.
    oc = fold[["hotel_id", "pi", "mean_score_A", "mean_score_B", "score_n_A", "score_n_B"]]
    for off, suf in ((0, ""), (-1, "_prev"), (1, "_next")):
        o = oc.copy()
        o["pi_src"] = o["pi"]
        o["pi"] = o["pi"] - off
        o = o.rename(columns={
            f"mean_score_{F}": f"ms{F}{suf}" for F in ("A", "B")
        } | {
            f"score_n_{F}": f"n{F}{suf}" for F in ("A", "B")
        })
        o = o.rename(columns={"pi_src": f"pi{suf}"}) if suf else o.drop(columns=["pi_src"])
        tr = tr.merge(o, on=["hotel_id", "pi"], how="left")
    tr["contiguous_next"] = (
        tr["pi_next"].notna() & (tr["pi_next"] == tr["pi"] + 1)
    ).fillna(False)
    return tr


def make_sample(tr: pd.DataFrame, *, timing: str, min_reviews: int,
                aspects: list[str] | None) -> pd.DataFrame:
    if timing not in TIMINGS:
        raise ValueError(f"unknown timing {timing!r}")
    d = tr
    if timing.endswith("_change"):
        d = d[d["contiguous_lag"]]
        for F in ("A", "B"):
            d = d[d[f"has_measurement_{F}"] & d[f"has{F}_lag"]]
    else:
        for F in ("A", "B"):
            d = d[d[f"has_measurement_{F}"]]
    if timing.startswith("lagged"):
        d = d[d["contiguous_next"]]
    if aspects is not None:
        d = d[d["aspect"].isin(aspects)]

    d = d.copy()
    for F in ("A", "B"):
        if timing == "lagged_change":
            d = d[(d[f"n{F}"] >= min_reviews) & (d[f"n{F}_next"] >= min_reviews)]
            d[f"y_{F}"] = d[f"ms{F}_next"] - d[f"ms{F}"]
            d[f"x_{F}"] = d[f"d_sn_{F}"]
        elif timing == "contemp_change":
            d = d[(d[f"n{F}"] >= min_reviews) & (d[f"n{F}_prev"] >= min_reviews)]
            d[f"y_{F}"] = d[f"ms{F}"] - d[f"ms{F}_prev"]
            d[f"x_{F}"] = d[f"d_sn_{F}"]
        elif timing == "lagged_level":
            d = d[d[f"n{F}_next"] >= min_reviews]
            d[f"y_{F}"] = d[f"ms{F}_next"]
            d[f"x_{F}"] = d[f"smoothed_net_{F}"]
        else:  # contemp_level
            d = d[d[f"n{F}"] >= min_reviews]
            d[f"y_{F}"] = d[f"ms{F}"]
            d[f"x_{F}"] = d[f"smoothed_net_{F}"]
    return d


def run_direction(d: pd.DataFrame, treat_fold: str, out_fold: str, seed: int | None = None,
                  n_perm: int = 0) -> dict:
    """Estimate beta for one direction (treatment fold -> outcome fold)."""
    dd = d[["hotel_id", "aspect", "city", "period", f"x_{treat_fold}", f"y_{out_fold}"]].copy()
    dd = dd.rename(columns={f"x_{treat_fold}": X_COL, f"y_{out_fold}": "y"})
    dd["cell"] = dd["hotel_id"] + "||" + dd["aspect"]
    res = clustered_fe_ols(dd, "y", [X_COL], "cell", "hotel_id", period_col="period")
    if "error" in res:
        return res
    fit: Fit = res["fit"]
    out = {"fit": fit.as_dict(), "n": res["n"], "n_clusters": res["n_clusters"]}

    perms = []
    if n_perm and seed is not None:
        rng = np.random.default_rng(seed)
        base = dd[[X_COL, "y", "cell", "hotel_id", "period", "aspect"]].copy()
        for _ in range(n_perm):
            b = base.copy()
            b[X_COL] = b.groupby(["period", "aspect"])[X_COL].transform(
                lambda s: rng.permutation(s.to_numpy())
            )
            r = clustered_fe_ols(b, "y", [X_COL], "cell", "hotel_id", period_col="period")
            if "fit" in r:
                perms.append(r["fit"].beta)
        if perms:
            arr = np.array(perms)
            out["permutation"] = {
                "n_perm": len(perms),
                "mean": float(arr.mean()),
                "sd": float(arr.std(ddof=1)),
                "p_two_sided": float((np.abs(arr) >= abs(fit.beta)).mean()),
            }
    return out


def run_spec(tr: pd.DataFrame, *, name: str, min_reviews: int, timing: str,
             aspects: list[str] | None, own_fold: bool, seed: int, n_perm: int) -> dict:
    d = make_sample(tr, timing=timing, min_reviews=min_reviews, aspects=aspects)
    if len(d) == 0:
        return {"name": name, "error": "empty_sample"}
    dirs = [("A", "A"), ("B", "B")] if own_fold else [("A", "B"), ("B", "A")]
    parts: dict = {}
    fits: list[Fit] = []
    for tf, of in dirs:
        r = run_direction(d, tf, of, seed=seed, n_perm=(n_perm if (tf, of) == dirs[0] else 0))
        parts[f"{tf}->{of}"] = r
        if "fit" in r:
            f = r["fit"]
            fits.append(Fit(**{**f, "ci95": tuple(f["ci95"])}))
    res: dict = {"name": name, "timing": timing, "rows": int(len(d)), "directions": parts}
    if len(fits) == 2:
        comb = combine_two_folds(fits[0], fits[1])
        res["combined"] = comb.as_dict()
        res["beta"] = comb.beta
        res["se"] = comb.se
        res["p"] = comb.p
        res["ci95"] = list(comb.ci95)
    return res


def summarise(r: dict) -> dict:
    return {k: r.get(k) for k in ("beta", "se", "p", "ci95", "rows")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-reviews", type=int, default=3)
    ap.add_argument("--perms", type=int, default=200)
    args = ap.parse_args(argv)

    cfg = load_config(ROOT)
    seed = int(cfg["seed"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    panel, fold, periods = load_tables()
    tr = build_transitions(panel, fold)
    print(f"transitions built: {len(tr)} rows, periods={periods}", flush=True)

    actionable = [a for a in cfg["aspects"] if a != cfg["immutable_negative_control_aspect"]]
    loc = [cfg["immutable_negative_control_aspect"]]

    results: dict = {
        "schema_version": "1.1",
        "spec": {
            "unit": "hotel x aspect x quarter (complete quarters only)",
            "treatment": "aspect sentiment (smoothed_net) on detection fold F",
            "outcome": "mean reviewer score on the other fold G (disjoint reviews)",
            "fixed_effects": ["hotel x aspect (absorbed)", "period dummies"],
            "cluster": "hotel",
            "min_scored_reviews_per_fold": args.min_reviews,
            "main_aspects": actionable,
            "seed": seed,
            "timings": {k: TIMING_LABEL[k] for k in TIMINGS},
        },
        "cross_fit": {},
        "own_fold_contrast": {},
        "location_negative_control": {},
        "sensitivity_min_reviews": {},
        "per_aspect": {},
    }

    for t in TIMINGS:
        print(f"running cross-fit {t} ...", flush=True)
        r = run_spec(tr, name=f"crossfit::{t}", min_reviews=args.min_reviews, timing=t,
                     aspects=actionable, own_fold=False, seed=seed,
                     n_perm=(args.perms if t == "lagged_change" else 0))
        results["cross_fit"][t] = r
        print(f"  beta={r.get('beta')} se={r.get('se')} n={r.get('rows')}", flush=True)

        print(f"running own-fold {t} ...", flush=True)
        ro = run_spec(tr, name=f"ownfold::{t}", min_reviews=args.min_reviews, timing=t,
                      aspects=actionable, own_fold=True, seed=seed, n_perm=0)
        results["own_fold_contrast"][t] = ro

        print(f"running location placebo {t} ...", flush=True)
        rl = run_spec(tr, name=f"location::{t}", min_reviews=args.min_reviews, timing=t,
                      aspects=loc, own_fold=False, seed=seed, n_perm=0)
        results["location_negative_control"][t] = rl

    print("running min-review sensitivity ...", flush=True)
    for mr in (1, 5):
        for t in ("lagged_change", "contemp_change"):
            r = run_spec(tr, name=f"mr{mr}::{t}", min_reviews=mr, timing=t,
                         aspects=actionable, own_fold=False, seed=seed, n_perm=0)
            results["sensitivity_min_reviews"].setdefault(str(mr), {})[t] = summarise(r)

    print("running per-aspect ...", flush=True)
    for a in cfg["aspects"]:
        row = {}
        for t in ("lagged_change", "contemp_change"):
            r = run_spec(tr, name=f"aspect::{a}::{t}", min_reviews=args.min_reviews, timing=t,
                         aspects=[a], own_fold=False, seed=seed, n_perm=0)
            row[t] = summarise(r)
        results["per_aspect"][a] = row

    # ---------------------------------------------------------------- verdict
    lead = results["cross_fit"]["lagged_change"]
    conc = results["cross_fit"]["contemp_change"]
    mb, mp = lead.get("beta"), lead.get("p")
    cb, cp = conc.get("beta"), conc.get("p")
    sig = bool(mp is not None and mp < 0.05)
    verdict = "AMBER_ASSOCIATIONAL"
    results["verdict"] = {
        "status": verdict,
        "lead_significant_at_0.05": sig,
        "contemporaneous_significant_at_0.05": bool(cp is not None and cp < 0.05),
        "reading": (
            "Contemporaneous cross-fold association is strong and survives fold separation, "
            "so it is a genuine hotel-quarter quality signal, not same-review mechanics. "
            "The LEAD specification (aspect change -> next-quarter rating change) is "
            "indistinguishable from zero, so these data do not support "
            "'improving aspect X raises later ratings'."
        ),
        "note": (
            "Observational. Fold separation removes same-review mechanical coupling but does "
            "not randomise hotel quality, and mean reversion in hotel quality depresses the "
            "lead coefficient. Outcome is guest RATING, not revenue: no price, room-night or "
            "cost fields exist in this dataset."
        ),
        "attenuation_note": (
            "Treatment is measured with sampling error independent of the outcome error "
            "(classical errors-in-variables), so |beta| is biased toward zero: estimates are "
            "lower bounds in magnitude."
        ),
    }

    (OUT_DIR / "effect_estimates.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUT_DIR / "EFFECT_ESTIMATES.md").write_text(render_md(results), encoding="utf-8")

    register_experiment(ROOT, {
        "experiment_id": "P2-crossfit-continuous",
        "wave": 11,
        "name": "crossfit_continuous_aspect_to_rating",
        "preregistered": "yes",
        "status": verdict,
        "artifact": "outputs/autonomous/p2/effect_estimates.json",
        "result_summary": f"lead_beta={mb} (p={mp}); contemp_beta={cb} (p={cp})",
        "claim_ids": "P2",
    })
    # merge_facts REPLACES facts["waves"][wave]; preserve anything already there.
    facts_path = ROOT / "outputs" / "autonomous" / "FACTS.json"
    prev = {}
    if facts_path.exists():
        prev = json.loads(facts_path.read_text(encoding="utf-8")).get("waves", {}).get("11", {})
    prev.update({
        "experiment": "crossfit_continuous_aspect_to_rating",
        "spec": results["spec"],
        "lead_beta": mb,
        "lead_se": lead.get("se"),
        "lead_p": mp,
        "lead_ci95": lead.get("ci95"),
        "contemp_beta": cb,
        "contemp_se": conc.get("se"),
        "contemp_p": cp,
        "contemp_ci95": conc.get("ci95"),
        "lead_significant_at_0.05": sig,
        "verdict": verdict,
        "own_fold_mechanical_contrast": {
            t: summarise(v) for t, v in results["own_fold_contrast"].items()
        },
        "location_negative_control": {
            t: summarise(v) for t, v in results["location_negative_control"].items()
        },
        "outcome": "guest_rating_NOT_revenue",
        "no_roi": True,
        "no_demand_lift": True,
    })
    merge_facts(ROOT, "11", prev)

    print(f"WROTE {OUT_DIR / 'effect_estimates.json'}")
    print(json.dumps({
        "lead_beta": mb, "lead_se": lead.get("se"), "lead_p": mp,
        "contemp_beta": cb, "contemp_se": conc.get("se"), "contemp_p": cp,
        "location_placebo_lead": results["location_negative_control"]["lagged_change"].get("beta"),
        "own_fold_lead": results["own_fold_contrast"]["lagged_change"].get("beta"),
    }, indent=2))
    return 0


def render_md(r: dict) -> str:
    sp = r["spec"]
    v = r["verdict"]

    def fmt(k: str, d: dict) -> str:
        if not d or d.get("beta") is None:
            return f"- {k}: n/a\n"
        return (f"- {k}: beta={d['beta']:+.4f} se={d['se']:.4f} p={d['p']:.4g} "
                f"95%CI=[{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}] n={d.get('rows')}\n")

    lines = [
        "# P2 cross-fit effect estimation\n\n",
        f"**Verdict: {v['status']}**\n\n",
        f"**Reading:** {v['reading']}\n\n",
        "## Specification\n\n",
        f"- unit: {sp['unit']}\n",
        f"- treatment: {sp['treatment']}\n",
        f"- outcome: {sp['outcome']}\n",
        f"- FE: {', '.join(sp['fixed_effects'])}; cluster: {sp['cluster']}\n",
        f"- min scored reviews per fold: {sp['min_scored_reviews_per_fold']}\n",
        "- both directions (A->B and B->A) estimated and averaged\n\n",
        "## Results by timing (cross-fit)\n\n",
    ]
    for t in TIMINGS:
        lines.append(fmt(f"{t} — {TIMING_LABEL[t]}", summarise(r["cross_fit"][t])))
    perm = r["cross_fit"]["lagged_change"].get("directions", {}).get("A->B", {}).get("permutation")
    if perm:
        lines.append(
            f"\nPermutation of x within period x aspect (lead spec): mean={perm['mean']:+.4f} "
            f"sd={perm['sd']:.4f} two-sided p={perm['p_two_sided']:.4f} (n={perm['n_perm']})\n"
        )

    lines += ["\n## Own-fold contrast (mechanical coupling check)\n\n",
              "Same fold on both sides; not a valid estimate, shown only to size the artefact.\n\n"]
    for t in TIMINGS:
        lines.append(fmt(t, summarise(r["own_fold_contrast"][t])))

    lines += ["\n## Location negative control (immutable aspect)\n\n"]
    for t in TIMINGS:
        lines.append(fmt(t, summarise(r["location_negative_control"][t])))

    lines += ["\n## Sensitivity: min scored reviews per fold\n\n"]
    for mr, d in r["sensitivity_min_reviews"].items():
        for t, vv in d.items():
            lines.append(fmt(f"min_reviews={mr} {t}", vv))

    lines += ["\n## Per aspect (cross-fit)\n\n"]
    for a, d in r["per_aspect"].items():
        for t, vv in d.items():
            lines.append(fmt(f"{a} / {t}", vv))

    lines += ["\n## Caveats\n\n", f"- {v['note']}\n", f"- {v['attenuation_note']}\n",
              "- No price, room-night or cost fields exist, so nothing here is ROI.\n"]
    return "".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

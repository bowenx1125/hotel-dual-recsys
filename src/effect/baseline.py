"""P1: freeze the pre-optimisation baseline.

Everything the P3 algorithm optimisation must beat, measured on the SAME frozen
panel and the SAME code state.  Written once, then hashed; re-running with
``--check`` only verifies nothing drifted.

Deliberately records the *incumbent* effect estimates including their known
defects (see ``defects`` below) so P3 gains cannot be claimed by quietly
changing the measurement rule.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE_DIR = ROOT / "outputs" / "autonomous" / "baseline"
BASE_JSON = BASE_DIR / "BASELINE.json"
BASE_MD = BASE_DIR / "BASELINE.md"

PANEL = ROOT / "data" / "processed" / "hotel_aspect_quarter_v2.parquet"
FACTS = ROOT / "outputs" / "autonomous" / "FACTS.json"
TRACKED = [
    "conf/demo.json",
    "conf/autonomous_research.json",
    "src/recommendation/scoring.py",
    "src/autonomous/panel.py",
    "src/autonomous/infer.py",
    "src/autonomous/common.py",
    "data/processed/hotel_aspect_quarter_v2.parquet",
    "outputs/autonomous/FACTS.json",
    "outputs/autonomous/CLAIMS_LEDGER.md",
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(args: list[str]) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        return out.stdout.strip()
    except Exception as exc:  # pragma: no cover - environment dependent
        return f"<git unavailable: {exc}>"


def panel_stats(panel: pd.DataFrame) -> dict:
    hq = (
        panel[["hotel_id", "city", "period", "period_complete", "total_reviews", "mean_reviewer_score"]]
        .drop_duplicates(subset=["hotel_id", "period"])
    )
    complete = hq[hq["period_complete"]]
    per_hotel = complete.groupby("hotel_id")["period"].count()
    return {
        "panel_rows": int(len(panel)),
        "aspects": int(panel["aspect"].nunique()),
        "hotel_quarters": int(len(hq)),
        "complete_hotel_quarters": int(len(complete)),
        "hotels": int(panel["hotel_id"].nunique()),
        "cities": int(panel["city"].nunique()),
        "hotels_with_ge4_complete_quarters": int((per_hotel >= 4).sum()),
        "measured_cells": int(panel["has_measurement"].sum()),
        "measured_cells_A": int(panel["has_measurement_A"].sum()),
        "measured_cells_B": int(panel["has_measurement_B"].sum()),
        "prior_only_cells": int(panel["prior_only"].sum()),
        "mean_reviewer_score_mean": float(hq["mean_reviewer_score"].mean()),
        "mean_reviewer_score_std": float(hq["mean_reviewer_score"].std()),
        "total_reviews_mean": float(hq["total_reviews"].mean()),
    }


def incumbent_effects(facts: dict) -> dict:
    w5 = facts.get("waves", {}).get("5", {})
    w6 = facts.get("waves", {}).get("6", {})
    att = {k: v for k, v in (w5.get("att_rel_to_m1") or {}).items()}
    return {
        "wave5_att_rel_to_m1": att,
        "wave5_att_at_event_k0": (att.get("0") or {}).get("mean"),
        "wave5_pretrend_k_minus2": (att.get("-2") or {}).get("mean"),
        "wave5_observational_interaction_beta": w5.get("observational_interaction", {}).get("beta"),
        "wave5_location_placebo": w5.get("location_placebo"),
        "wave6_no_roi": w6.get("no_roi"),
        "wave6_no_demand_lift": w6.get("no_demand_lift"),
        "strict_crossfit_events": facts.get("waves", {}).get("2", {}).get("strict_crossfit_events"),
        "legacy_permissive_event_count": facts.get("waves", {}).get("2", {}).get("legacy_permissive_event_count"),
        "defects": {
            "self_referential_outcome": (
                "Wave5 measures y with POOLED smoothed_net while events are detected per fold; "
                "the treatment and the outcome come from the same reviews."
            ),
            "violates_preregistered_crossfit_rule": (
                "conf/autonomous_research.json crossfit.rule = "
                "'detect_on_one_fold_measure_outcome_on_the_other' is not executed by Wave5."
            ),
            "outcome_is_not_downstream": (
                "smoothed_net is an aspect-sentiment index, not a hotel revenue/rating outcome; "
                "a change in it cannot be read as hotel benefit."
            ),
            "n_456_concentrated_in_2016Q2_Q4": (
                "Strict events cluster in few periods; quarter-score sd limits detectable effect."
            ),
        },
    }


def build() -> dict:
    facts = json.loads(FACTS.read_text(encoding="utf-8")) if FACTS.exists() else {}
    panel = pd.read_parquet(PANEL)
    cfg_demo = json.loads((ROOT / "conf" / "demo.json").read_text(encoding="utf-8"))
    cfg_res = json.loads((ROOT / "conf" / "autonomous_research.json").read_text(encoding="utf-8"))

    artifacts = {}
    for rel in TRACKED:
        p = ROOT / rel
        artifacts[rel] = {"sha256": _sha256(p), "bytes": p.stat().st_size} if p.exists() else {"missing": True}

    base = {
        "schema_version": "1.0",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "purpose": "P1 baseline freeze; reference point for P3 algorithm optimisation.",
        "git": {
            "head": _git(["rev-parse", "HEAD"]),
            "head_subject": _git(["log", "-1", "--pretty=%s"]),
            "dirty": _git(["status", "--porcelain"]).splitlines(),
        },
        "artifacts": artifacts,
        "algorithm": {
            "heuristic": "peer_relative (Peer-Relative Evidence-Weighted)",
            "weights": cfg_demo.get("weights"),
            "weight_grids": list((cfg_demo.get("weight_grids") or {}).keys()),
            "weights_are_design_choices": True,
            "min_mentions": cfg_demo.get("min_mentions"),
            "min_reviews_hotel": cfg_demo.get("min_reviews_hotel"),
            "reliability_k": cfg_demo.get("reliability_k"),
        },
        "research_gates": {
            "seed": cfg_res.get("seed"),
            "crossfit_rule": (cfg_res.get("crossfit") or {}).get("rule"),
            "prior_strength_main": (cfg_res.get("shrinkage") or {}).get("prior_strength_main"),
            "expected_complete_periods": (cfg_res.get("periods") or {}).get("expected_complete"),
            "event_main": cfg_res.get("events", {}).get("main"),
        },
        "panel_stats": panel_stats(panel),
        "incumbent_effects": incumbent_effects(facts),
        "p3_acceptance": {
            "must_beat": "P2 cross-fit effect estimate (downstream outcome, fold-separated).",
            "forbidden": [
                "lowering configured significance / delta thresholds",
                "tuning weights on the same data used to report the gain",
                "claiming ROI or booking growth from review data (no price or volume fields exist)",
            ],
        },
    }
    return base


def render_md(b: dict) -> str:
    a = b["algorithm"]
    p = b["panel_stats"]
    e = b["incumbent_effects"]
    return (
        "# P1 baseline freeze\n\n"
        f"Frozen at {b['frozen_at_utc']} | git HEAD `{b['git']['head'][:12]}` "
        f"({b['git']['head_subject']})\n\n"
        "## Algorithm (the thing P3 changes)\n\n"
        f"- {a['heuristic']}\n"
        f"- weights: {a['weights']} — **design choices, not learned** (`weights_are_design_choices=True`)\n"
        f"- grids available: {a['weight_grids']}\n"
        f"- gates: min_mentions={a['min_mentions']}, min_reviews_hotel={a['min_reviews_hotel']}, "
        f"reliability_k={a['reliability_k']}\n\n"
        "## Panel\n\n"
        f"- rows {p['panel_rows']} | hotels {p['hotels']} | cities {p['cities']}\n"
        f"- hotel-quarters {p['hotel_quarters']} (complete {p['complete_hotel_quarters']})\n"
        f"- measured cells A={p['measured_cells_A']} B={p['measured_cells_B']}; prior-only {p['prior_only_cells']}\n"
        f"- mean_reviewer_score {p['mean_reviewer_score_mean']:.4f} (sd {p['mean_reviewer_score_std']:.4f}); "
        f"total_reviews mean {p['total_reviews_mean']:.2f}\n\n"
        "## Incumbent effect estimates (and why they are weak)\n\n"
        f"- Wave5 ATT at k=0: **{e['wave5_att_at_event_k0']}** (unit = pooled smoothed_net, not a hotel outcome)\n"
        f"- strict cross-fit events: {e['strict_crossfit_events']} "
        f"(legacy permissive {e['legacy_permissive_event_count']} is not a strict result)\n"
        f"- Wave6: no_roi={e['wave6_no_roi']}, no_demand_lift={e['wave6_no_demand_lift']}\n\n"
        "Defects recorded:\n\n"
        + "".join(f"- **{k}**: {v}\n" for k, v in e["defects"].items())
        + "\n## P3 acceptance\n\n"
        f"- must beat: {b['p3_acceptance']['must_beat']}\n"
        + "".join(f"- forbidden: {x}\n" for x in b["p3_acceptance"]["forbidden"])
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="verify tracked artifacts have not drifted")
    args = ap.parse_args(argv)

    if args.check:
        if not BASE_JSON.exists():
            print("NO_BASELINE")
            return 2
        b = json.loads(BASE_JSON.read_text(encoding="utf-8"))
        bad = []
        for rel, meta in b["artifacts"].items():
            p = ROOT / rel
            if not p.exists() or _sha256(p) != meta.get("sha256"):
                bad.append(rel)
        print("DRIFT: " + (", ".join(bad) if bad else "none"))
        return 1 if bad else 0

    b = build()
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    BASE_JSON.write_text(json.dumps(b, indent=2, ensure_ascii=False), encoding="utf-8")
    BASE_MD.write_text(render_md(b), encoding="utf-8")
    print(f"WROTE {BASE_JSON}")
    print(f"WROTE {BASE_MD}")
    print(f"git HEAD {b['git']['head'][:12]} dirty={len(b['git']['dirty'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

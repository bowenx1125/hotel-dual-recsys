"""Streamlit: Actionability-aware Manager Demo + Temporal Research Lab shell."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from demo.config import ROOT, load_actionability_config, load_config
from demo.data_adapter import eligible_hotels, load_snapshot
from demo.evidence import BANNER, decide_evidence_level
from demo.scoring import (
    all_policies,
    criticism_metrics,
    diagnostic_largest_gap,
    explain_action_vs_diagnostic,
    ranking_under_intensity,
)

SNAPSHOT_PATH = ROOT / "outputs" / "night_demo" / "demo_snapshot.json"

LIMITATIONS = """
- Review counts are **not** bookings or demand.
- Aspect net is review sentiment, **not** a verified management intervention.
- Peer sets are labelled reference sets, **not** validated economic substitutes.
- **Peer-Relative Evidence-Weighted** scores use **design-choice weights**, not learned business returns.
- **Competition Crowding Hypothesis** slider is **assumed / illustrative**.
- Location may appear as a diagnostic disadvantage but is **not** a direct operational action.
- No event study, placebo, or causal estimate is claimed in this Demo.
"""


def _load():
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(
            f"Missing {SNAPSHOT_PATH}. Run: python3 scripts/build_demo_snapshot.py"
        )
    snap = load_snapshot(SNAPSHOT_PATH)
    cfg = load_config()
    # keep snapshot peer stats; overlay live config for naming/weights/actionability
    snap_cfg = snap.get("config") or {}
    cfg = {**snap_cfg, **cfg}
    return snap, cfg


def render_manager_tab(st, snap, cfg):
    ev = decide_evidence_level(snap)
    labels = cfg.get("aspect_labels") or {}
    act = load_actionability_config()["aspects"]
    hotels = eligible_hotels(snap)

    st.subheader("Manager Diagnostic Demo")
    st.caption("Manager-facing · DESCRIPTIVE evidence · no external API")
    st.error(ev["banner"])
    with st.expander("Why this evidence level / what we cannot claim", expanded=False):
        st.markdown(f"**Level:** `{ev['level']}`")
        st.write(ev["why"])
        for c in ev["cannot_claim"]:
            st.markdown(f"- {c}")
        st.caption(
            f"Sources: `{snap['sources']['aspect_features']}` · "
            f"`{snap['sources']['compsets']}` · `{snap['sources']['review_aspects_jsonl']}`"
        )

    cities = sorted({h["city"] for h in hotels})
    c1, c2, c3 = st.columns(3)
    with c1:
        city = st.selectbox("City", cities, index=0, key="mgr_city")
    hotels_c = [h for h in hotels if h["city"] == city]
    with c2:
        cs = st.selectbox(
            "Labelled peer set",
            ["(all)"] + sorted({h["compset_id"] for h in hotels_c}),
            key="mgr_cs",
        )
    hotels_f = hotels_c if cs == "(all)" else [h for h in hotels_c if h["compset_id"] == cs]
    with c3:
        names = {h["hotel_name"]: h["hotel_id"] for h in hotels_f}
        name = st.selectbox("Hotel", list(names.keys()), key="mgr_hotel")
    hotel = next(h for h in hotels_f if h["hotel_id"] == names[name])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Peer set size", hotel["compset_size"])
    m2.metric("Labelled reviews", hotel["n_reviews"])
    m3.metric("Low-rating reviews (<7)", hotel["n_negative"])
    m4.metric("Price tier", hotel["price_tier"] or "n/a")

    st.markdown("### Hotel vs peers (diagnostic)")
    rows = []
    for a in cfg["aspects"]:
        rec = hotel["aspects"][a]
        meta = act.get(a, {})
        rows.append({
            "aspect": labels.get(a, a),
            "actionability": meta.get("actionability_level", "?"),
            "direct_action": meta.get("eligible_for_direct_action", False),
            "hotel_net": rec.get("net"),
            "peer_median": rec.get("peer_median_net"),
            "gap (peer−hotel)": rec.get("gap"),
            "percentile": rec.get("percentile"),
            "mentions": rec.get("mention_count"),
            "neg_mentions": rec.get("neg_mentions"),
            "neg_rate": rec.get("neg_rate"),
            "neg_per_review": criticism_metrics(hotel, a)["neg_per_review"],
            "reliability": rec.get("reliability"),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    expl = explain_action_vs_diagnostic(hotel, cfg)
    diag = expl["diagnostic"]
    st.markdown("### Diagnostic disadvantage vs actionable recommendation")
    d1, d2 = st.columns(2)
    d1.metric(
        "Largest diagnostic disadvantage",
        labels.get(expl["diagnostic_aspect"], expl["diagnostic_aspect"] or "n/a"),
    )
    d2.metric(
        "Actionable recommendation (default heuristic)",
        labels.get(expl["actionable_recommendation"], expl["actionable_recommendation"] or "n/a"),
    )
    if expl["explanation"]:
        st.warning(expl["explanation"])
    else:
        st.info("Largest diagnostic disadvantage is actionable; diagnosis and action layers agree on eligibility.")

    st.markdown("### Action recommendation comparison")
    st.caption("Action layer excludes immutable aspects (e.g. Location). Weights are design choices, not learned returns.")
    intensity = st.slider(
        "Competition Crowding Hypothesis — assumed peer-improve intensity (SCENARIO / illustrative)",
        min_value=0.0,
        max_value=1.0,
        value=float(cfg["scenario"]["default_intensity"]),
        step=0.05,
        help="Assumed / illustrative. Not a fitted crowding elasticity.",
        key="mgr_intensity",
    )
    policies = all_policies(hotel, cfg, assumed_intensity=intensity)
    order = ["fix_weakest", "largest_peer_gap", "most_criticized", "peer_relative"]
    cols = st.columns(4)
    for col, key in zip(cols, order):
        p = policies[key]
        chosen = p["chosen_aspect"]
        col.metric(p["label"], labels.get(chosen, chosen) if chosen else "n/a")
        col.caption(p["rule"])

    pr = policies["peer_relative"]
    st.markdown(f"##### {pr['label']} score table")
    scores0 = ranking_under_intensity(hotel, cfg, 0.0)
    scoresI = ranking_under_intensity(hotel, cfg, intensity)
    st.table({
        "aspect": [labels.get(a, a) for a, _ in scoresI],
        "score@intensity": [round(s, 4) for _, s in scoresI],
        "score@0": [round(dict(scores0).get(a, 0.0), 4) for a, _ in scoresI],
    })
    st.caption(cfg.get("formula", ""))
    st.caption(
        f"Design-choice weights: gap={cfg['weights']['gap']}, "
        f"criticism={cfg['weights']['criticism']}, unreliable={cfg['weights']['unreliable']}. "
        "Not estimated business returns."
    )

    st.markdown("### Competition Crowding Hypothesis (Scenario Analysis)")
    st.warning("SCENARIO ANALYSIS — assumed / illustrative. Not an empirical crowding curve. Not causal.")
    scen_rows = []
    for g in (0.0, 0.25, 0.5, 0.75, 1.0):
        rnk = ranking_under_intensity(hotel, cfg, g)
        scen_rows.append({
            "assumed_intensity": g,
            "top_actionable_aspect": labels.get(rnk[0][0], rnk[0][0]) if rnk else None,
            "top_score": round(rnk[0][1], 4) if rnk else None,
        })
    st.dataframe(scen_rows, hide_index=True, use_container_width=True)

    with st.expander("Criticism metric audit (count vs rate vs per-review)"):
        crit_rows = []
        for a in cfg["aspects"]:
            if a not in hotel["aspects"]:
                continue
            m = criticism_metrics(hotel, a)
            crit_rows.append({
                "aspect": labels.get(a, a),
                "neg_mentions": m["neg_mentions"],
                "neg_rate": m["neg_rate"],
                "neg_per_review": round(m["neg_per_review"], 4),
                "actionable": act.get(a, {}).get("eligible_for_direct_action"),
            })
        st.dataframe(crit_rows, hide_index=True, use_container_width=True)
        st.caption("Default Most Criticized uses neg_mentions count; rate and per-review are reported for audit, not swapped silently.")

    st.markdown("### Provenance")
    st.json({
        "evidence_level": ev["level"],
        "hotel_id": hotel["hotel_id"],
        "compset_id": hotel["compset_id"],
        "diagnostic_aspect": expl["diagnostic_aspect"],
        "actionable_recommendation": expl["actionable_recommendation"],
        "policies": {k: policies[k]["chosen_aspect"] for k in order},
        "config": "conf/demo.json",
        "actionability": "conf/actionability.json",
        "synthetic": snap.get("synthetic"),
    })
    st.markdown("### Limitations")
    st.markdown(LIMITATIONS)


def render_temporal_tab(st):
    st.subheader("Temporal Research Feasibility Lab")
    st.caption(
        "Research lab · review-perceived aspect changes · geo reference sets · "
        "NOT causal · NOT managerial interventions · NOT validated competitors"
    )
    gate_path = ROOT / "outputs" / "overnight" / "feasibility" / "GO_NO_GO.md"
    metrics_path = ROOT / "outputs" / "overnight" / "feasibility" / "feasibility_metrics.json"
    panel_manifest = ROOT / "outputs" / "overnight" / "temporal_panel" / "panel_manifest.json"
    peer_manifest = ROOT / "outputs" / "overnight" / "peer_sets" / "peer_set_manifest.json"
    pred_metrics = ROOT / "outputs" / "overnight" / "predictive_pilot" / "metrics.json"
    fig_dir = ROOT / "outputs" / "overnight" / "feasibility" / "figures"

    if panel_manifest.exists():
        pm = json.loads(panel_manifest.read_text(encoding="utf-8"))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Quarter cells", pm.get("quarter_rows"))
        c2.metric("Hotels", pm.get("quarter_hotels"))
        c3.metric("Cities", pm.get("cities"))
        c4.metric("Mention cells", pm.get("valid_mention_cells_quarter"))
        st.caption(
            f"Labeling: structurally weak-labeled aspect sentiment · "
            f"prior_strength={pm.get('prior_strength_main')} · "
            f"source sha256 `{str(pm.get('source_sha256', ''))[:12]}…` (local cache)"
        )
    else:
        st.info("Panel not built yet.")

    if peer_manifest.exists():
        peers = json.loads(peer_manifest.read_text(encoding="utf-8"))
        st.markdown("### Geo reference sets")
        st.write(
            f"Main: same-city Haversine k={peers.get('main_k')} · "
            f"hotels={peers.get('n_hotels')} · cities={peers.get('n_cities')} · "
            "terminology: **geo reference set / candidate peer set** "
            "(not validated competitors)."
        )

    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        verdict = metrics.get("verdict", "UNKNOWN")
        if verdict == "GREEN":
            st.success(f"Feasibility verdict: **{verdict}**")
        elif verdict == "AMBER":
            st.warning(f"Feasibility verdict: **{verdict}**")
        else:
            st.error(f"Feasibility verdict: **{verdict}**")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Candidate events", metrics.get("candidate_events"))
        m2.metric("Event hotels", metrics.get("event_hotels"))
        m3.metric("Exposure > 0", metrics.get("events_exposure_gt0"))
        m4.metric("Exposure = 0", metrics.get("events_exposure_eq0"))
        st.markdown(
            f"- Main Δ threshold (fixed a priori): **{metrics.get('main_delta_threshold')}**\n"
            f"- Valid hotel-quarter-aspect cells: **{metrics.get('valid_cells')}**\n"
            f"- Hotels with ≥4 periods: **{metrics.get('hotels_with_enough_coverage')}**\n"
            f"- Change term: **review-perceived aspect change** (not managerial intervention)"
        )
        cols = st.columns(3)
        for i, name in enumerate(
            ["verdict_summary.png", "peer_exposure_distribution.png", "delta_q_distribution.png"]
        ):
            p = fig_dir / name
            if p.exists():
                cols[i % 3].image(str(p), use_container_width=True)
        with st.expander("Full feasibility metrics JSON"):
            st.json(metrics)
    else:
        st.info(
            "Temporal feasibility artifacts not built yet. "
            "Expected: panel coverage, candidate changes, peer-exposure, GREEN/AMBER/RED."
        )

    st.markdown("### Predictive pilot on temporal holdout")
    if pred_metrics.exists():
        pm = json.loads(pred_metrics.read_text(encoding="utf-8"))
        if pm.get("skipped"):
            st.warning(
                f"Predictive pilot not available / gate not passed. "
                f"({pm.get('verdict') or pm.get('reason')})"
            )
        else:
            st.info(
                "Predictive association only — does **not** upgrade Manager Demo to PREDICTIVE "
                "and is **not** a causal effect."
            )
            models = pm.get("models") or {}
            st.dataframe(
                [
                    {"model": k, "MAE": v.get("mae"), "RMSE": v.get("rmse")}
                    for k, v in models.items()
                ],
                hide_index=True,
                use_container_width=True,
            )
            st.caption(
                f"Target: {pm.get('target')} · test periods: {pm.get('test_periods')} · "
                f"peer improves on persistence: {pm.get('peer_model_improves_on_persistence')}"
            )
            pred_fig = ROOT / "outputs" / "overnight" / "predictive_pilot" / "figures" / "mae_by_model.png"
            if pred_fig.exists():
                st.image(str(pred_fig), use_container_width=True)
    else:
        st.warning("Predictive pilot not available / gate not passed.")

    st.markdown("### What this lab can / cannot claim")
    st.markdown(
        """
**Can:** descriptive coverage; feasibility of temporal measurement; predictive association on holdout.
**Cannot:** causal peer interference; ROI; demand lift; calling geo neighbors validated competitors;
calling sentiment deltas managerial interventions.
"""
    )
    if gate_path.exists():
        with st.expander("GO / NO-GO detail"):
            st.markdown(gate_path.read_text(encoding="utf-8")[:6000])


def render_research_evidence_tab(st):
    st.subheader("Research Evidence")
    st.caption("Numbers come from outputs/autonomous/FACTS.json. Demo does not invent metrics.")
    facts_p = ROOT / "outputs" / "autonomous" / "FACTS.json"
    claims_p = ROOT / "FINAL_CLAIMS_LEDGER.md"
    if not claims_p.exists():
        claims_p = ROOT / "outputs" / "autonomous" / "CLAIMS_LEDGER.md"
    if facts_p.exists():
        facts = json.loads(facts_p.read_text(encoding="utf-8"))
        waves = facts.get("waves") or {}
        w1, w2, w4, w6 = waves.get("1") or {}, waves.get("2") or {}, waves.get("4") or {}, waves.get("6") or {}
        st.info("Manager page remains DESCRIPTIVE unless the claims ledger upgrades it. No causal effect / ROI / demand lift.")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Measurement", w1.get("measurement_verdict", "n/a"))
        c2.metric("Strict events", w2.get("strict_crossfit_events", "n/a"))
        c3.metric("Peer prediction", w4.get("peer_predictive_claim", "n/a"))
        c4.metric("Paper track", w6.get("selected_track", "n/a"))
        st.caption(f"FACTS sha256 `{str(facts.get('facts_sha256') or '')[:16]}…` · legacy permissive events = {w2.get('legacy_permissive_event_count')}")
        st.json({
            "complete_periods": w1.get("complete_periods"),
            "partial_periods": w1.get("partial_periods"),
            "strict_verdict": w2.get("verdict"),
            "not_causal": True,
        })
    else:
        st.warning("Autonomous FACTS.json not built yet.")
    if claims_p.exists():
        with st.expander("Claims Ledger"):
            st.markdown(claims_p.read_text(encoding="utf-8")[:8000])


def main():
    import streamlit as st

    st.set_page_config(page_title="Provider Demo + Temporal Lab", layout="wide")
    snap, cfg = _load()
    st.title("Actionability-Aware Manager Demo + Temporal Feasibility Lab")
    tab1, tab2, tab3 = st.tabs([
        "Manager Diagnostic Demo",
        "Temporal Research Feasibility Lab",
        "Research Evidence",
    ])
    with tab1:
        render_manager_tab(st, snap, cfg)
    with tab2:
        render_temporal_tab(st)
    with tab3:
        render_research_evidence_tab(st)


if __name__ == "__main__":
    main()

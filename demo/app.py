"""Streamlit: Competition-Aware Provider-Side Hotel Improvement Demo."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from demo.config import ROOT, load_config
from demo.data_adapter import eligible_hotels, load_snapshot
from demo.evidence import BANNER, decide_evidence_level
from demo.scoring import all_policies, ranking_under_intensity

SNAPSHOT_PATH = ROOT / "outputs" / "night_demo" / "demo_snapshot.json"

LIMITATIONS = """
- Review counts are **not** bookings or demand.
- Aspect net is review sentiment, **not** a verified management intervention.
- Peer sets are DBSCAN(geo) ∩ price-tier labels, **not** validated economic substitutes.
- Competition-Aware scores are a **transparent heuristic**. The peer-exposure slider is **assumed / illustrative**.
- No event study, placebo, or causal estimate is in this repository.
- Coverage is Brussels centre only (3 valid sets, 24 hotels with aspects).
"""


def _load():
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(
            f"Missing {SNAPSHOT_PATH}. Run: python3 scripts/build_demo_snapshot.py"
        )
    snap = load_snapshot(SNAPSHOT_PATH)
    cfg = snap.get("config") or load_config()
    return snap, cfg


def main():
    import streamlit as st

    st.set_page_config(page_title="Provider-side hotel improvement Demo", layout="wide")
    snap, cfg = _load()
    ev = decide_evidence_level(snap)
    labels = cfg.get("aspect_labels") or {}
    hotels = eligible_hotels(snap)

    st.title("Competition-Aware Provider-Side Hotel Improvement")
    st.caption("Manager-facing Demo · evidence from real FYP processed tables · no external API")

    st.error(ev["banner"])
    with st.expander("Why this evidence level, and what we cannot claim", expanded=True):
        st.markdown(f"**Level:** `{ev['level']}`")
        st.write(ev["why"])
        st.markdown("**Cannot claim tonight:**")
        for c in ev["cannot_claim"]:
            st.markdown(f"- {c}")
        st.markdown(
            f"**Data files:** `{snap['sources']['aspect_features']}` · "
            f"`{snap['sources']['compsets']}` · `{snap['sources']['review_aspects_jsonl']}`"
        )
        st.caption("Synthetic mode is off. Snapshot flag: " + str(snap.get("synthetic")))

    cities = sorted({h["city"] for h in hotels})
    sets = sorted({h["compset_id"] for h in hotels})
    c1, c2, c3 = st.columns(3)
    with c1:
        city = st.selectbox("City", cities, index=0)
    hotels_c = [h for h in hotels if h["city"] == city]
    with c2:
        cs = st.selectbox("Competition set (peer set)", ["(all)"] + sorted({h["compset_id"] for h in hotels_c}))
    hotels_f = hotels_c if cs == "(all)" else [h for h in hotels_c if h["compset_id"] == cs]
    with c3:
        names = {h["hotel_name"]: h["hotel_id"] for h in hotels_f}
        name = st.selectbox("Hotel", list(names.keys()))
    hotel = next(h for h in hotels_f if h["hotel_id"] == names[name])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Peer set size", hotel["compset_size"])
    m2.metric("Reviews (ABSA-labelled)", hotel["n_reviews"])
    m3.metric("Low-rating reviews (<7)", hotel["n_negative"])
    m4.metric("Price tier", hotel["price_tier"] or "n/a")
    st.caption(
        f"hotel_id=`{hotel['hotel_id']}` · compset_id=`{hotel['compset_id']}` · "
        f"star={hotel['star'] if hotel['star'] is not None else 'missing'} · "
        f"price={'proxy ' if hotel['price_is_proxy'] else ''}"
        f"{hotel['price_imputed'] if hotel['price_imputed'] is not None else 'missing'}"
    )

    st.subheader("Hotel vs peers")
    rows = []
    for a in cfg["aspects"]:
        rec = hotel["aspects"][a]
        rows.append({
            "aspect": labels.get(a, a),
            "hotel_net": rec.get("net"),
            "peer_median": rec.get("peer_median_net"),
            "gap (peer−hotel)": rec.get("gap"),
            "percentile_in_set": rec.get("percentile"),
            "mentions": rec.get("mention_count"),
            "neg_mentions": rec.get("neg_mentions"),
            "neg_rate": rec.get("neg_rate"),
            "reliability": rec.get("reliability"),
            "peer_weakest_share": rec.get("peer_weakest_share"),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    # simple comparison bars via streamlit
    chart_data = {
        labels.get(a, a): {
            "hotel": hotel["aspects"][a].get("net") if hotel["aspects"][a].get("net") is not None else 0,
            "peer_median": hotel["aspects"][a].get("peer_median_net") if hotel["aspects"][a].get("peer_median_net") is not None else 0,
        }
        for a in cfg["aspects"]
        if hotel["aspects"][a].get("net") is not None
    }
    st.bar_chart(chart_data)

    st.subheader("Recommendation comparison")
    intensity = st.slider(
        "Assumed share of peers improving the same aspect (SCENARIO, not estimated)",
        min_value=0.0, max_value=1.0, value=float(cfg["scenario"]["default_intensity"]), step=0.05,
        help="Illustrative crowding penalty. Does not come from a fitted lambda.",
    )
    policies = all_policies(hotel, cfg, assumed_intensity=intensity)
    cols = st.columns(4)
    order = ["fix_weakest", "largest_peer_gap", "most_criticized", "competition_aware"]
    for col, key in zip(cols, order):
        p = policies[key]
        chosen = p["chosen_aspect"]
        lab = labels.get(chosen, chosen) if chosen else "n/a"
        col.metric(p["label"], lab)
        col.caption(p["rule"])

    chosen_list = [(k, policies[k]["chosen_aspect"]) for k in order]
    agree = len({c for _, c in chosen_list}) == 1
    st.write("**Agreement:** " + ("all four strategies pick the same aspect." if agree else "strategies **disagree** — see below."))
    if not agree:
        fw = policies["fix_weakest"]["chosen_aspect"]
        ca = policies["competition_aware"]["chosen_aspect"]
        if fw != ca:
            st.info(
                f"Competition-Aware picks **{labels.get(ca, ca)}** instead of Fix Weakest "
                f"**{labels.get(fw, fw)}** because it mixes peer gap, criticism, mention reliability, "
                f"and the assumed crowding term (intensity={intensity:.2f})."
            )

    st.markdown("##### Competition-Aware score table (heuristic)")
    scores0 = ranking_under_intensity(hotel, cfg, 0.0)
    scoresI = ranking_under_intensity(hotel, cfg, intensity)
    st.table({
        "aspect": [labels.get(a, a) for a, _ in scoresI],
        "score@intensity": [round(s, 4) for _, s in scoresI],
        "score@0": [round(dict(scores0).get(a, 0.0), 4) for a, _ in scoresI],
        "rank_change": [
            [x for x, _ in scores0].index(a) - i for i, (a, _) in enumerate(scoresI)
        ],
    })
    st.caption(cfg.get("formula", ""))
    st.caption(
        "Weights (conf/demo.json): "
        f"gap={cfg['weights']['gap']}, criticism={cfg['weights']['criticism']}, "
        f"unreliable={cfg['weights']['unreliable']}, "
        f"assumed crowding_weight={cfg['scenario']['crowding_weight']}. "
        "peer_weakest_share = share of peers whose own weakest eligible aspect is this aspect."
    )

    st.subheader("Peer-exposure scenario")
    st.warning("SCENARIO ANALYSIS — assumed / illustrative. Not an empirical crowding curve.")
    grid = [0.0, 0.25, 0.5, 0.75, 1.0]
    scen_rows = []
    for g in grid:
        rnk = ranking_under_intensity(hotel, cfg, g)
        scen_rows.append({
            "assumed_intensity": g,
            "top_aspect": labels.get(rnk[0][0], rnk[0][0]) if rnk else None,
            "top_score": round(rnk[0][1], 4) if rnk else None,
        })
    st.dataframe(scen_rows, hide_index=True, use_container_width=True)

    st.subheader("Explanation / provenance")
    st.json({
        "evidence_level": ev["level"],
        "hotel_id": hotel["hotel_id"],
        "hotel_url": hotel["hotel_url"],
        "compset_id": hotel["compset_id"],
        "peer_ids": hotel["peer_ids"],
        "n_reviews": hotel["n_reviews"],
        "source_files": hotel["source_files"],
        "chosen": {k: policies[k]["chosen_aspect"] for k in order},
        "config": "conf/demo.json",
        "snapshot": str(SNAPSHOT_PATH.relative_to(ROOT)),
        "synthetic": snap.get("synthetic"),
    })

    st.subheader("Limitations")
    st.markdown(LIMITATIONS)


if __name__ == "__main__":
    main()

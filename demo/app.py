"""Streamlit: hotel manager decision demo + temporal research workbench."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from demo.config import ROOT, load_actionability_config, load_config
from demo.data_adapter import eligible_hotels, load_snapshot
from demo.evidence import decide_evidence_level
from demo.i18n import DEFAULT_LANGUAGE, LANGUAGE_LABELS, SUPPORTED_LANGUAGES, get_locale, ui_text
from demo.scoring import (
    all_policies,
    criticism_metrics,
    explain_action_vs_diagnostic,
    ranking_under_intensity,
)
from demo.theme import apply_theme, render_header, render_recommendation, render_section_header

SNAPSHOT_PATH = ROOT / "outputs" / "night_demo" / "demo_snapshot.json"

OVERNIGHT_FEAS = ROOT / "outputs" / "overnight" / "feasibility"
OVERNIGHT_TABLES = OVERNIGHT_FEAS / "tables"
PRED_METRICS_PATH = ROOT / "outputs" / "overnight" / "predictive_pilot" / "metrics.json"

MGR_CITY_CANONICAL = "mgr_city"
MGR_CS_CANONICAL = "mgr_cs"


def hydrate_locale_select_state(
    session_state: dict,
    canonical_key: str,
    widget_key: str,
    options: list,
    default,
):
    """Validate canonical ID, then copy it into the locale-specific widget key before render."""
    if not options:
        return default
    canonical = session_state.get(canonical_key)
    if canonical not in options:
        canonical = default
        session_state[canonical_key] = canonical
    session_state[widget_key] = canonical
    return canonical


def sync_canonical_from_locale_widget(
    session_state: dict,
    canonical_key: str,
    widget_key: str,
) -> None:
    """Persist the locale widget choice into the language-neutral canonical key."""
    session_state[canonical_key] = session_state[widget_key]


def _locale_widget_key(base: str, lang: str) -> str:
    return f"{base}_{lang}"


def _make_locale_sync(st, canonical_key: str, widget_key: str):
    def _sync() -> None:
        sync_canonical_from_locale_widget(st.session_state, canonical_key, widget_key)

    return _sync


def _load():
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(
            f"Missing {SNAPSHOT_PATH}. Run: python3 scripts/build_demo_snapshot.py"
        )
    snap = load_snapshot(SNAPSHOT_PATH)
    cfg = load_config()
    snap_cfg = snap.get("config") or {}
    cfg = {**snap_cfg, **cfg}
    return snap, cfg


def _load_facts() -> dict | None:
    facts_p = ROOT / "outputs" / "autonomous" / "FACTS.json"
    if not facts_p.exists():
        return None
    return json.loads(facts_p.read_text(encoding="utf-8"))


def _facts_waves(facts: dict | None) -> dict:
    return (facts or {}).get("waves") or {}


def _legacy_event_count(loc, waves: dict) -> str:
    w0, w2 = waves.get("0") or {}, waves.get("2") or {}
    val = w2.get("legacy_permissive_event_count", w0.get("legacy_event_count_reproduced"))
    return loc.fmt_na(val)


def _strict_event_count(loc, waves: dict) -> str:
    w2 = waves.get("2") or {}
    val = w2.get("strict_crossfit_events")
    if val is None:
        val = (w2.get("metrics") or {}).get("n")
    return loc.fmt_na(val)


def _download_button(st, label: str, path: Path, mime: str):
    if path.exists():
        st.download_button(
            label,
            data=path.read_bytes(),
            file_name=path.name,
            mime=mime,
        )


def _render_verdict_event_chart(st, loc, metrics: dict):
    keys = [
        ("candidate_events", loc.UI["chart_verdict_candidate"]),
        ("events_exposure_gt0", loc.UI["chart_verdict_with_ref"]),
        ("events_exposure_eq0", loc.UI["chart_verdict_without_ref"]),
        ("event_hotels", loc.UI["chart_verdict_hotels"]),
    ]
    rows = [
        {loc.UI["chart_verdict_metric_col"]: label, loc.UI["chart_verdict_count_col"]: metrics.get(key)}
        for key, label in keys
        if metrics.get(key) is not None
    ]
    if not rows:
        st.info(loc.UI["chart_verdict_no_data"])
        return
    import pandas as pd

    df = pd.DataFrame(rows).set_index(loc.UI["chart_verdict_metric_col"])
    st.caption(loc.UI["chart_verdict_caption"])
    st.bar_chart(df)


def _render_peer_exposure_chart(st, loc):
    path = OVERNIGHT_TABLES / "candidate_events.csv"
    if not path.exists():
        st.info(loc.UI["chart_peer_missing"])
        return
    import pandas as pd

    df = pd.read_csv(path, usecols=["peer_exposure"])
    series = df["peer_exposure"].dropna()
    if series.empty:
        st.info(loc.UI["chart_peer_empty"])
        return
    counts = series.value_counts(bins=30, sort=False)
    chart_df = pd.DataFrame(
        {loc.UI["chart_freq_col"]: counts.values},
        index=[loc.format_hist_bin(i) for i in counts.index],
    )
    chart_df.index.name = loc.UI["chart_peer_bin_col"]
    st.caption(loc.UI["chart_peer_caption"])
    st.bar_chart(chart_df, sort=False)


def _render_delta_q_chart(st, loc):
    path = OVERNIGHT_TABLES / "delta_q_sample.csv"
    if not path.exists():
        st.info(loc.UI["chart_delta_missing"])
        return
    import pandas as pd

    df = pd.read_csv(path, usecols=["delta_q"])
    series = df["delta_q"].dropna()
    if series.empty:
        st.info(loc.UI["chart_delta_empty"])
        return
    counts = series.value_counts(bins=30, sort=False)
    chart_df = pd.DataFrame(
        {loc.UI["chart_freq_col"]: counts.values},
        index=[loc.format_hist_bin(i) for i in counts.index],
    )
    chart_df.index.name = loc.UI["chart_delta_bin_col"]
    st.caption(loc.UI["chart_delta_caption"])
    st.bar_chart(chart_df, sort=False)


def _render_aspect_peer_chart(st, loc, hotel: dict, cfg: dict, albl) -> None:
    """Grouped horizontal bars: hotel tendency vs comparison median per aspect."""
    import pandas as pd

    aspect_col = loc.UI["chart_aspect_col"]
    series_own = loc.UI["chart_series_own"]
    series_peer = loc.UI["chart_series_peer"]
    x_title = loc.UI["chart_sentiment_axis"]
    legend_title = loc.UI["chart_legend"]

    aspect_order = [albl(a) for a in cfg["aspects"]]
    rows: list[dict] = []
    for a in cfg["aspects"]:
        rec = hotel.get("aspects", {}).get(a, {})
        net = rec.get("net")
        peer = rec.get("peer_median_net")
        label = albl(a)
        if net is not None:
            rows.append({aspect_col: label, "series": series_own, "value": float(net)})
        if peer is not None:
            rows.append({aspect_col: label, "series": series_peer, "value": float(peer)})

    if not rows:
        st.info(loc.UI["chart_no_data"])
        return

    try:
        import altair as alt
    except ImportError:
        st.caption(loc.UI["chart_altair_fallback"])
        st.dataframe(
            pd.DataFrame(rows).pivot_table(
                index=aspect_col, columns="series", values="value", aggfunc="first"
            ).reindex(aspect_order),
            use_container_width=True,
        )
        return

    df = pd.DataFrame(rows)
    chart = (
        alt.Chart(df)
        .mark_bar(height=14)
        .encode(
            y=alt.Y(f"{aspect_col}:N", sort=aspect_order, axis=alt.Axis(title=None)),
            x=alt.X(
                "value:Q",
                scale=alt.Scale(domain=[-1, 1], nice=False),
                title=x_title,
            ),
            color=alt.Color("series:N", scale=alt.Scale(domain=[series_own, series_peer], range=["#5EEAD4", "#8DA9D9"]), legend=alt.Legend(title=None, orient="top", columns=1)),
            yOffset=alt.YOffset("series:N"),
            tooltip=[
                alt.Tooltip(f"{aspect_col}:N", title=aspect_col),
                alt.Tooltip("series:N", title=legend_title),
                alt.Tooltip("value:Q", title=x_title, format=".3f"),
            ],
        )
        .properties(height=max(240, len(cfg["aspects"]) * 44))
    )
    st.altair_chart(chart, use_container_width=True)


def _render_mae_chart(st, loc, models: dict):
    if not models:
        st.info(loc.UI["chart_mae_no_data"])
        return
    import pandas as pd

    rows = [
        {loc.UI["col_model"]: loc.model_name(k), "MAE": v.get("mae")}
        for k, v in models.items()
        if v.get("mae") is not None
    ]
    if not rows:
        st.info(loc.UI["chart_mae_empty"])
        return
    mae_col = loc.mae_column_label()
    df = pd.DataFrame(rows).set_index(loc.UI["col_model"]).rename(columns={"MAE": mae_col})
    st.caption(loc.UI["chart_mae_caption"])
    st.bar_chart(df[[mae_col]])


def render_manager_tab(st, loc, snap, cfg):
    ev = decide_evidence_level(snap)
    labels = cfg.get("aspect_labels") or {}
    act = load_actionability_config()["aspects"]
    hotels = eligible_hotels(snap)
    snap_hotel_count = len(snap.get("hotels") or [])
    eligible_count = len(hotels)

    def albl(a: str) -> str:
        return loc.aspect_label(a, labels.get(a, a))

    st.caption(loc.UI["recommendation_evidence_note"])

    lang = st.session_state.get("ui_language", DEFAULT_LANGUAGE)
    city_widget_key = _locale_widget_key(MGR_CITY_CANONICAL, lang)
    cs_widget_key = _locale_widget_key(MGR_CS_CANONICAL, lang)

    cities = sorted({h["city"] for h in hotels})
    default_city = cities[0] if cities else None
    hydrate_locale_select_state(
        st.session_state,
        MGR_CITY_CANONICAL,
        city_widget_key,
        cities,
        default_city,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.selectbox(
            loc.UI["city"],
            cities,
            key=city_widget_key,
            format_func=loc.city_label,
            on_change=_make_locale_sync(st, MGR_CITY_CANONICAL, city_widget_key),
        )
    city = st.session_state[MGR_CITY_CANONICAL]
    hotels_c = [h for h in hotels if h["city"] == city]

    cs_options = ["(all)"] + sorted({h["compset_id"] for h in hotels_c})
    hydrate_locale_select_state(
        st.session_state,
        MGR_CS_CANONICAL,
        cs_widget_key,
        cs_options,
        "(all)",
    )
    with c2:
        st.selectbox(
            loc.UI["peer_group"],
            cs_options,
            key=cs_widget_key,
            format_func=loc.compset_label,
            help=loc.UI["peer_group_help"],
            on_change=_make_locale_sync(st, MGR_CS_CANONICAL, cs_widget_key),
        )
    cs = st.session_state[MGR_CS_CANONICAL]
    hotels_f = hotels_c if cs == "(all)" else [h for h in hotels_c if h["compset_id"] == cs]
    with c3:
        names = {h["hotel_name"]: h["hotel_id"] for h in hotels_f}
        name = st.selectbox(loc.UI["hotel"], list(names.keys()), key="mgr_hotel")
    hotel = next(h for h in hotels_f if h["hotel_id"] == names[name])

    st.markdown(f"### {hotel['hotel_name']}")
    st.caption(
        ui_text(loc, "snapshot_caption", total=snap_hotel_count, eligible=eligible_count)
    )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(loc.UI["metric_peer_count"], hotel["compset_size"])
    m2.metric(loc.UI["metric_reviews"], hotel["n_reviews"])
    m3.metric(loc.UI["metric_low_reviews"], hotel["n_negative"])
    m4.metric(loc.UI["metric_price_range"], loc.price_tier_label(hotel.get("price_tier")))

    expl = explain_action_vs_diagnostic(hotel, cfg)
    render_section_header(
        st, loc.UI["section_recommendation"], css_class="fyp-section-header--emphasis"
    )
    rec_aspect = (
        albl(expl["actionable_recommendation"])
        if expl["actionable_recommendation"]
        else loc.UI["recommendation_none"]
    )
    loc_expl = loc.build_recommendation_explanation(expl, hotel, albl)
    if loc_expl:
        rec_body = loc_expl
    elif expl["diagnostic_aspect"]:
        rec_body = loc.UI["recommendation_fallback_actionable"]
    else:
        rec_body = loc.UI["recommendation_fallback_none"]
    render_recommendation(
        st,
        rec_aspect,
        rec_body,
        reliability_text=loc.UI["recommendation_evidence_note"],
        aria_label=loc.UI["recommendation_aria"],
    )

    render_section_header(st, loc.UI["section_compare"])
    rows = []
    for a in cfg["aspects"]:
        rec = hotel["aspects"][a]
        meta = act.get(a, {})
        rows.append({
            loc.UI["col_aspect"]: albl(a),
            loc.UI["col_actionability"]: loc.actionability_label(meta.get("actionability_level")),
            loc.UI["col_direct_action"]: loc.fmt_bool(meta.get("eligible_for_direct_action")),
            loc.UI["col_own_sentiment"]: rec.get("net"),
            loc.UI["col_peer_median"]: rec.get("peer_median_net"),
            loc.UI["col_gap"]: rec.get("gap"),
            loc.UI["col_percentile"]: rec.get("percentile"),
            loc.UI["col_mentions"]: rec.get("mention_count"),
            loc.UI["col_neg_mentions"]: rec.get("neg_mentions"),
            loc.UI["col_neg_rate"]: rec.get("neg_rate"),
            loc.UI["col_neg_per_review"]: criticism_metrics(hotel, a)["neg_per_review"],
            loc.UI["col_reliability"]: rec.get("reliability"),
        })
    _render_aspect_peer_chart(st, loc, hotel, cfg, albl)
    st.caption(loc.UI["chart_caption"])
    with st.expander(loc.UI["expander_detail_table"], expanded=False):
        st.dataframe(rows, use_container_width=True, hide_index=True)

    render_section_header(st, loc.UI["section_policies"])
    st.caption(loc.UI["policies_caption"])
    with st.expander(loc.UI["expander_scenario_try"], expanded=False):
        st.caption(loc.UI["expander_scenario_try_caption"])
        intensity = st.slider(
            loc.UI["slider_label"],
            min_value=0.0,
            max_value=1.0,
            value=float(cfg["scenario"]["default_intensity"]),
            step=0.05,
            help=loc.UI["slider_help"],
            key="mgr_intensity",
        )
    if "mgr_intensity" not in st.session_state:
        intensity = float(cfg["scenario"]["default_intensity"])
    else:
        intensity = float(st.session_state["mgr_intensity"])
    policies = all_policies(hotel, cfg, assumed_intensity=intensity)
    order = ["fix_weakest", "largest_peer_gap", "most_criticized", "peer_relative"]
    cols = st.columns(4)
    for col, key in zip(cols, order):
        p = policies[key]
        chosen = p["chosen_aspect"]
        col.metric(
            loc.policy_label(key, p.get("label")),
            albl(chosen) if chosen else loc.UI["recommendation_none"],
        )
        col.caption(loc.policy_summary(key))

    with st.expander(loc.UI["expander_calculation"], expanded=False):
        for key in order:
            st.markdown(f"**{loc.policy_label(key)}**")
            st.caption(loc.policy_rule(key, policies[key].get("rule"), cfg))
        st.caption(loc.formula_caption(cfg))
        st.caption(loc.weights_caption(cfg))
        st.markdown(f"**{loc.UI['expander_formula_terms']}**")
        st.markdown(loc.SCORE_TERM_DEFINITIONS)

    pr = policies["peer_relative"]
    with st.expander(loc.UI["expander_scores"], expanded=False):
        st.caption(loc.UI["expander_scores_caption"])
        st.markdown(f"##### {loc.policy_label('peer_relative', pr.get('label'))} — {loc.UI['expander_score_table']}")
        scores0 = ranking_under_intensity(hotel, cfg, 0.0)
        scoresI = ranking_under_intensity(hotel, cfg, intensity)
        st.table({
            loc.UI["col_aspect"]: [albl(a) for a, _ in scoresI],
            ui_text(loc, "col_score_at_intensity", intensity=intensity): [
                round(s, 4) for _, s in scoresI
            ],
            loc.UI["col_score_at_zero"]: [
                round(dict(scores0).get(a, 0.0), 4) for a, _ in scoresI
            ],
        })
        st.markdown(f"##### {loc.UI['expander_scenario']}")
        st.caption(loc.UI["expander_scenario_caption"])
        scen_rows = []
        for g in (0.0, 0.25, 0.5, 0.75, 1.0):
            rnk = ranking_under_intensity(hotel, cfg, g)
            scen_rows.append({
                loc.UI["col_assumed_intensity"]: g,
                loc.UI["col_top_aspect"]: albl(rnk[0][0]) if rnk else None,
                loc.UI["col_top_score"]: round(rnk[0][1], 4) if rnk else None,
            })
        st.dataframe(scen_rows, hide_index=True, use_container_width=True)

    with st.expander(loc.UI["expander_criticism"]):
        crit_rows = []
        for a in cfg["aspects"]:
            if a not in hotel["aspects"]:
                continue
            m = criticism_metrics(hotel, a)
            crit_rows.append({
                loc.UI["col_aspect"]: albl(a),
                loc.UI["col_neg_mentions"]: m["neg_mentions"],
                loc.UI["col_neg_rate"]: m["neg_rate"],
                loc.UI["col_neg_per_review"]: round(m["neg_per_review"], 4),
                loc.UI["col_actionable"]: loc.fmt_bool(
                    act.get(a, {}).get("eligible_for_direct_action")
                ),
            })
        st.dataframe(crit_rows, hide_index=True, use_container_width=True)
        st.caption(loc.UI["expander_criticism_caption"])

    with st.expander(loc.UI["expander_annotation"], expanded=False):
        st.markdown(loc.MODEL_ANNOTATION_BOUNDARY_EXPANDER)

    with st.expander(loc.UI["expander_provenance"], expanded=False):
        prov_rows = [
            {loc.UI["col_field"]: loc.UI["prov_evidence_level"], loc.UI["col_value"]: loc.evidence_level_label(ev["level"])},
            {loc.UI["col_field"]: loc.UI["prov_hotel_id"], loc.UI["col_value"]: hotel["hotel_id"]},
            {loc.UI["col_field"]: loc.UI["prov_compset_id"], loc.UI["col_value"]: hotel["compset_id"]},
            {
                loc.UI["col_field"]: loc.UI["prov_diagnostic_aspect"],
                loc.UI["col_value"]: albl(expl["diagnostic_aspect"])
                if expl["diagnostic_aspect"]
                else loc.UI["recommendation_none"],
            },
            {
                loc.UI["col_field"]: loc.UI["prov_action_aspect"],
                loc.UI["col_value"]: albl(expl["actionable_recommendation"])
                if expl["actionable_recommendation"]
                else loc.UI["recommendation_none"],
            },
            {
                loc.UI["col_field"]: loc.UI["prov_policy_selection"],
                loc.UI["col_value"]: loc.format_policy_selection(policies, order, albl),
            },
            {loc.UI["col_field"]: loc.UI["prov_config"], loc.UI["col_value"]: "conf/demo.json"},
            {
                loc.UI["col_field"]: loc.UI["prov_actionability_config"],
                loc.UI["col_value"]: "conf/actionability.json",
            },
            {
                loc.UI["col_field"]: loc.UI["prov_synthetic"],
                loc.UI["col_value"]: loc.fmt_bool(snap.get("synthetic")),
            },
        ]
        st.dataframe(prov_rows, hide_index=True, use_container_width=True)

    with st.expander(loc.UI["evidence_expander"], expanded=False):
        st.markdown(f"**{loc.UI['evidence_level_prefix']}** {loc.evidence_level_label(ev['level'])}")
        st.write(loc.evidence_why(ev["level"], ev["why"]))
        for c in loc.CANNOT_CLAIM_ZH:
            st.markdown(f"- {c}")
        st.caption(
            f"`{snap['sources']['aspect_features']}` · "
            f"`{snap['sources']['compsets']}` · `{snap['sources']['review_aspects_jsonl']}`"
        )

    if not hotels:
        st.info(loc.UI["no_eligible_hotels"])
        return

    with st.expander(loc.UI["expander_limitations"], expanded=False):
        st.markdown(loc.LIMITATIONS_ZH)


def render_temporal_tab(st, loc):
    st.subheader(loc.UI["temporal_subheader"])
    st.caption(loc.UI["temporal_caption"])
    waves = _facts_waves(_load_facts())
    w2, w5 = waves.get("2") or {}, waves.get("5") or {}
    legacy_n = _legacy_event_count(loc, waves)
    strict_n = _strict_event_count(loc, waves)
    strict_verdict = loc.strict_verdict_label(w2.get("verdict"))
    evt_strength = loc.event_study_strength_label(w5.get("classification"))
    st.warning(
        ui_text(
            loc,
            "temporal_warning",
            legacy_n=legacy_n,
            strict_n=strict_n,
            verdict=strict_verdict,
            evt_strength=evt_strength,
        )
    )

    gate_path = OVERNIGHT_FEAS / "GO_NO_GO.md"
    metrics_path = OVERNIGHT_FEAS / "feasibility_metrics.json"
    panel_manifest = ROOT / "outputs" / "overnight" / "temporal_panel" / "panel_manifest.json"
    peer_manifest = ROOT / "outputs" / "overnight" / "peer_sets" / "peer_set_manifest.json"

    if panel_manifest.exists():
        pm = json.loads(panel_manifest.read_text(encoding="utf-8"))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(loc.UI["metric_quarter_rows"], pm.get("quarter_rows"))
        c2.metric(loc.UI["metric_event_hotels"], pm.get("quarter_hotels"))
        c3.metric(loc.UI["city"], pm.get("cities"))
        c4.metric(loc.UI["metric_valid_mentions"], pm.get("valid_mention_cells_quarter"))
        st.caption(
            f"prior_strength={pm.get('prior_strength_main')} · "
            f"sha256 `{str(pm.get('source_sha256', ''))[:12]}…`"
        )
    else:
        st.info(loc.UI["temporal_panel_missing"])

    if peer_manifest.exists():
        peers = json.loads(peer_manifest.read_text(encoding="utf-8"))
        st.markdown(f"### {loc.UI['temporal_peer_section']}")
        st.write(
            ui_text(
                loc,
                "temporal_peer_summary",
                k=peers.get("main_k"),
                hotels=peers.get("n_hotels"),
                cities=peers.get("n_cities"),
            )
        )

    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        verdict = metrics.get("verdict", "UNKNOWN")
        vlabel = loc.feasibility_verdict_label(verdict)
        if verdict == "GREEN":
            st.success(ui_text(loc, "temporal_feasibility_green", label=vlabel))
        elif verdict == "AMBER":
            st.warning(ui_text(loc, "temporal_feasibility_amber", label=vlabel))
        else:
            st.error(ui_text(loc, "temporal_feasibility_red", label=vlabel))
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(loc.UI["metric_candidate_events"], metrics.get("candidate_events"))
        m2.metric(loc.UI["metric_event_hotels"], metrics.get("event_hotels"))
        m3.metric(loc.UI["metric_with_peer_ref"], metrics.get("events_exposure_gt0"))
        m4.metric(loc.UI["metric_without_peer_ref"], metrics.get("events_exposure_eq0"))
        st.markdown(
            ui_text(
                loc,
                "temporal_bullets",
                threshold=metrics.get("main_delta_threshold"),
                valid_cells=metrics.get("valid_cells"),
                coverage=metrics.get("hotels_with_enough_coverage"),
            )
        )
        st.markdown(f"#### {loc.UI['temporal_charts_heading']}")
        c_left, c_mid, c_right = st.columns(3)
        with c_left:
            _render_verdict_event_chart(st, loc, metrics)
        with c_mid:
            _render_peer_exposure_chart(st, loc)
        with c_right:
            _render_delta_q_chart(st, loc)

        with st.expander(loc.UI["expander_raw_feasibility"], expanded=False):
            st.caption(loc.UI["expander_raw_feasibility_caption"])
            _download_button(
                st, loc.UI["download_feasibility"], metrics_path, "application/json"
            )
    else:
        st.info(loc.UI["temporal_feasibility_missing"])

    st.markdown(f"### {loc.UI['temporal_predict_header']}")
    if PRED_METRICS_PATH.exists():
        pm = json.loads(PRED_METRICS_PATH.read_text(encoding="utf-8"))
        if pm.get("skipped"):
            st.warning(
                ui_text(
                    loc,
                    "temporal_predict_skipped",
                    reason=pm.get("verdict") or pm.get("reason") or loc.fmt_na(None),
                )
            )
        else:
            st.info(loc.UI["temporal_predict_info"])
            models = pm.get("models") or {}
            st.dataframe(
                [
                    {
                        loc.UI["col_model"]: loc.model_name(k),
                        loc.mae_column_label(): v.get("mae"),
                        loc.rmse_column_label(): v.get("rmse"),
                    }
                    for k, v in models.items()
                ],
                hide_index=True,
                use_container_width=True,
            )
            st.caption(
                ui_text(
                    loc,
                    "temporal_predict_caption",
                    target=loc.target_label(pm.get("target")),
                    periods=pm.get("test_periods") or loc.fmt_na(None),
                    beats=loc.fmt_bool(pm.get("peer_model_improves_on_persistence")),
                )
            )
            _render_mae_chart(st, loc, models)
            _download_button(
                st,
                loc.UI["download_predict_metrics"],
                PRED_METRICS_PATH,
                "application/json",
            )
    else:
        st.warning(loc.UI["temporal_predict_missing"])

    st.markdown(f"### {loc.UI['temporal_claims_header']}")
    st.markdown(loc.UI["temporal_claims_body"])
    if gate_path.exists():
        with st.expander(loc.UI["expander_go_no_go"], expanded=False):
            st.caption(loc.UI["expander_go_no_go_caption"])
            _download_button(st, loc.UI["download_go_no_go"], gate_path, "text/markdown")


def render_research_evidence_tab(st, loc):
    st.subheader(loc.UI["research_subheader"])
    st.caption(loc.UI["research_caption"])
    facts_p = ROOT / "outputs" / "autonomous" / "FACTS.json"
    claims_p = ROOT / "outputs" / "autonomous" / "CLAIMS_LEDGER.md"
    facts_sha = ""

    if facts_p.exists():
        facts = json.loads(facts_p.read_text(encoding="utf-8"))
        facts_sha = str(facts.get("facts_sha256") or "")[:16]
        waves = facts.get("waves") or {}
        w0 = waves.get("0") or {}
        w1, w2, w4, w5, w6 = (
            waves.get("1") or {},
            waves.get("2") or {},
            waves.get("4") or {},
            waves.get("5") or {},
            waves.get("6") or {},
        )
        st.info(loc.UI["research_info"])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(loc.UI["metric_measurement"], loc.measurement_label(w1.get("measurement_verdict")))
        c2.metric(loc.UI["metric_strict_events"], loc.fmt_na(w2.get("strict_crossfit_events")))
        c3.metric(loc.UI["metric_peer_predictive"], loc.peer_predictive_label(w4.get("peer_predictive_claim")))
        track = w6.get("selected_track")
        c4.metric(
            loc.UI["metric_track"],
            f"{loc.UI['track_prefix']} {track}" if track else loc.fmt_na(None),
        )
        st.caption(loc.UI["metric_strict_events_caption"])
        st.caption(
            ui_text(
                loc,
                "research_facts_caption",
                legacy=w2.get(
                    "legacy_permissive_event_count",
                    w0.get("legacy_event_count_reproduced", loc.fmt_na(None)),
                ),
            )
        )

        st.markdown(f"#### {loc.UI['research_summary_heading']}")
        summary_rows = [
            {
                loc.UI["col_field"]: loc.UI["research_row_complete_periods"],
                loc.UI["col_value"]: ", ".join(w1.get("complete_periods") or []) or loc.fmt_na(None),
            },
            {
                loc.UI["col_field"]: loc.UI["research_row_partial_periods"],
                loc.UI["col_value"]: ", ".join(w1.get("partial_periods") or []) or loc.fmt_na(None),
            },
            {
                loc.UI["col_field"]: loc.UI["research_row_strict_verdict"],
                loc.UI["col_value"]: loc.strict_verdict_label(w2.get("verdict")),
            },
            {
                loc.UI["col_field"]: loc.UI["research_row_strict_count"],
                loc.UI["col_value"]: loc.fmt_na(
                    (w2.get("metrics") or {}).get("n", w2.get("strict_crossfit_events"))
                ),
            },
            {
                loc.UI["col_field"]: loc.UI["research_row_event_strength"],
                loc.UI["col_value"]: loc.event_study_strength_label(w5.get("classification")),
            },
            {
                loc.UI["col_field"]: ui_text(
                    loc, "research_row_track_formulation", track=track or loc.fmt_na(None)
                ),
                loc.UI["col_value"]: loc.track_formulation(track, w6),
            },
            {
                loc.UI["col_field"]: loc.UI["research_row_non_causal"],
                loc.UI["col_value"]: loc.UI["research_row_non_causal_value"],
            },
        ]
        st.dataframe(summary_rows, hide_index=True, use_container_width=True)

        st.markdown(
            ui_text(
                loc,
                "research_compare",
                legacy=_legacy_event_count(loc, waves),
                strict=_strict_event_count(loc, waves),
                peer=loc.peer_predictive_label(w4.get("peer_predictive_claim")),
                strength=loc.event_study_strength_label(w5.get("classification")),
            )
        )
    else:
        st.warning(loc.UI["research_facts_missing"])

    if claims_p.exists():
        md = claims_p.read_text(encoding="utf-8")
        rows = loc.parse_claims_ledger(md)
        st.markdown(f"#### {loc.UI['research_claims_heading']}")
        if rows:
            st.dataframe(
                [
                    {
                        loc.UI["col_claim_id"]: r["id"],
                        loc.UI["col_claim"]: r["claim_zh"],
                        loc.UI["col_status"]: r["status_zh"],
                        loc.UI["col_notes"]: r["notes"],
                    }
                    for r in rows
                ],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info(loc.UI["research_claims_empty"])
        with st.expander(loc.UI["expander_claims_raw"], expanded=False):
            st.caption(loc.UI["expander_claims_caption"])
            _download_button(st, loc.UI["download_claims"], claims_p, "text/markdown")
    else:
        st.warning(loc.UI["research_claims_missing"])

    if facts_p.exists():
        with st.expander(loc.UI["expander_facts_raw"], expanded=False):
            st.caption(ui_text(loc, "research_facts_sha_caption", sha=facts_sha))
            _download_button(st, loc.UI["download_facts"], facts_p, "application/json")

    _render_model_annotation_section(st, loc)

    with st.expander(loc.UI["expander_annotation"], expanded=False):
        st.markdown(loc.MODEL_ANNOTATION_BOUNDARY_EXPANDER)


def _render_model_annotation_section(st, loc):
    report_p = ROOT / loc.MODEL_ANNOTATION_REPORT_PATH
    st.markdown(f"#### {loc.UI['model_annotation_heading']}")
    if not report_p.exists():
        st.info(ui_text(loc, "model_annotation_missing", path=loc.MODEL_ANNOTATION_REPORT_PATH))
        st.caption(
            ui_text(loc, "model_annotation_private_note", path=loc.MODEL_ANNOTATION_PRIVATE_CSV)
        )
        return
    report = json.loads(report_p.read_text(encoding="utf-8"))
    if report.get("status") != "MODEL_AUDITED_REFERENCE":
        st.warning(loc.UI["model_annotation_unknown_status"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(loc.UI["model_annotation_metric_items"], loc.fmt_na(report.get("n_items")))
    c2.metric(loc.UI["model_annotation_metric_accepted"], loc.fmt_na(report.get("final_accepted_count")))
    c3.metric(loc.UI["model_annotation_metric_unresolved"], loc.fmt_na(report.get("final_unresolved_count")))
    c4.metric(loc.UI["model_annotation_metric_audited"], loc.fmt_na(report.get("audited_count")))
    st.caption(
        loc.format_model_agreement_caption(
            report.get("raw_agreement_rate"),
            report.get("cohen_kappa"),
        )
    )
    st.caption(
        f"{loc.model_annotation_status_label(report.get('status'))} · "
        f"`{str(report.get('source_hash') or '')[:12]}…` · "
        f"`{str(report.get('sample_hash') or '')[:12]}…`"
    )
    per_aspect = report.get("per_aspect_final_label_counts") or {}
    if per_aspect:
        import pandas as pd

        rows = []
        for aspect, counts in sorted(per_aspect.items()):
            row: dict = {loc.UI["col_aspect"]: loc.aspect_label(aspect, aspect)}
            for lab, col in loc.SENTIMENT_LABELS.items():
                row[col] = counts.get(lab, 0)
            rows.append(row)
        st.markdown(f"##### {loc.UI['model_annotation_per_aspect']}")
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(
        ui_text(loc, "model_annotation_footer", path=loc.MODEL_ANNOTATION_PRIVATE_CSV)
    )


def _render_language_selector(st):
    """Render language control; returns active locale module from session state."""
    col, _ = st.columns([1.2, 4])
    with col:
        st.selectbox(
            "Language / 语言",
            options=list(SUPPORTED_LANGUAGES),
            format_func=lambda code: LANGUAGE_LABELS[code],
            key="ui_language",
        )
    return get_locale(st.session_state.get("ui_language"))


def main():
    import streamlit as st

    if "ui_language" not in st.session_state:
        st.session_state.ui_language = DEFAULT_LANGUAGE
    loc = get_locale(st.session_state.ui_language)
    st.set_page_config(page_title=loc.UI["page_title"], layout="wide")
    apply_theme(st)
    loc = _render_language_selector(st)
    render_header(
        st,
        loc.UI["header_title"],
        loc.UI["header_desc"],
        loc.UI["header_badge"],
    )
    snap, cfg = _load()
    tab1, tab2, tab3 = st.tabs([
        loc.UI["tab_improvement"],
        loc.UI["tab_history"],
        loc.UI["tab_research"],
    ])
    with tab1:
        render_manager_tab(st, loc, snap, cfg)
    with tab2:
        render_temporal_tab(st, loc)
    with tab3:
        render_research_evidence_tab(st, loc)


if __name__ == "__main__":
    main()

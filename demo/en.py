"""English display strings for the Streamlit demo. Backend keys stay English."""
from __future__ import annotations

import re
from typing import Any, Callable, Mapping

# --- Aspects (7) ---
ASPECT_LABELS: dict[str, str] = {
    "location": "Location",
    "cleanliness": "Cleanliness",
    "breakfast": "Breakfast",
    "service": "Service",
    "noise": "Noise / quiet",
    "room": "Room",
    "value": "Value for money",
}

CITY_LABELS: dict[str, str] = {
    "Brussels": "Brussels",
    "Amsterdam": "Amsterdam",
    "Paris": "Paris",
    "London": "London",
    "Barcelona": "Barcelona",
    "Vienna": "Vienna",
    "Milan": "Milan",
    "Bruges": "Bruges",
    "Antwerp": "Antwerp",
    "Ghent": "Ghent",
}

PRICE_TIER_LABELS: dict[str, str] = {
    "low": "Lower",
    "mid": "Mid",
    "high": "Higher",
}

ACTIONABILITY_LEVEL_LABELS: dict[str, str] = {
    "immutable": "Not directly actionable",
    "high": "Highly actionable",
    "conditional": "Conditionally actionable",
    "medium": "Moderately actionable",
}

POLICY_SUMMARIES: dict[str, str] = {
    "fix_weakest": "Lowest overall tendency among actionable aspects",
    "largest_peer_gap": "Largest gap vs comparison median among actionable aspects",
    "most_criticized": "Most negative mentions among actionable aspects",
    "peer_relative": (
        "Balances review gap, negative-review share and review volume (design weights)"
    ),
}

POLICY_LABELS: dict[str, str] = {
    "fix_weakest": "Fix lowest-rated areas first",
    "largest_peer_gap": "Close the gap vs nearby hotels",
    "most_criticized": "Address the most complaints",
    "peer_relative": "Balance gap and review volume",
    "competition_aware": "Balance gap and review volume",
    "diagnostic_largest_gap": "Largest gap vs peers (diagnostic)",
}

LANG_CODE = "en"

UI: dict[str, str] = {
    "page_title": "Hotel Improvement Assistant",
    "header_title": "Hotel Improvement Assistant",
    "header_desc": "Pick a hotel to see what to improve first and what the suggestion is based on.",
    "header_badge": "Research demo",
    "lang_selector_label": "Language",
    "tab_improvement": "Improvement priorities",
    "tab_history": "Changes over time",
    "tab_research": "Research progress",
    "section_improvement_desc": "For managers · descriptive evidence",
    "evidence_expander": "Evidence level / what we cannot claim",
    "evidence_level_prefix": "Level:",
    "city": "City",
    "peer_group": "Comparison hotel group",
    "peer_group_help": "Nearby hotels chosen for research reference; not proven direct competitors.",
    "hotel": "Select hotel",
    "snapshot_caption": "Demo snapshot: {total} hotels; {eligible} meet display criteria.",
    "no_eligible_hotels": "No hotels in the demo snapshot meet display criteria; hotel selection and suggestions are unavailable. Check that the snapshot was built correctly.",
    "metric_peer_count": "Hotels in comparison group",
    "metric_reviews": "Reviews",
    "metric_low_reviews": "Low-score reviews",
    "metric_price_range": "Price range",
    "section_compare": "Your hotel vs comparison group",
    "chart_no_data": "Not enough aspect data for a comparison chart.",
    "chart_altair_fallback": "Chart library unavailable; table shows non-missing comparisons.",
    "chart_caption": "Closer to 1 means more positive mentions; closer to −1 means more negative. Aspects not mentioned are not judged.",
    "chart_aspect_col": "Aspect",
    "chart_series_own": "Your hotel",
    "chart_series_peer": "Comparison group median",
    "chart_sentiment_axis": "Overall positive vs negative tendency",
    "chart_legend": "Series",
    "expander_detail_table": "Detailed comparison table",
    "section_recommendation": "Suggested focus",
    "section_policies": "Policy comparison",
    "policies_caption": "Location and other non-actionable aspects are excluded. Cards show illustrative rankings, not revenue forecasts.",
    "expander_scenario_try": "Try a what-if scenario",
    "expander_scenario_try_caption": "Hypothetical only — not observed competition changes.",
    "expander_calculation": "How scores are calculated",
    "slider_label": "Assumed peer improvement intensity",
    "slider_help": "Hypothetical scenario value, not a fitted competition elasticity.",
    "recommendation_none": "None",
    "recommendation_fallback_actionable": "Based on gaps vs nearby hotels, complaint volume, and review counts, this aspect is the suggested focus.",
    "recommendation_fallback_none": "No clear weakness or actionable suggestion under current evidence.",
    "recommendation_evidence_note": "Suggestions come from past reviews; improving these areas has not been verified to raise scores or revenue.",
    "expander_scores": "Score breakdown, formula, and intensity scan",
    "expander_scores_caption": "“Score @0” uses default intensity; “Score @intensity” matches the slider.",
    "expander_score_table": "Score table",
    "expander_formula_terms": "Formula terms (optional)",
    "expander_scenario": "Crowding assumption (scenario analysis)",
    "expander_scenario_caption": "Scenario analysis — illustrative only. Not a causal estimate.",
    "expander_criticism": "Complaint metrics audit",
    "expander_criticism_caption": "“Most criticized” uses negative mention counts; rates and per-review metrics are for audit only.",
    "expander_annotation": "Model labeling and usage limits",
    "expander_provenance": "Data provenance",
    "expander_limitations": "Limitations and boundaries",
    "col_aspect": "Aspect",
    "col_actionability": "Actionability",
    "col_direct_action": "Direct action",
    "col_own_sentiment": "Your hotel",
    "col_peer_median": "Comparison median",
    "col_gap": "Gap (peer − yours)",
    "col_percentile": "Percentile",
    "col_mentions": "Mentions",
    "col_neg_mentions": "Negative mentions",
    "col_neg_rate": "Negative rate",
    "col_neg_per_review": "Negatives per review",
    "col_reliability": "Reliability",
    "col_score_at_intensity": "Score @ {intensity}",
    "col_score_at_zero": "Score @ 0",
    "col_assumed_intensity": "Assumed intensity",
    "col_top_aspect": "Top actionable aspect",
    "col_top_score": "Top score",
    "col_actionable": "Actionable",
    "col_field": "Field",
    "col_value": "Value",
    "prov_evidence_level": "Evidence level",
    "prov_hotel_id": "Hotel ID",
    "prov_compset_id": "Comparison group ID",
    "prov_diagnostic_aspect": "Diagnostic aspect",
    "prov_action_aspect": "Action aspect",
    "prov_policy_selection": "Policy selection",
    "prov_config": "Config",
    "prov_actionability_config": "Actionability config",
    "prov_synthetic": "Synthetic data",
    "temporal_subheader": "Changes over time",
    "temporal_caption": "Track how guest reviews change over time and whether the analysis approach is workable.",
    "temporal_warning": "**Historical reference page:** uses the legacy permissive rules (**{legacy_n}** candidate events), not the current strict count (**{strict_n}**, verdict **{verdict}**, {evt_strength}). See the **Research progress** tab for current evidence.",
    "temporal_panel_missing": "Temporal panel has not been built yet.",
    "temporal_peer_section": "Geographic reference sets",
    "temporal_peer_summary": "Main setting: same-city Haversine k={k} · hotels={hotels} · cities={cities}. Term: **geographic reference / candidate peer set** (not verified economic competitors).",
    "temporal_feasibility_green": "Feasibility verdict: **{label}** (legacy permissive pipeline)",
    "temporal_feasibility_amber": "Feasibility verdict: **{label}** (legacy permissive pipeline)",
    "temporal_feasibility_red": "Feasibility verdict: **{label}** (legacy permissive pipeline)",
    "metric_quarter_rows": "Quarter cells",
    "metric_valid_mentions": "Valid mention cells",
    "metric_candidate_events": "Candidate events (permissive)",
    "metric_event_hotels": "Hotels involved",
    "metric_with_peer_ref": "Nearby review improvements",
    "metric_without_peer_ref": "No nearby review improvement",
    "temporal_bullets": "- Change threshold (pre-set): **{threshold}**\n- Valid hotel-quarter-aspect cells: **{valid_cells}**\n- Hotels with ≥4 periods: **{coverage}**\n- Change meaning: **review-based aspect change** (not a management intervention)",
    "temporal_charts_heading": "Charts",
    "chart_verdict_no_data": "No candidate event summary to chart.",
    "chart_verdict_caption": "Permissive candidate events from feasibility_metrics.json (not current strict definition).",
    "chart_verdict_candidate": "Candidate events (permissive)",
    "chart_verdict_with_ref": "Nearby review improvements",
    "chart_verdict_without_ref": "No nearby review improvement",
    "chart_verdict_hotels": "Hotels involved",
    "chart_verdict_metric_col": "Metric",
    "chart_verdict_count_col": "Count",
    "chart_peer_missing": "candidate_events.csv not found; cannot plot peer reference distribution.",
    "chart_peer_empty": "Peer reference column is empty.",
    "chart_peer_caption": "X-axis is the share of nearby hotels whose reviews improved on the same aspect (0–1); a review-based reference signal, not actual renovations.",
    "chart_peer_bin_col": "Reference range",
    "chart_delta_missing": "delta_q_sample.csv not found.",
    "chart_delta_empty": "Delta column is empty.",
    "chart_delta_caption": "Distribution of review-based aspect change (Δq) from delta_q_sample.csv.",
    "chart_delta_bin_col": "Change range",
    "chart_freq_col": "Frequency",
    "chart_mae_no_data": "No model MAE data to chart.",
    "chart_mae_empty": "All model MAE values are empty.",
    "chart_mae_caption": "Model prediction error comparison; lower is better. This does not prove business impact.",
    "expander_raw_feasibility": "Raw feasibility metrics (JSON download)",
    "expander_raw_feasibility_caption": "English schema file for audit; use the summary above for reading.",
    "download_feasibility": "Download feasibility_metrics.json",
    "temporal_feasibility_missing": "Temporal feasibility outputs not built yet. Expected: panel coverage, candidate changes, peer reference, green/amber/red verdict.",
    "temporal_predict_header": "Early prediction experiment",
    "temporal_predict_skipped": "Predictive pilot unavailable or below threshold ({reason}).",
    "temporal_predict_info": "Predictive association only — does **not** upgrade the manager page to predictive evidence and is **not** causal.",
    "temporal_predict_caption": "Target: {target} · Test periods: {periods} · Peer model beats persistence: {beats}",
    "temporal_predict_missing": "Predictive pilot unavailable or below threshold.",
    "download_predict_metrics": "Download metrics.json (raw)",
    "temporal_claims_header": "What this workbench can / cannot claim",
    "temporal_claims_body": "**Can claim:** descriptive coverage; feasibility of temporal measurement; predictive association on hold-out sets (not causal).\n\n**Cannot claim:** peer causal interference; ROI; demand lift; calling geographic neighbors verified competitors; equating sentiment change with management action; equating permissive events with strict event definition.",
    "expander_go_no_go": "Pass/fail raw record (optional download)",
    "expander_go_no_go_caption": "English Markdown for audit; full text not shown inline.",
    "download_go_no_go": "Download GO_NO_GO.md",
    "research_subheader": "Research progress",
    "research_caption": "Review data is organized and a suggestion prototype is ready; we are checking whether the suggestions are reliable.",
    "research_info": "The improvement tab stays descriptive — not causal effects, ROI, or booking growth. Model agreement is not human accuracy.",
    "metric_measurement": "Review data coverage",
    "metric_strict_events": "Filtered review changes",
    "metric_strict_events_caption": "Counts review changes detected in comments, not known hotel renovations or management actions.",
    "metric_peer_predictive": "Does nearby-hotel info help?",
    "metric_track": "Current research direction",
    "research_facts_caption": "Legacy permissive candidates for reference only: {legacy}",
    "research_facts_sha_caption": "Source checksum: FACTS sha256 `{sha}…`",
    "research_summary_heading": "Current facts summary",
    "research_row_complete_periods": "Complete quarters",
    "research_row_partial_periods": "Partial quarters (excluded)",
    "research_row_strict_verdict": "Strict event verdict",
    "research_row_strict_count": "Filtered review changes",
    "research_row_event_strength": "Event-study evidence strength",
    "research_row_track_formulation": "Track {track} formulation",
    "research_row_non_causal": "Non-causal disclaimer",
    "research_row_non_causal_value": "Yes",
    "research_compare": "**Vs historical page:** legacy permissive pipeline **{legacy}** permissive candidates; current strict count **{strict}**; peer prediction **{peer}**; **{strength}**.",
    "research_facts_missing": "autonomous/FACTS.json has not been built yet.",
    "research_claims_heading": "Claims ledger",
    "research_claims_empty": "Ledger table is empty or could not be parsed.",
    "expander_claims_raw": "Raw ledger file (optional download)",
    "expander_claims_caption": "English Markdown; table above is localized; statuses read live from file.",
    "download_claims": "Download CLAIMS_LEDGER.md",
    "research_claims_missing": "CLAIMS_LEDGER.md has not been built yet.",
    "expander_facts_raw": "Raw FACTS (optional download)",
    "download_facts": "Download FACTS.json",
    "model_annotation_heading": "Can the system read reviews?",
    "model_annotation_missing": "Final model annotation report not generated yet (expected: `{path}`). No agreement or acceptance rates shown until then.",
    "model_annotation_private_note": "Final label CSV stays on this machine at `{path}` (contains review text; not uploaded).",
    "model_annotation_unknown_status": "Report status unknown; figures below are reference only.",
    "model_annotation_metric_items": "Review snippets checked",
    "model_annotation_metric_accepted": "Labels kept",
    "model_annotation_metric_unresolved": "Still uncertain",
    "model_annotation_metric_audited": "Snippets re-checked",
    "model_annotation_per_aspect": "Final label counts by aspect",
    "model_annotation_footer": "Full per-item labels (with text) stay local: `{path}`. Public report has no review text, hotel names, or per-item rationales.",
    "col_claim_id": "ID",
    "col_claim": "Claim",
    "col_status": "Status",
    "col_notes": "Notes",
    "col_model": "Model",
    "track_prefix": "Track",
    "recommendation_aria": "Improvement suggestion",
}


def _min_mentions(cfg: dict | None) -> int:
    if cfg and cfg.get("min_mentions") is not None:
        return int(cfg["min_mentions"])
    return 5


def policy_rules(cfg: dict | None = None) -> dict[str, str]:
    min_m = _min_mentions(cfg)
    w = (cfg or {}).get("weights") or {}
    gap_w = w.get("gap", 0.45)
    crit_w = w.get("criticism", 0.35)
    unrel_w = w.get("unreliable", 0.20)
    return {
        "fix_weakest": (
            f"Among actionable aspects with ≥{min_m} mentions, pick the lowest overall tendency "
            "(location and other non-actionable aspects excluded)"
        ),
        "largest_peer_gap": (
            f"Among actionable aspects with ≥{min_m} mentions, pick the largest gap vs comparison median "
            "(peer median − yours; location excluded from action layer)"
        ),
        "most_criticized": (
            f"Among actionable aspects with ≥{min_m} mentions, pick the most negative mentions "
            "(rates and per-review metrics shown for audit)"
        ),
        "peer_relative": (
            f"Score = {gap_w}×normalized gap + {crit_w}×normalized negative rate "
            f"− {unrel_w}×(1−reliability) "
            "[design weights, not learned]. Crowding intensity applies only in scenario analysis."
        ),
        "diagnostic_largest_gap": (
            f"Among aspects visible in diagnostics with ≥{min_m} mentions, pick the largest gap vs peer median "
            "(may include location)"
        ),
    }


POLICY_RULES: dict[str, str] = policy_rules()

EVIDENCE_LEVEL_LABELS: dict[str, str] = {
    "DESCRIPTIVE": "Descriptive evidence",
    "PREDICTIVE": "Predictive evidence",
    "CAUSAL": "Causal evidence",
}

EVIDENCE_BANNERS: dict[str, str] = {
    "DESCRIPTIVE": (
        "Descriptive evidence — suggestions use relative gaps and review counts; "
        "not verified causal effect estimates."
    ),
    "PREDICTIVE": "Predictive evidence",
    "CAUSAL": "Causal evidence",
}

EVIDENCE_WHY: dict[str, str] = {
    "DESCRIPTIVE": (
        "The manager snapshot has cross-sectional aspect scores and researcher-defined comparison groups; "
        "this tab stays descriptive. Time-split prediction and strict events live on other tabs but do not "
        "upgrade this page to predictive or causal evidence."
    ),
    "PREDICTIVE": "Snapshot includes out-of-sample predictive metrics with time splits.",
    "CAUSAL": "All causal validation checks in the snapshot are true.",
}

CANNOT_CLAIM: list[str] = [
    "Improving an aspect causes a verified causal effect",
    "Booking demand or revenue will rise",
    "Comparison hotels are verified economic substitutes",
    "Review sentiment change equals management intervention",
    "Guaranteed improvement or return on investment (ROI)",
]

FEASIBILITY_VERDICT: dict[str, str] = {
    "GREEN": "Feasible (green)",
    "AMBER": "Caution (amber)",
    "RED": "Not feasible (red)",
    "UNKNOWN": "Unknown",
}

MEASUREMENT_VERDICT: dict[str, str] = {
    "MEASUREMENT_STRONG": "Strong measurement coverage",
    "MEASUREMENT_WEAK": "Weak measurement coverage",
}

PEER_PREDICTIVE: dict[str, str] = {
    "PARTIAL": "Partial support (non-causal)",
    "STRONG": "Stronger (non-causal)",
    "WEAK": "Weaker",
    "NONE": "N/A",
}

STRICT_VERDICT: dict[str, str] = {
    "AMBER_ASSOCIATIONAL": "Associational only (not causal confirmation)",
    "GREEN": "Green (pre-registered threshold passed)",
    "RED": "Red",
}

EVENT_STUDY_STRENGTH: dict[str, str] = {
    "WEAK": "Weak",
    "STRONG": "Strong",
}

TRACK_FORMULATION: dict[str, str] = {
    "A": "Supply-side recommendation under peer reference (track A)",
    "B": "Diagnostic ≠ action; location not directly actionable; abstain when evidence is thin",
    "C": "Sentiment change ≠ service improvement: measurement risk view (track C)",
}

CLAIM_TEXT: dict[str, str] = {
    "Demo is descriptive unless ledger upgrades it": "Demo is descriptive unless the ledger upgrades it",
    "Geo kNN are candidate peers / geo reference sets": "Geo kNN are candidate peers / geographic reference sets (not verified competitors)",
    "Location is not a direct operational action": "Location is not a direct operational lever",
    "Overnight 5774 is legacy_permissive only": "Legacy permissive pipeline counts are not the current strict definition",
    "Zero-mention is not observed neutral": "Zero mentions does not mean observed neutral quality",
    "Partial 2015Q3/2017Q3 excluded from main analyses": "Incomplete quarters 2015Q3/2017Q3 excluded from main analyses",
    "Peer incremental prediction": "Peer incremental prediction (associational, not causal)",
    "Strict events support confirmatory event-study": "Whether strict events support confirmatory event-study",
    "Causal wording": "Causal wording (forbidden in the demo)",
    "Selected track B": "Selected paper track",
}

CLAIM_STATUS: dict[str, str] = {
    "SUPPORTED": "Supported",
    "PARTIAL": "Partial",
    "AMBER_ASSOCIATIONAL": "Associational only",
    "FORBIDDEN": "Forbidden",
    "DECISION": "Decision record",
}

CLAIM_NOTES: dict[str, str] = {
    "evidence_level=DESCRIPTIVE": "Evidence level: descriptive",
    "Wave 3 PEER_SIGNAL_STRONG": "Wave 3: stronger peer signal",
    "actionability.json": "From actionability config",
    "Wave 2": "Wave 2 strict event definition",
    "Wave 1 has_measurement": "Wave 1: measurement coverage present",
    "Wave 1 completeness": "Wave 1: quarter completeness rules",
    "Wave 4": "Wave 4: temporal prediction experiment",
    "Wave 2; GREEN not lowered": "Wave 2 strict event result",
    "Wave 5 WEAK": "Wave 5: weak event-study evidence",
    "Wave 6": "Wave 6: paper track decision",
}

MODEL_NAME: dict[str, str] = {
    "city_mean": "City mean baseline",
    "persistence": "Persistence baseline",
    "own_trend": "Own trend",
    "own_features": "Own features",
    "own_plus_peer_state": "Own + peer state",
    "own_plus_peer_exposure": "Own + peer reference",
    "own_plus_same_aspect_peer_state": "Own + same-aspect peer state",
    "own_plus_same_aspect_peer_exposure": "Own + same-aspect peer reference",
}

TARGET_LABEL: dict[str, str] = {
    "next_quarter_mean_reviewer_score": "Next-quarter mean guest score",
}

SCORE_TERM_DEFINITIONS = (
    "**Terms (optional):** "
    "Overall tendency = net of positive vs negative mentions for an aspect; "
    "Gap = comparison median tendency − your hotel; "
    "Negative rate = share of mentions that are negative; "
    "Reliability = rises toward 1 with more mentions (shrinkage); "
    "Normalized gap/rate = 0–1 scale within actionable aspects for your hotel."
)

LIMITATIONS = """
- Review counts **do not equal** bookings or demand.
- Aspect tendencies come from reviews; **not** verified management intervention effects.
- Comparison groups are research reference sets; **not** verified economic substitutes.
- **Balanced gap and volume** policy uses **design weights**, not learned business returns.
- The **crowding assumption** slider is **illustrative**, not a fitted elasticity.
- Location may show as a weakness but is **not** a direct operational lever.
- This demo does **not** claim event-study, placebo, or causal estimates.
"""

MODEL_ANNOTATION_BOUNDARY_EXPANDER = """
**Automated labeling and limits** (this demo does not claim human-verified labels or real business validation):

1. **Flow:** Grok first pass → independent blind review (e.g. Claude) → Codex final call on disagreements; uncertain cases stay unresolved.
2. **Agreement meaning:** Raw agreement and Cohen κ reflect model pairing only; **not** human accuracy or overall correctness.
3. **Manager use:** UI suggestions remain descriptive; whether an issue is actionable or affects bookings/revenue needs your judgment — **not** verified with real hotels.

Full labeled text and rationales stay in a private local folder, not in the public repo.
"""

HUMAN_CONFIRM_EXPANDER = MODEL_ANNOTATION_BOUNDARY_EXPANDER

SENTIMENT_LABELS: dict[str, str] = {
    "positive": "Positive",
    "negative": "Negative",
    "neutral": "Neutral",
    "not_about_aspect": "Not mentioned",
}

MODEL_ANNOTATION_REPORT_PATH = "outputs/autonomous/model_annotation/final_20260913.json"
MODEL_ANNOTATION_PRIVATE_CSV = (
    "outputs/autonomous/private/model_annotation_rounds/round_20260913/final_labels.csv"
)


def model_annotation_status_label(status: str | None) -> str:
    mapping = {
        "MODEL_AUDITED_REFERENCE": "Model audit complete (reference)",
        "accepted_consensus": "Both models agreed (not spot-audited)",
        "accepted_codex": "Accepted by Codex",
        "unresolved": "Unresolved (insufficient evidence)",
    }
    return mapping.get(status or "", status or "N/A")


def format_model_agreement_caption(raw_rate: float | None, kappa: float | None) -> str:
    raw = f"{raw_rate * 100:.1f}%" if raw_rate is not None else "N/A"
    kappa_s = "undefined" if kappa is None else f"{kappa:.3f}"
    return (
        f"Raw model agreement {raw} · Cohen κ {kappa_s}. "
        "This is model pairing only, not human accuracy."
    )


def aspect_label(aspect_id: str, fallback: str | None = None) -> str:
    return ASPECT_LABELS.get(aspect_id, fallback or aspect_id)


def city_label(city: str) -> str:
    return CITY_LABELS.get(city, city)


def compset_label(cs: str) -> str:
    return "All groups" if cs == "(all)" else cs


def price_tier_label(tier: str | None) -> str:
    if not tier:
        return "N/A"
    return PRICE_TIER_LABELS.get(str(tier).lower(), tier)


def actionability_label(level: str | None) -> str:
    if not level:
        return "N/A"
    return ACTIONABILITY_LEVEL_LABELS.get(level, level)


def fmt_na(value: Any, empty: str = "N/A") -> str:
    if value is None:
        return empty
    if isinstance(value, str) and value.strip().lower() in ("n/a", "na", ""):
        return empty
    return str(value)


def fmt_bool(value: Any) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return fmt_na(value)


def evidence_banner(level: str) -> str:
    return EVIDENCE_BANNERS.get(level, f"{level} evidence")


def evidence_level_label(level: str) -> str:
    return EVIDENCE_LEVEL_LABELS.get(level, level)


def evidence_why(level: str, backend_why: str) -> str:
    return EVIDENCE_WHY.get(level, backend_why)


def policy_label(key: str, backend_label: str | None = None) -> str:
    return POLICY_LABELS.get(key, backend_label or key)


def policy_rule(key: str, backend_rule: str | None = None, cfg: dict | None = None) -> str:
    rules = policy_rules(cfg) if cfg else POLICY_RULES
    return rules.get(key, backend_rule or "")


def policy_summary(key: str) -> str:
    return POLICY_SUMMARIES.get(key, "")


def formula_caption(cfg: dict) -> str:
    w = cfg.get("weights") or {}
    return (
        f"Score = {w.get('gap', 'gap')}×normalized gap + {w.get('criticism', 'criticism')}×normalized criticism "
        f"− {w.get('unreliable', 'unreliable')}×(1−reliability) "
        "[design weights, not learned returns]. Crowding term applies only in scenario analysis."
    )


def weights_caption(cfg: dict) -> str:
    w = cfg.get("weights") or {}
    return (
        f"Design weights: gap={w.get('gap')}, criticism={w.get('criticism')}, unreliable={w.get('unreliable')}. "
        "Not estimated business returns."
    )


def format_gap_vs_median(gap: Any) -> str:
    """Phrase signed gap (peer median − yours) without exposing raw sign confusion."""
    if gap is None:
        return fmt_na(None)
    if not isinstance(gap, (int, float)):
        return fmt_na(gap)
    g = float(gap)
    if g == 0:
        return "equal to comparison median"
    if g > 0:
        return f"{abs(g):.3f} below comparison median"
    return f"{abs(g):.3f} above comparison median"


def _aspect_stats_line(rec: Mapping[str, Any], label: str) -> str:
    mentions = fmt_na(rec.get("mention_count"))
    neg = fmt_na(rec.get("neg_mentions"))
    gap_phrase = format_gap_vs_median(rec.get("gap"))
    return (
        f"“{label}”: {mentions} mentions, {neg} negative mentions; "
        f"vs comparison median: {gap_phrase}."
    )


def build_diagnostic_explanation(
    expl: dict,
    label_fn: Callable[[str], str] = aspect_label,
    hotel: dict | None = None,
) -> str | None:
    diag_a = expl.get("diagnostic_aspect")
    act_a = expl.get("actionable_recommendation")
    if not diag_a:
        return None
    diag = expl.get("diagnostic") or {}
    if diag.get("actionable"):
        return None
    diag_label = label_fn(diag_a)
    if act_a:
        act_label = label_fn(act_a)
        act_rec = ((hotel or {}).get("aspects") or {}).get(act_a) or {}
        stats = _aspect_stats_line(act_rec, act_label)
        return (
            f"The largest gap vs nearby hotels is in “{diag_label}”, which you usually cannot change directly "
            f"(e.g. you cannot move the hotel). Suggested actionable focus: {stats}"
        )
    return (
        f"The largest gap is in “{diag_label}”, which is not directly actionable. "
        "No direct action suggestion under current evidence."
    )


def build_recommendation_explanation(
    expl: dict,
    hotel: dict,
    label_fn: Callable[[str], str] = aspect_label,
) -> str | None:
    diag_expl = build_diagnostic_explanation(expl, label_fn, hotel)
    if diag_expl:
        return diag_expl
    act_a = expl.get("actionable_recommendation")
    if not act_a:
        return None
    rec = (hotel.get("aspects") or {}).get(act_a) or {}
    return _aspect_stats_line(rec, label_fn(act_a))


def translate_claim_text(text: str) -> str:
    return CLAIM_TEXT.get(text.strip(), text.strip())


def translate_claim_status(status: str) -> str:
    return CLAIM_STATUS.get(status.strip(), status.strip())


def translate_claim_notes(notes: str) -> str:
    raw = notes.strip()
    if not raw:
        return "N/A"
    return CLAIM_NOTES.get(raw, raw)


def format_policy_selection(
    policies: Mapping[str, Mapping[str, Any]],
    order: list[str],
    label_fn: Callable[[str], str],
) -> str:
    parts: list[str] = []
    for key in order:
        chosen = policies[key].get("chosen_aspect")
        aspect = label_fn(chosen) if chosen else "N/A"
        parts.append(f"{policy_label(key)}: {aspect}")
    return "; ".join(parts)


def format_hist_bin(idx: Any) -> str:
    if hasattr(idx, "left") and hasattr(idx, "right"):
        lo, hi = float(idx.left), float(idx.right)
        return f"{lo:.2f}–{hi:.2f}"
    try:
        return f"{float(idx):.2f}"
    except (TypeError, ValueError):
        return str(idx)


def target_label(code: str | None) -> str:
    if not code:
        return "N/A"
    return TARGET_LABEL.get(code, code)


def event_study_strength_label(code: str | None) -> str:
    if not code:
        return "N/A"
    strength = EVENT_STUDY_STRENGTH.get(code, code)
    return f"Event-study evidence strength: {strength}"


def track_formulation(track: str | None, wave6: dict | None = None) -> str:
    if not track:
        return "N/A"
    if wave6 and wave6.get("formulation"):
        if track == "B":
            return TRACK_FORMULATION.get("B", wave6["formulation"])
    return TRACK_FORMULATION.get(track, f"Track {track}")


def mae_column_label() -> str:
    return "MAE"


def rmse_column_label() -> str:
    return "RMSE"


def parse_claims_ledger(md_text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in md_text.splitlines():
        line = line.strip()
        if not line.startswith("|") or re.match(r"^\|[-\s|]+\|$", line):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) < 4 or parts[0].upper() == "ID":
            continue
        rows.append({
            "id": parts[0],
            "claim_en": parts[1],
            "claim_zh": translate_claim_text(parts[1]),
            "status_en": parts[2],
            "status_zh": translate_claim_status(parts[2]),
            "notes": translate_claim_notes(parts[3]),
        })
    return rows


def model_name(key: str) -> str:
    return MODEL_NAME.get(key, key)


def measurement_label(code: str | None) -> str:
    if not code:
        return "N/A"
    return MEASUREMENT_VERDICT.get(code, code)


def peer_predictive_label(code: str | None) -> str:
    if not code:
        return "N/A"
    return PEER_PREDICTIVE.get(code, code)


def strict_verdict_label(code: str | None) -> str:
    if not code:
        return "N/A"
    return STRICT_VERDICT.get(code, code)


def feasibility_verdict_label(code: str | None) -> str:
    if not code:
        return "Unknown"
    return FEASIBILITY_VERDICT.get(code, code)


# Backward-compatible aliases used by older imports
CANNOT_CLAIM_ZH = CANNOT_CLAIM
LIMITATIONS_ZH = LIMITATIONS
FEASIBILITY_VERDICT_ZH = FEASIBILITY_VERDICT
MEASUREMENT_VERDICT_ZH = MEASUREMENT_VERDICT
PEER_PREDICTIVE_ZH = PEER_PREDICTIVE
STRICT_VERDICT_ZH = STRICT_VERDICT
EVENT_STUDY_STRENGTH_ZH = EVENT_STUDY_STRENGTH
TRACK_FORMULATION_ZH = TRACK_FORMULATION
CLAIM_TEXT_ZH = CLAIM_TEXT
CLAIM_STATUS_ZH = CLAIM_STATUS
CLAIM_NOTES_ZH = CLAIM_NOTES
MODEL_NAME_ZH = MODEL_NAME
TARGET_LABEL_ZH = TARGET_LABEL
HEURISTIC_NAME_ZH = POLICY_LABELS["peer_relative"]

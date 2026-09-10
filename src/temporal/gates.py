"""Feasibility gate logic extracted so unit tests do not import matplotlib."""
from __future__ import annotations


def classify_gate(m: dict, green: dict) -> tuple[str, list[str]]:
    reasons = []
    checks = [
        ("min_hotels_with_coverage", m["hotels_with_enough_coverage"] >= green["min_hotels_with_coverage"]),
        ("min_valid_cells", m["valid_cells"] >= green["min_valid_cells"]),
        ("min_candidate_events", m["candidate_events"] >= green["min_candidate_events"]),
        ("min_event_hotels", m["event_hotels"] >= green["min_event_hotels"]),
        ("min_event_cities", m["event_cities"] >= green["min_event_cities"]),
        ("min_event_aspects", m["event_aspects"] >= green["min_event_aspects"]),
        ("min_events_exposure_gt0", m["events_exposure_gt0"] >= green["min_events_exposure_gt0"]),
        ("min_events_exposure_eq0", m["events_exposure_eq0"] >= green["min_events_exposure_eq0"]),
        ("min_frac_events_with_2pre_2post", m["frac_events_2pre_2post"] >= green["min_frac_events_with_2pre_2post"]),
    ]
    for name, ok in checks:
        if not ok:
            reasons.append(f"FAIL {name}")
    if not reasons:
        return "GREEN", ["All pre-registered GREEN gates passed."]
    panel_ok = (
        m["hotels_with_enough_coverage"] >= green["min_hotels_with_coverage"] * 0.5
        and m["valid_cells"] >= green["min_valid_cells"] * 0.5
        and m["candidate_events"] >= 50
    )
    if panel_ok:
        return "AMBER", reasons + [
            "Panel coverage partial; predictive association allowed; strong event-study not supported."
        ]
    return "RED", reasons + [
        "Insufficient temporal / exposure support for peer-interference main line."
    ]

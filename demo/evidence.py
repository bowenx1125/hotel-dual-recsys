"""Evidence-level gate. Never upgrades to CAUSAL on filename heuristics."""
from __future__ import annotations

from pathlib import Path

CAUSAL_REQUIRED = [
    "treatment_definition_no_future_leak",
    "event_study",
    "pretrend_test",
    "placebo",
    "exposure_definition",
    "clustered_or_stated_uncertainty",
    "effect_estimate_and_ci",
    "reproducible_from_code",
]

BANNER = (
    "DESCRIPTIVE EVIDENCE — recommendations are based on relative aspect gaps "
    "and review evidence; they are not validated cause-and-effect estimates."
)

FORBIDDEN_WORDS = (
    "causal effect",
    "causal gain",
    "estimated demand lift",
    "guaranteed improvement",
    "roi",
    "预计因果",
)


def inspect_repo_for_causal_artifacts(root: Path) -> dict:
    """Return which (if any) causal artifacts exist. Presence of a filename is not enough."""
    hits = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        name = p.name.lower()
        if any(k in name for k in ("did", "causal", "event_study", "placebo", "iv_", "ope")):
            if "node_modules" in p.parts or ".venv" in str(p) or "site-packages" in p.parts:
                continue
            hits.append(str(p.relative_to(root)))
    return {"filename_hits": hits, "validated_checks": {k: False for k in CAUSAL_REQUIRED}}


def decide_evidence_level(snapshot: dict) -> dict:
    """
    Level 3 requires validated checks, not filenames.
    Level 2 requires documented time-split predictive metrics in the snapshot.
    Otherwise Level 1 DESCRIPTIVE.
    """
    predictive = bool(snapshot.get("predictive_holdout_metrics"))
    causal_ok = all(snapshot.get("causal_checks", {}).values()) if snapshot.get("causal_checks") else False
    if causal_ok:
        level = "CAUSAL"
        why = "All causal validation checks are marked true in the snapshot."
    elif predictive:
        level = "PREDICTIVE"
        why = "Snapshot includes held-out predictive metrics with a documented time split."
    else:
        level = "DESCRIPTIVE"
        why = (
            "Only cross-sectional aspect scores and researcher-defined peer sets are available. "
            "There is no time-split predictive model and no identified treatment effect with CI."
        )
    cannot_claim = [
        "causal effect of improving an aspect",
        "booking demand or revenue lift",
        "that peer sets are verified economic substitutes",
        "that review-sentiment changes are actual management interventions",
        "guaranteed improvement or ROI",
    ]
    return {
        "level": level,
        "why": why,
        "banner": BANNER if level == "DESCRIPTIVE" else f"{level} EVIDENCE",
        "cannot_claim": cannot_claim,
        "forbidden_words": list(FORBIDDEN_WORDS),
    }


def assert_copy_matches_level(level: str, text: str) -> None:
    low = text.lower()
    if level != "CAUSAL":
        if any(p in low for p in ("not validated", "not a causal", "no causal", "not causal")):
            return
        for w in FORBIDDEN_WORDS:
            if w in low:
                raise ValueError(f"Wording '{w}' is forbidden at evidence level {level}")

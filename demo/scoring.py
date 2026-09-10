"""Deterministic policy scoring with actionability constraints. No ML / no network."""
from __future__ import annotations

import json
import math
from pathlib import Path

from demo.config import ROOT

ASPECTS_DEFAULT = [
    "location", "cleanliness", "breakfast", "service", "noise", "room", "value",
]


def is_finite(x) -> bool:
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def fnum(x) -> float | None:
    if not is_finite(x):
        return None
    return float(x)


def percentile_rank(value: float, values: list[float]) -> float | None:
    finite = [v for v in values if is_finite(v)]
    if not finite or not is_finite(value):
        return None
    n = len(finite)
    below = sum(1 for v in finite if v < value)
    equal = sum(1 for v in finite if v == value)
    return 100.0 * (below + 0.5 * equal) / n


def median(values: list[float]) -> float | None:
    finite = sorted(v for v in values if is_finite(v))
    if not finite:
        return None
    m = len(finite) // 2
    if len(finite) % 2:
        return float(finite[m])
    return 0.5 * (finite[m - 1] + finite[m])


def minmax(values: list[float]) -> list[float]:
    finite_idx = [i for i, v in enumerate(values) if is_finite(v)]
    out = [0.0] * len(values)
    if not finite_idx:
        return out
    xs = [values[i] for i in finite_idx]
    lo, hi = min(xs), max(xs)
    span = hi - lo
    for i in finite_idx:
        out[i] = 0.0 if span == 0 else (values[i] - lo) / span
    return out


def reliability(mention_count: float, k: float) -> float:
    m = max(0.0, float(mention_count))
    return m / (m + float(k))


def load_actionability(cfg: dict | None = None, path: Path | None = None) -> dict:
    if path is None:
        rel = (cfg or {}).get("actionability_config", "conf/actionability.json")
        path = ROOT / rel
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["aspects"]


def actionable_aspect_ids(actionability: dict) -> list[str]:
    return [
        a for a, meta in actionability.items()
        if meta.get("eligible_for_direct_action") is True
    ]


def eligible_aspects(hotel: dict, cfg: dict, actionable_only: bool = False) -> list[str]:
    min_m = int(cfg["min_mentions"])
    act = load_actionability(cfg) if actionable_only else None
    out = []
    for a in cfg.get("aspects", ASPECTS_DEFAULT):
        rec = hotel["aspects"][a]
        if not is_finite(rec.get("net")):
            continue
        if rec.get("mention_count", 0) < min_m:
            continue
        if actionable_only and not act.get(a, {}).get("eligible_for_direct_action", False):
            continue
        out.append(a)
    return out


def _tie_pick(candidates: list[tuple[float, str]], higher: bool) -> str | None:
    if not candidates:
        return None
    if higher:
        best = max(s for s, _ in candidates)
        names = sorted(n for s, n in candidates if s == best)
    else:
        best = min(s for s, _ in candidates)
        names = sorted(n for s, n in candidates if s == best)
    return names[0]


def diagnostic_largest_gap(hotel: dict, cfg: dict) -> dict:
    """Diagnostic layer: may include immutable aspects such as location."""
    elig = [a for a in eligible_aspects(hotel, cfg, False) if is_finite(hotel["aspects"][a].get("gap"))]
    cands = [(hotel["aspects"][a]["gap"], a) for a in elig]
    pick = _tie_pick(cands, higher=True)
    act = load_actionability(cfg)
    return {
        "strategy": "diagnostic_largest_gap",
        "label": "Largest Diagnostic Disadvantage",
        "chosen_aspect": pick,
        "actionable": bool(pick and act.get(pick, {}).get("eligible_for_direct_action")),
        "actionability_level": act.get(pick, {}).get("actionability_level") if pick else None,
        "rule": "argmax (peer_median_net - hotel_net) over diagnostic-visible aspects with enough mentions",
        "score_table": {a: hotel["aspects"][a]["gap"] for a in elig},
    }


def policy_fix_weakest(hotel: dict, cfg: dict) -> dict:
    elig = eligible_aspects(hotel, cfg, actionable_only=True)
    cands = [(hotel["aspects"][a]["net"], a) for a in elig]
    pick = _tie_pick(cands, higher=False)
    return {
        "strategy": "fix_weakest",
        "label": "Fix Weakest (actionable)",
        "chosen_aspect": pick,
        "rule": "argmin net among ACTIONABLE aspects with mention_count >= min_mentions (location excluded)",
        "score_table": {a: hotel["aspects"][a]["net"] for a in elig},
    }


def policy_largest_peer_gap_actionable(hotel: dict, cfg: dict) -> dict:
    elig = [a for a in eligible_aspects(hotel, cfg, True) if is_finite(hotel["aspects"][a].get("gap"))]
    cands = [(hotel["aspects"][a]["gap"], a) for a in elig]
    pick = _tie_pick(cands, higher=True)
    return {
        "strategy": "largest_peer_gap",
        "label": "Largest Peer Gap (actionable)",
        "chosen_aspect": pick,
        "rule": "argmax gap among ACTIONABLE aspects only (location excluded from action layer)",
        "score_table": {a: hotel["aspects"][a]["gap"] for a in elig},
    }


def criticism_metrics(hotel: dict, aspect: str) -> dict:
    rec = hotel["aspects"][aspect]
    n_rev = max(1, int(hotel.get("n_reviews") or 0))
    neg = float(rec.get("neg_mentions") or 0)
    return {
        "neg_mentions": neg,
        "neg_rate": rec.get("neg_rate"),
        "neg_per_review": neg / n_rev,
    }


def policy_most_criticized(hotel: dict, cfg: dict) -> dict:
    elig = eligible_aspects(hotel, cfg, actionable_only=True)
    cands = [(hotel["aspects"][a].get("neg_mentions", 0), a) for a in elig]
    if cands and max(s for s, _ in cands) == 0:
        cands = [(hotel["aspects"][a].get("neg_rate") or 0.0, a) for a in elig]
    pick = _tie_pick(cands, higher=True)
    metrics = {a: criticism_metrics(hotel, a) for a in elig}
    return {
        "strategy": "most_criticized",
        "label": "Most Criticized (actionable)",
        "chosen_aspect": pick,
        "rule": "argmax negative-sentiment mention COUNT among actionable aspects (also report rate & per-review)",
        "score_table": {a: hotel["aspects"][a].get("neg_mentions", 0) for a in elig},
        "criticism_metrics": metrics,
    }


def peer_relative_scores(
    hotel: dict,
    cfg: dict,
    assumed_intensity: float = 0.0,
    weights: dict | None = None,
    actionable_only: bool = True,
) -> dict[str, float]:
    elig = eligible_aspects(hotel, cfg, actionable_only=actionable_only)
    if not elig:
        return {}
    gaps = [hotel["aspects"][a].get("gap") for a in elig]
    crit = [float(hotel["aspects"][a].get("neg_rate") or 0.0) for a in elig]
    rels = [hotel["aspects"][a]["reliability"] for a in elig]
    crowd = [float(hotel["aspects"][a].get("peer_weakest_share") or 0.0) for a in elig]
    gap_n = minmax([g if is_finite(g) else 0.0 for g in gaps])
    crit_n = minmax(crit)
    w = weights or cfg["weights"]
    cw = float(cfg["scenario"]["crowding_weight"])
    intensity = max(0.0, min(1.0, float(assumed_intensity)))
    scores = {}
    for i, a in enumerate(elig):
        scores[a] = (
            float(w["gap"]) * gap_n[i]
            + float(w["criticism"]) * crit_n[i]
            - float(w["unreliable"]) * (1.0 - rels[i])
            - intensity * cw * crowd[i]
        )
    return scores


def policy_peer_relative(hotel: dict, cfg: dict, assumed_intensity: float = 0.0, weights: dict | None = None) -> dict:
    scores = peer_relative_scores(hotel, cfg, assumed_intensity, weights=weights, actionable_only=True)
    pick = _tie_pick([(s, a) for a, s in scores.items()], higher=True)
    name = cfg.get("heuristic_name", "Peer-Relative Evidence-Weighted (heuristic)")
    w = weights or cfg["weights"]
    return {
        "strategy": "peer_relative",
        "label": name,
        "chosen_aspect": pick,
        "rule": (
            f"score = {w['gap']}*gap_norm + {w['criticism']}*criticism_norm "
            f"- {w['unreliable']}*(1-reliability) "
            f"[design-choice weights; not learned]. "
            "Assumed crowding intensity applied only in scenario mode."
        ),
        "score_table": scores,
        "assumed_intensity": float(assumed_intensity),
        "heuristic": True,
        "weights_are_design_choices": True,
    }


# Backward-compatible aliases used by older tests / scripts
def competition_aware_scores(hotel, cfg, assumed_intensity=0.0):
    return peer_relative_scores(hotel, cfg, assumed_intensity, actionable_only=True)


def policy_competition_aware(hotel, cfg, assumed_intensity=0.0):
    return policy_peer_relative(hotel, cfg, assumed_intensity)


def policy_largest_peer_gap(hotel, cfg):
    return policy_largest_peer_gap_actionable(hotel, cfg)


def explain_action_vs_diagnostic(hotel: dict, cfg: dict) -> dict:
    diag = diagnostic_largest_gap(hotel, cfg)
    action = policy_peer_relative(hotel, cfg, 0.0)
    act = load_actionability(cfg)
    diag_a = diag["chosen_aspect"]
    act_a = action["chosen_aspect"]
    explanation = None
    if diag_a and not act.get(diag_a, {}).get("eligible_for_direct_action", False):
        explanation = (
            f"Largest diagnostic disadvantage: {diag_a}. "
            f"{diag_a.capitalize()} is not a direct operational action, so the recommendation layer "
            f"selects the next highest actionable aspect"
            + (f": {act_a}." if act_a else ".")
        )
    return {
        "diagnostic_aspect": diag_a,
        "actionable_recommendation": act_a,
        "explanation": explanation,
        "diagnostic": diag,
        "action": action,
    }


def all_policies(hotel: dict, cfg: dict, assumed_intensity: float = 0.0) -> dict[str, dict]:
    return {
        "fix_weakest": policy_fix_weakest(hotel, cfg),
        "largest_peer_gap": policy_largest_peer_gap_actionable(hotel, cfg),
        "most_criticized": policy_most_criticized(hotel, cfg),
        "peer_relative": policy_peer_relative(hotel, cfg, assumed_intensity),
        # alias key for older callers
        "competition_aware": policy_peer_relative(hotel, cfg, assumed_intensity),
    }


def ranking_under_intensity(hotel: dict, cfg: dict, assumed_intensity: float, weights: dict | None = None):
    scores = peer_relative_scores(hotel, cfg, assumed_intensity, weights=weights, actionable_only=True)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def sanitize_hotel_numbers(hotel: dict) -> dict:
    for a, rec in hotel["aspects"].items():
        for k, v in list(rec.items()):
            if isinstance(v, float) and not math.isfinite(v):
                rec[k] = None
    return hotel

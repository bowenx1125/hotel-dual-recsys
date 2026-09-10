"""Deterministic policy scoring. No ML, no network, no NaN leakage."""
from __future__ import annotations

import math
from typing import Any

from demo import ASPECTS, STRATEGIES


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
    # midrank percentile in [0, 100]
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


def eligible_aspects(hotel: dict, cfg: dict) -> list[str]:
    min_m = int(cfg["min_mentions"])
    out = []
    for a in cfg["aspects"]:
        rec = hotel["aspects"][a]
        if not is_finite(rec.get("net")):
            continue
        if rec.get("mention_count", 0) < min_m:
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


def policy_fix_weakest(hotel: dict, cfg: dict) -> dict:
    elig = eligible_aspects(hotel, cfg)
    cands = [(hotel["aspects"][a]["net"], a) for a in elig]
    pick = _tie_pick(cands, higher=False)
    return {
        "strategy": "fix_weakest",
        "label": "Fix Weakest",
        "chosen_aspect": pick,
        "rule": "argmin net sentiment among aspects with mention_count >= min_mentions",
        "score_table": {a: hotel["aspects"][a]["net"] for a in elig},
    }


def policy_largest_peer_gap(hotel: dict, cfg: dict) -> dict:
    elig = [a for a in eligible_aspects(hotel, cfg) if is_finite(hotel["aspects"][a].get("gap"))]
    cands = [(hotel["aspects"][a]["gap"], a) for a in elig]
    pick = _tie_pick(cands, higher=True)
    return {
        "strategy": "largest_peer_gap",
        "label": "Largest Peer Gap",
        "chosen_aspect": pick,
        "rule": "argmax (peer_median_net - hotel_net) among eligible aspects with a peer median",
        "score_table": {a: hotel["aspects"][a]["gap"] for a in elig},
    }


def policy_most_criticized(hotel: dict, cfg: dict) -> dict:
    elig = eligible_aspects(hotel, cfg)
    cands = [(hotel["aspects"][a].get("neg_mentions", 0), a) for a in elig]
    # if all zeros, fall back to neg_share then mention-weighted criticism
    if cands and max(s for s, _ in cands) == 0:
        cands = [(hotel["aspects"][a].get("neg_rate") or 0.0, a) for a in elig]
    pick = _tie_pick(cands, higher=True)
    return {
        "strategy": "most_criticized",
        "label": "Most Criticized",
        "chosen_aspect": pick,
        "rule": "argmax aspect-level negative-sentiment mention count (tie: aspect name)",
        "score_table": {a: hotel["aspects"][a].get("neg_mentions", 0) for a in elig},
    }


def competition_aware_scores(hotel: dict, cfg: dict, assumed_intensity: float) -> dict[str, float]:
    elig = eligible_aspects(hotel, cfg)
    if not elig:
        return {}
    gaps = [hotel["aspects"][a].get("gap") for a in elig]
    crit = [float(hotel["aspects"][a].get("neg_rate") or 0.0) for a in elig]
    rels = [hotel["aspects"][a]["reliability"] for a in elig]
    crowd = [float(hotel["aspects"][a].get("peer_weakest_share") or 0.0) for a in elig]
    gap_n = minmax([g if is_finite(g) else 0.0 for g in gaps])
    crit_n = minmax(crit)
    w = cfg["weights"]
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


def policy_competition_aware(hotel: dict, cfg: dict, assumed_intensity: float = 0.0) -> dict:
    scores = competition_aware_scores(hotel, cfg, assumed_intensity)
    pick = _tie_pick([(s, a) for a, s in scores.items()], higher=True)
    return {
        "strategy": "competition_aware",
        "label": "Competition-Aware (heuristic)",
        "chosen_aspect": pick,
        "rule": (
            "score = 0.45*gap_norm + 0.35*criticism_norm - 0.20*(1-reliability) "
            "- assumed_intensity*0.50*peer_weakest_share  [heuristic + scenario; not causal]"
        ),
        "score_table": scores,
        "assumed_intensity": float(assumed_intensity),
        "heuristic": True,
    }


def all_policies(hotel: dict, cfg: dict, assumed_intensity: float = 0.0) -> dict[str, dict]:
    return {
        "fix_weakest": policy_fix_weakest(hotel, cfg),
        "largest_peer_gap": policy_largest_peer_gap(hotel, cfg),
        "most_criticized": policy_most_criticized(hotel, cfg),
        "competition_aware": policy_competition_aware(hotel, cfg, assumed_intensity),
    }


def ranking_under_intensity(hotel: dict, cfg: dict, assumed_intensity: float) -> list[tuple[str, float]]:
    scores = competition_aware_scores(hotel, cfg, assumed_intensity)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def sanitize_hotel_numbers(hotel: dict) -> dict:
    """Replace non-finite display fields with None; never leave NaN/inf in output."""
    for a, rec in hotel["aspects"].items():
        for k, v in list(rec.items()):
            if isinstance(v, float) and not math.isfinite(v):
                rec[k] = None
    return hotel

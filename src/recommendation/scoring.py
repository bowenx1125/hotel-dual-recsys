"""Deterministic policy scoring with unified evidence gates. Stdlib only; no demo imports."""
from __future__ import annotations

import json
import math
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

ASPECTS_DEFAULT = [
    "location",
    "cleanliness",
    "breakfast",
    "service",
    "noise",
    "room",
    "value",
]

ABSTAIN_NO_ELIGIBLE = "no_eligible_aspects"
ABSTAIN_CROWDING_UNAVAILABLE = "crowding_data_unavailable"


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
    if cfg and "actionability" in cfg:
        data = cfg["actionability"]
        return data["aspects"] if isinstance(data, dict) and "aspects" in data else data
    if path is None:
        rel = (cfg or {}).get("actionability_config", "conf/actionability.json")
        path = REPO_ROOT / rel
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["aspects"]


def actionable_aspect_ids(actionability: dict) -> list[str]:
    return [
        a
        for a, meta in actionability.items()
        if a in ASPECTS_DEFAULT
        and a != "location"
        and meta.get("eligible_for_direct_action") is True
    ]


def _is_nonneg_int(x) -> bool:
    if isinstance(x, bool) or not isinstance(x, int):
        return False
    return x >= 0


def _is_positive_int(x) -> bool:
    return _is_nonneg_int(x) and x > 0


def _valid_count(x) -> bool:
    if x is None:
        return False
    try:
        v = float(x)
        return math.isfinite(v) and v >= 0
    except (TypeError, ValueError):
        return False


def _cfg_float(cfg: dict, key: str, default: float, *, lo: float | None = None, hi: float | None = None) -> float:
    if key not in cfg:
        return float(default)
    v = cfg[key]
    if not is_finite(v):
        raise ValueError(f"{key} must be a finite number, got {v!r}")
    f = float(v)
    if lo is not None and f < lo:
        raise ValueError(f"{key} must be >= {lo}, got {f}")
    if hi is not None and f > hi:
        raise ValueError(f"{key} must be <= {hi}, got {f}")
    return f


def _cfg_int(cfg: dict, key: str, default: int, *, positive: bool = True) -> int:
    if key not in cfg:
        return int(default)
    v = cfg[key]
    if positive:
        if not _is_positive_int(v):
            raise ValueError(f"{key} must be a positive integer, got {v!r}")
    elif not _is_nonneg_int(v):
        raise ValueError(f"{key} must be a nonnegative integer, got {v!r}")
    return int(v)


def _cfg_reliability_k(cfg: dict) -> float:
    k = _cfg_float(cfg, "reliability_k", 10.0)
    if k <= 0.0:
        raise ValueError("reliability_k must be > 0")
    return k


def _cfg_crowding_weight(cfg: dict) -> float:
    scenario = cfg.get("scenario") or {}
    if not isinstance(scenario, dict):
        raise ValueError("scenario must be a dict")
    return _cfg_float(scenario, "crowding_weight", 0.5, lo=0.0, hi=1.0)


def _validated_weights(cfg: dict, weights: dict | None) -> dict:
    w = weights if weights is not None else cfg.get("weights")
    if not isinstance(w, dict):
        raise ValueError("weights must be a dict")
    out: dict[str, float] = {}
    for key in ("gap", "criticism", "unreliable"):
        if key not in w:
            raise ValueError(f"weights missing required key: {key}")
        v = w[key]
        if not is_finite(v) or float(v) < 0:
            raise ValueError(f"weights[{key}] must be finite and nonnegative, got {v!r}")
        out[key] = float(v)
    return out


def _parse_intensity(assumed_intensity: float) -> float:
    if not is_finite(assumed_intensity):
        raise ValueError("assumed_intensity must be finite")
    f = float(assumed_intensity)
    return max(0.0, min(1.0, f))


def _optional_sentiment_counts_valid(rec: dict) -> bool:
    mention_count = rec.get("mention_count")
    mc_ok = _is_nonneg_int(mention_count)
    if "pos_mentions" in rec and not _is_nonneg_int(rec["pos_mentions"]):
        return False
    if "neg_mentions" in rec:
        neg = rec["neg_mentions"]
        if not _is_nonneg_int(neg):
            return False
        if mc_ok and int(neg) > int(mention_count):
            return False
    return True


def _ensure_cfg_gates(cfg: dict) -> None:
    _cfg_int(cfg, "min_mentions", 5)
    _cfg_int(cfg, "min_measured_peers", 2)
    _cfg_float(cfg, "min_reliability", 0.3, lo=0.0, hi=1.0)
    _cfg_reliability_k(cfg)
    if "weights" in cfg:
        _validated_weights(cfg, None)
    if cfg.get("scenario") is not None:
        _cfg_crowding_weight(cfg)


def _aspect_reliability(rec: dict, cfg: dict) -> float | None:
    if "reliability" in rec:
        rel = rec["reliability"]
        if rel is None:
            return None
        if not is_finite(rel):
            return None
        f = float(rel)
        if f < 0.0 or f > 1.0:
            return None
        return f
    if "mention_count" not in rec:
        return None
    mention_count = rec["mention_count"]
    if not _is_nonneg_int(mention_count):
        return None
    k = _cfg_reliability_k(cfg)
    return reliability(int(mention_count), k)


def _has_measurement(rec: dict) -> bool:
    if "has_measurement" not in rec:
        return True
    val = rec["has_measurement"]
    if isinstance(val, bool):
        return val
    if type(val) is int and val in (0, 1):
        return bool(val)
    return False


def _peer_count_value(hotel: dict, rec: dict) -> int | None:
    if "peer_n" in rec:
        peer_n = rec["peer_n"]
        if peer_n is None or not _is_nonneg_int(peer_n):
            return None
        return int(peer_n)
    if "peer_count" in hotel:
        peer_count = hotel["peer_count"]
        if peer_count is None or not _is_nonneg_int(peer_count):
            return None
        return int(peer_count)
    return None


def _peer_meets_min(hotel: dict, rec: dict, cfg: dict) -> bool:
    min_peers = _cfg_int(cfg, "min_measured_peers", 2)
    peer_n = _peer_count_value(hotel, rec)
    return peer_n is not None and peer_n >= min_peers


def _valid_neg_rate(rec: dict) -> bool:
    rate = rec.get("neg_rate")
    return is_finite(rate) and 0.0 <= float(rate) <= 1.0


def _is_actionable_aspect(aspect: str, act: dict | None, actionable_only: bool) -> bool:
    if aspect == "location":
        return False
    if not actionable_only:
        return True
    if act is None:
        return False
    meta = act.get(aspect)
    if meta is None:
        return False
    return meta.get("eligible_for_direct_action") is True


def _evaluate_aspect(
    hotel: dict,
    aspect: str,
    cfg: dict,
    *,
    actionable_only: bool,
    act: dict | None,
    require_peer: bool = False,
    require_neg_mentions: bool = False,
    require_neg_rate: bool = False,
    require_crowding: bool = False,
) -> tuple[bool, str | None]:
    if hotel.get("eligible") is False:
        return False, "hotel_ineligible"
    aspects = hotel.get("aspects")
    if not isinstance(aspects, dict):
        return False, "missing_aspects"
    rec = aspects.get(aspect)
    if not isinstance(rec, dict):
        return False, "missing_aspect_record"

    if aspect not in ASPECTS_DEFAULT:
        return False, "unknown_aspect"

    min_m = _cfg_int(cfg, "min_mentions", 5)
    min_rel = _cfg_float(cfg, "min_reliability", 0.3, lo=0.0, hi=1.0)

    if not _has_measurement(rec):
        return False, "no_measurement"
    if not is_finite(rec.get("net")):
        return False, "nonfinite_net"

    mention_count = rec.get("mention_count")
    if not _is_nonneg_int(mention_count) or int(mention_count) < min_m:
        return False, "insufficient_mentions"

    if not _optional_sentiment_counts_valid(rec):
        return False, "invalid_counts"

    rel = _aspect_reliability(rec, cfg)
    if rel is None or rel < min_rel:
        return False, "insufficient_reliability"

    if actionable_only and not _is_actionable_aspect(aspect, act, True):
        if aspect == "location":
            return False, "not_actionable"
        if act is None or act.get(aspect) is None:
            return False, "unknown_aspect"
        return False, "not_actionable"

    if require_neg_mentions:
        neg = rec.get("neg_mentions")
        if not _is_nonneg_int(neg):
            return False, "invalid_neg_mentions"

    if require_neg_rate and not _valid_neg_rate(rec):
        return False, "invalid_neg_rate"

    if require_peer:
        if not is_finite(rec.get("gap")):
            return False, "nonfinite_gap"
        if not _peer_meets_min(hotel, rec, cfg):
            return False, "insufficient_peers"

    if require_crowding:
        share = rec.get("peer_weakest_share")
        if not is_finite(share) or float(share) < 0.0 or float(share) > 1.0:
            return False, "crowding_unavailable"

    return True, None


def _collect_eligibility(
    hotel: dict,
    cfg: dict,
    *,
    actionable_only: bool,
    require_peer: bool = False,
    require_neg_mentions: bool = False,
    require_neg_rate: bool = False,
    require_crowding: bool = False,
) -> tuple[list[str], dict[str, str]]:
    _ensure_cfg_gates(cfg)
    act = load_actionability(cfg) if actionable_only else None
    excluded: dict[str, str] = {}
    eligible: list[str] = []
    for aspect in cfg.get("aspects", ASPECTS_DEFAULT):
        ok, reason = _evaluate_aspect(
            hotel,
            aspect,
            cfg,
            actionable_only=actionable_only,
            act=act,
            require_peer=require_peer,
            require_neg_mentions=require_neg_mentions,
            require_neg_rate=require_neg_rate,
            require_crowding=require_crowding,
        )
        if ok:
            eligible.append(aspect)
        elif reason:
            excluded[aspect] = reason
    return eligible, excluded


def eligible_aspects(hotel: dict, cfg: dict, actionable_only: bool = False) -> list[str]:
    elig, _ = _collect_eligibility(hotel, cfg, actionable_only=actionable_only)
    return elig


def _aspect_evidence(hotel: dict, aspect: str, cfg: dict) -> dict:
    rec = hotel["aspects"][aspect]
    act = load_actionability(cfg)
    return {
        "mention_count": rec.get("mention_count"),
        "net": rec.get("net"),
        "gap": rec.get("gap"),
        "reliability": _aspect_reliability(rec, cfg),
        "neg_mentions": rec.get("neg_mentions"),
        "neg_rate": rec.get("neg_rate"),
        "peer_n": _peer_count_value(hotel, rec),
        "actionability": act.get(aspect, {}).get("actionability_level"),
    }


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


def _make_policy_result(
    strategy: str,
    label: str,
    rule: str,
    hotel: dict,
    cfg: dict,
    elig: list[str],
    excluded: dict[str, str],
    pick: str | None,
    score_table: dict,
    *,
    extra: dict | None = None,
) -> dict:
    out = {
        "strategy": strategy,
        "label": label,
        "chosen_aspect": pick,
        "abstention_reason": None if pick else ABSTAIN_NO_ELIGIBLE,
        "excluded_aspects": excluded,
        "evidence": _aspect_evidence(hotel, pick, cfg) if pick else None,
        "rule": rule,
        "score_table": score_table,
    }
    if extra:
        out.update(extra)
    return out


def diagnostic_largest_gap(hotel: dict, cfg: dict) -> dict:
    elig, excluded = _collect_eligibility(
        hotel, cfg, actionable_only=False, require_peer=True,
    )
    cands = [(hotel["aspects"][a]["gap"], a) for a in elig]
    pick = _tie_pick(cands, higher=True)
    act = load_actionability(cfg)
    return _make_policy_result(
        "diagnostic_largest_gap",
        "Largest Diagnostic Disadvantage",
        "argmax (peer_median_net - hotel_net) over diagnostic-visible aspects with enough mentions",
        hotel,
        cfg,
        elig,
        excluded,
        pick,
        {a: hotel["aspects"][a]["gap"] for a in elig},
        extra={
            "actionable": bool(pick and _is_actionable_aspect(pick, act, True)),
            "actionability_level": act.get(pick, {}).get("actionability_level") if pick else None,
        },
    )


def policy_fix_weakest(hotel: dict, cfg: dict) -> dict:
    elig, excluded = _collect_eligibility(hotel, cfg, actionable_only=True)
    cands = [(hotel["aspects"][a]["net"], a) for a in elig]
    pick = _tie_pick(cands, higher=False)
    return _make_policy_result(
        "fix_weakest",
        "Fix Weakest (actionable)",
        "argmin net among ACTIONABLE aspects with mention_count >= min_mentions (location excluded)",
        hotel,
        cfg,
        elig,
        excluded,
        pick,
        {a: hotel["aspects"][a]["net"] for a in elig},
    )


def policy_largest_peer_gap_actionable(hotel: dict, cfg: dict) -> dict:
    elig, excluded = _collect_eligibility(
        hotel, cfg, actionable_only=True, require_peer=True,
    )
    cands = [(hotel["aspects"][a]["gap"], a) for a in elig]
    pick = _tie_pick(cands, higher=True)
    return _make_policy_result(
        "largest_peer_gap",
        "Largest Peer Gap (actionable)",
        "argmax gap among ACTIONABLE aspects only (location excluded from action layer)",
        hotel,
        cfg,
        elig,
        excluded,
        pick,
        {a: hotel["aspects"][a]["gap"] for a in elig},
    )


def criticism_metrics(hotel: dict, aspect: str) -> dict:
    rec = hotel["aspects"][aspect]
    neg: int | None = None
    if "neg_mentions" in rec:
        raw_neg = rec["neg_mentions"]
        mention_count = rec.get("mention_count")
        if (
            _is_nonneg_int(raw_neg)
            and _is_nonneg_int(mention_count)
            and int(raw_neg) <= int(mention_count)
        ):
            neg = int(raw_neg)
    n_rev_raw = hotel.get("n_reviews")
    n_rev = int(n_rev_raw) if _is_positive_int(n_rev_raw) else None
    neg_per_review = None
    if neg is not None and n_rev is not None:
        neg_per_review = neg / n_rev
    return {
        "neg_mentions": neg,
        "neg_rate": rec.get("neg_rate"),
        "neg_per_review": neg_per_review,
    }


def policy_most_criticized(hotel: dict, cfg: dict) -> dict:
    elig, excluded = _collect_eligibility(
        hotel, cfg, actionable_only=True, require_neg_mentions=True,
    )
    cands = [(float(hotel["aspects"][a]["neg_mentions"]), a) for a in elig]
    pick = _tie_pick(cands, higher=True)
    metrics = {a: criticism_metrics(hotel, a) for a in elig}
    return _make_policy_result(
        "most_criticized",
        "Most Criticized (actionable)",
        "argmax negative-sentiment mention COUNT among actionable aspects (also report rate & per-review)",
        hotel,
        cfg,
        elig,
        excluded,
        pick,
        {a: hotel["aspects"][a]["neg_mentions"] for a in elig},
        extra={"criticism_metrics": metrics},
    )


def peer_relative_scores(
    hotel: dict,
    cfg: dict,
    assumed_intensity: float = 0.0,
    weights: dict | None = None,
    actionable_only: bool = True,
) -> dict[str, float]:
    intensity = _parse_intensity(assumed_intensity)
    require_crowding = intensity > 0.0
    elig, _ = _collect_eligibility(
        hotel,
        cfg,
        actionable_only=actionable_only,
        require_peer=True,
        require_neg_rate=True,
        require_crowding=require_crowding,
    )
    if not elig:
        return {}
    gaps = [hotel["aspects"][a]["gap"] for a in elig]
    crit = [float(hotel["aspects"][a]["neg_rate"]) for a in elig]
    rels = [_aspect_reliability(hotel["aspects"][a], cfg) for a in elig]
    gap_n = minmax(gaps)
    crit_n = minmax(crit)
    w = _validated_weights(cfg, weights)
    cw = _cfg_crowding_weight(cfg)
    scores: dict[str, float] = {}
    for i, aspect in enumerate(elig):
        crowd_term = 0.0
        if intensity > 0.0:
            crowd_term = float(hotel["aspects"][aspect]["peer_weakest_share"])
        rel = rels[i] if rels[i] is not None else 0.0
        score = (
            w["gap"] * gap_n[i]
            + w["criticism"] * crit_n[i]
            - w["unreliable"] * (1.0 - rel)
            - intensity * cw * crowd_term
        )
        if not is_finite(score):
            continue
        scores[aspect] = float(score)
    return scores


def _peer_relative_abstention(
    intensity: float,
    elig: list[str],
    elig_without_crowding: list[str],
) -> str | None:
    if elig:
        return None
    if intensity > 0.0 and elig_without_crowding:
        return ABSTAIN_CROWDING_UNAVAILABLE
    return ABSTAIN_NO_ELIGIBLE


def policy_peer_relative(
    hotel: dict,
    cfg: dict,
    assumed_intensity: float = 0.0,
    weights: dict | None = None,
) -> dict:
    intensity = _parse_intensity(assumed_intensity)
    require_crowding = intensity > 0.0
    elig, excluded = _collect_eligibility(
        hotel,
        cfg,
        actionable_only=True,
        require_peer=True,
        require_neg_rate=True,
        require_crowding=require_crowding,
    )
    elig_without_crowding, _ = _collect_eligibility(
        hotel,
        cfg,
        actionable_only=True,
        require_peer=True,
        require_neg_rate=True,
        require_crowding=False,
    )
    scores = peer_relative_scores(hotel, cfg, intensity, weights=weights, actionable_only=True)
    pick = _tie_pick([(s, a) for a, s in scores.items()], higher=True)
    name = cfg.get("heuristic_name", "Peer-Relative Evidence-Weighted (heuristic)")
    w = _validated_weights(cfg, weights)
    rationale_default = (
        "Default mode (intensity=0): scores actionable aspects that pass mention, reliability, "
        "measurement, peer-gap, and neg_rate gates; location and unknown aspects are excluded."
    )
    rationale_scenario = (
        "Scenario mode (intensity>0) uses the same actionable candidate set as default mode, "
        "then additionally requires finite peer_weakest_share in [0,1] for every candidate; "
        "abstains with crowding_data_unavailable only when candidates exist without crowding "
        "but crowding data blocks them."
    )
    abstention = _peer_relative_abstention(intensity, elig, elig_without_crowding)
    return _make_policy_result(
        "peer_relative",
        name,
        (
            f"score = {w['gap']}*gap_norm + {w['criticism']}*criticism_norm "
            f"- {w['unreliable']}*(1-reliability) "
            f"[design-choice weights; not learned]. "
            "Assumed crowding intensity applied only in scenario mode."
        ),
        hotel,
        cfg,
        elig,
        excluded,
        pick,
        scores,
        extra={
            "assumed_intensity": intensity,
            "heuristic": True,
            "weights_are_design_choices": True,
            "rationale_default": rationale_default,
            "rationale_scenario": rationale_scenario,
            "mode": "scenario" if intensity > 0.0 else "default",
            "crowding_available": not require_crowding or bool(elig),
            "abstention_reason": abstention,
        },
    )


def policy_reliability_aware(hotel: dict, cfg: dict) -> dict:
    elig, excluded = _collect_eligibility(hotel, cfg, actionable_only=True)
    cands = []
    for aspect in elig:
        rec = hotel["aspects"][aspect]
        rel = _aspect_reliability(rec, cfg)
        if rel is None:
            continue
        cands.append((-float(rec["net"]) * rel, aspect))
    pick = _tie_pick(cands, higher=True)
    score_table = {
        a: (-float(hotel["aspects"][a]["net"]) * _aspect_reliability(hotel["aspects"][a], cfg))
        for a in elig
        if _aspect_reliability(hotel["aspects"][a], cfg) is not None
    }
    return _make_policy_result(
        "reliability_aware",
        "Reliability-Aware (actionable)",
        "argmax (-net * reliability) among ACTIONABLE aspects with sufficient evidence",
        hotel,
        cfg,
        elig,
        excluded,
        pick,
        score_table,
    )


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
        "competition_aware": policy_peer_relative(hotel, cfg, assumed_intensity),
        "reliability_aware": policy_reliability_aware(hotel, cfg),
    }


def ranking_under_intensity(
    hotel: dict,
    cfg: dict,
    assumed_intensity: float,
    weights: dict | None = None,
):
    scores = peer_relative_scores(hotel, cfg, assumed_intensity, weights=weights, actionable_only=True)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def sanitize_hotel_numbers(hotel: dict) -> dict:
    for _a, rec in hotel["aspects"].items():
        for k, v in list(rec.items()):
            if isinstance(v, float) and not math.isfinite(v):
                rec[k] = None
    return hotel

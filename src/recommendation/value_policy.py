"""P3: the shipped ranking with an aspect-specific VALUE coefficient inserted.

The shipped `peer_relative` rule is

    score_a = w_gap * gap_norm + w_criticism * criticism_norm
              - w_unreliable * (1 - reliability)

Every term is ASPECT-AGNOSTIC in value: the rule ranks by *how bad / how much
room to improve* and has no way to express "a point of service is worth more
than a point of breakfast". P4 confirmed the consequence -- the shipped policy
is indistinguishable from picking an aspect at random under the direct-method
value model (+0.0004 rating points, t = 0.24).

This module is the minimal structural fix: multiply the two *deficit* terms by
a learned, aspect-specific value coefficient v_a. The reliability penalty stays
unscaled because it is an evidence discount, not a value.

    score_a = v_a * (w_gap * gap_norm + w_criticism * criticism_norm)
              - w_unreliable * (1 - reliability)

v is normalised to mean 1 over the actionable aspects, so the change is a pure
relative re-ranking: it cannot change the scale of the score, only which
aspect wins. Eligibility gates are untouched -- the same set of aspects stays
eligible, so abstention behaviour is identical to `peer_relative` by
construction.

v comes from `src.effect.learn_value` and is an ASSOCIATIONAL cross-sectional
coefficient (which aspects accompany high ratings across hotels), not a
causal effect of intervening.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.recommendation import scoring

ASPECTS = scoring.ASPECTS_DEFAULT
ACTIONABLE = [a for a in ASPECTS if a != "location"]


def normalize_value(v: dict[str, float], actionable: list[str] | None = None,
                    *, clamp_nonneg: bool = True) -> dict[str, float]:
    """Rescale v to mean 1 over actionable aspects (pure relative re-ranking)."""
    acts = list(actionable or ACTIONABLE)
    vals = np.array([float(v.get(a, 0.0)) for a in acts], dtype=float)
    if clamp_nonneg:
        vals = np.clip(vals, 0.0, None)
    m = float(vals.mean())
    if not np.isfinite(m) or m <= 0:
        return {a: 1.0 for a in acts}
    return {a: float(vals[i] / m) for i, a in enumerate(acts)}


def load_value_vector(cfg: dict) -> dict[str, float] | None:
    """Read the P3 value vector if -- and only if -- the config opts in.

    Default is OFF, so the shipped behaviour is byte-identical to before P3.
    The vector lives outside `conf/` because it is an estimated quantity with
    its own provenance (n, CV R^2, placebo, stability); it must never be
    silently baked into the config as if it were a design constant.
    """
    if not cfg.get("use_learned_value_vector"):
        return None
    rel = cfg.get("value_vector_path")
    if not rel:
        return None
    path = (Path(rel) if Path(rel).is_absolute()
            else Path(__file__).resolve().parents[2] / rel)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    spec = cfg.get("value_spec", "conditional")
    vec = data.get("vectors", {}).get(spec)
    return vec or None


def value_aware_scores(
    hotel: dict,
    cfg: dict,
    value_vector: dict[str, float] | None = None,
    assumed_intensity: float = 0.0,
    weights: dict | None = None,
    *,
    actionable_only: bool = True,
    clamp_nonneg: bool = True,
) -> dict[str, float]:
    """peer_relative scores with the aspect value coefficient applied."""
    intensity = scoring._parse_intensity(assumed_intensity)
    require_crowding = intensity > 0.0
    elig, _ = scoring._collect_eligibility(
        hotel,
        cfg,
        actionable_only=actionable_only,
        require_peer=True,
        require_neg_rate=True,
        require_crowding=require_crowding,
    )
    if not elig:
        return {}

    vv = normalize_value(value_vector or {}, ACTIONABLE, clamp_nonneg=clamp_nonneg)
    gaps = [hotel["aspects"][a]["gap"] for a in elig]
    crit = [float(hotel["aspects"][a]["neg_rate"]) for a in elig]
    rels = [scoring._aspect_reliability(hotel["aspects"][a], cfg) for a in elig]
    gap_n = scoring.minmax(gaps)
    crit_n = scoring.minmax(crit)
    w = scoring._validated_weights(cfg, weights)
    cw = scoring._cfg_crowding_weight(cfg)

    scores: dict[str, float] = {}
    for i, aspect in enumerate(elig):
        crowd_term = 0.0
        if intensity > 0.0:
            crowd_term = float(hotel["aspects"][aspect]["peer_weakest_share"])
        rel = rels[i] if rels[i] is not None else 0.0
        deficit = w["gap"] * gap_n[i] + w["criticism"] * crit_n[i]
        score = vv.get(aspect, 1.0) * deficit - w["unreliable"] * (1.0 - rel) \
            - intensity * cw * crowd_term
        if not scoring.is_finite(score):
            continue
        scores[aspect] = float(score)
    return scores


def policy_value_aware(
    hotel: dict,
    cfg: dict,
    value_vector: dict[str, float] | None = None,
    assumed_intensity: float = 0.0,
    weights: dict | None = None,
) -> dict:
    """Drop-in sibling of `scoring.policy_peer_relative` with the value term."""
    intensity = scoring._parse_intensity(assumed_intensity)
    require_crowding = intensity > 0.0
    elig, excluded = scoring._collect_eligibility(
        hotel,
        cfg,
        actionable_only=True,
        require_peer=True,
        require_neg_rate=True,
        require_crowding=require_crowding,
    )
    elig_nc, _ = scoring._collect_eligibility(
        hotel, cfg, actionable_only=True, require_peer=True,
        require_neg_rate=True, require_crowding=False,
    )
    scores = value_aware_scores(hotel, cfg, value_vector, intensity,
                                weights=weights, actionable_only=True)
    pick = scoring._tie_pick([(s, a) for a, s in scores.items()], higher=True)
    w = scoring._validated_weights(cfg, weights)
    vv = normalize_value(value_vector or {}, ACTIONABLE)
    rule = (
        f"score = v_a * ({w['gap']}*gap_norm + {w['criticism']}*criticism_norm) "
        f"- {w['unreliable']}*(1-reliability); v_a = learned cross-sectional "
        f"aspect value (normalised to mean 1 over actionable aspects). "
        f"Gates identical to peer_relative."
    )
    abstention = scoring._peer_relative_abstention(intensity, elig, elig_nc)
    out = scoring._make_policy_result(
        "value_aware",
        "Value-Aware Peer-Relative (learned aspect value)",
        rule,
        hotel,
        cfg,
        elig,
        excluded,
        pick,
        scores,
        extra={
            "assumed_intensity": intensity,
            "heuristic": False,
            "weights_are_design_choices": False,
            "value_vector_applied": vv,
            "rationale_default": (
                "Same evidence gates as the shipped heuristic; the deficit terms are "
                "weighted by an aspect value coefficient learned on hotels OUTSIDE "
                "this hotel's estimation split. Associational, not causal."
            ),
            "rationale_scenario": (
                "Scenario mode (intensity>0) behaves as in peer_relative: crowding "
                "is a separate scenario diagnostic."
            ),
            "mode": "scenario" if intensity > 0.0 else "default",
            "crowding_available": not require_crowding or bool(elig),
            "abstention_reason": abstention,
        },
    )
    return out

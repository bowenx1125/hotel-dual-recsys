"""Synthetic "hotel improved an aspect" simulation. Stdlib only; no demo imports.

Chain, with each step computed by the same formulas as the real pipeline:

1. The hotel's real review mentions for the quarter (pos / neg / neutral
   counts per aspect) are expanded into synthetic mention records.
2. ASSUMPTION: after improving aspect A, a share ``flip_share`` of A's
   negative mentions become positive (same guests, happier). Nothing else
   changes.
3. Aspect measures are recomputed exactly as the panel adapter does:
   net = 2 * (pos + k/2) / (pos + neg + k) - 1  (= (pos - neg) / (pos + neg + k)),
   reliability = (pos + neg) / (pos + neg + k),
   neg_rate = neg / mentions, gap = peer_median_net - net, percentile among
   gated peers + self. Peers are left unchanged.
4. The manager recommendation (``explain_action_vs_diagnostic``) is rerun.
5. ASSUMPTION: rating change = ``rating_per_net`` x change in the
   mention-weighted overall review balance; revenue change (%) =
   ``revenue_pct_per_rating`` x rating change.

Steps 2 and 5 are adjustable assumptions, not estimates. The outputs show
what the recommendation logic implies if improvements work as assumed; they
are not predictions and not evidence of real-world impact.
"""
from __future__ import annotations

import hashlib
import math
import random

from .scoring import (
    eligible_aspects,
    explain_action_vs_diagnostic,
    median,
    percentile_rank,
)

DEFAULT_ASSUMPTIONS: dict[str, float] = {
    # Share of the improved aspect's negative mentions that turn positive.
    "flip_share": 0.5,
    # Guest-score points (10-point scale) per +1.0 overall review balance.
    "rating_per_net": 2.5,
    # Revenue change in % per +1.0 guest-score point.
    "revenue_pct_per_rating": 5.0,
}


def _f(x) -> float | None:
    if isinstance(x, bool) or x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _k(cfg: dict) -> float:
    k = _f(cfg.get("reliability_k", 10.0))
    if k is None or k <= 0:
        raise ValueError("reliability_k must be a positive number")
    return k


def _assumptions(assumptions: dict | None) -> dict[str, float]:
    out = dict(DEFAULT_ASSUMPTIONS)
    for key, val in (assumptions or {}).items():
        if key not in out:
            raise ValueError(f"unknown assumption: {key}")
        v = _f(val)
        if v is None or v < 0:
            raise ValueError(f"assumption {key} must be finite and nonnegative, got {val!r}")
        out[key] = v
    if out["flip_share"] > 1.0:
        raise ValueError("flip_share must be in [0, 1]")
    return out


def _counts(rec) -> tuple[int, int, int] | None:
    """(pos, neg, neu) for a measured aspect with consistent integer counts."""
    if not isinstance(rec, dict) or rec.get("has_measurement") is not True:
        return None
    vals = []
    for key in ("pos_mentions", "neg_mentions", "neu_mentions"):
        v = rec.get(key, 0) if key == "neu_mentions" else rec.get(key)
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            return None
        vals.append(v)
    pos, neg, neu = vals
    m = rec.get("mention_count")
    if not isinstance(m, int) or isinstance(m, bool) or m != pos + neg + neu:
        return None
    return pos, neg, neu


# ---------------------------------------------------------------------------
# Peer context (unchanged by the simulation)
# ---------------------------------------------------------------------------

def peer_nets(hotel: dict, aspect: str, hotels_by_id: dict, cfg: dict) -> list[float]:
    """Gated peer nets for ``aspect``, mirroring panel_adapter's rule."""
    min_m = int(cfg.get("min_mentions", 5))
    min_r = float(cfg.get("min_reliability", 0.3))
    out: list[float] = []
    for pid in hotel.get("peer_ids") or []:
        peer = hotels_by_id.get(pid)
        if not peer:
            continue
        rec = (peer.get("aspects") or {}).get(aspect) or {}
        if not rec.get("has_measurement"):
            continue
        net, rel = _f(rec.get("net")), _f(rec.get("reliability"))
        if net is None or rel is None or rel < min_r:
            continue
        if int(rec.get("mention_count") or 0) < min_m:
            continue
        out.append(net)
    return out


def recompute_aspect(rec: dict, pos: int, neg: int, neu: int, k: float, peers: list[float] | None) -> dict:
    """Return ``rec`` with counts replaced and derived measures recomputed."""
    m = pos + neg + neu
    # Same arithmetic as src/autonomous/common.py::smoothed_net, so unchanged
    # counts reproduce stored values bit for bit (ties in percentile depend on it).
    tot = pos + neg
    p = (pos + 0.5 * k) / (tot + k)
    out = dict(rec)
    out.update(
        pos_mentions=pos,
        neg_mentions=neg,
        neu_mentions=neu,
        mention_count=m,
        has_measurement=m > 0,
        net=float(2.0 * p - 1.0),
        reliability=float(tot / (tot + k)),
        neg_rate=(neg / m) if m else None,
    )
    if peers is not None:
        med = median(peers)
        out["peer_median_net"] = med
        out["peer_n"] = len(peers)
        out["gap"] = (med - out["net"]) if med is not None else None
        out["percentile"] = percentile_rank(out["net"], peers + [out["net"]])
    return out


# ---------------------------------------------------------------------------
# Synthetic review mention records (for display; same totals as the counts)
# ---------------------------------------------------------------------------

def _rng(seed: int, *parts: str) -> random.Random:
    h = hashlib.sha256("|".join([str(seed), *parts]).encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))


def synthesize_mentions(hotel: dict, cfg: dict, seed: int = 0) -> list[dict]:
    """Expand a hotel's real per-aspect counts into synthetic mention records.

    Each record: ``review_id`` (``sim-0001``...), ``aspect``, ``sentiment``
    (``pos`` / ``neg`` / ``neu``). Review ids are drawn deterministically from
    ``n_reviews`` slots; totals per aspect equal the hotel's counts exactly.
    No review text is generated.
    """
    n_reviews = max(1, int(hotel.get("n_reviews") or 1))
    width = max(4, len(str(n_reviews)))
    records: list[dict] = []
    for aspect in cfg.get("aspects") or []:
        c = _counts((hotel.get("aspects") or {}).get(aspect))
        if c is None:
            continue
        pos, neg, neu = c
        labels = ["pos"] * pos + ["neg"] * neg + ["neu"] * neu
        rng = _rng(seed, str(hotel.get("hotel_id")), aspect)
        rng.shuffle(labels)
        for lab in labels:
            rid = rng.randrange(n_reviews) + 1
            records.append({"review_id": f"sim-{rid:0{width}d}", "aspect": aspect, "sentiment": lab})
    records.sort(key=lambda r: (r["review_id"], r["aspect"], r["sentiment"]))
    return records


def improve_mentions(records: list[dict], aspect: str, flip_share: float, seed: int = 0) -> list[dict]:
    """Copy of ``records`` where round(flip_share * neg) negatives on ``aspect``
    become positive. Changed records carry ``sentiment_before``."""
    share = _f(flip_share)
    if share is None or not 0.0 <= share <= 1.0:
        raise ValueError("flip_share must be in [0, 1]")
    neg_idx = [i for i, r in enumerate(records) if r["aspect"] == aspect and r["sentiment"] == "neg"]
    n_flip = int(round(share * len(neg_idx)))
    chosen = set(_rng(seed, "flip", aspect).sample(neg_idx, n_flip)) if n_flip else set()
    out = []
    for i, r in enumerate(records):
        r2 = dict(r)
        if i in chosen:
            r2["sentiment_before"] = "neg"
            r2["sentiment"] = "pos"
        out.append(r2)
    return out


def aggregate_mentions(
    records: list[dict], hotel: dict, cfg: dict, hotels_by_id: dict | None = None
) -> dict:
    """Rebuild ``hotel`` aspect measures from mention records."""
    k = _k(cfg)
    tallies: dict[str, list[int]] = {}
    for r in records:
        t = tallies.setdefault(r["aspect"], [0, 0, 0])
        t[{"pos": 0, "neg": 1, "neu": 2}[r["sentiment"]]] += 1
    out = dict(hotel)
    aspects = {a: dict(v) for a, v in (hotel.get("aspects") or {}).items()}
    for a, (pos, neg, neu) in tallies.items():
        peers = peer_nets(hotel, a, hotels_by_id, cfg) if hotels_by_id is not None else None
        aspects[a] = recompute_aspect(aspects.get(a, {}), pos, neg, neu, k, peers)
    out["aspects"] = aspects
    return out


# ---------------------------------------------------------------------------
# Count-level simulation (fast path used for comparisons and city experiments)
# ---------------------------------------------------------------------------

def improve_hotel(
    hotel: dict, aspect: str, flip_share: float, cfg: dict, hotels_by_id: dict | None = None
) -> dict:
    """Copy of ``hotel`` after round(flip_share * neg) of ``aspect``'s negative
    mentions turn positive, with that aspect's measures recomputed.

    Equivalent to synthesize -> improve -> aggregate, without building records.
    """
    share = _f(flip_share)
    if share is None or not 0.0 <= share <= 1.0:
        raise ValueError("flip_share must be in [0, 1]")
    rec = (hotel.get("aspects") or {}).get(aspect)
    c = _counts(rec)
    if c is None:
        raise ValueError(f"aspect {aspect!r} has no usable review counts")
    pos, neg, neu = c
    n_flip = int(round(share * neg))
    peers = peer_nets(hotel, aspect, hotels_by_id, cfg) if hotels_by_id is not None else None
    out = dict(hotel)
    out["aspects"] = dict(hotel.get("aspects") or {})
    out["aspects"][aspect] = recompute_aspect(rec, pos + n_flip, neg - n_flip, neu, _k(cfg), peers)
    out["simulated_improvements"] = list(hotel.get("simulated_improvements") or []) + [
        {"aspect": aspect, "flipped": n_flip, "flip_share": share}
    ]
    return out


def overall_balance(hotel: dict, cfg: dict) -> float | None:
    """Mention-weighted mean net over measured aspects (all aspects)."""
    num = den = 0.0
    for a in cfg.get("aspects") or []:
        rec = (hotel.get("aspects") or {}).get(a) or {}
        if rec.get("has_measurement") is not True:
            continue
        net, m = _f(rec.get("net")), _f(rec.get("mention_count"))
        if net is None or m is None or m <= 0:
            continue
        num += m * net
        den += m
    return num / den if den else None


def outcome(before: dict, after: dict, cfg: dict, assumptions: dict | None = None) -> dict:
    """Overall balance, assumed rating and revenue change from before to after."""
    a = _assumptions(assumptions)
    b0, b1 = overall_balance(before, cfg), overall_balance(after, cfg)
    d_bal = (b1 - b0) if b0 is not None and b1 is not None else 0.0
    d_rating = a["rating_per_net"] * d_bal
    return {
        "balance_before": b0,
        "balance_after": b1,
        "d_balance": d_bal,
        "d_rating": d_rating,
        "d_revenue_pct": a["revenue_pct_per_rating"] * d_rating,
    }


def candidate_aspects(hotel: dict, cfg: dict) -> list[str]:
    """Aspects the recommender could choose from: actionable (location
    excluded), passing the same evidence gates, with usable review counts.
    Using the same set keeps the random / alternative baselines fair."""
    elig = set(eligible_aspects(hotel, cfg, actionable_only=True))
    return [
        a for a in cfg.get("aspects") or []
        if a in elig and _counts((hotel.get("aspects") or {}).get(a)) is not None
    ]


def recommended_aspect(hotel: dict, cfg: dict) -> str | None:
    return explain_action_vs_diagnostic(hotel, cfg)["actionable_recommendation"]


def compare_actions(
    hotel: dict,
    cfg: dict,
    assumptions: dict | None = None,
    hotels_by_id: dict | None = None,
) -> list[dict]:
    """Simulate the same-strength improvement on each candidate aspect.

    Rows sorted by assumed rating gain desc, then aspect name. Each row has
    ``aspect``, ``recommended`` flag, ``flipped`` and the ``outcome`` fields.
    """
    a = _assumptions(assumptions)
    rec = recommended_aspect(hotel, cfg)
    rows = []
    for asp in candidate_aspects(hotel, cfg):
        after = improve_hotel(hotel, asp, a["flip_share"], cfg, hotels_by_id)
        row = {"aspect": asp, "recommended": asp == rec,
               "flipped": after["simulated_improvements"][-1]["flipped"]}
        row.update(outcome(hotel, after, cfg, a))
        rows.append(row)
    rows.sort(key=lambda r: (-r["d_rating"], r["aspect"]))
    return rows


def follow_recommendations(
    hotel: dict,
    cfg: dict,
    rounds: int = 3,
    assumptions: dict | None = None,
    hotels_by_id: dict | None = None,
) -> list[dict]:
    """Repeatedly improve whatever the manager view recommends next.

    Each step: ``round``, ``aspect`` (None = abstain, stops), ``flipped``,
    ``stalled`` (the recommended aspect had no complaints left to convert, so
    nothing changes and the loop stops) and cumulative ``outcome`` versus the
    original hotel.
    """
    a = _assumptions(assumptions)
    current = hotel
    steps = []
    for i in range(1, int(rounds) + 1):
        asp = recommended_aspect(current, cfg)
        if asp is None or _counts(current["aspects"].get(asp)) is None:
            steps.append({"round": i, "aspect": None, "flipped": 0, "stalled": False})
            break
        current = improve_hotel(current, asp, a["flip_share"], cfg, hotels_by_id)
        flipped = current["simulated_improvements"][-1]["flipped"]
        step = {"round": i, "aspect": asp, "flipped": flipped, "stalled": flipped == 0}
        step.update(outcome(hotel, current, cfg, a))
        steps.append(step)
        if flipped == 0:
            break
    return steps


def city_experiment(
    hotels: list[dict],
    city: str,
    cfg: dict,
    assumptions: dict | None = None,
    hotels_by_id: dict | None = None,
) -> dict:
    """Every eligible hotel in ``city`` makes one same-strength improvement.

    Compares mean assumed rating gain when improving: the recommended aspect,
    a uniformly random candidate (expected value), the hotel's best-reviewed
    candidate, and the best possible candidate (oracle under the assumptions).
    Hotels where the recommender abstains are counted but skipped.
    """
    a = _assumptions(assumptions)
    rec_g, rand_g, strong_g, oracle_g = [], [], [], []
    beats_random = matches_oracle = abstained = 0
    for h in hotels:
        if h.get("city") != city or h.get("eligible") is False:
            continue
        rows = compare_actions(h, cfg, a, hotels_by_id)
        rec_rows = [r for r in rows if r["recommended"]]
        if not rows or not rec_rows:
            abstained += 1
            continue
        gains = {r["aspect"]: r["d_rating"] for r in rows}
        rec_gain = rec_rows[0]["d_rating"]
        rand_gain = sum(gains.values()) / len(gains)
        strongest = max(
            rows, key=lambda r: (h["aspects"][r["aspect"]]["net"], r["aspect"])
        )["aspect"]
        oracle_gain = max(gains.values())
        rec_g.append(rec_gain)
        rand_g.append(rand_gain)
        strong_g.append(gains[strongest])
        oracle_g.append(oracle_gain)
        beats_random += rec_gain >= rand_gain - 1e-12
        matches_oracle += rec_gain >= oracle_gain - 1e-12
    n = len(rec_g)

    def mean(xs):
        return sum(xs) / len(xs) if xs else None

    return {
        "n_hotels": n,
        "n_abstained": abstained,
        "mean_d_rating": {
            "recommended": mean(rec_g),
            "random": mean(rand_g),
            "best_reviewed": mean(strong_g),
            "oracle": mean(oracle_g),
        },
        "share_recommended_ge_random": (beats_random / n) if n else None,
        "share_recommended_is_best": (matches_oracle / n) if n else None,
        "revenue_pct_per_rating": a["revenue_pct_per_rating"],
    }

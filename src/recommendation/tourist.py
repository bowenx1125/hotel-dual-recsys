"""Tourist-side hotel matching from aspect net sentiment + explicit preferences.

Stdlib only; no demo imports. Same measurement as the manager view, different
decision: the manager view asks "which aspect to fix first" (peer gaps); this
module asks "given the aspects I care about, which hotels in the city fit
better".

    score(h) = sum_a(w_a * reliability_a * net_a) / sum_a(w_a * reliability_a)

Only aspects with ``w_a > 0``, a measurement, finite reliability in [0, 1] and
finite ``net`` contribute. Peer gaps, peer-relative or intensity scores are
deliberately NOT used. The result is a match on historical reviews: it says
nothing about live prices, availability, bookings or conversion.
"""
from __future__ import annotations

import math

from .scoring import ASPECTS_DEFAULT

STATUS_OK = "ok"
STATUS_INSUFFICIENT = "insufficient_evidence"


class ZeroTouristWeightsError(ValueError):
    """All preference weights are zero, so there is nothing to rank by."""


def _finite(x) -> float | None:
    if isinstance(x, bool) or x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _aspects(cfg: dict | None) -> list[str]:
    aspects = (cfg or {}).get("aspects") or ASPECTS_DEFAULT
    return list(aspects)


def uniform_tourist_weights(cfg: dict | None = None, value: float = 1.0) -> dict[str, float]:
    return {a: float(value) for a in _aspects(cfg)}


def validate_tourist_weights(weights: dict | None, cfg: dict | None = None) -> dict[str, float]:
    """Return weights for every configured aspect; missing keys count as 0.

    Raises ``ValueError`` for unknown aspects or negative / non-finite values
    and ``ZeroTouristWeightsError`` when every weight is zero.
    """
    aspects = _aspects(cfg)
    if weights is None:
        return uniform_tourist_weights(cfg)
    if not isinstance(weights, dict):
        raise ValueError("weights must be a dict of aspect -> nonnegative number")
    unknown = sorted(set(weights) - set(aspects))
    if unknown:
        raise ValueError(f"unknown aspects in weights: {unknown}")
    out: dict[str, float] = {}
    for a in aspects:
        v = weights.get(a, 0.0)
        f = _finite(v)
        if f is None or f < 0.0:
            raise ValueError(f"weights[{a}] must be finite and nonnegative, got {v!r}")
        out[a] = f
    if not any(v > 0.0 for v in out.values()):
        raise ZeroTouristWeightsError("all tourist weights are zero")
    return out


def tourist_weights_all_zero(weights: dict | None) -> bool:
    if weights is None:
        return False
    return not any((_finite(v) or 0.0) > 0.0 for v in weights.values())


def _usable_aspect(rec) -> tuple[float, float] | None:
    """Return (net, reliability) when the aspect may enter the score."""
    if not isinstance(rec, dict):
        return None
    hm = rec.get("has_measurement", True)
    if hm is not True and not (type(hm) is int and hm == 1):
        return None
    net = _finite(rec.get("net"))
    rel = _finite(rec.get("reliability"))
    if net is None or rel is None or not (0.0 <= rel <= 1.0):
        return None
    return net, rel


def _score_with_validated(hotel: dict, w: dict[str, float], aspects: list[str]) -> dict:
    recs = hotel.get("aspects") if isinstance(hotel.get("aspects"), dict) else {}
    per_aspect: dict[str, dict] = {}
    num = 0.0
    den = 0.0
    total_w = sum(w.values())
    used_w = 0.0
    for a in aspects:
        rec = recs.get(a)
        usable = _usable_aspect(rec)
        row = {
            "weight": w[a],
            "net": _finite((rec or {}).get("net")) if isinstance(rec, dict) else None,
            "reliability": _finite((rec or {}).get("reliability")) if isinstance(rec, dict) else None,
            "mention_count": (rec or {}).get("mention_count") if isinstance(rec, dict) else None,
            "measured": usable is not None,
            "used": False,
            "effective_weight": 0.0,
            "contribution": None,
        }
        if usable is not None and w[a] > 0.0:
            net, rel = usable
            ew = w[a] * rel
            if ew > 0.0:
                row["used"] = True
                row["effective_weight"] = ew
                num += ew * net
                den += ew
                used_w += w[a]
        per_aspect[a] = row

    used = [a for a in aspects if per_aspect[a]["used"]]
    if den <= 0.0:
        return {
            "hotel_id": hotel.get("hotel_id"),
            "hotel_name": hotel.get("hotel_name"),
            "status": STATUS_INSUFFICIENT,
            "score": None,
            "aspects": per_aspect,
            "used_aspects": [],
            "weight_coverage": 0.0,
            "strongest_aspect": None,
            "weakest_aspect": None,
        }

    for a in used:
        row = per_aspect[a]
        row["contribution"] = row["effective_weight"] * row["net"] / den

    # Ties: strongest takes the earliest aspect in config order, weakest the
    # latest, so the two differ whenever more than one aspect is used.
    strongest = max(used, key=lambda a: (per_aspect[a]["net"], -aspects.index(a)))
    weakest = min(used, key=lambda a: (per_aspect[a]["net"], -aspects.index(a)))
    return {
        "hotel_id": hotel.get("hotel_id"),
        "hotel_name": hotel.get("hotel_name"),
        "status": STATUS_OK,
        "score": num / den,
        "aspects": per_aspect,
        "used_aspects": used,
        "weight_coverage": used_w / total_w,
        "strongest_aspect": strongest,
        "weakest_aspect": weakest if weakest != strongest else None,
    }


def tourist_match_scores(hotel: dict, weights: dict | None, cfg: dict | None = None) -> dict:
    """Score one hotel against the tourist's aspect weights.

    Returns ``status`` (``ok`` / ``insufficient_evidence``), ``score`` in
    [-1, 1] or None, per-aspect rows (weight, net, reliability, measured, used,
    effective_weight, contribution — contributions sum to ``score``),
    ``used_aspects``, ``weight_coverage`` (share of the tourist's weight that
    landed on measured aspects) and strongest / weakest used aspect by net.
    ``weakest_aspect`` is None when only one aspect is used.
    """
    aspects = _aspects(cfg)
    w = validate_tourist_weights(weights, cfg)
    return _score_with_validated(hotel, w, aspects)


def _sort_key(r: dict) -> tuple:
    return (-r["score"], str(r.get("hotel_name") or ""), str(r.get("hotel_id") or ""))


def rank_hotels_for_tourist(
    hotels: list[dict],
    city: str,
    weights: dict | None,
    cfg: dict | None = None,
) -> list[dict]:
    """Rank eligible hotels in ``city`` by ``tourist_match_scores``.

    Order: scored hotels by score desc, then hotel_name asc, then hotel_id asc;
    then insufficient-evidence hotels (score None) by name/id. Each row gets
    ``rank`` (1-based, None when insufficient). Raises
    ``ZeroTouristWeightsError`` when every weight is zero.
    """
    aspects = _aspects(cfg)
    w = validate_tourist_weights(weights, cfg)
    results = [
        _score_with_validated(h, w, aspects)
        for h in hotels
        if h.get("city") == city and h.get("eligible") is not False
    ]
    ok = sorted((r for r in results if r["status"] == STATUS_OK), key=_sort_key)
    insufficient = sorted(
        (r for r in results if r["status"] != STATUS_OK),
        key=lambda r: (str(r.get("hotel_name") or ""), str(r.get("hotel_id") or "")),
    )
    for i, r in enumerate(ok, start=1):
        r["rank"] = i
    for r in insufficient:
        r["rank"] = None
    return ok + insufficient


# ---------------------------------------------------------------------------
# Illustrative personas (hand-picked demo weights, not learned from users) and
# a helper to re-rank a city with one hotel swapped for a simulated copy (see
# src/recommendation/simulation.py). Neither is a prediction.
# ---------------------------------------------------------------------------

TOURIST_PERSONAS: dict[str, dict[str, int]] = {
    "balanced": {
        "location": 3, "cleanliness": 3, "breakfast": 3, "service": 3,
        "noise": 3, "room": 3, "value": 3,
    },
    "business": {
        "location": 5, "cleanliness": 4, "breakfast": 2, "service": 4,
        "noise": 4, "room": 3, "value": 1,
    },
    "family": {
        "location": 3, "cleanliness": 5, "breakfast": 4, "service": 3,
        "noise": 3, "room": 5, "value": 3,
    },
    "budget": {
        "location": 4, "cleanliness": 3, "breakfast": 1, "service": 1,
        "noise": 2, "room": 1, "value": 5,
    },
    "couple": {
        "location": 4, "cleanliness": 3, "breakfast": 3, "service": 4,
        "noise": 5, "room": 4, "value": 2,
    },
}


def persona_for_weights(weights: dict | None) -> str | None:
    """Return the persona id whose weights equal ``weights`` exactly, else None."""
    if not isinstance(weights, dict):
        return None
    nonzero = {k for k, v in weights.items() if (_finite(v) or 0.0) != 0.0}
    for pid, pw in TOURIST_PERSONAS.items():
        same = all(_finite(weights.get(a, 0)) == float(v) for a, v in pw.items())
        if same and nonzero <= set(pw):
            return pid
    return None


def rank_change_with_replacement(
    hotels: list[dict],
    city: str,
    replacement: dict,
    weights: dict | None,
    cfg: dict | None = None,
) -> dict:
    """Rank ``city`` before and after swapping in ``replacement`` for the hotel
    with the same ``hotel_id`` (e.g. a simulated copy). Ranks are None when
    the hotel has insufficient evidence."""
    hid = replacement.get("hotel_id")
    if not any(h.get("hotel_id") == hid and h.get("city") == city for h in hotels):
        raise ValueError(f"hotel {hid!r} not found in city {city!r}")
    swapped = [replacement if h.get("hotel_id") == hid else h for h in hotels]

    def _find(ranked: list[dict]) -> dict:
        return next(r for r in ranked if r.get("hotel_id") == hid)

    before = _find(rank_hotels_for_tourist(hotels, city, weights, cfg))
    after = _find(rank_hotels_for_tourist(swapped, city, weights, cfg))
    return {
        "hotel_id": hid,
        "rank_before": before["rank"],
        "rank_after": after["rank"],
        "score_before": before["score"],
        "score_after": after["score"],
    }

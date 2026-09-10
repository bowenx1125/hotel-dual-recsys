"""Aspect keyword gate + placeholder filters for weak-labeled sections."""
from __future__ import annotations

import re
from typing import Iterable

ASPECTS = ["location", "cleanliness", "breakfast", "service", "noise", "room", "value"]

# Reused from src/aspect/extract_aspects.py with documented fixes in DECISIONS.md:
# - removed ultra-broad "area" from location (false positives)
# - removed bare "hear"/"heard" from noise (too many false positives)
ASPECT_KEYWORDS = {
    "location": [
        "location", "located", "locate", "metro", "subway", "station",
        "walk", "walking", "centre", "center", "central", "downtown",
        "distance", "nearby", "close to", "far from", "transport",
        "tram", "bus", "airport", "neighbourhood", "neighborhood",
        "grand place", "city center", "city centre",
    ],
    "cleanliness": [
        "clean", "dirty", "dust", "dusty", "hygien", "spotless",
        "stain", "smell", "smelly", "tidy", "mold", "mould",
        "filthy", "unclean", "immaculate", "grubby",
    ],
    "breakfast": [
        "breakfast", "buffet", "morning meal", "croissant",
        "continental breakfast", "brekkie",
    ],
    "service": [
        "staff", "service", "reception", "receptionist", "helpful",
        "friendly", "rude", "welcome", "welcoming", "host", "hostess",
        "manager", "employee", "concierge", "attentive", "polite",
        "unhelpful", "courteous",
    ],
    "noise": [
        "noise", "noisy", "quiet", "loud", "soundproof", "sound proof",
        "silent", "silence", "traffic noise", "thin wall", "peaceful",
    ],
    "room": [
        "room", "bed", "bedroom", "bathroom", "shower", "toilet",
        "spacious", "comfortable", "comfy", "mattress", "pillow",
        "air conditioning", "air con", "a/c", "heating", "cramped",
        "tiny room", "small room",
    ],
    "value": [
        "value", "price", "expensive", "cheap", "worth", "money",
        "overpriced", "affordable", "cost", "pricey", "bargain",
        "value for money", "good deal", "reasonable price",
    ],
}

ASPECT_RE: dict[str, re.Pattern] = {}
for asp, kws in ASPECT_KEYWORDS.items():
    parts = []
    for kw in kws:
        if " " in kw:
            parts.append(re.escape(kw))
        else:
            parts.append(r"\b" + re.escape(kw))
    ASPECT_RE[asp] = re.compile("|".join(parts), re.IGNORECASE)


def normalize_placeholder(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def is_placeholder(text: str, placeholders: Iterable[str]) -> bool:
    t = normalize_placeholder(text)
    if not t:
        return True
    # strip trailing punctuation
    t2 = t.strip(" .!,;")
    for p in placeholders:
        if t2 == p or t == p:
            return True
    return False


def gate_aspects(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    return [a for a in ASPECTS if ASPECT_RE[a].search(text)]


def smoothed_net(pos: int, neg: int, prior_strength: float) -> tuple[float, float]:
    """Symmetric Beta-Binomial Bayesian shrinkage toward 0.5.

    Prior is a fixed symmetric Beta(α, α) with α = prior_strength / 2.
    This is **not** empirical Bayes unless α is estimated from training data.
    Return (smoothed_net in [-1, 1], reliability = n / (n + prior_strength)).
    """
    ps = float(prior_strength)
    tot = pos + neg
    p = (pos + 0.5 * ps) / (tot + ps) if (tot + ps) > 0 else 0.5
    net = 2.0 * p - 1.0
    rel = tot / (tot + ps) if (tot + ps) > 0 else 0.0
    return float(net), float(rel)


def raw_net(pos: int, neg: int) -> float | None:
    tot = pos + neg
    if tot <= 0:
        return None
    return (pos - neg) / tot

"""City / hotel id helpers for 515K Europe addresses."""
from __future__ import annotations

import hashlib
import re

# Country suffixes appearing in Hotel_Address (longest first).
COUNTRY_SUFFIXES = [
    "United Kingdom",
    "United States of America",
    "Czech Republic",
    "Netherlands",
    "Switzerland",
    "Austria",
    "France",
    "Italy",
    "Spain",
    "Portugal",
    "Germany",
    "Belgium",
    "Ireland",
    "Hungary",
    "Poland",
    "Greece",
    "Sweden",
    "Norway",
    "Denmark",
    "Finland",
    "Romania",
    "Luxembourg",
]


# 515K Europe Hotel Reviews is the classic 6-city Booking corpus.
KNOWN_CITIES = ["London", "Paris", "Amsterdam", "Barcelona", "Vienna", "Milan"]


def parse_city_country(address: str) -> tuple[str, str]:
    addr = re.sub(r"\s+", " ", (address or "").strip())
    country = ""
    for c in COUNTRY_SUFFIXES:
        if addr.endswith(c):
            country = c
            break
    if not country:
        parts = addr.split(" ")
        country = parts[-1] if parts else ""
    city = ""
    for c in KNOWN_CITIES:
        if c in addr:
            city = c
            break
    if not city:
        # fallback: token before country suffix
        rest = addr[: -len(country)].strip() if country and addr.endswith(country) else addr
        toks = rest.split(" ")
        city = toks[-1] if toks else ""
    return city, country


def hotel_id_from_address(address: str) -> str:
    raw = (address or "").strip().lower()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

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


def parse_city_country(address: str) -> tuple[str, str]:
    addr = re.sub(r"\s+", " ", (address or "").strip())
    country = ""
    rest = addr
    for c in COUNTRY_SUFFIXES:
        if addr.endswith(c):
            country = c
            rest = addr[: -len(c)].strip()
            break
    if not country:
        parts = addr.split(" ")
        country = parts[-1] if parts else ""
        rest = " ".join(parts[:-1]) if len(parts) > 1 else ""
    # city is last token of rest (handles "Amsterdam", "Paris", "Barcelona", "Milan", "Vienna", "London")
    toks = rest.split(" ")
    city = toks[-1] if toks else ""
    # Special: "The Hague" / "Den Haag" rare; "Edinburgh" etc ok
    if city.lower() in {"kingdom"}:
        city = toks[-2] if len(toks) >= 2 else city
    return city, country


def hotel_id_from_address(address: str) -> str:
    raw = (address or "").strip().lower()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

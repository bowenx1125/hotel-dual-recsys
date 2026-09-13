#!/usr/bin/env python3
"""Audit 515K Europe CSV in FYP_DATA_CACHE_ROOT (no raw text in outputs)."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.temporal.geo_parse import parse_city_country
from src.temporal.io_util import atomic_write_json, atomic_write_text, sha256_file


def parse_date(s: str):
    s = (s or "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-root", default=os.environ.get("FYP_DATA_CACHE_ROOT", str(ROOT / "data" / "cache")))
    ap.add_argument("--relative", default="d1_europe/Hotel_Reviews.csv")
    args = ap.parse_args()
    if not args.cache_root:
        print("FYP_DATA_CACHE_ROOT required", file=sys.stderr)
        return 2
    path = Path(args.cache_root) / args.relative
    out = ROOT / "outputs" / "overnight" / "data_audit"
    out.mkdir(parents=True, exist_ok=True)

    hotels = set()
    cities = set()
    dates = []
    date_fail = 0
    lat_ok = 0
    rows = 0
    cols = None
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        cols = r.fieldnames
        for row in r:
            rows += 1
            hotels.add(row.get("Hotel_Name", ""))
            city, _ = parse_city_country(row.get("Hotel_Address", ""))
            if city:
                cities.add(city)
            dt = parse_date(row.get("Review_Date", ""))
            if dt:
                dates.append(dt)
            else:
                date_fail += 1
            try:
                float(row["lat"])
                float(row["lng"])
                lat_ok += 1
            except Exception:
                pass

    manifest = {
        "source": "huggingface:Dricz/515k-Hotel-Reviews-In-Europe/Hotel_Reviews.csv",
        "download_date_local": datetime.utcnow().strftime("%Y-%m-%d"),
        "filename": path.name,
        "cache_env": "FYP_DATA_CACHE_ROOT",
        "relative_path": args.relative,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "n_rows": rows,
        "n_hotels_by_name": len(hotels),
        "n_cities_parsed": len(cities),
        "lat_lng_ok": lat_ok,
        "lat_lng_coverage": lat_ok / rows if rows else 0,
        "date_min": min(dates).date().isoformat() if dates else None,
        "date_max": max(dates).date().isoformat() if dates else None,
        "date_parse_fail": date_fail,
        "columns": cols,
        "committed_to_git": False,
        "note": "Local cache only; not committed.",
    }
    atomic_write_json(out / "europe_515k_manifest.json", manifest)
    # append to RAW_DATA_AUDIT
    extra = f"""

## 515K Europe (cache)

- Source: `{manifest['source']}`
- Bytes: **{manifest['bytes']}**
- SHA256: `{manifest['sha256']}`
- Rows: **{manifest['n_rows']}**
- Hotels (by name): **{manifest['n_hotels_by_name']}**
- Cities (parsed): **{manifest['n_cities_parsed']}**
- Lat/lng coverage: **{manifest['lat_lng_coverage']:.4f}**
- Date range: **{manifest['date_min']} → {manifest['date_max']}**
- Date parse fail: {manifest['date_parse_fail']}
- Columns: {', '.join(cols or [])}
- Git: **not committed** (cache only under FYP_DATA_CACHE_ROOT)
"""
    audit = out / "RAW_DATA_AUDIT.md"
    txt = audit.read_text(encoding="utf-8") if audit.exists() else "# RAW DATA AUDIT\n"
    if "515K Europe" not in txt:
        atomic_write_text(audit, txt.rstrip() + "\n" + extra)
    print(json.dumps({k: manifest[k] for k in ["n_rows", "n_hotels_by_name", "n_cities_parsed", "date_min", "date_max", "sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

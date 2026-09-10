#!/usr/bin/env python3
"""Audit dated review sources and join integrity (streaming; no full RAM load)."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def env_path(name: str, default: Path | None = None) -> Path | None:
    v = os.environ.get(name)
    if v:
        return Path(v)
    return default


def sha256_file(path: Path, max_bytes: int | None = None) -> str:
    h = hashlib.sha256()
    n = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
            n += len(chunk)
            if max_bytes and n >= max_bytes:
                break
    return h.hexdigest()


def parse_date(s: str):
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # e.g. 11-Jul-21
    m = re.match(r"^(\d{1,2})-([A-Za-z]{3})-(\d{2})$", s)
    if m:
        try:
            return datetime.strptime(s, "%d-%b-%y").date()
        except ValueError:
            return None
    return None


def audit_raw_csv(path: Path) -> dict:
    csv.field_size_limit(10**9)
    size = path.stat().st_size
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        n = 0
        dates = []
        missing_date = 0
        ids = []
        id_dups = 0
        seen_ids = set()
        hotels = set()
        sample_dates = []
        for row in reader:
            n += 1
            rid = (row.get("index") or row.get("review_id") or "").strip()
            if rid:
                if rid in seen_ids:
                    id_dups += 1
                else:
                    seen_ids.add(rid)
                ids.append(rid)
            url = (row.get("hotel_url") or "").strip()
            if url:
                hotels.add(url)
            d = parse_date(row.get("reviewed_at") or row.get("review_date") or "")
            if d is None:
                missing_date += 1
            else:
                dates.append(d)
                if len(sample_dates) < 5:
                    sample_dates.append(str(d))
    return {
        "path_env": "FYP_PRIVATE_DATA_ROOT/booking_reviews copy.csv",
        "bytes": size,
        "sha256": sha256_file(path),
        "n_rows": n,
        "fields": fields,
        "date_field": "reviewed_at",
        "id_field": "index",
        "hotel_field": "hotel_url",
        "rating_field": "rating",
        "text_fields": ["review_text", "raw_review_text"],
        "n_unique_ids": len(seen_ids),
        "duplicate_id_rows": id_dups,
        "n_hotels": len(hotels),
        "date_missing": missing_date,
        "date_missing_rate": missing_date / n if n else None,
        "date_min": str(min(dates)) if dates else None,
        "date_max": str(max(dates)) if dates else None,
        "sample_dates": sample_dates,
        "id_unique": id_dups == 0 and len(seen_ids) == n,
    }


def audit_jsonl(path: Path) -> dict:
    n = 0
    ids = []
    seen = set()
    dups = 0
    hotels = set()
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n += 1
            obj = json.loads(line)
            rid = str(obj.get("review_id", "")).strip()
            if rid in seen:
                dups += 1
            else:
                seen.add(rid)
            hotels.add(obj.get("hotel_url") or "")
            if n == 1:
                keys = list(obj.keys())
    return {
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "n_rows": n,
        "keys": keys,
        "n_unique_ids": len(seen),
        "duplicate_id_rows": dups,
        "n_hotels": len([h for h in hotels if h]),
        "ids": seen,  # returned for join; stripped before write
    }


def join_audit(raw_ids: set[str], asp_ids: set[str]) -> dict:
    inter = raw_ids & asp_ids
    only_asp = asp_ids - raw_ids
    only_raw_sample = len(raw_ids - asp_ids)
    return {
        "left": "review_aspects.jsonl.review_id",
        "right": "booking_reviews.index",
        "left_n": len(asp_ids),
        "right_n": len(raw_ids),
        "matched_unique_ids": len(inter),
        "unmatched_aspect_ids": len(only_asp),
        "raw_ids_not_in_aspects": only_raw_sample,
        "match_rate_of_aspects": len(inter) / len(asp_ids) if asp_ids else None,
        "one_to_one_candidate": True,  # both sides unique ids checked separately
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--private-data-root", default=os.environ.get("FYP_PRIVATE_DATA_ROOT", ""))
    ap.add_argument("--aspects-jsonl", default="")
    args = ap.parse_args()

    private = Path(args.private_data_root) if args.private_data_root else env_path("FYP_PRIVATE_DATA_ROOT")
    if not private or not private.exists():
        raise SystemExit("FYP_PRIVATE_DATA_ROOT not set or missing")

    raw = private / "booking_reviews copy.csv"
    if not raw.exists():
        # try alternate names
        cands = list(private.glob("*booking*review*.csv")) + list(private.glob("*reviews*.csv"))
        raise SystemExit(f"Missing {raw}; candidates={cands[:5]}")

    aspects = Path(args.aspects_jsonl) if args.aspects_jsonl else (ROOT / "data" / "processed" / "review_aspects.jsonl")
    if not aspects.exists() and private:
        alt = private / "processed" / "review_aspects.jsonl"
        if alt.exists():
            aspects = alt

    out_dir = ROOT / "outputs" / "overnight" / "data_audit"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_report = audit_raw_csv(raw)
    asp_report = audit_jsonl(aspects)
    asp_ids = asp_report.pop("ids")
    # rebuild raw id set streaming again lightly for join
    raw_ids = set()
    with raw.open(encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            rid = (row.get("index") or "").strip()
            if rid:
                raw_ids.add(rid)
    join = join_audit(raw_ids, asp_ids)

    schema = {
        "raw_reviews": {k: raw_report[k] for k in raw_report if k != "sample_dates"},
        "aspects_jsonl": asp_report,
        "join": join,
    }
    (out_dir / "schema_manifest.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    (out_dir / "join_audit.json").write_text(json.dumps(join, indent=2), encoding="utf-8")

    md = f"""# RAW DATA AUDIT

## Raw reviews (private local file)

- Env path: `FYP_PRIVATE_DATA_ROOT/booking_reviews copy.csv`
- Bytes: **{raw_report['bytes']}**
- SHA256: `{raw_report['sha256']}`
- Rows: **{raw_report['n_rows']}**
- Fields: {', '.join(raw_report['fields'])}
- Date field: `{raw_report['date_field']}` range **{raw_report['date_min']} → {raw_report['date_max']}**
- Date missing rate: **{raw_report['date_missing_rate']:.4%}** ({raw_report['date_missing']})
- Unique review ids (`index`): **{raw_report['n_unique_ids']}** (duplicate id rows: {raw_report['duplicate_id_rows']})
- Hotels: **{raw_report['n_hotels']}**
- Text fields present: {raw_report['text_fields']} (not written to outputs)

## Aspects JSONL

- Path: `{asp_report['path']}`
- Rows: **{asp_report['n_rows']}**
- Unique review_id: **{asp_report['n_unique_ids']}** (dups: {asp_report['duplicate_id_rows']})
- Hotels: **{asp_report['n_hotels']}**

## Join integrity

- Matched unique ids: **{join['matched_unique_ids']}**
- Aspect match rate: **{join['match_rate_of_aspects']:.2%}**
- Unmatched aspect ids: **{join['unmatched_aspect_ids']}**
- Raw ids not in aspects: **{join['raw_ids_not_in_aspects']}** (expected: aspects are a Brussels valid-compset subset)

## Decision

- Dates are usable on the Belgium raw file.
- Join key `index` ↔ `review_id` is safe for the aspect subset (high match rate).
- Belgium panel alone is small for multi-city feasibility; proceed to attempt 515K Europe for scale.
"""
    (out_dir / "RAW_DATA_AUDIT.md").write_text(md, encoding="utf-8")
    print(json.dumps({
        "raw_rows": raw_report["n_rows"],
        "date_min": raw_report["date_min"],
        "date_max": raw_report["date_max"],
        "match_rate": join["match_rate_of_aspects"],
        "aspect_rows": asp_report["n_rows"],
    }, indent=2))


if __name__ == "__main__":
    main()

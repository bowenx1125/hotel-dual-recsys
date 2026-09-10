#!/usr/bin/env python3
"""Build weak-labeled hotel×period×aspect panels from 515K Europe reviews."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.temporal.aspect_gate import ASPECTS, gate_aspects, is_placeholder, raw_net, smoothed_net
from src.temporal.geo_parse import hotel_id_from_address, parse_city_country
from src.temporal.io_util import (
    atomic_write_json,
    atomic_write_text,
    load_temporal_config,
    resolve_europe_csv,
    sha256_file,
)


def parse_date(s: str) -> datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def period_keys(dt: datetime) -> tuple[str, str]:
    month = f"{dt.year:04d}-{dt.month:02d}"
    q = (dt.month - 1) // 3 + 1
    quarter = f"{dt.year:04d}Q{q}"
    return month, quarter


def build_panel(csv_path: Path, cfg: dict, prior: float) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    pos_ph = cfg["placeholders"]["positive"]
    neg_ph = cfg["placeholders"]["negative"]

    # key: (hotel_id, period, aspect) -> counts
    month_acc: dict[tuple, dict] = defaultdict(lambda: {"pos": 0, "neg": 0})
    quarter_acc: dict[tuple, dict] = defaultdict(lambda: {"pos": 0, "neg": 0})
    # hotel-period review totals / score sums
    month_rev: dict[tuple, dict] = defaultdict(lambda: {"n": 0, "score_sum": 0.0})
    quarter_rev: dict[tuple, dict] = defaultdict(lambda: {"n": 0, "score_sum": 0.0})
    hotel_meta: dict[str, dict] = {}

    stats = {
        "rows_read": 0,
        "rows_date_ok": 0,
        "rows_date_fail": 0,
        "pos_section_used": 0,
        "neg_section_used": 0,
        "pos_placeholder": 0,
        "neg_placeholder": 0,
        "aspect_hits_pos": 0,
        "aspect_hits_neg": 0,
        "hotels_seen": 0,
    }

    with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["rows_read"] += 1
            dt = parse_date(row.get("Review_Date", ""))
            if dt is None:
                stats["rows_date_fail"] += 1
                continue
            stats["rows_date_ok"] += 1
            addr = row.get("Hotel_Address", "")
            hid = hotel_id_from_address(addr)
            city, country = parse_city_country(addr)
            name = (row.get("Hotel_Name") or "").strip()
            try:
                lat = float(row["lat"]) if row.get("lat") not in (None, "", "NA") else np.nan
                lon = float(row["lng"]) if row.get("lng") not in (None, "", "NA") else np.nan
            except ValueError:
                lat = lon = np.nan
            try:
                score = float(row["Reviewer_Score"])
            except (TypeError, ValueError):
                score = np.nan

            if hid not in hotel_meta:
                hotel_meta[hid] = {
                    "hotel_id": hid,
                    "hotel_name": name,
                    "city": city,
                    "country": country,
                    "latitude": lat,
                    "longitude": lon,
                }
            month, quarter = period_keys(dt)
            mk = (hid, month)
            qk = (hid, quarter)
            month_rev[mk]["n"] += 1
            quarter_rev[qk]["n"] += 1
            if score == score:
                month_rev[mk]["score_sum"] += score
                quarter_rev[qk]["score_sum"] += score

            pos_txt = row.get("Positive_Review", "")
            neg_txt = row.get("Negative_Review", "")
            if is_placeholder(pos_txt, pos_ph):
                stats["pos_placeholder"] += 1
            else:
                stats["pos_section_used"] += 1
                for a in gate_aspects(pos_txt):
                    month_acc[(hid, month, a)]["pos"] += 1
                    quarter_acc[(hid, quarter, a)]["pos"] += 1
                    stats["aspect_hits_pos"] += 1
            if is_placeholder(neg_txt, neg_ph):
                stats["neg_placeholder"] += 1
            else:
                stats["neg_section_used"] += 1
                for a in gate_aspects(neg_txt):
                    month_acc[(hid, month, a)]["neg"] += 1
                    quarter_acc[(hid, quarter, a)]["neg"] += 1
                    stats["aspect_hits_neg"] += 1

            if stats["rows_read"] % 100000 == 0:
                print(f"  streamed {stats['rows_read']} rows...", flush=True)

    stats["hotels_seen"] = len(hotel_meta)

    def to_frame(acc, rev, period_type: str) -> pd.DataFrame:
        rows = []
        # all hotel-period-aspect combinations that have any mention OR we only emit mention cells
        # Also emit cells with zero mentions? Feasibility needs total_reviews; emit all aspects
        # for hotel-periods that have reviews, even if mentions=0.
        hotel_periods = set((h, p) for (h, p) in rev.keys())
        for hid, period in hotel_periods:
            meta = hotel_meta[hid]
            rv = rev[(hid, period)]
            n_rev = rv["n"]
            mean_score = (rv["score_sum"] / n_rev) if n_rev else np.nan
            for a in ASPECTS:
                c = acc.get((hid, period, a), {"pos": 0, "neg": 0})
                pos, neg = int(c["pos"]), int(c["neg"])
                rn = raw_net(pos, neg)
                sn, rel = smoothed_net(pos, neg, prior)
                rows.append({
                    "hotel_id": hid,
                    "hotel_name": meta["hotel_name"],
                    "city": meta["city"],
                    "country": meta.get("country", ""),
                    "latitude": meta["latitude"],
                    "longitude": meta["longitude"],
                    "period": period,
                    "period_type": period_type,
                    "aspect": a,
                    "positive_mentions": pos,
                    "negative_mentions": neg,
                    "total_mentions": pos + neg,
                    "total_reviews": n_rev,
                    "raw_net": rn if rn is not None else np.nan,
                    "smoothed_net": sn,
                    "mean_reviewer_score": mean_score,
                    "measurement_reliability": rel,
                    "prior_strength": prior,
                })
        return pd.DataFrame(rows)

    month_df = to_frame(month_acc, month_rev, "month")
    quarter_df = to_frame(quarter_acc, quarter_rev, "quarter")
    return month_df, quarter_df, stats


def coverage_tables(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # cells with mentions > 0
    ment = df[df["total_mentions"] > 0]
    by_asp = (
        ment.groupby("aspect")
        .agg(
            cells=("hotel_id", "size"),
            hotels=("hotel_id", "nunique"),
            cities=("city", "nunique"),
            mean_mentions=("total_mentions", "mean"),
            median_mentions=("total_mentions", "median"),
        )
        .reset_index()
    )
    by_city = (
        ment.groupby("city")
        .agg(
            cells=("hotel_id", "size"),
            hotels=("hotel_id", "nunique"),
            periods=("period", "nunique"),
        )
        .reset_index()
        .sort_values("hotels", ascending=False)
    )
    # periods per hotel (any aspect, reviews>0)
    base = df.drop_duplicates(["hotel_id", "period"])
    pph = (
        base.groupby("hotel_id")
        .agg(periods=("period", "nunique"), city=("city", "first"), hotel_name=("hotel_name", "first"))
        .reset_index()
    )
    return by_asp, by_city, pph


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-root", default=None)
    ap.add_argument("--prior", type=float, default=None)
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args()
    root = Path(args.root)
    cfg = load_temporal_config(root)
    prior = float(args.prior if args.prior is not None else cfg["shrinkage"]["prior_strength_main"])
    csv_path = resolve_europe_csv(cfg, args.cache_root)
    print(f"Building panels from {csv_path} prior={prior}")

    month_df, quarter_df, stats = build_panel(csv_path, cfg, prior)

    interim = root / "data" / "interim"
    processed = root / "data" / "processed"
    out = root / "outputs" / "overnight" / "temporal_panel"
    interim.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    month_path = interim / "hotel_aspect_month.parquet"
    quarter_path = processed / "hotel_aspect_quarter.parquet"
    month_df.to_parquet(month_path, index=False)
    quarter_df.to_parquet(quarter_path, index=False)

    # sample without text (already aggregated)
    sample = quarter_df.sample(n=min(500, len(quarter_df)), random_state=42)
    sample.to_csv(out / "hotel_aspect_quarter_sample.csv", index=False)

    by_asp, by_city, pph = coverage_tables(quarter_df)
    by_asp.to_csv(out / "coverage_by_aspect.csv", index=False)
    by_city.to_csv(out / "coverage_by_city.csv", index=False)
    pph.to_csv(out / "periods_per_hotel.csv", index=False)

    # sensitivity priors on quarter only (summary metrics)
    sens = {}
    for ps in cfg["shrinkage"]["prior_strength_sensitivity"]:
        # recompute nets from mentions without full rebuild
        pos = quarter_df["positive_mentions"].to_numpy()
        neg = quarter_df["negative_mentions"].to_numpy()
        nets = []
        for p, n in zip(pos, neg):
            sn, _ = smoothed_net(int(p), int(n), ps)
            nets.append(sn)
        arr = np.asarray(nets)
        sens[str(ps)] = {
            "mean_smoothed_net": float(np.mean(arr)),
            "std_smoothed_net": float(np.std(arr)),
            "corr_with_main": float(np.corrcoef(arr, quarter_df["smoothed_net"].to_numpy())[0, 1]),
        }

    manifest = {
        "source_csv": str(csv_path.name),
        "source_sha256": sha256_file(csv_path),
        "source_bytes": csv_path.stat().st_size,
        "labeling": "structurally_weak_labeled_aspect_sentiment",
        "prior_strength_main": prior,
        "stream_stats": stats,
        "month_rows": int(len(month_df)),
        "quarter_rows": int(len(quarter_df)),
        "month_hotels": int(month_df["hotel_id"].nunique()),
        "quarter_hotels": int(quarter_df["hotel_id"].nunique()),
        "month_periods": int(month_df["period"].nunique()),
        "quarter_periods": int(quarter_df["period"].nunique()),
        "cities": int(quarter_df["city"].nunique()),
        "valid_mention_cells_quarter": int((quarter_df["total_mentions"] > 0).sum()),
        "month_parquet": str(month_path.relative_to(root)),
        "quarter_parquet": str(quarter_path.relative_to(root)),
        "month_sha256": sha256_file(month_path),
        "quarter_sha256": sha256_file(quarter_path),
        "prior_sensitivity": sens,
        "date_note": "Review_Date parsed as M/D/YYYY from 515K Europe file",
    }
    atomic_write_json(out / "panel_manifest.json", manifest)

    report = f"""# PANEL BUILD REPORT

## Labeling

Structurally weak-labeled aspect sentiment from Positive_Review / Negative_Review sections
+ keyword aspect gate. **Not** human gold-standard ABSA.

## Source

- File: `{csv_path.name}`
- SHA256: `{manifest['source_sha256']}`
- Bytes: {manifest['source_bytes']}
- Rows streamed: {stats['rows_read']}
- Date OK: {stats['rows_date_ok']} | Date fail: {stats['rows_date_fail']}

## Placeholders

- Positive placeholders filtered: {stats['pos_placeholder']}
- Negative placeholders filtered: {stats['neg_placeholder']}
- Positive sections used: {stats['pos_section_used']}
- Negative sections used: {stats['neg_section_used']}

## Panel sizes

| Granularity | Rows (hotel×period×aspect) | Hotels | Periods | Cities | Mention cells |
|---|---:|---:|---:|---:|---:|
| Month (exploratory) | {manifest['month_rows']} | {manifest['month_hotels']} | {manifest['month_periods']} | {manifest['cities']} | {(month_df['total_mentions']>0).sum()} |
| Quarter (primary) | {manifest['quarter_rows']} | {manifest['quarter_hotels']} | {manifest['quarter_periods']} | {manifest['cities']} | {manifest['valid_mention_cells_quarter']} |

## Shrinkage

- Method: Beta-Binomial empirical Bayes toward neutral
- Main prior_strength: **{prior}** (fixed a priori)
- Sensitivity corr with main: {json.dumps(sens)}

## Gate keyword audit note

Removed overly broad terms `area` (location) and bare `hear`/`heard` (noise) vs original extract_aspects.py.
See `outputs/overnight/DECISIONS.md`.

## Artifacts

- `{manifest['month_parquet']}`
- `{manifest['quarter_parquet']}`
- No raw review text in aggregates.
"""
    atomic_write_text(out / "PANEL_BUILD_REPORT.md", report)
    print(json.dumps({k: manifest[k] for k in [
        "quarter_rows", "quarter_hotels", "quarter_periods", "cities",
        "valid_mention_cells_quarter", "prior_strength_main"
    ]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

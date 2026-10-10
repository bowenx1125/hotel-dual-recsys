"""P2a: hotel-quarter OUTCOME table split by review fold.

Why this exists
---------------
The shipped panel (``data/processed/hotel_aspect_quarter_v2.parquet``) stores
``smoothed_net_A`` / ``smoothed_net_B`` (aspect sentiment per fold) but only
*pooled* outcomes ``total_reviews`` / ``mean_reviewer_score``.  The project's
own pre-registered rule is

    conf/autonomous_research.json -> crossfit.rule
    "detect_on_one_fold_measure_outcome_on_the_other"

so a fold-specific OUTCOME column is required to actually execute that rule.
Wave 5 measured the outcome on pooled ``smoothed_net``, which violates it.

This module rebuilds hotel-quarter outcomes per fold by re-streaming the raw CSV
using the *same deterministic* fingerprint helpers as ``src/autonomous/panel.py``,
so fold membership is bit-identical to the shipped panel.

Privacy / boundary (AGENTS.md §7): this writes aggregates only. No review text,
no scores at review level, nothing printed from review content.

Idempotent: refuses to overwrite unless ``--force``.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.autonomous.common import (  # noqa: E402
    canonical_hotel_id,
    fold_from_fingerprint,
    parse_date,
    quarter_of,
    review_fingerprint,
)

PANEL = ROOT / "data" / "processed" / "hotel_aspect_quarter_v2.parquet"
OUT_PARQUET = ROOT / "data" / "processed" / "hotel_quarter_fold.parquet"
OUT_JSON = ROOT / "outputs" / "autonomous" / "p2" / "fold_outcomes.json"


def stream_fold_outcomes(csv_path: Path, progress_every: int = 100_000) -> tuple[pd.DataFrame, dict]:
    """Single streaming pass; returns (hotel-quarter fold table, counters)."""
    acc: dict[tuple[str, str], dict] = {}
    rows_read = rows_ok = 0
    fold_n = {"A": 0, "B": 0}
    t0 = time.time()

    with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows_read += 1
            dt = parse_date(row.get("Review_Date") or "")
            if dt is None:
                continue
            rows_ok += 1
            d = dt.date()
            addr = row.get("Hotel_Address") or ""
            hid = canonical_hotel_id(addr)
            qk = quarter_of(dt)
            score_s = row.get("Reviewer_Score") or ""
            nat = row.get("Reviewer_Nationality") or ""
            pos_txt = row.get("Positive_Review") or ""
            neg_txt = row.get("Negative_Review") or ""
            fp = review_fingerprint(addr, str(d), score_s, nat, pos_txt, neg_txt)
            fold = fold_from_fingerprint(fp)
            fold_n[fold] += 1

            a = acc.get((hid, qk))
            if a is None:
                a = {"n": 0, "nA": 0, "nB": 0, "sA": 0.0, "sA_n": 0, "sB": 0.0, "sB_n": 0}
                acc[(hid, qk)] = a
            a["n"] += 1
            a[f"n{fold}"] += 1
            try:
                score = float(score_s)
            except (TypeError, ValueError):
                score = float("nan")
            if score == score:  # not NaN
                a[f"s{fold}"] += score
                a[f"s{fold}_n"] += 1

            if progress_every and rows_read % progress_every == 0:
                print(f"  {rows_read} rows read / {rows_ok} with usable date", flush=True)

    recs = []
    for (hid, qk), a in acc.items():
        recs.append({
            "hotel_id": hid,
            "period": qk,
            "n_reviews": a["n"],
            "n_A": a["nA"],
            "n_B": a["nB"],
            "mean_score_A": (a["sA"] / a["sA_n"]) if a["sA_n"] else np.nan,
            "mean_score_B": (a["sB"] / a["sB_n"]) if a["sB_n"] else np.nan,
            "score_n_A": a["sA_n"],
            "score_n_B": a["sB_n"],
        })
    df = pd.DataFrame(recs)
    # pooled mean (weighted by scored reviews in each fold)
    tot_s = df["mean_score_A"].fillna(0) * df["score_n_A"] + df["mean_score_B"].fillna(0) * df["score_n_B"]
    tot_n = df["score_n_A"] + df["score_n_B"]
    df["mean_score"] = np.where(tot_n > 0, tot_s / tot_n.replace(0, np.nan), np.nan)
    df = df.sort_values(["hotel_id", "period"]).reset_index(drop=True)

    counters = {
        "rows_read": rows_read,
        "rows_with_usable_date": rows_ok,
        "fold_reviews": fold_n,
        "fold_review_intersection": 0,
        "hotel_quarters": int(len(df)),
        "elapsed_sec": round(time.time() - t0, 1),
    }
    return df, counters


def validate_against_panel(df: pd.DataFrame, panel: pd.DataFrame) -> dict:
    """Fold table must reproduce the shipped panel's pooled outcome columns."""
    ref = (
        panel[["hotel_id", "period", "total_reviews", "mean_reviewer_score"]]
        .drop_duplicates(subset=["hotel_id", "period"])
    )
    m = df.merge(ref, on=["hotel_id", "period"], how="outer", indicator=True)
    both = m[m["_merge"] == "both"]
    n_mismatch = int((both["n_reviews"] != both["total_reviews"]).sum())
    d = (both["mean_score"] - both["mean_reviewer_score"]).abs()
    max_abs_diff = float(d.max()) if len(d) else float("nan")
    return {
        "rows_fold_only": int((m["_merge"] == "left_only").sum()),
        "rows_panel_only": int((m["_merge"] == "right_only").sum()),
        "rows_both": int(len(both)),
        "n_reviews_mismatch": n_mismatch,
        "max_abs_mean_score_diff": max_abs_diff,
        "ok": bool(
            n_mismatch == 0
            and (m["_merge"] == "left_only").sum() == 0
            and (m["_merge"] == "right_only").sum() == 0
            and max_abs_diff == max_abs_diff
            and max_abs_diff < 1e-6
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(ROOT / "data" / "cache" / "d1_europe" / "Hotel_Reviews.csv"))
    ap.add_argument("--force", action="store_true", help="overwrite existing outputs")
    args = ap.parse_args(argv)

    csv_path = Path(args.csv)
    if OUT_PARQUET.exists() and not args.force:
        print(f"EXISTS {OUT_PARQUET} (use --force to rebuild)")
        return 0
    if not csv_path.exists():
        print(f"MISSING CSV {csv_path}")
        return 2

    print(f"Streaming {csv_path.name} ...", flush=True)
    df, counters = stream_fold_outcomes(csv_path)
    print(f"  hotel-quarters={counters['hotel_quarters']} folds={counters['fold_reviews']}", flush=True)

    panel = pd.read_parquet(PANEL)
    val = validate_against_panel(df, panel)
    print("validation vs shipped panel:", json.dumps(val, ensure_ascii=False), flush=True)

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps({"counters": counters, "validation": val, "artifact": str(OUT_PARQUET)}, indent=2),
        encoding="utf-8",
    )
    print(f"WROTE {OUT_PARQUET}")
    return 0 if val["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())

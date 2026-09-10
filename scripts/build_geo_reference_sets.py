#!/usr/bin/env python3
"""Build same-city geographic reference sets (not validated competitors)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.temporal.io_util import atomic_write_json, atomic_write_text, load_temporal_config, sha256_file


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def hotel_table(quarter_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(quarter_path, columns=[
        "hotel_id", "hotel_name", "city", "latitude", "longitude"
    ])
    h = (
        df.groupby("hotel_id", as_index=False)
        .agg(
            hotel_name=("hotel_name", "first"),
            city=("city", "first"),
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
        )
    )
    h = h[np.isfinite(h["latitude"]) & np.isfinite(h["longitude"])].copy()
    return h.reset_index(drop=True)


def knn_edges(h: pd.DataFrame, k: int) -> pd.DataFrame:
    rows = []
    for city, g in h.groupby("city"):
        g = g.sort_values("hotel_id").reset_index(drop=True)
        n = len(g)
        if n < 2:
            continue
        lats = g["latitude"].to_numpy()
        lons = g["longitude"].to_numpy()
        ids = g["hotel_id"].tolist()
        names = g["hotel_name"].tolist()
        for i in range(n):
            d = haversine_km(lats[i], lons[i], lats, lons)
            d[i] = np.inf
            # deterministic tie-break: distance then hotel_id
            order = np.lexsort((np.array(ids), d))
            take = order[: min(k, n - 1)]
            for rank, j in enumerate(take, 1):
                rows.append({
                    "city": city,
                    "hotel_id": ids[i],
                    "hotel_name": names[i],
                    "peer_hotel_id": ids[j],
                    "peer_hotel_name": names[j],
                    "distance_km": float(d[j]),
                    "rank": rank,
                    "method": "same_city_knn",
                    "k": k,
                    "radius_km": np.nan,
                })
    return pd.DataFrame(rows)


def mutual_knn(edges: pd.DataFrame) -> pd.DataFrame:
    if edges.empty:
        return edges
    pairs = set(zip(edges["hotel_id"], edges["peer_hotel_id"]))
    keep = [(a, b) in pairs and (b, a) in pairs for a, b in pairs]
    # filter rows where reverse also exists
    mask = [
        (row.peer_hotel_id, row.hotel_id) in pairs
        for row in edges.itertuples(index=False)
    ]
    out = edges.loc[mask].copy()
    out["method"] = "mutual_knn"
    return out


def radius_edges(h: pd.DataFrame, radius_km: float) -> pd.DataFrame:
    rows = []
    for city, g in h.groupby("city"):
        g = g.sort_values("hotel_id").reset_index(drop=True)
        n = len(g)
        if n < 2:
            continue
        lats = g["latitude"].to_numpy()
        lons = g["longitude"].to_numpy()
        ids = g["hotel_id"].tolist()
        names = g["hotel_name"].tolist()
        for i in range(n):
            d = haversine_km(lats[i], lons[i], lats, lons)
            d[i] = np.inf
            order = np.lexsort((np.array(ids), d))
            rank = 0
            for j in order:
                if d[j] > radius_km:
                    break
                rank += 1
                rows.append({
                    "city": city,
                    "hotel_id": ids[i],
                    "hotel_name": names[i],
                    "peer_hotel_id": ids[j],
                    "peer_hotel_name": names[j],
                    "distance_km": float(d[j]),
                    "rank": rank,
                    "method": "radius_km",
                    "k": np.nan,
                    "radius_km": radius_km,
                })
    return pd.DataFrame(rows)


def validate(edges: pd.DataFrame, h: pd.DataFrame) -> dict:
    city_map = dict(zip(h["hotel_id"], h["city"]))
    cross = 0
    self_e = 0
    if not edges.empty:
        for row in edges.itertuples(index=False):
            if row.hotel_id == row.peer_hotel_id:
                self_e += 1
            if city_map.get(row.hotel_id) != city_map.get(row.peer_hotel_id):
                cross += 1
            if row.city != city_map.get(row.hotel_id):
                cross += 1
    return {
        "n_edges": int(len(edges)),
        "self_edges": int(self_e),
        "cross_city_errors": int(cross),
        "n_hotels_with_peers": int(edges["hotel_id"].nunique()) if len(edges) else 0,
        "mean_degree": float(edges.groupby("hotel_id").size().mean()) if len(edges) else 0.0,
        "median_distance_km": float(edges["distance_km"].median()) if len(edges) else None,
        "p90_distance_km": float(edges["distance_km"].quantile(0.9)) if len(edges) else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--quarter-parquet", default=None)
    args = ap.parse_args()
    root = Path(args.root)
    cfg = load_temporal_config(root)
    qpath = Path(args.quarter_parquet) if args.quarter_parquet else root / "data" / "processed" / "hotel_aspect_quarter.parquet"
    out_dir = root / "outputs" / "overnight" / "peer_sets"
    out_dir.mkdir(parents=True, exist_ok=True)

    h = hotel_table(qpath)
    print(f"Hotels with coords: {len(h)} cities={h['city'].nunique()}")

    main_k = int(cfg["peers"]["main"]["k"])
    main_edges = knn_edges(h, main_k)
    sens = {
        "knn5": knn_edges(h, 5),
        "knn10": main_edges,
        "knn20": knn_edges(h, 20),
        "mutual10": mutual_knn(main_edges),
        "radius_1_5": radius_edges(h, 1.5),
    }

    # commit main k=10 as processed artifact
    out_parquet = root / "data" / "processed" / "geo_reference_sets.parquet"
    main_edges.to_parquet(out_parquet, index=False)

    # distance distribution for main
    dist_hist = (
        main_edges.assign(bin=pd.cut(main_edges["distance_km"], bins=[0, 0.5, 1, 2, 5, 10, 50, 500]))
        .groupby("bin", observed=False)
        .size()
        .reset_index(name="n_edges")
    )
    dist_hist["bin"] = dist_hist["bin"].astype(str)
    dist_hist.to_csv(out_dir / "distance_distribution.csv", index=False)

    metrics = {name: validate(df, h) for name, df in sens.items()}
    # stability: top-1 peer overlap knn5 vs knn10
    def top1(df):
        return df[df["rank"] == 1].set_index("hotel_id")["peer_hotel_id"]

    t5, t10 = top1(sens["knn5"]), top1(sens["knn10"])
    common = t5.index.intersection(t10.index)
    stability = float((t5.loc[common] == t10.loc[common]).mean()) if len(common) else 0.0

    assert metrics["knn10"]["self_edges"] == 0
    assert metrics["knn10"]["cross_city_errors"] == 0

    manifest = {
        "terminology": "geo_reference_set / candidate peer set",
        "not": ["validated competitors", "economic substitutes"],
        "construction": "same city, Haversine nearest-k, exclude self, deterministic tie-break by hotel_id",
        "main_k": main_k,
        "n_cities": int(h["city"].nunique()),
        "n_hotels": int(len(h)),
        "metrics": metrics,
        "top1_stability_knn5_vs_knn10": stability,
        "artifact": str(out_parquet.relative_to(root)),
        "sha256": sha256_file(out_parquet),
    }
    atomic_write_json(out_dir / "peer_set_manifest.json", manifest)
    report = f"""# PEER SET REPORT

## Terminology

These are **geo reference sets / candidate peer sets**.
They are **not** validated competitors or economic substitutes.

## Construction (main)

- Same city only
- Nearest **k={main_k}** by Haversine
- Exclude self
- Deterministic tie-break: distance then `hotel_id`

## Scale

- Cities: **{manifest['n_cities']}**
- Hotels with coords: **{manifest['n_hotels']}**
- Main edges: **{metrics['knn10']['n_edges']}**
- Self-edges: **{metrics['knn10']['self_edges']}** (must be 0)
- Cross-city errors: **{metrics['knn10']['cross_city_errors']}** (must be 0)
- Median distance km: **{metrics['knn10']['median_distance_km']}**
- P90 distance km: **{metrics['knn10']['p90_distance_km']}**
- Top-1 stability knn5 vs knn10: **{stability:.3f}**

## Sensitivity metrics

```json
{json.dumps(metrics, indent=2)}
```

## Limitation

Geographic proximity ≠ verified competitive substitution. Do not use within-set share summing to 1 as evidence of competition.
"""
    atomic_write_text(out_dir / "PEER_SET_REPORT.md", report)
    print(json.dumps({"n_hotels": manifest["n_hotels"], "n_cities": manifest["n_cities"],
                      "edges": metrics["knn10"]["n_edges"], "median_km": metrics["knn10"]["median_distance_km"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

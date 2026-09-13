"""Build a Demo-compatible snapshot from a quarterly hotel-aspect panel and geo peer edges."""
from __future__ import annotations

import copy
import math
import re
from collections import Counter, defaultdict
from typing import Any

import numpy as np
import pandas as pd

ASPECTS_DEFAULT = [
    "location", "cleanliness", "breakfast", "service", "noise", "room", "value",
]

PANEL_REQUIRED = [
    "hotel_id", "hotel_name", "city", "country", "latitude", "longitude",
    "period", "period_complete", "aspect",
    "positive_mentions", "negative_mentions", "total_mentions", "has_measurement",
    "raw_net", "smoothed_net", "measurement_reliability",
    "total_reviews", "mean_reviewer_score", "prior_strength",
]

PEERS_REQUIRED = ["hotel_id", "city", "rank", "distance_km"]

TEXT_COLUMNS = {
    "Positive_Review", "Negative_Review", "review_text", "raw_review_text",
    "Review_Text", "text", "review",
}

SCHEMA_VERSION = "research-panel-2026-09-14"
PERIOD_LABEL_RE = re.compile(r"^\d{4}Q[1-4]$")


def period_sort_key(period: str) -> tuple[int, int]:
    validate_period_label(str(period))
    year, quarter = str(period).split("Q")
    return int(year), int(quarter)


def validate_period_label(period: str) -> None:
    label = str(period)
    if not PERIOD_LABEL_RE.fullmatch(label):
        raise ValueError(f"invalid period label {label!r}; expected YYYYQ1..Q4")


def is_finite(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def fnum(value: Any) -> float | None:
    if not is_finite(value):
        return None
    return float(value)


def median(values: list[float]) -> float | None:
    finite = sorted(v for v in values if is_finite(v))
    if not finite:
        return None
    mid = len(finite) // 2
    if len(finite) % 2:
        return finite[mid]
    return 0.5 * (finite[mid - 1] + finite[mid])


def percentile_rank(value: float, values: list[float]) -> float | None:
    finite = [v for v in values if is_finite(v)]
    if not finite or not is_finite(value):
        return None
    below = sum(1 for v in finite if v < value)
    equal = sum(1 for v in finite if v == value)
    return 100.0 * (below + 0.5 * equal) / len(finite)


def _as_bool(value: Any, *, field: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if pd.isna(value):
        raise ValueError(f"{field} must be boolean, got missing value")
    if value in (0, 1):
        return bool(value)
    raise ValueError(f"{field} must be boolean, got {value!r}")


def _as_nonneg_int(value: Any, *, field: str) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{field} must be a non-negative integer, got bool")
    if pd.isna(value):
        raise ValueError(f"{field} must be a non-negative integer, got missing value")
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a non-negative integer, got {value!r}") from None
    if not math.isfinite(num):
        raise ValueError(f"{field} must be a non-negative integer, got non-finite value")
    if num != int(num):
        raise ValueError(f"{field} must be a non-negative integer, got fractional value {value!r}")
    iv = int(num)
    if iv < 0:
        raise ValueError(f"{field} must be a non-negative integer, got negative value {iv}")
    return iv


def _finite_in_range(value: Any, *, field: str, low: float, high: float) -> float:
    if not is_finite(value):
        raise ValueError(f"{field} must be finite")
    num = float(value)
    if num < low or num > high:
        raise ValueError(f"{field} must be within [{low}, {high}]")
    return num


def _coord_or_none(value: Any) -> float | None:
    if not is_finite(value):
        return None
    num = float(value)
    return num


def _coords_valid(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def _validate_no_text_columns(df: pd.DataFrame, name: str) -> None:
    bad = TEXT_COLUMNS.intersection(df.columns)
    if bad:
        raise ValueError(f"{name} contains forbidden text columns: {sorted(bad)}")


def _require_nonempty_str_id(value: Any, *, field: str, context: str = "") -> str:
    suffix = f" ({context})" if context else ""
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{field} must be a non-empty string, got bool{suffix}")
    if pd.isna(value):
        raise ValueError(f"{field} must be a non-empty string, got missing value{suffix}")
    if isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError(f"{field} must be a non-empty string, got numeric {value!r}{suffix}")
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a non-empty string, got {type(value).__name__}{suffix}")
    if not value:
        raise ValueError(f"{field} must be a non-empty string, got empty string{suffix}")
    return value


def _require_nonempty_str_text(value: Any, *, field: str, context: str = "") -> str:
    suffix = f" ({context})" if context else ""
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{field} must be a non-empty string, got bool{suffix}")
    if pd.isna(value):
        raise ValueError(f"{field} must be a non-empty string, got missing value{suffix}")
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a non-empty string, got {type(value).__name__}{suffix}")
    if not value:
        raise ValueError(f"{field} must be a non-empty string, got empty string{suffix}")
    return value


def _validate_id_column(values: pd.Series, *, field: str, frame: str) -> None:
    seen: dict[str, str] = {}
    for idx, raw in values.items():
        context = f"{frame} row {idx}"
        canonical = _require_nonempty_str_id(raw, field=field, context=context)
        prior = seen.get(canonical)
        if prior is not None and prior != raw:
            raise ValueError(
                f"{frame} {field} numeric/string collision: {prior!r} and {raw!r} both map to {canonical!r}"
            )
        seen.setdefault(canonical, raw)


def _normalize_actionability(value: dict) -> dict:
    if "aspects" in value and isinstance(value["aspects"], dict):
        return value["aspects"]
    return value


def _freeze_cfg(cfg: dict, actionability: dict | None = None) -> dict:
    frozen = copy.deepcopy(cfg)
    if "actionability" in frozen:
        return frozen
    if actionability is not None:
        frozen["actionability"] = copy.deepcopy(_normalize_actionability(actionability))
    return frozen


def _peer_id_column(peers: pd.DataFrame) -> str:
    if "peer_hotel_id" in peers.columns:
        return "peer_hotel_id"
    if "peer_id" in peers.columns:
        return "peer_id"
    raise ValueError("peers missing peer_hotel_id/peer_id column")


def _hotel_city_map(panel: pd.DataFrame) -> dict[str, str]:
    cities: dict[str, str] = {}
    for hid, grp in panel.groupby("hotel_id", sort=False):
        hotel_id = _require_nonempty_str_id(hid, field="hotel_id")
        city_values = sorted({str(v) for v in grp["city"].astype(str)})
        if len(city_values) != 1:
            raise ValueError(f"inconsistent city for hotel_id={hotel_id}")
        cities[hotel_id] = city_values[0]
    return cities


def validate_panel(panel: pd.DataFrame, aspects: list[str]) -> None:
    missing = [c for c in PANEL_REQUIRED if c not in panel.columns]
    if missing:
        raise ValueError(f"panel missing columns: {missing}")
    _validate_no_text_columns(panel, "panel")
    if panel.empty:
        raise ValueError("panel is empty")

    _validate_id_column(panel["hotel_id"], field="hotel_id", frame="panel")
    for idx, row in panel.iterrows():
        context = f"panel row {idx}"
        _require_nonempty_str_text(row["hotel_name"], field="hotel_name", context=context)
        _require_nonempty_str_text(row["city"], field="city", context=context)

    aspect_set = set(aspects)
    unknown = sorted(set(panel["aspect"].astype(str)) - aspect_set)
    if unknown:
        raise ValueError(f"panel contains unknown aspects: {unknown}")

    for period in panel["period"].astype(str).unique():
        validate_period_label(period)

    dup = panel.duplicated(subset=["hotel_id", "aspect", "period"], keep=False)
    if dup.any():
        n = int(dup.sum())
        raise ValueError(f"panel has {n} duplicate hotel/aspect/period rows")

    count_cols = ("positive_mentions", "negative_mentions", "total_mentions", "total_reviews")
    numeric_counts = {}
    for col in count_cols:
        vals = pd.to_numeric(panel[col], errors="coerce")
        if vals.isna().any():
            raise ValueError(f"panel has non-numeric {col}")
        for raw in panel[col]:
            numeric_counts.setdefault(col, []).append(_as_nonneg_int(raw, field=col))

    pos = numeric_counts["positive_mentions"]
    neg = numeric_counts["negative_mentions"]
    tot = numeric_counts["total_mentions"]
    for i, (p, n, t) in enumerate(zip(pos, neg, tot)):
        if p + n != t:
            row = panel.iloc[i]
            raise ValueError(
                "panel row total_mentions != positive_mentions + negative_mentions for "
                f"{row['hotel_id']}/{row['aspect']}/{row['period']}"
            )

    for _, grp in panel.groupby(["hotel_id", "period"]):
        meta_cols = ["hotel_name", "city", "country", "latitude", "longitude", "total_reviews", "period_complete"]
        for col in meta_cols:
            if grp[col].nunique(dropna=False) > 1:
                hid = grp["hotel_id"].iloc[0]
                per = grp["period"].iloc[0]
                raise ValueError(f"inconsistent {col} for hotel_id={hid} period={per}")

        flags = {_as_bool(v, field="period_complete") for v in grp["period_complete"]}
        if len(flags) != 1:
            hid = str(grp["hotel_id"].iloc[0])
            per = str(grp["period"].iloc[0])
            raise ValueError(f"period_complete inconsistent within hotel_id={hid} period={per}")

        for _, row in grp.iterrows():
            has_measurement = _as_bool(row["has_measurement"], field="has_measurement")
            mention_count = _as_nonneg_int(row["total_mentions"], field="total_mentions")
            if has_measurement and mention_count <= 0:
                raise ValueError(
                    f"has_measurement=true but total_mentions=0 for "
                    f"{row['hotel_id']}/{row['aspect']}/{row['period']}"
                )
            if not has_measurement and mention_count > 0:
                raise ValueError(
                    f"has_measurement=false but total_mentions>0 for "
                    f"{row['hotel_id']}/{row['aspect']}/{row['period']}"
                )
            if has_measurement:
                _finite_in_range(row["smoothed_net"], field="smoothed_net", low=-1.0, high=1.0)
                _finite_in_range(
                    row["measurement_reliability"],
                    field="measurement_reliability",
                    low=0.0,
                    high=1.0,
                )


def validate_peers(peers: pd.DataFrame, *, hotel_cities: dict[str, str]) -> str:
    missing = [c for c in PEERS_REQUIRED if c not in peers.columns]
    if missing:
        raise ValueError(f"peers missing columns: {missing}")
    _validate_no_text_columns(peers, "peers")
    peer_col = _peer_id_column(peers)
    if peers.empty:
        return peer_col
    _validate_id_column(peers["hotel_id"], field="hotel_id", frame="peers")
    _validate_id_column(peers[peer_col], field=peer_col, frame="peers")
    if (peers["hotel_id"] == peers[peer_col]).any():
        raise ValueError("peers contain self edges")
    dup = peers.duplicated(subset=["hotel_id", peer_col], keep=False)
    if dup.any():
        raise ValueError(f"peers contain {int(dup.sum())} duplicate hotel/peer edges")

    for row in peers.itertuples(index=False):
        hid = _require_nonempty_str_id(row.hotel_id, field="hotel_id")
        pid = _require_nonempty_str_id(getattr(row, peer_col), field=peer_col)
        edge_city = _require_nonempty_str_text(row.city, field="city")
        if hid in hotel_cities and hotel_cities[hid] != edge_city:
            raise ValueError(
                f"peer edge city mismatch for hotel_id={hid}: edge={edge_city!r} panel={hotel_cities[hid]!r}"
            )
        if pid in hotel_cities and hotel_cities[pid] != edge_city:
            raise ValueError(
                f"peer edge city mismatch for peer_hotel_id={pid}: edge={edge_city!r} panel={hotel_cities[pid]!r}"
            )
    return peer_col


def complete_periods(panel: pd.DataFrame) -> list[str]:
    out: list[str] = []
    for period, grp in panel.groupby("period"):
        validate_period_label(str(period))
        flags = {_as_bool(v, field="period_complete") for v in grp["period_complete"]}
        if len(flags) != 1:
            raise ValueError(f"period_complete inconsistent across hotels for period={period!r}")
        if next(iter(flags)):
            out.append(str(period))
    return sorted(out, key=period_sort_key)


def resolve_period(panel: pd.DataFrame, period: str | None) -> str:
    available = complete_periods(panel)
    if not available:
        raise ValueError("panel has no complete quarters")
    if period is None:
        return available[-1]
    validate_period_label(period)
    if period not in set(panel["period"].astype(str)):
        raise ValueError(f"requested period {period!r} not found in panel")
    flags = {_as_bool(v, field="period_complete") for v in panel.loc[panel["period"] == period, "period_complete"]}
    if len(flags) != 1 or not next(iter(flags)):
        raise ValueError(f"requested period {period!r} is not complete")
    return period


def _peer_lists(
    peers: pd.DataFrame,
    peer_col: str,
    hotels_in_period: set[str],
) -> tuple[dict[str, list[str]], int]:
    out: dict[str, list[str]] = defaultdict(list)
    removed_absent_period = 0
    if peers.empty:
        return out, removed_absent_period
    sub = peers[peers["hotel_id"].isin(hotels_in_period)].copy()
    sub = sub.sort_values(["hotel_id", "rank", peer_col])
    seen: set[tuple[str, str]] = set()
    for row in sub.itertuples(index=False):
        hid = _require_nonempty_str_id(row.hotel_id, field="hotel_id")
        pid = _require_nonempty_str_id(getattr(row, peer_col), field=peer_col)
        if pid == hid:
            continue
        key = (hid, pid)
        if key in seen:
            continue
        if pid not in hotels_in_period:
            removed_absent_period += 1
            continue
        seen.add(key)
        out[hid].append(pid)
    return out, removed_absent_period


def _weakest_aspect(
    hotel: dict,
    aspects: list[str],
    *,
    min_mentions: int,
    min_reliability: float,
) -> str | None:
    candidates: list[tuple[float, str]] = []
    for aspect in aspects:
        rec = hotel["aspects"][aspect]
        if not rec.get("has_measurement"):
            continue
        net = rec.get("net")
        if not is_finite(net):
            continue
        if int(rec.get("mention_count") or 0) < min_mentions:
            continue
        rel = rec.get("reliability")
        if rel is None or float(rel) < min_reliability:
            continue
        candidates.append((float(net), aspect))
    if not candidates:
        return None
    best = min(score for score, _ in candidates)
    names = sorted(name for score, name in candidates if score == best)
    return names[0]


def _sanitize_hotel_numbers(hotel: dict) -> None:
    for rec in hotel["aspects"].values():
        for key, value in list(rec.items()):
            if isinstance(value, float) and not math.isfinite(value):
                rec[key] = None


def _resolve_synthetic(meta: dict) -> bool | None:
    if "synthetic" not in meta:
        return None
    value = meta["synthetic"]
    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    raise ValueError("source_metadata['synthetic'] must be a boolean or null")


def build_panel_snapshot(
    panel: pd.DataFrame,
    peers: pd.DataFrame,
    cfg: dict,
    *,
    period: str | None = None,
    source_metadata: dict | None = None,
    actionability: dict | None = None,
) -> dict:
    """Pure builder: panel + geo peer edges -> Demo-compatible snapshot dict (no raw text)."""
    frozen_cfg = _freeze_cfg(cfg, actionability)

    aspects = list(frozen_cfg.get("aspects") or ASPECTS_DEFAULT)
    min_mentions = int(frozen_cfg.get("min_mentions", 5))
    min_reviews = int(frozen_cfg.get("min_reviews_hotel", 10))
    min_reliability = float(frozen_cfg.get("min_reliability", 0.3))

    validate_panel(panel, aspects)
    hotel_cities = _hotel_city_map(panel)
    peer_col = validate_peers(peers, hotel_cities=hotel_cities)
    selected = resolve_period(panel, period)

    all_hotel_ids = sorted(
        {_require_nonempty_str_id(h, field="hotel_id") for h in panel["hotel_id"].unique()}
    )
    sub = panel[panel["period"].astype(str) == selected].copy()
    hotels_in_period = {
        _require_nonempty_str_id(h, field="hotel_id") for h in sub["hotel_id"].unique()
    }
    absent_selected_period = sorted(set(all_hotel_ids) - hotels_in_period)

    peer_map, peers_removed_absent_period = _peer_lists(peers, peer_col, hotels_in_period)

    hotel_rows: dict[str, dict] = {}
    for hid, grp in sub.groupby("hotel_id", sort=False):
        hid = _require_nonempty_str_id(hid, field="hotel_id")
        first = grp.iloc[0]
        lat = _coord_or_none(first["latitude"])
        lon = _coord_or_none(first["longitude"])
        has_coords = _coords_valid(lat, lon)
        city = _require_nonempty_str_text(first["city"], field="city")
        compset_id = f"geo:{city}"
        aspect_records: dict[str, dict] = {}

        for aspect in aspects:
            row = grp[grp["aspect"] == aspect]
            if row.empty:
                aspect_records[aspect] = {
                    "net": None,
                    "mention_rate": None,
                    "mention_count": None,
                    "pos_mentions": None,
                    "neg_mentions": None,
                    "neu_mentions": None,
                    "neg_rate": None,
                    "has_measurement": False,
                    "reliability": None,
                    "peer_median_net": None,
                    "peer_n": 0,
                    "gap": None,
                    "percentile": None,
                    "peer_weakest_share": None,
                }
                continue

            rec_row = row.iloc[0]
            has_measurement = _as_bool(rec_row["has_measurement"], field="has_measurement")
            pos = _as_nonneg_int(rec_row["positive_mentions"], field="positive_mentions")
            neg = _as_nonneg_int(rec_row["negative_mentions"], field="negative_mentions")
            mention_count = _as_nonneg_int(rec_row["total_mentions"], field="total_mentions")
            n_reviews = _as_nonneg_int(rec_row["total_reviews"], field="total_reviews")

            if has_measurement and mention_count > 0:
                net = _finite_in_range(rec_row["smoothed_net"], field="smoothed_net", low=-1.0, high=1.0)
                reliability = _finite_in_range(
                    rec_row["measurement_reliability"],
                    field="measurement_reliability",
                    low=0.0,
                    high=1.0,
                )
                mention_rate = mention_count / n_reviews if n_reviews > 0 else None
                neg_rate = neg / mention_count
                neu = 0
            else:
                net = None
                reliability = None
                mention_rate = None
                neg_rate = None
                neu = None
                has_measurement = False

            aspect_records[aspect] = {
                "net": net,
                "mention_rate": mention_rate,
                "mention_count": mention_count if has_measurement else None,
                "pos_mentions": pos if has_measurement else None,
                "neg_mentions": neg if has_measurement else None,
                "neu_mentions": neu,
                "neg_rate": neg_rate,
                "has_measurement": has_measurement,
                "reliability": reliability,
                "peer_median_net": None,
                "peer_n": 0,
                "gap": None,
                "percentile": None,
                "peer_weakest_share": None,
            }

        hotel_rows[hid] = {
            "hotel_id": hid,
            "hotel_name": _require_nonempty_str_text(first["hotel_name"], field="hotel_name"),
            "city": city,
            "compset_id": compset_id,
            "compset_valid": has_coords,
            "price_tier": None,
            "lat": lat if has_coords else None,
            "lon": lon if has_coords else None,
            "n_reviews": _as_nonneg_int(first["total_reviews"], field="total_reviews"),
            "n_negative": None,
            "peer_ids": list(peer_map.get(hid, [])),
            "peer_count": len(peer_map.get(hid, [])),
            "compset_size": len(peer_map.get(hid, [])) + 1,
            "aspects": aspect_records,
            "eligible": False,
            "ineligible_reason": "",
        }

    hotels = list(hotel_rows.values())
    hotels_by_id = {h["hotel_id"]: h for h in hotels}

    def peer_aspect_net(peer_id: str, aspect: str) -> float | None:
        rec = hotels_by_id[peer_id]["aspects"][aspect]
        if not rec.get("has_measurement"):
            return None
        net = rec.get("net")
        if not is_finite(net):
            return None
        if int(rec.get("mention_count") or 0) < min_mentions:
            return None
        rel = rec.get("reliability")
        if rel is None or float(rel) < min_reliability:
            return None
        return float(net)

    weakest_map = {
        h["hotel_id"]: _weakest_aspect(h, aspects, min_mentions=min_mentions, min_reliability=min_reliability)
        for h in hotels
    }

    for hotel in hotels:
        peer_ids = hotel["peer_ids"]
        for aspect in aspects:
            rec = hotel["aspects"][aspect]
            peer_nets = [n for pid in peer_ids if (n := peer_aspect_net(pid, aspect)) is not None]
            med = median(peer_nets)
            rec["peer_median_net"] = med
            rec["peer_n"] = len(peer_nets)
            own_net = rec.get("net")
            if med is not None and is_finite(own_net):
                rec["gap"] = med - float(own_net)
            comparable = peer_nets + ([float(own_net)] if is_finite(own_net) else [])
            rec["percentile"] = (
                percentile_rank(float(own_net), comparable) if is_finite(own_net) else None
            )

            measured_peers = [pid for pid in peer_ids if weakest_map.get(pid) is not None]
            if measured_peers:
                denom = len(measured_peers)
                share = sum(1 for pid in measured_peers if weakest_map[pid] == aspect) / denom
                rec["peer_weakest_share"] = share
            else:
                rec["peer_weakest_share"] = None

        _sanitize_hotel_numbers(hotel)

    exclusion_counts: Counter[str] = Counter()
    eligible_hotels: list[dict] = []
    for hotel in hotels:
        if not hotel["compset_valid"]:
            hotel["eligible"] = False
            hotel["ineligible_reason"] = "missing_coordinates"
            exclusion_counts["missing_coordinates"] += 1
            continue
        if hotel["n_reviews"] < min_reviews:
            hotel["eligible"] = False
            hotel["ineligible_reason"] = f"n_reviews<{min_reviews}"
            exclusion_counts[f"n_reviews<{min_reviews}"] += 1
            continue
        if hotel["peer_count"] < 2:
            hotel["eligible"] = False
            hotel["ineligible_reason"] = "peer_count<2"
            exclusion_counts["peer_count<2"] += 1
            continue
        measured_aspects = [
            a for a in aspects
            if hotel["aspects"][a].get("has_measurement") and is_finite(hotel["aspects"][a].get("net"))
        ]
        if not measured_aspects:
            hotel["eligible"] = False
            hotel["ineligible_reason"] = "no_measured_aspects"
            exclusion_counts["no_measured_aspects"] += 1
            continue
        hotel["eligible"] = True
        hotel["ineligible_reason"] = ""
        eligible_hotels.append(hotel)

    meta = dict(source_metadata or {})
    synthetic = _resolve_synthetic(meta)
    dataset_id = str(meta.get("dataset_id") or frozen_cfg.get("dataset_id") or "d1_europe")
    scoring_version = str(
        meta.get("scoring_version")
        or frozen_cfg.get("policy_version")
        or "panel_adapter_v1"
    )

    sources = {
        "panel_parquet": meta.get("panel_path"),
        "peers_parquet": meta.get("peers_path"),
        "demo_config": meta.get("config_path"),
        "actionability_path": meta.get("actionability_path"),
    }
    source_hashes = {
        k: v for k, v in {
            "panel_parquet": meta.get("panel_sha256"),
            "peers_parquet": meta.get("peers_sha256"),
            "demo_config": meta.get("config_sha256"),
            "actionability_sha256": meta.get("actionability_sha256"),
        }.items()
        if v
    }

    thresholds = {
        "min_mentions": min_mentions,
        "min_reviews_hotel": min_reviews,
        "min_reliability": min_reliability,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "period": selected,
        "dataset_id": dataset_id,
        "synthetic": synthetic,
        "aspects": aspects,
        "config": frozen_cfg,
        "scoring_version": scoring_version,
        "thresholds": thresholds,
        "sources": sources,
        "source_file_hashes": source_hashes,
        "n_hotels_source_panel": len(all_hotel_ids),
        "n_hotels_total": len(hotels),
        "n_hotels_in_aspect_table": len(hotels),
        "n_hotels_in_selected_period": len(hotels),
        "absent_selected_period_count": len(absent_selected_period),
        "absent_selected_period_hotel_ids": absent_selected_period,
        "n_eligible_hotels": len(eligible_hotels),
        "n_excluded_hotels": len(hotels) - len(eligible_hotels),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "peers_removed_absent_period": peers_removed_absent_period,
        "n_compsets": len({h["compset_id"] for h in eligible_hotels}),
        "hotels": hotels,
        "causal_checks": {},
        "predictive_holdout_metrics": None,
        "notes": [
            "Peer sets are same-city kNN geographic reference sets, not validated economic competitors.",
            "Aspect net uses smoothed_net from the quarterly panel (Bayesian shrinkage), not legacy demo raw (pos-neg)/mentions.",
            "has_measurement=false or zero mentions -> net/rates are null; prior-only cells are not treated as neutral zero.",
            "measurement_reliability reflects mention volume vs prior strength, not labeling accuracy.",
            "peer_median_net/gap use peers with has_measurement, finite net, mention_count>="
            f"{min_mentions}, reliability>={min_reliability}; absent-period peers are excluded.",
            f"peers_removed_absent_period={peers_removed_absent_period} peer edges dropped because peer hotel has no rows in selected period.",
            "peer_weakest_share denominator = measured peers with at least one eligible aspect; scenario diagnostic only, not causal.",
            "Review counts are not bookings.",
            "n_hotels_source_panel counts unique hotels across all panel periods; absent_selected_period_hotel_ids have no rows in the selected quarter.",
        ],
    }

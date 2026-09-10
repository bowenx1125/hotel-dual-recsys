"""Shared primitives for the autonomous research pipeline."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ASPECTS = ["location", "cleanliness", "breakfast", "service", "noise", "room", "value"]
ACTIONABLE = ["cleanliness", "breakfast", "service", "noise", "room", "value"]
KNOWN_CITIES = ["London", "Paris", "Amsterdam", "Barcelona", "Vienna", "Milan"]
DATASET_CODE = "d1_europe"
SEED = 42

TEXT_COLUMNS = {
    "Positive_Review", "Negative_Review", "review_text", "raw_review_text",
    "Review_Text", "text", "review",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_config(root: Path | None = None) -> dict:
    root = root or repo_root()
    return json.loads((root / "conf" / "autonomous_research.json").read_text(encoding="utf-8"))


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path: Path, obj: Any) -> None:
    atomic_write_text(path, json.dumps(obj, indent=2, ensure_ascii=False, default=_json_default) + "\n")


def _json_default(o: Any) -> Any:
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        v = float(o)
        return None if np.isnan(v) else v
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=_json_default).encode("utf-8")
    return sha256_bytes(blob)


def canonical_hotel_id(address: str) -> str:
    raw = (address or "").strip().lower()
    return f"{DATASET_CODE}:{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


def legacy_hotel_id(address: str) -> str:
    raw = (address or "").strip().lower()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def parse_city_country(address: str) -> tuple[str, str]:
    from src.temporal.geo_parse import parse_city_country as _p
    return _p(address)


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


def quarter_of(dt: datetime | date) -> str:
    return f"{dt.year:04d}Q{(dt.month - 1) // 3 + 1}"


def quarter_bounds(period: str) -> tuple[date, date]:
    y, q = period.split("Q")
    y, q = int(y), int(q)
    start_m = 3 * (q - 1) + 1
    start = date(y, start_m, 1)
    if q == 4:
        end = date(y, 12, 31)
    else:
        nxt = date(y, start_m + 3, 1)
        end = date.fromordinal(nxt.toordinal() - 1)
    return start, end


def period_sort_key(p: str) -> tuple[int, int]:
    y, q = p.split("Q")
    return (int(y), int(q))


def classify_period_completeness(data_min: date, data_max: date, period: str) -> str:
    start, end = quarter_bounds(period)
    if data_min <= start and data_max >= end:
        return "complete"
    return "partial"


def review_fingerprint(addr: str, date_s: str, score: str, nat: str, pos: str, neg: str) -> str:
    h = hashlib.sha1()
    h.update(f"{addr}|{date_s}|{score}|{nat}|".encode("utf-8", errors="replace"))
    h.update(hashlib.sha1((pos or "").encode("utf-8", errors="replace")).digest())
    h.update(hashlib.sha1((neg or "").encode("utf-8", errors="replace")).digest())
    return h.hexdigest()


def fold_from_fingerprint(fp: str) -> str:
    return "A" if int(fp[:8], 16) % 2 == 0 else "B"


def smoothed_net(pos: int, neg: int, prior_strength: float) -> tuple[float, float]:
    """Symmetric Beta-Binomial Bayesian shrinkage toward 0.5. Not empirical Bayes."""
    ps = float(prior_strength)
    tot = pos + neg
    p = (pos + 0.5 * ps) / (tot + ps) if (tot + ps) > 0 else 0.5
    net = 2.0 * p - 1.0
    rel = tot / (tot + ps) if (tot + ps) > 0 else 0.0
    return float(net), float(rel)


def raw_net(pos: int, neg: int) -> float:
    tot = pos + neg
    if tot <= 0:
        return float("nan")
    return (pos - neg) / tot


def p_delta_gt0(
    pos_t: np.ndarray,
    neg_t: np.ndarray,
    pos_0: np.ndarray,
    neg_0: np.ndarray,
    prior: float,
    draws: int = 2000,
    seed: int = 42,
) -> np.ndarray:
    """Monte Carlo P(p_t > p_{t-1}) under independent symmetric Beta posteriors."""
    a = prior / 2.0
    rng = np.random.default_rng(seed)
    n = len(pos_t)
    out = np.empty(n, dtype=np.float64)
    # batched for memory
    bs = 4096
    for i in range(0, n, bs):
        sl = slice(i, min(i + bs, n))
        k = sl.stop - sl.start
        p1 = rng.beta(pos_t[sl] + a, neg_t[sl] + a, size=(draws, k))
        p0 = rng.beta(pos_0[sl] + a, neg_0[sl] + a, size=(draws, k))
        out[sl] = (p1 > p0).mean(axis=0)
    return out


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def resolve_europe_csv(cfg: dict, cache_root: str | None = None) -> Path:
    cache = Path(cache_root or os.environ.get("FYP_DATA_CACHE_ROOT") or "")
    if not str(cache):
        raise FileNotFoundError("Set FYP_DATA_CACHE_ROOT")
    path = cache / cfg["dataset"]["relative_path"]
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    return path


def validate_no_text_columns(df: pd.DataFrame, name: str) -> None:
    bad = TEXT_COLUMNS.intersection(set(df.columns))
    if bad:
        raise ValueError(f"{name} contains forbidden text columns: {bad}")


def schema_validate(df: pd.DataFrame, name: str, required: list[str]) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing columns: {missing}")
    validate_no_text_columns(df, name)


def write_parquet(df: pd.DataFrame, path: Path, name: str, required: list[str]) -> None:
    schema_validate(df, name, required)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def out_dir(root: Path) -> Path:
    rel = os.environ.get("FYP_AUTONOMOUS_OUT", "outputs/autonomous")
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    return d


def panel_v2_path(root: Path) -> Path:
    rel = os.environ.get("FYP_PANEL_V2", "data/processed/hotel_aspect_quarter_v2.parquet")
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def peers_v2_path(root: Path) -> Path:
    rel = os.environ.get("FYP_PEERS_V2", "data/processed/geo_reference_sets_v2.parquet")
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def paper_dir(root: Path) -> Path:
    rel = os.environ.get("FYP_PAPER_DIR", "paper/autonomous")
    p = root / rel
    p.mkdir(parents=True, exist_ok=True)
    return p


def finals_dir(root: Path) -> Path:
    rel = os.environ.get("FYP_FINALS_DIR")
    return (root / rel) if rel else root


def update_state(root: Path, **kwargs: Any) -> dict:
    path = out_dir(root) / "STATE.json"
    if path.exists():
        st = json.loads(path.read_text(encoding="utf-8"))
    else:
        st = {
            "schema_version": "2.0",
            "wave": 0,
            "status": "INIT",
            "iterations": {},
            "blockers": [],
            "facts_sha256": "",
        }
    st.update(kwargs)
    st["updated_at"] = datetime.now().isoformat(timespec="seconds")
    atomic_write_json(path, st)
    return st


def append_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prev = path.read_text(encoding="utf-8") if path.exists() else ""
    atomic_write_text(path, prev + text)


def cohen_kappa(y_true: np.ndarray, y_pred: np.ndarray, labels: list[str]) -> float:
    """Cohen's kappa for categorical labels."""
    idx = {l: i for i, l in enumerate(labels)}
    k = len(labels)
    cm = np.zeros((k, k), dtype=np.float64)
    for a, b in zip(y_true, y_pred):
        if a not in idx or b not in idx:
            continue
        cm[idx[a], idx[b]] += 1
    n = cm.sum()
    if n == 0:
        return float("nan")
    po = np.trace(cm) / n
    pe = (cm.sum(0) * cm.sum(1)).sum() / (n * n)
    if pe >= 1:
        return 1.0 if po >= 1 else 0.0
    return float((po - pe) / (1 - pe))


def cluster_bootstrap_delta(
    hotel_ids: np.ndarray,
    err_a: np.ndarray,
    err_b: np.ndarray,
    n_boot: int = 1000,
    seed: int = 42,
) -> dict:
    """Hotel-clustered bootstrap of mean(err_a) - mean(err_b)."""
    rng = np.random.default_rng(seed)
    hotels = np.unique(hotel_ids)
    groups = {h: np.where(hotel_ids == h)[0] for h in hotels}
    diffs = np.empty(n_boot)
    nh = len(hotels)
    for i in range(n_boot):
        samp = rng.choice(hotels, size=nh, replace=True)
        idx = np.concatenate([groups[h] for h in samp])
        diffs[i] = err_a[idx].mean() - err_b[idx].mean()
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"mean": float(diffs.mean()), "ci95": [float(lo), float(hi)], "n_boot": n_boot, "n_hotels": int(nh)}


PANEL_REQUIRED = [
    "hotel_id", "legacy_hotel_id", "hotel_name", "city", "country",
    "latitude", "longitude", "period", "period_complete", "aspect",
    "positive_mentions", "negative_mentions", "total_mentions", "has_measurement",
    "positive_mentions_A", "negative_mentions_A", "total_mentions_A", "has_measurement_A",
    "positive_mentions_B", "negative_mentions_B", "total_mentions_B", "has_measurement_B",
    "raw_net", "smoothed_net", "measurement_reliability",
    "smoothed_net_A", "smoothed_net_B", "prior_only",
    "total_reviews", "mean_reviewer_score", "prior_strength",
]


def ridge_with_intercept(X: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray:
    """Ridge; do not penalize intercept column 0."""
    n, p = X.shape
    xtx = X.T @ X
    pen = np.ones(p) * alpha
    pen[0] = 0.0
    xtx = xtx + np.diag(pen)
    try:
        return np.linalg.solve(xtx, X.T @ y)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(xtx, X.T @ y, rcond=None)[0]

"""Load processed FYP tables into a Demo snapshot (no raw review text)."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from demo.config import ROOT, load_config
from demo.scoring import fnum, is_finite, median, percentile_rank, reliability, sanitize_hotel_numbers

ASPECTS_FALLBACK = [
    "location", "cleanliness", "breakfast", "service", "noise", "room", "value",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_url(u: str) -> str:
    p = urlparse((u or "").strip())
    return f"{p.scheme}://{p.netloc}{p.path}"


def hotel_id_from_url(u: str) -> str:
    path = urlparse(clean_url(u)).path.rstrip("/")
    slug = path.split("/")[-1].replace(".en-gb.html", "").replace(".html", "")
    return slug or hashlib.sha1(u.encode()).hexdigest()[:12]


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_mention_counts(jsonl_path: Path, aspects: list[str]) -> dict:
    out = defaultdict(lambda: {a: {"positive": 0, "negative": 0, "neutral": 0, "n_reviews": 0} for a in aspects})
    review_totals = defaultdict(int)
    if not jsonl_path.exists():
        return {}
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            url = clean_url(rec.get("hotel_url", ""))
            review_totals[url] += 1
            for a, d in (rec.get("aspects") or {}).items():
                if a not in out[url]:
                    continue
                s = (d or {}).get("sentiment")
                if s in ("positive", "negative", "neutral"):
                    out[url][a][s] += 1
    for url, counts in out.items():
        for a in aspects:
            counts[a]["n_reviews"] = review_totals[url]
    return dict(out)


def build_snapshot(root: Path | None = None, config_path: Path | None = None) -> dict:
    root = Path(root) if root else ROOT
    cfg = load_config(config_path)
    aspects = list(cfg.get("aspects") or ASPECTS_FALLBACK)

    p_aspect = root / "data" / "processed" / "aspect_features.csv"
    p_comp = root / "data" / "processed" / "compsets.csv"
    p_bru = root / "data" / "processed" / "brussels_hotels.csv"
    p_jsonl = root / "data" / "processed" / "review_aspects.jsonl"

    aspect_rows = _read_csv(p_aspect)
    comp_rows = _read_csv(p_comp)
    bru_rows = _read_csv(p_bru) if p_bru.exists() else []
    mentions = load_mention_counts(p_jsonl, aspects)

    bru_by_url = {clean_url(r["hotel_url"]): r for r in bru_rows}
    comp_by_url = {clean_url(r["hotel_url"]): r for r in comp_rows}

    hotels = []
    for row in aspect_rows:
        url = clean_url(row["hotel_url"])
        comp = comp_by_url.get(url, {})
        bru = bru_by_url.get(url, {})
        n_reviews = int(float(row["n_reviews"] or 0))
        n_negative = int(float(row["n_negative"] or 0))
        hid = hotel_id_from_url(url)
        recs = {}
        msrc = mentions.get(url, {})
        for a in aspects:
            net = fnum(row.get(f"{a}_net"))
            mention_rate = fnum(row.get(f"{a}_mention_rate")) or 0.0
            csv_neg_share = fnum(row.get(f"neg_{a}_share"))
            c = msrc.get(a, {})
            pos, neg, neu = int(c.get("positive", 0)), int(c.get("negative", 0)), int(c.get("neutral", 0))
            mention_count = pos + neg + neu
            if mention_count == 0 and mention_rate and n_reviews:
                mention_count = int(round(mention_rate * n_reviews))
            neg_rate = (neg / mention_count) if mention_count else None
            recs[a] = {
                "net": net,
                "mention_rate": mention_rate,
                "mention_count": mention_count,
                "pos_mentions": pos,
                "neg_mentions": neg,
                "neu_mentions": neu,
                "neg_rate": neg_rate,
                "csv_neg_share": csv_neg_share,
                "reliability": reliability(mention_count, cfg["reliability_k"]),
            }
        hotels.append({
            "hotel_id": hid,
            "hotel_url": url,
            "hotel_name": row["hotel_name"],
            "city": (bru.get("city_label") or "Brussels"),
            "compset_id": row["compset_id"] or comp.get("compset_id") or "",
            "compset_valid": str(comp.get("compset_valid") or "") == "1",
            "price_tier": comp.get("price_tier") or "",
            "star": fnum(comp.get("star")),
            "price": fnum(comp.get("price")),
            "price_imputed": fnum(comp.get("price_imputed")),
            "price_is_proxy": str(comp.get("price_is_proxy") or "0") == "1",
            "lat": fnum(comp.get("lat")),
            "lon": fnum(comp.get("lon")),
            "n_reviews": n_reviews,
            "n_negative": n_negative,
            "aspects": recs,
            "source_files": [
                "data/processed/aspect_features.csv",
                "data/processed/compsets.csv",
                "data/processed/review_aspects.jsonl",
            ],
        })

    # Peer stats within each valid compset among hotels that also have aspect rows
    by_cs: dict[str, list] = defaultdict(list)
    for h in hotels:
        if h["compset_valid"] and h["compset_id"]:
            by_cs[h["compset_id"]].append(h)

    # peer_weakest_share: among peers (excluding self), fraction whose lowest-net eligible
    # aspect equals this aspect. Computed after we have nets; uses min_mentions from config.
    min_m = int(cfg["min_mentions"])

    def weakest_aspect(h):
        cands = []
        for a in aspects:
            r = h["aspects"][a]
            if is_finite(r.get("net")) and r.get("mention_count", 0) >= min_m:
                cands.append((r["net"], a))
        if not cands:
            return None
        best = min(s for s, _ in cands)
        names = sorted(n for s, n in cands if s == best)
        return names[0]

    weakest_map = {h["hotel_id"]: weakest_aspect(h) for h in hotels}

    for h in hotels:
        peers = [p for p in by_cs.get(h["compset_id"], []) if p["hotel_id"] != h["hotel_id"]]
        h["peer_ids"] = [p["hotel_id"] for p in peers]
        h["peer_count"] = len(peers)
        h["compset_size"] = len(peers) + 1
        for a in aspects:
            peer_nets = [p["aspects"][a]["net"] for p in peers if is_finite(p["aspects"][a].get("net"))]
            all_nets = peer_nets + ([h["aspects"][a]["net"]] if is_finite(h["aspects"][a].get("net")) else [])
            med = median(peer_nets)
            h["aspects"][a]["peer_median_net"] = med
            h["aspects"][a]["peer_n"] = len(peer_nets)
            gap = (med - h["aspects"][a]["net"]) if (med is not None and is_finite(h["aspects"][a].get("net"))) else None
            h["aspects"][a]["gap"] = gap
            h["aspects"][a]["percentile"] = percentile_rank(h["aspects"][a]["net"], all_nets) if is_finite(h["aspects"][a].get("net")) else None
            if peers:
                wshare = sum(1 for p in peers if weakest_map.get(p["hotel_id"]) == a) / len(peers)
            else:
                wshare = 0.0
            h["aspects"][a]["peer_weakest_share"] = wshare
        sanitize_hotel_numbers(h)

    min_rev = int(cfg["min_reviews_hotel"])
    eligible = []
    for h in hotels:
        if not h["compset_valid"]:
            h["eligible"] = False
            h["ineligible_reason"] = "compset_valid=0"
            continue
        if h["n_reviews"] < min_rev:
            h["eligible"] = False
            h["ineligible_reason"] = f"n_reviews<{min_rev}"
            continue
        if h["peer_count"] < 2:
            h["eligible"] = False
            h["ineligible_reason"] = "peer_count<2"
            continue
        h["eligible"] = True
        h["ineligible_reason"] = ""
        eligible.append(h)

    sources = {
        "aspect_features": str(p_aspect.relative_to(root)),
        "compsets": str(p_comp.relative_to(root)),
        "brussels_hotels": str(p_bru.relative_to(root)) if p_bru.exists() else None,
        "review_aspects_jsonl": str(p_jsonl.relative_to(root)),
    }
    hashes = {k: sha256_file(root / v) for k, v in sources.items() if v and (root / v).exists()}

    return {
        "schema_version": "night-demo-2026-09-10",
        "synthetic": False,
        "city_default": "Brussels",
        "aspects": aspects,
        "config": cfg,
        "sources": sources,
        "source_file_hashes": hashes,
        "n_hotels_in_aspect_table": len(hotels),
        "n_eligible_hotels": len(eligible),
        "n_compsets": len({h["compset_id"] for h in eligible}),
        "hotels": hotels,
        "causal_checks": {},
        "predictive_holdout_metrics": None,
        "notes": [
            "Peer sets are DBSCAN(geo) ∩ price-tier labels, not validated substitutes.",
            "Aspect nets are (pos-neg)/mentions from keyword-gated DeBERTa-ABSA.",
            "Review counts are not bookings.",
        ],
    }


def hotels_by_id(snapshot: dict) -> dict[str, dict]:
    return {h["hotel_id"]: h for h in snapshot["hotels"]}


def eligible_hotels(snapshot: dict) -> list[dict]:
    return [h for h in snapshot["hotels"] if h.get("eligible")]


def save_snapshot(snapshot: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def load_snapshot(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))

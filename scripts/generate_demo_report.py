#!/usr/bin/env python3
"""Compute RESULTS.md, CASE_STUDIES.md, demo_metrics.json from the snapshot."""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.data_adapter import eligible_hotels, load_snapshot  # noqa: E402
from demo.evidence import decide_evidence_level  # noqa: E402
from demo.scoring import all_policies, ranking_under_intensity  # noqa: E402


def pairwise_agree(a: dict, b: dict) -> float:
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    return sum(1 for k in keys if a[k] == b[k]) / len(keys)


def main() -> None:
    snap_path = ROOT / "outputs" / "night_demo" / "demo_snapshot.json"
    snap = load_snapshot(snap_path)
    cfg = snap["config"]
    ev = decide_evidence_level(snap)
    hotels = eligible_hotels(snap)
    labels = cfg.get("aspect_labels") or {}

    recs = {}
    for h in hotels:
        recs[h["hotel_id"]] = {
            k: v["chosen_aspect"]
            for k, v in all_policies(h, cfg, 0.0).items()
        }

    dist = {k: Counter(v[k] for v in recs.values() if v[k]) for k in recs[next(iter(recs))]}
    keys = list(next(iter(recs.values())).keys())
    pair = {}
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            pair[f"{a}__{b}"] = pairwise_agree(
                {hid: recs[hid][a] for hid in recs},
                {hid: recs[hid][b] for hid in recs},
            )
    disagree_fw_ca = sum(1 for hid, r in recs.items() if r["fix_weakest"] != r["competition_aware"])
    disagree_fw_gap = sum(1 for hid, r in recs.items() if r["fix_weakest"] != r["largest_peer_gap"])

    # coverage
    aspect_cov = {}
    for a in cfg["aspects"]:
        n_ok = 0
        for h in hotels:
            rec = h["aspects"][a]
            if rec.get("net") is not None and rec.get("mention_count", 0) >= cfg["min_mentions"]:
                n_ok += 1
        aspect_cov[a] = {"eligible_hotels_with_aspect": n_ok, "share": n_ok / len(hotels) if hotels else 0}

    sizes = [h["compset_size"] for h in hotels]
    evidence = [h["n_reviews"] for h in hotels]
    mentions = [sum(h["aspects"][a]["mention_count"] for a in cfg["aspects"]) for h in hotels]

    # case studies
    agree_all = [h for h in hotels if len({recs[h["hotel_id"]][k] for k in keys}) == 1]
    fw_vs_gap = [h for h in hotels if recs[h["hotel_id"]]["fix_weakest"] != recs[h["hotel_id"]]["largest_peer_gap"]]
    ca_changes = [h for h in hotels if recs[h["hotel_id"]]["fix_weakest"] != recs[h["hotel_id"]]["competition_aware"]]

    def pack_case(h, why):
        r = recs[h["hotel_id"]]
        pol = all_policies(h, cfg, 0.0)
        rnk0 = ranking_under_intensity(h, cfg, 0.0)
        rnk1 = ranking_under_intensity(h, cfg, 1.0)
        return {
            "why": why,
            "hotel_id": h["hotel_id"],
            "hotel_name": h["hotel_name"],
            "compset_id": h["compset_id"],
            "n_reviews": h["n_reviews"],
            "n_negative": h["n_negative"],
            "choices_intensity0": r,
            "ca_rank_intensity0": rnk0,
            "ca_rank_intensity1": rnk1,
            "changes_at_full_assumed_crowding": (rnk0[0][0] != rnk1[0][0]) if rnk0 and rnk1 else False,
            "aspect_preview": {
                a: {
                    "net": h["aspects"][a]["net"],
                    "gap": h["aspects"][a]["gap"],
                    "mentions": h["aspects"][a]["mention_count"],
                    "neg_mentions": h["aspects"][a]["neg_mentions"],
                    "reliability": round(h["aspects"][a]["reliability"], 3),
                    "peer_weakest_share": h["aspects"][a]["peer_weakest_share"],
                }
                for a in cfg["aspects"]
            },
            "rules": {k: pol[k]["rule"] for k in keys},
        }

    cases = []
    if agree_all:
        cases.append(pack_case(agree_all[0], "four strategies agree at assumed_intensity=0"))
    if fw_vs_gap:
        # prefer one not already used
        used = {c["hotel_id"] for c in cases}
        h = next((x for x in fw_vs_gap if x["hotel_id"] not in used), fw_vs_gap[0])
        cases.append(pack_case(h, "Fix Weakest disagrees with Largest Peer Gap"))
    if ca_changes:
        used = {c["hotel_id"] for c in cases}
        h = next((x for x in ca_changes if x["hotel_id"] not in used), ca_changes[0])
        cases.append(pack_case(h, "Competition-Aware differs from Fix Weakest (heuristic mix / reliability / peer context)"))
    else:
        # honesty: maybe crowding at intensity=1 changes someone
        crowd_change = []
        for h in hotels:
            r0 = ranking_under_intensity(h, cfg, 0.0)
            r1 = ranking_under_intensity(h, cfg, 1.0)
            if r0 and r1 and r0[0][0] != r1[0][0]:
                crowd_change.append(h)
        if crowd_change:
            used = {c["hotel_id"] for c in cases}
            h = next((x for x in crowd_change if x["hotel_id"] not in used), crowd_change[0])
            cases.append(pack_case(h, "Competition-Aware ranking changes only under assumed crowding intensity=1 (scenario, not estimated)"))
        else:
            cases.append({
                "why": "NO_CASE: Competition-Aware never differed from Fix Weakest in this snapshot",
                "hotel_id": None,
            })

    metrics = {
        "evidence_level": ev["level"],
        "n_eligible_hotels": len(hotels),
        "n_compsets": snap["n_compsets"],
        "compset_ids": sorted({h["compset_id"] for h in hotels}),
        "compset_size_min": min(sizes) if sizes else None,
        "compset_size_median": statistics.median(sizes) if sizes else None,
        "compset_size_max": max(sizes) if sizes else None,
        "n_reviews_min": min(evidence) if evidence else None,
        "n_reviews_median": statistics.median(evidence) if evidence else None,
        "n_reviews_max": max(evidence) if evidence else None,
        "aspect_coverage": aspect_cov,
        "policy_choice_counts": {k: dict(v) for k, v in dist.items()},
        "pairwise_agreement": pair,
        "n_fix_weakest_ne_competition_aware": disagree_fw_ca,
        "share_fix_weakest_ne_competition_aware": disagree_fw_ca / len(hotels) if hotels else 0,
        "n_fix_weakest_ne_largest_peer_gap": disagree_fw_gap,
        "share_fix_weakest_ne_largest_peer_gap": disagree_fw_gap / len(hotels) if hotels else 0,
        "n_all_four_agree": len(agree_all),
        "recommendations": recs,
    }

    out_dir = ROOT / "outputs" / "night_demo"
    (out_dir / "demo_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    def fmt_counts(c):
        if not c:
            return "(none)"
        return ", ".join(f"{labels.get(a,a)}={n}" for a, n in sorted(c.items(), key=lambda kv: -kv[1]))

    results = f"""# Night Demo RESULTS (DESCRIPTIVE)

Evidence level: **{ev['level']}**

{ev['why']}

## Data facts (not heuristics)

- Eligible hotels (valid compset, ≥{cfg['min_reviews_hotel']} labelled reviews, ≥2 aspect-peers): **{len(hotels)}**
- Valid competition sets used: **{snap['n_compsets']}** — `{', '.join(sorted({h['compset_id'] for h in hotels}))}`
- Compset size among eligible hotels: min={metrics['compset_size_min']}, median={metrics['compset_size_median']}, max={metrics['compset_size_max']}
- Labelled-review count among eligible hotels: min={metrics['n_reviews_min']}, median={metrics['n_reviews_median']}, max={metrics['n_reviews_max']}
- Aspect coverage (eligible hotels with net defined and mentions ≥ {cfg['min_mentions']}):
"""
    for a, d in aspect_cov.items():
        results += f"  - {labels.get(a,a)}: {d['eligible_hotels_with_aspect']}/{len(hotels)} ({d['share']:.0%})\n"

    results += f"""
## Heuristic policy results (assumed_intensity = 0)

These counts are **outputs of the documented heuristic**, not estimated effects.

Fix Weakest: {fmt_counts(dist['fix_weakest'])}
Largest Peer Gap: {fmt_counts(dist['largest_peer_gap'])}
Most Criticized: {fmt_counts(dist['most_criticized'])}
Competition-Aware: {fmt_counts(dist['competition_aware'])}

Pairwise agreement (share of eligible hotels with the same chosen aspect):
"""
    for k, v in pair.items():
        results += f"- {k}: **{v:.1%}**\n"

    results += f"""
- Fix Weakest ≠ Largest Peer Gap: **{disagree_fw_gap}/{len(hotels)}** ({metrics['share_fix_weakest_ne_largest_peer_gap']:.1%})
- Fix Weakest ≠ Competition-Aware: **{disagree_fw_ca}/{len(hotels)}** ({metrics['share_fix_weakest_ne_competition_aware']:.1%})
- All four agree: **{len(agree_all)}/{len(hotels)}**

## What is a data fact vs a heuristic vs a scenario

| Item | Kind |
|---|---|
| Eligible hotel/compset counts, mention counts, nets, peer medians | Data fact from processed tables |
| Four strategy choices at intensity=0 | Transparent heuristic |
| Slider / intensity>0 ranking changes | Assumed scenario, not estimated lambda |
| Causal gain, demand lift, ROI | **Not computed; not claimed** |

## Conclusions that are NOT supported

- Improving the recommended aspect will raise ratings, reviews, or bookings.
- Peer-weakest-share is an identified spillover or crowding elasticity.
- These 3 Brussels centre sets are the true consideration set of guests.
"""
    (out_dir / "RESULTS.md").write_text(results, encoding="utf-8")

    case_md = "# Case studies\n\nAll cases use real eligible hotels from `aspect_features.csv` + `compsets.csv`.\n\n"
    for i, c in enumerate(cases, 1):
        if not c.get("hotel_id"):
            case_md += f"## Case {i}\n\n{c['why']}\n\n"
            continue
        case_md += f"## Case {i}: {c['hotel_name']}\n\n"
        case_md += f"- Why selected: {c['why']}\n"
        case_md += f"- hotel_id: `{c['hotel_id']}`\n"
        case_md += f"- compset_id: `{c['compset_id']}`\n"
        case_md += f"- labelled reviews: {c['n_reviews']} (low-rating reviews: {c['n_negative']})\n"
        case_md += "- Choices at assumed_intensity=0:\n"
        for k, a in c["choices_intensity0"].items():
            case_md += f"  - {k}: **{labels.get(a,a)}**\n"
        case_md += "- Aspect snapshot:\n\n"
        case_md += "| aspect | net | gap | mentions | neg_mentions | reliability | peer_weakest_share |\n|---|---:|---:|---:|---:|---:|---:|\n"
        for a, rec in c["aspect_preview"].items():
            case_md += (
                f"| {labels.get(a,a)} | {rec['net']} | {rec['gap']} | {rec['mentions']} | "
                f"{rec['neg_mentions']} | {rec['reliability']} | {rec['peer_weakest_share']:.2f} |\n"
            )
        case_md += (
            f"\n- CA top at intensity=0: `{c['ca_rank_intensity0'][0][0] if c['ca_rank_intensity0'] else None}`"
            f" · at assumed intensity=1: `{c['ca_rank_intensity1'][0][0] if c['ca_rank_intensity1'] else None}`"
            f" · ranking flips: {c['changes_at_full_assumed_crowding']}\n\n"
        )
    (out_dir / "CASE_STUDIES.md").write_text(case_md, encoding="utf-8")
    print("wrote RESULTS.md CASE_STUDIES.md demo_metrics.json")
    print("eligible", len(hotels), "fw!=ca", disagree_fw_ca, "fw!=gap", disagree_fw_gap)


if __name__ == "__main__":
    main()

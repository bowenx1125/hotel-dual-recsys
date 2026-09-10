#!/usr/bin/env python3
"""Weight sensitivity for Peer-Relative Evidence-Weighted heuristic (design-choice weights)."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.data_adapter import eligible_hotels, load_snapshot
from demo.scoring import policy_peer_relative


def main() -> None:
    snap = load_snapshot(ROOT / "outputs" / "night_demo" / "demo_snapshot.json")
    cfg = snap["config"]
    # refresh weights/grids from canonical file if present
    from demo.config import load_config
    live = load_config()
    cfg = {**cfg, **{k: live[k] for k in ("weights", "weight_grids", "heuristic_name", "actionability_config") if k in live}}
    hotels = eligible_hotels(snap)
    grids = live.get("weight_grids") or {"current-default": live["weights"]}
    labels = live.get("aspect_labels") or {}

    per_hotel = {}
    grid_counts = {g: Counter() for g in grids}
    for h in hotels:
        picks = {}
        for gname, w in grids.items():
            pol = policy_peer_relative(h, cfg, 0.0, weights=w)
            a = pol["chosen_aspect"]
            picks[gname] = a
            if a:
                grid_counts[gname][a] += 1
        unique = {p for p in picks.values() if p}
        per_hotel[h["hotel_id"]] = {
            "hotel_name": h["hotel_name"],
            "picks": picks,
            "n_unique": len(unique),
            "stable": len(unique) <= 1,
        }

    n = len(hotels)
    n_stable = sum(1 for v in per_hotel.values() if v["stable"])
    switching = 1.0 - (n_stable / n if n else 0.0)
    # most unstable: max unique picks
    unstable = sorted(per_hotel.items(), key=lambda kv: (-kv[1]["n_unique"], kv[0]))[:5]

    out = {
        "n_hotels": n,
        "grids": list(grids.keys()),
        "weights": grids,
        "n_fully_stable_across_grids": n_stable,
        "share_fully_stable": n_stable / n if n else 0.0,
        "top1_switching_rate": switching,
        "recommendation_counts_by_grid": {g: dict(c) for g, c in grid_counts.items()},
        "most_unstable_hotels": [
            {"hotel_id": hid, **meta} for hid, meta in unstable if meta["n_unique"] > 1
        ],
        "note": "Weights are design choices, not learned business returns.",
    }
    out_dir = ROOT / "outputs" / "overnight" / "demo_semantics"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "weight_sensitivity.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    md = [
        "# Weight Sensitivity",
        "",
        "**Weights are design choices, not learned business returns.**",
        "",
        f"- Eligible hotels: **{n}**",
        f"- Grids: {', '.join(grids)}",
        f"- Fully stable top-1 across all grids: **{n_stable}/{n}** ({out['share_fully_stable']:.1%})",
        f"- Top-1 switching rate: **{switching:.1%}**",
        "",
        "## Recommendation counts by grid",
        "",
    ]
    for g, c in grid_counts.items():
        pretty = ", ".join(f"{labels.get(a,a)}={k}" for a, k in c.most_common())
        md.append(f"- `{g}`: {pretty or '(none)'}")
    md += ["", "## Most unstable hotels", ""]
    if out["most_unstable_hotels"]:
        for u in out["most_unstable_hotels"]:
            md.append(f"- {u['hotel_name']} (`{u['hotel_id']}`): {u['n_unique']} distinct picks → {u['picks']}")
    else:
        md.append("- (none)")
    (out_dir / "WEIGHT_SENSITIVITY.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("n_hotels", "n_fully_stable_across_grids", "top1_switching_rate")}, indent=2))


if __name__ == "__main__":
    main()

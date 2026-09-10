#!/usr/bin/env python3
"""Render a dashboard-style PNG covering required Demo sections (no browser required)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.data_adapter import eligible_hotels, load_snapshot
from demo.evidence import BANNER, decide_evidence_level
from demo.scoring import all_policies, ranking_under_intensity


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    snap = load_snapshot(ROOT / "outputs" / "night_demo" / "demo_snapshot.json")
    cfg = snap["config"]
    labels = cfg.get("aspect_labels") or {}
    ev = decide_evidence_level(snap)
    hotels = eligible_hotels(snap)
    # pick a disagreement hotel if possible
    hotel = hotels[0]
    for h in hotels:
        pol = all_policies(h, cfg, 0.0)
        if pol["fix_weakest"]["chosen_aspect"] != pol["competition_aware"]["chosen_aspect"]:
            hotel = h
            break
        if pol["fix_weakest"]["chosen_aspect"] != pol["largest_peer_gap"]["chosen_aspect"]:
            hotel = h
    pol0 = all_policies(hotel, cfg, 0.0)
    pol1 = all_policies(hotel, cfg, 1.0)

    fig = plt.figure(figsize=(13.5, 9.2))
    gs = GridSpec(3, 2, figure=fig, height_ratios=[0.55, 1.3, 1.1], hspace=0.45, wspace=0.28)

    ax_ban = fig.add_subplot(gs[0, :])
    ax_ban.axis("off")
    ax_ban.set_title("Hotel Selector  ·  Evidence Banner  ·  Hotel vs Peers  ·  Policies  ·  Scenario", loc="left", fontsize=11)
    banner = (
        f"SELECTOR  city={hotel['city']}   set={hotel['compset_id']}   hotel={hotel['hotel_name']}\n"
        f"{BANNER}\n"
        f"level={ev['level']}   peers={hotel['peer_count']}   labelled_reviews={hotel['n_reviews']}   "
        f"sources=aspect_features.csv + compsets.csv + review_aspects.jsonl"
    )
    ax_ban.text(0.0, 0.5, banner, va="center", ha="left", fontsize=9,
                bbox=dict(boxstyle="round", facecolor="#FDECEC", edgecolor="#C0392B"),
                transform=ax_ban.transAxes, wrap=True)

    ax_cmp = fig.add_subplot(gs[1, 0])
    aspects = cfg["aspects"]
    y = range(len(aspects))
    hotel_net = [hotel["aspects"][a].get("net") for a in aspects]
    peer_med = [hotel["aspects"][a].get("peer_median_net") for a in aspects]
    ax_cmp.plot(peer_med, y, "o", color="#4C78A8", label="peer median", ms=8)
    ax_cmp.plot(hotel_net, y, "s", color="#F58518", label="this hotel", ms=8)
    ax_cmp.set_yticks(list(y), [labels.get(a, a) for a in aspects])
    ax_cmp.set_xlim(-1.05, 1.05)
    ax_cmp.axvline(0, color="#aaa", lw=0.8)
    ax_cmp.invert_yaxis()
    ax_cmp.set_xlabel("net sentiment")
    ax_cmp.set_title("Hotel vs peers")
    ax_cmp.legend(frameon=False, loc="lower right")

    ax_pol = fig.add_subplot(gs[1, 1])
    ax_pol.axis("off")
    ax_pol.set_title("Four strategies (assumed_intensity=0)")
    lines = []
    for k in ("fix_weakest", "largest_peer_gap", "most_criticized", "competition_aware"):
        a = pol0[k]["chosen_aspect"]
        lines.append(f"{pol0[k]['label']}:  {labels.get(a, a)}")
    lines.append("")
    lines.append("At assumed intensity=1 (SCENARIO, not estimated):")
    a1 = pol1["competition_aware"]["chosen_aspect"]
    lines.append(f"Competition-Aware:  {labels.get(a1, a1)}")
    ax_pol.text(0.0, 0.95, "\n".join(lines), va="top", family="monospace", fontsize=10)

    ax_sc = fig.add_subplot(gs[2, :])
    xs = [0, 0.25, 0.5, 0.75, 1.0]
    tops = []
    for x in xs:
        r = ranking_under_intensity(hotel, cfg, x)
        tops.append(r[0][0] if r else None)
    # plot score of each aspect vs intensity
    for a in aspects:
        ys = []
        for x in xs:
            r = dict(ranking_under_intensity(hotel, cfg, x))
            ys.append(r.get(a))
        if any(v is not None for v in ys):
            ax_sc.plot(xs, ys, marker="o", label=labels.get(a, a))
    ax_sc.set_xlabel("assumed peer-improve intensity (illustrative)")
    ax_sc.set_ylabel("heuristic score")
    ax_sc.set_title("Peer-exposure scenario (assumed crowding; not a fitted lambda)")
    ax_sc.legend(ncol=4, frameon=False, fontsize=8)
    fig.suptitle("Provider-side Demo screenshot  ·  NOT SYNTHETIC  ·  DESCRIPTIVE only", fontsize=13, y=0.995)
    out = ROOT / "outputs" / "night_demo" / "demo_screenshot.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    main()

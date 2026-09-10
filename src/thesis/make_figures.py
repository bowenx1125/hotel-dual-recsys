#!/usr/bin/env python3
"""Generate publication-style figures for the FYP-1 partial thesis from real data."""
import csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIG = os.path.join(ROOT, "figures")
os.makedirs(FIG, exist_ok=True)

# palette (matches the deck: navy/blue/gold)
NAVY = "#0B2E4A"; BLUE = "#0166A4"; BLUELT = "#4E9AC4"; GOLD = "#C0892B"
INK = "#1F2A37"; MUTE = "#6B7785"; CARD = "#EEF4FA"; LINE = "#D8E2EC"
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 11, "axes.edgecolor": "#888", "axes.linewidth": 0.8,
    "figure.dpi": 200,
})

# ---------------------------------------------------------------- Figure: architecture
def fig_architecture():
    fig, ax = plt.subplots(figsize=(7.2, 4.3)); ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 6)

    def box(x, y, w, h, text, fc, tc="white", fs=10, bold=True):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.12",
                                    fc=fc, ec="none"))
        ax.text(x + w/2, y + h/2, text, ha="center", va="center", color=tc,
                fontsize=fs, fontweight="bold" if bold else "normal", wrap=True)

    def arrow(x1, y1, x2, y2, color=BLUE):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                     mutation_scale=14, lw=1.6, color=color))

    # shared representation in the middle
    box(3.2, 2.5, 3.6, 1.0, "Shared Hotel Representation", NAVY, fs=11)
    ax.text(5.0, 2.32, "relative price  ·  aspect quality  ·  location  ·  review credibility  ·  complaint mix",
            ha="center", va="top", color=MUTE, fontsize=7.3)

    # data sources feeding representation
    box(0.4, 4.7, 4.2, 0.85, "Booking.com reviews (Kaggle, 26,675)", BLUE, fs=8.7)
    box(5.4, 4.7, 4.2, 0.85, "Scraped attributes (price, geo, star)", BLUE, fs=8.7)
    arrow(2.5, 4.7, 4.2, 3.5)
    arrow(7.5, 4.7, 5.8, 3.5)

    # two readouts
    box(0.3, 0.5, 4.0, 1.15, "TOURIST view\nbest value within budget", GOLD, fs=9.5)
    box(5.7, 0.5, 4.0, 1.15, "MANAGER view\ncompetitive diagnosis", GOLD, fs=9.5)
    arrow(4.4, 2.5, 2.3, 1.65); arrow(5.6, 2.5, 7.7, 1.65)

    ax.text(2.3, 1.95, "rank", ha="center", color=MUTE, fontsize=7.5, style="italic")
    ax.text(7.7, 1.95, "position +\nsuggest", ha="center", color=MUTE, fontsize=7.5, style="italic")

    plt.tight_layout(pad=0.2)
    fig.savefig(os.path.join(FIG, "fig_architecture.png"), bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ---------------------------------------------------------------- Figure: pipeline
def fig_pipeline():
    fig, ax = plt.subplots(figsize=(7.4, 2.3)); ax.axis("off")
    ax.set_xlim(0, 12); ax.set_ylim(0, 3)
    stages = [
        ("Phase 0\nScrape & clean", "822 pages\nprice/geo/star", BLUE),
        ("Phase 1\nCompetition sets", "DBSCAN +\nprice tiers", NAVY),
        ("Phase 2\nABSA", "7 aspects\nDeBERTa", BLUE),
        ("Phase 3+\nDual readout", "Tourist +\nManager", GOLD),
    ]
    w = 2.4; gap = 0.7; x = 0.3
    for i, (t, sub, c) in enumerate(stages):
        ax.add_patch(FancyBboxPatch((x, 0.9), w, 1.25, boxstyle="round,pad=0.04,rounding_size=0.1",
                                    fc=c, ec="none"))
        ax.text(x + w/2, 1.75, t, ha="center", va="center", color="white", fontsize=9.5, fontweight="bold")
        ax.text(x + w/2, 1.18, sub, ha="center", va="center", color="#dce8f2", fontsize=7.6)
        if i < len(stages) - 1:
            ax.add_patch(FancyArrowPatch((x + w, 1.52), (x + w + gap, 1.52), arrowstyle="-|>",
                         mutation_scale=14, lw=1.8, color=MUTE))
        x += w + gap
    plt.tight_layout(pad=0.2)
    fig.savefig(os.path.join(FIG, "fig_pipeline.png"), bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ---------------------------------------------------------------- Figure: city distribution
def fig_cities():
    data = [("Brussels", 80), ("Bruges", 62), ("Antwerp", 38), ("Ghent", 29),
            ("Ostend", 25), ("Liège", 20), ("Namur", 18), ("Ypres", 16),
            ("De Haan", 16), ("Blankenberge", 13)]
    names = [d[0] for d in data][::-1]; vals = [d[1] for d in data][::-1]
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    colors = [BLUE if n == "Brussels" else BLUELT for n in names]
    ax.barh(names, vals, color=colors, height=0.68)
    for i, v in enumerate(vals):
        ax.text(v + 0.8, i, str(v), va="center", fontsize=9, color=INK)
    ax.set_xlabel("Number of distinct hotels (located by coordinates)", fontsize=9.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(0, 90)
    ax.tick_params(labelsize=9)
    plt.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_cities.png"), bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ---------------------------------------------------------------- Figure: competition set scatter
def fig_compset():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data/processed/compsets.csv"))))
    geo0 = [r for r in rows if r["geo_cluster"] == "0" and r["compset_valid"] == "1"]
    tier_color = {"low": BLUELT, "mid": BLUE, "high": NAVY}
    tier_label = {"low": "Low tier", "mid": "Mid tier", "high": "High tier"}
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    seen = set()
    for r in geo0:
        t = r["price_tier"]
        lab = tier_label[t] if t not in seen else None
        seen.add(t)
        ax.scatter(float(r["lon"]), float(r["lat"]), s=120, color=tier_color[t],
                   edgecolor="white", linewidth=0.8, label=lab, zorder=3)
    ax.set_xlabel("Longitude", fontsize=9.5); ax.set_ylabel("Latitude", fontsize=9.5)
    ax.set_title("Brussels city-centre cluster: one geographic group split into three price-tier competition sets",
                 fontsize=8.8, color=INK, pad=8)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)
    ax.grid(True, color=LINE, linewidth=0.6, zorder=0)
    plt.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_compset.png"), bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ---------------------------------------------------------------- Figure: aspect heatmap (one comp set)
def fig_aspect_heatmap():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data/processed/aspect_features.csv"))))
    # use the high-tier competition set (recognisable brands, manager-diagnosis story)
    target = "geo0_high"
    aspects = ["location", "cleanliness", "breakfast", "service", "noise", "room", "value"]
    sub = [r for r in rows if r["compset_id"] == target]
    # shorten names
    def short(n):
        n = n.replace("Brussels", "Br.").replace("Hotel", "").strip()
        return (n[:22] + "…") if len(n) > 23 else n
    labels = [short(r["hotel_name"]) for r in sub]
    M = np.full((len(sub), len(aspects)), np.nan)
    for i, r in enumerate(sub):
        for j, a in enumerate(aspects):
            v = r[f"{a}_net"]
            if v not in ("", None):
                M[i, j] = float(v)
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    cmap = plt.cm.RdYlGn
    im = ax.imshow(M, cmap=cmap, vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(aspects))); ax.set_xticklabels([a.capitalize() for a in aspects], fontsize=8.5, rotation=30, ha="right")
    ax.set_yticks(range(len(sub))); ax.set_yticklabels(labels, fontsize=8.2)
    for i in range(len(sub)):
        for j in range(len(aspects)):
            if not np.isnan(M[i, j]):
                ax.text(j, i, f"{M[i,j]:.2f}", ha="center", va="center", fontsize=7,
                        color="#222" if abs(M[i, j]) < 0.6 else "white")
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cb.set_label("Net sentiment  (−1 … +1)", fontsize=8)
    cb.ax.tick_params(labelsize=7.5)
    ax.set_title("Aspect net sentiment within one competition set (high-tier, Brussels centre)",
                 fontsize=8.8, color=INK, pad=8)
    plt.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_aspect_heatmap.png"), bbox_inches="tight", facecolor="white")
    plt.close(fig)

if __name__ == "__main__":
    fig_architecture(); fig_pipeline(); fig_cities(); fig_compset(); fig_aspect_heatmap()
    print("Figures written to", FIG)
    for f in sorted(os.listdir(FIG)):
        print("  ", f)

"""Optional matplotlib helpers. App also works without matplotlib."""
from __future__ import annotations

from pathlib import Path


def hotel_vs_peers_png(hotel: dict, labels: dict, path: Path) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None
    aspects = list(hotel["aspects"].keys())
    names = [labels.get(a, a) for a in aspects]
    hotel_net = [hotel["aspects"][a].get("net") for a in aspects]
    peer_med = [hotel["aspects"][a].get("peer_median_net") for a in aspects]
    y = range(len(aspects))
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    ax.hlines(y, [-1] * len(y), [1] * len(y), color="#e6e6e6", linewidth=1)
    ax.plot(peer_med, y, "o", color="#4C78A8", label="Peer median net", markersize=8)
    ax.plot(hotel_net, y, "s", color="#F58518", label="This hotel net", markersize=8)
    ax.set_yticks(list(y), names)
    ax.set_xlim(-1.05, 1.05)
    ax.set_xlabel("Aspect net sentiment  (pos−neg)/mentions   [-1, 1]")
    ax.set_title(f"{hotel['hotel_name']}  vs  {hotel['compset_id']} peers")
    ax.axvline(0, color="#999", linewidth=0.8)
    ax.legend(loc="lower right", frameon=False)
    ax.invert_yaxis()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def strategy_bar_png(score_table: dict, labels: dict, title: str, path: Path) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None
    items = sorted(score_table.items(), key=lambda kv: kv[1] if kv[1] is not None else -999)
    names = [labels.get(a, a) for a, _ in items]
    vals = [v if v is not None else 0 for _, v in items]
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.barh(names, vals, color="#4C78A8")
    ax.set_title(title)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path

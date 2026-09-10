#!/usr/bin/env python3
"""Regenerate conf/demo.yaml from canonical conf/demo.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cfg = json.loads((ROOT / "conf" / "demo.json").read_text(encoding="utf-8"))
    lines = [
        "# AUTO-GENERATED from conf/demo.json — do not edit by hand.",
        "# Regenerate: python3 scripts/sync_demo_yaml.py",
        "# Canonical machine source: conf/demo.json",
        "",
        "aspects:",
    ]
    for a in cfg["aspects"]:
        lines.append(f"  - {a}")
    lines.append("")
    lines.append("aspect_labels:")
    for k, v in cfg["aspect_labels"].items():
        lines.append(f"  {k}: {v}")
    lines += [
        "",
        f"min_mentions: {cfg['min_mentions']}",
        f"min_reviews_hotel: {cfg['min_reviews_hotel']}",
        f"reliability_k: {cfg['reliability_k']}",
        "",
        "# Peer-Relative Evidence-Weighted (heuristic) — DESCRIPTIVE design-choice weights.",
        "# Weights are NOT learned business returns.",
        "weights:",
        f"  gap: {cfg['weights']['gap']}",
        f"  criticism: {cfg['weights']['criticism']}",
        f"  unreliable: {cfg['weights']['unreliable']}",
        "",
        "scenario:",
        f"  crowding_weight: {cfg['scenario']['crowding_weight']}",
        f"  default_intensity: {cfg['scenario']['default_intensity']}",
        f"  intensity_min: {cfg['scenario']['intensity_min']}",
        f"  intensity_max: {cfg['scenario']['intensity_max']}",
        "",
        f"tie_break: {cfg['tie_break']}",
        f"heuristic_name: {cfg['heuristic_name']}",
        f"formula: \"{cfg['formula']}\"",
        f"actionability_config: {cfg['actionability_config']}",
        "",
    ]
    (ROOT / "conf" / "demo.yaml").write_text("\n".join(lines), encoding="utf-8")
    print("synced conf/demo.yaml from conf/demo.json")


if __name__ == "__main__":
    main()

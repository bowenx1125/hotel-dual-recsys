#!/usr/bin/env python3
"""Build outputs/night_demo/demo_snapshot.json from processed FYP tables."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.data_adapter import build_snapshot, save_snapshot  # noqa: E402


def main() -> None:
    snap = build_snapshot(ROOT)
    out = ROOT / "outputs" / "night_demo" / "demo_snapshot.json"
    save_snapshot(snap, out)
    print(f"wrote {out}")
    print(f"hotels_in_table={snap['n_hotels_in_aspect_table']} eligible={snap['n_eligible_hotels']} compsets={snap['n_compsets']}")
    print("synthetic=", snap["synthetic"])
    print("sources=", snap["sources"])


if __name__ == "__main__":
    main()

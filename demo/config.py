"""Demo configuration. conf/demo.json is canonical; YAML is a generated mirror."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "conf" / "demo.json"
ACTIONABILITY_CONFIG = ROOT / "conf" / "actionability.json"


def load_config(path: Path | None = None) -> dict:
    p = Path(path) if path else DEFAULT_CONFIG
    data = json.loads(p.read_text(encoding="utf-8"))
    required = ["aspects", "min_mentions", "min_reviews_hotel", "weights", "scenario"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"Invalid config {p}: missing {missing}")
    return data


def load_actionability_config(path: Path | None = None) -> dict:
    p = Path(path) if path else ACTIONABILITY_CONFIG
    return json.loads(p.read_text(encoding="utf-8"))

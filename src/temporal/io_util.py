from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path: Path, obj: Any) -> None:
    atomic_write_text(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def load_temporal_config(root: Path) -> dict:
    p = root / "conf" / "temporal_feasibility.json"
    return json.loads(p.read_text(encoding="utf-8"))


def resolve_europe_csv(cfg: dict, cache_root: str | None = None) -> Path:
    cache = Path(
        cache_root
        or os.environ.get("FYP_DATA_CACHE_ROOT")
        or ""
    )
    if not str(cache):
        raise FileNotFoundError(
            "Set FYP_DATA_CACHE_ROOT or pass --cache-root; expected 515K Europe CSV."
        )
    rel = cfg["dataset"]["relative_path"]
    path = cache / rel
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Download Hotel_Reviews.csv into FYP_DATA_CACHE_ROOT/{rel}"
        )
    return path

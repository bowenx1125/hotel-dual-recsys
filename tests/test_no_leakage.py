"""No secrets, no raw review text in tracked research artifacts."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SECRET_MARKERS = (
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "ghp_",
    "github_pat_",
    "AKIA",
)
TEXT_COLS = ("Positive_Review", "Negative_Review", "raw_review_text", "review_text")
SKIP_DIRS = {".git", ".venv-fyp", "node_modules", "outputs/autonomous/private", "data/interim"}


def _iter_text_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel = os.path.relpath(dirpath, ROOT)
        dirnames[:] = [d for d in dirnames if d not in {".git", ".venv-fyp", "node_modules", "private", ".venv"}]
        if "outputs/autonomous/private" in rel.replace("\\", "/"):
            continue
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() in {".png", ".parquet", ".jpg", ".safetensors", ".pyc"}:
                continue
            if p.stat().st_size > 2_000_000:
                continue
            yield p


class TestNoLeakage(unittest.TestCase):
    def test_no_secret_markers_in_small_text(self):
        hits = []
        for p in _iter_text_files():
            rel = str(p.relative_to(ROOT))
            if rel.startswith("tests/"):
                continue
            try:
                t = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for m in SECRET_MARKERS:
                if m in t:
                    hits.append((str(p.relative_to(ROOT)), m))
        self.assertEqual(hits, [])

    def test_autonomous_outputs_have_no_review_text_columns(self):
        import pandas as pd
        base = ROOT / "outputs" / "autonomous"
        if not base.exists():
            self.skipTest("no autonomous outputs yet")
        bad = []
        for p in base.rglob("*"):
            if "private" in p.parts or "fixtures" in p.parts:
                continue
            if p.suffix == ".csv":
                try:
                    cols = set(pd.read_csv(p, nrows=0).columns)
                except Exception:
                    continue
                if cols.intersection(TEXT_COLS):
                    bad.append(str(p.relative_to(ROOT)))
            if p.suffix == ".parquet":
                try:
                    cols = set(pd.read_parquet(p, columns=None).columns)
                except Exception:
                    continue
                if cols.intersection(TEXT_COLS):
                    bad.append(str(p.relative_to(ROOT)))
        self.assertEqual(bad, [])

    def test_gitignore_private_pack(self):
        gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("outputs/autonomous/private/", gi)
        self.assertIn("Hotel_Reviews.csv", gi)


if __name__ == "__main__":
    unittest.main()

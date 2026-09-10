from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from demo.data_adapter import build_snapshot, eligible_hotels, save_snapshot
from demo.scoring import all_policies


class TestSmoke(unittest.TestCase):
    def test_end_to_end_snapshot_roundtrip(self):
        snap = build_snapshot(ROOT)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "snap.json"
            save_snapshot(snap, p)
            data = json.loads(p.read_text())
            self.assertGreaterEqual(data["n_eligible_hotels"], 3)
            h = eligible_hotels(data)[0]
            pol = all_policies(h, data["config"], 0.0)
            self.assertEqual(len(pol), 4)
            self.assertTrue(h["hotel_id"] and h["compset_id"])

    def test_build_script(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_demo_snapshot.py")],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertTrue((ROOT / "outputs" / "night_demo" / "demo_snapshot.json").exists())

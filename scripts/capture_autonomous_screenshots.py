#!/usr/bin/env python3
"""Capture live Streamlit screenshots from THIS autonomous branch (not 0f5ebd5)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    out = ROOT / "outputs" / "autonomous" / "demo"
    out.mkdir(parents=True, exist_ok=True)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        (out / "screenshot_manifest.json").write_text(
            json.dumps({"status": "SKIPPED_NO_PLAYWRIGHT"}, indent=2) + "\n", encoding="utf-8"
        )
        return 2

    env = {**os.environ, "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"}
    port = 8517
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", str(ROOT / "demo" / "app.py"),
            "--server.port", str(port), "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        ready = False
        for _ in range(90):
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(url, timeout=2) as r:
                    if r.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(1)
        if not ready:
            (out / "screenshot_manifest.json").write_text(
                json.dumps({"status": "STREAMLIT_NOT_READY"}, indent=2) + "\n", encoding="utf-8"
            )
            return 1

        facts = {}
        fp = ROOT / "outputs" / "autonomous" / "FACTS.json"
        if fp.exists():
            facts = json.loads(fp.read_text(encoding="utf-8"))
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.goto(url, wait_until="networkidle", timeout=120000)
            page.get_by_text("酒店改善助手").first.wait_for(timeout=120000)
            page.get_by_text("建议先关注").first.wait_for(timeout=60000)
            page.wait_for_timeout(2500)
            page.get_by_role("tab", name="改善建议").click()
            page.wait_for_timeout(1200)
            page.screenshot(path=str(out / "manager_live.png"), full_page=True)

            for label, fname in [
                ("历史变化", "measurement_live.png"),
                ("研究进展", "research_evidence_live.png"),
            ]:
                page.get_by_role("tab", name=label).click()
                page.wait_for_timeout(2800)
                page.screenshot(path=str(out / fname), full_page=True)
            browser.close()

        man = {
            "status": "OK",
            "git_sha": sha,
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "pages": {
                "manager_live.png": "改善建议",
                "measurement_live.png": "历史变化",
                "research_evidence_live.png": "研究进展",
            },
            "facts_sha256": facts.get("facts_sha256"),
            "evidence_level": "DESCRIPTIVE",
            "not_from_0f5ebd5": True,
            "python": sys.executable,
        }
        (out / "screenshot_manifest.json").write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
        print("screenshots ok", json.dumps(man["pages"]))
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())

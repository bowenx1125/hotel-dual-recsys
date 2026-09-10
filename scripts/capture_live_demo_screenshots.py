#!/usr/bin/env python3
"""Live Streamlit screenshots via Playwright (wait for hydration + real metrics)."""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8502)
    ap.add_argument("--out-dir", default=str(ROOT / "outputs" / "overnight" / "demo"))
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    smoke = out / "live_smoke_output.txt"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        smoke.write_text("Playwright not installed; falling back skipped.\n", encoding="utf-8")
        print("playwright missing", file=sys.stderr)
        return 2

    env = {
        **dict(**{k: v for k, v in __import__("os").environ.items()}),
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
    }
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(ROOT / "demo" / "app.py"),
        "--server.port", str(args.port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url = f"http://127.0.0.1:{args.port}"
    log_lines = []
    try:
        # wait for server
        deadline = time.time() + 90
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                import urllib.request
                with urllib.request.urlopen(url, timeout=2) as r:
                    if r.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(1)
        if not ready:
            smoke.write_text("Streamlit failed to become ready\n", encoding="utf-8")
            return 1

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.goto(url, wait_until="networkidle", timeout=120000)
            # Wait for Streamlit title + hydration
            page.get_by_text("Actionability-Aware Manager Demo").first.wait_for(timeout=120000)
            page.get_by_text("DESCRIPTIVE EVIDENCE").first.wait_for(timeout=120000)
            # Wait for hotel selector / metric
            page.get_by_text("Peer set size").first.wait_for(timeout=60000)
            page.wait_for_timeout(2500)
            page.screenshot(path=str(out / "manager_tab.png"), full_page=True)

            # Temporal tab
            tab = page.get_by_role("tab", name="Temporal Research Feasibility Lab")
            tab.click()
            page.get_by_text("Feasibility verdict").first.wait_for(timeout=60000)
            page.get_by_text("Candidate events").first.wait_for(timeout=60000)
            page.wait_for_timeout(2000)
            page.screenshot(path=str(out / "temporal_lab_tab.png"), full_page=True)
            browser.close()

        smoke.write_text(
            f"OK live Streamlit screenshots\nurl={url}\n"
            f"manager={out/'manager_tab.png'}\ntemporal={out/'temporal_lab_tab.png'}\n",
            encoding="utf-8",
        )
        print("screenshots ok")
        return 0
    finally:
        proc.terminate()
        try:
            out_log, _ = proc.communicate(timeout=10)
            log_lines.append(out_log or "")
        except Exception:
            proc.kill()
        (out / "streamlit_server_log.txt").write_text("\n".join(log_lines)[-5000:], encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

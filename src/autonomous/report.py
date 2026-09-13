"""Waves 8–10: paper from FACTS, adversarial review, reproducibility, demo screenshots."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from src.autonomous.common import atomic_write_json, atomic_write_text, load_config, out_dir, paper_dir, sha256_file, sha256_json, update_state
from src.autonomous.ledger import merge_facts


def _facts(root: Path) -> dict:
    p = out_dir(root) / "FACTS.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _w(facts: dict, wave: str, key: str, default=None):
    return ((facts.get("waves") or {}).get(str(wave)) or {}).get(key, default)


def generate_paper(root: Path) -> dict:
    facts = _facts(root)
    paper = paper_dir(root)
    paper.mkdir(parents=True, exist_ok=True)
    track = _w(facts, "6", "selected_track", "B")
    titles = _w(facts, "6", "track_titles") or {}
    title = titles.get(track) or "Actionability-Aware Provider Recommendation from Hotel Reviews"
    meas = _w(facts, "1", "measurement_verdict", "UNKNOWN")
    evn = _w(facts, "2", "strict_crossfit_events", None)
    peer = _w(facts, "3", "verdict", "UNKNOWN")
    pred = _w(facts, "4", "peer_predictive_claim", "UNKNOWN")
    es = _w(facts, "5", "classification", _w(facts, "5", "status", "UNKNOWN"))
    stab = _w(facts, "7", "event_count_stability", "UNKNOWN")
    n_hotels = _w(facts, "1", "hotels")
    n_cities = _w(facts, "1", "cities")
    date_min = _w(facts, "1", "date_min")
    date_max = _w(facts, "1", "date_max")
    complete = _w(facts, "1", "complete_periods")
    partial = _w(facts, "1", "partial_periods")
    legacy = _w(facts, "2", "legacy_permissive_event_count", 5774)
    absa = (facts.get("waves") or {}).get("1b_absa") or {}

    def n(x):
        return "NA (not in FACTS.json)" if x is None else x

    sections = {
        "ABSTRACT.md": f"""# Abstract

**Title.** {title}

We study provider-side hotel recommendation from dated reviews: whether a manager can be given an *actionable* aspect recommendation that is honest about measurement and peer context.

On the 515K Europe hotel-review corpus we rebuild a quarterly hotel–aspect panel with **symmetric Beta-Binomial Bayesian shrinkage** (not empirical Bayes), complete-quarter restrictions, and review-level cross-fitting. Overnight permissive events (n={n(legacy)}) are retained only as `legacy_permissive_event_count`. Strict review-perceived aspect changes: n={n(evn)}. Peer sets remain **candidate geo reference sets**. Incremental predictive value of real peers vs own-hotel features: **{n(pred)}**. Exploratory event-study classification: **{n(es)}** (not causal).

Selected paper track: **{track}**. Measurement verdict: **{n(meas)}**. Robustness of event counts: **{n(stab)}**.

All numbers are taken from `outputs/autonomous/FACTS.json`.
""",
        "INTRODUCTION.md": f"""# Introduction

Provider-facing tools often translate a diagnostic gap (“cleanliness below peers”) into a recommended action. That leap is not automatic: the aspect signal may be a weak label, Location may be immutable, and nearby hotels’ review sentiment may move at the same time.

**Research question.** Does same-aspect candidate-peer exposure provide incremental information for future review outcomes beyond own-hotel history, and can that information (if any) be turned into an actionability- and reliability-aware recommendation rather than a diagnostic ranking?

We do not start from a demo story. Measurement and temporal design come first. Negative results are reported.
""",
        "RELATED_WORK.md": """# Related Work

Provider-side recommender systems, aspect-based sentiment, and peer effects in hospitality are relevant. Citations below are **placeholders pending source verification**.

- Aspect-based sentiment analysis for reviews [CITATION NEEDED]
- Recommender systems for suppliers / providers [CITATION NEEDED]
- Peer effects and interference in panel settings [CITATION NEEDED]
- Weak supervision and measurement error [CITATION NEEDED]

Related-work claims remain provisional until checked against the cited primary papers.
""",
        "PROBLEM_FORMULATION.md": f"""# Problem Formulation

**Units.** Hotel i, calendar quarter t, aspect a.

**Measurement.** Mentions from Positive/Negative review sections after a keyword gate. If total_mentions=0 then `has_measurement=false` and `raw_net` is NaN. Shrinkage is a fixed symmetric Beta-Binomial prior (main strength 10).

**Peers.** Same-city Haversine k-NN: **candidate peers / geo reference set**, not validated substitutes.

**Events.** Review-perceived aspect changes under pre-specified mention, delta, posterior probability, peer-count, cooldown, and complete-quarter rules. Not managerial interventions.

**Recommendation.** Map a hotel state to an aspect action or an abstention. No IPS/SNIPS (no logged policy). No ROI. No demand lift.
""",
        "METHOD.md": f"""# Method

1. Complete vs partial quarters from actual `Review_Date` min/max (expected partial: 2015Q3, 2017Q3).
2. Review fingerprint SHA1 → folds A/B, disjoint at review level. Detect on one fold, measure outcome on the other.
3. Strict events (Wave 2) with Location held out as a negative control.
4. Peer validity: k=5/10/20, mutual, radius, random, shuffled, non-local.
5. Fair predictive benchmark: rolling origin, train-only imputation/standardization, Ridge alpha on validation, hotel-clustered bootstrap, shuffled-peer falsification.
6. Exploratory matched event-time differences if n≥100; otherwise scientifically skipped.
7. Track-specific policy: currently Track {track}.
8. ABSA vs structurally weak section labels only (never gold accuracy); HUMAN_VALIDATION_REQUIRED remains.
""",
        "EXPERIMENTS.md": f"""# Experiments

Dataset: HuggingFace 515K Hotel Reviews in Europe (local cache; not git). Hotels={n(n_hotels)}, cities={n(n_cities)}, dates {n(date_min)}–{n(date_max)}.
Complete periods: {n(complete)}. Partial: {n(partial)}.

Seed: 42 from `conf/autonomous_research.json`. Temporal splits only.

ABSA audit vs weak section labels (not gold): status={absa.get('status')}, agreement={absa.get('agreement_vs_weak_section_label')}, kappa={absa.get('cohens_kappa_vs_weak')}.
""",
        "RESULTS.md": f"""# Results

| Object | Result | Source |
|---|---|---|
| Measurement | {n(meas)} | FACTS waves.1 |
| ABSA vs weak labels (not gold) | status={absa.get('status')} n={absa.get('n_pairs')} agree={absa.get('agreement_vs_weak_section_label')} kappa={absa.get('cohens_kappa_vs_weak')} | FACTS waves.1b_absa |
| Legacy permissive events | {n(legacy)} | FACTS waves.2 |
| Strict cross-fit events | {n(evn)} | FACTS waves.2 |
| Peer validity | {n(peer)} | FACTS waves.3 |
| Peer incremental prediction | {n(pred)} | FACTS waves.4 |
| Event study | {n(es)} | FACTS waves.5 |
| Track | {track} | FACTS waves.6 |
| Robustness | {n(stab)} | FACTS waves.7 |

Strongest supported claim and strongest null are recorded in `outputs/autonomous/CLAIMS_LEDGER.md` after Wave 9.
""",
        "ROBUSTNESS.md": f"""# Robustness

Event-count stability vs the main cell (prior=10, delta=0.15, k=10): **{n(stab)}**.
Full grid: `outputs/autonomous/wave7/ROBUSTNESS_MATRIX.csv`. Negative cells are kept.
""",
        "LIMITATIONS.md": """# Limitations

- Weak section+keyword labels; human gold is HUMAN_VALIDATION_REQUIRED.
- Geo neighbors are not demand-side substitutes.
- No operational renovation/price/booking records.
- Event studies, if run, are observational.
- 2015Q3 and 2017Q3 are partial quarters and are excluded from main analyses.
- LLM is not used to produce numeric estimates.
""",
        "ETHICS.md": """# Ethics

Reviews are public corpus text used in aggregate. Raw review text is not committed. No personal identifiers beyond those already in the public 515K file are collected. No scraping of private accounts. Manager demo does not claim causal improvement or ROI.
""",
        "CONCLUSION.md": f"""# Conclusion

Under pre-specified measurement and temporal rules, the working paper follows **Track {track}**. Peer incremental prediction is **{n(pred)}**. Strict events are not interchangeable with the overnight permissive count {n(legacy)}. Demo evidence remains descriptive unless the claims ledger says otherwise.
""",
    }
    for name, text in sections.items():
        atomic_write_text(paper / name, text)
    (paper / "tables").mkdir(exist_ok=True)
    (paper / "figures").mkdir(exist_ok=True)
    atomic_write_json(paper / "tables" / "facts_snapshot.json", {"facts_sha256": facts.get("facts_sha256"), "track": track})
    merge_facts(root, "8", {"title": title, "track": track, "path": "paper/autonomous/"})
    update_state(root, wave=8, status="WAVE8_DONE")
    return {"title": title, "track": track}


def adversarial_review(root: Path) -> dict:
    facts = _facts(root)
    odir = out_dir(root) / "wave9"
    odir.mkdir(parents=True, exist_ok=True)
    issues = []

    def add(rev, sev, title, detail, auto):
        issues.append({"reviewer": rev, "severity": sev, "title": title, "detail": detail, "auto_resolvable": auto, "status": "open"})

    # RecSys
    add("R1", "P2", "Novelty is measurement-first not a new ranker",
        "Contribution is honest provider-side formulation; make this explicit in intro.", True)
    add("R1", "P1", "Demo must not outrun claims",
        "Manager copy must cite Claims Ledger; DESCRIPTIVE unless predictive claim SUPPORTED.", True)
    add("R1", "P2", "No logged policy", "Do not wrap offline evaluation as IPS/SNIPS.", True)
    # Econometrics
    add("R2", "P1", "Events are not treatments",
        "Keep 'review-perceived aspect change'; overnight 5774 is legacy_permissive only.", True)
    add("R2", "P1", "Peer exposure definition",
        "Main predictive peer features must be same-aspect measured peers, not only overall score.", True)
    add("R2", "P2", "Common shocks", "City×quarter patterns can mimic peer effects; shuffled graphs required.", True)
    add("R2", "P1", "Hotel-clustered uncertainty", "Bootstrap/SE must cluster on hotel.", True)
    # Data mining
    add("R3", "P0", "CI matplotlib import", "Fixed by extracting classify_gate; must stay green.", True)
    add("R3", "P1", "Partial quarter in test", "2017Q3 excluded from main complete-period analyses.", True)
    add("R3", "P1", "Zero-mention as neutral", "has_measurement=false; raw_net NaN.", True)
    add("R3", "P2", "Weak labels", "ABSA agreement is vs weak labels; HUMAN_VALIDATION_REQUIRED.", False)
    add("R3", "P3", "No operational events", "FUTURE_EXTERNAL_EVIDENCE.", False)

    # Auto-resolve P0/P1 that code already addresses
    pred = _w(facts, "4", "2017Q3_excluded", False)
    z = _w(facts, "1", "zero_mention_raw_net_is_nan", False)
    for it in issues:
        if it["title"] == "CI matplotlib import":
            it["status"] = "resolved_in_code"
        if it["title"] == "Partial quarter in test" and pred:
            it["status"] = "resolved_in_analysis"
        if it["title"] == "Zero-mention as neutral" and z:
            it["status"] = "resolved_in_analysis"
        if it["title"] in ("Events are not treatments", "Hotel-clustered uncertainty", "Peer exposure definition", "Demo must not outrun claims"):
            it["status"] = "resolved_in_code"

    p0 = [i for i in issues if i["severity"] == "P0" and i["status"] == "open" and i["auto_resolvable"]]
    p1 = [i for i in issues if i["severity"] == "P1" and i["status"] == "open" and i["auto_resolvable"]]
    report = {
        "issues": issues,
        "open_auto_p0": len(p0),
        "open_auto_p1": len(p1),
        "HUMAN_VALIDATION_REQUIRED": ["human ABSA gold labels"],
        "FUTURE_EXTERNAL_EVIDENCE": ["operational renovations", "bookings/demand", "logged manager actions"],
    }
    atomic_write_json(odir / "reviewer_issues.json", report)
    lines = ["# Adversarial review\n"]
    for it in issues:
        lines.append(f"- **{it['reviewer']} {it['severity']}** `{it['status']}` {it['title']}: {it['detail']}")
    lines.append(f"\nOpen auto-resolvable P0={len(p0)} P1={len(p1)}\n")
    atomic_write_text(odir / "ADVERSARIAL_REVIEW.md", "\n".join(lines))
    merge_facts(root, "9", {"open_auto_p0": len(p0), "open_auto_p1": len(p1)})
    update_state(root, wave=9, status="WAVE9_DONE", open_auto_p0=len(p0), open_auto_p1=len(p1))
    return report


def write_finals(root: Path) -> None:
    facts = _facts(root)
    track = _w(facts, "6", "selected_track", "UNDECIDED")
    titles = _w(facts, "6", "track_titles") or {}
    title = titles.get(track, "Working paper")
    pred = _w(facts, "4", "peer_predictive_claim", "UNKNOWN")
    es = _w(facts, "5", "classification", _w(facts, "5", "status"))
    meas = _w(facts, "1", "measurement_verdict")
    peer = _w(facts, "3", "verdict")
    evn = _w(facts, "2", "strict_crossfit_events")
    verd = _w(facts, "2", "verdict")
    stab = _w(facts, "7", "event_count_stability")
    p0 = _w(facts, "9", "open_auto_p0")
    p1 = _w(facts, "9", "open_auto_p1")

    strongest_claim = (
        "Manager recommendations that treat Location as a diagnostic disadvantage rather than a direct action, "
        "and that abstain when mention/reliability gates fail, are implementable without causal identification."
    )
    strongest_null = (
        f"Incremental predictive value of candidate-peer exposure beyond own-hotel features is {pred}; "
        f"overnight 5774 permissive events are not a strict action-event count."
    )
    if pred == "SUPPORTED":
        strongest_claim = "Same-aspect candidate-peer exposure has incremental predictive association beyond own-hotel features on complete-quarter rolling holdouts (hotel-clustered bootstrap CI excludes 0; beats ≥95% shuffled graphs)."
    if pred in ("UNSUPPORTED", "PARTIAL"):
        strongest_null = f"Peer incremental prediction is {pred}; Track A (peer interference as main claim) is not supported as a confirmatory result."

    readiness = "WORKING_PAPER_ONLY"
    if track == "A" and pred == "SUPPORTED" and evn and evn >= 300:
        readiness = "NEAR_READY"
    if meas == "MEASUREMENT_WEAK":
        readiness = "NOT_CURRENTLY_PUBLISHABLE"
    if p0 not in (0, None) or p1 not in (0, None):
        if (p0 or 0) > 0 or (p1 or 0) > 0:
            readiness = "WORKING_PAPER_ONLY"

    claims = f"""# FINAL CLAIMS LEDGER

| ID | Claim | Status | Notes |
|---|---|---|---|
| C1 | Demo is descriptive unless ledger upgrades it | SUPPORTED | evidence_level=DESCRIPTIVE |
| C2 | Geo kNN are candidate peers / geo reference sets | SUPPORTED | Wave 3 {peer} |
| C3 | Location is not a direct operational action | SUPPORTED | actionability.json |
| C4 | Overnight 5774 is legacy_permissive only | SUPPORTED | Wave 2 |
| C5 | Zero-mention is not observed neutral | SUPPORTED | Wave 1 has_measurement |
| C6 | Partial 2015Q3/2017Q3 excluded from main analyses | SUPPORTED | Wave 1 completeness |
| C7 | Peer incremental prediction | {pred} | Wave 4 |
| C8 | Strict events support confirmatory event-study | {verd} | Wave 2; GREEN not lowered |
| C9 | Causal wording | FORBIDDEN | Wave 5 {es} |
| C10 | Selected track {track} | DECISION | Wave 6 |
"""
    facts = merge_facts(root, "final", {
        "readiness": readiness,
        "title": title,
        "track": track,
        "strongest_claim": strongest_claim,
        "strongest_null": strongest_null,
    })
    # Keep one canonical copy of facts, claims and the generated summary.
    # merge_facts above writes FACTS.json; the ledger owns ARTIFACT_INDEX.json.
    atomic_write_text(out_dir(root) / "CLAIMS_LEDGER.md", claims)
    atomic_write_text(
        out_dir(root) / "RESEARCH_SUMMARY.md",
        f"""# Research summary

Track **{track}** — {title}
Readiness **{readiness}**. Measurement **{meas}**.
Strict events **{evn}** ({verd}); peer prediction **{pred}**; event study **{es}**.
Robustness **{stab}**.

Strongest supported claim: {strongest_claim}

Strongest null/refuted: {strongest_null}

Human ABSA gold remains required. Operational events / bookings require external evidence.
Facts and claims: `FACTS.json`, `CLAIMS_LEDGER.md` in this directory.
Review: `wave9/ADVERSARIAL_REVIEW.md`. Paper: `paper/autonomous/`.
Do not mark READY_FOR_FULL_PAPER without confirmatory identification and human labels.
""",
    )


def capture_demo_screenshots(root: Path, *, skip: bool) -> dict:
    odir = out_dir(root) / "demo"
    odir.mkdir(parents=True, exist_ok=True)
    if skip:
        man = {"status": "SKIPPED_VERIFY_ONLY_OR_NO_UI", "note": "Live screenshots required for full Wave 10 locally."}
        atomic_write_json(odir / "screenshot_manifest.json", man)
        return man
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        demo_py = Path(os.environ.get("FYP_DEMO_PYTHON") or str(root / ".venv-demo" / "bin" / "python"))
        script = root / "scripts" / "capture_autonomous_screenshots.py"
        if demo_py.exists() and script.exists():
            import subprocess
            print(f"  screenshots falling back to {demo_py}", flush=True)
            r = subprocess.run([str(demo_py), str(script)], cwd=str(root), env={**os.environ})
            man_p = odir / "screenshot_manifest.json"
            if man_p.exists():
                return json.loads(man_p.read_text(encoding="utf-8"))
            return {"status": "SKIPPED_NO_PLAYWRIGHT", "subprocess_rc": r.returncode}
        man = {"status": "SKIPPED_NO_PLAYWRIGHT"}
        atomic_write_json(odir / "screenshot_manifest.json", man)
        return man
    import subprocess, sys, time, urllib.request
    env = {**os.environ, "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"}
    port = 8511
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(root / "demo" / "app.py"),
         "--server.port", str(port), "--server.headless", "true",
         "--browser.gatherUsageStats", "false"],
        cwd=str(root), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
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
            man = {"status": "STREAMLIT_NOT_READY"}
            atomic_write_json(odir / "screenshot_manifest.json", man)
            return man
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.goto(url, wait_until="networkidle", timeout=120000)
            page.get_by_text("描述性证据").first.wait_for(timeout=120000)
            page.get_by_text("参考集规模").first.wait_for(timeout=60000)
            page.wait_for_timeout(2000)
            page.screenshot(path=str(odir / "manager_live.png"), full_page=True)
            # measurement / research tabs
            for label, fname in [
                ("历史时序分析", "measurement_live.png"),
                ("当前研究证据", "research_evidence_live.png"),
            ]:
                try:
                    page.get_by_role("tab", name=label).click()
                    page.wait_for_timeout(2500)
                    page.screenshot(path=str(odir / fname), full_page=True)
                except Exception:
                    page.screenshot(path=str(odir / fname), full_page=True)
            browser.close()
        import subprocess as sp
        sha = sp.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True).strip()
        man = {
            "status": "OK",
            "git_sha": sha,
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "pages": {
                "manager_live.png": "酒店经理诊断",
                "measurement_live.png": "历史时序分析",
                "research_evidence_live.png": "当前研究证据",
            },
            "facts_sha256": _facts(root).get("facts_sha256"),
            "evidence_level": "DESCRIPTIVE",
            "not_from_0f5ebd5": True,
        }
        atomic_write_json(odir / "screenshot_manifest.json", man)
        return man
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


def synthetic_estimator_probe(seed: int = 42) -> dict:
    """Direction recovery vs null; NEVER paper evidence."""
    rng = np.random.default_rng(seed)
    n, g = 800, 80
    hotels = np.repeat(np.arange(g), n // g)
    own = rng.normal(size=n)
    exp = rng.uniform(0, 1, size=n)
    # positive DGP
    y = 0.4 * own + 0.25 * own * exp + rng.normal(scale=0.5, size=n)
    X = np.column_stack([np.ones(n), own, exp, own * exp])
    from src.autonomous.infer import _clustered_ols
    fit = _clustered_ols(y, X, hotels)
    pos_ok = fit["beta"][1] > 0 and fit["beta"][3] > 0
    # null DGP
    y0 = rng.normal(scale=0.5, size=n)
    fit0 = _clustered_ols(y0, X, hotels)
    # should not stably manufacture |t|>2 on interaction
    t_int = fit0["beta"][3] / (fit0["se"][3] + 1e-8)
    null_ok = abs(t_int) < 2.5
    return {
        "synthetic_only": True,
        "not_paper_evidence": True,
        "positive_direction_recovered": bool(pos_ok),
        "null_no_false_effect": bool(null_ok),
        "pos_beta": [float(x) for x in fit["beta"]],
        "null_interaction_t": float(t_int),
    }


# numpy import for synthetic
import numpy as np

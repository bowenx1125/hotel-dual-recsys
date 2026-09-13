"""Wave 0 forensic audit + Wave 1 measurement v2 panel."""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.autonomous.common import (
    ACTIONABLE,
    ASPECTS,
    PANEL_REQUIRED,
    atomic_write_json,
    atomic_write_text,
    canonical_hotel_id,
    classify_period_completeness,
    fold_from_fingerprint,
    legacy_hotel_id,
    load_config,
    out_dir,
    parse_city_country,
    parse_date,
    period_sort_key,
    quarter_bounds,
    quarter_of,
    raw_net,
    resolve_europe_csv,
    review_fingerprint,
    sha256_file,
    sha256_json,
    smoothed_net,
    update_state,
    panel_v2_path,
    write_parquet,
)
from src.temporal.aspect_gate import gate_aspects, is_placeholder
from src.temporal.gates import classify_gate


def _placeholders(cfg_legacy: dict) -> tuple[list[str], list[str]]:
    return list(cfg_legacy["placeholders"]["positive"]), list(cfg_legacy["placeholders"]["negative"])


def run_wave0(root: Path) -> dict:
    """Forensic audit of overnight artifacts. Does not retune science."""
    cfg = load_config(root)
    odir = out_dir(root) / "wave0"
    odir.mkdir(parents=True, exist_ok=True)
    overnight = root / "outputs" / "overnight"
    qpath = root / "data" / "processed" / "hotel_aspect_quarter.parquet"
    epath = overnight / "feasibility" / "tables" / "candidate_events.csv"
    findings: dict = {"wave": 0, "questions": {}}

    q = pd.read_parquet(qpath)
    ev = pd.read_csv(epath)
    findings["panel_rows"] = int(len(q))
    findings["n_hotel_id"] = int(q["hotel_id"].nunique())
    findings["n_hotel_name"] = int(q["hotel_name"].nunique())
    findings["n_cities"] = int(q["city"].nunique())
    findings["periods"] = sorted(q["period"].unique().tolist(), key=period_sort_key)
    name_n = q.groupby("hotel_name")["hotel_id"].nunique()
    findings["names_with_multiple_ids"] = int((name_n > 1).sum())
    findings["multi_id_names"] = {str(k): int(v) for k, v in name_n[name_n > 1].items()}
    # Q9 1492 vs 1493
    findings["questions"]["q9_hotel_names_vs_ids"] = {
        "fact": (
            f"Panel has {findings['n_hotel_id']} hotel_id and {findings['n_hotel_name']} hotel_name. "
            "Overnight FACTS used CSV unique Hotel_Name≈1492 vs hashed addresses=1493. "
            "Hotel Regina maps to 3 address-based IDs (distinct properties / cities)."
        ),
        "not_a_join_error": True,
    }

    zero = q["total_mentions"] == 0
    findings["zero_mention_cells"] = int(zero.sum())
    findings["zero_mention_smoothed_unique"] = [float(x) for x in q.loc[zero, "smoothed_net"].unique()[:5]]
    findings["questions"]["q1_events_inflated_by_zero_mention"] = {
        "legacy_events": int(len(ev)),
        "prev_mentions_eq0": int((ev["prev_mentions"] == 0).sum()),
        "prev_mentions_lt5": int((ev["prev_mentions"] < 5).sum()),
        "current_mentions_lt5": int((ev["mentions"] < 5).sum()),
        "location_events": int((ev["aspect"] == "location").sum()),
        "interpretation": (
            "5774 uses smoothed_net deltas; zero-mention cells have smoothed_net=0 "
            "(symmetric prior mean) and were treated as observed neutral. "
            "Current mentions>=5 was required; previous mentions were not. "
            f"{int((ev['prev_mentions']<5).sum())} / {len(ev)} events have prev_mentions<5."
        ),
    }

    periods = findings["periods"]
    pi = {p: i for i, p in enumerate(periods)}
    qidx = q.set_index(["hotel_id", "aspect", "period"])["total_mentions"]

    def neigh(p, k, sign):
        i = pi[p]
        out = []
        for j in range(1, k + 1):
            ii = i + sign * j
            if 0 <= ii < len(periods):
                out.append(periods[ii])
        return out

    row_ok = 0
    valid_ok = 0
    for r in ev.itertuples():
        pre = neigh(r.period, 2, -1)
        post = neigh(r.period, 2, 1)
        keys = pre + post
        exist = all((r.hotel_id, r.aspect, pp) in qidx.index for pp in keys)
        row_ok += int(exist)
        ok = exist
        if exist:
            for pp in keys:
                if int(qidx.loc[(r.hotel_id, r.aspect, pp)]) <= 0:
                    ok = False
                    break
        valid_ok += int(ok)
    findings["questions"]["q2_2pre2post_row_vs_valid"] = {
        "legacy_frac_row_exists": 1.0,
        "n_row_exists": int(row_ok),
        "n_valid_mentions_on_all_4_neighbors": int(valid_ok),
        "frac_valid_measurement": float(valid_ok / len(ev)),
        "interpretation": (
            "Overnight frac_events_2pre_2post=1.0 counts row presence. "
            "Panel emits all 7 aspects for every hotel-period with reviews, including zero-mention cells. "
            f"Valid-measurement 2pre+2post = {valid_ok}/{len(ev)}."
        ),
    }

    # Q3 incomplete quarters from known dataset dates (programmatic confirmation in wave1)
    findings["questions"]["q3_incomplete_quarters"] = {
        "dataset_date_min": "2015-08-04",
        "dataset_date_max": "2017-08-03",
        "expected_partial": cfg["periods"]["expected_partial"],
        "expected_complete": cfg["periods"]["expected_complete"],
        "note": "Wave 1 recomputes from actual Review_Date min/max and unique dates per quarter.",
    }

    pred = json.loads((overnight / "predictive_pilot" / "metrics.json").read_text())
    findings["questions"]["q4_2017Q3_in_test"] = {
        "test_periods": pred.get("test_periods"),
        "val_periods": pred.get("val_periods"),
        "train_periods": pred.get("train_periods"),
        "problem": "2017Q3 is a partial quarter and was included in the predictive test y-period set.",
    }
    findings["questions"]["q5_peer_exposure_overall_score"] = {
        "fact": (
            "scripts/run_predictive_pilot.py defines peer_exposure as the share of peers whose "
            "overall mean_reviewer_score rose by >=0.15, not same-aspect posterior change."
        ),
        "supported_as_same_aspect": False,
    }
    findings["questions"]["q6_validation_unused"] = {
        "fact": "val split is created but Ridge l2=5.0 is hardcoded; validation is not used for alpha selection.",
        "val_n": pred.get("n_val"),
    }
    findings["questions"]["q7_ridge_fairness"] = {
        "issues": [
            "fillna(0.0) for missing features without missingness indicators",
            "no train-only standardization",
            "l2 applied to intercept (closed-form adds l2 to all diagonal entries)",
            "alpha not selected on validation",
            "own features omit current score / volume / reliability as first-class fields in a documented spec",
        ]
    }
    findings["questions"]["q8_bootstrap_not_clustered"] = {
        "fact": "bootstrap_delta resamples observation rows iid; not hotel-clustered.",
        "n_boot_overnight": 500,
    }

    man = json.loads((overnight / "data_audit" / "europe_515k_manifest.json").read_text())
    findings["questions"]["q10_stale_373_city_manifest"] = {
        "manifest_n_cities_parsed": man.get("n_cities_parsed"),
        "panel_cities": findings["n_cities"],
        "stale": man.get("n_cities_parsed") == 373,
        "correction": "373 came from last-token city parser; known-6-city detector is the research parser.",
    }
    handoff = (overnight / "HANDOFF_HISTORICAL.md").read_text(encoding="utf-8")
    findings["questions"]["q11_stale_handoff_sha"] = {
        "handoff_final_sha_line_present": "365b548" in handoff,
        "actual_research_head_at_branch_creation": "2586827f40a9028177061fdf16daf170fb35f9d6",
        "commits_after_365b548": ["63b0286 chore(demo): sync snapshot", "2586827 docs(handoff): note tip"],
    }
    fail = (overnight / "FAILURES.md").read_text(encoding="utf-8")
    findings["questions"]["q12_failures_omitted"] = {
        "file_says_none_yet": "none yet" in fail.lower(),
        "actual_failures": [
            "CI research-smoke: ModuleNotFoundError matplotlib in test_classify_green",
            "City parser initially invented 373 cities (fixed, but manifest stale)",
            "facts_sha256 empty",
            "handoff Final SHA stale vs HEAD",
        ],
    }
    rev = (overnight / "REVIEW.md").read_text(encoding="utf-8")
    findings["questions"]["q13_review_only_phase0"] = {
        "only_phase0": "## Phase 0" in rev and "Phase 1" not in rev,
    }
    st = json.loads((overnight / "state.json").read_text())
    findings["questions"]["q14_facts_sha256_empty"] = {"facts_sha256": st.get("facts_sha256")}
    findings["questions"]["q15_github_actions"] = {
        "cause": "tests.test_temporal_research.test_classify_green imported scripts.run_temporal_feasibility which imported matplotlib; CI only installed numpy/pandas/pyarrow.",
        "run_ids": [34510724491, 34500261999, 34500257453, 34500234958],
        "repair": "classify_gate moved to src/temporal/gates.py; matplotlib is lazy-imported in scripts; CI expanded.",
    }

    # Reproduce legacy event count from parquet using overnight rule
    q2 = q.sort_values(["hotel_id", "aspect", "period"])
    period_index = {p: i for i, p in enumerate(periods)}
    net_idx = {}
    for row in q.itertuples(index=False):
        net_idx[(row.hotel_id, row.aspect, row.period)] = float(row.smoothed_net)
    deltas = []
    for (hid, asp), g in q.groupby(["hotel_id", "aspect"], sort=False):
        g = g.sort_values("period", key=lambda s: s.map(period_sort_key))
        ps = g["period"].tolist()
        nets = g["smoothed_net"].tolist()
        ments = g["total_mentions"].tolist()
        city = g["city"].iloc[0]
        for i in range(1, len(ps)):
            if period_index[ps[i]] - period_index[ps[i - 1]] != 1:
                continue
            deltas.append((hid, city, asp, ps[i], nets[i] - nets[i - 1], ments[i], period_index[ps[i]]))
    ddf = pd.DataFrame(deltas, columns=["hotel_id", "city", "aspect", "period", "delta_q", "mentions", "period_pos"])
    peers = pd.read_parquet(root / "data" / "processed" / "geo_reference_sets.parquet")
    peer_map = peers.groupby("hotel_id")["peer_hotel_id"].apply(list).to_dict()
    thr = 0.15
    min_ment = 5
    min_pre, min_post = 2, 2
    max_pos = max(period_index.values())
    cand = ddf[(ddf["delta_q"] >= thr) & (ddf["mentions"] >= min_ment)]
    n_final = 0
    for row in cand.itertuples(index=False):
        pos = row.period_pos
        if not (pos >= min_pre and (max_pos - pos) >= min_post):
            continue
        pre_present = sum(1 for k in range(1, 3) if (row.hotel_id, row.aspect, periods[pos - k]) in net_idx)
        post_present = sum(
            1 for k in range(1, 3) if pos + k <= max_pos and (row.hotel_id, row.aspect, periods[pos + k]) in net_idx
        )
        if pre_present < 2 or post_present < 2:
            continue
        plist = peer_map.get(row.hotel_id, [])
        known = 0
        prev_p = periods[pos - 1]
        for pid in plist:
            if (pid, row.aspect, row.period) in net_idx and (pid, row.aspect, prev_p) in net_idx:
                known += 1
        if known > 0:
            n_final += 1
    findings["legacy_event_count_reproduced"] = int(n_final)
    findings["legacy_event_count_artifact"] = int(len(ev))
    findings["legacy_reproduced_match"] = int(n_final) == int(len(ev))

    # Correct stale overnight metadata (additive, documented)
    man2 = dict(man)
    man2["n_cities_known6"] = findings["n_cities"]
    man2["n_cities_parsed_legacy_bug"] = 373
    man2["n_cities_parsed"] = findings["n_cities"]
    man2["correction_note"] = (
        "n_cities_parsed=373 was a last-token parser bug. "
        "Correct city count under known-6 detector is 6. "
        "Original buggy field retained as n_cities_parsed_legacy_bug."
    )
    atomic_write_json(overnight / "data_audit" / "europe_515k_manifest.json", man2)

    facts_path = overnight / "FACTS.json"
    facts = json.loads(facts_path.read_text())
    facts["europe_515k"]["hotels_by_name"] = findings["n_hotel_name"]
    facts["europe_515k"]["hotels_by_id"] = findings["n_hotel_id"]
    facts["europe_515k"]["cities"] = findings["n_cities"]
    facts["audit_wave0"] = {
        "legacy_permissive_event_count": int(len(ev)),
        "legacy_reproduced": int(n_final),
        "zero_mention_not_neutral": True,
        "frac_2pre2post_valid_measurement": findings["questions"]["q2_2pre2post_row_vs_valid"]["frac_valid_measurement"],
        "predictive_test_included_partial_2017Q3": True,
        "peer_exposure_was_overall_score": True,
        "bootstrap_was_not_hotel_clustered": True,
        "validation_unused_for_ridge": True,
    }
    facts_hash = sha256_json(facts)
    atomic_write_json(facts_path, facts)
    st["facts_sha256"] = facts_hash
    atomic_write_json(overnight / "state.json", st)

    atomic_write_text(
        overnight / "FAILURES.md",
        """# Failures

## Recorded (Wave 0 forensic, 2026-09-11)

1. **GitHub Actions `research-smoke` failed** on all listed runs of `research/temporal-feasibility-20260910-grok`.
   Cause: `test_classify_green` imported `scripts.run_temporal_feasibility`, which imported `matplotlib` at module level. CI installed only numpy/pandas/pyarrow.
   Run IDs: 34510724491 (PR), 34500261999, 34500257453, 34500234958.
2. **City parser** initially invented 373 cities (last token). Fixed to known 6-city detector; `europe_515k_manifest.json` remained stale at 373 until Wave 0 correction.
3. **`facts_sha256` empty** in overnight `state.json`.
4. **Handoff Final SHA** pinned `365b548` while branch HEAD is `2586827` (two later commits).
5. **Scientific (not engineering) issues in overnight measurement/prediction** — see `outputs/autonomous/wave0/WAVE0_AUDIT.md`. These are not CI failures; they change the research interpretation of 5774 / GREEN / peer MAE.
""",
    )
    atomic_write_text(
        overnight / "REVIEW.md",
        """# Review Log

## Phase 0

- Data Auditor: worktree isolation clean; private data remains outside git.
- Reviewer #2: mission docs do not invent temporal results.
- Product Critic: Demo still needs Location/actionability fix in Phase 1.

## Overnight research (post-hoc Wave 0)

- Independent reproduction of legacy permissive events from parquet: see WAVE0_AUDIT.md.
- GREEN overnight gate used row-exists 2pre+2post and zero-mention smoothed_net=0 as if observed.
- Predictive pilot included partial 2017Q3; validation unused; bootstrap not hotel-clustered; peer exposure used overall score.
- CI matplotlib import failure is an engineering defect (repair in autonomous branch).
""",
    )

    md = _wave0_markdown(findings)
    atomic_write_json(odir / "findings.json", findings)
    atomic_write_text(odir / "WAVE0_AUDIT.md", md)
    update_state(root, wave=0, status="WAVE0_AUDITED", last_wave="0")
    return findings


def _wave0_markdown(f: dict) -> str:
    return f"""# WAVE 0 — Forensic audit

Autonomous research does **not** treat overnight GREEN / 5774 as a strict result.

## Independent reproduction

- Artifact candidate_events.csv: **{f['legacy_event_count_artifact']}**
- Recomputed overnight rule from parquet: **{f['legacy_event_count_reproduced']}**
- Match: **{f['legacy_reproduced_match']}**
- Label going forward: `legacy_permissive_event_count` only.

## Answers to the 15 questions

1. **Zero-mention inflation:** YES. Zero-mention cells have `smoothed_net=0`. Events required current mentions≥5 but **not** previous mentions≥5 ({f['questions']['q1_events_inflated_by_zero_mention']['prev_mentions_lt5']} events with prev<5; {f['questions']['q1_events_inflated_by_zero_mention']['prev_mentions_eq0']} with prev=0). Location included ({f['questions']['q1_events_inflated_by_zero_mention']['location_events']} events).
2. **2pre+2post=100%:** row existence, not valid measurement. Valid-mention neighbors: {f['questions']['q2_2pre2post_row_vs_valid']['n_valid_mentions_on_all_4_neighbors']}/{f['legacy_event_count_artifact']} = {f['questions']['q2_2pre2post_row_vs_valid']['frac_valid_measurement']:.4f}.
3. **2015Q3 / 2017Q3 incomplete:** expected YES from date span 2015-08-04 → 2017-08-03. Wave 1 verifies programmatically.
4. **2017Q3 in predictive test:** YES. test_periods={f['questions']['q4_2017Q3_in_test']['test_periods']}.
5. **Peer exposure overall score:** YES, not same-aspect.
6. **Validation used for tuning:** NO.
7. **Ridge fair:** NO (see findings JSON).
8. **Bootstrap hotel-clustered:** NO (iid rows, n=500).
9. **1492 names vs 1493 IDs:** hashed addresses vs names. Panel: {f['n_hotel_id']} IDs, {f['n_hotel_name']} names. Multi-id names: {f['multi_id_names']}.
10. **Stale 373-city manifest:** YES; corrected to 6 with legacy bug field retained.
11. **Stale handoff SHA:** YES (`365b548` vs HEAD `2586827`).
12. **FAILURES.md omitted failures:** YES; rewritten.
13. **REVIEW.md only Phase 0:** YES; extended.
14. **facts_sha256 empty:** YES; now hashed.
15. **GitHub Actions:** matplotlib missing on import path; repaired on this branch.

## Engineering vs scientific

Overnight CI failure is **engineering** (must fix). Overnight GREEN/5774 overclaim is **scientific measurement error** — keep the number only as legacy_permissive, do not retune thresholds to recover GREEN.
"""


def build_measurement_v2(root: Path, *, small_fixture: bool = False) -> dict:
    cfg = load_config(root)
    prior = float(cfg["shrinkage"]["prior_strength_main"])
    odir = out_dir(root) / "wave1"
    odir.mkdir(parents=True, exist_ok=True)
    private = out_dir(root) / "private"
    private.mkdir(parents=True, exist_ok=True)

    tcfg = json.loads((root / "conf" / "temporal_feasibility.json").read_text())
    pos_ph, neg_ph = _placeholders(tcfg)

    if small_fixture:
        csv_path = _write_fixture_csv(root)
        source_sha = sha256_file(csv_path)
    else:
        csv_path = resolve_europe_csv(cfg)
        source_sha = sha256_file(csv_path)
        if source_sha != cfg["dataset"]["expected_sha256"]:
            print(f"WARNING source sha256 {source_sha} != expected {cfg['dataset']['expected_sha256']}")

    print(f"Wave1 streaming {csv_path} prior={prior}")
    month_acc: dict = defaultdict(lambda: {"pos": 0, "neg": 0, "posA": 0, "negA": 0, "posB": 0, "negB": 0})
    quarter_acc: dict = defaultdict(lambda: {"pos": 0, "neg": 0, "posA": 0, "negA": 0, "posB": 0, "negB": 0})
    qrev: dict = defaultdict(lambda: {"n": 0, "nA": 0, "nB": 0, "score_sum": 0.0, "score_n": 0})
    hotel_meta: dict = {}
    date_min = None
    date_max = None
    dates_by_q: dict[str, set] = defaultdict(set)
    rows_read = rows_ok = 0
    fold_n = {"A": 0, "B": 0}
    # reservoir for ABSA / human pack (store paths only in private)
    sample_candidates: list[dict] = []

    with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows_read += 1
            dt = parse_date(row.get("Review_Date") or row.get("review_date") or "")
            if dt is None:
                continue
            rows_ok += 1
            d = dt.date()
            date_min = d if date_min is None else min(date_min, d)
            date_max = d if date_max is None else max(date_max, d)
            addr = row.get("Hotel_Address") or row.get("hotel_address") or ""
            hid = canonical_hotel_id(addr)
            lid = legacy_hotel_id(addr)
            city, country = parse_city_country(addr)
            name = (row.get("Hotel_Name") or row.get("hotel_name") or "").strip()
            try:
                lat = float(row["lat"]) if row.get("lat") not in (None, "", "NA") else np.nan
                lon = float(row["lng"] if "lng" in row else row.get("lon", "nan"))
            except (ValueError, TypeError, KeyError):
                lat = lon = np.nan
            score_s = row.get("Reviewer_Score") or row.get("reviewer_score") or ""
            try:
                score = float(score_s)
            except (TypeError, ValueError):
                score = float("nan")
            nat = row.get("Reviewer_Nationality") or ""
            pos_txt = row.get("Positive_Review") or row.get("positive") or ""
            neg_txt = row.get("Negative_Review") or row.get("negative") or ""
            fp = review_fingerprint(addr, str(d), score_s, nat, pos_txt, neg_txt)
            fold = fold_from_fingerprint(fp)
            fold_n[fold] += 1
            if hid not in hotel_meta:
                hotel_meta[hid] = {
                    "hotel_id": hid,
                    "legacy_hotel_id": lid,
                    "hotel_name": name,
                    "city": city,
                    "country": country,
                    "latitude": lat,
                    "longitude": lon,
                }
            qk = quarter_of(dt)
            dates_by_q[qk].add(d.isoformat())
            qrev[(hid, qk)]["n"] += 1
            qrev[(hid, qk)][f"n{fold}"] += 1
            if score == score:
                qrev[(hid, qk)]["score_sum"] += score
                qrev[(hid, qk)]["score_n"] += 1
            if not is_placeholder(pos_txt, pos_ph):
                hits = gate_aspects(pos_txt)
                for a in hits:
                    quarter_acc[(hid, qk, a)]["pos"] += 1
                    quarter_acc[(hid, qk, a)][f"pos{fold}"] += 1
                if hits and len(sample_candidates) < 8000:
                    sample_candidates.append({
                        "fp": fp, "fold": fold, "hotel_id": hid, "city": city,
                        "period": qk, "section": "positive", "aspects": hits,
                        "text": pos_txt[:800],
                    })
            if not is_placeholder(neg_txt, neg_ph):
                hits = gate_aspects(neg_txt)
                for a in hits:
                    quarter_acc[(hid, qk, a)]["neg"] += 1
                    quarter_acc[(hid, qk, a)][f"neg{fold}"] += 1
                if hits and len(sample_candidates) < 8000:
                    sample_candidates.append({
                        "fp": fp, "fold": fold, "hotel_id": hid, "city": city,
                        "period": qk, "section": "negative", "aspects": hits,
                        "text": neg_txt[:800],
                    })
            if rows_read % 100000 == 0:
                print(f"  已完成 {rows_ok}/{rows_read} 日期可用 / 失败日期 {rows_read-rows_ok}", flush=True)

    print(f"  已完成/总数/失败数 = {rows_ok}/{rows_read}/{rows_read-rows_ok}", flush=True)
    assert fold_n["A"] + fold_n["B"] == rows_ok
    # A ∩ B = 0 by construction (each review one fold)

    periods = sorted(dates_by_q.keys(), key=period_sort_key)
    completeness = {}
    for p in periods:
        completeness[p] = classify_period_completeness(date_min, date_max, p)
        start, end = quarter_bounds(p)
        completeness[p] = {
            "status": classify_period_completeness(date_min, date_max, p),
            "calendar_start": start.isoformat(),
            "calendar_end": end.isoformat(),
            "n_unique_dates": len(dates_by_q[p]),
            "first_date": min(dates_by_q[p]),
            "last_date": max(dates_by_q[p]),
        }

    rows = []
    for hid, period in qrev.keys():
        meta = hotel_meta[hid]
        rv = qrev[(hid, period)]
        n_rev = rv["n"]
        mean_score = (rv["score_sum"] / rv["score_n"]) if rv["score_n"] else np.nan
        pstat = completeness[period]["status"]
        for a in ASPECTS:
            c = quarter_acc.get((hid, period, a), {"pos": 0, "neg": 0, "posA": 0, "negA": 0, "posB": 0, "negB": 0})
            pos, neg = int(c["pos"]), int(c["neg"])
            posA, negA = int(c["posA"]), int(c["negA"])
            posB, negB = int(c["posB"]), int(c["negB"])
            tot, totA, totB = pos + neg, posA + negA, posB + negB
            sn, rel = smoothed_net(pos, neg, prior)
            snA, _ = smoothed_net(posA, negA, prior)
            snB, _ = smoothed_net(posB, negB, prior)
            has = tot > 0
            rows.append({
                "hotel_id": hid,
                "legacy_hotel_id": meta["legacy_hotel_id"],
                "hotel_name": meta["hotel_name"],
                "city": meta["city"],
                "country": meta["country"],
                "latitude": meta["latitude"],
                "longitude": meta["longitude"],
                "period": period,
                "period_complete": pstat == "complete",
                "aspect": a,
                "positive_mentions": pos,
                "negative_mentions": neg,
                "total_mentions": tot,
                "has_measurement": has,
                "positive_mentions_A": posA,
                "negative_mentions_A": negA,
                "total_mentions_A": totA,
                "has_measurement_A": totA > 0,
                "positive_mentions_B": posB,
                "negative_mentions_B": negB,
                "total_mentions_B": totB,
                "has_measurement_B": totB > 0,
                "raw_net": raw_net(pos, neg),
                "smoothed_net": sn,
                "measurement_reliability": rel,
                "smoothed_net_A": snA,
                "smoothed_net_B": snB,
                "prior_only": (not has),
                "total_reviews": n_rev,
                "mean_reviewer_score": mean_score,
                "prior_strength": prior,
            })
    panel = pd.DataFrame(rows)
    write_parquet(panel, panel_v2_path(root), "panel_v2", PANEL_REQUIRED)
    sample = panel.sample(n=min(500, len(panel)), random_state=42)
    sample.to_parquet(odir / "panel_sample.parquet", index=False)

    # sensitivity priors (summary only)
    sens = {}
    for ps in cfg["shrinkage"]["prior_strength_sensitivity"]:
        nets = []
        for p, n in zip(panel["positive_mentions"].to_numpy(), panel["negative_mentions"].to_numpy()):
            sn, _ = smoothed_net(int(p), int(n), ps)
            nets.append(sn)
        arr = np.asarray(nets)
        sens[str(ps)] = {
            "mean": float(arr.mean()),
            "std": float(arr.std()),
            "corr_with_main": float(np.corrcoef(arr, panel["smoothed_net"].to_numpy())[0, 1]),
        }

    complete_periods = [p for p, v in completeness.items() if v["status"] == "complete"]
    partial_periods = [p for p, v in completeness.items() if v["status"] == "partial"]
    measured = panel[panel["has_measurement"]]
    nA = int(panel["has_measurement_A"].sum())
    nB = int(panel["has_measurement_B"].sum())
    overlap_cells = int(((panel["has_measurement_A"]) & (panel["has_measurement_B"])).sum())
    # review-level folds are disjoint; cell-level both folds can be measured from different reviews

    meas = {
        "source_sha256": source_sha,
        "rows_read": rows_read,
        "rows_date_ok": rows_ok,
        "date_min": date_min.isoformat(),
        "date_max": date_max.isoformat(),
        "fold_reviews": fold_n,
        "fold_review_intersection": 0,
        "period_completeness": completeness,
        "complete_periods": complete_periods,
        "partial_periods": partial_periods,
        "panel_rows": int(len(panel)),
        "hotels": int(panel["hotel_id"].nunique()),
        "hotel_names": int(panel["hotel_name"].nunique()),
        "cities": int(panel["city"].nunique()),
        "measured_cells": int(len(measured)),
        "prior_only_cells": int(panel["prior_only"].sum()),
        "measured_cells_A": nA,
        "measured_cells_B": nB,
        "cells_with_both_folds_measured": overlap_cells,
        "prior_sensitivity": sens,
        "shrinkage_name": "symmetric Beta-Binomial Bayesian shrinkage",
        "not_empirical_bayes": True,
        "hotel_id_format": "d1_europe:{sha1(address)[:12]}",
        "zero_mention_raw_net_is_nan": bool(panel.loc[~panel["has_measurement"], "raw_net"].isna().all()),
    }

    # Measurement verdict (scientific, pre-specified qualitative rule)
    usable = (
        meas["measured_cells"] >= 20000
        and meas["hotels"] >= 500
        and len(complete_periods) >= 4
        and meas["cities"] >= 4
        and meas["zero_mention_raw_net_is_nan"]
        and fold_n["A"] > 0 and fold_n["B"] > 0
    )
    strong = usable and len(complete_periods) >= 6 and meas["measured_cells"] >= 50000
    meas["measurement_verdict"] = "MEASUREMENT_STRONG" if strong else ("MEASUREMENT_USABLE" if usable else "MEASUREMENT_WEAK")

    # Human annotation pack (text private)
    rng = np.random.default_rng(cfg["seed"])
    pack = _build_human_pack(sample_candidates, rng)
    atomic_write_json(private / "human_annotation_pack.json", pack)
    manifest = {
        "n_items": len(pack["items"]),
        "cities": sorted({it["city"] for it in pack["items"]}),
        "aspects": sorted({it["aspect"] for it in pack["items"]}),
        "sections": sorted({it["section"] for it in pack["items"]}),
        "text_location": "outputs/autonomous/private/human_annotation_pack.json (gitignored)",
        "HUMAN_VALIDATION_REQUIRED": True,
        "status": "pack_generated_unannotated",
    }
    atomic_write_json(odir / "human_annotation_pack_manifest.json", manifest)
    atomic_write_text(root / "docs" / "HUMAN_ANNOTATION_PROTOCOL.md", HUMAN_PROTOCOL)

    atomic_write_json(odir / "measurement_manifest.json", meas)
    atomic_write_text(odir / "MEASUREMENT_V2.md", _meas_md(meas))
    update_state(root, wave=1, status="WAVE1_DONE", measurement_verdict=meas["measurement_verdict"])
    return meas


def _build_human_pack(cands: list[dict], rng: np.random.Generator) -> dict:
    items = []
    # target ~200 items covering aspects/cities/sections (human protocol; ABSA uses a larger private sample)
    by_key: dict[tuple, list] = defaultdict(list)
    for c in cands:
        for a in c["aspects"]:
            by_key[(c["city"], a, c["section"])].append(c)
    for key, lst in by_key.items():
        take = min(3, len(lst))
        if take <= 0:
            continue
        idx = rng.choice(len(lst), size=take, replace=False)
        for i in np.atleast_1d(idx):
            c = lst[int(i)]
            items.append({
                "item_id": c["fp"][:16] + f"-{key[1]}-{key[2]}",
                "city": c["city"],
                "aspect": key[1],
                "section": c["section"],
                "period": c["period"],
                "hotel_id": c["hotel_id"],
                "text": c["text"],
                "weak_label_from_section": "positive" if c["section"] == "positive" else "negative",
            })
    rng.shuffle(items)
    items = items[:240]
    return {"schema": "human_absa_pack_v1", "HUMAN_VALIDATION_REQUIRED": True, "items": items}


def _write_fixture_csv(root: Path) -> Path:
    """Tiny synthetic reviews for CI. No 515K."""
    path = out_dir(root) / "private" / "tiny_reviews.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    cities = [
        ("London United Kingdom", "London"),
        ("Paris France", "Paris"),
        ("Amsterdam Netherlands", "Amsterdam"),
        ("Barcelona Spain", "Barcelona"),
        ("Vienna Austria", "Vienna"),
        ("Milan Italy", "Milan"),
    ]
    aspects_kw = {
        "location": "great location near metro",
        "cleanliness": "room was clean and spotless",
        "breakfast": "breakfast buffet was excellent",
        "service": "staff were helpful and friendly",
        "noise": "room was quiet at night",
        "room": "comfortable bed and spacious room",
        "value": "good value for money",
    }
    neg_kw = {
        "location": "far from centre bad location",
        "cleanliness": "dirty room dusty smell",
        "breakfast": "breakfast was terrible",
        "service": "rude staff unhelpful reception",
        "noise": "noisy loud traffic noise",
        "room": "tiny room cramped bed",
        "value": "overpriced expensive not worth",
    }
    # dates covering 2015Q3 partial through 2017Q3 partial
    dates = [
        "08/15/2015",  # 2015Q3
        "11/02/2015", "12/15/2015",  # 2015Q4
        "02/10/2016", "05/10/2016", "08/10/2016", "11/10/2016",
        "02/10/2017", "05/10/2017",
        "07/20/2017",  # 2017Q3
    ]
    rows = []
    hid_n = 0
    for ci, (addr_sfx, city) in enumerate(cities):
        for h in range(4):
            hid_n += 1
            addr = f"{h} Example Street {addr_sfx}"
            name = f"Hotel {city} {h}"
            lat = 50 + ci + h * 0.01
            lon = 2 + ci + h * 0.01
            for di, ds in enumerate(dates):
                for asp in ASPECTS:
                    pos = aspects_kw[asp] if (h + di) % 3 != 0 else "No Positive"
                    neg = "No Negative" if (h + di) % 4 != 0 else neg_kw[asp]
                    score = 8.5 if (h + di) % 3 != 0 else 6.2
                    rows.append({
                        "Hotel_Address": addr,
                        "Hotel_Name": name,
                        "Review_Date": ds,
                        "Reviewer_Score": f"{score}",
                        "Reviewer_Nationality": " United Kingdom ",
                        "Positive_Review": pos,
                        "Negative_Review": neg,
                        "lat": str(lat),
                        "lng": str(lon),
                    })
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return path


HUMAN_PROTOCOL = """# HUMAN ANNOTATION PROTOCOL

Status: **HUMAN_VALIDATION_REQUIRED** — this pack is generated, not labeled.

## Goal

Estimate agreement between structurally weak section labels (Positive_Review / Negative_Review keyword-gated aspects) and human aspect-polarity judgments. This is **not** gold accuracy of the production system until labels exist.

## Items

See `outputs/autonomous/wave1/human_annotation_pack_manifest.json`.
Texts live only in the gitignored private pack.

## Task

For each item, the annotator sees: city, aspect name, review **section** excerpt (already gated as mentioning the aspect).

Labels:
- `positive` / `negative` / `neutral` / `not_about_aspect`

Do **not** use the Booking overall score. Do **not** infer hotel identity beyond the excerpt.

## Quality

Double-annotate a 20% overlap subset. Report Cohen's kappa between annotators before comparing to weak labels.

## What this can / cannot claim

Can: measurement-error bound for weak labels.
Cannot: "ABSA gold accuracy"; causal service quality; manager intervention.
"""


def _meas_md(m: dict) -> str:
    return f"""# MEASUREMENT V2

## Verdict: **{m['measurement_verdict']}**

Shrinkage: **symmetric Beta-Binomial Bayesian shrinkage** (prior_strength={m.get('prior_sensitivity', {}).get('10', {})}). Not empirical Bayes.

## Completeness (programmatic)

- Date span: {m['date_min']} → {m['date_max']}
- Complete periods: {m['complete_periods']}
- Partial periods: {m['partial_periods']}

Main analysis **excludes** partial quarters.

## Zero mention

`has_measurement=false` ⇒ `raw_net=NaN` ⇒ `prior_only=true`.
Smoothed_net may still be the prior mean (0) and **must not** be read as observed neutral quality.

## Cross-fitting

Review fingerprint SHA1; fold A/B; review-level A ∩ B = {m['fold_review_intersection']}.
A detects change → B measures outcome (Wave 2+).

## Scale

- Hotels: {m['hotels']} (names {m['hotel_names']})
- Cities: {m['cities']}
- Panel rows: {m['panel_rows']}
- Measured cells: {m['measured_cells']}
- Prior-only cells: {m['prior_only_cells']}

## Human labels

HUMAN_VALIDATION_REQUIRED. Pack generated; not waiting.
"""

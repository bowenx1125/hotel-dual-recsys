# WAVE 0 — Forensic audit

Autonomous research does **not** treat overnight GREEN / 5774 as a strict result.

## Independent reproduction

- Artifact candidate_events.csv: **5774**
- Recomputed overnight rule from parquet: **5774**
- Match: **True**
- Label going forward: `legacy_permissive_event_count` only.

## Answers to the 15 questions

1. **Zero-mention inflation:** YES. Zero-mention cells have `smoothed_net=0`. Events required current mentions≥5 but **not** previous mentions≥5 (1047 events with prev<5; 78 with prev=0). Location included (800 events).
2. **2pre+2post=100%:** row existence, not valid measurement. Valid-mention neighbors: 5525/5774 = 0.9569.
3. **2015Q3 / 2017Q3 incomplete:** expected YES from date span 2015-08-04 → 2017-08-03. Wave 1 verifies programmatically.
4. **2017Q3 in predictive test:** YES. test_periods=['2017Q2', '2017Q3'].
5. **Peer exposure overall score:** YES, not same-aspect.
6. **Validation used for tuning:** NO.
7. **Ridge fair:** NO (see findings JSON).
8. **Bootstrap hotel-clustered:** NO (iid rows, n=500).
9. **1492 names vs 1493 IDs:** hashed addresses vs names. Panel: 1493 IDs, 1491 names. Multi-id names: {'Hotel Regina': 3}.
10. **Stale 373-city manifest:** YES; corrected to 6 with legacy bug field retained.
11. **Stale handoff SHA:** YES (`365b548` vs HEAD `2586827`).
12. **FAILURES.md omitted failures:** YES; rewritten.
13. **REVIEW.md only Phase 0:** YES; extended.
14. **facts_sha256 empty:** YES; now hashed.
15. **GitHub Actions:** matplotlib missing on import path; repaired on this branch.

## Engineering vs scientific

Overnight CI failure is **engineering** (must fix). Overnight GREEN/5774 overclaim is **scientific measurement error** — keep the number only as legacy_permissive, do not retune thresholds to recover GREEN.

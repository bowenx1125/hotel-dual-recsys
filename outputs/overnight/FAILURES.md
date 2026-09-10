# Failures

## Recorded (Wave 0 forensic, 2026-09-11)

1. **GitHub Actions `research-smoke` failed** on all listed runs of `research/temporal-feasibility-20260910-grok`.
   Cause: `test_classify_green` imported `scripts.run_temporal_feasibility`, which imported `matplotlib` at module level. CI installed only numpy/pandas/pyarrow.
   Run IDs: 34510724491 (PR), 34500261999, 34500257453, 34500234958.
2. **City parser** initially invented 373 cities (last token). Fixed to known 6-city detector; `europe_515k_manifest.json` remained stale at 373 until Wave 0 correction.
3. **`facts_sha256` empty** in overnight `state.json`.
4. **Handoff Final SHA** pinned `365b548` while branch HEAD is `2586827` (two later commits).
5. **Scientific (not engineering) issues in overnight measurement/prediction** — see `outputs/autonomous/wave0/WAVE0_AUDIT.md`. These are not CI failures; they change the research interpretation of 5774 / GREEN / peer MAE.

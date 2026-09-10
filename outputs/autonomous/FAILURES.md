# Failures

## Engineering (Wave 0)

1. GitHub Actions `research-smoke` failed: `ModuleNotFoundError: matplotlib` when `test_classify_green` imported `scripts.run_temporal_feasibility`.
   Run IDs: 34510724491, 34500261999, 34500257453, 34500234958.
   Repair: `src/temporal/gates.py` + lazy matplotlib import. Local unit tests pass after repair.

## Scientific (not engineering; do not retune)

Overnight GREEN / 5774 is a **permissive** count. See `outputs/autonomous/wave0/WAVE0_AUDIT.md`.
Kept as `legacy_permissive_event_count` only.

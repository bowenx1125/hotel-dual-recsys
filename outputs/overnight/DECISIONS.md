# Decisions Log

## D0 — Worktree isolation (2026-09-10)

- Created `/Users/xubosmell/Desktop/FYP1-temporal` on branch `research/temporal-feasibility-20260910-grok` at `c6a33d7`.
- Original `/Users/xubosmell/Desktop/FYP1` left on `demo/provider-side-20260910-grok` untouched.
- Private data accessed via `FYP_PRIVATE_DATA_ROOT` (not committed absolute paths).

## D1 — Config canonical source

- `conf/demo.json` is canonical for the Demo runtime.
- `conf/demo.yaml` becomes a generated human-readable mirror; parity test required.
- New `conf/actionability.json` is the single source for actionability metadata.


## D-2026-09-10-phase2
- Belgium join index↔review_id match_rate=1.0; dates usable 2018-07-31→2021-07-19 but only 24 hotels with aspects.
- Primary temporal source: 515K Europe in FYP_DATA_CACHE_ROOT (not git).
- Aspect gate: drop location `area`, noise bare `hear`/`heard` (false positives).

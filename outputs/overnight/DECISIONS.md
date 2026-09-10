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


## D-2026-09-11-panel-peers-feas
- City parse: use known 6-city detector (London/Paris/Amsterdam/Barcelona/Vienna/Milan), not last token (was inventing 373 false cities).
- Primary panel: quarterly; monthly exploratory only.
- prior_strength main=10 fixed a priori; sensitivity 5/10/20 reported (corr≈0.988).
- Feasibility main Δ=0.15 fixed; GREEN gates all passed without retuning.
- Predictive pilot executed under GREEN; Manager Demo remains DESCRIPTIVE.
- Peer MAE gain vs own_features is negligible → do not overclaim peer predictive value.

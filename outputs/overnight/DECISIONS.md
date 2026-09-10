# Decisions Log

## D0 — Worktree isolation (2026-09-10)

- Created `/Users/xubosmell/Desktop/FYP1-temporal` on branch `research/temporal-feasibility-20260910-grok` at `c6a33d7`.
- Original `/Users/xubosmell/Desktop/FYP1` left on `demo/provider-side-20260910-grok` untouched.
- Private data accessed via `FYP_PRIVATE_DATA_ROOT` (not committed absolute paths).

## D1 — Config canonical source

- `conf/demo.json` is canonical for the Demo runtime.
- `conf/demo.yaml` becomes a generated human-readable mirror; parity test required.
- New `conf/actionability.json` is the single source for actionability metadata.

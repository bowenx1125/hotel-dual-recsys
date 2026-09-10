# Decisions

## D-A0-2026-09-11 Remote base

- Research base = latest `origin/research/temporal-feasibility-20260910-grok` @ `2586827`.
- Demo `0f5ebd5` is screenshot-only; not merged, not cherry-picked.

## D-A0-CI

- Extract `classify_gate` so CI never imports matplotlib for unit tests.

## D-A0-science

- Do not retune delta/mentions to recover overnight GREEN.
- 5774 is `legacy_permissive_event_count` only.
- Main analyses exclude partial quarters; zero-mention is not observed neutral.

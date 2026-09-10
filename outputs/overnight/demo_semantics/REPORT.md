# Phase 1 — Demo Scientific Semantics REPORT

## Changes

1. **Actionability schema** (`conf/actionability.json`): Location is diagnostic-visible but not eligible for direct action.
2. **Heuristic rename**: UI/default label is **Peer-Relative Evidence-Weighted (heuristic)**. Crowding is under **Competition Crowding Hypothesis** (scenario / illustrative).
3. **Action layer** excludes immutable aspects; diagnostic layer still reports Location when it is the largest gap.
4. **Weights** remain design choices; sensitivity grid reported (not tuned to cases).
5. **Config**: `conf/demo.json` canonical; `conf/demo.yaml` auto-generated.

## Weight sensitivity (assumed_intensity=0)

- Hotels: 22
- Fully stable across 5 grids: **12/22 (54.5%)**
- Top-1 switching rate: **45.5%**
- See `WEIGHT_SENSITIVITY.md`

## Claims updates

- C3 Location not direct action: **SUPPORTED** by schema + tests
- C4 weights not learned: **SUPPORTED** + sensitivity shows instability under alternate design choices

## Tests

See `test_phase1.txt` (after fixes: actionability + scoring + evidence + adapter + smoke).

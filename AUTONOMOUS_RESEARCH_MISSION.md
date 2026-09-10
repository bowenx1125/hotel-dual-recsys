# Autonomous Research Mission — BNBU FYP `hotel-dual-recsys`

Unattended research run on branch `research/autonomous-paper-20260911`.
Worktree: `/Users/xubosmell/Desktop/FYP1-autonomous`.
Base: `origin/research/temporal-feasibility-20260910-grok` @ `2586827`.

## Order (mandatory)

Research Question → Measurement → Data → Peer Definition → Temporal Design
→ Experiments → Falsification → Recommendation Method → Robustness
→ Claims → Paper → Demo

Demo is a downstream visualization of claims. Never reverse this order.

## Two gates

- **Engineering**: tests/CI/joins/leakage/schema — repair until PASS.
- **Scientific**: null/inconclusive/confounded are valid. Do not p-hack.
  Outcomes: PASS_POSITIVE / PASS_NULL / PASS_INCONCLUSIVE / PASS_CONFOUNDED.

## Paper tracks (always maintained)

- **A** Provider-Side Recommendation under Peer Exposure
- **B** From Diagnosis to Action: Actionability- and Reliability-Aware Provider Recommendation
- **C** Review Sentiment Change Is Not Service Improvement

If the core story fails, switch track. Never change analysis principles to keep Track A alive.

## Waves 0–10

See `conf/autonomous_research.json` for preregistered thresholds.
Runner: `python run_research.py --wave N` / `--resume` / `--small-fixture` / `--verify-only`.

## Forbidden git

No `reset --hard`, `clean -fdx`, force push, merge of default branch, rewrite of pushed history.
Do not modify `/Users/xubosmell/Desktop/FYP1` or `/Users/xubosmell/Desktop/FYP1-temporal`.
Do not merge/cherry-pick demo commit `0f5ebd5` (screenshot-only).

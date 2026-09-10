# Remote branch reconciliation — 2026-09-11

Verified with `git fetch origin --prune` before any research work.

## HEADs (not stale)

| Ref | SHA | Role |
|---|---|---|
| `origin/research/temporal-feasibility-20260910-grok` | `2586827f40a9028177061fdf16daf170fb35f9d6` | **Research base** (matches known SHA; still current) |
| `origin/demo/provider-side-20260910-grok` | `0f5ebd5af125d397c99eced28175ec2131e68ca9` | Historical Demo only |
| merge-base of the two | `c6a33d79d3441028a3d54292bcc96f0a763d1f37` | Shared ancestor (`chore(repo): add FYP source…`) |

Research is **not** an ancestor of demo; demo is **not** an ancestor of research.

## Commits on demo not in research

Only:

```
0f5ebd5 chore(demo): add live Streamlit screenshot artifact
```

File-level: **adds** `outputs/night_demo/demo_screenshot_streamlit.png` only. No code, no config, no research logic.

## Decision

- Autonomous branch created **from latest origin research HEAD** `2586827`.
- Worktree: `/Users/xubosmell/Desktop/FYP1-autonomous`
- Branch: `research/autonomous-paper-20260911`
- **Do not** merge demo, cherry-pick `0f5ebd5`, or rewrite research history for the screenshot.
- Final live screenshots will be recaptured from this branch’s own Streamlit + latest artifacts.

## Other worktrees (untouched)

- `/Users/xubosmell/Desktop/FYP1` @ demo `0f5ebd5`
- `/Users/xubosmell/Desktop/FYP1-temporal` @ research `2586827`

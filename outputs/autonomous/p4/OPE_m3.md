# P4 Off-Policy Evaluation (direct method, cross-fitted)

**Not IPS/SNIPS.** No logged policy exists in this project (`wave6/policy.json: no_ips_snips=true`; reviewer rule R1 P2). Values below come from an outcome regression (direct method) with hotel-clustered uncertainty, not from inverse propensity weighting.

## Timing: forward

- units/direction: **2646**, hotels/direction: **795**, periods: 2016Q1, 2016Q2, 2016Q3, 2016Q4, 2017Q1
- reference improvement delta: **0.1229** (median positive quarter-over-quarter aspect move)

### Aspect value coefficients (rating points per 1 unit of sentiment)

| aspect | gamma | se |
|---|---|---|
| location | -0.0735 | 0.0686 |
| cleanliness | +0.0448 | 0.0476 |
| breakfast | +0.0060 | 0.0471 |
| service | -0.0796 | 0.0572 |
| noise | -0.0588 | 0.0454 |
| room | -0.0244 | 0.0660 |
| value | +0.0003 | 0.0463 |

### Policy values (rating points; abstention = 0)

| policy | value | se | 95% CI | abstain |
|---|---|---|---|---|
| fix_weakest | -0.0021 | 0.0030 | [-0.0079, +0.0038] | 3.8% |
| largest_peer_gap | -0.0026 | 0.0025 | [-0.0075, +0.0022] | 4.0% |
| most_criticized | -0.0030 | 0.0076 | [-0.0179, +0.0120] | 3.8% |
| peer_relative | -0.0026 | 0.0027 | [-0.0080, +0.0028] | 4.0% |
| reliability_aware | -0.0019 | 0.0031 | [-0.0080, +0.0042] | 3.8% |
| wrank_current-default | -0.0026 | 0.0027 | [-0.0080, +0.0028] | 4.0% |
| wrank_gap-dominant | -0.0027 | 0.0026 | [-0.0077, +0.0024] | 4.0% |
| wrank_criticism-dominant | -0.0021 | 0.0033 | [-0.0086, +0.0044] | 4.0% |
| wrank_reliability-conservative | -0.0030 | 0.0035 | [-0.0098, +0.0038] | 4.0% |
| wrank_equal-weight | -0.0023 | 0.0034 | [-0.0090, +0.0043] | 4.0% |
| random_uniform | -0.0023 | 0.0021 | [-0.0063, +0.0017] | — |
| always_cleanliness | +0.0055 | 0.0059 | [-0.0060, +0.0170] | — |
| always_breakfast | +0.0007 | 0.0058 | [-0.0106, +0.0121] | — |
| always_service | -0.0098 | 0.0070 | [-0.0236, +0.0040] | — |
| always_noise | -0.0072 | 0.0056 | [-0.0182, +0.0037] | — |
| always_room | -0.0030 | 0.0081 | [-0.0189, +0.0129] | — |
| always_value | +0.0000 | 0.0057 | [-0.0111, +0.0112] | — |
| oracle_best | +0.0055 | 0.0059 | [-0.0060, +0.0170] | — |
| oracle_worst | -0.0098 | 0.0070 | [-0.0236, +0.0040] | — |
| never_act | +0.0000 | 0.0000 | [+0.0000, +0.0000] | — |

### Policy contrasts (rating points vs the named comparator)

| contrast | diff | se | t | bootstrap se | 5% sig |
|---|---|---|---|---|---|
| always_service - peer_relative | -0.0072 | 0.0069 | -1.04 | 0.0122 | no |
| largest_peer_gap - peer_relative | -0.0000 | 0.0010 | -0.02 | 0.0015 | no |
| wrank_gap-dominant - wrank_current-default | -0.0000 | 0.0006 | -0.07 | — | no |
| peer_relative - random_uniform | -0.0003 | 0.0016 | -0.21 | 0.0026 | no |
| oracle_best - random_uniform | +0.0078 | 0.0057 | +1.36 | 0.0062 | no |

### Discrimination power (headline)

- split-sample best-minus-worst gap: **+0.0260** (sd across 20 reps 0.0050, 90% range [+0.0178, +0.0323])
- in-sample optimistic gap (cleanliness vs service): **+0.0153** (se 0.0094) — upper bound only
- permutation placebo gap: **+0.0216** (reward shuffled within period; should be ~0)
- cross-fit vs full-sample max abs value diff: **0.00017**
- cluster-bootstrap SE (n=60): peer_relative=0.0040, largest_peer_gap=0.0040, always_service=0.0129, random_uniform=0.0030, oracle_best=0.0074, oracle_worst=0.0064

## Timing: contemp

- units/direction: **2651**, hotels/direction: **801**, periods: 2016Q1, 2016Q2, 2016Q3, 2016Q4, 2017Q1
- reference improvement delta: **0.1229** (median positive quarter-over-quarter aspect move)

### Aspect value coefficients (rating points per 1 unit of sentiment)

| aspect | gamma | se |
|---|---|---|
| location | +0.1323 | 0.0671 |
| cleanliness | -0.0067 | 0.0546 |
| breakfast | +0.0329 | 0.0471 |
| service | +0.1917 | 0.0599 |
| noise | +0.0117 | 0.0469 |
| room | +0.0284 | 0.0642 |
| value | +0.0204 | 0.0431 |

### Policy values (rating points; abstention = 0)

| policy | value | se | 95% CI | abstain |
|---|---|---|---|---|
| fix_weakest | +0.0032 | 0.0029 | [-0.0025, +0.0089] | 3.9% |
| largest_peer_gap | +0.0073 | 0.0025 | [+0.0025, +0.0122] | 4.1% |
| most_criticized | +0.0038 | 0.0074 | [-0.0108, +0.0183] | 3.9% |
| peer_relative | +0.0061 | 0.0027 | [+0.0008, +0.0114] | 4.1% |
| reliability_aware | +0.0032 | 0.0030 | [-0.0027, +0.0092] | 3.9% |
| wrank_current-default | +0.0061 | 0.0027 | [+0.0008, +0.0114] | 4.1% |
| wrank_gap-dominant | +0.0068 | 0.0026 | [+0.0018, +0.0118] | 4.1% |
| wrank_criticism-dominant | +0.0037 | 0.0032 | [-0.0027, +0.0100] | 4.1% |
| wrank_reliability-conservative | +0.0067 | 0.0034 | [-0.0000, +0.0135] | 4.1% |
| wrank_equal-weight | +0.0049 | 0.0034 | [-0.0017, +0.0115] | 4.1% |
| random_uniform | +0.0057 | 0.0021 | [+0.0017, +0.0097] | — |
| always_cleanliness | -0.0008 | 0.0067 | [-0.0140, +0.0123] | — |
| always_breakfast | +0.0040 | 0.0058 | [-0.0073, +0.0154] | — |
| always_service | +0.0236 | 0.0074 | [+0.0091, +0.0380] | — |
| always_noise | +0.0014 | 0.0058 | [-0.0099, +0.0127] | — |
| always_room | +0.0035 | 0.0079 | [-0.0120, +0.0190] | — |
| always_value | +0.0025 | 0.0053 | [-0.0079, +0.0129] | — |
| oracle_best | +0.0236 | 0.0074 | [+0.0091, +0.0380] | — |
| oracle_worst | -0.0008 | 0.0067 | [-0.0140, +0.0123] | — |
| never_act | +0.0000 | 0.0000 | [+0.0000, +0.0000] | — |

### Policy contrasts (rating points vs the named comparator)

| contrast | diff | se | t | bootstrap se | 5% sig |
|---|---|---|---|---|---|
| always_service - peer_relative | +0.0175 | 0.0071 | +2.45 | 0.0096 | yes |
| largest_peer_gap - peer_relative | +0.0013 | 0.0010 | +1.24 | 0.0016 | no |
| wrank_gap-dominant - wrank_current-default | +0.0007 | 0.0006 | +1.30 | — | no |
| peer_relative - random_uniform | +0.0004 | 0.0016 | +0.24 | 0.0026 | no |
| oracle_best - random_uniform | +0.0179 | 0.0067 | +2.65 | 0.0054 | yes |

### Discrimination power (headline)

- split-sample best-minus-worst gap: **+0.0348** (sd across 20 reps 0.0064, 90% range [+0.0243, +0.0432])
- in-sample optimistic gap (service vs cleanliness): **+0.0244** (se 0.0103) — upper bound only
- permutation placebo gap: **+0.0199** (reward shuffled within period; should be ~0)
- cross-fit vs full-sample max abs value diff: **0.00012**
- cluster-bootstrap SE (n=60): peer_relative=0.0048, largest_peer_gap=0.0042, always_service=0.0090, random_uniform=0.0034, oracle_best=0.0062, oracle_worst=0.0082

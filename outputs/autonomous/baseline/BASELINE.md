# P1 baseline freeze

Frozen at 2026-09-14T07:32:08+00:00 | git HEAD `378981c13ca4` (Record final clone and CI acceptance for colleague handoff)

## Algorithm (the thing P3 changes)

- peer_relative (Peer-Relative Evidence-Weighted)
- weights: {'gap': 0.45, 'criticism': 0.35, 'unreliable': 0.2} — **design choices, not learned** (`weights_are_design_choices=True`)
- grids available: ['current-default', 'gap-dominant', 'criticism-dominant', 'reliability-conservative', 'equal-weight']
- gates: min_mentions=5, min_reviews_hotel=10, reliability_k=10.0

## Panel

- rows 89075 | hotels 1493 | cities 6
- hotel-quarters 12725 (complete 9960)
- measured cells A=72485 B=72828; prior-only 8389
- mean_reviewer_score 8.4467 (sd 0.7900); total_reviews mean 40.53

## Incumbent effect estimates (and why they are weak)

- Wave5 ATT at k=0: **0.16971589236138307** (unit = pooled smoothed_net, not a hotel outcome)
- strict cross-fit events: 456 (legacy permissive 5774 is not a strict result)
- Wave6: no_roi=True, no_demand_lift=True

Defects recorded:

- **self_referential_outcome**: Wave5 measures y with POOLED smoothed_net while events are detected per fold; the treatment and the outcome come from the same reviews.
- **violates_preregistered_crossfit_rule**: conf/autonomous_research.json crossfit.rule = 'detect_on_one_fold_measure_outcome_on_the_other' is not executed by Wave5.
- **outcome_is_not_downstream**: smoothed_net is an aspect-sentiment index, not a hotel revenue/rating outcome; a change in it cannot be read as hotel benefit.
- **n_456_concentrated_in_2016Q2_Q4**: Strict events cluster in few periods; quarter-score sd limits detectable effect.

## P3 acceptance

- must beat: P2 cross-fit effect estimate (downstream outcome, fold-separated).
- forbidden: lowering configured significance / delta thresholds
- forbidden: tuning weights on the same data used to report the gain
- forbidden: claiming ROI or booking growth from review data (no price or volume fields exist)

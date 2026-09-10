# Problem Formulation

**Units.** Hotel i, calendar quarter t, aspect a.

**Measurement.** Mentions from Positive/Negative review sections after a keyword gate. If total_mentions=0 then `has_measurement=false` and `raw_net` is NaN. Shrinkage is a fixed symmetric Beta-Binomial prior (main strength 10).

**Peers.** Same-city Haversine k-NN: **candidate peers / geo reference set**, not validated substitutes.

**Events.** Review-perceived aspect changes under pre-specified mention, delta, posterior probability, peer-count, cooldown, and complete-quarter rules. Not managerial interventions.

**Recommendation.** Map a hotel state to an aspect action or an abstention. No IPS/SNIPS (no logged policy). No ROI. No demand lift.

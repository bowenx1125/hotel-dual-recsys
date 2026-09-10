# Night Demo RESULTS (DESCRIPTIVE)

Evidence level: **DESCRIPTIVE**

Only cross-sectional aspect scores and researcher-defined peer sets are available. There is no time-split predictive model and no identified treatment effect with CI.

## Data facts (not heuristics)

- Eligible hotels (valid compset, ≥10 labelled reviews, ≥2 aspect-peers): **22**
- Valid competition sets used: **3** — `geo0_high, geo0_low, geo0_mid`
- Compset size among eligible hotels: min=6, median=7.0, max=11
- Labelled-review count among eligible hotels: min=11, median=95.5, max=846
- Aspect coverage (eligible hotels with net defined and mentions ≥ 5):
  - Location: 22/22 (100%)
  - Cleanliness: 20/22 (91%)
  - Breakfast: 19/22 (86%)
  - Service: 20/22 (91%)
  - Noise / quiet: 18/22 (82%)
  - Room: 21/22 (95%)
  - Value: 17/22 (77%)

## Heuristic policy results (assumed_intensity = 0)

These counts are **outputs of the documented heuristic**, not estimated effects.

Fix Weakest: Noise / quiet=16, Room=2, Breakfast=2, Location=2
Largest Peer Gap: Breakfast=5, Location=4, Noise / quiet=4, Cleanliness=3, Room=3, Value=2, Service=1
Most Criticized: Room=13, Cleanliness=3, Breakfast=2, Location=2, Service=1, Noise / quiet=1
Competition-Aware: Noise / quiet=8, Breakfast=4, Location=3, Cleanliness=3, Value=2, Service=1, Room=1

Pairwise agreement (share of eligible hotels with the same chosen aspect):
- fix_weakest__largest_peer_gap: **36.4%**
- fix_weakest__most_criticized: **22.7%**
- fix_weakest__competition_aware: **54.5%**
- largest_peer_gap__most_criticized: **31.8%**
- largest_peer_gap__competition_aware: **68.2%**
- most_criticized__competition_aware: **27.3%**

- Fix Weakest ≠ Largest Peer Gap: **14/22** (63.6%)
- Fix Weakest ≠ Competition-Aware: **10/22** (45.5%)
- All four agree: **3/22**

## What is a data fact vs a heuristic vs a scenario

| Item | Kind |
|---|---|
| Eligible hotel/compset counts, mention counts, nets, peer medians | Data fact from processed tables |
| Four strategy choices at intensity=0 | Transparent heuristic |
| Slider / intensity>0 ranking changes | Assumed scenario, not estimated lambda |
| Causal gain, demand lift, ROI | **Not computed; not claimed** |

## Conclusions that are NOT supported

- Improving the recommended aspect will raise ratings, reviews, or bookings.
- Peer-weakest-share is an identified spillover or crowding elasticity.
- These 3 Brussels centre sets are the true consideration set of guests.

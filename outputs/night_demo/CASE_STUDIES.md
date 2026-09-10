# Case studies

All cases use real eligible hotels from `aspect_features.csv` + `compsets.csv`.

## Case 1: Aloft Brussels Schuman

- Why selected: four strategies agree at assumed_intensity=0
- hotel_id: `aloft-brussels-schuman`
- compset_id: `geo0_mid`
- labelled reviews: 223 (low-rating reviews: 0)
- Choices at assumed_intensity=0:
  - fix_weakest: **Breakfast**
  - largest_peer_gap: **Breakfast**
  - most_criticized: **Breakfast**
  - competition_aware: **Breakfast**
- Aspect snapshot:

| aspect | net | gap | mentions | neg_mentions | reliability | peer_weakest_share |
|---|---:|---:|---:|---:|---:|---:|
| Location | 0.863 | -0.24449999999999994 | 51 | 2 | 0.836 | 0.17 |
| Cleanliness | 0.722 | -0.17199999999999993 | 36 | 4 | 0.783 | 0.00 |
| Breakfast | -0.04 | 0.471 | 25 | 9 | 0.714 | 0.00 |
| Service | 0.887 | -0.20199999999999996 | 53 | 2 | 0.841 | 0.00 |
| Noise / quiet | 0.385 | -0.6775 | 13 | 4 | 0.565 | 0.83 |
| Room | 0.772 | -0.4365 | 79 | 4 | 0.888 | 0.00 |
| Value | 0.692 | -0.5489999999999999 | 13 | 2 | 0.565 | 0.00 |

- CA top at intensity=0: `breakfast` · at assumed intensity=1: `breakfast` · ranking flips: False

## Case 2: B&B Place Jourdan

- Why selected: Fix Weakest disagrees with Largest Peer Gap
- hotel_id: `b-amp-b-place-jourdan`
- compset_id: `geo0_low`
- labelled reviews: 24 (low-rating reviews: 0)
- Choices at assumed_intensity=0:
  - fix_weakest: **Room**
  - largest_peer_gap: **Location**
  - most_criticized: **Cleanliness**
  - competition_aware: **Location**
- Aspect snapshot:

| aspect | net | gap | mentions | neg_mentions | reliability | peer_weakest_share |
|---|---:|---:|---:|---:|---:|---:|
| Location | 0.667 | 0.007499999999999951 | 15 | 1 | 0.6 | 0.10 |
| Cleanliness | 0.75 | -0.2835 | 8 | 1 | 0.444 | 0.00 |
| Breakfast | 0.769 | -0.3945 | 13 | 0 | 0.565 | 0.10 |
| Service | 0.857 | -0.26 | 14 | 1 | 0.583 | 0.00 |
| Noise / quiet | 1.0 | -1.143 | 4 | 0 | 0.286 | 0.70 |
| Room | 0.4 | -0.09500000000000003 | 10 | 1 | 0.5 | 0.00 |
| Value | None | None | 0 | 0 | 0.0 | 0.00 |

- CA top at intensity=0: `location` · at assumed intensity=1: `room` · ranking flips: True

## Case 3: Mercure Hotel Brussels Centre Midi

- Why selected: Competition-Aware differs from Fix Weakest (heuristic mix / reliability / peer context)
- hotel_id: `mercure-brussels-centre-midi-brussels`
- compset_id: `geo0_high`
- labelled reviews: 97 (low-rating reviews: 26)
- Choices at assumed_intensity=0:
  - fix_weakest: **Noise / quiet**
  - largest_peer_gap: **Cleanliness**
  - most_criticized: **Room**
  - competition_aware: **Cleanliness**
- Aspect snapshot:

| aspect | net | gap | mentions | neg_mentions | reliability | peer_weakest_share |
|---|---:|---:|---:|---:|---:|---:|
| Location | 0.371 | 0.391 | 35 | 9 | 0.778 | 0.00 |
| Cleanliness | 0.263 | 0.44099999999999995 | 19 | 7 | 0.655 | 0.00 |
| Breakfast | 0.667 | -0.03500000000000003 | 15 | 1 | 0.6 | 0.00 |
| Service | 0.333 | 0.39199999999999996 | 30 | 9 | 0.75 | 0.00 |
| Noise / quiet | -0.091 | -0.909 | 11 | 6 | 0.524 | 0.60 |
| Room | 0.333 | -0.24200000000000002 | 42 | 11 | 0.808 | 0.20 |
| Value | 0.143 | 0.38449999999999995 | 7 | 3 | 0.412 | 0.00 |

- CA top at intensity=0: `cleanliness` · at assumed intensity=1: `cleanliness` · ranking flips: False


# Weight Sensitivity

**Weights are design choices, not learned business returns.**

- Eligible hotels: **22**
- Grids: current-default, gap-dominant, criticism-dominant, reliability-conservative, equal-weight
- Fully stable top-1 across all grids: **12/22** (54.5%)
- Top-1 switching rate: **45.5%**

## Recommendation counts by grid

- `current-default`: Noise / quiet=8, Breakfast=4, Cleanliness=4, Room=2, Value=2, Service=1
- `gap-dominant`: Noise / quiet=5, Room=4, Breakfast=4, Cleanliness=4, Service=2, Value=2
- `criticism-dominant`: Noise / quiet=13, Cleanliness=4, Breakfast=2, Value=2
- `reliability-conservative`: Room=5, Noise / quiet=5, Service=4, Cleanliness=4, Breakfast=2, Value=1
- `equal-weight`: Noise / quiet=9, Cleanliness=4, Room=3, Breakfast=2, Service=2, Value=1

## Most unstable hotels

- Diamant Suites Brussels EU (`brussel-lounge`): 3 distinct picks → {'current-default': 'value', 'gap-dominant': 'value', 'criticism-dominant': 'noise', 'reliability-conservative': 'cleanliness', 'equal-weight': 'noise'}
- NH Collection Brussels Grand Sablon (`grandsablon`): 3 distinct picks → {'current-default': 'breakfast', 'gap-dominant': 'breakfast', 'criticism-dominant': 'noise', 'reliability-conservative': 'service', 'equal-weight': 'service'}
- Mercure Hotel Brussels Centre Midi (`mercure-brussels-centre-midi-brussels`): 3 distinct picks → {'current-default': 'cleanliness', 'gap-dominant': 'cleanliness', 'criticism-dominant': 'value', 'reliability-conservative': 'service', 'equal-weight': 'cleanliness'}
- Warwick Brussels - Grand Place (`warwick-brussels`): 3 distinct picks → {'current-default': 'breakfast', 'gap-dominant': 'breakfast', 'criticism-dominant': 'noise', 'reliability-conservative': 'room', 'equal-weight': 'room'}
- B&B Place Jourdan (`b-amp-b-place-jourdan`): 2 distinct picks → {'current-default': 'room', 'gap-dominant': 'room', 'criticism-dominant': 'cleanliness', 'reliability-conservative': 'room', 'equal-weight': 'room'}

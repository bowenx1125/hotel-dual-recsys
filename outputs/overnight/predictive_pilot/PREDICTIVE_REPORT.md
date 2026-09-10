# PREDICTIVE PILOT REPORT

## Status

Executed under feasibility verdict **GREEN**.

## Target

Next-quarter mean reviewer score (hotel-period).

## Split (time-ordered)

- Train y-periods: ['2015Q3', '2015Q4', '2016Q1', '2016Q2', '2016Q3']
- Val y-periods: ['2016Q4', '2017Q1']
- Test y-periods: ['2017Q2', '2017Q3']
- No random row split; no future features.

## Metrics (test MAE / RMSE)

```json
{
  "city_mean": {
    "mae": 0.6417721554378448,
    "rmse": 0.8395095729827374
  },
  "persistence": {
    "mae": 0.4916009116791631,
    "rmse": 0.7138299412550757
  },
  "own_trend": {
    "mae": 0.6606837044610153,
    "rmse": 0.9536383319936297
  },
  "own_features": {
    "mae": 0.4593462185252869,
    "rmse": 0.6446389987139147
  },
  "own_plus_peer_state": {
    "mae": 0.45835963781083905,
    "rmse": 0.6425888126621537
  },
  "own_plus_peer_exposure": {
    "mae": 0.4581395630182637,
    "rmse": 0.6420469433354444
  }
}
```

## Peer-aware vs persistence

- Bootstrap mean(MAE_persist - MAE_peer): 0.0333 CI95=[0.0171, 0.0496]
- Peer model improves on persistence: **True**

## Honest conclusion

This is a **predictive association** pilot only.
It does **not** establish causal peer interference.
Do **not** upgrade the Manager Demo evidence level to PREDICTIVE globally.

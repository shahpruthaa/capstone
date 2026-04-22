# `death_risk_v1`

`death_risk_v1` is currently a research-only heuristic and should not be treated as production-ready.

## Current Construction

- Training script: `apps/api/scripts/ml/train_death_risk_model.py`
- Core implementation: `apps/api/app/ml/death_risk/train.py`
- Estimator: `GradientBoostingClassifier`
- Features:
  - `cv_price`
  - `max_drawdown`
  - `price_collapse`
  - `low_liquidity`
  - `avg_volume_log`

## Target Definition

The current label is a proxy:

- `label = 1` when a symbol has fewer than 200 trading-history rows in the local database snapshot
- `label = 0` otherwise

This is not a realized default, delisting, fraud, or permanent-capital-impairment target. It is better interpreted as a weak survivorship/listing-stability proxy.

## Validation Status

Current stored metrics from `apps/api/artifacts/models/death_risk_v1/death_risk_metrics.json`:

- Cross-validation ROC AUC: `0.7786`
- Cross-validation ROC AUC std: `0.0235`
- In-sample train accuracy: `0.9153`

What is still missing:

- explicit out-of-sample time-series validation
- a production target tied to realized adverse outcomes
- calibration analysis
- threshold analysis for operational use

## Production Guidance

Do not use `death_risk_v1` as a hard production gate in the scoring pipeline until:

- the target is redefined around a real adverse outcome
- walk-forward or time-split validation is added
- acceptance thresholds are documented
- model-card style operating limits are approved

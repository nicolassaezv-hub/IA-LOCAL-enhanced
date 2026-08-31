# WFV-Aligned Tuner Contract

## Baseline Failure

The controlled EURUSD default-parameter baseline used 1,756 rows and 87
features. Dataset quality passed at 83.0, but production WFV failed:

- fold 1: 54.347826% precision, 46 signals
- fold 2: 0.00% precision, 0 signals
- average precision: 27.17%
- median precision: 27.17%
- pooled precision: 54.347826%
- evidence sufficient: false

Final calibration and validation passed on their later split, but could not
override the failed outer WFV contract. No model was promoted.

## Existing Tuner Mismatch

The legacy `tune()` API remains available and unchanged. It still optimizes XGB
and LightGBM separately on a single validation split and retains its historical
persistence/cache behavior. It is not treated as production model-selection
evidence.

The new `tune_wfv_aligned()` API is separate. It evaluates the actual
`ForexEnsembleTrainer` and its XGB, LightGBM, unchanged RandomForest,
soft-voting, isotonic-calibration, and learned-threshold path on nested temporal
folds.

## Nested Validation Design

Parameter selection and certification use different temporal observations:

```text
first outer training slice -> inner Optuna selection
reserved outer validations -> later production WFV certification
```

The tuner accepts the full prepared training frame only to derive the canonical
geometry. Optuna receives slices from the first outer training portion; outer
validation rows never enter an inner fit, calibration, or evaluation.

## Outer Fold Isolation

`WalkForwardValidator.split_positions(n)` is now the common positional source
for both `split()` and nested tuning. It uses the same auto window, step, purge,
minimum-size checks, maximum-fold truncation, and half-open slicing as the
existing production path.

For 1,756 rows, the unchanged outer geometry is:

- fold 1 train: `[0, 980)`, validation: `[1020, 1320)`
- fold 2 train: `[300, 1280)`, validation: `[1320, 1620)`

The tuning pool is exactly `[0, 980)`. The purge boundary, both validation
periods, and every later row are excluded. Regression tests construct the
positional sets and require an empty intersection between tuning and outer
validation.

## Inner Fold Geometry

The inner validator uses the same geometry helper with explicit selection-only
settings:

- window: 500
- step: 200
- purge: 20
- maximum/required folds: 2

For the 980-row pool this yields:

- fold 1 train: `[0, 480)`, validation: `[520, 720)`
- fold 2 train: `[200, 680)`, validation: `[720, 920)`

Each split is time ordered, train and validation do not overlap, and the
existing purge convention leaves 40 excluded positions across each boundary.
Fewer than two inner folds fails closed.

## Signal Evidence

Each inner fold requires:

`ceil(validation_size * 0.10)` directional signals.

For the 200-row inner validations this is 20 signals per fold. Every fold must
meet its floor. Zero-signal and high-precision/tiny-signal trials are evidence
insufficient; folds are not silently discarded.

The selected-candidate summary records validation size, minimum signals, TP,
FP, signals, precision, accuracy, positional boundaries, and all aggregates.

## Objective

For evidence-sufficient trials:

`objective_score = min(inner_avg_precision, inner_pooled_precision)`

Evidence-insufficient trials receive `-1.0`, strictly below every possible
evidence-sufficient precision score. The separate `inner_wfv_passed` diagnostic
requires sufficient evidence, pooled precision at least 65%, and the unchanged
average-65% or median-70% production metric branch.

If no trial has sufficient evidence, the API returns
`NO_INNER_EVIDENCE_SUFFICIENT_CANDIDATE`, exposes no selected `params`, and
keeps any highest diagnostic configuration separate. If evidence exists but no
candidate passes the inner WFV-like gate, the best diagnostic params are
returned with `inner_wfv_passed=false`; they are not eligible for outer
certification.

## Parameter Override

`ForexEnsembleTrainer` now accepts additive
`tuned_params_override=None` semantics:

- `None`: preserve the legacy on-disk loader behavior
- explicit dict: use exactly that dict, without merging disk parameters
- explicit `{}`: force production defaults

The optional argument propagates through `WalkForwardValidator.evaluate()`,
`train_with_wfv()`, and `_train_quality_candidate()`. Every outer WFV fold and
the final trainer receive the same override object. When no override is
provided, legacy call signatures and behavior remain unchanged.

## Hyperparameter Provenance

Selected parameters are canonicalized with sorted compact JSON and SHA-256, so
dict key order cannot change their identity. Concise provenance records:

- mode `nested_wfv_tuning`
- pair and exact snapshot SHA
- parameter SHA
- seed 42 and completed trial count
- tuning-pool and inner geometry
- selected inner metrics
- persistence state

An explicit candidate override requires matching nested-WFV provenance,
matching pair/snapshot/parameter identities, and
`inner_metrics.inner_wfv_passed=true`. The provenance is preserved in candidate
metadata; a diagnostic candidate cannot silently enter outer certification.

## Persistence Safety

`tune_wfv_aligned()` defaults to `persist=false` and `use_cache=false`. Under
those defaults it writes no params JSON, does not read or write
`HyperparameterCache`, writes no model, and performs no DB operation. Cache use
fails closed because the legacy cache is not bound to the canonical snapshot.

Optional params persistence occurs only when explicitly requested and only for
an inner-WFV-passing selection. This task did not execute real tuning or any
persistence path.

## Backward Compatibility

Legacy `tune()` remains callable with its existing behavior. Existing callers
that do not provide overrides retain disk-parameter loading and unchanged WFV
execution. Compatibility tests that load `integrated_pipeline` through minimal
module stubs also pass because the new hash helper is imported only inside the
explicit-override path.

Production thresholds, horizon, risk/reward ratio, features, RF defaults,
calibration threshold selection, WFV window/step/purge/n-folds, promotion, and
lifecycle logic were not changed.

## Tests

The test-first commit added 15 tests covering the requested geometry,
isolation, signal-evidence, objective, override, provenance, persistence, hash,
and legacy compatibility contracts. Before implementation, 14 failed on the
missing behavior and the legacy API test passed.

Final validation:

- new contract file: 15 passed
- focused nested-WFV/statistical/manual-retrain/first-run/legacy suite: 115 passed
- full suite: 803 passed, 10 expected skips, 0 failed, 23 subtests passed
- warnings: 13 existing deprecation warnings
- actual EURUSD Optuna tuning: not executed
- `latest_EURUSD.pkl`: absent
- model provenance/retrain/model-quality rows: 0/0/0
- EURUSD lifecycle: `qualified`
- legacy params SHA-256 unchanged:
  `3c4d6147c9647f2f5e19db7b94384306caabece0c5e62cabe9cb5af0c5148961`

## Remaining Gate

The remaining operation is a separately authorized, controlled EURUSD
`tune_wfv_aligned()` run bound to the reviewed canonical snapshot. Any selected
parameters must then face the untouched outer production WFV and all existing
calibration, validation, provenance, promotion, and activation gates.

## Decision

**WFV-ALIGNED TUNER READY — CONTROLLED EURUSD TUNING AUTHORIZED NEXT**

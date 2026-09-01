# H1 Directional RF Production Contract

## Validated Hypothesis

This source contract promotes the previously validated EURUSD hypothesis without
re-evaluating any real observation: `fixed_horizon_direction_v1` +
`stationary_v1` + the frozen Random Forest. The historical frozen holdout and
current outer result remain the only observed evidence; the current outer is
consumed.

## Contract Identity

- Model contract: `h1_direction_rf_v1`
- Symbol/timeframe eligibility: exact requested EURUSD / `H1`
- Target definition version: `1`
- Horizon: `12`
- Model family: `RandomForestClassifier`

The artifact, eligibility metadata, prediction record, and outcome record carry
explicit contract identities. Mismatches fail closed and never fall back to the
legacy interpretation.

## Target Contract

The target is terminal direction at exactly 12 complete H1 candles:
`1` when `close[t+12] > close[t]`, otherwise `0`. It is not a first-touch TP/SL
target and is not a transaction-profit claim.

## Feature Contract

The inference profile is `stationary_v1`. Its 102 ordered feature names are
bound to SHA-256
`5f51168349400e31bfe891c78a1833e1618166c478d3c0bebba983728b551791`.
H1 inference derives this profile from the model contract and rejects missing,
reordered, or mismatched features instead of zero-filling another profile.

## Random Forest Contract

The production constructor is prediction-equivalent to the frozen research
helper:

- `n_estimators=300`
- `max_depth=8`
- `min_samples_leaf=15`
- `class_weight={0: 1.0, 1: train_negative_count/train_positive_count}`
- `random_state=42`
- `n_jobs=-1`

No tuning or calibration is introduced.

## OOF Reference

Candidate construction uses the existing deterministic temporal position helper
with `window=1000`, `step=200`, `purge=20`, and `n_folds=3`. Eligibility requires
exactly three 200-row validation folds, 600 finite scores, and both classes in
every fit segment. The sorted score reference, count, SHA-256, fold geometry,
fit-class counts, and diagnostics are persisted and recomputed during artifact
validation.

## Decision Policy

`oof_quartile_abstention_v1` uses score-only empirical percentiles against the
frozen OOF reference. Percentile `>=0.75` is BUY, percentile `<=0.25` is SELL,
and the interior band is HOLD. Boundaries are inclusive; labels never optimize
the quartiles.

## Score Semantics

`rf_raw_p_up_v1` is a raw direction-ranking score, not a calibrated success
probability. The compatibility confidence is
`2 * abs(decision_percentile - 0.5)`, clipped to `[0,1]`, with semantics
`oof_percentile_extremeness_v1`. H1 surfaces do not emit or display
`est_prob_correct`.

## Predictor Dispatch

`ForexPredictor`, the CSV bridge, and the integrated prediction path dispatch
H1 artifacts to stationary features and the OOF policy. H1 does not apply the
legacy `MIN_CONFIDENCE=0.65` or ADX veto. Legacy artifacts continue through the
unchanged predictor path. Downstream ASTRA risk and Decision Engine protections
remain the final execution authority; this work does not activate automated
trading.

## Prediction Persistence

Nullable prediction columns were added for model/target/feature identity, score
type, direction score, percentile, policy, and confidence semantics. Legacy rows
and writes remain valid with NULL values in the new columns.

## Outcome Semantics

Only final BUY/SELL actions enter the pending outcome loop. H1 outcomes mature
only with all 12 exact closed H1 candles. BUY is correct for a positive terminal
move; SELL is correct for a non-positive move, including exact zero. H1 records
use `terminal_direction_at_horizon_v1`; `hit_tp` and `hit_sl` remain NULL. Legacy
strict SELL and first-touch-compatible behavior are unchanged.

## Production Eligibility

`RetrainManager` dispatches by exact model contract. Legacy candidates retain
quality, WFV, calibration, validation, model-valid, and 65% gates. H1 candidates
must satisfy the exact identity, frozen RF, OOF, dataset provenance, independent
validation, and evidence-SHA contracts. H1 does not reuse the legacy 65% gate.

## Independent Validation Gate

Protocol `post_outer_tail_v1` is frozen before any remaining tail is touched.
It requires at least 200 rows, AUC `>=0.55`, AP lift `>0`, positive AUC and AP-lift
deltas over the mean-reversion comparator, action coverage `>=0.30`, at least 20
BUY and 20 SELL signals, BUY and SELL directional precision each `>0.50`, and
pooled emitted-action precision `>=0.55`.

Evidence must bind source/snapshot hashes, validation positions/timestamps,
counts, metrics, and pass status. Its canonical SHA-256 is recomputed. Missing
evidence returns `H1_INDEPENDENT_VALIDATION_MISSING` and blocks promotion.

## Model Storage

The H1 wrapper serializes the fitted RF, resolved config, ordered features,
training class counts, training metadata/provenance, OOF diagnostics, and sorted
reference. `ModelStorage` validates these identities before staging or loading.

## Audit

`audit_pair_model()` uses the same contract-specific checks as promotion.
Tampered RF config, feature identity, OOF geometry/reference/count/hash/quartiles,
training evidence, dataset provenance, independent evidence, or SHA fails
closed. A complete synthetic H1 artifact promotes and audits as
`PRODUCTION_ELIGIBLE`; no real artifact was promoted.

## Legacy Compatibility

Models without `h1_direction_rf_v1` retain first-touch targets, legacy features,
ensemble/isotonic behavior, confidence and ADX filters, and the existing
production evidence path. No artifact is automatically migrated to H1.

## SQLite Read-Only Safety

Prediction/outcome schema migration is additive. Isolated regression tests prove
legacy readability, H1 metadata round-trip, rejection of writes in read-only
mode, and unchanged database SHA. Final read-only inspection left the real DB at
SHA-256 `1d6aff3270278096e614f096dfedbc8d199dcc8559bade7dc736128ae7ac4383`
with no WAL/SHM/journal sidecars.

## Tests

- Test-first commit: `e68294beaeeadfa380ca17999df571014d495175`
- Implementation commit: `ceafe832c2048bbacf03ee5293833277ddfa0d7f`
- New contract suites: 54 passed, 0 failed
- Focused regression suite: 251 passed, 17 subtests passed, 0 failed
- Full suite: 895 passed, 10 skipped, 23 subtests passed, 0 failed
- `python -m compileall -q .`: exit 0
- `git diff --check`: exit 0

The 10 skips are the existing five opt-in repository-dataset integrations and
five POSIX-only scheduler shell-harness cases on Windows.

## EURUSD Tail Safety

No real post-outer EURUSD observation was inspected, labeled, scored, ranked, or
used for selection. No provider fetch, canonical/qualification mutation, real
training, promotion, activation, scheduler execution, or trading occurred.
EURUSD remains `qualified`; model provenance and retrain-run counts remain zero;
`latest_EURUSD.pkl` remains absent.

## Remaining Gate

In a separate authorized task, execute the preregistered `post_outer_tail_v1`
protocol exactly once on a genuinely untouched remaining EURUSD tail. Promotion
must remain blocked unless that independent evidence passes and its identity/SHA
audit succeeds.

## Decision

H1 DIRECTIONAL RF PRODUCTION CONTRACT READY — INDEPENDENT TAIL VALIDATION AUTHORIZED NEXT

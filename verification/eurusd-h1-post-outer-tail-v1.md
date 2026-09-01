# EURUSD H1 Post-Outer Tail V1

## Contract Freeze

The one-shot validation ran on branch
`validation/eurusd-h1-post-outer-tail-v1` from report-only HEAD
`dd69d0e3e0c6d337057c9332184ed88fbb4e8913`. Executable production-contract
source remained frozen at
`ceafe832c2048bbacf03ee5293833277ddfa0d7f`.

The evaluated identity was `h1_direction_rf_v1`, target
`fixed_horizon_direction_v1` version 1 at horizon 12, feature profile
`stationary_v1`, policy `oof_quartile_abstention_v1`, score
`rf_raw_p_up_v1`, and confidence semantics
`oof_percentile_extremeness_v1`. No executable source changed before or after
tail access.

## Pre-State

Read-only SQLite inspection found EURUSD `qualified`, no
`latest_EURUSD.pkl`, zero EURUSD model-provenance rows, and zero EURUSD
retrain-run rows. The DB had no WAL/SHM sidecars and remained at SHA-256
`1d6aff3270278096e614f096dfedbc8d199dcc8559bade7dc736128ae7ac4383`
throughout precheck.

## Snapshot

`RetrainManager.capture_training_snapshot("EURUSD")` produced the required
SHA-256 `f4e77d47ab061f72a65ceb0d7733ba6d026422795119566eb5433180c5b1a3d2`.
Canonical hashes were:

- H1: `868eb4a92006de5c42fdd6465d923284f5d56a2448e740b1df38a9edc45d8f67`
- H4: `9d805c070c3a3119efdd1c1823e16e732beff7d927037e7a6aa56c653ef4f66b`
- D1: `1913093a055bfe0746b16d87305c23a5f688970538f2fab6c43240c859b49bdf`

The snapshot matched before the tail was accessed.

## Matrix Contract

Under the canonical H1/H4/D1 snapshot lock, `_load()`, `build_features()`,
and `DatasetBuilder.build()` reconstructed exactly 1,888 rows and 102 ordered
features. Feature SHA-256 was
`5f51168349400e31bfe891c78a1833e1618166c478d3c0bebba983728b551791`.

## Leakage Boundary

The maximum terminal timestamp used by a training target was
`2026-08-13T08:00:00`. Independent validation began at
`2026-08-13T17:00:00`. The strict invariant
`max_training_target_terminal_timestamp < validation_start_timestamp` passed.

## Training Partition

The final candidate was fitted exactly once on `[0,1620)`: 1,620 rows from
`2026-05-06T11:00:00` through `2026-08-12T20:00:00`. The partition contained
749 positive and 871 negative targets.

Resolved Random Forest configuration was:

```text
n_estimators=300
max_depth=8
min_samples_leaf=15
class_weight={0: 1.0, 1: 1.1628838451268357}
random_state=42
n_jobs=-1
```

There was no Optuna, calibration, tuned parameter, alternate feature set, or
second fit.

## Purge

The fixed purge was `[1620,1640)`, exactly 20 matrix rows. It was not enlarged,
reduced, or selected after observing validation evidence.

## Independent Tail

The entire remaining range `[1640,1888)` was consumed once: 248 rows from
`2026-08-13T17:00:00` through `2026-08-28T10:00:00`. It contained 120 positives
and 128 negatives, for prevalence `0.4838709677419355`.

## Candidate Identity

The in-memory candidate identity SHA-256 frozen before tail access was
`22e09f2c991f8d6c56e23dbe42a58b71a1f28ca22dc3c0aa8472e31d14f5b365`.
It bound contract/model identity, resolved RF config, feature SHA, OOF-reference
SHA, deterministic training metadata, dataset-provenance SHA, and the serialized
fitted object SHA. The fitted-object SHA was
`94004fcb3da9739180d02181c51f1b02630dd9a9d02479b7765258688b8e7eb0`.

## OOF Reference

Candidate fitting produced exactly three temporal folds, 200 validation scores
per fold, and a sorted 600-score reference. Reference SHA-256 was
`dce6b07590070853491ce69d5c3fc9ff590adf5244aa140c773f89b0a73209f9`;
q25 was `0.18777309470042766` and q75 was `0.5376209898917477`.

Training-only fold diagnostics were:

- Fold 1: AUC `0.6565656565656566`, AP `0.6432446617135206`, AP lift
  `0.14824466171352058`, BUY/SELL/HOLD `62/7/131`, coverage `0.345`, emitted
  directional precision `0.6811594202898551`.
- Fold 2: AUC `0.6299744245524297`, AP `0.6724100830634717`, AP lift
  `0.09741008306347176`, BUY/SELL/HOLD `89/4/107`, coverage `0.465`, emitted
  directional precision `0.6666666666666666`.
- Fold 3: AUC `0.6154461784713885`, AP `0.5686309044914748`, AP lift
  `0.0786309044914748`, BUY/SELL/HOLD `0/139/61`, coverage `0.695`, emitted
  directional precision `0.5539568345323741`.

These diagnostics did not alter the candidate or independent gate.

## Tail Ranking

The exact final candidate produced raw, uncalibrated direction scores once.
ROC-AUC was `0.4932942708333333`. Average precision was
`0.5321789597721076`; AP lift over tail prevalence was
`0.04830799203017211`.

## Mean-Reversion Comparator

The frozen causal 12-candle mean-reversion comparator was evaluated on the
same 248 rows. AUC was `0.47135416666666663`, AP was
`0.47043010752688175`, and AP lift was `-0.013440860215053752`.

RF minus comparator deltas were `0.021940104166666696` for AUC and
`0.06174885224522586` for AP lift. Both comparator deltas passed, but they do
not compensate for failure of the absolute AUC and action-evidence gates.

## Decision Coverage

The frozen OOF percentile policy emitted 0 BUY, 24 SELL, and 224 HOLD actions.
Coverage was `0.0967741935483871`. No threshold or abstention band was changed.

## Directional Precision

BUY precision was `0.0` because there were no BUY actions. SELL precision was
`0.3333333333333333`. Pooled emitted-action precision was
`0.3333333333333333`; HOLD observations were excluded from its denominator.

## Independent Gate

The conjunctive preregistered gate results were:

- Rows `>=200`: PASS
- AUC `>=0.55`: FAIL
- AP lift `>0`: PASS
- AUC delta `>0`: PASS
- AP-lift delta `>0`: PASS
- Coverage `>=0.30`: FAIL
- BUY count `>=20`: FAIL
- SELL count `>=20`: PASS
- BUY precision `>0.50`: FAIL
- SELL precision `>0.50`: FAIL
- Pooled precision `>=0.55`: FAIL

The independent validation result was FAIL. Canonical eligibility independently
returned `H1_INDEPENDENT_AUC_GATE`, matching the first failed canonical gate.

## Evidence SHA

The exact `post_outer_tail_v1` evidence SHA-256 was
`89615d53ce70b9c4b315560c15fbcec57aaa607f3e3071bc4629043f6ed4c838`.
Immediate canonical recomputation matched exactly.

## Promotion

Promotion was not executed. There was no retry, refit, tuning, policy change,
threshold change, or use of tail knowledge in training.

## Artifact

No candidate artifact and no `models/forex/latest_EURUSD.pkl` were created.
The pre-existing model tree and all legacy artifacts remained byte-identical.

## DB Provenance

Final read-only inspection found zero EURUSD model-provenance rows and zero
EURUSD retrain-run rows. No PENDING, RUNNING, VALIDATED, PROMOTED, or FAILED run
was created. The physical DB SHA remained
`1d6aff3270278096e614f096dfedbc8d199dcc8559bade7dc736128ae7ac4383`
with no WAL/SHM sidecars.

## Audit

`audit_pair_model()` was not called because promotion was correctly blocked.
Production eligibility is not established; the canonical pre-promotion reason
is `H1_INDEPENDENT_AUC_GATE`.

## Lifecycle

EURUSD remains `qualified`. Activation, live prediction, scheduler prediction,
OutcomeTracker live recording, Decision Engine execution, and trading were not
executed.

Canonical H1/H4/D1 bytes and registry rows, qualification evidence, legacy
parameter files, hyperparameter cache, and every pre-existing model artifact
were unchanged. Provider fetch count and canonical update count were both zero.

## Evidence Consumption

The independent tail is permanently **CONSUMED**. There was exactly one
`H1DirectionalRandomForestModel.fit()` call and exactly one tail
`predict_proba()` call. This tail cannot be reused for tuning, threshold
selection, feature changes, policy changes, retry, or validation of a revised
hypothesis.

## Statistical Interpretation

The RF retained positive AP lift and beat the weak mean-reversion comparator,
but its absolute ranking was below chance-level AUC and far below the frozen
production requirement. The quartile policy generalized asymmetrically: it
emitted no BUY actions, only 24 SELL actions, and those SELL actions were correct
one-third of the time. Both discrimination and action evidence are therefore
insufficient. This is a genuine independent rejection, not a calibration or
promotion-system failure.

## Decision

EURUSD H1 INDEPENDENT TAIL REJECTED — H1_INDEPENDENT_AUC_GATE

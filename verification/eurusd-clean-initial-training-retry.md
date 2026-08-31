# EURUSD Clean Initial Training Retry

## Previous Abort

The previous controlled attempt stopped before WFV and before any model fit
because Windows stdout used `cp1252` and could not encode the Unicode trainer
output. It created no retrain run, model provenance, staged artifact, or latest
alias. That historical result remains recorded separately in
`verification/eurusd-clean-initial-training.md`.

This task used the newly authorized candidate call exactly once. An initial
pre-candidate structural check distinguished the 1,949 rows returned by `_load`
from the 1,900 rows retained after `build_features`; it did not call the
candidate or fit a model.

## UTF-8 Runtime

PowerShell set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` before launching
Python. Before importing Forex training modules, both streams were defensively
reconfigured with strict UTF-8 handling.

- stdout encoding: `utf-8`
- stderr encoding: `utf-8`
- smoke test: PASS
- characters printed successfully: `═`, `─`, `✓`, `✗`, `⚠`, `→`, `█`

## Baseline

The retry ran on branch `fix/ifc-2020-holiday-authority` at source HEAD
`88a2eaa08ae33c0b536bd61be1a3b4b4a011473f`. The tracked working tree was
clean. EURUSD started as `qualified`; `latest_EURUSD.pkl` was absent, and model
provenance, retrain runs, and H1 model-quality rows were all zero.

No source code, thresholds, provider data, canonical dataset, scheduler state,
activation state, or trading state was changed.

## Snapshot

`capture_training_snapshot("EURUSD")` and
`validate_training_snapshot(snapshot)` reproduced the exact authorized SHA-256:

`f4e77d47ab061f72a65ceb0d7733ba6d026422795119566eb5433180c5b1a3d2`

The same snapshot was revalidated under the H1/H4/D1 locks immediately before
the candidate build. Only its exact canonical paths were loaded.

## Hyperparameter Isolation

The legacy `best_params_EURUSD.json` remained at SHA-256
`3c4d6147c9647f2f5e19db7b94384306caabece0c5e62cabe9cb5af0c5148961`
and was not used. It still has no valid binding to the current snapshot.

Before any WFV trainer existed, `_load_tuned_params` was replaced in memory
with a loader returning `{}`. The `ForexEnsembleTrainer` constructor and the
trainer class referenced by `train_with_wfv` were verified to resolve that
patched loader. A diagnostic trainer returned `_tuned == {}` and was
discarded. Every actual fold and final trainer reported `Params tuned: NO
(defaults)`, so default production hyperparameters were exercised. No tuning,
Optuna, or cache was used.

## Dataset Build

- `_load` rows after the existing gap filter: 1,949
- rows after `build_features`: 1,900
- resolved training rows: 1,756
- feature count: 87
- final `h4_*` feature count: 10
- final `d1_*` feature count: 9
- horizon: 12
- risk/reward ratio: 1.0

These values match the deterministic locked-snapshot observations.

## Quality Gate

- passed: true
- approved: true
- score: 83.0
- critical count: 0
- warning count: 2

## WFV

WFV executed with the unchanged sliding geometry: two folds, purge 20, each
with a 980-row training window after purge and a 300-row validation window.

Fold 1:

- validation size: 300
- TP: 25
- FP: 21
- signals: 46
- precision: 54.347826%
- accuracy: 40.00%

Fold 2:

- validation size: 300
- TP: 0
- FP: 0
- signals: 0
- precision: 0.00%
- accuracy: 41.00%

Aggregate evidence:

- fold count: 2
- average precision: 27.17%
- median precision: 27.17%
- pooled precision: 54.347826%
- average accuracy: 40.50%
- total TP: 25
- total FP: 21
- total signals: 46
- evidence sufficient: false
- WFV passed: false
- canonical `wfv_quality_passed`: false

The result fails closed independently on three dimensions: fold 2 has fewer
than 30 signals, pooled precision is below 65%, and both the 65% average and
70% median branches of the existing metric gate fail. No threshold was changed,
`force` was not used, and no tuning or retry followed.

## Calibration

The existing candidate path performs final training after recording WFV, even
when WFV fails. Its final calibration result was:

- executed: true
- sufficient/passed: true
- threshold: 0.6923076923
- precision at threshold: 69.230769%
- recall at threshold: 20.930233%
- signals: 39 of 246

This later calibration result cannot override failed WFV.

## Validation

- executed: true
- validation sufficient/passed: true
- accuracy: 47.154472%
- precision: 100.00%
- validation signals: 1 of 246
- `model_valid`: true

The high validation precision has only one emitted BUY signal and does not
authorize promotion because the independent WFV contract failed first.

## Candidate Metadata

Candidate identity fields are `EURUSD`, `H1`, and `initial_training`. The
candidate provenance SHA matches
`RetrainManager.dataset_provenance_sha256(provenance)`, and metadata precision
equals `eligibility.validation_precision`.

Quality, calibration, validation, and `model_valid` evidence are true. The
canonical eligibility payload correctly records `wfv_passed=false`; therefore
the candidate is not production eligible and its complete conjunctive metadata
gate is false.

## Snapshot Revalidation

The snapshot was revalidated before candidate training. Because WFV failed and
the required action was to stop without promotion, the
immediately-before-promotion revalidation was not reached. Post-run physical
hashes and registry comparison nevertheless confirm the canonical snapshot
remained unchanged.

## Promotion

Not executed. The executable latest alias remains absent. No immutable
candidate artifact was staged and no promotion run was created.

## Artifact

No artifact SHA, latest-alias SHA comparison, or stored feature-name payload is
applicable. `latest_EURUSD.pkl` remains absent.

## Provenance

Post-run database counts remain:

- model provenance rows: 0
- retrain-run rows: 0
- H1 model-quality rows: 0

## Eligibility Audit

`audit_pair_model("EURUSD")` remains fail-closed:

```text
eligible=false
reason=MODEL_NOT_DEPLOYED
```

## Canonical Safety

The H1/H4/D1 file SHA-256 values and the complete three-row ready registry are
unchanged. Qualification evidence remains unchanged at SHA-256
`9c6e6c0a08d048044f2fa8b707b567332626dabfb44219d707b59b91a8a9e59a`.
All four legacy ensemble artifacts, the quarantined legacy alias, and the
legacy parameter file are unchanged. No provider fetch or canonical update
occurred.

## Lifecycle

EURUSD remains `qualified`. No activation, prediction, trading, scheduler
cycle, or Oracle access occurred.

## Decision

**INITIAL TRAINING REJECTED — WFV**

# EURUSD Clean Initial Training

## Baseline

The controlled run was started on branch
`fix/ifc-2020-holiday-authority` at source HEAD
`1325a1e9c7f08de05b1f2f132933c002d2e3a962`. The working tree had no
tracked modifications. The accepted source-suite baseline remains 788 passed,
10 skipped, and zero failed; source code was not changed or revalidated in this
runtime-only task.

EURUSD started with lifecycle `qualified`. Model provenance, retrain runs, and
H1 model-quality rows were all zero. The executable alias
`models/forex/latest_EURUSD.pkl` was absent.

The candidate builder was invoked exactly once. It stopped before the first
model fit because the Windows `cp1252` stdout encoder could not encode the
Unicode WFV separator printed by `train_with_wfv()`. The exact exception was
`UnicodeEncodeError: 'charmap' codec can't encode characters`. The call was not
retried, preserving the one-call/one-attempt constraint.

## Canonical Snapshot

`capture_training_snapshot("EURUSD")` and its initial validation reproduced
the reviewed SHA-256
`f4e77d47ab061f72a65ceb0d7733ba6d026422795119566eb5433180c5b1a3d2`.
The snapshot was revalidated under the existing H1/H4/D1 file locks before the
candidate call.

The canonical inputs remained:

- H1: 2,000 rows, SHA-256 `868eb4a92006de5c42fdd6465d923284f5d56a2448e740b1df38a9edc45d8f67`
- H4: 2,000 rows, SHA-256 `9d805c070c3a3119efdd1c1823e16e732beff7d927037e7a6aa56c653ef4f66b`
- D1: 2,000 rows, SHA-256 `1913093a055bfe0746b16d87305c23a5f688970538f2fab6c43240c859b49bdf`

The integrated MTF load yielded 1,949 H1 frame rows after the existing gap
filter. Dataset construction yielded 1,756 resolved training rows and 87
features, including 10 final `h4_*` features and 9 final `d1_*` features.

## Legacy Hyperparameter Isolation

`models/forex/params/best_params_EURUSD.json` exists with SHA-256
`3c4d6147c9647f2f5e19db7b94384306caabece0c5e62cabe9cb5af0c5148961`.
Its top-level keys are `lgb` and `xgb`; it contains no verifiable binding to
the current canonical snapshot and was classified legacy/unverified.

For the candidate process, `_load_tuned_params` was replaced in memory with a
function returning `{}`. A diagnostic `ForexEnsembleTrainer(pair="EURUSD")`
confirmed `_tuned == {}` and was discarded. The legacy parameters were not
loaded. No actual model fit occurred, so the selected default hyperparameters
were not exercised by an estimator.

## Pair Configuration

The registered EURUSD configuration resolved without override to:

- horizon: 12 candles
- risk/reward ratio: 1.0

## Quality Gate

The candidate advanced beyond the quality gate. A read-only reproduction under
the unchanged snapshot locks recorded:

- passed: true
- approved: true
- score: 83.0
- critical count: 0
- warning count: 2

## Walk-Forward Validation

WFV did not execute. `train_with_wfv()` raised while printing its first
separator, before split evaluation or trainer construction. Consequently there
are no fold metrics, aggregates, evidence-sufficiency result, or WFV PASS/FAIL
result from this attempt. No threshold was changed and `force` was not used.

## Calibration

Not executed. There is no calibration threshold, precision, recall, signal
count, or calibration decision.

## Final Validation

Not executed. There is no final accuracy, precision, validation decision, or
`model_valid` result.

## Candidate Eligibility

No candidate object or candidate metadata was returned because execution
stopped at WFV startup. Dataset-provenance metadata therefore could not be
certified for a candidate, and no candidate was eligible for promotion.

## Snapshot Revalidation

The snapshot was revalidated before the candidate call. Because no completed
candidate existed and promotion was prohibited, there was no
immediately-before-promotion revalidation. A later read-only postcheck again
reproduced the exact original snapshot.

## Initial Promotion

Not executed. No initial-training run was created and no promotion retry was
attempted.

## Model Artifact

No staged artifact and no executable alias were created. Artifact SHA,
feature-name storage, and latest-alias SHA comparison are not applicable.

## Model Provenance

Postcheck counts remain:

- model provenance rows: 0
- retrain-run rows: 0
- H1 model-quality rows: 0

## Model Eligibility Audit

`audit_pair_model("EURUSD")` remains fail-closed:

```text
eligible=false
reason=MODEL_NOT_DEPLOYED
```

## Canonical Safety

All H1/H4/D1 physical SHA-256 values and their three ready registry rows remain
unchanged. Qualification evidence remains unchanged at SHA-256
`9c6e6c0a08d048044f2fa8b707b567332626dabfb44219d707b59b91a8a9e59a`.
No provider fetch or canonical update was performed.

## Legacy Artifact Safety

All four pre-existing ensemble files, the quarantined legacy alias, and
`best_params_EURUSD.json` retain their reviewed SHA-256 values. No legacy file
was overwritten, renamed, or deleted.

## Lifecycle State

EURUSD remains `qualified`. Activation, prediction, trading, scheduler cycles,
provider access, and Oracle access were not executed.

## Remaining Gate

A newly authorized clean initial-training attempt is still required, with a
UTF-8-capable process stdout configured before the one allowed candidate call.
All production gates (WFV, calibration, validation, `model_valid`, provenance,
and audit eligibility) remain pending and unchanged.

## Decision

**NOT EXECUTED — PRECONDITION FAILED**

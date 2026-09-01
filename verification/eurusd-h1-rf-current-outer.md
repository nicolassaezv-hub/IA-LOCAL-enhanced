# EURUSD H1 Random Forest Current Outer

## Hypothesis Freeze

This was a research-only evaluation of the frozen EURUSD hypothesis:
`fixed_horizon_direction_v1` at horizon 12, `stationary_v1`, and one fixed
`RandomForestClassifier`. There was no Optuna, parameter, feature, target,
calibration, or threshold search. The two current-outer folds were evaluated
automatically in one immutable invocation. The outer evidence is consumed.

The branch was created from
`7e1b83db5ba1f9789ea39950518b49d88d846025`. Tests were frozen in
`a9497d4675578f1779e1232fb81e38a2a2fdca96`; executable implementation and
the research gate were frozen before access to outer metrics in
`6cdce878aab9ccf7cb7b62b65628fd7bd4ac8dab`. That implementation SHA is the
`OUTER_EVALUATION_SOURCE_SHA` and was not modified after evaluation.

## Historical Evidence

The independent historical holdout had selected this hypothesis with median
ROC-AUC 0.551548 and median average-precision lift +0.056541. Its mandatory
12-candle mean-reversion comparator had median ROC-AUC 0.526276 and median AP
lift +0.013020. Those results selected the frozen hypothesis; they were not
combined with the current-outer results.

## Source Contract

The implementation is additive and non-productive. The default
`DatasetBuilder` target remains `first_touch_v1`, and existing production
calls retain their prior behavior. The research Random Forest helper is not
connected to production prediction, persistence, retraining, model
resolution, lifecycle, activation, or promotion.

## Target Contract

- Profile: `fixed_horizon_direction_v1`
- Horizon: 12 H1 observations
- Definition version: 1
- Return: `close[t+12] / close[t] - 1`
- Label: 1 when the return is strictly positive; 0 otherwise, including an
  exact zero
- Structural tail: the final 12 rows are unavailable and excluded

## Feature Contract

The matrix used the unchanged causal `stationary_v1` profile. After the
existing load, gap filter, H4/D1 causal merge, and feature/target availability
filter, it contained 1,888 rows and 102 features. The deterministic feature
identity was
`5f51168349400e31bfe891c78a1833e1618166c478d3c0bebba983728b551791`.
No whole-matrix or outer-label prevalence was inspected before the single
outer invocation.

## Random Forest Contract

The fixed constructor contract was:

```text
n_estimators=300
max_depth=8
min_samples_leaf=15
class_weight_strategy=TRAIN_NEGATIVE_TO_POSITIVE_RATIO
random_state=42
n_jobs=-1
```

At each fit, and only from that fold's training labels, the strategy resolves
to `class_weight={0: 1.0, 1: negative_count / positive_count}`. It resolved to
1.3167848699763594 for class 1 in fold 1 and 1.1491228070175439 in fold 2.
There was no scaling, calibration, SMOTE, cutoff tuning, or artifact
persistence.

## Snapshot

The required snapshot matched exactly:
`f4e77d47ab061f72a65ceb0d7733ba6d026422795119566eb5433180c5b1a3d2`.
Its canonical file hashes were H1
`868eb4a92006de5c42fdd6465d923284f5d56a2448e740b1df38a9edc45d8f67`,
H4 `9d805c070c3a3119efdd1c1823e16e732beff7d927037e7a6aa56c653ef4f66b`,
and D1 `1913093a055bfe0746b16d87305c23a5f688970538f2fab6c43240c859b49bdf`.
No provider fetch or canonical regeneration occurred.

## Outer Geometry

The unchanged dynamic walk-forward geometry produced exactly two folds with
purge 20 and 300 validation rows per fold:

- Fold 1: train `[0,980)`, validation `[1020,1320)`; train timestamps
  2026-05-06 11:00:00 through 2026-07-06 03:00:00; validation timestamps
  2026-07-07 20:00:00 through 2026-07-24 17:00:00.
- Fold 2: train `[300,1280)`, validation `[1320,1620)`; train timestamps
  2026-05-25 14:00:00 through 2026-07-23 01:00:00; validation timestamps
  2026-07-24 18:00:00 through 2026-08-12 20:00:00.

## Predeclared Gate

Before metrics were accessed, PASS required exactly two valid folds; each
fold ROC-AUC greater than 0.50; median ROC-AUC at least 0.55; each fold AP
lift greater than zero; median AP lift greater than zero; and Random Forest
median ROC-AUC and median AP lift each greater than the corresponding
mean-reversion median. The gate is research-only and is not a production
quality, calibration, validation, eligibility, or promotion gate.

## Fold 1

The 300 validation observations contained 159 positives and 141 negatives
(prevalence 0.530000). Random Forest ROC-AUC was 0.6605557785806682, AP
0.6739606660286965, AP lift +0.1439606660286965, Brier score
0.23532522175708231, accuracy at the fixed 0.5 cutoff 0.6066666666666667,
and top-10% precision 0.8000000000000000. Mean predicted probability was
0.48846908715249837 for actual positives and 0.4219704309109302 for actual
negatives.

## Fold 2

The 300 validation observations contained 153 positives and 147 negatives
(prevalence 0.510000). Random Forest ROC-AUC was 0.5944600062247122, AP
0.5776324508409432, AP lift +0.06763245084094316, Brier score
0.3151257366156356, accuracy at the fixed 0.5 cutoff 0.5466666666666666,
and top-10% precision 0.5666666666666667. Mean predicted probability was
0.3161194239724698 for actual positives and 0.26140514243922025 for actual
negatives.

## Mean-Reversion Comparator

The comparator was frozen as the causal binary score derived from the sign
opposite to `close[t] / close[t-12] - 1`; it had no fitted parameters or
tuned threshold. On fold 1 it produced ROC-AUC 0.5671082563896696, AP
0.5676797095943608, AP lift +0.03767970959436073, and accuracy
0.5666666666666667. On fold 2 it produced ROC-AUC 0.5207416299853275, AP
0.5208214604786758, AP lift +0.010821460478675826, and accuracy 0.520000.

## Aggregate Results

Random Forest median/mean/worst ROC-AUC were
0.6275078924026902/0.6275078924026902/0.5944600062247122. Median and mean AP
lift were both +0.10579655843481983. Both folds exceeded ROC-AUC 0.50 and
both had positive AP lift.

Mean reversion had median ROC-AUC 0.5439249431874985 and median AP lift
+0.02425058503651828. Random Forest therefore exceeded it by
+0.08358294921519172 median ROC-AUC and +0.08154597339830155 median AP lift.
Every conjunct of the preregistered research gate passed.

## Optional Uncertainty

A diagnostic moving-block bootstrap used blocks of 24 labeled H1
observations, 2,000 valid resamples per fold, and fixed seeds 43 and 44. It
did not affect the gate. Fold 1's 95% intervals were
`[0.5588436428459476, 0.7556798196601543]` for ROC-AUC and
`[0.04426377506358115, 0.24994002706163532]` for AP lift. Fold 2's were
`[0.43768281396731207, 0.784012567492844]` and
`[-0.04291118767956212, 0.2785500446932773]`, respectively.

## Statistical Interpretation

The point estimates pass the frozen current-outer gate and beat the required
trivial comparator on both aggregate ranking measures. The fold-2 bootstrap
intervals nevertheless cross the null values for both metrics. With only two
300-row outer blocks, this is validation of a narrow research hypothesis,
not proof of stable production performance or calibrated trading utility.
The current outer may not be reused to tune this target, feature set, model,
parameters, cutoff, or future production gates.

## Production Implications

The result justifies separately authorized production-contract engineering.
That work would need preregistered decision, calibration, validation,
statistical-evidence, lifecycle, eligibility, persistence, and promotion
contracts, followed by genuinely new independent evidence. The legacy
first-touch production path and all existing production gates remain
unchanged. This evaluation created no production model and authorizes no
activation, prediction, promotion, or trading.

## Safety

During the immutable outer invocation, pre/post fingerprints were identical:
canonical `fda7e99649e6129e70d084c33c6f582f60e883060582d583c3786821c369e83f`,
qualification evidence
`a9bdc270404b2fd13ee20a1a7183893f02760c1485e287ccc4fc3ccceece8ab9`,
legacy models
`f8e62fedd418d0b21ad27a702914f38bd94c347d56356eeb1768c6dc9d4f7d81`,
and SQLite
`969809216611c5004d0a712c1b2317e73cd36ea8e37dd2a82603035146553f4c`.
The hyperparameter cache remained absent. No model artifact, candidate,
`latest_EURUSD.pkl`, provider fetch, activation, prediction, or trade was
created or executed. EURUSD remained `qualified`.

There is one safety exception to the requested whole-task invariant. Before
outer evaluation, snapshot validation instantiated the existing writable
SQLite adapter through `RetrainManager`; its schema initialization rewrote
the main database file from physical SHA-256
`acc3482911a78363b0bf8faa4f026f25d51f667b995e1fca2eec6493d31a0b65`
to `969809216611c5004d0a712c1b2317e73cd36ea8e37dd2a82603035146553f4c`.
Read-only verification found no logical lifecycle, model-quality, retrain-run,
or other application-row change, and the evaluation itself used SQLite
read-only and caused no further byte change. This physical mutation is
reported rather than hidden; no attempt was made to reverse or rewrite it.

## Decision

**H1 RANDOM FOREST CURRENT OUTER VALIDATED**

The remaining gate is production-contract engineering plus genuinely new
independent evidence. The current outer is consumed.

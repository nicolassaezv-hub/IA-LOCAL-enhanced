# EURUSD Inner Signal Collapse Diagnosis

## Baseline

The diagnostic ran on branch `fix/wfv-aligned-hyperparameter-tuning` at source
HEAD `cfeccaee75bed37b2287c5aa1c70096ac1716fc7`, starting from a clean tracked
working tree. It used the previously authorized EURUSD snapshot and did not
run Optuna, tuning, outer WFV, promotion, activation, prediction, trading, or a
provider fetch.

The exact matrix rebuilt to 1,756 rows and 87 features with the unchanged
horizon 12 and risk/reward ratio 1.0. Each inner fold was trained once with
the explicit override `{}`, so no legacy parameter file was used. Both
diagnostic trainers used `save=False`.

## Data Isolation

`capture_training_snapshot("EURUSD")` and `validate_training_snapshot()`
matched the authorized snapshot SHA-256:

`f4e77d47ab061f72a65ceb0d7733ba6d026422795119566eb5433180c5b1a3d2`

After rebuilding the matrix, the diagnostic copied positions `[0,980)` and
discarded its references to the full feature/target matrix. Every balance,
probability, ranking, top-k, and drift computation used only this copy. No
feature value, target, probability, model result, or statistic from position
980 onward was inspected. The reserved outer ranges `[1020,1320)` and
`[1320,1620)` remain untouched and unconsumed.

## Target Balance

Inner fold 1:

- input training `[0,480)`: 217 positive, 263 negative, 45.208333% positive
- model fit `[0,408)`: 180 positive, 228 negative, 44.117647% positive
- calibration `[408,480)`: 37 positive, 35 negative, 51.388889% positive
- external validation `[520,720)`: 82 positive, 118 negative, 41.000000% positive

Inner fold 2:

- input training `[200,680)`: 222 positive, 258 negative, 46.250000% positive
- model fit `[200,608)`: 202 positive, 206 negative, 49.509804% positive
- calibration `[608,680)`: 20 positive, 52 negative, 27.777778% positive
- external validation `[720,920)`: 89 positive, 111 negative, 44.500000% positive

The observed 55.5% accuracy of an all-zero fold-2 predictor is exactly the
111/200 negative rate. Fold 2 is not globally target-starved; its external
validation contains 89 positives. Its 72-row calibration segment, however,
has a substantially lower positive rate than both model fit and validation.

## Fold 1

The fold received 480 training rows, internally split into 408 model-fit and
72 calibration rows, followed by 200 external validation rows.

Calibration learned threshold 0.846153846. On its calibration data it emitted
14 signals with 85.714286% precision and 32.432432% recall, and marked
calibration sufficient. On external validation it emitted 138 signals.

Raw ranking on external validation was weak: ROC-AUC 0.526354 and average
precision 0.444557 against a 0.410000 positive prevalence. Mean raw probability
was 0.796531 for positives and 0.774246 for negatives.

## Fold 2

The fold received 480 training rows, internally split into 408 model-fit and
72 calibration rows, followed by 200 external validation rows.

Calibration learned effective threshold 0.900000000. On calibration it emitted
only 2 signals, with 100.000000% precision and 10.000000% recall, and marked
calibration sufficient. On external validation it emitted exactly 0 signals.

The zero-signal outcome is not caused by a lack of external positives: 89 of
200 targets are positive. It is reproduced directly because the maximum
calibrated external probability is only 0.283333333, far below the 0.9
threshold.

Raw ranking also fails to provide a useful fallback explanation. Fold-2 raw
ROC-AUC is 0.457941 and average precision is 0.439372, slightly below the
44.500000% target prevalence. Mean raw probability is nearly identical for
positives (0.847489) and negatives (0.845449).

## Calibration Thresholds

- fold 1: threshold 0.846153846; calibration precision 85.714286%; recall
  32.432432%; signals 14/72; sufficient `true`
- fold 2: threshold 0.900000000; calibration precision 100.000000%; recall
  10.000000%; signals 2/72; sufficient `true`

Fold 2 therefore demonstrates a small-sample calibration decision: two
calibration signals satisfy the existing precision/recall contract, while the
same threshold produces no external signal. This is diagnostic evidence only;
no gate or threshold was changed.

## Raw Probability Distribution

External fold 1 raw p(BUY):

- min 0.298765; p05 0.476809; p25 0.704344; median 0.848567
- p75 0.892222; p95 0.918488; max 0.932987; mean 0.783383

External fold 2 raw p(BUY):

- min 0.526619; p05 0.749192; p25 0.826170; median 0.857013
- p75 0.881702; p95 0.904645; max 0.921308; mean 0.846357

Fold-2 raw scores are high in absolute terms but do not separate classes.
Their location is also strongly shifted relative to the model-fit scores.

## Calibrated Probability Distribution

External fold 1 calibrated p(BUY):

- min 0.250000; p05 0.321429; p25 0.600000; median 0.846154
- p75 1.000000; p95 1.000000; max 1.000000; mean 0.792486

External fold 2 calibrated p(BUY):

- min 0.192662; p05 0.283333; p25 0.283333; median 0.283333
- p75 0.283333; p95 0.283333; max 0.283333; mean 0.282378

At least 95% of fold-2 external values occupy the same 0.283333 plateau.
None approaches the learned threshold.

## Threshold Margins

Margin is calibrated p(BUY) minus the unchanged learned threshold.

- fold 1: min -0.596154; median 0.000000; p95 0.153846; max 0.153846
- fold 2: min -0.707338; median -0.616667; p95 -0.616667; max -0.616667

Fold 2 has a strictly negative maximum margin. The zero-signal collapse is
therefore exact threshold separation, not a counting or reporting defect.

## Ranking Quality

Fold 1 external validation:

- raw ROC-AUC 0.526354; raw average precision 0.444557
- calibrated ROC-AUC 0.519585; calibrated average precision 0.420654
- raw mean p(BUY): positives 0.796531, negatives 0.774246

Fold 2 external validation:

- raw ROC-AUC 0.457941; raw average precision 0.439372
- calibrated ROC-AUC 0.512602; calibrated average precision 0.451314
- raw mean p(BUY): positives 0.847489, negatives 0.845449

The calibrated fold-2 ROC-AUC near 0.5 is driven by a highly tied mapping and
does not imply actionable discrimination. Raw evidence is below random AUC,
average precision does not beat prevalence, and class means are effectively
the same.

## Top-K Diagnostic

These are ranking diagnostics only and are not signal rules.

Fold 1 by raw p(BUY):

- top 10%: 20 rows, 11 positives, 55.000000% precision
- top 15%: 30 rows, 17 positives, 56.666667% precision
- top 20%: 40 rows, 18 positives, 45.000000% precision

Fold 2 by raw p(BUY):

- top 10%: 20 rows, 10 positives, 50.000000% precision
- top 15%: 30 rows, 11 positives, 36.666667% precision
- top 20%: 40 rows, 13 positives, 32.500000% precision

Fold 2 has no stable top-ranked concentration of positives. Its modest top-10%
result reverses at 15% and 20%.

## Isotonic Mapping

- fold 1: 10 isotonic X/Y breakpoints; 7 unique calibrated values on
  calibration and 11 on external validation; external range 0.25 to 1.0
- fold 2: 8 isotonic X/Y breakpoints; 4 unique calibrated values on
  calibration and 5 on external validation; external range 0.192662 to
  0.283333

Fold 2 shows material quantization. Although five exact values exist, nearly
the entire external distribution is mapped to one plateau. The calibration
set can reach 1.0, but the external set never exceeds 0.283333.

## Feature Drift

The shift metric is the signed difference `mean(fold2) - mean(fold1)` divided
by the square root of the average sample variance of both 200-row validation
windows. The 15 largest absolute shifts are:

```text
h4_ema20        -6.027289
EMA50           -5.307675
h4_ema50        -5.178436
EMA200          -5.170571
d1_macd         -4.936750
d1_ema20        -4.150419
EMA20           -4.024648
h4_ema200       -3.958864
rolling_mean_20 -3.860398
d1_ema50        -3.795583
BB_upper        -3.792155
d1_close        -3.672288
close_lag_10    -3.610788
rolling_mean_10 -3.605049
d1_ema200       -3.508094
```

These are unusually large distribution shifts, concentrated in price-level,
moving-average, and MTF features. They support a substantial inner regime
shift, while not by themselves proving causality for target direction.

## Target Drift

Sequential target rates inside `[0,980)` were:

- `[0,200)`: 82/200 = 41.000000%
- `[200,400)`: 91/200 = 45.500000%
- `[400,600)`: 105/200 = 52.500000%
- `[600,800)`: 72/200 = 36.000000%
- `[800,980)`: 82/180 = 45.555556%

The target is not globally imbalanced, but its local rate changes materially.
For fold 2 specifically, the rate moves from 49.509804% on model fit to
27.777778% on calibration and then to 44.500000% on external validation.

The fold-2 raw median simultaneously moves from 0.309490 on model fit to
0.853725 on calibration and 0.857013 on validation. The largest score-location
shift occurs model-fit to calibration; target prevalence then changes sharply
again calibration to validation. The isotonic map learned from the small,
low-positive calibration slice maps the external distribution to the 0.283333
plateau.

## Root Cause

The exact zero-signal mechanism is
`CALIBRATION_QUANTIZATION_FAILURE` combined with
`CALIBRATION_THRESHOLD_PORTABILITY_FAILURE`: the fold-2 mapping compresses
external values below 0.283334 while the calibration-selected threshold is
0.9.

This is not the only statistical problem. `MODEL_DISCRIMINATION_FAILURE` is
independently present because raw fold-2 ROC-AUC is below 0.5, average precision
is below prevalence, class means are nearly equal, and top-k precision is not
stable. `INNER_REGIME_SHIFT` is a contributing factor supported by large
feature shifts and unstable local target rates. `TARGET_IMBALANCE_FAILURE` is
not supported because external fold 2 contains 89 positives.

The appropriate classification is `MULTIPLE_CAUSES`, ranked:

1. calibration quantization and threshold portability explain the exact zero
   signals;
2. raw model discrimination failure means a threshold-only remedy would not
   create reliable signal;
3. inner feature/target regime shift plausibly drives both failures.

## Recommended Remediation

Do not lower the threshold and do not weaken any production gate. A future
test-first task should examine calibration hardening with a larger or
rolling/out-of-fold calibration sample, compare isotonic with a less quantized
Platt/sigmoid mapping, and require minimum calibration evidence plus explicit
threshold-portability/coverage evidence.

Because raw discrimination also fails, calibration work alone is insufficient.
The next research path should add independent history and test a more
regime-robust feature/model hypothesis, especially the portability of absolute
price-level and MTF features. None of these hypotheses is implemented here.

## Outer Evidence Safety

Outer rows were not inspected and outer evidence was not consumed. The
canonical H1/H4/D1 hashes, complete registry, all model files, model-provenance
count, retrain-run count, missing latest alias, and `qualified` lifecycle state
were unchanged after diagnosis. No model was created.

## Decision

**ROOT CAUSE FOUND — MULTIPLE FACTORS**

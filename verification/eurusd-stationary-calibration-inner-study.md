# EURUSD Stationary Feature / Calibration Study

## Baseline

This inner-only study ran on branch
`research/eurusd-stationary-features-calibration`, based on
`630059091c2ad221bb02c4e35e74ed1f424b529b`. The source changes are split into
the test-first commit `817edd622031329986954781e3e15cebba27e04d` and the
implementation commit `52ccc9d33fd9f5c4a62c5d4082018f91cd807cd3`.

The authorized snapshot reproduced the exact SHA-256
`f4e77d47ab061f72a65ceb0d7733ba6d026422795119566eb5433180c5b1a3d2`.
The legacy matrix remained exactly 1,756 rows by 87 ordered features. Its
ordered feature-name identity is
`1a73ea42879bc3049d337dbcfd1ad71b3017a3b6845d9877a2836a23058e9136`.
Horizon 12, risk/reward ratio 1.0, model defaults `{}`, seed 42, target logic,
SMOTE behavior, WFV gates, calibration gate, and validation gate were not
changed.

The known legacy/isotonic baseline was reproduced exactly: fold-2 raw ROC-AUC
0.457941, average precision 0.439372, threshold 0.900000, calibrated maximum
0.283333, and zero external signals.

## Outer Isolation

Only the authorized tuning pool `[0,980)` was copied for experimental use.
The complete-matrix references were then discarded before any fit, metric,
probability, balance, or drift calculation. The only folds used were:

- fold 1: train `[0,480)`, external validation `[520,720)`;
- fold 2: train `[200,680)`, external validation `[720,920)`.

No position at or above 980 was used or inspected by an experiment. In
particular, the reserved outer ranges `[1020,1320)` and `[1320,1620)` were not
evaluated, scored, calibrated, or used for selection. This study makes no
production-candidate selection.

## Legacy Feature Inventory

The exact 87-feature legacy input, classified by statistical character, is:

**A. Stationary, bounded, binary, or row-normalized (40):** `RSI_14`,
`h4_rsi`, `h4_return5`, `h4_trend`, `d1_rsi`, `d1_return5`, `d1_trend`,
`body_strength`, `upper_shadow`, `lower_shadow`, `ADX_14`, `plus_DI`,
`minus_DI`, `stoch_k`, `stoch_d`, `stoch_cross`, `williams_r`, `bb_squeeze`,
`bb_pct_b`, `pattern_doji`, `pattern_hammer`, `pattern_shooting_star`,
`pattern_bull_engulf`, `pattern_bear_engulf`, `ema20_above_50`,
`ema_cross_signal`, `ema50_above_200`, `rsi_overbought`, `rsi_oversold`,
`price_vs_ema200`, `price_in_range_50`, `atr_ratio`, `atr_expansion`,
`trend_align_score`, `close_vs_h4`, `rsi_divergence`, `candle_body_ratio`,
`momentum_accel`, `volume_relative`, `h4_rsi_extreme`.

**B. Approximately stationary but not bounded (4):** `volume`, `rsi_slope`,
`tick_vol_flow_diverge`, `obv_diverge`. The last name duplicates the same
divergence series and is not retained by stationary_v1.

**C. Absolute price-level or raw price-unit features (33):** `open`, `high`,
`low`, `close`, `EMA20`, `EMA50`, `EMA200`, `BB_upper`, `BB_lower`, `h4_atr`,
`h4_ema20`, `h4_ema50`, `h4_ema200`, `h4_macd`, `h4_close`, `d1_atr`,
`d1_ema20`, `d1_ema50`, `d1_ema200`, `d1_macd`, `d1_close`, `close_lag_1`,
`close_lag_2`, `close_lag_3`, `close_lag_5`, `close_lag_10`,
`rolling_mean_5`, `rolling_mean_10`, `rolling_mean_20`, `trend_strength`,
`momentum_5`, `momentum_10`, `bb_width`.

**D. Cumulative/nonstationary levels (4):** `tick_vol_flow`,
`tick_vol_flow_ema`, `obv`, `obv_ema`.

**E. Temporal categorical (6):** `hour`, `day_of_week`, `session`,
`session_tokyo`, `session_london`, `session_newyork`.

The category totals A-E equal exactly 87. The profile comparison itself is
the authoritative identity and removes 38 legacy names: all 33 category-C
names, all four category-D names, and the redundant `obv_diverge` feature.

## Stationary V1

`DatasetBuilder.build(..., feature_profile="legacy")` remains the default.
The additive `stationary_v1` profile contains 102 ordered features and has
feature-name SHA-256
`5f51168349400e31bfe891c78a1833e1618166c478d3c0bebba983728b551791`.
It has the same 1,756 row indices and targets as legacy.

The profile removes 38 raw absolute/cumulative legacy features and adds 44
explicit row-local or trailing-only normalized replacements:

- OHLC structure: `open_vs_close`, `high_vs_close`, `low_vs_close`,
  `range_pct`, `body_pct`;
- EMA structure: `close_vs_ema20`, `close_vs_ema50`, `close_vs_ema200`,
  `ema20_vs_50`, `ema50_vs_200`, `trend_strength_pct`;
- lag/rolling structure: five `close_vs_lag_*`, three
  `close_vs_rollmean_*`, and three `rolling_std_pct_*` features;
- normalized momentum/volatility: `momentum_pct_5`, `momentum_pct_10`,
  `bb_width_pct`, `atr_pct`, `macd_pct`, `macd_signal_pct`, `macd_hist_pct`,
  `spread_pct`;
- H4 and D1 context: seven normalized features per timeframe covering close
  versus EMAs, EMA spreads, ATR, and MACD.

Nine already-existing relative features that legacy's absolute variance
cutoff removed are retained by the stationary profile's positive-variance
contract: `returns`, `volatility_24h`, five `returns_lag_*` features,
`volatility_regime`, and `ema20_slope`. This explains the net feature-count
change: 87 - 38 + 44 + 9 = 102. No future/global scaler is fitted.

## Calibration Strategies

`ForexEnsembleTrainer` now accepts `calibration_method`. The default remains
`isotonic`, preserving production behavior. The experimental `sigmoid` path
fits a logistic/Platt mapping from raw ensemble p(BUY) to the calibration
target using only the trainer's calibration block. It exposes the same
`predict_proba`, `predict`, threshold, precision, recall, signal count, and
`sufficient` interface. External validation is never used to fit calibration
or choose a threshold.

## Calibration Evidence

The additive diagnostic requires at least 60 calibration rows and at least
`ceil(calibration_size * 0.10)` signals at the effective threshold. Every
fold had 72 calibration rows and therefore required eight signals. This
diagnostic deliberately does not redefine the existing `sufficient` gate.

- Config A: fold 1 `14/72`, evidence sufficient; fold 2 `2/72`, insufficient.
- Config B: fold 1 `3/72`, insufficient; fold 2 `2/72`, insufficient.
- Config C: fold 1 `14/72`, evidence sufficient; fold 2 `2/72`, insufficient.
- Config D: fold 1 `9/72`, evidence sufficient; fold 2 `2/72`, insufficient.

The separate inner evidence contract required at least 20 external signals in
each 200-row fold. No configuration met that contract in both folds.

## Experiment Matrix

Exactly four deterministic configurations were run, once per inner fold, with
default model hyperparameters `{}`:

- A: legacy + isotonic;
- B: stationary_v1 + isotonic;
- C: legacy + sigmoid;
- D: stationary_v1 + sigmoid.

No Optuna search, outer WFV, provider fetch, production validation, promotion,
activation, prediction, or trading was executed. Every trainer used
`save=False`.

## Config A

Fold 1 had 82 positives and 118 negatives. Raw ROC-AUC/AP were
0.526354/0.444557; calibrated ROC-AUC/AP were 0.519585/0.420654. Calibration
selected threshold 0.846154 with 14 signals and sufficient diagnostic
evidence. External validation emitted 138 signals at 42.028986% precision and
48.000000% accuracy. The maximum threshold margin was 0.153846 and calibrated
range was 0.250000 to 1.000000.

Fold 2 had 89 positives and 111 negatives. Raw ROC-AUC/AP were
0.457941/0.439372; calibrated ROC-AUC/AP were 0.512602/0.451314. Calibration
selected threshold 0.900000 with only two signals and insufficient diagnostic
evidence. External validation emitted zero signals, 0% precision, and
55.500000% accuracy. The maximum threshold margin was -0.616667 and calibrated
range was 0.192662 to 0.283333.

Aggregate average/median precision was 21.014493%, pooled precision was
42.028986% over 138 signals, inner evidence was insufficient, and the
WFV-like gate failed.

## Config B

Fold 1 had raw ROC-AUC/AP 0.544647/0.463925 and calibrated ROC-AUC/AP
0.520308/0.435853. Threshold 0.900000 came from only three calibration
signals, so calibration evidence was insufficient. External validation
emitted 41 signals at 46.341463% precision and 57.500000% accuracy; maximum
margin was 0.100000 and calibrated range was 0 to 1.

Fold 2 had raw ROC-AUC/AP 0.468367/0.451812 and calibrated ROC-AUC/AP
0.463154/0.430051. Threshold 0.900000 came from two calibration signals and
insufficient evidence. External validation emitted 16 signals at 37.500000%
precision and 53.500000% accuracy; maximum margin was 0.100000 and calibrated
range was 0 to 1.

Aggregate average/median precision was 41.920732%, pooled precision was
43.859649% over 57 signals. Fold 2 missed the 20-signal inner evidence floor;
inner evidence was insufficient and the WFV-like gate failed.

## Config C

Raw ranking was necessarily identical to A. Fold-1 raw ROC-AUC/AP were
0.526354/0.444557 and calibrated ROC-AUC/AP were also 0.526354/0.444557.
Threshold 0.549563 used 14 calibration signals with sufficient evidence.
External validation emitted 138 signals at 42.028986% precision and
48.000000% accuracy. Calibrated range was 0.435245 to 0.591956 and maximum
margin was 0.042393.

Fold-2 raw and calibrated ROC-AUC/AP were 0.457941/0.439372. Threshold
0.286302 used two calibration signals, so evidence was insufficient. The
external calibrated range was continuous, 0.260755 to 0.285364, but its
maximum margin remained negative at -0.000938 and it emitted zero signals.

Aggregate average/median precision was 21.014493%, pooled precision was
42.028986% over 138 signals, inner evidence was insufficient, and the
WFV-like gate failed. Sigmoid removed isotonic quantization but did not make
the legacy fold-2 threshold portable.

## Config D

Raw ranking was identical to B. Fold-1 raw ROC-AUC/AP were
0.544647/0.463925. Calibrated ROC-AUC/AP fell to 0.455353/0.378084, consistent
with an inverse Platt slope learned on that calibration block. Threshold
0.547250 used nine calibration signals with sufficient diagnostic evidence.
External validation emitted 34 signals at 29.411765% precision and 52.000000%
accuracy; calibrated range was 0.472033 to 0.576347 and maximum margin was
0.029097.

Fold-2 raw and calibrated ROC-AUC/AP were 0.468367/0.451812. Threshold
0.281461 used two calibration signals and insufficient evidence. External
validation emitted 14 signals at 42.857143% precision and 54.500000% accuracy;
calibrated range was 0.271915 to 0.281833 and maximum margin was 0.000372.

Aggregate average/median precision was 36.134454%, pooled precision was
33.333333% over 48 signals. Fold 2 missed the 20-signal floor; inner evidence
was insufficient and the WFV-like gate failed.

## Drift Comparison

The standardized shift is `(mean(fold2)-mean(fold1))` divided by the square
root of the average sample variance across the two 200-row validation windows.

- legacy: maximum absolute shift 6.027289, median 0.249154, 32 features above
  1, and 30 above 2;
- stationary_v1: maximum absolute shift 5.394362, median 0.129884, 11 features
  above 1, and 6 above 2.

Stationary_v1 reduced median shift by about 47.9% and the count above 2 by
80%, but did not eliminate severe drift. Its largest remaining shifts were
`h4_ema50_vs_200` (5.394362), `d1_macd_pct` (4.957872),
`d1_ema20_vs_50` (4.738706), `d1_ema50_vs_200` (3.864349), and
`d1_close_vs_ema200` (3.322233).

## Discrimination Comparison

Stationary_v1 improved fold-1 raw ROC-AUC from 0.526354 to 0.544647
(+0.018293) and AP from 0.444557 to 0.463925 (+0.019367). On the critical
fold 2 it improved ROC-AUC from 0.457941 to 0.468367 (+0.010426) and AP from
0.439372 to 0.451812 (+0.012440).

The direction is favorable but not material evidence of solved
discrimination: fold-2 ROC-AUC remains below 0.5, no configuration meets
inner evidence, and all pooled precisions remain far below 65%. B and D tie
for the best raw-discrimination configuration because calibration does not
alter the underlying ensemble.

## Calibration Portability

Sigmoid generated 200 unique external probabilities rather than isotonic
plateaus, but continuity alone did not improve outcome quality. With legacy
features, C still emitted zero fold-2 signals. With stationary features, D
emitted 14 fold-2 signals, fewer than B's 16, and had worse pooled precision
(33.333333% versus 43.859649%). It also inverted fold-1 ranking after fitting
to the small calibration block.

B is the least-bad portability result because both folds emit signals and it
has the highest pooled precision among configurations with nonzero signals in
both folds. It is not eligible: both calibration evidence diagnostics fail,
fold 2 misses the inner signal floor, and quality metrics fail.

## Recommended Production Hypothesis

Keep legacy/isotonic as the unchanged production defaults and do not consume
outer evidence. The next research hypothesis should combine more independent
history with a refined stationary/regime-aware feature design and larger or
out-of-fold calibration evidence. Stationary_v1 is worth further inner-only
study because it materially reduces aggregate location drift, but the present
version does not solve raw fold-2 discrimination. Calibration-only changes
are not supported: sigmoid changes coverage/quantization without reliable
precision or portable evidence.

## Outer Evidence Safety

Pre/post safety fingerprints were identical for canonical H1/H4/D1 files,
the complete EURUSD qualification evidence tree, the complete Forex model and
parameter tree, the hyperparameter cache, and the SQLite database file.
EURUSD remained `qualified`; `latest_EURUSD.pkl` remained absent; EURUSD model
provenance, retrain runs, and H1 model-quality row counts remained zero. No
model, candidate, parameter, cache, canonical, qualification, or DB artifact
was created or modified. Outer evidence remains unconsumed.

## Decision

**INNER RESEARCH COMPLETE — MIXED_RESULT**

Stationary_v1 reduces measured drift and modestly improves raw ranking, but
the critical fold remains below-random by ROC-AUC and no configuration has
sufficient inner evidence. Sigmoid does not independently improve threshold
portability or precision. These results justify further inner research, not
outer evaluation or production selection.

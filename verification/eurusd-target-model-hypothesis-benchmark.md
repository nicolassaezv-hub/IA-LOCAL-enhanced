# EURUSD Target / Model Hypothesis Benchmark

## Historical Motivation

The preceding independent-history audit concluded `SYSTEMIC MODEL
DISCRIMINATION FAILURE`: the existing first-touch target and current ensemble
were centered near random discrimination under both legacy and
`stationary_v1` features. This benchmark therefore asks whether the limiting
factor is the target, the model family, or the available feature information.

This was a research-only run from source HEAD
`d0c6b12a971c6751d37aded68026c90f264fa80e` on branch
`research/eurusd-target-model-hypotheses`. No production source, target,
threshold, model, parameter, dataset, qualification artifact, lifecycle
state, or database row was changed.

## Evidence Boundaries

MT5 was used directly against `IFCMarkets-Demo` with `allow_fallback=False`.
The requests were 12,000 H1, 4,000 H4, and 2,000 D1 candles. Each returned
frame was restricted immediately to `timestamp <= 2025-10-31 23:59:59`
before indicators, MTF joins, features, targets, statistics, or model fits.
The retained counts were 6,983 H1, 2,724 H4, and 1,787 D1 candles.

The development protocol ended at `2025-07-31 23:59:59`. The common usable
feature/target range was `2024-09-11 20:00:00` through
`2025-07-31 11:00:00`; the earlier terminal time is the causal twelve-candle
target tail. Historical holdout was reserved before fitting as
`2025-08-01 00:00:00` through `2025-10-31 23:59:59`. Its usable target rows
ended at `2025-10-31 08:00:00` for the same reason.

All intermediate CSVs lived in a `TemporaryDirectory`. The production
indicator implementation was applied over the already bounded frames. The
existing `_load()` merge used H4 only after open plus four hours and D1 only
after open plus one day. An independent check found zero H4 and zero D1
lookahead violations.

No November 2025, 2026, current-inner, or current-outer feature value, target,
fit, statistic, or metric entered this experiment.

## Development / Holdout Protocol

The primary representation was the existing 102-column `stationary_v1`
profile. The only legacy continuity case was H0 plus the existing raw default
ensemble. All transformations were causal; each StandardScaler was fit only
on its fold's training rows.

Exactly six deterministic development folds used the unchanged
`WalkForwardValidator(window=500, step=200, purge=20, n_folds=6)` geometry.
Each H1/H2 validation block contained 200 non-overlapping rows. H0 was
evaluated on the same temporal blocks and retained 191, 187, 194, 197, 195,
and 185 resolved labels after its predeclared timeout/ambiguity exclusion.
Training always preceded validation. No validation threshold was selected.

Two deterministic, non-overlapping holdout blocks were reserved before the
development screen: `2025-08-01 00:00:00` to `2025-08-13 17:00:00` and
`2025-10-20 19:00:00` to `2025-10-31 08:00:00`, 200 rows each. Their labels
and metrics were not materialized until after the development screen and
shortlist freeze. Models were not tuned after holdout access.

Classification development eligibility was fixed at median AUC at least
0.55, AUC above 0.50 in at least four of six folds, and median AP lift at
least +0.02. Regression eligibility was fixed at median Spearman IC at least
+0.05, at least four positive-IC folds, and at least four positive-spread
folds. These are research screens, not production gates.

## Target H0

H0 used `DatasetBuilder` unchanged: horizon 12, risk/reward 1.0, first
+ATR touch is class 1, first -ATR touch is class 0, and unresolved or
intrabar-ambiguous observations are excluded. It produced 4,903 usable
development rows from 5,224 structurally labelable rows: exclusion rate
6.144717% and positive prevalence 51.641852%.

## Target H1

H1 was research-only fixed-horizon direction:

`future_return_12 = close[t+12] / close[t] - 1`

The label is 1 when that return is positive and 0 otherwise, with no neutral
zone. It produced 5,224 development rows and positive prevalence 49.808576%.
No production target implementation was changed.

## Target H2

H2 was research-only ATR-normalized terminal return:

`future_atr_return_12 = (close[t+12] - close[t]) / ATR_14[t]`

ATR came only from row `t`. The 5,224 development targets had mean
-0.060550, median -0.009817, standard deviation 2.940305, and 49.808576%
positive values. No clipping or global target normalization was used.

## Trivial Baselines

For H1, majority-class development median AUC/AP lift was 0.500000/0.000000.
Past-12-candle momentum was 0.413470/-0.034162. Its opposite, mean reversion,
was the strongest trivial development baseline at 0.586530/+0.043676, with
five of six folds above AUC 0.50.

The mean-reversion result is material: H1 Random Forest did not beat it on
development median AUC, although the model had much stronger median AP lift
(+0.107908 versus +0.043676). The predeclared holdout comparison resolves
that ambiguity. On holdout, mean reversion had fold AUCs 0.538462 and
0.514090, median 0.526276, and median AP lift +0.013020. Momentum had median
AUC 0.473724 and median AP lift -0.011769; majority remained 0.500000/0.

For H2, zero prediction supplied no ranking information and the causal
previous-12-return predictor did not meet the regression screen consistently.
The learned regressors beat those development references, but none retained
positive IC on holdout.

## Development Classification Results

Every classifier used raw probabilities for AUC/AP. Accuracy used only the
fixed 0.5 diagnostic cutoff. Each fold also recorded Brier score, top-decile
precision, and mean p(positive) by actual class.

H0's strongest development result was the legacy current raw ensemble:
median/mean AUC 0.536664/0.527076, median AP lift +0.055980, four of six folds
above 0.50, three at or above 0.55, and five with AP above prevalence. It
failed because median AUC was below 0.55. LogisticRegression, XGBClassifier,
RandomForestClassifier, and the raw ensemble under `stationary_v1` also
failed the conjunctive screen; no H0 hypothesis entered holdout.

H1 fold records follow. `p+` and `p-` are mean raw p(positive) on actual
positive and negative rows.

- LogisticRegression: fold AUCs 0.581706, 0.383583, 0.416600, 0.548589,
  0.590020, 0.614210; AP lifts +0.103262, -0.039554, +0.032259, +0.031873,
  +0.041908, +0.111232. Median/mean AUC were 0.565148/0.522451 and median AP
  lift +0.037083; four folds exceeded 0.50 and five had positive AP lift.
  It passed.
- XGBClassifier: fold AUCs 0.586914, 0.484386, 0.669912, 0.477743,
  0.608641, 0.417546; AP lifts +0.114203, +0.101208, +0.160933, +0.039650,
  +0.140968, -0.000547. Median/mean AUC were 0.535650/0.540857 and median AP
  lift +0.107706. Only three folds exceeded 0.50, so it failed.
- RandomForestClassifier: fold 1 had prevalence 0.640, AUC 0.605577, AP
  0.763376, lift +0.123376, accuracy 0.475, Brier 0.290330, top-decile
  precision 1.000, p+ 0.393394, p- 0.349898. Fold 2: 0.435, 0.483471,
  0.556878, +0.121878, 0.635, 0.256882, 0.850, 0.380085, 0.372986. Fold 3:
  0.530, 0.650341, 0.623938, +0.093938, 0.520, 0.264149, 0.600, 0.384366,
  0.320177. Fold 4: 0.725, 0.531912, 0.748911, +0.023911, 0.460, 0.313188,
  0.750, 0.425995, 0.413112. Fold 5: 0.395, 0.709698, 0.597929,
  +0.202929, 0.405, 0.268498, 0.650, 0.632326, 0.592401. Fold 6: 0.535,
  0.471711, 0.586349, +0.051349, 0.445, 0.281762, 0.750, 0.503427,
  0.515288. Median/mean AUC were 0.568745/0.575452, median AP lift
  +0.107908, four folds exceeded 0.50, three reached 0.55, and all six had
  AP above prevalence. It passed and was the strongest H1 model.
- Current raw ensemble: fold AUCs 0.608507, 0.491710, 0.657065, 0.484639,
  0.627681, 0.453221. Median/mean AUC were 0.550108/0.553804 and median AP
  lift +0.120561, but only three folds exceeded 0.50. It failed.

## Development Regression Results

RandomForestRegressor fold Spearman ICs were 0.117927, 0.223972, 0.385480,
0.088066, 0.298962, and -0.031720. Corresponding directional accuracies were
0.480, 0.630, 0.490, 0.500, 0.395, and 0.530; decile spreads were 0.067900,
3.713333, 1.656266, 2.861863, 3.220301, and -0.702764. Median/mean IC were
0.170950/0.180448, five folds had positive IC, median directional accuracy
was 0.495, median spread was 2.259064, and five spreads were positive. It
passed and was the strongest H2 model.

Ridge fold ICs were -0.109713, -0.102975, 0.112111, 0.235147, 0.194499, and
0.300306. Median/mean IC were 0.153305/0.104896; four folds were positive,
median directional accuracy was 0.517500, median spread 1.213887, and all six
spreads were positive. It passed.

XGBRegressor median/mean IC were 0.112735/0.160625, four of six folds were
positive, median decile spread was 2.217797, and five spreads were positive.
It passed. All regression fits used fixed deterministic defaults; there was
no tuning.

## Development Screening

Five hypotheses passed exactly the predeclared development screen:

- H1 `stationary_v1` + LogisticRegression;
- H1 `stationary_v1` + RandomForestClassifier;
- H2 `stationary_v1` + Ridge;
- H2 `stationary_v1` + XGBRegressor;
- H2 `stationary_v1` + RandomForestRegressor.

No H0 hypothesis passed. The holdout therefore remained inaccessible to H0
and to the failed H1 XGB/raw-ensemble hypotheses.

## Frozen Shortlist

Before holdout labels or metrics were read, the five eligible target/model
identities, `stationary_v1` profile, fixed configurations, and development
summaries were serialized deterministically in memory. Its SHA-256 was:

`0781d0844be5a3c894da643f2ce0cc608261ab46ecf01b54c2e8b33f677e39f5`

No shortlisted target, feature profile, model family, parameter, threshold,
or screen changed afterward.

## Historical Holdout

Only the five frozen hypotheses entered the two 200-row historical holdout
blocks.

H1 LogisticRegression produced fold AUCs 0.458571 and 0.464976, with AP lifts
+0.003190 and -0.026141. Median AUC was 0.461774 and median AP lift
-0.011476; it failed.

H1 RandomForestClassifier produced fold AUCs 0.519560 and 0.583535, with AP
lifts +0.039097 and +0.073985. Median AUC was 0.551548, both folds exceeded
0.50, and median AP lift was +0.056541. It also materially exceeded the
strongest trivial holdout baseline: +0.025272 median AUC and +0.043521 median
AP lift over mean reversion. It passed the predeclared research holdout rule.

No H2 model generalized. RandomForestRegressor fold ICs were -0.296317 and
-0.271680 (median -0.283999); spreads were -2.236372 and +0.398402 (median
-0.918985). Ridge fold ICs were -0.117192 and +0.056130 (median -0.030531);
spreads were -0.478569 and +0.930810 (median +0.226120). XGBRegressor fold
ICs were -0.271022 and -0.403368 (median -0.337195); spreads were -1.551789
and -1.822343 (median -1.687066). Each failed the positive-IC requirements.

The best holdout classification evidence was therefore Random Forest H1 at
median AUC 0.551548 and AP lift +0.056541. The least-negative regression IC
was Ridge at -0.030531, with median spread +0.226120; this is a failure, not
positive evidence.

## Target Agreement

Across 4,903 rows where H0 resolved, H0 and H1 agreed 72.017132% of the time.
H0=1/H1=0 occurred on 14.786865%; H0=0/H1=1 occurred on 13.196002%.
First-touch direction is therefore related to, but materially different from,
terminal twelve-candle direction. H0 discarded 6.144717% rather than most of
the sample, so its weakness is not explained primarily by timeout volume.

## Statistical Interpretation

The evidence is `LEVEL 2`: H1 generalized while H0 did not, and H2 showed
development ranking signal that reversed on holdout. This makes the current
first-touch formulation the primary demonstrated target problem, not proof
that the information set is universally sufficient.

The surviving effect is narrow. Only RandomForestClassifier generalized for
H1, and its holdout median AUC is 0.551548 rather than a production-quality
claim. Logistic H1 and every H2 regressor failed holdout. Mean reversion was
stronger than Random Forest on development median AUC, although weaker on AP
lift and clearly weaker on both holdout metrics. The result warrants a
separate implementation/evaluation hypothesis, not promotion or trading.

## Current Outer Safety

The experiment used no timestamp after `2025-10-31 23:59:59`; current 2026
inner and outer rows were not inspected. The current outer was not scored,
ranked, selected against, or consumed.

Pre/post fingerprints were identical for canonical H1/H4/D1 data, the EURUSD
qualification tree, model and parameter roots, hyperparameter cache, and the
SQLite database. EURUSD remained `qualified`; `latest_EURUSD.pkl` remained
absent; model provenance, retrain-run, and H1 model-quality state remained
unchanged. No model or research dataset was written.

## Recommended Architecture

The next separately authorized research change should implement H1 as an
explicit fixed-horizon-direction target behind a non-production experimental
contract, retain `stationary_v1`, and use the fixed Random Forest family as
the primary candidate. Mean reversion must remain a mandatory comparator.
That implementation should receive a newly preregistered independent
validation protocol before any discussion of production gates, lifecycle
eligibility, activation, or promotion. The current outer must remain pristine
until such a protocol is explicitly authorized.

## Decision

**RESEARCH SIGNAL FOUND — FIXED-HORIZON CLASSIFICATION**

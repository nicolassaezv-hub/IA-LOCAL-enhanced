# EURUSD Historical Regime Robustness

## Baseline

This research-only audit ran from source HEAD
`6cd329bf1fe12cbe3015f0ecae25f55a312ad199` on branch
`research/eurusd-historical-regime-robustness`. No source code was changed.
Legacy features and isotonic calibration remained the production defaults;
`stationary_v1` was evaluated only as the already-existing experimental
profile. Every fit used explicit model defaults `{}`, seed 42, isotonic
calibration, and `save=False`. Optuna was not invoked.

The current canonical snapshot was revalidated at SHA-256
`f4e77d47ab061f72a65ceb0d7733ba6d026422795119566eb5433180c5b1a3d2`.
Its legacy matrix reproduced exactly 1,756 rows. EURUSD began and ended
`qualified`; `latest_EURUSD.pkl` remained absent; model provenance, retrain
runs, and H1 model-quality counts remained zero.

## Current Evidence Boundary

The timestamp mapped from current training-matrix position 979 is
`2026-07-08 14:00:00` UTC-naive. This is the immutable `RESEARCH_CUTOFF`.
Current matrix positions at or above 980 were not read into any research
pool, feature statistic, target statistic, model fit, or metric. The current
outer ranges `[1020,1320)` and `[1320,1620)` were not inspected or evaluated.

The already-known allowed current fold-2 result used only for comparison was
stationary_v1 ROC-AUC 0.468367 and AP 0.451812. It was not recalculated and did
not select a profile, model, parameter, feature, or window.

## IFC Historical Acquisition

The hardened `MT5Provider` connected directly to server `IFCMarkets-Demo`
(`IFCMarkets. Corp.`) with `allow_fallback=False`. No account identifier was
read into the report. DataRouter, Yahoo, and OANDA were not used.

The provider requests and safe row counts after the immediate cutoff filter
were:

- H1: 12,000 requested; 11,099 retained; 2024-09-09 18:00:00 through
  2026-07-08 14:00:00;
- H4: 4,000 requested; 3,772 retained; 2024-01-31 23:00:00 through
  2026-07-08 14:00:00;
- D1: 2,000 requested; 1,963 retained; 2018-12-11 23:00:00 through
  2026-07-07 22:00:00.

Each fetched object was filtered to `timestamp <= RESEARCH_CUTOFF`
immediately, before indicator calculation, feature engineering, target
generation, descriptive statistics, or fitting. No individual post-cutoff
row was inspected or reported. All intermediate CSVs lived only inside a
`TemporaryDirectory` and were removed automatically.

## Research Cutoff

The production indicator implementation
`forex.data.indicator_delta.recalculate_tail_indicators()` was applied to each
already-filtered frame with full available causal context. The existing
`_load()` adapter and `build_features()` then produced a 10,088-row historical
research matrix spanning 2024-09-11 19:00:00 through 2026-07-08 02:00:00.
The twelve-hour difference between the last labeled row and the acquisition
cutoff is the unchanged target horizon.

Targets used exactly horizon 12 and risk/reward ratio 1.0. Legacy and
stationary_v1 had identical row indices and target values. The longer sample
produced 92 legacy columns rather than the current snapshot's 87 because the
existing variance filter retained five additional small-variance features;
the profile code and filter threshold were not changed. Stationary_v1 had 102
features.

## Historical MTF Contract

The existing MTF merge-asof implementation was used with H4 availability at
candle open plus four hours and D1 availability at candle open plus one day.
An independent aggregate invariant check matched context for all 11,099 H1
rows and found zero H4 and zero D1 lookahead violations. Every matched context
availability timestamp was less than or equal to its H1 timestamp.

Indicators followed the same helper used by the production RollingDataset
pipeline. No indicator formula was independently rewritten and no canonical
dataset was opened for writing.

## Window Construction

Exactly six deterministic 1,756-row windows were selected as the six most
recent valid windows ending at or before the cutoff. Window ends were spaced
by 400 labeled rows. In each window the research pool was its last 980 rows.
`WalkForwardValidator(window=500, step=200, purge=20, n_folds=2)` returned the
unchanged positions:

- fold 1: train `[0,480)`, validation `[520,720)`;
- fold 2: train `[200,680)`, validation `[720,920)`.

The 12 validation blocks were pairwise disjoint. No date was cherry-picked:

- window 1: 2025-11-03 15:00:00 to 2026-02-27 09:00:00; pool starts
  2025-12-23 05:00:00;
- window 2: 2025-11-27 17:00:00 to 2026-03-26 01:00:00; pool starts
  2026-01-22 14:00:00;
- window 3: 2025-12-24 05:00:00 to 2026-04-21 19:00:00; pool starts
  2026-02-17 12:00:00;
- window 4: 2026-01-23 17:00:00 to 2026-05-18 08:00:00; pool starts
  2026-03-13 13:00:00;
- window 5: 2026-02-18 13:00:00 to 2026-06-11 09:00:00; pool starts
  2026-04-09 11:00:00;
- window 6: 2026-03-16 18:00:00 to 2026-07-08 02:00:00; pool starts
  2026-05-05 23:00:00.

## Legacy Historical Results

The twelve legacy fold records are below. `p+` and `p-` are mean raw p(BUY)
for positive and negative targets. Calibration evidence uses the existing
diagnostic floor of at least 60 calibration rows and 10% selected signals.

- W1/F1 — train 2025-12-23 05:00 to 2026-01-28 07:00; validation
  2026-01-30 00:00 to 2026-02-11 19:00; targets 107/93,
  prevalence 0.535; AUC 0.612602, AP 0.636197, AP lift +0.101197;
  p+ 0.367745, p- 0.304162, top-10% precision 0.700; calibration threshold
  0.900000, 4 signals, evidence no; external 67 signals, precision 0.582090.
- W1/F2 — train 2026-01-08 22:00 to 2026-02-10 03:00; validation
  2026-02-11 20:00 to 2026-02-24 20:00; targets 64/136,
  prevalence 0.320; AUC 0.614200, AP 0.398798, AP lift +0.078798;
  p+ 0.601456, p- 0.511575, top-10% 0.450; threshold 0.900000,
  23 calibration signals, evidence yes; external 100, precision 0.380000.
- W2/F1 — train 2026-01-22 14:00 to 2026-02-23 04:00; validation
  2026-02-24 21:00 to 2026-03-09 22:00; targets 87/113,
  prevalence 0.435; AUC 0.478181, AP 0.443610, AP lift +0.008610;
  p+ 0.733390, p- 0.756034, top-10% 0.450; threshold 0.612903,
  31 calibration signals, evidence yes; external 61, precision 0.426230.
- W2/F2 — train 2026-02-04 13:00 to 2026-03-06 01:00; validation
  2026-03-09 23:00 to 2026-03-23 02:00; targets 100/100,
  prevalence 0.500; AUC 0.487800, AP 0.497056, AP lift -0.002944;
  p+ 0.744259, p- 0.746683, top-10% 0.550; threshold 0.900000,
  1 calibration signal, evidence no; external 2, precision 0.500000.
- W3/F1 — train 2026-02-17 12:00 to 2026-03-19 05:00; validation
  2026-03-23 03:00 to 2026-04-03 16:00; targets 89/111,
  prevalence 0.445; AUC 0.497014, AP 0.459554, AP lift +0.014554;
  p+ 0.453471, p- 0.451692, top-10% 0.450; threshold 0.642857,
  14 calibration signals, evidence yes; external 66, precision 0.469697.
- W3/F2 — train 2026-03-02 11:00 to 2026-04-01 13:00; validation
  2026-04-03 17:00 to 2026-04-16 20:00; targets 124/76,
  prevalence 0.620; AUC 0.472517, AP 0.617602, AP lift -0.002398;
  p+ 0.176613, p- 0.180306, top-10% 0.600; threshold 0.597015,
  69 calibration signals, evidence yes; external 73, precision 0.657534.
- W4/F1 — train 2026-03-13 13:00 to 2026-04-15 02:00; validation
  2026-04-16 21:00 to 2026-04-30 03:00; targets 82/118,
  prevalence 0.410; AUC 0.470029, AP 0.387453, AP lift -0.022547;
  p+ 0.542439, p- 0.568048, top-10% 0.300; threshold 0.900000,
  4 calibration signals, evidence no; external 23, precision 0.304348.
- W4/F2 — train 2026-03-26 23:00 to 2026-04-28 09:00; validation
  2026-04-30 04:00 to 2026-05-13 09:00; targets 107/93,
  prevalence 0.535; AUC 0.382173, AP 0.467167, AP lift -0.067833;
  p+ 0.338981, p- 0.405643, top-10% 0.450; threshold 0.471429,
  71 calibration signals, evidence yes; external 193, precision 0.518135.
- W5/F1 — train 2026-04-09 11:00 to 2026-05-11 17:00; validation
  2026-05-13 10:00 to 2026-05-26 16:00; targets 70/130,
  prevalence 0.350; AUC 0.554725, AP 0.373422, AP lift +0.023422;
  p+ 0.757871, p- 0.750130, top-10% 0.300; threshold 0.900000,
  7 calibration signals, evidence no; external 177, precision 0.338983.
- W5/F2 — train 2026-04-22 17:00 to 2026-05-22 18:00; validation
  2026-05-26 17:00 to 2026-06-08 19:00; targets 100/100,
  prevalence 0.500; AUC 0.524200, AP 0.522980, AP lift +0.022980;
  p+ 0.310780, p- 0.296809, top-10% 0.500; threshold 0.833333,
  6 calibration signals, evidence no; external 0, precision 0.
- W6/F1 — train 2026-05-05 23:00 to 2026-06-04 20:00; validation
  2026-06-08 20:00 to 2026-06-19 17:00; targets 92/108,
  prevalence 0.460; AUC 0.524758, AP 0.467891, AP lift +0.007891;
  p+ 0.757295, p- 0.727133, top-10% 0.400; threshold 0.900000,
  14 calibration signals, evidence yes; external 124, precision 0.475806.
- W6/F2 — train 2026-05-19 05:00 to 2026-06-18 01:00; validation
  2026-06-19 18:00 to 2026-07-03 09:00; targets 90/110,
  prevalence 0.450; AUC 0.463030, AP 0.451367, AP lift +0.001367;
  p+ 0.821945, p- 0.821654, top-10% 0.600; threshold 0.900000,
  2 calibration signals, evidence no; external 0, precision 0.

Across all 12 legacy folds, median/mean AUC were 0.492407/0.506769,
minimum/maximum were 0.382173/0.614200, 5/12 exceeded 0.50, and 3/12
exceeded 0.55. Median AP was 0.463360 and median AP lift was +0.008250;
8/12 AP values exceeded prevalence. Calibration evidence was sufficient in
6/12 folds and external signals reached 20 in 9/12 folds.

## Stationary V1 Historical Results

- W1/F1 — train 2025-12-23 05:00 to 2026-01-28 07:00; validation
  2026-01-30 00:00 to 2026-02-11 19:00; targets 107/93,
  prevalence 0.535; AUC 0.627977, AP 0.639871, AP lift +0.104871; p+ 0.538765,
  p- 0.431829, top-10% precision 0.650; threshold 0.777778,
  11 calibration signals, evidence yes; external 94, precision 0.638298.
- W1/F2 — train 2026-01-08 22:00 to 2026-02-10 03:00; validation
  2026-02-11 20:00 to 2026-02-24 20:00; targets 64/136,
  prevalence 0.320; AUC 0.604779, AP 0.404626, AP lift
  +0.084626; p+ 0.609463, p- 0.526037, top-10% 0.450; threshold 0.900000,
  18 calibration signals, evidence yes; external 68, precision 0.411765.
- W2/F1 — train 2026-01-22 14:00 to 2026-02-23 04:00; validation
  2026-02-24 21:00 to 2026-03-09 22:00; targets 87/113,
  prevalence 0.435; AUC 0.461601, AP 0.435280, AP lift
  +0.000280; p+ 0.794593, p- 0.809607, top-10% 0.400; threshold 0.583333,
  24 calibration signals, evidence yes; external 46, precision 0.369565.
- W2/F2 — train 2026-02-04 13:00 to 2026-03-06 01:00; validation
  2026-03-09 23:00 to 2026-03-23 02:00; targets 100/100,
  prevalence 0.500; AUC 0.502600, AP 0.502561, AP lift
  +0.002561; p+ 0.388782, p- 0.381081, top-10% 0.350; threshold 0.900000,
  1 calibration signal, evidence no; external 5, precision 0.400000.
- W3/F1 — train 2026-02-17 12:00 to 2026-03-19 05:00; validation
  2026-03-23 03:00 to 2026-04-03 16:00; targets 89/111,
  prevalence 0.445; AUC 0.498431, AP 0.494950, AP lift
  +0.049950; p+ 0.421853, p- 0.411876, top-10% 0.600; threshold 0.750000,
  8 calibration signals, evidence yes; external 37, precision 0.513514.
- W3/F2 — train 2026-03-02 11:00 to 2026-04-01 13:00; validation
  2026-04-03 17:00 to 2026-04-16 20:00; targets 124/76,
  prevalence 0.620; AUC 0.449491, AP 0.608550, AP lift
  -0.011450; p+ 0.168929, p- 0.179348, top-10% 0.550; threshold 0.692308,
  14 calibration signals, evidence yes; external 21, precision 0.523810.
- W4/F1 — train 2026-03-13 13:00 to 2026-04-15 02:00; validation
  2026-04-16 21:00 to 2026-04-30 03:00; targets 82/118,
  prevalence 0.410; AUC 0.572447, AP 0.472226, AP lift
  +0.062226; p+ 0.711334, p- 0.666022, top-10% 0.550; threshold 0.750000,
  5 calibration signals, evidence no; external 3, precision 0.666667.
- W4/F2 — train 2026-03-26 23:00 to 2026-04-28 09:00; validation
  2026-04-30 04:00 to 2026-05-13 09:00; targets 107/93,
  prevalence 0.535; AUC 0.418048, AP 0.484560, AP lift
  -0.050440; p+ 0.287938, p- 0.330889, top-10% 0.350; threshold 0.525424,
  59 calibration signals, evidence yes; external 159, precision 0.490566.
- W5/F1 — train 2026-04-09 11:00 to 2026-05-11 17:00; validation
  2026-05-13 10:00 to 2026-05-26 16:00; targets 70/130,
  prevalence 0.350; AUC 0.610879, AP 0.483009, AP lift
  +0.133009; p+ 0.742554, p- 0.719412, top-10% 0.600; threshold 0.741935,
  31 calibration signals, evidence yes; external 188, precision 0.345745.
- W5/F2 — train 2026-04-22 17:00 to 2026-05-22 18:00; validation
  2026-05-26 17:00 to 2026-06-08 19:00; targets 100/100,
  prevalence 0.500; AUC 0.404900, AP 0.441049, AP lift
  -0.058951; p+ 0.260592, p- 0.303497, top-10% 0.400; threshold 0.423077,
  26 calibration signals, evidence yes; external 10, precision 0.400000.
- W6/F1 — train 2026-05-05 23:00 to 2026-06-04 20:00; validation
  2026-06-08 20:00 to 2026-06-19 17:00; targets 92/108,
  prevalence 0.460; AUC 0.493559, AP 0.484738, AP lift
  +0.024738; p+ 0.605153, p- 0.607569, top-10% 0.600; threshold 0.900000,
  6 calibration signals, evidence no; external 39, precision 0.487179.
- W6/F2 — train 2026-05-19 05:00 to 2026-06-18 01:00; validation
  2026-06-19 18:00 to 2026-07-03 09:00; targets 90/110,
  prevalence 0.450; AUC 0.434747, AP 0.430839, AP lift
  -0.019161; p+ 0.555397, p- 0.616597, top-10% 0.450; threshold 0.900000,
  2 calibration signals, evidence no; external 24, precision 0.416667.

Across all 12 stationary_v1 folds, median/mean AUC were
0.495995/0.506622, minimum/maximum were 0.404900/0.627977, 5/12 exceeded
0.50, and 4/12 exceeded 0.55. Median AP was 0.483784 and median AP lift was
+0.013650; 8/12 AP values exceeded prevalence. Calibration evidence was
sufficient in 8/12 folds and external signals reached 20 in 9/12 folds.

## Profile Comparison

Stationary_v1 beat legacy by raw AUC in exactly 6 of 12 paired folds. Its
mean AUC was 0.000147 lower and median AUC only 0.003588 higher. It improved
median AP by 0.020424 and median AP lift by 0.005399, but did not increase the
number of folds whose AP exceeded prevalence. Neither profile has stable raw
discrimination: both have mean AUC about 0.507, median AUC below 0.50, and
only 5/12 folds above 0.50.

Stationary_v1 therefore is not historically superior in a consistent paired
sense. It changes which periods rank better, but does not solve the underlying
model-signal instability.

## Current Regime Percentile

Against the 12 historical stationary_v1 folds, the known recent fold-2 AUC
0.468367 has ascending rank 6/12 and lower-tail percentile 41.67%. Its AP
0.451812 has ascending rank 5/12 and lower-tail percentile 33.33%.

The recent result is weak, but it is not a clear historical lower-tail
outlier. Historical stationary_v1 contains AUC values as low as 0.404900 and
several comparable sub-0.50 folds. This directly rejects the hypothesis that
the recent period alone explains the weak discrimination.

## Historical Drift

For each window, standardized feature shift compares fold-1 validation with
fold-2 validation using the same definition as the prior inner study.

- legacy median maximum shift: 3.410527; median of per-window median shifts:
  0.271774; median features above 1: 21.5; above 2: 5.0;
- stationary_v1 median maximum shift: 3.478927; median of per-window median
  shifts: 0.148946; median features above 1: 10.5; above 2: 4.5.

Per-window legacy median shifts were 0.372021, 0.272697, 0.491416, 0.151452,
0.270850, and 0.234482. Stationary_v1 values were 0.168752, 0.129139,
0.365782, 0.179695, 0.084142, and 0.106833. Stationary_v1 was lower in five
of six windows. Its historical reduction in broad location drift is therefore
consistent rather than unique to the recent period. Maximum shifts remain
large, and lower drift did not translate into consistently better AUC.

## Regime Association

Regime labels are descriptive only and use causal row features. A validation
block is `high_trend` when its median absolute `trend_strength_pct` exceeds
the preceding training block's median, and `high_volatility` when its median
`atr_pct` exceeds the preceding training block's median. Direction uses the
sign of validation median `trend_strength_pct`. No production regime model or
global future threshold was created.

The clearest diagnostic cluster is uptrend/high-trend:

- all 3 uptrend folds were below AUC 0.50 for both profiles; median AUC was
  0.472517 legacy and 0.449491 stationary_v1;
- high-trend folds had 4/6 below 0.50 for both profiles; median AUC was
  0.482991 legacy and 0.477580 stationary_v1;
- low-trend median AUC was 0.510607 legacy and 0.535439 stationary_v1;
- high-volatility versus low-volatility separation was weak: stationary_v1
  medians were 0.495995 and 0.510969, while legacy medians were 0.492407 and
  0.498358.

The sample contains only three uptrend blocks, so this is a hypothesis, not a
gate or causal conclusion. Tokyo was the dominant encoded session in every
validation block and therefore cannot explain cross-window discrimination.

## Statistical Interpretation

The current problematic fold is not exceptional relative to the historical
distribution. Both profiles are centered near random discrimination,
stationary_v1 wins only half of paired folds, and favorable folds alternate
with below-random folds. AP beats prevalence in two thirds of folds, but its
median lift is only +0.008250 legacy and +0.013650 stationary_v1. Calibration
evidence and signal coverage are also intermittent, but raw AUC establishes
that calibration is not the sole cause.

The main finding is `SYSTEMIC MODEL DISCRIMINATION FAILURE`, with a secondary
diagnostic association to high-trend/uptrend periods. The evidence does not
support `RECENT REGIME IS PRIMARY FAILURE` or historical sufficiency of
stationary_v1.

## Outer Evidence Safety

All historical source frames were filtered before study computations to the
timestamp mapped from current position 979. Current positions 980 onward were
not used. The two current outer ranges were not inspected, scored, ranked, or
consumed.

Pre/post fingerprints were identical for canonical H1/H4/D1, the complete
EURUSD qualification tree, Forex models and parameter files, hyperparameter
cache, and SQLite database. Temporary research files were outside canonical
and qualification roots and were deleted. No DB row, model, candidate,
parameter, cache entry, canonical dataset, or qualification artifact changed.

## Recommended Next Hypothesis

Do not consume current outer evidence and do not lower gates. The next
research task should redesign the model/target hypothesis on a separately
reserved historical protocol. Candidate questions for later, not implemented
here, include alternative horizon/RR target definitions, classification
versus expected-return formulation, a different model family, and principled
feature reduction. The uptrend/high-trend association should be tested with
more independent periods before considering regime-aware abstention or
separate regime models.

## Decision

**HISTORICAL AUDIT COMPLETE — SYSTEMIC MODEL DISCRIMINATION FAILURE**

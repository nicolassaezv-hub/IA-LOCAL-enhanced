# EURUSD H1 Temporal Adaptation Study

## Motivation

This research-only study tested `TEMPORAL_ADAPTATION_V1`: whether the rejected
`h1_direction_rf_v1` hypothesis failed because an expanding training history
contained stale regimes, and whether a shorter recent rolling window improved
raw discrimination, temporal consistency, and score stability.

The target, features, model family, and hyperparameters were frozen. The target
was `fixed_horizon_direction_v1`, definition version 1, at horizon 12. The
feature profile was `stationary_v1`; the resulting ordered 102-column identity
matched the required SHA-256 exactly:
`5f51168349400e31bfe891c78a1833e1618166c478d3c0bebba983728b551791`.
Every fit used `RandomForestClassifier(n_estimators=300, max_depth=8,
min_samples_leaf=15, class_weight={0: 1.0, 1: train_negatives /
train_positives}, random_state=42, n_jobs=-1)`. There was no model-family,
target, feature, threshold, quartile, or hyperparameter search.

## Evidence Isolation

The source HEAD was
`4c6bc4dd447663d9f9fb42ecd0757ebbcfbeb167` and the research branch was
`research/eurusd-h1-temporal-adaptation`.

Each provider return was immediately filtered to timestamps earlier than
`2025-01-01T00:00:00`, then to timestamps earlier than
`2024-09-01T00:00:00`, before indicator calculation, feature statistics,
target generation, fitting, or metrics. The existing production indicator
helper was applied only after those boundaries. All CSVs and the research
harness lived under a `TemporaryDirectory` or the operating-system temporary
directory. No canonical dataset was read for evidence or written.

The reserved interval `TEMPORAL_ADAPTATION_HOLDOUT_V1` was
`2024-07-01T00:00:00` through `2024-08-31T23:59:59`. Its structural capacity
was counted without reading target values: 1,023 usable labeled positions were
available, above the required 400. Because no rolling strategy passed the
predeclared development selection, holdout labels and metrics were never
constructed or inspected.

No 2025 or 2026 row entered the research matrix. Therefore 2026 rows used for
research were exactly zero. The consumed 2026 outer and final tail, including
`[1640,1888)` and `2026-08-13T17:00:00` through
`2026-08-28T10:00:00`, were not loaded, scored, or reproduced.

## IFC Historical Acquisition

`MT5Provider` connected directly to `IFCMarkets-Demo` (`IFCMarkets. Corp.`)
with `allow_fallback=False`. DataRouter, Yahoo, and OANDA were not used. The
server clock profile was `ifcmarkets-demo-europe-berlin` in
`Europe/Berlin`; ASTRA normalized timestamps to UTC-naive values.

| Timeframe | Requested | Provider rows | Rows after research boundaries | Oldest | Newest | Invalid dropped |
|---|---:|---:|---:|---|---|---:|
| H1 | 30,000 | 30,000 | 17,854 | 2021-09-30 13:00 | 2024-08-30 19:00 | 0 |
| H4 | 8,000 | 8,000 | 4,910 | 2021-07-06 22:00 | 2024-08-30 18:00 | 0 |
| D1 | 1,500 | 1,500 | 983 | 2020-11-18 23:00 | 2024-08-29 22:00 | 0 |

The H1 frame therefore exceeded the requested minimum depth of 2023. The
existing gap filter removed 459 post-gap H1 rows. The existing causal MTF
merge used H4 only after opening time plus four hours and D1 only after opening
time plus one day. The bounded H1 research-frame SHA-256 was
`d5a68ed947cccf1476f48fc6bf7cfdc528d981115db58003c5d7084372869db1`.

## Development Protocol

After feature and target availability, 16,299 development rows remained. The
eight development validations were the eight consecutive, non-overlapping
200-row blocks immediately preceding the development boundary. This
deterministic rule was fixed before metrics. Validation spanned
`2024-03-22T19:00:00` through `2024-06-28T07:00:00`.

For every main fold, training ended 20 eligible rows before validation. The
expanding strategy used every eligible prior row; rolling strategies used
exactly the most recent 1,600, 1,200, or 1,000 training rows. The target
terminal invariant passed in all 32 strategy/folds:

| Fold | Validation start | Maximum training-target terminal timestamp |
|---:|---|---|
| 1 | 2024-03-22 19:00 | 2024-03-22 10:00 |
| 2 | 2024-04-04 12:00 | 2024-04-04 03:00 |
| 3 | 2024-04-17 06:00 | 2024-04-16 21:00 |
| 4 | 2024-04-30 00:00 | 2024-04-29 15:00 |
| 5 | 2024-05-10 13:00 | 2024-05-10 04:00 |
| 6 | 2024-05-23 07:00 | 2024-05-22 22:00 |
| 7 | 2024-06-05 01:00 | 2024-06-04 16:00 |
| 8 | 2024-06-17 19:00 | 2024-06-17 10:00 |

For the diagnostic `oof_quartile_abstention_v1` policy, each main fold used
600 score-only OOF observations from the three preceding, non-overlapping
200-row blocks. Each OOF subfit used the same expanding or exact rolling
strategy as its main fit and the same purge 20. The empirical percentile
boundaries remained exactly 0.25 and 0.75. OOF labels did not select the
quartiles.

The primary tables below use `pos/neg` for validation counts. Top-10 precision
is the positive-label rate in the 20 highest raw `p_up` scores.

## Expanding Baseline

| Fold | Train rows and dates | Validation dates | Pos/neg | Prev. | AUC | AP | AP lift | Brier | Top-10 precision |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 14,679; 2021-10-04 19:00–2024-03-21 22:00 | 2024-03-22 19:00–2024-04-04 11:00 | 104/96 | 0.520000 | 0.359475 | 0.467337 | -0.052663 | 0.280614 | 0.500000 |
| 2 | 14,879; 2021-10-04 19:00–2024-04-03 15:00 | 2024-04-04 12:00–2024-04-17 05:00 | 78/122 | 0.390000 | 0.512715 | 0.444813 | +0.054813 | 0.256589 | 0.500000 |
| 3 | 15,079; 2021-10-04 19:00–2024-04-16 09:00 | 2024-04-17 06:00–2024-04-29 23:00 | 119/81 | 0.595000 | 0.717606 | 0.800882 | +0.205882 | 0.241388 | 0.950000 |
| 4 | 15,279; 2021-10-04 19:00–2024-04-29 03:00 | 2024-04-30 00:00–2024-05-10 12:00 | 98/102 | 0.490000 | 0.535814 | 0.574455 | +0.084455 | 0.248710 | 0.600000 |
| 5 | 15,479; 2021-10-04 19:00–2024-05-09 16:00 | 2024-05-10 13:00–2024-05-23 06:00 | 99/101 | 0.495000 | 0.536654 | 0.528929 | +0.033929 | 0.248750 | 0.550000 |
| 6 | 15,679; 2021-10-04 19:00–2024-05-22 10:00 | 2024-05-23 07:00–2024-06-05 00:00 | 105/95 | 0.525000 | 0.620752 | 0.665631 | +0.140631 | 0.240822 | 0.800000 |
| 7 | 15,879; 2021-10-04 19:00–2024-06-04 04:00 | 2024-06-05 01:00–2024-06-17 18:00 | 95/105 | 0.475000 | 0.653534 | 0.611110 | +0.136110 | 0.241223 | 0.700000 |
| 8 | 16,079; 2021-10-04 19:00–2024-06-14 17:00 | 2024-06-17 19:00–2024-06-28 07:00 | 97/103 | 0.485000 | 0.609549 | 0.607719 | +0.122719 | 0.244456 | 0.550000 |

Aggregate median/mean/worst AUC was
0.573101/0.568262/0.359475; population AUC standard deviation was 0.101713.
Seven of eight folds exceeded 0.50 and four reached 0.55. Median AP lift was
`+0.103587` and seven folds had positive lift. Median decision coverage was
0.557500, median pooled action precision was 0.605953, and one fold collapsed
directionally.

## Rolling 1600

| Fold | Train dates | Validation dates | Pos/neg | Prev. | AUC | AP | AP lift | Brier | Top-10 precision |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2023-12-13 00:00–2024-03-21 22:00 | 2024-03-22 19:00–2024-04-04 11:00 | 104/96 | 0.520000 | 0.442208 | 0.549910 | +0.029910 | 0.309769 | 0.750000 |
| 2 | 2023-12-26 18:00–2024-04-03 15:00 | 2024-04-04 12:00–2024-04-17 05:00 | 78/122 | 0.390000 | 0.612232 | 0.462826 | +0.072826 | 0.306316 | 0.500000 |
| 3 | 2024-01-09 21:00–2024-04-16 09:00 | 2024-04-17 06:00–2024-04-29 23:00 | 119/81 | 0.595000 | 0.652350 | 0.730215 | +0.135215 | 0.225996 | 0.750000 |
| 4 | 2024-01-22 15:00–2024-04-29 03:00 | 2024-04-30 00:00–2024-05-10 12:00 | 98/102 | 0.490000 | 0.528711 | 0.490484 | +0.000484 | 0.270591 | 0.350000 |
| 5 | 2024-02-02 04:00–2024-05-09 16:00 | 2024-05-10 13:00–2024-05-23 06:00 | 99/101 | 0.495000 | 0.620262 | 0.582079 | +0.087079 | 0.241862 | 0.600000 |
| 6 | 2024-02-14 22:00–2024-05-22 10:00 | 2024-05-23 07:00–2024-06-05 00:00 | 105/95 | 0.525000 | 0.589173 | 0.653418 | +0.128418 | 0.243532 | 0.900000 |
| 7 | 2024-02-27 16:00–2024-06-04 04:00 | 2024-06-05 01:00–2024-06-17 18:00 | 95/105 | 0.475000 | 0.644812 | 0.626379 | +0.151379 | 0.235550 | 0.700000 |
| 8 | 2024-03-11 10:00–2024-06-14 17:00 | 2024-06-17 19:00–2024-06-28 07:00 | 97/103 | 0.485000 | 0.491142 | 0.482070 | -0.002930 | 0.283929 | 0.450000 |

Every training set contained exactly 1,600 rows. Aggregate
median/mean/worst AUC was 0.600702/0.572611/0.442208 and AUC standard
deviation was 0.071812. Six folds exceeded 0.50 and five reached 0.55. Median
AP lift was +0.079953 with seven positive folds. Median coverage was 0.595000,
median pooled action precision was 0.532642, and three folds collapsed.

## Rolling 1200

| Fold | Train dates | Validation dates | Pos/neg | Prev. | AUC | AP | AP lift | Brier | Top-10 precision |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2024-01-09 21:00–2024-03-21 22:00 | 2024-03-22 19:00–2024-04-04 11:00 | 104/96 | 0.520000 | 0.440004 | 0.497928 | -0.022072 | 0.318107 | 0.500000 |
| 2 | 2024-01-22 15:00–2024-04-03 15:00 | 2024-04-04 12:00–2024-04-17 05:00 | 78/122 | 0.390000 | 0.611286 | 0.499150 | +0.109150 | 0.302000 | 0.550000 |
| 3 | 2024-02-02 04:00–2024-04-16 09:00 | 2024-04-17 06:00–2024-04-29 23:00 | 119/81 | 0.595000 | 0.668119 | 0.748807 | +0.153807 | 0.223426 | 0.850000 |
| 4 | 2024-02-14 22:00–2024-04-29 03:00 | 2024-04-30 00:00–2024-05-10 12:00 | 98/102 | 0.490000 | 0.550120 | 0.504914 | +0.014914 | 0.270203 | 0.400000 |
| 5 | 2024-02-27 16:00–2024-05-09 16:00 | 2024-05-10 13:00–2024-05-23 06:00 | 99/101 | 0.495000 | 0.599960 | 0.566999 | +0.071999 | 0.246352 | 0.550000 |
| 6 | 2024-03-11 10:00–2024-05-22 10:00 | 2024-05-23 07:00–2024-06-05 00:00 | 105/95 | 0.525000 | 0.625965 | 0.700416 | +0.175416 | 0.253962 | 1.000000 |
| 7 | 2024-03-21 23:00–2024-06-04 04:00 | 2024-06-05 01:00–2024-06-17 18:00 | 95/105 | 0.475000 | 0.599900 | 0.555478 | +0.080478 | 0.246128 | 0.600000 |
| 8 | 2024-04-03 16:00–2024-06-14 17:00 | 2024-06-17 19:00–2024-06-28 07:00 | 97/103 | 0.485000 | 0.412071 | 0.424749 | -0.060251 | 0.298299 | 0.250000 |

Every training set contained exactly 1,200 rows. Aggregate
median/mean/worst AUC was 0.599930/0.563428/0.412071 and AUC standard
deviation was 0.085254. Six folds exceeded 0.50 and six reached 0.55. Median
AP lift was +0.076238 with six positive folds. Median coverage was 0.685000,
median pooled action precision was 0.535299, and two folds collapsed.

## Rolling 1000

| Fold | Train dates | Validation dates | Pos/neg | Prev. | AUC | AP | AP lift | Brier | Top-10 precision |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2024-01-22 15:00–2024-03-21 22:00 | 2024-03-22 19:00–2024-04-04 11:00 | 104/96 | 0.520000 | 0.485978 | 0.521862 | +0.001862 | 0.302686 | 0.600000 |
| 2 | 2024-02-02 04:00–2024-04-03 15:00 | 2024-04-04 12:00–2024-04-17 05:00 | 78/122 | 0.390000 | 0.609395 | 0.486386 | +0.096386 | 0.299831 | 0.500000 |
| 3 | 2024-02-14 22:00–2024-04-16 09:00 | 2024-04-17 06:00–2024-04-29 23:00 | 119/81 | 0.595000 | 0.677145 | 0.781200 | +0.186200 | 0.221651 | 0.950000 |
| 4 | 2024-02-27 16:00–2024-04-29 03:00 | 2024-04-30 00:00–2024-05-10 12:00 | 98/102 | 0.490000 | 0.554522 | 0.519764 | +0.029764 | 0.258413 | 0.450000 |
| 5 | 2024-03-11 10:00–2024-05-09 16:00 | 2024-05-10 13:00–2024-05-23 06:00 | 99/101 | 0.495000 | 0.432543 | 0.517420 | +0.022420 | 0.281130 | 0.650000 |
| 6 | 2024-03-21 23:00–2024-05-22 10:00 | 2024-05-23 07:00–2024-06-05 00:00 | 105/95 | 0.525000 | 0.541353 | 0.581001 | +0.056001 | 0.278465 | 0.500000 |
| 7 | 2024-04-03 16:00–2024-06-04 04:00 | 2024-06-05 01:00–2024-06-17 18:00 | 95/105 | 0.475000 | 0.491228 | 0.495670 | +0.020670 | 0.260344 | 0.550000 |
| 8 | 2024-04-16 10:00–2024-06-14 17:00 | 2024-06-17 19:00–2024-06-28 07:00 | 97/103 | 0.485000 | 0.514563 | 0.505141 | +0.020141 | 0.297972 | 0.550000 |

Every training set contained exactly 1,000 rows. Aggregate
median/mean/worst AUC was 0.527958/0.538341/0.432543 and AUC standard
deviation was 0.071856. Five folds exceeded 0.50 and three reached 0.55.
Median AP lift was +0.026092 and all eight folds had positive lift. Median
coverage was 0.692500, median pooled action precision was 0.508599, and two
folds collapsed.

## Score Distribution Stability

Each distribution cell is `median / p25 / p75 / mean / population std` for
the 600-score OOF reference or the 200 validation scores.

| Strategy/fold | OOF reference distribution | Validation distribution | KS | Wasserstein |
|---|---|---|---:|---:|
| Expanding/1 | 0.509431 / 0.451109 / 0.552423 / 0.494458 / 0.072039 | 0.542329 / 0.461162 / 0.560956 / 0.500154 / 0.089840 | 0.201667 | 0.022756 |
| Expanding/2 | 0.542451 / 0.506923 / 0.566277 / 0.530447 / 0.049420 | 0.542897 / 0.492955 / 0.567275 / 0.527165 / 0.056213 | 0.083333 | 0.006926 |
| Expanding/3 | 0.551325 / 0.504937 / 0.568340 / 0.525647 / 0.068941 | 0.487976 / 0.448954 / 0.517200 / 0.479163 / 0.050096 | 0.548333 | 0.053126 |
| Expanding/4 | 0.513188 / 0.465668 / 0.554048 / 0.500022 / 0.069415 | 0.500518 / 0.445882 / 0.531634 / 0.489021 / 0.050502 | 0.213333 | 0.022296 |
| Expanding/5 | 0.504413 / 0.458974 / 0.531896 / 0.488995 / 0.064555 | 0.493237 / 0.469594 / 0.514825 / 0.493303 / 0.028872 | 0.181667 | 0.025337 |
| Expanding/6 | 0.491625 / 0.460582 / 0.517191 / 0.484918 / 0.042989 | 0.505047 / 0.468763 / 0.524444 / 0.495556 / 0.047826 | 0.155000 | 0.011967 |
| Expanding/7 | 0.497155 / 0.463785 / 0.526605 / 0.493169 / 0.044433 | 0.516634 / 0.498365 / 0.541094 / 0.517672 / 0.040135 | 0.273333 | 0.024504 |
| Expanding/8 | 0.502765 / 0.471908 / 0.527550 / 0.498861 / 0.044133 | 0.511365 / 0.474678 / 0.529790 / 0.501935 / 0.039940 | 0.111667 | 0.006264 |
| Rolling 1600/1 | 0.527559 / 0.434284 / 0.616549 / 0.522556 / 0.131822 | 0.643570 / 0.500804 / 0.776674 / 0.618490 / 0.177093 | 0.323333 | 0.096119 |
| Rolling 1600/2 | 0.586156 / 0.512839 / 0.698362 / 0.599952 / 0.130260 | 0.658470 / 0.577572 / 0.778782 / 0.667171 / 0.135781 | 0.258333 | 0.067277 |
| Rolling 1600/3 | 0.621780 / 0.537119 / 0.719727 / 0.617179 / 0.139280 | 0.619371 / 0.509702 / 0.688201 / 0.598958 / 0.104738 | 0.148333 | 0.034456 |
| Rolling 1600/4 | 0.630238 / 0.517349 / 0.721908 / 0.614943 / 0.146439 | 0.540799 / 0.395099 / 0.686450 / 0.543219 / 0.160642 | 0.231667 | 0.071783 |
| Rolling 1600/5 | 0.622705 / 0.484386 / 0.701419 / 0.591370 / 0.143323 | 0.441509 / 0.383531 / 0.514669 / 0.451901 / 0.100375 | 0.485000 | 0.139469 |
| Rolling 1600/6 | 0.527017 / 0.420141 / 0.657228 / 0.535169 / 0.140159 | 0.426162 / 0.371691 / 0.471409 / 0.419025 / 0.098131 | 0.385000 | 0.116144 |
| Rolling 1600/7 | 0.471646 / 0.398865 / 0.589522 / 0.492297 / 0.135262 | 0.505453 / 0.371881 / 0.592335 / 0.493662 / 0.117959 | 0.121667 | 0.032199 |
| Rolling 1600/8 | 0.458101 / 0.388786 / 0.527185 / 0.457493 / 0.108222 | 0.652811 / 0.602797 / 0.705069 / 0.653773 / 0.066318 | 0.763333 | 0.196281 |
| Rolling 1200/1 | 0.524203 / 0.436253 / 0.596353 / 0.509163 / 0.136572 | 0.654448 / 0.513838 / 0.786420 / 0.620866 / 0.196569 | 0.391667 | 0.120292 |
| Rolling 1200/2 | 0.575764 / 0.514743 / 0.672745 / 0.591747 / 0.133496 | 0.668339 / 0.586602 / 0.763663 / 0.661095 / 0.135303 | 0.350000 | 0.070572 |
| Rolling 1200/3 | 0.608898 / 0.538415 / 0.693093 / 0.603961 / 0.144782 | 0.610397 / 0.527047 / 0.671361 / 0.595182 / 0.100079 | 0.131667 | 0.034497 |
| Rolling 1200/4 | 0.638447 / 0.541673 / 0.710107 / 0.617290 / 0.147671 | 0.530245 / 0.394932 / 0.702271 / 0.545337 / 0.180552 | 0.270000 | 0.072201 |
| Rolling 1200/5 | 0.629097 / 0.483705 / 0.697396 / 0.590959 / 0.148627 | 0.445934 / 0.391293 / 0.522272 / 0.461357 / 0.095151 | 0.500000 | 0.135900 |
| Rolling 1200/6 | 0.530248 / 0.413199 / 0.664460 / 0.535757 / 0.143217 | 0.375709 / 0.309762 / 0.422866 / 0.369872 / 0.104480 | 0.496667 | 0.165885 |
| Rolling 1200/7 | 0.446946 / 0.367314 / 0.551557 / 0.471469 / 0.143290 | 0.478160 / 0.390279 / 0.557222 / 0.479614 / 0.120065 | 0.115000 | 0.028298 |
| Rolling 1200/8 | 0.413230 / 0.355058 / 0.487274 / 0.428091 / 0.110067 | 0.682964 / 0.594512 / 0.733949 / 0.659354 / 0.083520 | 0.758333 | 0.231263 |
| Rolling 1000/1 | 0.477585 / 0.401011 / 0.570923 / 0.480336 / 0.131695 | 0.663448 / 0.527218 / 0.770762 / 0.614739 / 0.193288 | 0.455000 | 0.140839 |
| Rolling 1000/2 | 0.563989 / 0.475746 / 0.667206 / 0.570352 / 0.136619 | 0.669620 / 0.579512 / 0.769258 / 0.653706 / 0.142540 | 0.331667 | 0.083992 |
| Rolling 1000/3 | 0.595229 / 0.493463 / 0.705486 / 0.590144 / 0.152087 | 0.594536 / 0.530455 / 0.662475 / 0.591213 / 0.090340 | 0.193333 | 0.046692 |
| Rolling 1000/4 | 0.641235 / 0.547046 / 0.724369 / 0.619239 / 0.147589 | 0.513112 / 0.404220 / 0.630805 / 0.520002 / 0.144045 | 0.341667 | 0.104240 |
| Rolling 1000/5 | 0.609990 / 0.480546 / 0.695939 / 0.586204 / 0.139929 | 0.377531 / 0.304437 / 0.466875 / 0.390598 / 0.110156 | 0.555000 | 0.195606 |
| Rolling 1000/6 | 0.510070 / 0.374949 / 0.640108 / 0.509001 / 0.149660 | 0.342561 / 0.294482 / 0.386415 / 0.344794 / 0.066781 | 0.611667 | 0.164244 |
| Rolling 1000/7 | 0.388393 / 0.314808 / 0.498207 / 0.421234 / 0.137605 | 0.489145 / 0.406536 / 0.587366 / 0.486647 / 0.119397 | 0.308333 | 0.072485 |
| Rolling 1000/8 | 0.376817 / 0.308349 / 0.460706 / 0.396673 / 0.121270 | 0.712065 / 0.614313 / 0.774229 / 0.690961 / 0.103893 | 0.820000 | 0.294288 |

Median score-distribution KS was 0.191667 for expanding, 0.290833 for rolling
1600, 0.370833 for rolling 1200, and 0.398333 for rolling 1000. Shortening the
history did not stabilize raw score location relative to the strategy's own
OOF reference; it increased the measured discrepancy.

## Decision Collapse

The table records OOF raw-score q25/q75, BUY/SELL/HOLD, coverage, directional
precisions, pooled action precision, collapse, and causal train-to-validation
feature KS (median/p90 across 102 stationary features).

| Strategy/fold | q25/q75 | B/S/H | Coverage | BUY p. | SELL p. | Pooled p. | Collapse | Feature KS median/p90 |
|---|---|---:|---:|---:|---:|---:|---|---|
| Expanding/1 | 0.451109/0.552423 | 78/48/74 | 0.630000 | 0.397436 | 0.312500 | 0.365079 | no | 0.146794/0.532495 |
| Expanding/2 | 0.506923/0.566277 | 55/62/83 | 0.585000 | 0.436364 | 0.661290 | 0.555556 | no | 0.169800/0.368524 |
| Expanding/3 | 0.504937/0.568340 | 0/120/80 | 0.600000 | 0 | 0.541667 | 0.541667 | yes | 0.156487/0.440635 |
| Expanding/4 | 0.465668/0.554048 | 13/69/118 | 0.410000 | 0.923077 | 0.550725 | 0.609756 | no | 0.137179/0.438325 |
| Expanding/5 | 0.458974/0.531896 | 22/20/158 | 0.210000 | 0.590909 | 0.650000 | 0.619048 | no | 0.164565/0.629609 |
| Expanding/6 | 0.460582/0.517191 | 74/43/83 | 0.585000 | 0.635135 | 0.604651 | 0.623932 | no | 0.112027/0.586783 |
| Expanding/7 | 0.463785/0.526605 | 77/16/107 | 0.465000 | 0.532468 | 0.937500 | 0.602151 | no | 0.128055/0.338615 |
| Expanding/8 | 0.471908/0.527550 | 58/48/94 | 0.530000 | 0.637931 | 0.625000 | 0.632075 | no | 0.136492/0.509229 |
| Rolling 1600/1 | 0.434284/0.616549 | 107/39/54 | 0.730000 | 0.448598 | 0.410256 | 0.438356 | no | 0.095000/0.557688 |
| Rolling 1600/2 | 0.512839/0.698362 | 83/27/90 | 0.550000 | 0.469880 | 0.851852 | 0.563636 | no | 0.134688/0.429563 |
| Rolling 1600/3 | 0.537119/0.719727 | 28/63/109 | 0.455000 | 0.750000 | 0.507937 | 0.582418 | no | 0.124062/0.492875 |
| Rolling 1600/4 | 0.517349/0.721908 | 33/94/73 | 0.635000 | 0.424242 | 0.574468 | 0.535433 | no | 0.083437/0.424688 |
| Rolling 1600/5 | 0.484386/0.701419 | 0/134/66 | 0.670000 | 0 | 0.529851 | 0.529851 | yes | 0.106563/0.626687 |
| Rolling 1600/6 | 0.420141/0.657228 | 0/97/103 | 0.485000 | 0 | 0.515464 | 0.515464 | yes | 0.085938/0.486063 |
| Rolling 1600/7 | 0.398865/0.589522 | 53/58/89 | 0.555000 | 0.679245 | 0.655172 | 0.666667 | no | 0.113750/0.368188 |
| Rolling 1600/8 | 0.388786/0.527185 | 200/0/0 | 1.000000 | 0.485000 | 0 | 0.485000 | yes | 0.087813/0.580875 |
| Rolling 1200/1 | 0.436253/0.596353 | 123/40/37 | 0.815000 | 0.471545 | 0.400000 | 0.453988 | no | 0.089167/0.472500 |
| Rolling 1200/2 | 0.514743/0.672745 | 98/36/66 | 0.670000 | 0.428571 | 0.777778 | 0.522388 | no | 0.139167/0.416500 |
| Rolling 1200/3 | 0.538415/0.693093 | 32/55/113 | 0.435000 | 0.843750 | 0.545455 | 0.655172 | no | 0.156250/0.548417 |
| Rolling 1200/4 | 0.541673/0.710107 | 46/102/52 | 0.740000 | 0.521739 | 0.558824 | 0.547297 | no | 0.074167/0.347917 |
| Rolling 1200/5 | 0.483705/0.697396 | 1/128/71 | 0.645000 | 1.000000 | 0.531250 | 0.534884 | no | 0.109167/0.592333 |
| Rolling 1200/6 | 0.413199/0.664460 | 0/140/60 | 0.700000 | 0 | 0.535714 | 0.535714 | yes | 0.093750/0.525750 |
| Rolling 1200/7 | 0.367314/0.551557 | 53/40/107 | 0.465000 | 0.622642 | 0.450000 | 0.548387 | no | 0.107917/0.336917 |
| Rolling 1200/8 | 0.355058/0.487274 | 197/0/3 | 0.985000 | 0.482234 | 0 | 0.482234 | yes | 0.095833/0.626083 |
| Rolling 1000/1 | 0.401011/0.570923 | 130/35/35 | 0.825000 | 0.507692 | 0.457143 | 0.496970 | no | 0.083500/0.480100 |
| Rolling 1000/2 | 0.475746/0.667206 | 102/35/63 | 0.685000 | 0.421569 | 0.771429 | 0.510949 | no | 0.144000/0.418000 |
| Rolling 1000/3 | 0.493463/0.705486 | 17/32/151 | 0.245000 | 1.000000 | 0.687500 | 0.795918 | no | 0.180500/0.622700 |
| Rolling 1000/4 | 0.547046/0.724369 | 27/113/60 | 0.700000 | 0.555556 | 0.557522 | 0.557143 | no | 0.079000/0.396200 |
| Rolling 1000/5 | 0.480546/0.695939 | 1/159/40 | 0.800000 | 1.000000 | 0.503145 | 0.506250 | no | 0.123000/0.665800 |
| Rolling 1000/6 | 0.374949/0.640108 | 0/136/64 | 0.680000 | 0 | 0.477941 | 0.477941 | yes | 0.087500/0.624100 |
| Rolling 1000/7 | 0.314808/0.498207 | 99/20/81 | 0.595000 | 0.464646 | 0.750000 | 0.512605 | no | 0.104000/0.407300 |
| Rolling 1000/8 | 0.308349/0.460706 | 195/0/5 | 0.975000 | 0.487179 | 0 | 0.487179 | yes | 0.097000/0.642700 |

Expanding collapsed once (fold 3, no BUY). Rolling 1600 collapsed three
times (folds 5 and 6 with no BUY; fold 8 with no SELL). Rolling 1200 and 1000
each collapsed twice (fold 6 with no BUY; fold 8 with no SELL). Thus every
rolling strategy was less directionally stable than the expanding baseline
under the frozen policy.

## Development Selection

The preregistered conjunctive comparison was applied without modification:
median AUC at least expanding plus 0.02, worst AUC above expanding worst,
at least six of eight AUCs above 0.50, positive median AP lift, and fewer
directional-collapse folds than expanding.

| Strategy | Median AUC | Delta vs expanding | Worst AUC | AUC >0.50 | Median AP lift | Collapse folds | Qualifies |
|---|---:|---:|---:|---:|---:|---:|---|
| Rolling 1600 | 0.600702 | +0.027601 | 0.442208 | 6/8 | +0.079953 | 3 | no |
| Rolling 1200 | 0.599930 | +0.026829 | 0.412071 | 6/8 | +0.076238 | 2 | no |
| Rolling 1000 | 0.527958 | -0.045143 | 0.432543 | 5/8 | +0.026092 | 2 | no |

Rolling 1600 and 1200 passed the AUC and AP clauses but failed the strict
collapse clause because expanding collapsed once. Rolling 1000 additionally
failed median-AUC improvement and the six-of-eight clause. The qualifying set
was empty; the shortest-window tie rule was therefore not reached.

## Frozen Strategy

No strategy was selected or frozen. `temporal_strategy_sha256` is not
applicable. No configuration was permitted to enter the historical holdout.

## Fresh Historical Holdout

The reserved range remained exactly `2024-07-01T00:00:00` through
`2024-08-31T23:59:59`, with 1,023 structurally usable positions. It was not
inspected because development produced no winner. Consequently there are no
holdout fold AUCs, AP lifts, actions, pooled precision, or expanding-comparator
metrics. This absence is the required fail-closed result, not missing data.

## Drift Relationship

Score-drift association used fold degradation defined as the strategy median
AUC minus the fold AUC. Across all 32 development results, KS versus
degradation had Pearson `r=+0.238143` (`p=0.189345`) and Spearman
`rho=+0.240836` (`p=0.184240`). Per strategy, Pearson correlations were
-0.530544 for expanding, +0.482793 for rolling 1600, +0.609712 for rolling
1200, and +0.541184 for rolling 1000; none had `p<0.10` with only eight folds.
The pooled association is weak and the baseline sign reverses, so this study
does not establish score-distribution drift as a reliable predictor of model
failure or justify a drift cutoff.

Causal feature drift was the train-to-validation two-sample KS statistic for
each of the 102 stationary features. The median across features and folds was
0.141986 for expanding, 0.100781 for rolling 1600, 0.101875 for rolling 1200,
and 0.100500 for rolling 1000. Shorter windows therefore reduced this
distribution-mismatch summary by roughly 28–29%. That did not translate into
stable score distributions or action direction: rolling score KS increased
and all rolling strategies had more collapse folds. Recency reduces one
measured feature mismatch but does not solve the model's instability.

## Statistical Interpretation

There is partial development evidence that 1,200–1,600 recent rows improve
median rank discrimination and protect the worst AUC relative to an expanding
history. It is not robust enough under the predeclared contract. The benefit
coexists with lower median pooled action precision, materially larger
score-reference drift, and two or three directional collapses versus one for
expanding. The 1,000-row window loses the median-AUC advantage.

The result rejects rolling recency as a sufficient standalone solution. It
does not invalidate the fixed-horizon target in all settings, and it does not
license retrospective changes to the collapse criterion, q25/q75, the model,
or the window set. Because the selection stopped before holdout access, no
claim about July–August 2024 performance is made.

## 2026 Evidence Safety

Rows from 2026 used for feature statistics, target statistics, OOF references,
training, validation, drift, decisions, or metrics: **0**. Rows from 2025 used:
**0**. The known rejected current outer and consumed final tail were neither
reused nor rescored. No alternative actions were produced for them.

No model artifact, `latest_EURUSD.pkl`, lifecycle change, activation,
promotion, trading action, Optuna study, canonical dataset, database update,
or production-source modification was created by this work. EURUSD lifecycle
state remains unchanged.

## Recommended Next Architecture

Do not create a rolling-only `h1_direction_rf_v2`. The next separately
authorized research should test a genuinely new model or causal-information
hypothesis designed for stable bidirectional scores, with an untouched
historical selection/holdout protocol preregistered before access. It should
retain the target and feature identities as explicit comparators, retain
directional-collapse reporting, and must obtain new independent evidence
before any production-contract, eligibility, activation, or promotion work.

## Decision

**ROLLING TRAINING DOES NOT SOLVE H1 INSTABILITY**

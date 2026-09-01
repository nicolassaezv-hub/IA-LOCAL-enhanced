# EURUSD Cross-FX Context V1

## Motivation

This research-only study tested `cross_fx_context_v1`: whether causal relative
EUR and USD strength from other IFC FX pairs improves the robustness of the
rejected EURUSD H1 directional hypothesis. The only experimental change was
information. The target remained `fixed_horizon_direction_v1`, definition
version 1, horizon 12; the base profile remained `stationary_v1`; training was
expanding; and every fit used the frozen Random Forest:

```text
n_estimators=300
max_depth=8
min_samples_leaf=15
class_weight={0: 1.0, 1: train_negative_count / train_positive_count}
random_state=42
n_jobs=-1
```

There was no target, model-family, hyperparameter, rolling-window, threshold,
q25/q75, component, or feature-selection search.

## Evidence Isolation

The research branch was `research/eurusd-cross-fx-context-v1`, created from
source HEAD `f0917968145174c361cc4061a98a405a5c0ed002`. Every provider return
was immediately reduced to timestamps earlier than `2025-01-01T00:00:00` and
then earlier than `2024-09-01T00:00:00`. No retained frame contained 2025 or
2026.

Development feature construction was stricter still: each EURUSD and context
frame was copied and cut at `2024-03-01T00:00:00` before indicators, trailing
returns, causal alignment, target generation, training, or metrics. Thus no
timestamp on or after `2024-07-01T00:00:00` influenced development. The eight
validation blocks occupy a period not used as the main validation range in the
immediately preceding temporal-adaptation study.

`CROSS_FX_HOLDOUT_V1`, from `2024-07-01T00:00:00` through
`2024-08-31T23:59:59`, remained untouched. Development failed its conjunctive
gate, so holdout features, labels, target statistics, OOF references, models,
actions, and metrics were never constructed or inspected.

All fetched data, intermediate CSVs, the harness, and result JSON were
temporary. No canonical CSV, database, parameter cache, model, lifecycle,
activation, promotion, or production source was changed.

## Context Symbol Contract

Preflight occurred before data or model metrics. The canonical ASTRA MT5 route
and the exact `IFCMarkets-Demo` symbol resolved identically for all five frozen
contexts:

| Canonical context | Catalog MT5 symbol | IFC resolved symbol | Available |
|---|---|---|---|
| GBPUSD | GBPUSD | GBPUSD | yes |
| USDCHF | USDCHF | USDCHF | yes |
| USDJPY | USDJPY | USDJPY | yes |
| EURGBP | EURGBP | EURGBP | yes |
| EURJPY | EURJPY | EURJPY | yes |

No context was unavailable. EURJPY therefore remained in the frozen contract;
the reduced EURGBP-only EUR-strength formula was not used. Yahoo, OANDA, DXY,
and performance-based symbol substitution were not used.

## IFC Acquisition

`MT5Provider` connected only to `IFCMarkets-Demo` with
`allow_fallback=False`. Timestamps came through the existing
`ifcmarkets-demo-europe-berlin` clock profile and were normalized to UTC-naive
values. The retained research range was `2021-10-01T00:00:00` through
`2024-08-30T19:00:00` for H1.

| Symbol | TF | Requested | Provider rows | Retained research rows | Oldest | Newest | Invalid dropped |
|---|---|---:|---:|---:|---|---|---:|
| EURUSD | H1 | 30,000 | 30,000 | 17,843 | 2021-10-01 00:00 | 2024-08-30 19:00 | 0 |
| EURUSD | H4 | 8,000 | 8,000 | 4,907 | 2021-07-07 10:00 | 2024-08-30 18:00 | 0 |
| EURUSD | D1 | 1,500 | 1,500 | 983 | 2020-11-18 23:00 | 2024-08-29 22:00 | 0 |
| GBPUSD | H1 | 30,000 | 30,000 | 17,843 | 2021-10-01 00:00 | 2024-08-30 19:00 | 0 |
| USDCHF | H1 | 30,000 | 30,000 | 17,843 | 2021-10-01 00:00 | 2024-08-30 19:00 | 0 |
| USDJPY | H1 | 30,000 | 30,000 | 17,843 | 2021-10-01 00:00 | 2024-08-30 19:00 | 0 |
| EURGBP | H1 | 30,000 | 30,000 | 17,843 | 2021-10-01 00:00 | 2024-08-30 19:00 | 0 |
| EURJPY | H1 | 30,000 | 30,000 | 17,843 | 2021-10-01 00:00 | 2024-08-30 19:00 | 0 |

EURUSD H4/D1 passed through the unchanged production indicator helper and
causal MTF merge needed by `stationary_v1`. The context symbols used only H1
closed prices.

## Causal Alignment

MT5 candle timestamps represent candle opening. For both EURUSD and every
context H1 row, availability was defined as opening timestamp plus one hour.
For each EURUSD row, `merge_asof(direction="backward")` selected only a
context row satisfying:

```text
context_available_timestamp <= eurusd_available_timestamp
```

All 40 symbol/fold no-lookahead assertions passed. Each of the five symbols
had 200/200 valid rows in each of eight validation folds: 1,600/1,600 in
aggregate, 0% missing, 100% availability, and maximum context age 0 hours.
The minimum across every symbol/fold cell was therefore 100%, exceeding the
98% data-contract requirement. No future fill, global fill, scaler, or
arbitrary context substitution occurred.

The deterministic, non-overlapping 200-row validation geometry was spread
chronologically across the preregistered preferred period:

| Fold | Validation start | Validation end |
|---:|---|---|
| 1 | 2023-07-03 01:00 | 2023-07-13 13:00 |
| 2 | 2023-08-03 02:00 | 2023-08-15 19:00 |
| 3 | 2023-09-05 09:00 | 2023-09-18 02:00 |
| 4 | 2023-10-06 10:00 | 2023-10-19 03:00 |
| 5 | 2023-11-08 18:00 | 2023-11-21 11:00 |
| 6 | 2023-12-12 00:00 | 2023-12-22 12:00 |
| 7 | 2024-01-16 16:00 | 2024-01-29 09:00 |
| 8 | 2024-02-16 18:00 | 2024-02-29 11:00 |

Training used all prior eligible rows and stopped 20 rows before validation.
For all 16 A/B fits and all OOF subfits, the maximum training-target terminal
timestamp was strictly earlier than validation start. Each profile/fold used
600 training-only OOF scores from three preceding 200-row blocks.

## Cross-FX Feature Contract

The base profile retained all 102 `stationary_v1` features in exact order and
matched SHA-256
`5f51168349400e31bfe891c78a1833e1618166c478d3c0bebba983728b551791`.
`stationary_cross_fx_v1` appended exactly 36 features, for 138 total and
ordered feature SHA-256
`453ed70d393f5982d5b1a7edaa0340445e57da50998774a6d5963dec00b4a5d4`.

For each of GBPUSD, USDCHF, USDJPY, EURGBP, and EURJPY, four causal returns
were appended in frozen pair order and horizon order 1, 3, 6, 12:

```text
ctx_<pair>_ret_h = close[t] / close[t-h] - 1
```

For each horizon `h`, the remaining formulas were:

```text
usd_strength_h = mean(-GBPUSD_ret_h, +USDCHF_ret_h, +USDJPY_ret_h)
eur_strength_h = mean(+EURGBP_ret_h, +EURJPY_ret_h)
eur_minus_usd_h = eur_strength_h - usd_strength_h
fx_context_dispersion_h = population_std(
    -GBPUSD_ret_h, +USDCHF_ret_h, +USDJPY_ret_h,
    +EURGBP_ret_h, +EURJPY_ret_h
)
```

The deterministic appended order was the 20 pair returns, four
`usd_strength_*`, four `eur_strength_*`, four `eur_minus_usd_*`, and four
`fx_context_dispersion_*`. No raw price, raw EMA level, learned weight, or
selected subset entered the profile.

## Development Baseline

| Fold | Train rows | Validation | Pos/neg | Prev. | AUC | AP | AP lift | Brier | Top-10 p. | mean p+ / p- |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 10,357 | 2023-07-03–2023-07-13 | 133/67 | 0.665000 | 0.403771 | 0.650928 | -0.014072 | 0.287292 | 0.650000 | 0.450758 / 0.486561 |
| 2 | 10,890 | 2023-08-03–2023-08-15 | 99/101 | 0.495000 | 0.625463 | 0.623136 | +0.128136 | 0.244731 | 0.550000 | 0.487688 / 0.465627 |
| 3 | 11,424 | 2023-09-05–2023-09-18 | 97/103 | 0.485000 | 0.608548 | 0.611160 | +0.126160 | 0.246111 | 0.750000 | 0.561518 / 0.541091 |
| 4 | 11,957 | 2023-10-06–2023-10-19 | 110/90 | 0.550000 | 0.649091 | 0.642084 | +0.092084 | 0.239929 | 0.650000 | 0.493081 / 0.456357 |
| 5 | 12,491 | 2023-11-08–2023-11-21 | 121/79 | 0.605000 | 0.401506 | 0.543620 | -0.061380 | 0.278314 | 0.450000 | 0.426263 / 0.442381 |
| 6 | 13,024 | 2023-12-12–2023-12-22 | 142/58 | 0.710000 | 0.676785 | 0.822004 | +0.112004 | 0.242775 | 0.900000 | 0.499577 / 0.465831 |
| 7 | 13,558 | 2024-01-16–2024-01-29 | 94/106 | 0.470000 | 0.658671 | 0.571431 | +0.101431 | 0.238288 | 0.600000 | 0.523957 / 0.494073 |
| 8 | 14,092 | 2024-02-16–2024-02-29 | 106/94 | 0.530000 | 0.595845 | 0.650704 | +0.120704 | 0.246237 | 0.850000 | 0.466451 / 0.443809 |

Baseline median/mean/worst AUC was
0.617005/0.577460/0.401506, with population AUC standard deviation 0.103880.
Six of eight folds exceeded 0.50 and six reached 0.55. Median AP lift was
`+0.106718`; six folds had positive lift. Median Brier was 0.245421. Median BUY,
SELL, and pooled emitted precision were 0.561688, 0.512824, and 0.522627;
median coverage was 0.502500. One fold collapsed directionally.

## Development Cross-FX

| Fold | Train rows | Validation | Pos/neg | Prev. | AUC | AP | AP lift | Brier | Top-10 p. | mean p+ / p- |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 10,357 | 2023-07-03–2023-07-13 | 133/67 | 0.665000 | 0.437998 | 0.663143 | -0.001857 | 0.284800 | 0.700000 | 0.452154 / 0.484185 |
| 2 | 10,890 | 2023-08-03–2023-08-15 | 99/101 | 0.495000 | 0.612661 | 0.599339 | +0.104339 | 0.243020 | 0.500000 | 0.490533 / 0.470647 |
| 3 | 11,424 | 2023-09-05–2023-09-18 | 97/103 | 0.485000 | 0.604944 | 0.545125 | +0.060125 | 0.243777 | 0.650000 | 0.532369 / 0.513810 |
| 4 | 11,957 | 2023-10-06–2023-10-19 | 110/90 | 0.550000 | 0.616768 | 0.628112 | +0.078112 | 0.244822 | 0.550000 | 0.479836 / 0.450920 |
| 5 | 12,491 | 2023-11-08–2023-11-21 | 121/79 | 0.605000 | 0.452453 | 0.590757 | -0.014243 | 0.271765 | 0.450000 | 0.434977 / 0.442310 |
| 6 | 13,024 | 2023-12-12–2023-12-22 | 142/58 | 0.710000 | 0.691476 | 0.832648 | +0.122648 | 0.244528 | 0.900000 | 0.494514 / 0.459833 |
| 7 | 13,558 | 2024-01-16–2024-01-29 | 94/106 | 0.470000 | 0.663890 | 0.614945 | +0.144945 | 0.238038 | 0.700000 | 0.524796 / 0.494993 |
| 8 | 14,092 | 2024-02-16–2024-02-29 | 106/94 | 0.530000 | 0.592533 | 0.614297 | +0.084297 | 0.246528 | 0.750000 | 0.470039 / 0.450401 |

Cross-FX median/mean/worst AUC was
0.608803/0.584091/0.437998, with AUC standard deviation 0.085850. Six folds
exceeded 0.50 and six reached 0.55. Median AP lift was +0.081204; six folds
had positive lift. Median Brier was 0.244675. Median BUY, SELL, and pooled
precision were 0.586885, 0.576726, and 0.582057; median coverage was 0.440000.
No fold collapsed directionally.

## Ranking Stability

Each distribution cell is `median / q25 / q75 / population std`. Location
shift is validation median minus OOF median; dispersion shift is validation
standard deviation minus OOF standard deviation.

| Profile/fold | OOF score distribution | Validation score distribution | KS | Wasserstein | Location shift | Dispersion shift |
|---|---|---|---:|---:|---:|---:|
| Base/1 | 0.482122 / 0.441975 / 0.540958 / 0.077045 | 0.475788 / 0.453263 / 0.514430 / 0.087526 | 0.176667 | 0.032525 | -0.006334 | +0.010482 |
| Base/2 | 0.490193 / 0.404604 / 0.574199 / 0.143738 | 0.462319 / 0.427236 / 0.525470 / 0.073791 | 0.161667 | 0.058407 | -0.027874 | -0.069947 |
| Base/3 | 0.471794 / 0.429667 / 0.531130 / 0.070482 | 0.546480 / 0.520615 / 0.588295 / 0.046742 | 0.511667 | 0.069179 | +0.074686 | -0.023740 |
| Base/4 | 0.537398 / 0.496294 / 0.573638 / 0.054408 | 0.465493 / 0.409644 / 0.549152 / 0.072205 | 0.408333 | 0.054124 | -0.071905 | +0.017797 |
| Base/5 | 0.469926 / 0.415691 / 0.528329 / 0.069290 | 0.436240 / 0.398922 / 0.456466 / 0.043859 | 0.368333 | 0.041474 | -0.033686 | -0.025431 |
| Base/6 | 0.471025 / 0.433312 / 0.531428 / 0.078728 | 0.493964 / 0.464205 / 0.523588 / 0.047748 | 0.216667 | 0.031946 | +0.022940 | -0.030980 |
| Base/7 | 0.511423 / 0.478935 / 0.531892 / 0.044967 | 0.507939 / 0.475350 / 0.548531 / 0.051218 | 0.128333 | 0.008149 | -0.003484 | +0.006252 |
| Base/8 | 0.512506 / 0.481468 / 0.548739 / 0.052569 | 0.469791 / 0.426931 / 0.493145 / 0.053972 | 0.415000 | 0.052899 | -0.042715 | +0.001403 |
| Cross-FX/1 | 0.482925 / 0.448181 / 0.529893 / 0.064491 | 0.480629 / 0.452605 / 0.508653 / 0.083083 | 0.163333 | 0.027266 | -0.002296 | +0.018593 |
| Cross-FX/2 | 0.497812 / 0.435091 / 0.560426 / 0.126169 | 0.482089 / 0.436962 / 0.525610 / 0.052696 | 0.215000 | 0.052421 | -0.015724 | -0.073474 |
| Cross-FX/3 | 0.483120 / 0.435184 / 0.530817 / 0.057615 | 0.526123 / 0.496428 / 0.556080 / 0.042932 | 0.341667 | 0.038402 | +0.043002 | -0.014683 |
| Cross-FX/4 | 0.524808 / 0.483063 / 0.557522 / 0.052520 | 0.463095 / 0.401525 / 0.534164 / 0.068677 | 0.391667 | 0.052031 | -0.061713 | +0.016158 |
| Cross-FX/5 | 0.468474 / 0.414628 / 0.525146 / 0.064364 | 0.439228 / 0.411601 / 0.462681 / 0.036795 | 0.351667 | 0.033544 | -0.029246 | -0.027569 |
| Cross-FX/6 | 0.477020 / 0.440010 / 0.522899 / 0.066730 | 0.492698 / 0.456852 / 0.520367 / 0.045154 | 0.188333 | 0.021707 | +0.015678 | -0.021576 |
| Cross-FX/7 | 0.507176 / 0.486726 / 0.531079 / 0.039452 | 0.512099 / 0.479058 / 0.540188 / 0.047590 | 0.091667 | 0.009392 | +0.004923 | +0.008138 |
| Cross-FX/8 | 0.511362 / 0.481436 / 0.537752 / 0.048963 | 0.471885 / 0.432536 / 0.494152 / 0.049242 | 0.401667 | 0.044418 | -0.039477 | +0.000279 |

Median KS improved modestly from 0.292500 to 0.278333. Median location shift
moved from -0.017104 to -0.009010 and median dispersion shift from -0.011168
to -0.007202. Cross-market context therefore modestly stabilized these score
distribution summaries, but did not improve aggregate rank discrimination.

## Bidirectional Stability

The existing score-only `oof_quartile_abstention_v1` policy used fixed
empirical percentiles 0.25/0.75. The table records BUY/SELL/HOLD, coverage,
directional precision, pooled precision, and collapse.

| Profile/fold | B/S/H | Coverage | BUY precision | SELL precision | Pooled precision | Collapse |
|---|---:|---:|---:|---:|---:|---|
| Base/1 | 19/36/145 | 0.275000 | 0.684211 | 0.277778 | 0.418182 | no |
| Base/2 | 26/27/147 | 0.265000 | 0.538462 | 0.444444 | 0.490566 | no |
| Base/3 | 126/2/72 | 0.640000 | 0.547619 | 1.000000 | 0.554688 | no |
| Base/4 | 19/117/64 | 0.680000 | 0.631579 | 0.564103 | 0.573529 | no |
| Base/5 | 8/73/119 | 0.405000 | 0.375000 | 0.315068 | 0.320988 | no |
| Base/6 | 37/25/138 | 0.310000 | 0.891892 | 0.560000 | 0.758065 | no |
| Base/7 | 66/54/80 | 0.600000 | 0.575758 | 0.814815 | 0.683333 | no |
| Base/8 | 0/131/69 | 0.655000 | 0 | 0.465649 | 0.465649 | yes |
| Cross-FX/1 | 24/43/133 | 0.335000 | 0.750000 | 0.255814 | 0.432836 | no |
| Cross-FX/2 | 8/48/144 | 0.280000 | 0.625000 | 0.604167 | 0.607143 | no |
| Cross-FX/3 | 90/7/103 | 0.485000 | 0.566667 | 1.000000 | 0.597938 | no |
| Cross-FX/4 | 21/115/64 | 0.680000 | 0.571429 | 0.565217 | 0.566176 | no |
| Cross-FX/5 | 2/54/144 | 0.280000 | 0.500000 | 0.333333 | 0.339286 | no |
| Cross-FX/6 | 45/34/121 | 0.395000 | 0.844444 | 0.588235 | 0.734177 | no |
| Cross-FX/7 | 61/63/76 | 0.620000 | 0.573770 | 0.714286 | 0.645161 | no |
| Cross-FX/8 | 5/121/74 | 0.630000 | 0.600000 | 0.495868 | 0.500000 | no |

Cross-FX eliminated the baseline's single collapse and raised median BUY,
SELL, and pooled precision while reducing median coverage from 0.502500 to
0.440000. These are useful diagnostics, but they cannot override the primary
conjunctive development gate.

## Development Gate

| Required conjunct | Result | Pass |
|---|---|---|
| Median AUC >= baseline + 0.02 | 0.608803 vs required 0.637005 | no |
| Median AUC >= 0.56 | 0.608803 | yes |
| Worst AUC > baseline worst | 0.437998 > 0.401506 | yes |
| At least 6/8 AUC > 0.50 | 6/8 | yes |
| Median AP lift > 0 | +0.081204 | yes |
| Median AP lift >= baseline | 0.081204 < 0.106718 | no |
| Collapse folds <= 1 | 0 | yes |
| Collapse improves baseline or baseline is zero | 0 < 1 | yes |
| Median BUY precision > 0.50 | 0.586885 | yes |
| Median SELL precision > 0.50 | 0.576726 | yes |

The gate failed exactly two conjuncts. Candidate median AUC was 0.008202 below
baseline rather than at least 0.02 above it, and median AP lift was 0.025514
below baseline. The development gate result is **FAIL**.

## Frozen Candidate

No candidate was frozen and `cross_fx_candidate_sha256` is not applicable.
The holdout could not be opened. No post-metric component ablation or formula,
symbol, horizon, weight, feature-order, or gate change was attempted.

## Fresh Holdout

`CROSS_FX_HOLDOUT_V1` remained uninspected. There are no holdout baseline or
candidate fold AUCs, AP lifts, actions, precisions, coverage, pooled precision,
or context-availability metrics. This is the required fail-closed consequence
of the failed development gate, not a missing execution.

## Feature Importance Diagnostic

Importance was diagnostic only and was averaged across the eight fitted
Cross-FX development forests. Ranks are among all 138 features; they did not
select, remove, or retune anything.

| Feature | Mean importance | Rank |
|---|---:|---:|
| eur_minus_usd_1 | 0.001653 | 115 |
| eur_minus_usd_3 | 0.003004 | 86 |
| eur_minus_usd_6 | 0.003773 | 73 |
| eur_minus_usd_12 | 0.005563 | 60 |
| usd_strength_1 | 0.001661 | 114 |
| usd_strength_3 | 0.002710 | 92 |
| usd_strength_6 | 0.005983 | 56 |
| usd_strength_12 | 0.006929 | 46 |
| eur_strength_1 | 0.001818 | 110 |
| eur_strength_3 | 0.003695 | 75 |
| eur_strength_6 | 0.006713 | 48 |
| eur_strength_12 | 0.012976 | 28 |

The ten strongest added features were `eur_strength_12` (rank 28),
`ctx_usdchf_ret_12` (32), `ctx_eurgbp_ret_12` (33),
`ctx_eurjpy_ret_12` (37), `ctx_usdjpy_ret_12` (43),
`ctx_usdjpy_ret_6` (45), `usd_strength_12` (46), `eur_strength_6` (48),
`ctx_usdchf_ret_6` (50), and `ctx_gbpusd_ret_12` (53). The stronger ranks of
longer horizons are descriptive only; no ablation or new hypothesis was run.

## 2026 Safety

Rows from 2026 used for features, targets, availability, training, OOF,
selection, actions, importance, or metrics: **0**. The consumed current outer
was not reused. The consumed final tail was not reused. Its feature values,
scores, and alternative actions were not loaded or reproduced.

EURUSD remains `qualified`, with no production model. No model artifact,
`latest_EURUSD.pkl`, database mutation, lifecycle transition, activation,
promotion, trading action, canonical dataset, parameter cache, or production
source modification occurred.

## Recommended Next Architecture

Do not add `stationary_cross_fx_v1` to production and do not reopen the held-out
period. The bundle improves bidirectional behavior and modestly stabilizes
scores, but it does not improve the primary ranking evidence over the existing
information set. Any next task should preregister a genuinely distinct causal
information hypothesis and a new untouched evaluation protocol; it must not
post-hoc ablate this bundle against the still-unopened holdout in this task.

## Decision

**CROSS-FX CONTEXT DOES NOT SOLVE H1 INSTABILITY**

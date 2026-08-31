# Controlled EURUSD IFC Qualification

## Source Baseline

The reviewed session/holiday implementation was
`3bf2a8e039b698bb83caff8da5691ec7cdf9e742`, with its established suite result
of 788 passed, 10 skipped, and zero failed. Repository hygiene was then fixed
without changing Python behavior by commit
`ef6842b42223dce4c54562ff8c0fd0cbe1355b10`, which became the exact source
HEAD used for qualification.

The pre-existing untracked files were exclusively:

- `data/qualification/EURUSD/EURUSD_H1.csv`
- `data/qualification/EURUSD/EURUSD_H4.csv`
- `data/qualification/EURUSD/EURUSD_D1.csv`
- `data/qualification/EURUSD/evidence.json`

They are expected qualification runtime. Four additional JSON artifacts under
`data/forex_analytics/` were known runtime already covered by the existing
specific ignore rule. No unknown untracked file was found. The new
`/data/qualification/` rule is deliberately narrower than `/data/`.

## Safety Scope

Exactly one qualification call was authorized and executed. Candidate rolling
datasets, durable qualification evidence, and the lifecycle transition from
`candidate` to `qualified` were the only expected mutations. No activation,
training, model promotion, scheduler cycle, canonical dataset promotion,
trading request, Oracle operation, or provider fallback was executed.

## MT5 Preflight

The runtime was Python 3.12.6 with MetaTrader5 importable and initialization
successful. Only the approved safe account fields were inspected:

- server: `IFCMarkets-Demo`
- company: `IFCMarkets. Corp.`

Direct hardened `MT5Provider` fetches returned exactly five valid bars for each
of H1, H4, and D1. Every timeframe reported provider `MT5`, observed server
`IFCMarkets-Demo`, source timezone `Europe/Berlin`, profile
`ifcmarkets-demo-europe-berlin`, normalization
`SERVER_WALL_TIME_TO_UTC`, and zero invalid OHLC rows.

## Pre-State

EURUSD already existed with status `candidate`, so no registration call was
made. Its qualification evidence fields were unset. EURUSD had zero dataset
registry rows and no canonical H1, H4, or D1 file.

Previous qualification-runtime SHA-256 values were:

- H1: `388cb95cd29899a8d5dbd6d2ec74e5db2f315f51eecd9fb3286fe5a3a3d9c03e`
- H4: `d2e7c0b51ea99dec0e7ffd161f920b93b90ced917522e348682c63fbab2345f7`
- D1: `ee2b75907b66c9b5c3f5db8701294b980aaf19f78ef4e2f94639f5b3d5fb70f1`
- evidence: `84523f2ae24c1908f79612c4ba6b280ef640f425eef9b6331b1c0c609754f4b8`

## IFC-Only Router

The temporary in-memory `IFCOnlyRouter` accepted only `EURUSD`, selected only
the catalogued MT5 route, and invoked `get_mt5_provider().fetch()` with
`allow_fallback=False`. It exposed `source_used=MT5`, the exact MT5 route and
acquisition metadata, and an empty `attempt_errors` tuple. It contained no
OANDA, Yahoo, retry, synthetic-data, or persistence route. Any MT5 exception
would have propagated immediately.

`qualify_candidate()` was called exactly once.

## H1 Qualification

H1 returned `PASS` using provider `MT5`, external ticker `EURUSD`, and provider
class `BROKER`. The candidate contains exactly 2000 rows from
`2026-05-04 09:00:00 UTC` through `2026-08-31 02:00:00 UTC`.

The live rolling frame contains 17 logical gaps. This count is observational,
not a fixed gate. All gaps are authorized; provider gaps and unexplained
positions are both zero. Duplicate timestamps, future candles, invalid OHLC,
and negative-volume rows are zero, and all 2000 rows are closed.

## H4 Qualification

H4 returned `PASS` using native MT5 data, external ticker `EURUSD`, and provider
class `BROKER`. The candidate contains exactly 2000 rows from
`2025-05-15 14:00:00 UTC` through `2026-08-30 22:00:00 UTC`.

All 70 observed logical gaps are authorized weekend/session closures. Provider
gaps and unexplained positions are zero. Duplicate timestamps, future candles,
invalid OHLC, and negative-volume rows are zero, and all 2000 rows are closed.

## D1 Qualification

D1 returned `PASS` using native MT5 data, external ticker `EURUSD`, and provider
class `BROKER`. The candidate contains exactly 2000 rows from
`2018-12-11 23:00:00 UTC` through `2026-08-27 22:00:00 UTC`.

The frame still contains all 12 historical holiday events and all 12 are
authorized. Provider gaps and unexplained positions are zero. Duplicate
timestamps, future candles, invalid OHLC, and negative-volume rows are zero,
and all 2000 rows are closed.

## Cross-Timeframe

The qualification cross-timeframe stage returned `PASS` with `blocking=false`,
no errors, and no warnings. H1-to-H4 and H4-to-D1 both returned `PASS` using
the existing unchanged tolerances.

Read-only post-validation independently reloaded the three candidate CSVs and
reconfirmed the same non-blocking result. All 12 contractual indicators passed
in each timeframe.

## Qualification Evidence

The durable evidence file is
`data/qualification/EURUSD/evidence.json`. It records result `PASS`, symbol
`EURUSD`, current catalog version
`0e1998ea743556edb42412114597ce033fe86a2f52785cb7b61595d0383f10e8`,
PASS for H1/H4/D1, and non-blocking cross-timeframe PASS.

Its SHA-256 is
`9c6e6c0a08d048044f2fa8b707b567332626dabfb44219d707b59b91a8a9e59a`,
which exactly matches the database `qualification_sha256`. The database path
and every candidate path/SHA also match the evidence.

## Database Transition

EURUSD transitioned exactly once from `candidate` to `qualified`. Its final
record remains `activation_origin=managed`, stores the current catalog version,
and points to the durable evidence with the matching SHA. It was not activated.

## Candidate Artifacts

All three expected qualification artifacts changed from the pre-snapshot and
were left untouched after qualification:

- H1: 2000 rows, SHA-256 `7a1418610d5c8d90e884b68af3cd13dcd0537e63768d68bcc59f3d7eaf81bc27`
- H4: 2000 rows, SHA-256 `9d805c070c3a3119efdd1c1823e16e732beff7d927037e7a6aa56c653ef4f66b`
- D1: 2000 rows, SHA-256 `1913093a055bfe0746b16d87305c23a5f688970538f2fab6c43240c859b49bdf`

The runtime files remain ignored and are not part of any Git commit.

## Canonical Registry Safety

The EURUSD dataset registry contained zero rows before and after qualification.
Its deterministic snapshot hash remained
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
No canonical registry mutation occurred.

## Canonical Dataset Safety

`data/forex/EURUSD_H1.csv`, `EURUSD_H4.csv`, and `EURUSD_D1.csv` were absent
before qualification and remain absent afterward. Qualification did not create,
replace, or promote a canonical dataset.

## Model Safety

The six pre-existing EURUSD model/parameter artifacts retained the same paths,
sizes, and SHA-256 inventory after qualification. No model was trained,
created, deleted, moved, promoted, or aliased.

## Activation Status

No activation function or CLI command was executed. EURUSD ends at
`qualified`, not `active`. No MT5 `order_send`, `order_check`, trade request,
or position mutation was performed.

## Remaining Gates

Qualification is complete. Training, WFV, calibration, validation, model
eligibility, and any later controlled activation remain separate mandatory
phases. This task authorizes none of them.

## Decision

**EURUSD QUALIFIED — READY FOR TRAINING/MODEL ELIGIBILITY PHASE**

# EURUSD Canonical Training Preflight

## Baseline

The controlled preflight ran on branch `fix/ifc-2020-holiday-authority` at
source HEAD `dc9905fc8c4a9a1936c0d75407ac0983cd869205`. This HEAD already had an
accepted suite result of 788 passed, 10 skipped, and zero failed. No tracked
source file was modified during canonical generation or model audit.

The only authorized runtime mutations were three canonical EURUSD rolling
datasets and their three dataset-registry rows. No training, model mutation,
activation, prediction, autonomous scheduler cycle, Oracle operation, or
trading operation was executed.

## Qualification State

EURUSD started and finished with lifecycle status `qualified`. Its durable
qualification evidence remained at
`data/qualification/EURUSD/evidence.json` with unchanged SHA-256
`9c6e6c0a08d048044f2fa8b707b567332626dabfb44219d707b59b91a8a9e59a`,
which still matches the database.

The H1, H4, and D1 qualification candidates also retained their pre-task
hashes. Canonical generation did not rewrite qualification runtime.

## IFC MT5 Preflight

Python 3.12.6 imported and initialized MetaTrader5 successfully. The approved
safe connection fields were:

- server: `IFCMarkets-Demo`
- company: `IFCMarkets. Corp.`

Direct five-bar H1/H4/D1 fetches each returned valid OHLC with provider `MT5`,
server `IFCMarkets-Demo`, source timezone `Europe/Berlin`, profile
`ifcmarkets-demo-europe-berlin`, and normalization
`SERVER_WALL_TIME_TO_UTC`.

For canonical generation, `scheduler.autonomous_scheduler.fetch_market_data`
was replaced only inside one temporary Python process with an EURUSD-only
function backed by `get_mt5_provider()`. It invoked MT5 with
`allow_fallback=False` and propagated any exception. No DataRouter, OANDA,
Yahoo, retry, or synthetic source was available.

Exactly three `run_rolling_update` calls were made: one each for H1, H4, and
D1. All returned `action=generated`, `status=ready`, `total=2000`, and
`source=MT5`.

## Canonical H1

- path: `data/forex/EURUSD_H1.csv`
- rows: 2000
- first timestamp: `2026-05-04 10:00:00 UTC`
- last timestamp: `2026-08-31 03:00:00 UTC`
- SHA-256: `868eb4a92006de5c42fdd6465d923284f5d56a2448e740b1df38a9edc45d8f67`
- registry evidence ID: 1
- registry readiness: true, no reasons, provenance `VERIFIED`
- provider gaps: 0
- unexplained positions: 0
- observed logical gaps: 17

The frame has zero invalid OHLC rows, duplicate timestamps, future/incomplete
candles, and negative-volume rows. All 12 indicators pass. The candidate ended
at `2026-08-31 02:00:00 UTC`; the canonical frame advanced normally by one
closed H1 candle.

## Canonical H4

- path: `data/forex/EURUSD_H4.csv`
- rows: 2000
- first timestamp: `2025-05-15 14:00:00 UTC`
- last timestamp: `2026-08-30 22:00:00 UTC`
- SHA-256: `9d805c070c3a3119efdd1c1823e16e732beff7d927037e7a6aa56c653ef4f66b`
- registry evidence ID: 2
- registry readiness: true, no reasons, provenance `VERIFIED`
- provider gaps: 0
- unexplained positions: 0
- observed logical gaps: 70

The frame has zero invalid OHLC rows, duplicate timestamps, future/incomplete
candles, and negative-volume rows. All 12 indicators pass. Candidate and
canonical latest timestamps coincide; no SHA identity was required.

## Canonical D1

- path: `data/forex/EURUSD_D1.csv`
- rows: 2000
- first timestamp: `2018-12-11 23:00:00 UTC`
- last timestamp: `2026-08-27 22:00:00 UTC`
- SHA-256: `1913093a055bfe0746b16d87305c23a5f688970538f2fab6c43240c859b49bdf`
- registry evidence ID: 3
- registry readiness: true, no reasons, provenance `VERIFIED`
- provider gaps: 0
- unexplained positions: 0
- historical holiday events: 12 observed, 12 authorized

The frame has zero invalid OHLC rows, duplicate timestamps, future/incomplete
candles, and negative-volume rows. All 12 indicators pass. Candidate and
canonical latest timestamps coincide; no SHA identity was required.

## Registry Readiness

The post-generation EURUSD registry contains exactly H1, H4, and D1. Every row
has `status=ready`, `candle_count=2000`, `rolling_window_size=2000`, provider
`MT5`, provider class `BROKER`, external ticker `EURUSD`, a source-fetch time,
and `legacy_provenance_pending=0`.

Each registry `source_sha256` equals its physical canonical file. Acquisition
metadata is present and validated as `VERIFIED`, including exact server,
timezone, clock profile, normalization, and dataset SHA binding.

## Cross-Timeframe

Read-only canonical validation returned non-blocking results for H1, H4, and
D1. All 36 indicator checks passed with unchanged tolerances. Cross-timeframe
validation returned `PASS`, `blocking=false`; H1-to-H4 and H4-to-D1 both
returned `PASS`.

## Training Snapshot

`RetrainManager.capture_training_snapshot("EURUSD")` completed read-only and
`validate_training_snapshot(snapshot)` reproduced an exact match. The snapshot
SHA-256 is
`f4e77d47ab061f72a65ceb0d7733ba6d026422795119566eb5433180c5b1a3d2`.

Its bound datasets are:

- H1: evidence ID 1, 2000 rows, latest `2026-08-31 03:00:00`, SHA-256 `868eb4a92006de5c42fdd6465d923284f5d56a2448e740b1df38a9edc45d8f67`
- H4: evidence ID 2, 2000 rows, latest `2026-08-30 22:00:00`, SHA-256 `9d805c070c3a3119efdd1c1823e16e732beff7d927037e7a6aa56c653ef4f66b`
- D1: evidence ID 3, 2000 rows, latest `2026-08-27 22:00:00`, SHA-256 `1913093a055bfe0746b16d87305c23a5f688970538f2fab6c43240c859b49bdf`

All paths resolve to the exact canonical `data/forex/` root.

## Existing Model Inventory

Six EURUSD-related files exist under `models/forex/`; inventory was performed
without deserializing arbitrary artifacts:

- `ensemble_EURUSD_20260806_011320.pkl` — 1,571,228 bytes — SHA-256 `31fb37d8449a8460563a1b4f2ee27de31662adfaf7be85d964c8b7e8a825d615` — mtime `2026-08-06T01:13:20Z`
- `ensemble_EURUSD_20260806_011330.pkl` — 1,589,372 bytes — SHA-256 `a36afe27dd51fec532feba7a95d5327799a829e010d5c16f51c70722260d16b6` — mtime `2026-08-06T01:13:30Z`
- `ensemble_EURUSD_20260806_051342.pkl` — 4,536,004 bytes — SHA-256 `62cd79e47fff4bfac7558d21aeed17c0190c5f523fc96e75ca4da136d110c1bf` — mtime `2026-08-06T05:13:42Z`
- `ensemble_EURUSD_20260806_051425.pkl` — 1,571,452 bytes — SHA-256 `cf22ead0e88f5a71c730e4462e3ac7e29503e9652067c73ffa2cb41f649a9c07` — mtime `2026-08-06T05:14:24Z`
- `legacy_unverified/latest_EURUSD_cf22ead0e88f5a71c730e4462e3ac7e29503e9652067c73ffa2cb41f649a9c07.pkl` — 1,571,452 bytes — SHA-256 `cf22ead0e88f5a71c730e4462e3ac7e29503e9652067c73ffa2cb41f649a9c07` — mtime `2026-08-06T05:14:24Z`
- `params/best_params_EURUSD.json` — 715 bytes — SHA-256 `3c4d6147c9647f2f5e19db7b94384306caabece0c5e62cabe9cb5af0c5148961` — mtime `2026-08-06T01:07:02Z`

The inventory, sizes, hashes, and mtimes are identical before and after this
task. No candidate or rollback model file exists.

## Latest EURUSD Alias

The executable alias `models/forex/latest_EURUSD.pkl` does not exist. It
therefore has no SHA, feature-name payload, or metadata keys, and artifact
validation is not applicable. The similarly named file under
`legacy_unverified/` is quarantined historical state, not the executable alias.

## Model Provenance

Read-only database inspection found:

- model provenance rows for EURUSD: 0
- retrain-run rows for EURUSD: 0
- H1 model-quality rows for EURUSD: 0

Counts, statuses, and deterministic row fingerprints were unchanged by
canonical generation. `reconcile()` was intentionally not called because it
can mutate interrupted-run recovery state.

## Model Eligibility Audit

`RetrainManager.audit_pair_model("EURUSD")` returned exactly:

```text
eligible=false
reason=MODEL_NOT_DEPLOYED
```

It did not return `bootstrap_revalidation=true`. No existing artifact was
adopted, certified, promoted, or given retroactive provenance.

## Initial Training Collision

`ForexIntegratedPipeline.train()` reaches `_promote_initial_training()` only
after quality, WFV, calibration, validation, and `model_valid` all pass. That
method delegates to `RetrainManager.promote_initial_model()`, which rejects an
existing `latest_EURUSD.pkl` rather than overwriting it.

Because that exact executable alias is absent, initial training is not blocked
by an alias collision. No promotion was attempted in this task.

## Recommended Training Path

The appropriate next path is `CLEAN_INITIAL_TRAINING`, using the captured
canonical snapshot and all existing fail-closed quality gates. Bootstrap
revalidation is neither required nor authorized because there is no deployed
EURUSD alias to revalidate.

## Safety Verification

EURUSD remains `qualified` and its qualification evidence is unchanged.
Candidate datasets are unchanged. Models, model provenance, retrain runs, and
model quality are unchanged. No activation, prediction, training, model
promotion, scheduler cycle, trading request, or Oracle action occurred.
Canonical datasets, DB runtime, and qualification/model runtime remain ignored
and are not included in Git.

## Decision

**CANONICAL READY — CLEAN INITIAL TRAINING POSSIBLE**

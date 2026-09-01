# Forex Shadow Runtime — EURUSD + USDJPY

## Objective

Prepare a non-trading H1 shadow runtime for independent EURUSD and USDJPY observation with mandatory H4 and D1 context. Source implementation and tests are complete. Real runtime preparation stopped at the mandatory USDJPY qualification gate.

## Runtime Scope

- Runtime symbols: `EURUSD,USDJPY`.
- Primary timeframe: H1.
- Required context: H4 and D1 from the same symbol.
- Shadow mode defaults to disabled.
- No cross-FX features or rows are accepted.

## Shadow Safety

The shadow route is separate from production prediction. Eligibility requires lifecycle `qualified`, enabled shadow mode, and explicit symbol configuration. It cannot activate a symbol, publish a production alias, promote a production model, call the Decision Engine for execution, or place an order. BUY, SELL, and HOLD are observational records only.

## Provider

The controlled preflight connected successfully to native MT5 with `availability_state=ACCOUNT_CONNECTED`, `terminal_connected=true`, and server `IFCMarkets-Demo`. Shadow acquisitions use the pinned MT5 provider directly and do not construct `DataRouter`, so OANDA/Yahoo fallback is unavailable.

## EURUSD Data State

EURUSD remained `qualified`. Existing canonical datasets were validated without regeneration:

- H1: ready, 2000 rows, MT5, last candle `2026-08-31 03:00:00`, SHA-256 `868eb4a92006de5c42fdd6465d923284f5d56a2448e740b1df38a9edc45d8f67`.
- H4: ready, 2000 rows, MT5, last candle `2026-08-30 22:00:00`, SHA-256 `9d805c070c3a3119efdd1c1823e16e732beff7d927037e7a6aa56c653ef4f66b`.
- D1: ready, 2000 rows, MT5, last candle `2026-08-27 22:00:00`, SHA-256 `1913093a055bfe0746b16d87305c23a5f688970538f2fab6c43240c859b49bdf`.

## USDJPY Qualification

Initial lifecycle state was unregistered. USDJPY was registered once as `candidate` and qualified through a direct MT5-only router. Qualification result was `FAIL`, so the lifecycle remained `candidate`.

- H1: FAIL, 17 blocking `PROVIDER_GAP` classifications; diagnostic candidate SHA-256 `4ffe18333c941b38f2d4b1cb50fb792cdeac59e210614c64a9a75b775d5fbbb6`.
- H4: FAIL, 69 blocking `PROVIDER_GAP` classifications; diagnostic candidate SHA-256 `e525b51298d24bd2954995c2e371af1f42c2a2c48f3500759b976d4c1310a1ef`.
- D1: FAIL, 410 blocking `PROVIDER_GAP` classifications; diagnostic candidate SHA-256 `f9e772713ca7a87d49f5324e40db8e05b5f08652d0c2457038010e1e11fb5fe3`.
- Cross-timeframe validation: FAIL because no timeframe produced a validated frame.

No gap was bypassed or reclassified, and no alternate provider was attempted.

## USDJPY Data State

No canonical USDJPY H1/H4/D1 dataset or registry row was created because qualification did not pass. Canonical row counts and SHA-256 values are therefore unavailable.

## Multiframe Contract

Training and prediction require ready, exactly-2000-row H1/H4/D1 datasets with complete MT5 provenance. Raw and merged frames must contain only the requested symbol. Missing context or cross-symbol rows fail closed.

## Shadow Model Contract

- Contract: `shadow_multiframe_directional_v1`.
- Target: `fixed_horizon_direction_v1`.
- Horizon: 12 closed H1 candles.
- Feature profile: `stationary_v1`.
- Model: frozen 300-tree Random Forest operational baseline.
- Decision policy: `shadow_oof_quartile_abstention_v1`.

Neither shadow model was trained because both symbols did not reach the required ready state. No production model was promoted.

## Scheduler Integration

When runtime scope is configured, only EURUSD and USDJPY are selected. Shadow-symbol acquisition is pinned to MT5. H1 performs update, outcome maturation, chronological retrain check, and one idempotent prediction. H4 and D1 only update their own datasets. With the runtime configuration absent, legacy scheduler selection and production gates remain unchanged.

## Retraining Cadence

Retraining is due only after 168 new closed H1 candles beyond the artifact training cutoff. Performance metrics are not an input. Each successful retrain increments generation and old predictions retain their original model identity.

## Prediction Persistence

Predictions bind symbol, H1 candle, model generation, model identity, execution mode, model stage, score, percentile, feature/target contracts, and dataset provenance. The stable identity permits at most one prediction per symbol/candle/generation. HOLD is persisted as an observational prediction.

## Outcome Tracking

Only shadow BUY/SELL observations enter the separate shadow outcome table. They mature after the next 12 closed H1 candles and record entry/evaluation candles, prices, future return, directional correctness, model identity, generation, and `execution_mode=shadow`. HOLD never becomes a trade outcome. No TP/SL or PnL claim is made.

## Metrics

Metrics are read-only observational summaries grouped by symbol, model identity, and execution mode. They separate BUY, SELL, HOLD, coverage, evaluated directional counts, per-direction precision, pooled directional accuracy, average future returns, and prediction date range. No production gate consumes these metrics.

## Tests

- Shadow-focused suite: 38 passed, 0 failed.
- Relevant scheduler/persistence focused suite: 84 passed, 0 failed, 6 subtests passed.
- Full suite: 933 passed, 0 failed, 10 skipped, 23 subtests passed.
- Skips: five opt-in repository-dataset integrations and five POSIX-only scheduler activation cases on Windows.
- `python -m compileall -q .`: exit 0 (the inaccessible local `.pytest_cache` directory emitted a non-fatal listing notice).
- `git diff --check`: exit 0 before the implementation commit.

## EURUSD Canary

Not executed. The required precondition that both symbols have ready canonical datasets was not met.

## USDJPY Canary

Not executed. USDJPY qualification failed closed and progression stopped.

## Production Isolation

- EURUSD remained `qualified`; no activation or production promotion occurred.
- USDJPY remained `candidate`; no activation or production promotion occurred.
- No trading occurred.
- No Shadow artifact or Shadow prediction was created.
- Production EURUSD alias was absent before and after preparation.
- A production USDJPY alias was already present during preflight. It was not created, loaded, modified, or removed by this task. This pre-existing runtime artifact must be explicitly resolved before deployment even though lifecycle gates prevent a candidate/qualified symbol from using it.

## Remaining Deployment Work

1. Diagnose the real USDJPY MT5 gap evidence against an authoritative IFC market-session/closure source; do not lower or bypass the existing gap contract.
2. Repeat USDJPY qualification through pinned MT5 and require PASS.
3. Only after PASS, create and validate canonical USDJPY H1/H4/D1 datasets and registry entries.
4. Resolve the pre-existing USDJPY production alias through a separately authorized, recoverable runtime-artifact procedure.
5. Train exactly one initial Shadow model per pair, then execute exactly one persisted manual H1 canary per pair.
6. Revalidate both lifecycle states, production isolation, scheduler status, pending outcomes, and artifact identities before Windows VM deployment.

## Decision

`FOREX SHADOW RUNTIME NOT READY — USDJPY QUALIFICATION FAILED (PROVIDER_GAP)`

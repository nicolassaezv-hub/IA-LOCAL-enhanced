# Forex Historical Replay — July/August 2026

## Purpose

Exercise the production-intended Forex Shadow pipeline causally for EURUSD and USDJPY from `2026-07-01T00:00:00Z` through the exclusive end `2026-09-01T00:00:00Z`, using direct IFCMarkets-Demo MT5 history and disposable state.

The run was fail-closed before initial model training. No prediction, outcome, retrain, promotion, activation, or trading action occurred.

## Why This Is Not New Independent ML Evidence

This task is a system/pipeline replay, not model research or independent scientific validation. It does not change the fixed target, feature profile, Random Forest, horizon, decision policy, retrain cadence, or any production gate. Because the operational replay did not reach prediction, it produced no predictive evidence or accuracy result.

## Real-State Isolation

The replay CLI snapshots the real SQLite database, canonical datasets, qualification evidence, live Shadow artifacts, aliases, and quarantine files before creating a `TemporaryDirectory`. Its replay database, datasets, source freeze, model storage, and logs live only under that temporary root.

The failed attempt reached only temporary dataset preparation. The source contains no production database factory, promotion, activation, Decision Engine execution, or order-placement call. Post-failure checks confirmed:

- EURUSD lifecycle remains `qualified`.
- USDJPY lifecycle remains `qualified`.
- The two existing live canaries retain their original IDs, model identities, generations, status, and unresolved state.
- `latest_EURUSD.pkl` and `latest_USDJPY.pkl` remain absent.
- All six canonical dataset hashes remain unchanged from the readiness checkpoint.
- The two real Shadow artifacts remain present and were not opened by the replay.

Current real SQLite SHA-256 after the attempt is `7ec04390943c2a770f899046d86bbc23d4952c24bfb7c4ae5af208141f9d10d2`.

## Source Acquisition

The single attempt acquired all six requested sources directly from `MT5Provider` on `IFCMarkets-Demo`, without DataRouter and without fallback:

- EURUSD: H1 3600, H4 2400, D1 2100 closed candles.
- USDJPY: H1 3600, H4 2400, D1 2100 closed candles.
- Yahoo, OANDA, synthetic candles, and forward fill were not used.

Acquisition completed before the failure. Each returned count is enforced by the capture contract. Sources were normalized, symbol-bound, bounded to the replay/maturity requirement, serialized deterministically, and placed under the disposable source root. The temporary source hashes were deleted with the failed attempt before a final result document could be emitted.

## Replay Clock

The adapter defines candle availability exactly as requested:

- H1: open timestamp + 1 hour.
- H4: open timestamp + 4 hours.
- D1: open timestamp + 1 day.

The event queue contains metadata only and orders equal availability instants as D1, H4, then H1. No event processing began because initial state validation failed.

## Initial EURUSD State

The temporary EURUSD lifecycle row was created as `qualified`, independently of the real database. Its three initial rolling files were built with exactly 2000 closed candles under the existing atomic `RollingDataset` contract.

Before generation-1 training, `ShadowForexRuntime` called the canonical `require_shadow_registry()` validation. EURUSD H1 failed that gate because the 2000-candle history extends before the quote-session evidence window.

No EURUSD replay model was written and no EURUSD replay prediction was generated.

## Initial USDJPY State

USDJPY source acquisition completed, but temporary USDJPY registry initialization was not reached because the ordered preparation stopped on the preceding EURUSD H1 fail-closed gate.

No USDJPY replay model was written and no USDJPY replay prediction was generated.

## Causal Visibility Contract

The implementation and tests enforce hidden future H1/H4/D1 rows, metadata-only event ordering, an exact 2000-row initial cut, maximum training feature/terminal-target timestamps at or before the replay clock, and post-window H1 reveal solely for outcome maturity.

No lookahead violation was observed. Training did not start, so the causal training assertion was not exercised by the real attempt beyond registry validation.

## Event Ordering

The queue contract is deterministic: `available_at`, then D1, H4, H1, then symbol. No live event was processed in this attempt. Event and prediction counts are therefore zero/not reached rather than partial performance observations.

## Initial Shadow Training

Initial training was blocked before fitting generation 1. The exact causal chain is:

1. A July 1 initial H1 window requires the latest 2000 closed H1 candles.
2. That window necessarily reaches into March 2026.
3. Both IFC symbol authorities constrain their weekly quote-session rule to the terminal-observed interval beginning `2026-03-29T00:00:00 Europe/Berlin`.
4. A reviewed probe such as Friday `2026-03-20T21:00:00Z` classifies as `UNKNOWN` for both EURUSD and USDJPY, while Friday `2026-04-03T20:00:00Z` classifies as `CLOSED`.
5. Pre-window Friday close gaps therefore remain unknown/blocking in the initial H1 registry.
6. `require_shadow_registry()` rejects H1 as not ready and prevents training.

No authority range was enlarged and no unknown gap was relabeled.

## EURUSD Replay

- H1 events: 0 (not reached)
- H4 events: 0 (not reached)
- D1 events: 0 (not reached)
- Predictions: 0
- Duplicates: 0
- Model generations: 0
- Retrains: 0

## USDJPY Replay

- H1 events: 0 (not reached)
- H4 events: 0 (not reached)
- D1 events: 0 (not reached)
- Predictions: 0
- Duplicates: 0
- Model generations: 0
- Retrains: 0

## Retraining Generations

No initial generation was produced, so the 168-new-H1 retrain cadence was not entered. Unit tests prove the boundary is false at 167 and true at exactly 168, is independent of performance, increments generation, and preserves old prediction identity.

## Outcome Maturation

No BUY/SELL/HOLD replay prediction existed. Therefore no directional outcome or post-window maturity candle was consumed. Unit tests cover HOLD persistence without outcome, BUY/SELL evaluation at exactly t+12, and the prohibition on post-window prediction/retraining.

## Functional Integrity

The implementation test surface passed:

- Focused replay plus Shadow tests: 65 passed, 0 failed.
- Full suite: 972 passed, 10 expected skips, 0 failed, 23 subtests passed.
- `python -m compileall -q .`: passed; only the pre-existing inaccessible `.pytest_cache` listing warning was emitted.
- `git diff --check`: passed before the real attempt.

Operational replay result: FAIL, because all six initial registries and both generation-1 trainings were not completed. Predictive accuracy was not considered.

## EURUSD Historical Prediction Comparison

Not available. BUY 0, SELL 0, HOLD 0, coverage not applicable, matured directional outcomes 0, and no precision/return statistic exists.

## USDJPY Historical Prediction Comparison

Not available. BUY 0, SELL 0, HOLD 0, coverage not applicable, matured directional outcomes 0, and no precision/return statistic exists.

## Predictive Descriptive Summary

Neither `ABOVE_50_REFERENCE` nor `AT_OR_BELOW_50_REFERENCE` is assigned because the matured directional sample size is zero for both symbols. Assigning the lower label to an execution that never produced a prediction would be misleading.

## Real-State Postcheck

Canonical SHA-256 values remain:

- EURUSD H1 `868eb4a92006de5c42fdd6465d923284f5d56a2448e740b1df38a9edc45d8f67`
- EURUSD H4 `9d805c070c3a3119efdd1c1823e16e732beff7d927037e7a6aa56c653ef4f66b`
- EURUSD D1 `1913093a055bfe0746b16d87305c23a5f688970538f2fab6c43240c859b49bdf`
- USDJPY H1 `b56077727c6d83199ff8e0fb9b8cf946a6002b5f5c440d5d793cda59577840a3`
- USDJPY H4 `242be7e3f4b10f3a6378dec79e6a99390e05476458a3171676a1e5562a51244d`
- USDJPY D1 `73377d27ab968e798cfe1a5806e51150cc8ee0725425fe10f229aa028d2b3506`

Real Shadow envelope hashes after the attempt are EURUSD `01308a78264c937be20ba972710be94fd67b6a4e964033a40877e24254f5edc3` and USDJPY `f1cf66ff2e1538f8566d482a18f460f53529641d8378c444e313aa88228f175c`. The original canaries remain `shadow_pred_2ecdb99088b7658cb6ae8a1166f04ab0` and `shadow_pred_b9a22f447c11cd47ea4e7cda8af83e38`, both generation 1, `PENDING`, unresolved, and `execution_mode=shadow`.

Production promotion, activation, and trading were not executed.

## Deployment Readiness

Windows VM Shadow deployment readiness cannot be granted from this replay because the initial historical H1 registry cannot be proven ready under the current evidence window. This is an evidence/authority precondition, not a predictive-performance rejection.

The minimum remaining work is a separately authorized evidence task to establish broker quote-session authority for the pre-`2026-03-29` portion required by the 2000-candle initial H1 window. It must not infer past sessions from ordinary metadata or bypass `UNKNOWN`. After that evidence is accepted, one new complete replay may be authorized.

## Decision

`FOREX HISTORICAL REPLAY NOT READY — INITIAL_H1_SESSION_EVIDENCE_OUTSIDE_AUTHORITY_WINDOW`

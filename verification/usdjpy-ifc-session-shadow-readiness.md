# USDJPY IFC Session / Shadow Readiness

## Initial Blocker

USDJPY qualification originally failed closed because the market-time grid had no symbol-scoped IFCMarkets-Demo session authority for USDJPY. The raw 2000-row probes were intact, but all logical discontinuities were classified as blocking `PROVIDER_GAP`: H1 17, H4 69, and D1 410. No gap was ignored, filled, thresholded away, or manually authorized.

## EURUSD Authority Scope

The existing authority remains unchanged and EURUSD-specific:

- Authority ID: `ifcmarkets-demo-eurusd-session-v1`
- Symbol: `EURUSD`
- Evidence identity: `IFC_EURUSD_SESSION_EVIDENCE_BUNDLE_2026_08_30`
- Evidence hash: `497038aeee0119de925e441aa125f9eae1dc86eacff26218f9b490f1d5b0f151`

It was not reused as the USDJPY authority. EURUSD canonical datasets and model artifacts were not mutated during the USDJPY qualification work.

## USDJPY Raw Gap Evidence

The failed qualification's complete gap set was reclustered without changing the candle data:

- H1: 17 gaps, all local Friday 21:00 to Monday 00:00, each 183600 seconds. UTC examples are Friday 19:00 to Sunday 22:00 during CEST.
- H4: 69 gaps. There are 65 ordinary local Friday 20:00 to Monday 00:00 gaps of 187200 seconds, one spring-DST instance of 183600 seconds, one autumn-DST instance of 190800 seconds, and two reviewed holiday spans.
- D1: 410 gaps. There are 383 ordinary local Friday 00:00 to Monday 00:00 gaps of 259200 seconds, eight spring-DST gaps of 255600 seconds, seven autumn-DST gaps of 262800 seconds, and 12 reviewed Christmas/New-Year closures.

Every raw gap remains represented in `data/qualification/USDJPY/evidence.json` as runtime evidence with previous/current UTC timestamps, local timestamps, duration, classification, timezone profile, authority ID, authority hash, and supporting evidence where applicable.

## Gap Pattern Analysis

The gaps are systematic session-grid boundaries, not isolated missing provider candles:

- H1: 17 `AUTHORIZED_SESSION_CLOSURE`.
- H4: 67 `AUTHORIZED_SESSION_CLOSURE` and 2 `AUTHORIZED_HOLIDAY`.
- D1: 398 `AUTHORIZED_SESSION_CLOSURE` and 12 `AUTHORIZED_HOLIDAY`.
- `PROVIDER_GAP`: 0 after applying the exact USDJPY authority.
- `UNKNOWN_SESSION_EVIDENCE`: 0.

The 410 D1 result was caused by applying a legacy/default UTC expected grid to native broker D1 anchors without a USDJPY session authority. It counted 398 Friday-to-Monday session boundaries, including 15 DST-duration variants, plus 12 evidence-backed general IFC Forex holiday closures as missing daily candles. The new grid evaluates server-local CET/CEST state first; it does not alter any OHLC row.

## Broker Session Evidence

Raw terminal evidence was captured from the connected IFCMarkets-Demo terminal with the existing MQL5 session diagnostic and restored after use:

- Provider/server: MetaTrader 5 / `IFCMarkets-Demo`
- Account type: `Demo Account - Hedge`
- Symbol: `USDJPY`
- Capture UTC: `2026-09-01T17:41:55Z`
- Server clock at capture: `2026-09-01 19:41:55`
- `SymbolInfoSessionQuote`: Monday-Thursday 00:00-00:00, Friday 00:00-22:00, no Saturday/Sunday session.
- `SymbolInfoSessionTrade`: Monday-Thursday 00:00-23:00 and 23:15-24:00, Friday 00:00-22:00, no Saturday/Sunday session.

The EURUSD control was captured on the same server at `2026-09-01T17:45:44Z` and returned the same quote and trade sessions. The pairs therefore share the observed session schedule, while retaining separate symbol-scoped evidence identities and hashes.

## Official IFC Comparison

The official IFC general Forex trading schedule reports Monday-Thursday CET 00:00-23:00 and 23:15-24:00, and Friday 00:00-22:00. This matches the terminal trade-session result. The terminal quote-session result is continuous Monday-Thursday; therefore the 23:00-23:15 trade maintenance interval is not treated as a missing H1 quote candle. The public schedule remains secondary evidence and does not replace the symbol-specific terminal capture.

## USDJPY Session Contract

The explicit descriptor is:

- Authority ID: `ifcmarkets-demo-usdjpy-session-v1`
- Provider: `MT5`
- Server: `IFCMarkets-Demo`
- Symbol: `USDJPY`
- Timezone: `Europe/Berlin`
- Evidence identity: `IFC_USDJPY_SESSION_EVIDENCE_BUNDLE_2026_09_01`
- Symbol-session source: `MT5_SYMBOL_INFO_SESSION_QUOTE_USDJPY`
- Evidence hash: `bd7c6158f2ceb431a8ff8c0eae554a24a248d1d9217dc0b577a1bfca1354a8c2`
- Effective descriptor window: 2018-01-01 through 2026-12-31
- Version: 1

The quote-session rule is constrained to the terminal-observed 2026 CEST window. Reviewed IFC Forex holiday records are shared only where their source applies generally to Forex; the USDJPY quote capture remains separately hashed and symbol-bound. Unknown or open-session omissions remain blocking.

## H1 Validation

- Result: PASS
- Closed physical rows: 2000
- Provider: MT5, no fallback
- Logical gaps: 17
- Authorized session closures: 17
- Authorized holidays: 0
- Remaining provider gaps: 0
- Unknown gaps: 0
- First timestamp: `2026-05-06 05:00:00`
- Last timestamp: `2026-09-01 22:00:00`
- Canonical SHA-256: `b56077727c6d83199ff8e0fb9b8cf946a6002b5f5c440d5d793cda59577840a3`

## H4 Validation

- Result: PASS
- Closed physical rows: 2000
- Provider: MT5, no fallback
- Logical gaps: 69
- Authorized session closures: 67
- Authorized holidays: 2
- Remaining provider gaps: 0
- Unknown gaps: 0
- First timestamp: `2025-05-19 10:00:00`
- Last timestamp: `2026-09-01 18:00:00`
- Canonical SHA-256: `242be7e3f4b10f3a6378dec79e6a99390e05476458a3171676a1e5562a51244d`

## D1 Validation

- Result: PASS
- Closed physical rows: 2000
- Provider: MT5, no fallback
- Logical gaps: 410
- Authorized session closures: 398
- Authorized holidays: 12
- Remaining provider gaps: 0
- Unknown gaps: 0
- First timestamp: `2018-12-13 23:00:00`
- Last timestamp: `2026-08-31 22:00:00`
- Canonical SHA-256: `73377d27ab968e798cfe1a5806e51150cc8ee0725425fe10f229aa028d2b3506`

## Cross-Timeframe Validation

PASS. H1-to-H4 compared 491 aligned rows and H4-to-D1 compared 331 aligned rows; maximum relative OHLC error was 0.0 in both checks. Indicator validation, causal as-of joins, no-lookahead checks, acquisition provenance, exact symbol binding, and dataset SHA binding passed.

## Qualification

The single authorized live retry used direct MT5 on IFCMarkets-Demo with no fallback. H1, H4, and D1 each returned exactly 2000 closed candles. Qualification result was PASS, evidence SHA-256 was `7858d5cc45b7fc7f13c3a305f270ab19b671fb8f9648d3ab20e965a10ec4fcde`, and USDJPY transitioned from `candidate` to `qualified`. It was not activated.

## Canonical Dataset State

The existing atomic rolling transaction created all three USDJPY canonical datasets. Registry state is `ready`, candle count and rolling window are 2000, provider is MT5, and each registry hash matches the file bytes:

- H1 fetched at `2026-09-01T23:33:39.283138+00:00`; SHA-256 `b56077727c6d83199ff8e0fb9b8cf946a6002b5f5c440d5d793cda59577840a3`.
- H4 fetched at `2026-09-01T23:33:39.521842+00:00`; SHA-256 `242be7e3f4b10f3a6378dec79e6a99390e05476458a3171676a1e5562a51244d`.
- D1 fetched at `2026-09-01T23:33:39.749731+00:00`; SHA-256 `73377d27ab968e798cfe1a5806e51150cc8ee0725425fe10f229aa028d2b3506`.

## Legacy USDJPY Alias Quarantine

The pre-shadow artifact was not deserialized. Before moving it, `models/forex/latest_USDJPY.pkl` was 1105395 bytes, had mtime `2026-08-06T01:10:10Z`, and SHA-256 `9692aff3eac992ce9b50c61c04fa7bdeee3f307cef34753e8812fc088c19af42`.

It was moved reversibly to `models/forex/legacy_quarantine/latest_USDJPY.pre_shadow_9692aff3eac9.pkl`. A runtime-only ignored manifest records the original path, quarantine path, size, mtime, hash, timestamp, and reason. The production alias is absent.

## Shadow Models

Exactly one independent shadow model was trained per qualified/ready symbol under `models/forex/shadow/` using `shadow_multiframe_directional_v1`. No production alias or promotion was created.

- EURUSD: generation 1, identity `shadow_EURUSD_g0001_1abeff5705067f13`, artifact SHA-256 `1abeff5705067f13b488c919ecca673f46e1ac91097165efe780dfaeb702cfde`, 1888 training rows.
- USDJPY: generation 1, identity `shadow_USDJPY_g0001_57fdf2c1d203109b`, artifact SHA-256 `57fdf2c1d203109b5fdb95a3014df5543f1f8e010045277b695023e4ffe9ed08`, 1888 training rows.

## EURUSD Canary

Exactly one canary was persisted:

- Prediction ID: `shadow_pred_2ecdb99088b7658cb6ae8a1166f04ab0`
- Execution mode: `shadow`
- Closed H1 candle: `2026-08-31T03:00:00+00:00`
- Action: BUY
- Direction score: 0.5087401133888133
- Decision percentile: 0.805
- Model identity/generation: `shadow_EURUSD_g0001_1abeff5705067f13` / 1
- Entry close: 1.15908
- Outcome status: `PENDING`, unresolved

## USDJPY Canary

Exactly one canary was persisted:

- Prediction ID: `shadow_pred_b9a22f447c11cd47ea4e7cda8af83e38`
- Execution mode: `shadow`
- Closed H1 candle: `2026-09-01T22:00:00+00:00`
- Action: SELL
- Direction score: 0.37365873332318394
- Decision percentile: 0.22333333333333333
- Model identity/generation: `shadow_USDJPY_g0001_57fdf2c1d203109b` / 1
- Entry close: 160.2
- Outcome status: `PENDING`, unresolved

## Production Isolation

- EURUSD lifecycle: `qualified`
- USDJPY lifecycle: `qualified`
- `models/forex/latest_EURUSD.pkl`: absent
- `models/forex/latest_USDJPY.pkl`: absent; legacy file quarantined
- Production promotion: not executed
- Activation: not executed
- Trading/order placement: not executed

Focused contract suites passed, including the 12-test USDJPY authority regression file and the broader 99-test qualification/session focus. The full suite completed with 945 passed, 10 skipped, 0 failed, 13 warnings, and 23 subtests passed. The skips were the five opt-in complete-pipeline tests and five POSIX scheduler-activation tests on Windows.

## Next Step — Historical Replay

Allow both canaries to remain observational and accumulate shadow outcomes. A later, separately authorized task may perform historical replay or evaluate matured shadow evidence. No backtest, model research, production promotion, activation, or trading belongs to this readiness step.

## Decision

`USDJPY QUALIFIED — EURUSD/USDJPY SHADOW CANARIES READY`

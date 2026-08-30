# IFC Timezone-Aware Session Contract

## Baseline

The implementation starts from MT5 timestamp normalization commit
`0e925594833e0a1d5afe74427ab7b01df7e0c360`, with 738 passed, 10 skipped,
and no failures. Canonical ASTRA timestamps remain UTC-naive. No qualification,
canonical dataset write, registry/DB mutation, training, activation, scheduler
cycle, Oracle operation, or trading operation was executed.

## Market Grid Design

Gap continuity is evaluated in the clock domain authorized for the feed:

1. parse canonical timestamps as UTC;
2. resolve the exact acquisition clock profile;
3. convert observed opens to `Europe/Berlin`;
4. generate H1, H4, or D1 expected opens in broker-local wall time;
5. classify each missing local open independently;
6. retain UTC timestamps as the stored canonical representation.

H1 advances one local hour, H4 four local hours, and D1 one local day. D1 is
therefore continuous across DST even when consecutive UTC opens differ by 23
or 25 hours. Ambiguous/nonexistent local opens fail closed when the market is
not unambiguously closed. DST transitions that occur during an IFC weekend do
not invent candles.

## Provenance Binding

The broker-local grid resolves only when all of the following match the known
profile in `forex/data/mt5_clock_profiles.py`:

- provider `MT5`
- symbol `EURUSD`
- asset class `FOREX`
- source domain `MT5_SERVER_TIME`
- source timezone `Europe/Berlin`
- profile `ifcmarkets-demo-europe-berlin`, version 1
- exact profile evidence hash
- normalization `SERVER_WALL_TIME_TO_UTC`
- observed server `IFCMarkets-Demo`

Missing metadata, a different server, altered timezone, profile version, or
evidence hash cannot resolve the grid or IFC authority. Yahoo, OANDA, and
Binance retain their prior behavior.

The additive `SessionAuthorityDescriptor` scope includes exact symbol, clock
profile, and server identity. Its combined evidence hash binds the quote
session evidence, clock-profile hash, and every reviewed holiday record.

## IFC Quote Session

The authority uses only the supplied `SymbolInfoSessionQuote(EURUSD)` evidence:

- Monday through Thursday: open continuously from 00:00 to 00:00 local
- Friday: open from 00:00 through 21:59:59 local; closed from 22:00
- Saturday and Sunday: no quote session

The 23:00-23:15 trade-session maintenance interval is not used as a candle
closure because quote sessions, not trade sessions, govern data continuity.
The weekly quote rule is constrained to the reviewed 2026 CEST evidence range
and is not projected backward across the historical holiday period.

## H1 Classification

The live read-only 2001-row acquisition covers 2026-05-04 03:00 UTC through
2026-08-28 19:00 UTC. It has exactly 16 logical weekly gap events. Each event
contains two Friday local positions after the 22:00 quote close plus 48
Saturday/Sunday positions. All 16 classify `MARKET_SESSION_CLOSED`; unexplained
`PROVIDER_GAP` count is zero.

## H4 Classification

The live native 2001-row acquisition covers 2025-05-15 06:00 UTC through
2026-08-28 18:00 UTC. It has 67 ordinary broker-local weekend events, two
authorized holiday events, and zero unexplained provider gaps.

The holiday events are Christmas 2025 and New Year 2025/2026. Every missing
native H4 open lies inside its reviewed IFC closure interval.

## D1 Classification

The live native 2001-row acquisition covers 2018-12-10 23:00 UTC through
2026-08-27 22:00 UTC. Its broker-local grid contains:

- 397 ordinary weekend events;
- 12 holiday/weekend logical events;
- 10 events fully explained by reviewed IFC evidence;
- exactly 2 unexplained provider gaps.

The two unexplained gaps contain exactly one unsupported broker-local weekday
each: 2020-12-25 and 2021-01-01.

## Supported Holidays

Holiday authorization is interval-based and source-bound, not a recurring
Christmas/New-Year rule. Versioned closure records cover only approved sources:

- archived official IFC 2018/2019 notice, published 2018-12-13 and captured
  2019-01-27;
- archived official IFC 2019/2020 notice, published 2019-12-18 and captured
  2020-01-08;
- official IFC 2023/2024 notice, published 2023-12-12;
- official IFC 2024/2025 notice, published 2024-12-12;
- official IFC Christmas 2025 notice, published 2025-12-15;
- official IFC New Year 2025/2026 notice, published 2025-12-22.

Each record includes source identity, publication/capture identity, timezone,
local closure bounds, version, and deterministic evidence hash.

## Unsupported 2020 Holidays

`2020-12-25` and `2021-01-01` have explicit fail-closed overrides to
`SessionState.UNKNOWN`. They are not inferred from neighboring years, generic
holiday knowledge, weekday/weekend rules, or third-party evidence. Both remain
blocking `PROVIDER_GAP` events.

## DST Validation

Tests prove consecutive IFC D1 local midnights remain continuous across the
2026 CEST start and end, including the 23-hour and 25-hour UTC deltas. Tests
also prove the weekend decision uses broker-local weekday: a Friday UTC instant
that is Saturday in Berlin is weekend, while Sunday 23:00 UTC in winter is
Monday 00:00 CET and is not weekend.

## Temporary Dataset Validation

Only in-memory rolling-2000 frames were built from live read-only acquisition:

- H1: `WARNING`, non-blocking; 16 authoritative session closures
- H4: `WARNING`, non-blocking; 67 weekends and 2 authoritative closures
- D1: `WARNING`, blocking only for 2 provider gaps

No canonical path or registry was touched.

## Indicator Validation

All 12 contractual indicators passed independent comparison in H1, H4, and D1
with `rtol=1e-6`, `atol=1e-9`, and maximum absolute error 0.0.

## Cross-Timeframe Validation

Cross-timeframe validation passed without warnings. H1-to-H4 compared 491
complete groups and H4-to-D1 compared 331; all OHLC maximum relative errors
were 0.0.

## Fail-Closed Tests

Regression coverage proves unknown MT5 servers, altered timezone, altered
profile version/hash, missing acquisition provenance, wrong providers, and
wrong scope cannot enable the IFC grid. It also proves each approved holiday
family, both unsupported 2020 dates, mixed weekend/session gaps, quote-session
hours, DST continuity, and unchanged Yahoo/OANDA/crypto behavior.

## Remaining Blockers

The sole remaining evidence blocker is authoritative IFC documentation for the
closures on 2020-12-25 and 2021-01-01. Qualification was intentionally not run
and must remain blocked until those dates gain approved evidence or the D1
source contract changes through a separately reviewed task.

## Decision

**SESSION CONTRACT READY — ONLY 2020 HOLIDAY EVIDENCE REMAINS**

# IFC MT5 Timezone Normalization Audit

Audit date: 2026-08-30. Scope: read-only `IFCMarkets-Demo / EURUSD`
acquisition and in-memory validation only. No qualification, dataset write,
training, activation, scheduler, Oracle, or trading operation was executed.

## Finding and clock authority

The old provider interpreted every MT5 `time` integer with
`pd.to_datetime(..., unit="s", utc=True)`. Live terminal evidence disproves
that interpretation for this server: `TimeTradeServer - TimeGMT` was +02:00
during August 2026, the terminal showed the final Friday H1 bar at 21:00,
and the quote session ended at 22:00 server time. A read-only reconfirmation
found server `IFCMarkets-Demo`, tick raw `1787954398` (the supplied
`TimeCurrent` sample was `1787954399` one second later), and recent H1 raw
bar digits ending at Friday 21:00.

The new explicit profile is:

- profile: `ifcmarkets-demo-europe-berlin`, version 1
- exact server identity: `IFCMarkets-Demo`
- IANA timezone: `Europe/Berlin`
- authority: `BROKER_DOCUMENTATION_AND_LIVE_TERMINAL`
- evidence identity:
  `IFC_MARKETS_PLATFORM_CET_CEST_AND_TERMINAL_AUDIT_2026_08_30`
- evidence hash:
  `00ad79892885f8034eb37f01eceede355b43486cbca18b9b69c45f87f8eed331`

Unknown server identities have no default and fail closed before rates are
copied. Raw integers are decoded as naive server wall-clock values, localized
with `Europe/Berlin`, converted DST-aware to UTC, and stored UTC-naive.
Ambiguous and nonexistent local times raise explicit contract errors rather
than selecting a DST fold or inventing a time.

Verified conversions:

- summer: 2026-08-21 21:00 CEST -> 2026-08-21 19:00 UTC
- summer: 2026-08-24 00:00 CEST -> 2026-08-23 22:00 UTC
- winter: 2025-12-24 16:00 CET -> 2025-12-24 15:00 UTC

The provider metadata now identifies the source domain, timezone, profile,
profile version/hash/authority, normalization method, and observed server.
It contains no login, account number, balance, equity, password, or other
credential field.

## Live physical and analytical validation

All acquisitions used native MT5 timeframes and returned exactly 2001 closed
rows. All three were strictly chronological, had zero duplicate timestamps,
zero malformed OHLC rows, zero negative volume rows, and zero rows dropped by
sanitization.

- H1: first 2026-05-04 03:00 UTC; last 2026-08-28 19:00 UTC
- H4: first 2025-05-15 06:00 UTC; last 2026-08-28 18:00 UTC
- D1: first 2018-12-10 23:00 UTC; last 2026-08-27 22:00 UTC

The native D1 timestamps correctly move to the preceding UTC calendar date;
they were not forced to UTC midnight.

Temporary in-memory rolling-2000 frames were recalculated with ASTRA's
indicator implementation and checked independently. Every contractual
indicator passed with maximum absolute error 0.0. Cross-timeframe validation
also passed: H1->H4 compared 491 aggregates and H4->D1 compared 331, with
zero relative OHLC error and latest-price scale ratio 1.0.

## Gap event identity

The normalized UTC event boundaries below are the same physical events as the
earlier server-wall-clock audit. Reconstructing `Europe/Berlin` wall time for
continuity analysis preserves the prior counts: H1 has 16 recurrent weekly
boundaries, H4 has 67 weekends plus 2 holiday closures, and D1 has 397 weekends
plus 12 holiday/weekend events.

H1 corrected UTC weekly boundaries:

- 2026-05-08 19:00 -> 2026-05-10 22:00
- 2026-05-15 19:00 -> 2026-05-17 22:00
- 2026-05-22 19:00 -> 2026-05-24 22:00
- 2026-05-29 19:00 -> 2026-05-31 22:00
- 2026-06-05 19:00 -> 2026-06-07 22:00
- 2026-06-12 19:00 -> 2026-06-14 22:00
- 2026-06-19 19:00 -> 2026-06-21 22:00
- 2026-06-26 19:00 -> 2026-06-28 22:00
- 2026-07-03 19:00 -> 2026-07-05 22:00
- 2026-07-10 19:00 -> 2026-07-12 22:00
- 2026-07-17 19:00 -> 2026-07-19 22:00
- 2026-07-24 19:00 -> 2026-07-26 22:00
- 2026-07-31 19:00 -> 2026-08-02 22:00
- 2026-08-07 19:00 -> 2026-08-09 22:00
- 2026-08-14 19:00 -> 2026-08-16 22:00
- 2026-08-21 19:00 -> 2026-08-23 22:00

Every boundary maps back exactly to Friday 21:00 -> Monday 00:00 server time.
The Friday 21:00 candle closes at Friday 20:00 UTC, exactly when the supplied
quote session closes at Friday 22:00 CEST. The next quote is Sunday 22:00 UTC,
which is Monday 00:00 CEST. The 23:00-23:15 trade-session maintenance break is
irrelevant to candle continuity because the quote session remains open.

H4 corrected UTC holiday boundaries:

- 2025-12-24 15:00 -> 2025-12-25 23:00
- 2025-12-31 03:00 -> 2026-01-02 07:00

D1 corrected UTC event boundaries:

- 2018-12-23 23:00 -> 2018-12-25 23:00
- 2018-12-27 23:00 -> 2019-01-01 23:00
- 2019-12-23 23:00 -> 2019-12-25 23:00
- 2019-12-30 23:00 -> 2020-01-01 23:00
- 2020-12-23 23:00 -> 2020-12-27 23:00
- 2020-12-30 23:00 -> 2021-01-03 23:00
- 2023-12-21 23:00 -> 2023-12-25 23:00
- 2023-12-28 23:00 -> 2024-01-01 23:00
- 2024-12-23 23:00 -> 2024-12-25 23:00
- 2024-12-30 23:00 -> 2025-01-01 23:00
- 2025-12-23 23:00 -> 2025-12-25 23:00
- 2025-12-30 23:00 -> 2026-01-01 23:00

Ten D1 events retain the previously documented IFC holiday evidence. The
2020-12-25 and 2021-01-01 closures remain
`UNAUTHORIZED_HISTORICAL_HOLIDAY_GAP`; this patch neither infers nor
authorizes them.

## Session assessment and remaining blocker

The exact current H1 weekly-session evidence is **READY for a future scoped
IFC session authority**: the terminal quote sessions, server-time observations,
IANA conversion, and all 16 physical boundaries agree. No
`IFCSessionAuthority` was implemented here.

The current generic `classify_gaps()` contract evaluates weekend membership
on UTC-naive timestamps. Once native H4/D1 server-midnight grids are converted
to their true UTC instants, a weekly gap begins on Friday UTC rather than
Saturday UTC. Consequently, the current UTC-only classifier reports 69 H4 and
409 D1 `PROVIDER_GAP` events, even though reconstruction in the authoritative
server timezone proves the event identity remains 67 weekends + 2 H4 holiday
events and 397 weekends + 12 D1 holiday/weekend events. H1 remains 16 in both
views.

That classifier/session integration is deliberately not changed in this
timestamp-only patch. It is a fail-closed blocker for a real qualification
retry: the corrected MT5 provider is viable and analytically coherent, but
qualification should wait for a timezone-aware, provenance-bound IFC session
authority or equivalent approved gap-classification contract.

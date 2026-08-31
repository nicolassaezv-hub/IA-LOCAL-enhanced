# IFC 2020 Holiday Authority Binding

## Baseline

The work started from `diagnose/ifc-2020-holiday-evidence-final` at
`5b62ad797e379b4bc22e53550a3bf18671a08b40` and continued on
`fix/ifc-2020-holiday-authority`. The pre-change evidence bundle hash was
`e199d146efc375b71ddc30584ecc30c06b009233ca26522bc9ebfa3d4fc9e2fe`.
The known suite baseline was 777 passed with no failures. No qualification,
canonical dataset write, registry or database mutation, training, activation,
scheduler cycle, Oracle operation, or trading operation was executed.

## Evidence Source

The binding uses the official IFC notice published on 2020-12-15:

- original notice: `https://www.ifcmarkets.com/fa/company-news/chiristmas-newyear-trading-schedule-2020-2021`
- archived notice: `https://web.archive.org/web/20230705153445id_/https://www.ifcmarkets.com/fa/company-news/chiristmas-newyear-trading-schedule-2020-2021`
- archive capture: `2023-07-05T15:34:45Z`
- archived English index corroboration: `https://web.archive.org/web/20210125173509id_/https://www.ifcmarkets.com/en/company-news`

The English index identifies the corresponding notice and binds it to
24-25 December 2020, 31 December 2020, and 1 January 2021.

## Christmas 2020 Binding

The explicit record `ifc-2020-christmas` binds source identity
`IFC_ARCHIVED_CHRISTMAS_NEW_YEAR_2020_2021` to the exact Europe/Berlin
interval `[2020-12-24 19:00:00, 2020-12-28 00:00:00)`, equivalent to
`[2020-12-24 18:00:00Z, 2020-12-27 23:00:00Z)`. Its runtime record hash is
`433defdb00fb750a38142e1caecdd024060986b6a0bda5913825bef804c6d6eb`.

## New Year 2020/2021 Binding

The explicit record `ifc-2020-2021-new-year` binds the same official source
to the exact Europe/Berlin interval `[2020-12-31 07:00:00,
2021-01-04 00:00:00)`, equivalent to `[2020-12-31 06:00:00Z,
2021-01-03 23:00:00Z)`. Its runtime record hash is
`66959408e3647adbf2825cd23c148e70b786649d4aa600acc01e514f89499bfe`.

## Provenance

Both records retain the existing deterministic serialization of evidence ID,
source identity, publication/capture identity, timezone, exact local bounds,
and version. Adding them changed the combined authority descriptor hash to
`497038aeee0119de925e441aa125f9eae1dc86eacff26218f9b490f1d5b0f151`.
Tests independently reconstruct the pre-binding bundle from all records except
the two new IDs and prove it differs from the runtime descriptor hash.

## No Recurrence

No month/day rule or recurring holiday inference was introduced. Nearby dates
outside the exact half-open intervals and the corresponding dates in 2022
remain `UNKNOWN` outside independently authorized session evidence.

## Scope

The authority remains exactly scoped to provider `MT5`, server
`IFCMarkets-Demo`, clock profile `ifcmarkets-demo-europe-berlin`, symbol
`EURUSD`, and asset class `FOREX`. The official notice describes general
trading closure, so the existing timestamp-scoped authority may explain H1,
H4, or D1 missing opens only when their exact timestamps fall inside these
two source-bound intervals. No timeframe-specific refactor and no broader
historical interval were introduced.

## Live Window Boundary Diagnosis

The previous H1 audit covered 2001 rows from `2026-05-04 03:00:00 UTC` through
`2026-08-28 19:00:00 UTC`. It ended on Friday before any post-reopen Monday bar
could form the next observed gap, so it contained 16 logical weekly events.

The current read-only frame covers 2001 rows from `2026-05-04 08:00:00 UTC`
through `2026-08-31 02:00:00 UTC`. It includes bars after the broker-local
Monday reopen and therefore contains 17 logical events. The additional event
is exactly:

- UTC: `2026-08-28 19:00:00` to `2026-08-30 22:00:00`
- Europe/Berlin: `2026-08-28 21:00:00` to `2026-08-31 00:00:00`
- classification: `MARKET_SESSION_CLOSED`
- explanation: `SESSION_CLOSED=2`, `WEEKEND=48`, `UNEXPLAINED=0`
- evidence: `ifc-eurusd-quote-session-2026-08-30`

This is natural live-window advancement, not a regression. The number of
logical gaps is observational. The live acceptance contract is 2001 rows,
valid OHLC and acquisition provenance, at least one logical gap, zero provider
gaps, and zero unexplained positions; it does not require a fixed gap count.
A synthetic rolling-window regression test proves that same-sized windows can
legitimately observe N and N+1 fully authorized weekly closures.

## H1 Revalidation

Direct read-only MT5 acquisition returned 2001 rows, 17 logical gaps, zero
provider gaps, zero unexplained positions, and zero invalid OHLC rows. Every
gap classified `MARKET_SESSION_CLOSED` with exact IFC quote-session evidence.
Acquisition provenance resolved to the expected server, timezone, profile,
profile version, and evidence hash.

## H4 Revalidation

Direct read-only native H4 acquisition returned 2001 rows. All 70 observed
logical gaps were ordinary weekends or authoritative session closures, with
zero provider gaps, zero unexplained positions, and zero invalid OHLC rows.

## D1 Revalidation

Direct read-only native D1 acquisition returned 2001 rows and 409 total gap
events. Its historical frame contains 12 holiday logical events; all 12 are
now source-authorized and none remains a provider gap. There are zero
unexplained positions and zero invalid OHLC rows.

## Indicators

In-memory rolling frames of exactly 2000 rows were built for H1, H4, and D1.
All 12 contractual indicators passed independent comparison in every
timeframe using unchanged tolerances `rtol=1e-6` and `atol=1e-9`.

## Cross-Timeframe

The existing H1-to-H4 and H4-to-D1 comparisons both returned `PASS`, with no
blocking warning or error.

## Fail-Closed Regression

The focal authority suite passed 50 tests. It proves exact Christmas and New
Year provenance, no recurrence or interval leakage, unchanged symbol/server
scope, a changed bundle hash, fail-closed behavior for wrong server and wrong
symbol, and retained fail-closed behavior for wrong timezone profile, profile
hash, profile version, server, and missing acquisition provenance.

The complete suite passed 788 tests with 10 expected skips, zero failures, and
zero errors when run with the established external pytest temp directory. The
initial run against the inaccessible global pytest temp root produced setup
permission errors only; isolation changed no test semantics.

## Remaining Blockers

There is no remaining IFC session/holiday-authority blocker for a separately
controlled EURUSD qualification attempt. Qualification remains intentionally
unexecuted in this task.

## Decision

**IFC SESSION/HOLIDAY AUTHORITY COMPLETE — READY FOR CONTROLLED EURUSD QUALIFICATION**

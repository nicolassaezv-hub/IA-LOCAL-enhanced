# IFC Forex Session and Holiday Evidence Audit

## Scope

This evidence-only audit evaluates whether the gaps recorded in `verification/ifc-mt5-eurusd-live-audit.md` can be authorized by a future, provenance-bound `SessionAuthority`. It covers the IFC Markets Demo `EURUSD` feed, the observed H1 range from 2026-05-04 through 2026-08-28, the two H4 events in December 2025/January 2026, and the twelve D1 events from December 2018 through January 2026.

No production contract, classifier, provider, candle, model, database, qualification state, or lifecycle state was changed or exercised. Sources were retrieved on 2026-08-30. Current pages are not treated as proof of earlier conditions unless an effective date or contemporaneous notice establishes the relevant period.

## Source Hierarchy

Evidence was accepted in this order:

1. current IFC Markets trading-condition or FAQ pages;
2. contemporaneous IFC Markets Company News;
3. Web Archive snapshots whose original URL is on `ifcmarkets.com` and whose IFC text and capture date are visible;
4. official MetaQuotes documentation as secondary timestamp evidence;
5. third-party material as corroboration only, never as authority.

The principal sources are:

- [Forex Trading Hours / CFD Trading Hours](https://www.ifcmarkets.com/en/trading-conditions/trading-times), IFC Markets, current page, no publication or effective date shown.
- [Trading FAQ](https://www.ifcmarkets.com/en/faqs), IFC Markets, current page, no publication or effective date shown.
- [Daylight saving time in the European Union from 29.03.2026](https://www.ifcmarkets.com/en-CA/company-news/europe-summer-time-2026), IFC Markets Company News, 2026-03-27.
- [Christmas - changes in trading schedule](https://www.ifcmarkets.com/es/company-news/christmas-trading-schedule-24-26-12-2025), IFC Markets Company News, 2025-12-15.
- [Changes in the trading schedule on December, 31 - January, 2](https://www.ifcmarkets.com/en/company-news/new-year-trading-schedule-2025-2026), IFC Markets Company News, 2025-12-22.
- [Christmas and New Year - changes in trading schedule](https://www.ifcmarkets.com/en/company-news/christmas-newyear-trading-schedule-2024-2025), IFC Markets Company News, 2024-12-12.
- [Christmas and New Year - changes in trading schedule](https://www.ifcmarkets.com/en/company-news/new-year-2024-trading-schedule), IFC Markets Company News, 2023-12-12.
- [Archived IFC 2018/2019 Christmas and New Year notice](https://web.archive.org/web/20190127194639/https://www.ifcmarkets.com/en/company-news/christmas-new-year-trading-schedule-2018-2019), captured 2019-01-27; original IFC publication metadata 2018-12-13.
- [Archived IFC 2019/2020 Christmas and New Year notice](https://web.archive.org/web/20200108190923/https://www.ifcmarkets.com/en/company-news/christmas-new-year-trading-schedule-2020), captured 2020-01-08; original IFC publication date 2019-12-18.
- [MetaTrader 5 Python `copy_rates_from` reference](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrom_py), MetaQuotes, secondary evidence that returned bar times use UTC.

## Regular Forex Session

The current IFC Markets page titled **Forex Trading Hours / CFD Trading Hours**, on `ifcmarkets.com`, explicitly lists the generic Forex group as:

- Monday through Thursday: 00:00–23:00 and 23:15–24:00;
- Friday: 00:00–22:00;
- a daily maintenance interruption Monday through Thursday from 23:00 to 23:15;
- weekly trading begins Monday at 00:00 in the declared platform clock and ends Friday at 22:00;
- special changes are published in Company News.

The page states that terminal/server time corresponds to Central European time. The IFC FAQ makes the convention more precise: its platforms use CET in winter and CEST in summer, switching on the last Sundays of March and October; it says that this timezone is fixed for all IFC trading platforms. The schedule is explicitly for Forex and is generic across IFC platforms, not presented as an MT5-only contract. The current trading-times page displays no publication date or historical effective range.

The 2026 daylight-saving Company News is contemporaneous evidence for the audited H1 interval: from 2026-03-29 it repeats the same Forex hours in the summer-time platform clock. It therefore supports the existence of a regular weekend closure throughout 2026-05-04 through 2026-08-28.

Assessment of the observed H1 pattern: **PARTIALLY_SUPPORTED**. The weekly closure and all sixteen recurrent boundaries are supported as a pattern. Exact UTC authorization is not yet supported because the published CEST boundaries do not reproduce the observed UTC bar limits exactly.

## H1 Evidence

All sixteen H1 events have the same observed shape: last bar Friday 21:00 UTC, next bar Monday 00:00 UTC, with zero residual intrawEEK gaps. The official schedule explains why a weekend discontinuity is expected and the dated 2026 summer-time notice covers the full audited range.

For a representative week, `ZoneInfo("Europe/Berlin")` converts the published Friday close at 22:00 CEST to Friday 20:00 UTC and the published Monday start at 00:00 CEST to Sunday 22:00 UTC. Official MetaQuotes documentation says that Python MT5 bar times are UTC. Those exact boundaries differ from the observed last/next bar timestamps, Friday 21:00 UTC and Monday 00:00 UTC.

Consequently:

- recurring weekly-boundary explanation: 16/16;
- exact UTC intervals safe to encode today: 0/16;
- H1 weekly authority evidence: **PARTIAL**;
- unresolved item: the IFCMarkets-Demo server/bar timestamp semantics that relate the published platform clock to MT5 H1 bar-open timestamps.

The discrepancy is not evidence of data loss, but it prevents a future authority from authorizing the exact missing timestamps until the mapping is documented by an IFC source or separately verified with provenance. No offset may be invented.

## Christmas 2025 H4 Evidence

The IFC notice published 2025-12-15 declares CET and states that Forex closes at 19:00 on 2025-12-24, all trading is closed on 2025-12-25, and 2025-12-26 follows the scheduled session. In winter, 19:00 CET is 18:00 UTC and the scheduled 00:00 CET start is 23:00 UTC on 2025-12-25.

The observed H4 gap is 2025-12-24 16:00 UTC to 2025-12-26 00:00 UTC. Every missing native H4 timestamp—2025-12-24 20:00 and 2025-12-25 00:00, 04:00, 08:00, 12:00, 16:00, and 20:00 UTC—falls inside the officially declared closure.

Result: **FULL_MATCH**.

## New Year 2025/2026 H4 Evidence

The IFC notice published 2025-12-22 declares CET and closes all instruments from 07:00 CET on 2025-12-31 through 09:00 CET on 2026-01-02. The exact UTC interval is 2025-12-31 06:00 UTC through 2026-01-02 08:00 UTC.

The observed H4 gap is 2025-12-31 04:00 UTC to 2026-01-02 08:00 UTC. All twelve missing native H4 timestamps—from 2025-12-31 08:00 through 2026-01-02 04:00 UTC—are inside that official closure, and the next observed bar equals the stated UTC reopening boundary.

Result: **FULL_MATCH**.

**NO EVIDENCE OF H4 PROVIDER DATA LOSS**

## D1 Gap Matrix

Only weekday closures beyond the ordinary weekend are evaluated. No recurring Christmas or New Year rule is inferred.

| ID | Weekday closure requiring authority | Source-bound result | Supported |
| --- | --- | --- | --- |
| A | 2018-12-25 | Archived IFC 2018/2019 notice says all trades closed on 2018-12-25 | yes |
| B | 2018-12-31 and 2019-01-01 | Same archived notice says both dates closed; weekend is excluded from the provider-failure question | yes |
| C | 2019-12-25 | Archived IFC 2019/2020 notice identifies 2019-12-25 as a day off | yes |
| D | 2020-01-01 | Same archived notice identifies 2020-01-01 as a day off | yes |
| E | 2020-12-25 | No qualifying IFC source or official IFC archive snapshot was located | no |
| F | 2021-01-01 | No qualifying IFC source or official IFC archive snapshot was located | no |
| G | 2023-12-25 | Official 2023 Company News closes all instruments through 00:00 CET on 2023-12-26 | yes |
| H | 2024-01-01 | Same notice closes all instruments 2023-12-30 through 2024-01-01 | yes |
| I | 2024-12-25 | Official 2024 Company News closes all trading 2024-12-24 22:00 through 2024-12-26 00:00 CET | yes |
| J | 2025-01-01 | Same notice closes all trading 2024-12-31 07:00 through 2025-01-02 09:00 CET | yes |
| K | 2025-12-25 | Official 2025 Christmas notice closes all trading on 2025-12-25 | yes |
| L | 2026-01-01 | Official 2025/2026 New Year notice closes all instruments across the date | yes |

Result: 10/12 D1 weekday closure events have official or archived-official support. Events E and F remain unauthorized; they are not characterized as data loss.

## 2018–2021 Historical Evidence

The 2018/2019 archive snapshot captures an official `ifcmarkets.com` URL, has capture timestamp 2019-01-27, and displays IFC's notice with original publication metadata 2018-12-13. It declares CET, closes all trading on 2018-12-25, closes all trading on 2018-12-31 and 2019-01-01, and reopens on 2019-01-02 at 07:00 CET. It authorizes D1 events A and B.

The 2019/2020 archive snapshot captures an official `ifcmarkets.com` URL, has capture timestamp 2020-01-08, and displays IFC's notice published 2019-12-18. It declares CET and identifies 2019-12-25, 2019-12-31, and 2020-01-01 as days off. It authorizes D1 events C and D. A year typo in the reopening line is not used as evidence; the dated closure statements themselves are sufficient for the observed dates.

Searches of the current Company News index, official-language variants, historical official URLs, and Web Archive captures did not locate a qualifying IFC notice for Christmas 2020 or New Year 2020/2021. Generic holiday calendars cannot authorize them.

Assessment for 2018–2021: **PARTIAL**.

## 2023–2026 Historical Evidence

The 2023-12-12 IFC notice declares CET and closes all instruments, including cryptocurrencies, from 22:00 CET on 2023-12-22 through 00:00 CET on 2023-12-26. It separately closes all instruments from 2023-12-30 through 2024-01-01 and reopens at 09:00 CET on 2024-01-02. This fully supports D1 events G and H.

The 2024-12-12 IFC notice declares CET and closes all trading from 22:00 CET on 2024-12-24 through 00:00 CET on 2024-12-26, then from 07:00 CET on 2024-12-31 through 09:00 CET on 2025-01-02. This fully supports D1 events I and J.

The two 2025 notices independently support Christmas 2025 and New Year 2025/2026, fully covering D1 events K and L as well as both H4 events.

Assessment for 2023–2026: **COMPLETE**.

## Timezone Validation

Conversions were checked programmatically with Python `zoneinfo.ZoneInfo("Europe/Berlin")`; no fixed offset was assumed.

- May–August 2026 is CEST (UTC+2): Friday 22:00 CEST = Friday 20:00 UTC; Monday 00:00 CEST = Sunday 22:00 UTC.
- 2023-12-22 22:00 CET = 2023-12-22 21:00 UTC; 2023-12-26 00:00 CET = 2023-12-25 23:00 UTC; 2024-01-02 09:00 CET = 08:00 UTC.
- 2024-12-24 22:00 CET = 21:00 UTC; 2024-12-26 00:00 CET = 2024-12-25 23:00 UTC; 2024-12-31 07:00 CET = 06:00 UTC; 2025-01-02 09:00 CET = 08:00 UTC.
- 2025-12-24 19:00 CET = 18:00 UTC; 2025-12-26 00:00 CET = 2025-12-25 23:00 UTC.
- 2025-12-31 07:00 CET = 06:00 UTC; 2026-01-02 09:00 CET = 08:00 UTC.

Timezone conversion result: **PASS**. The H1 issue is not a conversion failure; it is an unresolved mapping between the published IFC platform schedule and the observed MT5 UTC bar grid.

## Evidence Matrix

| Event | Observed gap | Timeframe | IFC source | Publication date | Declared timezone | Declared closure | UTC closure | Observed missing bars covered | Coverage | Authority quality |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Regular weekly session, audited range | Fri 21:00 → Mon 00:00 UTC, repeated 16 times | H1 | Trading Times + FAQ + 2026 DST notice | Current / 2026-03-27 | CET/CEST | Mon–Thu 00:00–23:00, 23:15–24:00; Fri 00:00–22:00 | Summer close Fri 20:00; start Sun 22:00 | 16/16 as weekly pattern; exact UTC bounds do not match | PARTIAL | OFFICIAL_CURRENT |
| Christmas 2025 | 2025-12-24 16:00 → 2025-12-26 00:00 | H4 | IFC Christmas 2025 notice | 2025-12-15 | CET | Forex closes Dec 24 19:00; Dec 25 closed; Dec 26 scheduled | Dec 24 18:00 → Dec 25 23:00 | All 7 | FULL | OFFICIAL_HISTORICAL |
| New Year 2025/2026 | 2025-12-31 04:00 → 2026-01-02 08:00 | H4 | IFC New Year 2025/2026 notice | 2025-12-22 | CET | Dec 31 07:00 → Jan 2 09:00 | Dec 31 06:00 → Jan 2 08:00 | All 12 | FULL | OFFICIAL_HISTORICAL |
| A — Christmas 2018 | Missing 2018-12-25 | D1 | Archived IFC 2018/2019 notice | 2018-12-13; captured 2019-01-27 | CET | Dec 25 closed | Entire UTC trading date covered by closure | 1/1 weekday date | FULL | ARCHIVED_OFFICIAL |
| B — New Year 2018/2019 | Dec 28 → Jan 2; weekday Dec 31 + Jan 1 | D1 | Archived IFC 2018/2019 notice | 2018-12-13; captured 2019-01-27 | CET | Dec 31 and Jan 1 closed; Jan 2 opens 07:00 | Jan 2 opens 06:00 UTC | 2/2 weekday dates | FULL | ARCHIVED_OFFICIAL |
| C — Christmas 2019 | Missing 2019-12-25 | D1 | Archived IFC 2019/2020 notice | 2019-12-18; captured 2020-01-08 | CET | Dec 25 day off | Entire UTC trading date covered by closure | 1/1 | FULL | ARCHIVED_OFFICIAL |
| D — New Year 2019/2020 | Missing 2020-01-01 | D1 | Archived IFC 2019/2020 notice | 2019-12-18; captured 2020-01-08 | CET | Jan 1 day off | Entire UTC trading date covered by closure | 1/1 | FULL | ARCHIVED_OFFICIAL |
| E — Christmas 2020 | Dec 24 → Dec 28; weekday Dec 25 | D1 | No qualifying IFC source located | — | — | Unknown | Unknown | 0/1 | NONE | CORROBORATIVE_ONLY |
| F — New Year 2020/2021 | Dec 31 → Jan 4; weekday Jan 1 | D1 | No qualifying IFC source located | — | — | Unknown | Unknown | 0/1 | NONE | CORROBORATIVE_ONLY |
| G — Christmas 2023 | Dec 22 → Dec 26; weekday Dec 25 | D1 | IFC 2023/2024 notice | 2023-12-12 | CET | Dec 22 22:00 → Dec 26 00:00 | Dec 22 21:00 → Dec 25 23:00 | 1/1 | FULL | OFFICIAL_HISTORICAL |
| H — New Year 2023/2024 | Dec 29 → Jan 2; weekday Jan 1 | D1 | IFC 2023/2024 notice | 2023-12-12 | CET | Dec 30–Jan 1 closed; Jan 2 opens 09:00 | Jan 2 opens 08:00 UTC | 1/1 | FULL | OFFICIAL_HISTORICAL |
| I — Christmas 2024 | Missing 2024-12-25 | D1 | IFC 2024/2025 notice | 2024-12-12 | CET | Dec 24 22:00 → Dec 26 00:00 | Dec 24 21:00 → Dec 25 23:00 | 1/1 | FULL | OFFICIAL_HISTORICAL |
| J — New Year 2024/2025 | Missing 2025-01-01 | D1 | IFC 2024/2025 notice | 2024-12-12 | CET | Dec 31 07:00 → Jan 2 09:00 | Dec 31 06:00 → Jan 2 08:00 | 1/1 | FULL | OFFICIAL_HISTORICAL |
| K — Christmas 2025 | Missing 2025-12-25 | D1 | IFC Christmas 2025 notice | 2025-12-15 | CET | Dec 25 closed | Dec 24 18:00 → Dec 25 23:00 at minimum | 1/1 | FULL | OFFICIAL_HISTORICAL |
| L — New Year 2025/2026 | Missing 2026-01-01 | D1 | IFC New Year 2025/2026 notice | 2025-12-22 | CET | Dec 31 07:00 → Jan 2 09:00 | Dec 31 06:00 → Jan 2 08:00 | 1/1 | FULL | OFFICIAL_HISTORICAL |

`CORROBORATIVE_ONLY` for E and F does not mean that third-party material authorizes the gaps. It records that no qualifying IFC authority was found; those rows have coverage `NONE` and remain fail-closed.

## Remaining Unsupported Gaps

The following remain `UNAUTHORIZED_HISTORICAL_HOLIDAY_GAP`:

- D1 event E: 2020-12-25;
- D1 event F: 2021-01-01.

Additionally, the exact UTC bounds of all sixteen H1 weekend gaps remain unauthorized pending authoritative IFC/MT5 timestamp-to-session mapping. The repeated shape is explained, but a classifier must not convert those intervals to `MARKET_SESSION_CLOSED` from the current evidence alone.

No unsupported item is labeled provider data loss. There is no positive evidence of actual IFC data loss in the audited events.

## Proposed Authority Scope

A future authority may safely use only narrow, source-bound records:

- provider/feed identity: IFC Markets / `IFCMarkets-Demo`;
- instrument class and symbol: Forex / `EURUSD`;
- explicit effective range and source URL/version for every schedule record;
- timezone identifier and DST conversion provenance;
- one-off holiday intervals from the contemporaneous notices listed above;
- archived-official intervals only for the exact dates visible in the captured official pages;
- no recurring Christmas/New Year rule and no static exception for 2020/2021;
- no H1 weekly authorization until the observed UTC bar grid is reconciled with IFC's published platform clock.

This scope must not infer closures from ordinary acquisition metadata, generic calendars, repeated date patterns, or a current page outside its demonstrated effective period.

## Revised Provider Assessment

The earlier `NOT READY — IFC PROVIDER GAPS` wording is too broad. Official IFC evidence fully explains both H4 events and ten of twelve D1 weekday events, while the H1 events are an entirely recurrent weekly-boundary pattern with no intrawEEK residuals.

The more accurate fail-closed assessment is:

**NOT READY — SESSION/HOLIDAY AUTHORITY MISSING**

That result reflects missing authority and unresolved timestamp semantics, not demonstrated provider loss.

## Decision

H1 weekly authority evidence is **PARTIAL**. H4 holiday evidence is 2/2 `FULL_MATCH`, and **NO EVIDENCE OF H4 PROVIDER DATA LOSS**. D1 historical holiday evidence is 10/12, with 2023–2026 **COMPLETE** and 2018–2021 **PARTIAL**. Timezone conversion is verified, but the H1 exact UTC mapping remains unresolved.

**PARTIAL — HISTORICAL HOLIDAY EVIDENCE STILL MISSING**

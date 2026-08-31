# IFC 2020 Holiday Evidence Final Search

## Baseline

- Audit date: 2026-08-30.
- Source branch at start: `fix/ifc-timezone-aware-session-contract`.
- Source commit: `6650ff22a7c49f1b11a2b31cd1afef3eb8ace647`.
- Evidence branch: `diagnose/ifc-2020-holiday-evidence-final`.
- Scope: evidence collection for the two remaining IFC Markets Demo / EURUSD
  D1 dates, `2020-12-25` and `2021-01-01`.
- No provider, session-authority, qualification, training, activation,
  scheduler, trading, dataset, model, database, or runtime state was read or
  changed. The pre-existing untracked `data/` directory was left untouched.

The executable contract remains fail-closed until a separately reviewed change
binds the evidence records below into `IFCForexSessionAuthority`. This report is
not that change.

## Acceptance Criteria

Evidence is authoritative for this audit only when it is one of:

1. a current official IFC Markets page with date, affected trading scope,
   hours, and timezone;
2. a readable Wayback snapshot of an original IFC Markets URL containing those
   facts; or
3. an archived official IFC Company News index that identifies a precise IFC
   notice, provided the notice content can also be recovered authoritatively.

An adjacent-year notice, generic holiday calendar, search snippet, another
broker's schedule, or repeated market pattern is corroborative only. Nothing in
this audit creates a recurring Christmas/New-Year rule.

## Current Web Search

Current-web searches covered English, Spanish, Vietnamese, Russian, French,
German, Italian, Portuguese, and Czech Company News roots. Queries used both
date forms (`2020-12-25`, `25.12.2020`, `2021-01-01`, `01.01.2021`) and
translated Christmas/New-Year terms. The current Company News indexes and
historical detail results exposed by search engines returned adjacent notices,
but not the target notice.

Ten plausible English slugs were probed before the real URL was discovered.
They either received the site's HTTP 403 guard or returned only a generic asset
shell through a text fetcher; none was treated as evidence. Pagination probes
for the current dynamic index (`?page=2`, `?page=50`, and `?page=100`) likewise
returned no historical article content.

The current-web phase is **PASS as an executed search, with zero authoritative
target results**. It was the archived index, not a guessed URL, that revealed
the historical spelling error in the real slug.

## Wayback CDX Search

The public Wayback CDX and replay endpoints were accessible during this audit.

- Broad enumeration was run for both `ifcmarkets.com` and
  `www.ifcmarkets.com`, for the requested language roots, over the capture
  interval 2020-12-01 through 2021-01-15. Host normalization caused the two
  forms to converge on the same stored originals.
- The unfiltered Company News enumeration returned seven unique HTTP 200 HTML
  URLs. All seven were older May/July 2020 publications captured in the target
  interval; none concerned Christmas or New Year.
- A supplemental 2020-2022 Company News enumeration returned 111 unique URLs
  whose slugs contained `2020` or `2021`. A separate holiday-slug scan returned
  16 URLs. Neither contained the target English detail because the real slug
  misspells `christmas` as `chiristmas`.
- The exact English Company News index had no capture in the initial target
  interval, but CDX exposed readable captures at `20210125173509` and
  `20210205003759`. Both index snapshots preserve the target entry.
- The exact English detail URL had no HTTP 200 CDX capture. A host-wide scan for
  the newly discovered typo found one readable official detail capture in the
  Persian locale at `20230705153445`.

The seven URLs from the initial broad capture window were:

- `https://www.ifcmarkets.com/ja/company-news/s-oxy-top-trading-03072020`
- `https://www.ifcmarkets.com/pt/company-news/s-oxy-top-trading-03072020`
- `https://www.ifcmarkets.com/pt/company-news/trading-schedule-01072020`
- `https://www.ifcmarkets.com/ru/company-news/trading-schedule-01072020`
- `https://www.ifcmarkets.com/vi/company-news/memorial-day-us-uk-2020`
- `https://www.ifcmarkets.com/vi/company-news/s-oxy-top-trading-03072020`
- `https://www.ifcmarkets.com/vi/company-news/trading-schedule-01072020`

In total, **45 unique IFC Company News original URLs/paths were deliberately
queried or inspected**, in addition to programmatic review of the 111-row broad
CDX result. No whole HTML page, WARC payload, or browser dump is stored in this
repository.

## Discovered IFC URLs

The decisive archived English index entry is:

- original index URL: `https://www.ifcmarkets.com/en/company-news`
- archive URL:
  `https://web.archive.org/web/20210125173509id_/https://www.ifcmarkets.com/en/company-news`
- publication date shown by the index: `15/12/2020`
- title: `New Year and Christmas - Changes in the Trading Schedule.`
- linked path:
  `/en/company-news/chiristmas-newyear-trading-schedule-2020-2021`
- indexed scope: schedule changes for `24-25.12.2020`, `31.12.2020`, and
  `01.01.2021`, expressed in CET.

The typo in `chiristmas` explains why normal Christmas-slug searches missed the
notice. The same archived page also contains the language-root links needed to
identify the multilingual notice family.

The recoverable official detail is:

- original URL:
  `https://www.ifcmarkets.com/fa/company-news/chiristmas-newyear-trading-schedule-2020-2021`
- archive URL:
  `https://web.archive.org/web/20230705153445id_/https://www.ifcmarkets.com/fa/company-news/chiristmas-newyear-trading-schedule-2020-2021`
- Wayback timestamp: `20230705153445`
- Wayback response: HTTP 200, `text/html`
- CDX digest: `G75KP5DHDC6DBUH2YOJFWCPUN7YLEX3T`
- original publication date: `15/12/2020`
- language: Persian (`fa`)
- original title:
  `سال جدید میلادی و کریسمس - تغییرات در زمانبندی معامله`
- English title translation: `New Year and Christmas - Changes in the Trading
  Schedule`.

The search therefore produced **four relevant 2020/2021 candidate artifacts**:
two archived English index snapshots, the uncaptured English detail URL they
identify, and the readable archived Persian detail. Only the archived detail
is sufficient on its own; the English index snapshots bind it to the same
multilingual IFC notice.

Positive controls remain useful only for URL and notice-structure validation:

- [archived IFC 2018/2019 notice](https://web.archive.org/web/20190127194639id_/https://www.ifcmarkets.com/en/company-news/christmas-new-year-trading-schedule-2018-2019),
  published 2018-12-13;
- [archived IFC 2019/2020 notice](https://web.archive.org/web/20200108190923id_/https://www.ifcmarkets.com/en/company-news/christmas-new-year-trading-schedule-2020),
  published 2019-12-18;
- [archived IFC 2021/2022 notice](https://web.archive.org/web/20220528220500id_/https://www.ifcmarkets.com/en/company-news/christmas-new-year-2022),
  published 2021-12-20.

They demonstrate IFC's changing slug convention and CET schedule format. They
are not used to infer the 2020/2021 closures.

## Christmas 2020 Evidence

The archived official detail announces the Christmas/New-Year schedule in CET.
For the Christmas interval it states that trading and the office close at 19:00
CET on 2020-12-24, includes a further closure statement at 07:00 CET on
2020-12-25, and identifies 00:00 CET on 2020-12-28 as the next trading reopen.
The surrounding instrument table gives the special 2020-12-24 early closes;
the general close/reopen statements apply to the provider's trading schedule.

The explicit close followed by the only stated reopen places all of
`2020-12-25` inside the closed Christmas interval. The separate 07:00 statement
for December 25 is retained in the evidence summary rather than normalized
away. No recurring rule or unstated OHLC/session heuristic is needed.

Result for `2020-12-25`: **ARCHIVED_OFFICIAL — supported**.

## New Year 2020/2021 Evidence

For the New-Year interval, the same official detail states that trading and the
office close at 07:00 CET on 2020-12-31, explicitly identifies 2021-01-01 as a
day off, and identifies 00:00 CET on 2021-01-04 as the next trading reopen.

The archived English index independently binds the same underlying notice to
`31.12.2020` and `01.01.2021` in CET.

Result for `2021-01-01`: **ARCHIVED_OFFICIAL — supported**.

## Timezone Validation

The notice explicitly uses CET. Programmatic conversion used the IANA
`Europe/Berlin` zone; all four endpoints are in standard time with UTC offset
`+01:00`:

- `2020-12-24T19:00:00+01:00` = `2020-12-24T18:00:00Z`;
- `2020-12-28T00:00:00+01:00` = `2020-12-27T23:00:00Z`;
- `2020-12-31T07:00:00+01:00` = `2020-12-31T06:00:00Z`;
- `2021-01-04T00:00:00+01:00` = `2021-01-03T23:00:00Z`.

There is no CET/CEST ambiguity for either target date.

## Corroborative Evidence

Independent broker evidence was kept separate from IFC authority. World Forex's
[2020 Christmas/New-Year schedule](https://wforex.com/company-news/changes-schedule-trading-sessions-during-period-christmas-and-new-year-holidays-0),
published 2020-12-21, says currency trading was closed on both 2020-12-25 and
2021-01-01 in its EET schedule. This corroborates the market-wide holiday
pattern but does not authorize IFC behavior and is not included in an IFC
evidence hash.

## Evidence Records Proposed

Canonical source records use compact UTF-8 JSON without a BOM and
lexicographically sorted keys. Their SHA-256 values were computed over those
exact canonical serializations.

### Source record: archived English index

- `original_url`: `https://www.ifcmarkets.com/en/company-news`
- `archive_url`:
  `https://web.archive.org/web/20210125173509id_/https://www.ifcmarkets.com/en/company-news`
- `archive_timestamp`: `20210125173509`
- `publication_date`: `2020-12-15`
- `title`: `New Year and Christmas - Changes in the Trading Schedule.`
- `language`: `en`
- `evidence_status`: `ARCHIVED_OFFICIAL_INDEX`
- `relevant_scope`: IFC Markets schedule and exact multilingual notice
  discovery.
- `timezone`: `CET`
- `closure_summary`: the index binds the notice to 24-25 December 2020,
  31 December 2020, and 1 January 2021 and supplies its exact typo-bearing
  path.
- canonical serialization:

```json
{"archive_timestamp":"20210125173509","archive_url":"https://web.archive.org/web/20210125173509id_/https://www.ifcmarkets.com/en/company-news","closure_summary":"The archived IFC Company News index states that the trading schedule for 24-25.12.2020, 31.12.2020 and 01.01.2021 changed for listed instruments (CET) and links the exact notice slug.","evidence_status":"ARCHIVED_OFFICIAL_INDEX","language":"en","original_url":"https://www.ifcmarkets.com/en/company-news","publication_date":"2020-12-15","relevant_scope":"IFC Markets trading schedule; discovery record for the linked multilingual notice","timezone":"CET","title":"New Year and Christmas - Changes in the Trading Schedule."}
```

- `sha256`:
  `a782f5b3521abedf1b8d4550dd36e3625210fdc7c6c67dad93c8f25bac879832`

### Source record: archived official detail

- `original_url`:
  `https://www.ifcmarkets.com/fa/company-news/chiristmas-newyear-trading-schedule-2020-2021`
- `archive_url`:
  `https://web.archive.org/web/20230705153445id_/https://www.ifcmarkets.com/fa/company-news/chiristmas-newyear-trading-schedule-2020-2021`
- `archive_timestamp`: `20230705153445`
- `publication_date`: `2020-12-15`
- `title`: `سال جدید میلادی و کریسمس - تغییرات در زمانبندی معامله`
- `language`: `fa`
- `evidence_status`: `ARCHIVED_OFFICIAL`
- `relevant_scope`: IFC Markets general trading and office schedule, relevant
  to Forex and EURUSD.
- `timezone`: `CET`
- `closure_summary`: 24 December close at 19:00, 25 December closure statement
  at 07:00, 28 December reopen at 00:00; 31 December close at 07:00, 1 January
  day off, and 4 January reopen at 00:00.
- canonical serialization:

```json
{"archive_timestamp":"20230705153445","archive_url":"https://web.archive.org/web/20230705153445id_/https://www.ifcmarkets.com/fa/company-news/chiristmas-newyear-trading-schedule-2020-2021","closure_summary":"IFC trading closes 2020-12-24 19:00 CET; the notice states a 2020-12-25 07:00 CET closure and reopens 2020-12-28 00:00 CET. IFC trading closes 2020-12-31 07:00 CET; 2021-01-01 is a day off and trading reopens 2021-01-04 00:00 CET.","evidence_status":"ARCHIVED_OFFICIAL","language":"fa","original_url":"https://www.ifcmarkets.com/fa/company-news/chiristmas-newyear-trading-schedule-2020-2021","publication_date":"2020-12-15","relevant_scope":"IFC Markets general trading and office closure schedule; relevant to Forex and EURUSD","timezone":"CET","title":"سال جدید میلادی و کریسمس - تغییرات در زمانبندی معامله"}
```

- `sha256`:
  `a1f1b373044d4121ad5135b808d20de5a9497b690ee92fe60d4cbf8e8ea59139`

Two exact historical authority records are proposed for a future separately
reviewed implementation:

1. `target_date=2020-12-25`, local interval
   `2020-12-24T19:00:00+01:00/2020-12-28T00:00:00+01:00`, UTC interval
   `2020-12-24T18:00:00Z/2020-12-27T23:00:00Z`, scope
   `provider=MT5;server=IFCMarkets-Demo;symbol=EURUSD;timeframe=D1;historical_exact_only`,
   canonical-record SHA-256
   `0860c36b3bf0b242248eefbf45d7fab323b124111b99ca91e372f64a0138a9e9`.

   ```json
   {"authority_scope":"provider=MT5;server=IFCMarkets-Demo;symbol=EURUSD;timeframe=D1;historical_exact_only","local_interval":"2020-12-24T19:00:00+01:00/2020-12-28T00:00:00+01:00","source_archive_timestamp":"20230705153445","source_original_url":"https://www.ifcmarkets.com/fa/company-news/chiristmas-newyear-trading-schedule-2020-2021","target_date":"2020-12-25","timezone":"Europe/Berlin","utc_interval":"2020-12-24T18:00:00Z/2020-12-27T23:00:00Z"}
   ```

2. `target_date=2021-01-01`, local interval
   `2020-12-31T07:00:00+01:00/2021-01-04T00:00:00+01:00`, UTC interval
   `2020-12-31T06:00:00Z/2021-01-03T23:00:00Z`, with the same exact-only
   scope, canonical-record SHA-256
   `f65ab1506e80a5ea58451c456dc4f646d97e837472129a8f16229884ed6b2f9e`.

   ```json
   {"authority_scope":"provider=MT5;server=IFCMarkets-Demo;symbol=EURUSD;timeframe=D1;historical_exact_only","local_interval":"2020-12-31T07:00:00+01:00/2021-01-04T00:00:00+01:00","source_archive_timestamp":"20230705153445","source_original_url":"https://www.ifcmarkets.com/fa/company-news/chiristmas-newyear-trading-schedule-2020-2021","target_date":"2021-01-01","timezone":"Europe/Berlin","utc_interval":"2020-12-31T06:00:00Z/2021-01-03T23:00:00Z"}
   ```

These records must not authorize another year, symbol, provider, server,
timeframe, or recurring holiday.

## Remaining Unsupported Dates

Evidence result: **none**. The two formerly unsupported evidence dates now have
an archived-official, source-bound notice:

- `2020-12-25`: supported by the Christmas close/reopen interval;
- `2021-01-01`: supported by the New-Year close, explicit day-off statement,
  and reopen interval.

Implementation state is intentionally different: both dates remain fail-closed
in the current executable authority because this task did not modify production
code. A qualification retry before a separately reviewed evidence-binding patch
would therefore be premature.

## IFC Support Escalation

No support escalation is required to establish the two dates: the authoritative
archived IFC detail was recovered. The official current contact page identifies
[`support@ifcmarkets.com`](https://www.ifcmarkets.com/en/contact-us), but no
message was sent and no draft is needed for this decision.

## Decision

**EVIDENCE COMPLETE — BOTH 2020 HOLIDAYS AUTHORITATIVELY SUPPORTED**

The same IFC notice covers both `2020-12-25` and `2021-01-01`. Evidence is
sufficient to prepare an exact, provenance-bound authority update for both
historical intervals. This report does not itself change that authority, so a
live EURUSD qualification retry is not yet authorized.

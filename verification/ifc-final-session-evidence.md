# IFC Final Session Evidence Audit

## Scope and baseline

This evidence-only follow-up attempts to close the two independent gaps identified in `verification/ifc-forex-session-holiday-evidence.md`:

1. the exact current weekly-session mapping for `IFCMarkets-Demo / EURUSD`; and
2. authoritative IFC evidence for the closures on 2020-12-25 and 2021-01-01.

The audit was performed on 2026-08-30 from commit `a3bd53acf1d67374ec0403522dd59691f95e5e80`. No production code, classifier, provider, candle, qualification, model, database, activation, scheduler, account, order, position, or trading state was modified or exercised.

The two tracks remain independent. Failure to complete one track is not offset by evidence obtained in the other.

## Track A — MQL5 runtime session metadata

### Authoritative mechanism

The official [MQL5 Market Information reference](https://www.mql5.com/en/docs/marketinformation) defines `SymbolInfoSessionTrade()` as the read-only function that returns the beginning and end of each trading session for a symbol, weekday, and zero-based session index. This is the appropriate terminal-runtime evidence for the current broker configuration.

The existing IFC evidence remains unchanged:

- IFC's [2026 European summer-time notice](https://www.ifcmarkets.com/en-CA/company-news/europe-summer-time-2026), published 2026-03-27, establishes the published Forex schedule effective from 2026-03-29.
- IFC's current [Trading Times](https://www.ifcmarkets.com/en/trading-conditions/trading-times) page gives the regular Forex schedule.
- IFC's [Trading FAQ](https://www.ifcmarkets.com/en/faqs) says that IFC platforms use CET/CEST and switch on the last Sunday of March and October.
- The observed H1 evidence contains sixteen identical Friday 21:00 UTC to Monday 00:00 UTC discontinuities and zero residual intrawEEK gaps during 2026-05-04 through 2026-08-28.

### Temporary script and compilation

A temporary, unversioned MQL5 script named `IFCSessionEvidence.mq5` was created in the active terminal's `MQL5\Scripts` directory, outside the repository. It:

- queries only `EURUSD`;
- iterates Monday through Sunday;
- increments `session_index` from zero until `SymbolInfoSessionTrade()` returns false;
- prints only `symbol`, `day`, `session_index`, `from`, and `to`;
- contains no account-information, order, position, trade-class, DLL, file-write, or trading call.

MetaEditor command-line compilation completed with **0 errors and 0 warnings** and produced the temporary `IFCSessionEvidence.ex5` outside the repository.

### Execution constraint

The IFC MetaTrader 5 terminal was already running and connected. MetaQuotes documents automatic script startup through a custom `[StartUp]` configuration, but applying that path here would require changing or restarting the active terminal state, or launching a second instance with account/profile state. No direct, isolated Python API exists for `SymbolInfoSessionTrade()`, and no safe stateless CLI can inject the script into the already-running terminal.

GUI automation, terminal restart, profile mutation, credential handling, and a second account-bearing instance were deliberately not attempted.

Result: **MANUAL_MT5_SCRIPT_EXECUTION_REQUIRED**.

Minimum operator procedure:

1. In the already connected `IFCMarkets-Demo` terminal, open any `EURUSD` chart.
2. In Navigator, run `Scripts\IFCSessionEvidence` once.
3. Copy only the `symbol = EURUSD` line and the `day=... session_index=... from=... to=...` lines from the Experts log.
4. Do not copy the full terminal log or any account information.
5. After the evidence is captured, delete the temporary `.mq5` and `.ex5` files.

### Runtime result slots

Because safe automatic execution was not available, no runtime session values were obtained.

| Day | Runtime `SymbolInfoSessionTrade()` result |
| --- | --- |
| Monday | NOT_OBTAINED — manual execution required |
| Tuesday | NOT_OBTAINED — manual execution required |
| Wednesday | NOT_OBTAINED — manual execution required |
| Thursday | NOT_OBTAINED — manual execution required |
| Friday | NOT_OBTAINED — manual execution required |
| Saturday | NOT_OBTAINED — manual execution required |
| Sunday | NOT_OBTAINED — manual execution required |

### H1 assessment

The official published schedule continues to explain the repeated weekend shape qualitatively, but the runtime metadata needed to reconcile IFC's CEST schedule with the observed MT5 UTC bar grid is absent. Therefore no observed gap can yet be authorized **exactly** from `SymbolInfoSessionTrade()` evidence.

- published weekly-pattern explanation: 16/16;
- exact runtime-backed mapping: 0/16;
- exact timestamp authority: **PARTIAL**;
- contradiction: none established, because the runtime values were not obtained.

## Track B — 2020/2021 historical holiday evidence

### Wayback CDX search

Directed read-only CDX queries targeted captures from 2020-12-01 through 2021-01-15 under `ifcmarkets.com`, including `company-news` paths and filters for Christmas, New Year, schedule, trading, 2020, and 2021. Prefix and wildcard queries were attempted over HTTPS and HTTP, including IPv4-only retries.

The public `web.archive.org` CDX/replay host was unreachable from this environment: each direct attempt ended in a connection timeout. The same restriction prevented retrieval of raw archived index-page content. Accordingly, the CDX execution result is **FAIL (archive endpoint unavailable)**, not a claim that the Wayback index contains no records.

### Availability API and directed discovery

The official Internet Archive Availability API at `archive.org/wayback/available` remained accessible and was used as a narrower fallback. It checked the six requested discovery slugs across all eight requested IFC language roots (`en`, `es`, `ru`, `vi`, `fr`, `de`, `pt`, and `it`): 48 targeted candidate URLs in total.

The candidate slugs were:

- `christmas-new-year-2021`;
- `christmas-new-year-2020-2021`;
- `christmas-new-year-trading-schedule-2021`;
- `christmas-new-year-trading-schedule-2020-2021`;
- `christmas-trading-schedule-2020`;
- `new-year-trading-schedule-2021`.

None returned an available archived page. Positive-control checks did find known adjacent IFC notices: the 2019/2020 schedule under `christmas-new-year-trading-schedule-2020` in multiple languages and the 2021/2022 schedule under `christmas-new-year-2022` in multiple languages. This demonstrates that the fallback query could detect known IFC archive records while finding no target 2020/2021 notice under the directed slugs.

Availability checks also found archived `company-news` index snapshots for several language roots, but the closest useful index captures were outside the requested interval (for example, English on 2021-01-25, and French, Portuguese, Vietnamese, and German in February 2021). Because the replay host was unreachable, their contents and links could not be inspected. An index timestamp alone is not schedule authority.

Search-engine discovery covered exact dates, English title variants, the requested language roots, and current official IFC regional mirrors. It found the known 2019/2020 and 2021/2022 notices but no 2020/2021 IFC notice. Common Crawl was used only as ancillary URL discovery; partial index responses exposed no relevant URL and intermittent service failures made it unsuitable as exhaustive or authoritative evidence.

Relevant 2020 IFC captures with visible, sufficient schedule content discovered: **0**.

### Event classification

| Event | Authority classification | Supported | Reason |
| --- | --- | --- | --- |
| 2020-12-25 | NONE | no | No official historical page or readable archived-official IFC page was found |
| 2021-01-01 | NONE | no | No official historical page or readable archived-official IFC page was found |

No recurring Christmas or New Year rule is inferred from 2018, 2019, 2023, 2024, or 2025. Those years are strong corroboration only for the unresolved dates and cannot authorize them.

Result: **OFFICIAL_2020_ARCHIVE_NOT_FOUND**.

The next authoritative route is a request to IFC Markets support for written confirmation of the Forex trading schedule for 2020-12-25 and 2021-01-01, preferably an official/archived URL, PDF, or written response stating the relevant dates, hours, and timezone. No credentials or account data are needed or should be supplied.

## Unchanged supported evidence

- H4 Christmas 2025: supported, full match.
- H4 New Year 2025/2026: supported, full match.
- H4 support remains 2/2, with zero unexplained H4 provider gaps.
- D1 support remains 10/12.
- There is still no positive evidence of actual IFC provider data loss.

## Remaining blockers

Two independent evidence blockers remain:

1. manual execution of the compiled read-only MQL5 script and capture of the seven weekday session results, followed by exact comparison with the sixteen H1 gaps; and
2. authoritative IFC confirmation for 2020-12-25 and 2021-01-01, or successful future access to a readable archived IFC notice with sufficient schedule content.

The provider assessment remains `NOT READY — SESSION/HOLIDAY AUTHORITY MISSING`.

## Decision

H1 exact authority is **PARTIAL**, with 0/16 exactly runtime-authorized. Historical D1 support remains 10/12. The two H4 events remain fully supported and there is no evidence of actual provider data loss.

**PARTIAL — H1 AND 2020 HOLIDAY EVIDENCE REMAIN**

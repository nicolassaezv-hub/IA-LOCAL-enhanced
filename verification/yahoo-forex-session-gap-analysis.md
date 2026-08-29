# Yahoo Forex Session / Gap Analysis

## Baseline

- Diagnostic branch: `diagnose/yahoo-forex-session-gaps`.
- Approved source HEAD: `55e56255f41fb5621ec844c9369dfa6af80294c7`.
- Retry evidence commit reviewed: `6270e97ad20c162a11a95f1b02d6ac2c2ae08d7b`.
- Python: `3.12.6`; yfinance: `1.7.0`.
- Analysis was read-only: no DB/lifecycle mutation, qualification, canonical update, training, model activation, or scheduler run.
- Network acquisition was limited to public Yahoo metadata, one wide H1 download, and one D1 download. All reconstruction was in memory.
- Current blocking counts reproduced from the retry artifacts: H1 `17`, H4 `74`, D1 `5`.
- OHLC, indicator, and sanitization-provenance defects from the earlier run were not reproduced.

## Yahoo Native Metadata

`Ticker("EURUSD=X").get_history_metadata()` exists and returned all queried fields:

- `exchangeTimezoneName`: `Europe/London`.
- `timezone`: `BST` at query time.
- `gmtoffset`: `3600` at query time.
- `instrumentType`: `CURRENCY`.
- `exchangeName`: `CCY`.
- `regularMarketTime`: a current timestamp.
- `currentTradingPeriod`: current-day `pre`, `regular`, and `post` intervals, with the regular interval reported as `00:00` through `23:59` London time.
- `tradingPeriods`: five current weekday rows (2026-08-24 through 2026-08-28), also expressed in London time.

The metadata also exposed `firstTradeDate`, `dataGranularity`, `validRanges`, `hasPrePostMarketData`, price fields, names, and repair metadata. No field in the returned payload supplied a versioned historical session calendar, historical holidays, or effective-date rules for weekend open/close transitions.

Assessment: Yahoo exposes useful current timezone/session metadata, but only partially. It is insufficient as contractual authority because:

1. `currentTradingPeriod` is current-only.
2. `tradingPeriods` covered only the current five weekdays.
3. The daily `00:00–23:59` representation does not explain the observed weekend boundary.
4. It cannot prove historical holidays, outages, or why specific historical bars were omitted.

## H1 Weekly Session Pattern

The read-only H1 response contained `17,237` valid closed rows from `2023-11-13 00:00 UTC` through `2026-08-28 21:00 UTC`; no H1 row was rejected by OHLC sanitization.

Within the 2,000-row qualification artifact:

- `16/17` gaps match the recurring summer pattern exactly: Friday `21:00 UTC` to Sunday `23:00 UTC`, duration `180,000` seconds (50 hours).
- `1/17` is not a weekly boundary.

Across the wider response, the dominant recurrent groups demonstrate DST behavior:

- Summer/London-or-New-York DST pattern: Friday `21:00 UTC` to Sunday `23:00 UTC`; `81` occurrences in the downloaded range.
- Winter pattern: Friday `22:00 UTC` to Monday `00:00 UTC`; `48` occurrences.
- Small transition groups occur around weeks where London and New York change DST on different dates.
- Exceptional delayed resumptions also exist; they are not promoted to session closures by this analysis.

Using `zoneinfo.ZoneInfo("America/New_York")` and the diagnostic reference session Sunday 17:00 New York through Friday 17:00 New York:

- The normal Yahoo final Friday bar is stamped around 17:00 New York.
- Yahoo usually resumes around 19:00 New York, approximately two hours later than the reference open.
- Therefore the generic 17:00 New York comparator does **not** fully explain the Yahoo gap: each recurrent gap includes timestamps during which that reference says the market is open.
- All `17` qualification gaps contain at least one reference-open missing timestamp; zero are wholly closed under the generic comparator.

The observed recurrence is strong evidence for a Yahoo-specific schedule profile, but it is not itself an authorized session contract.

## H1 True In-Session Gaps

The sole non-weekly H1 gap is:

- Previous: `2026-07-17 05:00:00 UTC`.
- Next: `2026-07-17 09:00:00 UTC`.
- Duration: `14,400` seconds.
- Expected missing timestamps: `06:00`, `07:00`, and `08:00 UTC`.
- Present in the new raw Yahoo H1 response: no for all three.
- New York reference session open: yes for all three.
- Provisional classification: `RAW_PROVIDER_MISSING`.

This is a genuine upstream Yahoo omission in an expected-open interval, not a weekend boundary and not a sanitization effect.

Diagnostic H1 reclassification:

- Current: `PROVIDER_GAP=17`.
- If an authorized Yahoo session profile eventually proves the recurrent schedule: `MARKET_SESSION_CLOSED=16`, `PROVIDER_GAP=1`.
- Under the generic Sunday/Friday 17:00 New York comparator alone: `MARKET_SESSION_CLOSED=0`, `PROVIDER_GAP=17`, because Yahoo's observed reopen is later.

## H4 Resample Boundary Analysis

ASTRA H4 is derived from Yahoo H1 and requires four consecutive H1 observations for a block. Reconstructing H4 directly from the same raw H1 response produced `4,192` complete H4 blocks.

Of the `74` H4 qualification gaps:

- `67` match Friday `16:00 UTC` to Monday `00:00 UTC`, duration `201,600` seconds.
- These are the combined result of the recurrent weekly boundary and the complete-four-H1 requirement.
- The Friday `20:00` H4 block is incomplete near session close; the Sunday `20:00` block is incomplete near Yahoo's later session resume. Both are omitted, so the next complete block begins Monday `00:00`.
- Conceptual diagnostic category: `RESAMPLE_SESSION_BOUNDARY=67` if, and only if, an authorized source first proves the underlying Yahoo session closure.

This is not native Yahoo H4 behavior and must not be represented as such. H4 needs upstream H1/session and resample provenance.

## H4 Residual Gaps

Exactly seven H4 gaps do not match the recurrent Friday-16-to-Monday-00 pattern:

1. `2025-09-15 16:00 -> 2025-09-16 04:00` (`43,200` seconds): incomplete blocks caused by missing H1 `22:00`, `23:00`, and `00:00`; all are reference-open. Category: `UPSTREAM_H1_PROVIDER_GAP`.
2. `2025-12-25 04:00 -> 2025-12-26 00:00` (`72,000` seconds): multiple partial/empty H1 blocks in a reference-open weekday. Category: `HOLIDAY_OR_SESSION_ANOMALY_UNPROVEN`.
3. `2025-12-31 20:00 -> 2026-01-02 00:00` (`100,800` seconds): multiple partial/empty H1 blocks throughout 2026-01-01. Category: `HOLIDAY_OR_SESSION_ANOMALY_UNPROVEN`.
4. `2026-01-30 12:00 -> 2026-02-02 20:00` (`288,000` seconds): absence begins during reference-open Friday hours and extends well beyond the ordinary weekly resume. Category: `UPSTREAM_H1_PROVIDER_GAP` plus a weekly boundary.
5. `2026-04-20 00:00 -> 2026-04-20 12:00` (`43,200` seconds): missing H1 `07:00` and `08:00` makes two blocks incomplete during reference-open hours. Category: `UPSTREAM_H1_PROVIDER_GAP`.
6. `2026-05-01 16:00 -> 2026-05-04 04:00` (`216,000` seconds): weekly boundary with a later-than-normal resume; the generic reference says several Sunday/Monday hours should be open. Category: `HOLIDAY_OR_SESSION_ANOMALY_UNPROVEN`.
7. `2026-07-17 00:00 -> 2026-07-17 12:00` (`43,200` seconds): direct consequence of the H1 `06:00–08:00` raw omission. Category: `UPSTREAM_H1_PROVIDER_GAP`.

No residual was silently classified as a session closure. Diagnostic counts after a future authorized session plus resample contract would be:

- `RESAMPLE_SESSION_BOUNDARY=67`.
- Residual blocking gaps=`7` (`4` direct/extended upstream H1 gaps and `3` unproven holiday/session anomalies).
- `UNKNOWN=0` for this observed set, while the three unproven anomalies remain blocking.

## D1 Exact Provider Gaps

The single authorized D1 download and in-process contract reconstruction produced:

- Raw rows: `5,901`.
- Raw closed rows: `5,901`.
- Invalid rows dropped: `128`.
- Sanitization reason: `INVALID_OHLC_ENVELOPE=128`.
- Valid rows before tail: `5,773`.
- Returned valid rows: `2,001`.
- Qualification-equivalent artifact rows: `2,000`.
- Gap counts: `WEEKEND=388`, `SANITIZED_PROVIDER_ROW=51`, `PROVIDER_GAP=5`, `INVALID_GAP=0`, `EXPECTED_MARKET_CLOSURE=0`.

The exact five provider gaps are:

1. `2019-05-21 -> 2019-05-23`; duration `172,800` seconds. Missing `2019-05-22` (Wednesday). Present in raw D1: no. Discarded by sanitization: no.
2. `2024-12-31 -> 2025-01-02`; duration `172,800` seconds. Missing `2025-01-01` (Wednesday). Present in raw D1: no. Discarded by sanitization: no.
3. `2025-04-15 -> 2025-04-22`; duration `604,800` seconds. This is a mixed gap:
   - `2025-04-16` Wednesday: present raw, discarded as `INVALID_OHLC_ENVELOPE`.
   - `2025-04-17` Thursday: present raw, discarded as `INVALID_OHLC_ENVELOPE`.
   - `2025-04-18` Friday: absent raw, not sanitized.
   - `2025-04-19` Saturday: absent raw, not sanitized.
   - `2025-04-20` Sunday: absent raw, not sanitized.
   - `2025-04-21` Monday: absent raw, not sanitized.
   Because the provenance covers only part of the expected-open missing timestamps, the entire gap correctly remains `PROVIDER_GAP`.
4. `2025-12-24 -> 2025-12-26`; duration `172,800` seconds. Missing `2025-12-25` (Thursday). Present in raw D1: no. Discarded by sanitization: no.
5. `2025-12-31 -> 2026-01-02`; duration `172,800` seconds. Missing `2026-01-01` (Thursday). Present in raw D1: no. Discarded by sanitization: no.

The fifth gap is therefore `2025-04-15 -> 2025-04-22`, not a guessed single holiday date. Its partial sanitization provenance is insufficient by design.

## D1 vs H1 Evidence

The wide H1 response overlaps all recent D1 cases:

- Missing D1 `2025-01-01`: `7` H1 rows exist.
- `2025-04-16`: `24` H1 rows; D1 existed raw but was sanitized.
- `2025-04-17`: `24` H1 rows; D1 existed raw but was sanitized.
- Missing raw D1 `2025-04-18`: `22` H1 rows exist.
- `2025-04-19`: `0` H1 rows.
- `2025-04-20`: `1` H1 row.
- Missing raw D1 `2025-04-21`: `24` H1 rows exist.
- Missing D1 `2025-12-25`: `11` H1 rows exist.
- Missing D1 `2026-01-01`: `7` H1 rows exist.
- The 2019 gap is outside the available H1 range.

Thus every recent raw-missing D1 weekday still has H1 observations for at least part of that date. This supports a D1 aggregation/publication-specific omission or partial-session effect rather than a total Yahoo outage, but it is not authoritative proof of a market holiday.

## Current Gap Contract Problem

The current contract intentionally treats every expected weekday timestamp without exact sanitization provenance as `PROVIDER_GAP`. This is fail-closed and correctly prevents weekly/session heuristics, ordinary metadata, or date guesses from unblocking qualification.

The resulting false-positive class is structural:

- H1 cadence assumes all wall-clock hours except Saturday/Sunday are expected, so the provider's Friday/Sunday boundary leaves weekday-edge timestamps unexplained.
- H4 applies that same wall-clock expectation to resampled blocks and does not record why incomplete boundary blocks were omitted.
- D1 correctly separates exact sanitization gaps, but real provider omissions remain mixed with possible partial-session closures.

The contract should remain blocking until an independent authority can distinguish intentional closure from an expected-open provider omission.

## Failed-Evidence Reporting Gap

Defect confirmed: yes.

`qualify_candidate()` computes `acquisition_metadata`, the isolated candidate path, and the complete validation `stage` before raising on a blocking stage. The `except` block currently persists only `result`, a summarized error, and `attempt_errors`. It loses acquisition counts, dropped timestamps/reasons, validation details, and exact gap items even though the isolated evidence JSON is still written. `database.mark_qualified()` is already guarded by `evidence["result"] == "PASS"`, so retaining diagnostic failure evidence would not qualify the symbol or touch the production registry.

Minimum future patch:

1. Initialize optional per-timeframe diagnostic locals before the `try`.
2. In the failure path, include any already-produced route identity, acquisition metadata, isolated candidate path/SHA, row counts, and validation stage.
3. Preserve the existing `FAIL` result and the PASS-only `mark_qualified()` guard.
4. Do not copy the candidate to canonical paths or upsert `dataset_registry`.
5. Add tests proving failed evidence survives with exact dropped rows/gaps while lifecycle remains `candidate`, registry stays unchanged, and canonical paths remain absent.

No implementation was made in this audit.

## Simulated Corrected Classification

Two diagnostic simulations must be kept distinct:

### Generic 17:00 New York reference only

- H1: `MARKET_SESSION_CLOSED=0`, `PROVIDER_GAP=17`, because Yahoo normally resumes about two hours after the generic reference says the session is open.
- H4: the generic reference alone cannot authorize the `67` resample-boundary gaps; they remain unproven.
- D1: `SANITIZED_PROVIDER_ROW=51`, `PROVIDER_GAP=5`.

### Future authorized Yahoo/session plus resample provenance

- H1 actual `PROVIDER_GAP=17` -> simulated `MARKET_SESSION_CLOSED=16`, `PROVIDER_GAP=1`, `SANITIZED_PROVIDER_ROW=0`, `INVALID_GAP=0`.
- H4 actual `PROVIDER_GAP=74` -> simulated `RESAMPLE_SESSION_BOUNDARY=67`, residual `PROVIDER_GAP=7`, `SANITIZED_PROVIDER_ROW=0`, `INVALID_GAP=0`.
- D1 actual `PROVIDER_GAP=5` -> simulated `SANITIZED_PROVIDER_ROW=51`, residual `PROVIDER_GAP=5`, `INVALID_GAP=0`. No D1 provider gap is changed to a closure without authority.

The important residual is therefore H1=`1`, H4=`7`, D1=`5`. Session handling alone cannot make qualification pass.

## Architecture Options

### Option A — Forex market session contract

Advantages: timezone-aware, DST-correct, explicit effective-date/version provenance, reusable across providers and timeframes. Risks: spot FX is OTC and has no single exchange calendar; a generic Sunday/Friday 17:00 New York rule does not match Yahoo's observed two-hour-later resume and cannot prove provider holidays.

### Option B — Provider-specific session contract

Advantages: can model the stable Yahoo-specific Friday/Sunday pattern and DST transitions. Risks: Yahoo's native metadata is current-only and does not prove its historical weekend or holiday policy. An observed pattern must not self-authorize. This option is acceptable only if backed by a versioned authoritative source and effective-date rules.

### Option C — Resample provenance

Advantages: directly explains why H4 blocks were omitted when fewer than four H1 observations existed; avoids pretending Yahoo supplied native H4; preserves exact upstream causes. Risks: it does not establish whether the missing H1 data was a legitimate closure or an outage. It must depend on A/B or remain blocking.

### Option D — Second-provider gap verification/fill

Advantages: an independent real provider can distinguish Yahoo omission from broad market closure and may supply authentic missing OHLC. Risks: symbol/session semantics, timestamps, prices, licenses, and provider quality must be reconciled; mixing sources needs explicit per-row provenance. No price may be synthesized. Verification can remain diagnostic even when fill is not authorized.

### Option E — Allow provenance-backed missing market data

Advantages: permits training on honest irregular observations without fabricating prices. Risks: a return across a multi-period gap is treated as one observation; RSI/MACD EWM decay is observation-based rather than elapsed-time-based; ATR absorbs gap jumps; WFV sees inconsistent cadence/horizon; feature semantics and timestamp joins change. This must not be enabled automatically. It would require explicit gap features, elapsed-time-aware transformations or segmentation, and dedicated statistical gates.

## Recommended Production Contract

Use Options A, C, and D together, with a constrained future Option B only when authoritative Yahoo session evidence exists:

1. Introduce a versioned, timezone-aware session authority interface with source identity, effective date range, timezone database version, session intervals, and evidence hash. Default absence of authority remains blocking.
2. Separate `MARKET_SESSION_CLOSED` from provider data. A timestamp is closed only when the authority explicitly covers it; neither weekday/date heuristics nor ordinary acquisition metadata can authorize it.
3. Record H4 block-level resample provenance: expected H1 members, observed members, missing members, session-closed members, upstream-provider-missing members, and why the block was omitted.
4. For every expected-open missing H1/D1 timestamp, retain `PROVIDER_GAP` and optionally query a second authoritative provider. Store exact per-row/provider provenance; never synthesize OHLC.
5. Persist full failed qualification evidence in the isolated qualification area so every decision remains auditable without repeating a mutable external fetch.
6. Keep `EXPECTED_MARKET_CLOSURE` unavailable until a trusted historical calendar/session source exists.

## Remaining Real Provider Gaps

After only the recurrent session/resample pattern is authoritatively explained:

- H1: `1` real residual (`2026-07-17 06:00–08:00` missing raw).
- H4: `7` residual gaps; four directly/partly trace to H1 provider omissions and three are unproven holiday/session anomalies.
- D1: `5` residual gaps, including the mixed partial-sanitization gap `2025-04-15 -> 2025-04-22`.

All remain blocking until independently explained or supplied by an authorized real provider.

## Viability Assessment

`NOT READY — SESSION MODEL INCOMPLETE AND REAL PROVIDER GAPS REMAIN`

The recurrent H1/H4 false positives are explainable in principle, but Yahoo's native metadata is not sufficient contractual authority and session handling alone would not clear qualification. The architecture needs an authorized session contract, H4 resample provenance, full failed-evidence persistence, and independent verification for expected-open omissions before EURUSD can be retried safely.

# EURUSD Post-Contract-Fix Verification

## Code Baseline

- Branch: `verify/eurusd-after-contract-fix`
- Approved source HEAD: `55e56255f41fb5621ec844c9369dfa6af80294c7`
- Python: `3.12.6` from `.venv`
- No code was modified during this verification.

## Runtime Pre-State

- EURUSD lifecycle status: `candidate`.
- Productive alias `models/forex/latest_EURUSD.pkl`: absent.
- Quarantined legacy model: present at `models/forex/legacy_unverified/latest_EURUSD_cf22ead0e88f5a71c730e4462e3ac7e29503e9652067c73ffa2cb41f649a9c07.pkl`.
- Quarantined legacy SHA256: `cf22ead0e88f5a71c730e4462e3ac7e29503e9652067c73ffa2cb41f649a9c07`.
- Previous qualification evidence SHA256: `8b4f4d12d7f7098d281d914062eae07aa07d213754ec42883c370b5e4d69688c`.
- Previous qualification timestamp: `2026-08-29T03:49:09.200428+00:00`.
- Previous qualification result: `FAIL`.

## Qualification Retry

- Command executed exactly once: `.\.venv\Scripts\python.exe scripts/manage_symbol_lifecycle.py qualify-symbol EURUSD`.
- Exit code: `1`.
- Result: `FAIL`.
- Qualification timestamp: `2026-08-29T16:47:03.115797+00:00`.
- Evidence path: `data/qualification/EURUSD/evidence.json`.
- Evidence SHA256: `84523f2ae24c1908f79612c4ba6b280ef640f425eef9b6331b1c0c609754f4b8`.
- Catalog version: `6f2a7b3f0266099c311dcbb3defa55981e12483ed7c2766104f5b44ccef1a855`.
- Stop condition was honored immediately after qualification failed. No canonical update, training, activation, H1 scheduler run, or second provider fetch was executed.

## Yahoo Acquisition Evidence

- H1/H4/D1 attempted MT5 first; `MT5 unavailable` was recorded and the configured Yahoo fallback produced each candidate artifact.
- Requested bars per timeframe: `2001` (`PROBE_BARS`).
- Persisted qualification artifact rows per timeframe: `2000`.
- Artifact SHA256 values:
  - H1: `388cb95cd29899a8d5dbd6d2ec74e5db2f315f51eecd9fb3286fe5a3a3d9c03e`.
  - H4: `d2e7c0b51ea99dec0e7ffd161f920b93b90ced917522e348682c63fbab2345f7`.
  - D1: `ee2b75907b66c9b5c3f5db8701294b980aaf19f78ef4e2f94639f5b3d5fb70f1`.
- The provider's in-memory acquisition metadata was used by validation, as proven by the distinct D1 counts `SANITIZED_PROVIDER_ROW=51` and `PROVIDER_GAP=5`.
- On a failed timeframe, the current evidence writer retains the error summary but not the full acquisition metadata or validation stage. Consequently `raw_closed_rows`, `invalid_rows_dropped`, `valid_rows_before_tail`, `returned_rows`, sanitization reasons, dropped timestamps, and the exact mapping of the five D1 provider gaps are not recoverable after the process exits.
- A second fetch was deliberately not used to reconstruct that missing reporting detail because the qualification-failure contract requires a complete stop.

## Sanitization Evidence

- H1 accepted artifact OHLC-invalid rows: `0`.
- H4 accepted artifact OHLC-invalid rows: `0`.
- D1 accepted artifact OHLC-invalid rows: `0`.
- D1 validation reported `51` known gaps backed by exact sanitization provenance. These were non-blocking and were not counted among the five provider gaps.
- No `EXPECTED_MARKET_CLOSURE` was reported.
- The exact dropped timestamps and reason-by-timestamp were available in-process but were not serialized into failed evidence; they are therefore not asserted here.

## Gap Classification

Runtime classification used acquisition provenance and reported:

- H1: `PROVIDER_GAP=17`; `SANITIZED_PROVIDER_ROW=0`; `INVALID_GAP=0`; `EXPECTED_MARKET_CLOSURE=0`.
- H4: `PROVIDER_GAP=74`; `SANITIZED_PROVIDER_ROW=0`; `INVALID_GAP=0`; `EXPECTED_MARKET_CLOSURE=0`.
- D1: `WEEKEND=388`; `SANITIZED_PROVIDER_ROW=51`; `PROVIDER_GAP=5`; `INVALID_GAP=0`; `EXPECTED_MARKET_CLOSURE=0`.

The H1 and H4 artifacts contain no reported sanitization-backed gaps, so the following blocking intervals existed in the provider output and were not caused by sanitization.

### H1 provider gaps (17)

- `2026-05-08 21:00:00` -> `2026-05-10 23:00:00`; `180000` seconds.
- `2026-05-15 21:00:00` -> `2026-05-17 23:00:00`; `180000` seconds.
- `2026-05-22 21:00:00` -> `2026-05-24 23:00:00`; `180000` seconds.
- `2026-05-29 21:00:00` -> `2026-05-31 23:00:00`; `180000` seconds.
- `2026-06-05 21:00:00` -> `2026-06-07 23:00:00`; `180000` seconds.
- `2026-06-12 21:00:00` -> `2026-06-14 23:00:00`; `180000` seconds.
- `2026-06-19 21:00:00` -> `2026-06-21 23:00:00`; `180000` seconds.
- `2026-06-26 21:00:00` -> `2026-06-28 23:00:00`; `180000` seconds.
- `2026-07-03 21:00:00` -> `2026-07-05 23:00:00`; `180000` seconds.
- `2026-07-10 21:00:00` -> `2026-07-12 23:00:00`; `180000` seconds.
- `2026-07-17 05:00:00` -> `2026-07-17 09:00:00`; `14400` seconds.
- `2026-07-17 21:00:00` -> `2026-07-19 23:00:00`; `180000` seconds.
- `2026-07-24 21:00:00` -> `2026-07-26 23:00:00`; `180000` seconds.
- `2026-07-31 21:00:00` -> `2026-08-02 23:00:00`; `180000` seconds.
- `2026-08-07 21:00:00` -> `2026-08-09 23:00:00`; `180000` seconds.
- `2026-08-14 21:00:00` -> `2026-08-16 23:00:00`; `180000` seconds.
- `2026-08-21 21:00:00` -> `2026-08-23 23:00:00`; `180000` seconds.

### H4 provider gaps (74)

- `2025-05-02 16:00:00` -> `2025-05-05 00:00:00`; `201600` seconds.
- `2025-05-09 16:00:00` -> `2025-05-12 00:00:00`; `201600` seconds.
- `2025-05-16 16:00:00` -> `2025-05-19 00:00:00`; `201600` seconds.
- `2025-05-23 16:00:00` -> `2025-05-26 00:00:00`; `201600` seconds.
- `2025-05-30 16:00:00` -> `2025-06-02 00:00:00`; `201600` seconds.
- `2025-06-06 16:00:00` -> `2025-06-09 00:00:00`; `201600` seconds.
- `2025-06-13 16:00:00` -> `2025-06-16 00:00:00`; `201600` seconds.
- `2025-06-20 16:00:00` -> `2025-06-23 00:00:00`; `201600` seconds.
- `2025-06-27 16:00:00` -> `2025-06-30 00:00:00`; `201600` seconds.
- `2025-07-04 16:00:00` -> `2025-07-07 00:00:00`; `201600` seconds.
- `2025-07-11 16:00:00` -> `2025-07-14 00:00:00`; `201600` seconds.
- `2025-07-18 16:00:00` -> `2025-07-21 00:00:00`; `201600` seconds.
- `2025-07-25 16:00:00` -> `2025-07-28 00:00:00`; `201600` seconds.
- `2025-08-01 16:00:00` -> `2025-08-04 00:00:00`; `201600` seconds.
- `2025-08-08 16:00:00` -> `2025-08-11 00:00:00`; `201600` seconds.
- `2025-08-15 16:00:00` -> `2025-08-18 00:00:00`; `201600` seconds.
- `2025-08-22 16:00:00` -> `2025-08-25 00:00:00`; `201600` seconds.
- `2025-08-29 16:00:00` -> `2025-09-01 00:00:00`; `201600` seconds.
- `2025-09-05 16:00:00` -> `2025-09-08 00:00:00`; `201600` seconds.
- `2025-09-12 16:00:00` -> `2025-09-15 00:00:00`; `201600` seconds.
- `2025-09-15 16:00:00` -> `2025-09-16 04:00:00`; `43200` seconds.
- `2025-09-19 16:00:00` -> `2025-09-22 00:00:00`; `201600` seconds.
- `2025-09-26 16:00:00` -> `2025-09-29 00:00:00`; `201600` seconds.
- `2025-10-03 16:00:00` -> `2025-10-06 00:00:00`; `201600` seconds.
- `2025-10-10 16:00:00` -> `2025-10-13 00:00:00`; `201600` seconds.
- `2025-10-17 16:00:00` -> `2025-10-20 00:00:00`; `201600` seconds.
- `2025-10-24 16:00:00` -> `2025-10-27 00:00:00`; `201600` seconds.
- `2025-10-31 16:00:00` -> `2025-11-03 00:00:00`; `201600` seconds.
- `2025-11-07 16:00:00` -> `2025-11-10 00:00:00`; `201600` seconds.
- `2025-11-14 16:00:00` -> `2025-11-17 00:00:00`; `201600` seconds.
- `2025-11-21 16:00:00` -> `2025-11-24 00:00:00`; `201600` seconds.
- `2025-11-28 16:00:00` -> `2025-12-01 00:00:00`; `201600` seconds.
- `2025-12-05 16:00:00` -> `2025-12-08 00:00:00`; `201600` seconds.
- `2025-12-12 16:00:00` -> `2025-12-15 00:00:00`; `201600` seconds.
- `2025-12-19 16:00:00` -> `2025-12-22 00:00:00`; `201600` seconds.
- `2025-12-25 04:00:00` -> `2025-12-26 00:00:00`; `72000` seconds.
- `2025-12-26 16:00:00` -> `2025-12-29 00:00:00`; `201600` seconds.
- `2025-12-31 20:00:00` -> `2026-01-02 00:00:00`; `100800` seconds.
- `2026-01-02 16:00:00` -> `2026-01-05 00:00:00`; `201600` seconds.
- `2026-01-09 16:00:00` -> `2026-01-12 00:00:00`; `201600` seconds.
- `2026-01-16 16:00:00` -> `2026-01-19 00:00:00`; `201600` seconds.
- `2026-01-23 16:00:00` -> `2026-01-26 00:00:00`; `201600` seconds.
- `2026-01-30 12:00:00` -> `2026-02-02 20:00:00`; `288000` seconds.
- `2026-02-06 16:00:00` -> `2026-02-09 00:00:00`; `201600` seconds.
- `2026-02-13 16:00:00` -> `2026-02-16 00:00:00`; `201600` seconds.
- `2026-02-20 16:00:00` -> `2026-02-23 00:00:00`; `201600` seconds.
- `2026-02-27 16:00:00` -> `2026-03-02 00:00:00`; `201600` seconds.
- `2026-03-06 16:00:00` -> `2026-03-09 00:00:00`; `201600` seconds.
- `2026-03-13 16:00:00` -> `2026-03-16 00:00:00`; `201600` seconds.
- `2026-03-20 16:00:00` -> `2026-03-23 00:00:00`; `201600` seconds.
- `2026-03-27 16:00:00` -> `2026-03-30 00:00:00`; `201600` seconds.
- `2026-04-03 16:00:00` -> `2026-04-06 00:00:00`; `201600` seconds.
- `2026-04-10 16:00:00` -> `2026-04-13 00:00:00`; `201600` seconds.
- `2026-04-17 16:00:00` -> `2026-04-20 00:00:00`; `201600` seconds.
- `2026-04-20 00:00:00` -> `2026-04-20 12:00:00`; `43200` seconds.
- `2026-04-24 16:00:00` -> `2026-04-27 00:00:00`; `201600` seconds.
- `2026-05-01 16:00:00` -> `2026-05-04 04:00:00`; `216000` seconds.
- `2026-05-08 16:00:00` -> `2026-05-11 00:00:00`; `201600` seconds.
- `2026-05-15 16:00:00` -> `2026-05-18 00:00:00`; `201600` seconds.
- `2026-05-22 16:00:00` -> `2026-05-25 00:00:00`; `201600` seconds.
- `2026-05-29 16:00:00` -> `2026-06-01 00:00:00`; `201600` seconds.
- `2026-06-05 16:00:00` -> `2026-06-08 00:00:00`; `201600` seconds.
- `2026-06-12 16:00:00` -> `2026-06-15 00:00:00`; `201600` seconds.
- `2026-06-19 16:00:00` -> `2026-06-22 00:00:00`; `201600` seconds.
- `2026-06-26 16:00:00` -> `2026-06-29 00:00:00`; `201600` seconds.
- `2026-07-03 16:00:00` -> `2026-07-06 00:00:00`; `201600` seconds.
- `2026-07-10 16:00:00` -> `2026-07-13 00:00:00`; `201600` seconds.
- `2026-07-17 00:00:00` -> `2026-07-17 12:00:00`; `43200` seconds.
- `2026-07-17 16:00:00` -> `2026-07-20 00:00:00`; `201600` seconds.
- `2026-07-24 16:00:00` -> `2026-07-27 00:00:00`; `201600` seconds.
- `2026-07-31 16:00:00` -> `2026-08-03 00:00:00`; `201600` seconds.
- `2026-08-07 16:00:00` -> `2026-08-10 00:00:00`; `201600` seconds.
- `2026-08-14 16:00:00` -> `2026-08-17 00:00:00`; `201600` seconds.
- `2026-08-21 16:00:00` -> `2026-08-24 00:00:00`; `201600` seconds.

### D1 provider gaps (5)

The runtime validator proved that five D1 gaps were not covered by sanitization provenance. The failed evidence persisted only the aggregate count and discarded the per-gap stage details, while the CSV alone contains 56 non-weekend gaps (51 sanitized plus 5 provider gaps). Therefore the exact five cannot be selected from the 56 without a prohibited second acquisition. Four intervals were already independently established as preexisting provider gaps before this retry:

- `2019-05-21 00:00:00` -> `2019-05-23 00:00:00`; `172800` seconds.
- `2024-12-31 00:00:00` -> `2025-01-02 00:00:00`; `172800` seconds.
- `2025-12-24 00:00:00` -> `2025-12-26 00:00:00`; `172800` seconds.
- `2025-12-31 00:00:00` -> `2026-01-02 00:00:00`; `172800` seconds.

The fifth interval is intentionally not guessed. This missing failed-evidence detail does not weaken the gate: all five remained blocking.

## Indicator Contract Verification

- H1 artifact: 2000 rows; all independent checks passed for `RSI_14`, `MACD`, `MACD_signal`, `MACD_hist`, `ATR_14`, `EMA20`, `EMA50`, `EMA200`, `BB_upper`, `BB_lower`, `returns`, and `volatility_24h`.
- H4 artifact: 2000 rows; the same 12 indicator checks passed.
- D1 artifact: 2000 rows; the same 12 indicator checks passed.
- Previous RSI/MACD/ATR/hidden-EWM mismatch reproduced: no.
- This retry did not expose an indicator or OHLC code regression.

## Qualification Decision

`QUALIFICATION BLOCKED — UNEXPLAINED PROVIDER GAPS`

The non-blocking zero-volume warnings did not cause the rejection. The blocking causes were 17 H1 provider gaps, 74 H4 provider gaps, and 5 D1 provider gaps. The fail-closed behavior is correct under the approved contract.

## Canonical Dataset Creation

- H1: `PENDING` — not executed after qualification failure.
- H4: `PENDING` — not executed after qualification failure.
- D1: `PENDING` — not executed after qualification failure.
- The EURUSD dataset registry has zero rows.

## Dataset Registry Readiness

- H1: `PENDING`.
- H4: `PENDING`.
- D1: `PENDING`.
- `registry_entry_readiness()` was not applicable because no canonical registry rows were created.

## Cross-Timeframe Validation

- The qualification command returned blocking `FAIL`: `Missing validated timeframe frames: ['D1', 'H1', 'H4']`.
- No post-qualification canonical cross-timeframe validation was executed.
- Latest-close, scale-ratio, overlap-row, and relative-error evidence: `PENDING`.

## Initial Training

- `PENDING` — not executed because qualification failed.
- `use_wfv=True`, `force=False` were therefore not invoked.

## Quality Gate

- `PENDING` — not executed.

## WFV Statistical Evidence

- `PENDING` — no folds, TP/FP/signals, aggregate precision, pooled precision, or evidence sufficiency were produced.

## Calibration

- `PENDING` — not executed.

## Validation

- `PENDING` — not executed.

## Initial Model Promotion

- `PENDING` — no candidate model or production alias was created.
- Productive alias remains absent.
- Quarantined legacy model remains intact with its historical SHA256.
- Model audit: `PENDING` because training/promotion did not run.

## EURUSD Final State

- Lifecycle status: `candidate`.
- Qualification evidence path/SHA on the lifecycle row: absent, as expected for a failed qualification.
- Dataset registry rows: none.
- Productive model alias: absent.
- Legacy quarantined artifact: intact.

## Remaining Blockers

- H1: 17 unexplained provider gaps.
- H4: 74 unexplained provider gaps.
- D1: 5 unexplained provider gaps.
- Failed qualification evidence currently omits full acquisition metadata/stage details, preventing post-process recovery of the exact D1 five-versus-51 mapping. This is a reporting limitation only; the gate remained fail-closed.

## Viability Decision

`QUALIFICATION BLOCKED — UNEXPLAINED PROVIDER GAPS`

EURUSD is not ready for canonical dataset creation, initial training, model promotion, or activation testing.

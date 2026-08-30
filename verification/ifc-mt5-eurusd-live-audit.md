# IFC Markets MT5 EURUSD Live Read-Only Audit

## Baseline

- Repository base: `fix/mt5-production-data-contract` at `92439e6005b7082dfbc8ac694875257496c50f39`.
- Audit branch: `verify/ifc-mt5-eurusd-live-audit`.
- Interpreter: Python 3.12.6 from `.venv\Scripts\python.exe`.
- Scope: live, read-only EURUSD data audit. No qualification, canonical write, database mutation, training, WFV, activation, scheduler, Oracle access, or trading operation was executed.
- SessionAuthority remained `UNKNOWN` throughout.

## Terminal Connectivity

The direct five-row H1 probe passed before the full audit.

- MetaTrader5 package available: yes
- terminal initialized: yes
- account connected: yes (connectivity boolean only; no account identifier or financial field was collected)
- server: `IFCMarkets-Demo`
- company: `IFCMarkets. Corp.`
- MetaTrader5 package version: `5.0.6147`
- terminal build: `6140`
- EURUSD available: yes, demonstrated by the successful exact-symbol fetch
- probe rows: 5
- last result: PASS
- trade mode: `0` (safe provider metadata)

## Security

Only the hardened provider's read-only initialization, terminal/account connectivity checks, symbol lookup/selection, rate-copy, and shutdown path was exercised. No order, position, trade-request, pending-order, or account-mutation API was called. The audit output and this report contain no login, account number, balance, equity, password, credential, candle CSV, database, or model artifact.

## H1 Acquisition

- Direct provider: `MT5Provider` (no DataRouter/OANDA/Yahoo)
- rows: 2001
- first timestamp: `2026-05-04T05:00:00`
- last timestamp: `2026-08-28T21:00:00`
- monotonically increasing: yes
- duplicate timestamps: 0
- future timestamps: 0
- current/open candles: 0
- invalid accepted OHLC rows: 0
- negative-volume rows: 0

Safe acquisition metadata:

- schema_version: 1
- provider: `MT5`
- symbol/timeframe: `EURUSD/H1`
- requested_bars: 2001
- raw_closed_rows: 2011
- invalid_rows_dropped: 0
- valid_rows_before_tail: 2011
- returned_rows: 2001
- dropped_rows count/reasons: 0 / none
- native_timeframe: true
- terminal_connected: true
- server/company: `IFCMarkets-Demo` / `IFCMarkets. Corp.`
- trade_mode: `0`
- mt5_package_version / terminal_build: `5.0.6147` / `6140`
- symbol_external: `EURUSD`
- headroom_requested: 10
- volume_provenance: `MT5_TICK_VOLUME`

## H1 Gap Analysis

Contract view: 16 total gap events; `WEEKEND=0`, `SANITIZED_PROVIDER_ROW=0`, `MARKET_SESSION_CLOSED=0`, `PROVIDER_GAP=16`, `INVALID_GAP=0`. With no authorized session source, all 16 remain blocking `PROVIDER_GAP` in ASTRA.

Diagnostic-only view: all 16 share the same repeated Friday 21:00 UTC → Monday 00:00 UTC shape and are `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`. IntrawEEK residuals: 0. This diagnostic label does not change the contract classification or authorize a market closure.

All exact contract `PROVIDER_GAP` observations:

1. previous: `2026-05-08T21:00:00`; current: `2026-05-11T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-05-08T22:00:00`
   - `2026-05-08T23:00:00`
   - `2026-05-09T00:00:00`
   - `2026-05-09T01:00:00`
   - `2026-05-09T02:00:00`
   - `2026-05-09T03:00:00`
   - `2026-05-09T04:00:00`
   - `2026-05-09T05:00:00`
   - `2026-05-09T06:00:00`
   - `2026-05-09T07:00:00`
   - `2026-05-09T08:00:00`
   - `2026-05-09T09:00:00`
   - `2026-05-09T10:00:00`
   - `2026-05-09T11:00:00`
   - `2026-05-09T12:00:00`
   - `2026-05-09T13:00:00`
   - `2026-05-09T14:00:00`
   - `2026-05-09T15:00:00`
   - `2026-05-09T16:00:00`
   - `2026-05-09T17:00:00`
   - `2026-05-09T18:00:00`
   - `2026-05-09T19:00:00`
   - `2026-05-09T20:00:00`
   - `2026-05-09T21:00:00`
   - `2026-05-09T22:00:00`
   - `2026-05-09T23:00:00`
   - `2026-05-10T00:00:00`
   - `2026-05-10T01:00:00`
   - `2026-05-10T02:00:00`
   - `2026-05-10T03:00:00`
   - `2026-05-10T04:00:00`
   - `2026-05-10T05:00:00`
   - `2026-05-10T06:00:00`
   - `2026-05-10T07:00:00`
   - `2026-05-10T08:00:00`
   - `2026-05-10T09:00:00`
   - `2026-05-10T10:00:00`
   - `2026-05-10T11:00:00`
   - `2026-05-10T12:00:00`
   - `2026-05-10T13:00:00`
   - `2026-05-10T14:00:00`
   - `2026-05-10T15:00:00`
   - `2026-05-10T16:00:00`
   - `2026-05-10T17:00:00`
   - `2026-05-10T18:00:00`
   - `2026-05-10T19:00:00`
   - `2026-05-10T20:00:00`
   - `2026-05-10T21:00:00`
   - `2026-05-10T22:00:00`
   - `2026-05-10T23:00:00`

2. previous: `2026-05-15T21:00:00`; current: `2026-05-18T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-05-15T22:00:00`
   - `2026-05-15T23:00:00`
   - `2026-05-16T00:00:00`
   - `2026-05-16T01:00:00`
   - `2026-05-16T02:00:00`
   - `2026-05-16T03:00:00`
   - `2026-05-16T04:00:00`
   - `2026-05-16T05:00:00`
   - `2026-05-16T06:00:00`
   - `2026-05-16T07:00:00`
   - `2026-05-16T08:00:00`
   - `2026-05-16T09:00:00`
   - `2026-05-16T10:00:00`
   - `2026-05-16T11:00:00`
   - `2026-05-16T12:00:00`
   - `2026-05-16T13:00:00`
   - `2026-05-16T14:00:00`
   - `2026-05-16T15:00:00`
   - `2026-05-16T16:00:00`
   - `2026-05-16T17:00:00`
   - `2026-05-16T18:00:00`
   - `2026-05-16T19:00:00`
   - `2026-05-16T20:00:00`
   - `2026-05-16T21:00:00`
   - `2026-05-16T22:00:00`
   - `2026-05-16T23:00:00`
   - `2026-05-17T00:00:00`
   - `2026-05-17T01:00:00`
   - `2026-05-17T02:00:00`
   - `2026-05-17T03:00:00`
   - `2026-05-17T04:00:00`
   - `2026-05-17T05:00:00`
   - `2026-05-17T06:00:00`
   - `2026-05-17T07:00:00`
   - `2026-05-17T08:00:00`
   - `2026-05-17T09:00:00`
   - `2026-05-17T10:00:00`
   - `2026-05-17T11:00:00`
   - `2026-05-17T12:00:00`
   - `2026-05-17T13:00:00`
   - `2026-05-17T14:00:00`
   - `2026-05-17T15:00:00`
   - `2026-05-17T16:00:00`
   - `2026-05-17T17:00:00`
   - `2026-05-17T18:00:00`
   - `2026-05-17T19:00:00`
   - `2026-05-17T20:00:00`
   - `2026-05-17T21:00:00`
   - `2026-05-17T22:00:00`
   - `2026-05-17T23:00:00`

3. previous: `2026-05-22T21:00:00`; current: `2026-05-25T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-05-22T22:00:00`
   - `2026-05-22T23:00:00`
   - `2026-05-23T00:00:00`
   - `2026-05-23T01:00:00`
   - `2026-05-23T02:00:00`
   - `2026-05-23T03:00:00`
   - `2026-05-23T04:00:00`
   - `2026-05-23T05:00:00`
   - `2026-05-23T06:00:00`
   - `2026-05-23T07:00:00`
   - `2026-05-23T08:00:00`
   - `2026-05-23T09:00:00`
   - `2026-05-23T10:00:00`
   - `2026-05-23T11:00:00`
   - `2026-05-23T12:00:00`
   - `2026-05-23T13:00:00`
   - `2026-05-23T14:00:00`
   - `2026-05-23T15:00:00`
   - `2026-05-23T16:00:00`
   - `2026-05-23T17:00:00`
   - `2026-05-23T18:00:00`
   - `2026-05-23T19:00:00`
   - `2026-05-23T20:00:00`
   - `2026-05-23T21:00:00`
   - `2026-05-23T22:00:00`
   - `2026-05-23T23:00:00`
   - `2026-05-24T00:00:00`
   - `2026-05-24T01:00:00`
   - `2026-05-24T02:00:00`
   - `2026-05-24T03:00:00`
   - `2026-05-24T04:00:00`
   - `2026-05-24T05:00:00`
   - `2026-05-24T06:00:00`
   - `2026-05-24T07:00:00`
   - `2026-05-24T08:00:00`
   - `2026-05-24T09:00:00`
   - `2026-05-24T10:00:00`
   - `2026-05-24T11:00:00`
   - `2026-05-24T12:00:00`
   - `2026-05-24T13:00:00`
   - `2026-05-24T14:00:00`
   - `2026-05-24T15:00:00`
   - `2026-05-24T16:00:00`
   - `2026-05-24T17:00:00`
   - `2026-05-24T18:00:00`
   - `2026-05-24T19:00:00`
   - `2026-05-24T20:00:00`
   - `2026-05-24T21:00:00`
   - `2026-05-24T22:00:00`
   - `2026-05-24T23:00:00`

4. previous: `2026-05-29T21:00:00`; current: `2026-06-01T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-05-29T22:00:00`
   - `2026-05-29T23:00:00`
   - `2026-05-30T00:00:00`
   - `2026-05-30T01:00:00`
   - `2026-05-30T02:00:00`
   - `2026-05-30T03:00:00`
   - `2026-05-30T04:00:00`
   - `2026-05-30T05:00:00`
   - `2026-05-30T06:00:00`
   - `2026-05-30T07:00:00`
   - `2026-05-30T08:00:00`
   - `2026-05-30T09:00:00`
   - `2026-05-30T10:00:00`
   - `2026-05-30T11:00:00`
   - `2026-05-30T12:00:00`
   - `2026-05-30T13:00:00`
   - `2026-05-30T14:00:00`
   - `2026-05-30T15:00:00`
   - `2026-05-30T16:00:00`
   - `2026-05-30T17:00:00`
   - `2026-05-30T18:00:00`
   - `2026-05-30T19:00:00`
   - `2026-05-30T20:00:00`
   - `2026-05-30T21:00:00`
   - `2026-05-30T22:00:00`
   - `2026-05-30T23:00:00`
   - `2026-05-31T00:00:00`
   - `2026-05-31T01:00:00`
   - `2026-05-31T02:00:00`
   - `2026-05-31T03:00:00`
   - `2026-05-31T04:00:00`
   - `2026-05-31T05:00:00`
   - `2026-05-31T06:00:00`
   - `2026-05-31T07:00:00`
   - `2026-05-31T08:00:00`
   - `2026-05-31T09:00:00`
   - `2026-05-31T10:00:00`
   - `2026-05-31T11:00:00`
   - `2026-05-31T12:00:00`
   - `2026-05-31T13:00:00`
   - `2026-05-31T14:00:00`
   - `2026-05-31T15:00:00`
   - `2026-05-31T16:00:00`
   - `2026-05-31T17:00:00`
   - `2026-05-31T18:00:00`
   - `2026-05-31T19:00:00`
   - `2026-05-31T20:00:00`
   - `2026-05-31T21:00:00`
   - `2026-05-31T22:00:00`
   - `2026-05-31T23:00:00`

5. previous: `2026-06-05T21:00:00`; current: `2026-06-08T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-06-05T22:00:00`
   - `2026-06-05T23:00:00`
   - `2026-06-06T00:00:00`
   - `2026-06-06T01:00:00`
   - `2026-06-06T02:00:00`
   - `2026-06-06T03:00:00`
   - `2026-06-06T04:00:00`
   - `2026-06-06T05:00:00`
   - `2026-06-06T06:00:00`
   - `2026-06-06T07:00:00`
   - `2026-06-06T08:00:00`
   - `2026-06-06T09:00:00`
   - `2026-06-06T10:00:00`
   - `2026-06-06T11:00:00`
   - `2026-06-06T12:00:00`
   - `2026-06-06T13:00:00`
   - `2026-06-06T14:00:00`
   - `2026-06-06T15:00:00`
   - `2026-06-06T16:00:00`
   - `2026-06-06T17:00:00`
   - `2026-06-06T18:00:00`
   - `2026-06-06T19:00:00`
   - `2026-06-06T20:00:00`
   - `2026-06-06T21:00:00`
   - `2026-06-06T22:00:00`
   - `2026-06-06T23:00:00`
   - `2026-06-07T00:00:00`
   - `2026-06-07T01:00:00`
   - `2026-06-07T02:00:00`
   - `2026-06-07T03:00:00`
   - `2026-06-07T04:00:00`
   - `2026-06-07T05:00:00`
   - `2026-06-07T06:00:00`
   - `2026-06-07T07:00:00`
   - `2026-06-07T08:00:00`
   - `2026-06-07T09:00:00`
   - `2026-06-07T10:00:00`
   - `2026-06-07T11:00:00`
   - `2026-06-07T12:00:00`
   - `2026-06-07T13:00:00`
   - `2026-06-07T14:00:00`
   - `2026-06-07T15:00:00`
   - `2026-06-07T16:00:00`
   - `2026-06-07T17:00:00`
   - `2026-06-07T18:00:00`
   - `2026-06-07T19:00:00`
   - `2026-06-07T20:00:00`
   - `2026-06-07T21:00:00`
   - `2026-06-07T22:00:00`
   - `2026-06-07T23:00:00`

6. previous: `2026-06-12T21:00:00`; current: `2026-06-15T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-06-12T22:00:00`
   - `2026-06-12T23:00:00`
   - `2026-06-13T00:00:00`
   - `2026-06-13T01:00:00`
   - `2026-06-13T02:00:00`
   - `2026-06-13T03:00:00`
   - `2026-06-13T04:00:00`
   - `2026-06-13T05:00:00`
   - `2026-06-13T06:00:00`
   - `2026-06-13T07:00:00`
   - `2026-06-13T08:00:00`
   - `2026-06-13T09:00:00`
   - `2026-06-13T10:00:00`
   - `2026-06-13T11:00:00`
   - `2026-06-13T12:00:00`
   - `2026-06-13T13:00:00`
   - `2026-06-13T14:00:00`
   - `2026-06-13T15:00:00`
   - `2026-06-13T16:00:00`
   - `2026-06-13T17:00:00`
   - `2026-06-13T18:00:00`
   - `2026-06-13T19:00:00`
   - `2026-06-13T20:00:00`
   - `2026-06-13T21:00:00`
   - `2026-06-13T22:00:00`
   - `2026-06-13T23:00:00`
   - `2026-06-14T00:00:00`
   - `2026-06-14T01:00:00`
   - `2026-06-14T02:00:00`
   - `2026-06-14T03:00:00`
   - `2026-06-14T04:00:00`
   - `2026-06-14T05:00:00`
   - `2026-06-14T06:00:00`
   - `2026-06-14T07:00:00`
   - `2026-06-14T08:00:00`
   - `2026-06-14T09:00:00`
   - `2026-06-14T10:00:00`
   - `2026-06-14T11:00:00`
   - `2026-06-14T12:00:00`
   - `2026-06-14T13:00:00`
   - `2026-06-14T14:00:00`
   - `2026-06-14T15:00:00`
   - `2026-06-14T16:00:00`
   - `2026-06-14T17:00:00`
   - `2026-06-14T18:00:00`
   - `2026-06-14T19:00:00`
   - `2026-06-14T20:00:00`
   - `2026-06-14T21:00:00`
   - `2026-06-14T22:00:00`
   - `2026-06-14T23:00:00`

7. previous: `2026-06-19T21:00:00`; current: `2026-06-22T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-06-19T22:00:00`
   - `2026-06-19T23:00:00`
   - `2026-06-20T00:00:00`
   - `2026-06-20T01:00:00`
   - `2026-06-20T02:00:00`
   - `2026-06-20T03:00:00`
   - `2026-06-20T04:00:00`
   - `2026-06-20T05:00:00`
   - `2026-06-20T06:00:00`
   - `2026-06-20T07:00:00`
   - `2026-06-20T08:00:00`
   - `2026-06-20T09:00:00`
   - `2026-06-20T10:00:00`
   - `2026-06-20T11:00:00`
   - `2026-06-20T12:00:00`
   - `2026-06-20T13:00:00`
   - `2026-06-20T14:00:00`
   - `2026-06-20T15:00:00`
   - `2026-06-20T16:00:00`
   - `2026-06-20T17:00:00`
   - `2026-06-20T18:00:00`
   - `2026-06-20T19:00:00`
   - `2026-06-20T20:00:00`
   - `2026-06-20T21:00:00`
   - `2026-06-20T22:00:00`
   - `2026-06-20T23:00:00`
   - `2026-06-21T00:00:00`
   - `2026-06-21T01:00:00`
   - `2026-06-21T02:00:00`
   - `2026-06-21T03:00:00`
   - `2026-06-21T04:00:00`
   - `2026-06-21T05:00:00`
   - `2026-06-21T06:00:00`
   - `2026-06-21T07:00:00`
   - `2026-06-21T08:00:00`
   - `2026-06-21T09:00:00`
   - `2026-06-21T10:00:00`
   - `2026-06-21T11:00:00`
   - `2026-06-21T12:00:00`
   - `2026-06-21T13:00:00`
   - `2026-06-21T14:00:00`
   - `2026-06-21T15:00:00`
   - `2026-06-21T16:00:00`
   - `2026-06-21T17:00:00`
   - `2026-06-21T18:00:00`
   - `2026-06-21T19:00:00`
   - `2026-06-21T20:00:00`
   - `2026-06-21T21:00:00`
   - `2026-06-21T22:00:00`
   - `2026-06-21T23:00:00`

8. previous: `2026-06-26T21:00:00`; current: `2026-06-29T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-06-26T22:00:00`
   - `2026-06-26T23:00:00`
   - `2026-06-27T00:00:00`
   - `2026-06-27T01:00:00`
   - `2026-06-27T02:00:00`
   - `2026-06-27T03:00:00`
   - `2026-06-27T04:00:00`
   - `2026-06-27T05:00:00`
   - `2026-06-27T06:00:00`
   - `2026-06-27T07:00:00`
   - `2026-06-27T08:00:00`
   - `2026-06-27T09:00:00`
   - `2026-06-27T10:00:00`
   - `2026-06-27T11:00:00`
   - `2026-06-27T12:00:00`
   - `2026-06-27T13:00:00`
   - `2026-06-27T14:00:00`
   - `2026-06-27T15:00:00`
   - `2026-06-27T16:00:00`
   - `2026-06-27T17:00:00`
   - `2026-06-27T18:00:00`
   - `2026-06-27T19:00:00`
   - `2026-06-27T20:00:00`
   - `2026-06-27T21:00:00`
   - `2026-06-27T22:00:00`
   - `2026-06-27T23:00:00`
   - `2026-06-28T00:00:00`
   - `2026-06-28T01:00:00`
   - `2026-06-28T02:00:00`
   - `2026-06-28T03:00:00`
   - `2026-06-28T04:00:00`
   - `2026-06-28T05:00:00`
   - `2026-06-28T06:00:00`
   - `2026-06-28T07:00:00`
   - `2026-06-28T08:00:00`
   - `2026-06-28T09:00:00`
   - `2026-06-28T10:00:00`
   - `2026-06-28T11:00:00`
   - `2026-06-28T12:00:00`
   - `2026-06-28T13:00:00`
   - `2026-06-28T14:00:00`
   - `2026-06-28T15:00:00`
   - `2026-06-28T16:00:00`
   - `2026-06-28T17:00:00`
   - `2026-06-28T18:00:00`
   - `2026-06-28T19:00:00`
   - `2026-06-28T20:00:00`
   - `2026-06-28T21:00:00`
   - `2026-06-28T22:00:00`
   - `2026-06-28T23:00:00`

9. previous: `2026-07-03T21:00:00`; current: `2026-07-06T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-07-03T22:00:00`
   - `2026-07-03T23:00:00`
   - `2026-07-04T00:00:00`
   - `2026-07-04T01:00:00`
   - `2026-07-04T02:00:00`
   - `2026-07-04T03:00:00`
   - `2026-07-04T04:00:00`
   - `2026-07-04T05:00:00`
   - `2026-07-04T06:00:00`
   - `2026-07-04T07:00:00`
   - `2026-07-04T08:00:00`
   - `2026-07-04T09:00:00`
   - `2026-07-04T10:00:00`
   - `2026-07-04T11:00:00`
   - `2026-07-04T12:00:00`
   - `2026-07-04T13:00:00`
   - `2026-07-04T14:00:00`
   - `2026-07-04T15:00:00`
   - `2026-07-04T16:00:00`
   - `2026-07-04T17:00:00`
   - `2026-07-04T18:00:00`
   - `2026-07-04T19:00:00`
   - `2026-07-04T20:00:00`
   - `2026-07-04T21:00:00`
   - `2026-07-04T22:00:00`
   - `2026-07-04T23:00:00`
   - `2026-07-05T00:00:00`
   - `2026-07-05T01:00:00`
   - `2026-07-05T02:00:00`
   - `2026-07-05T03:00:00`
   - `2026-07-05T04:00:00`
   - `2026-07-05T05:00:00`
   - `2026-07-05T06:00:00`
   - `2026-07-05T07:00:00`
   - `2026-07-05T08:00:00`
   - `2026-07-05T09:00:00`
   - `2026-07-05T10:00:00`
   - `2026-07-05T11:00:00`
   - `2026-07-05T12:00:00`
   - `2026-07-05T13:00:00`
   - `2026-07-05T14:00:00`
   - `2026-07-05T15:00:00`
   - `2026-07-05T16:00:00`
   - `2026-07-05T17:00:00`
   - `2026-07-05T18:00:00`
   - `2026-07-05T19:00:00`
   - `2026-07-05T20:00:00`
   - `2026-07-05T21:00:00`
   - `2026-07-05T22:00:00`
   - `2026-07-05T23:00:00`

10. previous: `2026-07-10T21:00:00`; current: `2026-07-13T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-07-10T22:00:00`
   - `2026-07-10T23:00:00`
   - `2026-07-11T00:00:00`
   - `2026-07-11T01:00:00`
   - `2026-07-11T02:00:00`
   - `2026-07-11T03:00:00`
   - `2026-07-11T04:00:00`
   - `2026-07-11T05:00:00`
   - `2026-07-11T06:00:00`
   - `2026-07-11T07:00:00`
   - `2026-07-11T08:00:00`
   - `2026-07-11T09:00:00`
   - `2026-07-11T10:00:00`
   - `2026-07-11T11:00:00`
   - `2026-07-11T12:00:00`
   - `2026-07-11T13:00:00`
   - `2026-07-11T14:00:00`
   - `2026-07-11T15:00:00`
   - `2026-07-11T16:00:00`
   - `2026-07-11T17:00:00`
   - `2026-07-11T18:00:00`
   - `2026-07-11T19:00:00`
   - `2026-07-11T20:00:00`
   - `2026-07-11T21:00:00`
   - `2026-07-11T22:00:00`
   - `2026-07-11T23:00:00`
   - `2026-07-12T00:00:00`
   - `2026-07-12T01:00:00`
   - `2026-07-12T02:00:00`
   - `2026-07-12T03:00:00`
   - `2026-07-12T04:00:00`
   - `2026-07-12T05:00:00`
   - `2026-07-12T06:00:00`
   - `2026-07-12T07:00:00`
   - `2026-07-12T08:00:00`
   - `2026-07-12T09:00:00`
   - `2026-07-12T10:00:00`
   - `2026-07-12T11:00:00`
   - `2026-07-12T12:00:00`
   - `2026-07-12T13:00:00`
   - `2026-07-12T14:00:00`
   - `2026-07-12T15:00:00`
   - `2026-07-12T16:00:00`
   - `2026-07-12T17:00:00`
   - `2026-07-12T18:00:00`
   - `2026-07-12T19:00:00`
   - `2026-07-12T20:00:00`
   - `2026-07-12T21:00:00`
   - `2026-07-12T22:00:00`
   - `2026-07-12T23:00:00`

11. previous: `2026-07-17T21:00:00`; current: `2026-07-20T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-07-17T22:00:00`
   - `2026-07-17T23:00:00`
   - `2026-07-18T00:00:00`
   - `2026-07-18T01:00:00`
   - `2026-07-18T02:00:00`
   - `2026-07-18T03:00:00`
   - `2026-07-18T04:00:00`
   - `2026-07-18T05:00:00`
   - `2026-07-18T06:00:00`
   - `2026-07-18T07:00:00`
   - `2026-07-18T08:00:00`
   - `2026-07-18T09:00:00`
   - `2026-07-18T10:00:00`
   - `2026-07-18T11:00:00`
   - `2026-07-18T12:00:00`
   - `2026-07-18T13:00:00`
   - `2026-07-18T14:00:00`
   - `2026-07-18T15:00:00`
   - `2026-07-18T16:00:00`
   - `2026-07-18T17:00:00`
   - `2026-07-18T18:00:00`
   - `2026-07-18T19:00:00`
   - `2026-07-18T20:00:00`
   - `2026-07-18T21:00:00`
   - `2026-07-18T22:00:00`
   - `2026-07-18T23:00:00`
   - `2026-07-19T00:00:00`
   - `2026-07-19T01:00:00`
   - `2026-07-19T02:00:00`
   - `2026-07-19T03:00:00`
   - `2026-07-19T04:00:00`
   - `2026-07-19T05:00:00`
   - `2026-07-19T06:00:00`
   - `2026-07-19T07:00:00`
   - `2026-07-19T08:00:00`
   - `2026-07-19T09:00:00`
   - `2026-07-19T10:00:00`
   - `2026-07-19T11:00:00`
   - `2026-07-19T12:00:00`
   - `2026-07-19T13:00:00`
   - `2026-07-19T14:00:00`
   - `2026-07-19T15:00:00`
   - `2026-07-19T16:00:00`
   - `2026-07-19T17:00:00`
   - `2026-07-19T18:00:00`
   - `2026-07-19T19:00:00`
   - `2026-07-19T20:00:00`
   - `2026-07-19T21:00:00`
   - `2026-07-19T22:00:00`
   - `2026-07-19T23:00:00`

12. previous: `2026-07-24T21:00:00`; current: `2026-07-27T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-07-24T22:00:00`
   - `2026-07-24T23:00:00`
   - `2026-07-25T00:00:00`
   - `2026-07-25T01:00:00`
   - `2026-07-25T02:00:00`
   - `2026-07-25T03:00:00`
   - `2026-07-25T04:00:00`
   - `2026-07-25T05:00:00`
   - `2026-07-25T06:00:00`
   - `2026-07-25T07:00:00`
   - `2026-07-25T08:00:00`
   - `2026-07-25T09:00:00`
   - `2026-07-25T10:00:00`
   - `2026-07-25T11:00:00`
   - `2026-07-25T12:00:00`
   - `2026-07-25T13:00:00`
   - `2026-07-25T14:00:00`
   - `2026-07-25T15:00:00`
   - `2026-07-25T16:00:00`
   - `2026-07-25T17:00:00`
   - `2026-07-25T18:00:00`
   - `2026-07-25T19:00:00`
   - `2026-07-25T20:00:00`
   - `2026-07-25T21:00:00`
   - `2026-07-25T22:00:00`
   - `2026-07-25T23:00:00`
   - `2026-07-26T00:00:00`
   - `2026-07-26T01:00:00`
   - `2026-07-26T02:00:00`
   - `2026-07-26T03:00:00`
   - `2026-07-26T04:00:00`
   - `2026-07-26T05:00:00`
   - `2026-07-26T06:00:00`
   - `2026-07-26T07:00:00`
   - `2026-07-26T08:00:00`
   - `2026-07-26T09:00:00`
   - `2026-07-26T10:00:00`
   - `2026-07-26T11:00:00`
   - `2026-07-26T12:00:00`
   - `2026-07-26T13:00:00`
   - `2026-07-26T14:00:00`
   - `2026-07-26T15:00:00`
   - `2026-07-26T16:00:00`
   - `2026-07-26T17:00:00`
   - `2026-07-26T18:00:00`
   - `2026-07-26T19:00:00`
   - `2026-07-26T20:00:00`
   - `2026-07-26T21:00:00`
   - `2026-07-26T22:00:00`
   - `2026-07-26T23:00:00`

13. previous: `2026-07-31T21:00:00`; current: `2026-08-03T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-07-31T22:00:00`
   - `2026-07-31T23:00:00`
   - `2026-08-01T00:00:00`
   - `2026-08-01T01:00:00`
   - `2026-08-01T02:00:00`
   - `2026-08-01T03:00:00`
   - `2026-08-01T04:00:00`
   - `2026-08-01T05:00:00`
   - `2026-08-01T06:00:00`
   - `2026-08-01T07:00:00`
   - `2026-08-01T08:00:00`
   - `2026-08-01T09:00:00`
   - `2026-08-01T10:00:00`
   - `2026-08-01T11:00:00`
   - `2026-08-01T12:00:00`
   - `2026-08-01T13:00:00`
   - `2026-08-01T14:00:00`
   - `2026-08-01T15:00:00`
   - `2026-08-01T16:00:00`
   - `2026-08-01T17:00:00`
   - `2026-08-01T18:00:00`
   - `2026-08-01T19:00:00`
   - `2026-08-01T20:00:00`
   - `2026-08-01T21:00:00`
   - `2026-08-01T22:00:00`
   - `2026-08-01T23:00:00`
   - `2026-08-02T00:00:00`
   - `2026-08-02T01:00:00`
   - `2026-08-02T02:00:00`
   - `2026-08-02T03:00:00`
   - `2026-08-02T04:00:00`
   - `2026-08-02T05:00:00`
   - `2026-08-02T06:00:00`
   - `2026-08-02T07:00:00`
   - `2026-08-02T08:00:00`
   - `2026-08-02T09:00:00`
   - `2026-08-02T10:00:00`
   - `2026-08-02T11:00:00`
   - `2026-08-02T12:00:00`
   - `2026-08-02T13:00:00`
   - `2026-08-02T14:00:00`
   - `2026-08-02T15:00:00`
   - `2026-08-02T16:00:00`
   - `2026-08-02T17:00:00`
   - `2026-08-02T18:00:00`
   - `2026-08-02T19:00:00`
   - `2026-08-02T20:00:00`
   - `2026-08-02T21:00:00`
   - `2026-08-02T22:00:00`
   - `2026-08-02T23:00:00`

14. previous: `2026-08-07T21:00:00`; current: `2026-08-10T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-08-07T22:00:00`
   - `2026-08-07T23:00:00`
   - `2026-08-08T00:00:00`
   - `2026-08-08T01:00:00`
   - `2026-08-08T02:00:00`
   - `2026-08-08T03:00:00`
   - `2026-08-08T04:00:00`
   - `2026-08-08T05:00:00`
   - `2026-08-08T06:00:00`
   - `2026-08-08T07:00:00`
   - `2026-08-08T08:00:00`
   - `2026-08-08T09:00:00`
   - `2026-08-08T10:00:00`
   - `2026-08-08T11:00:00`
   - `2026-08-08T12:00:00`
   - `2026-08-08T13:00:00`
   - `2026-08-08T14:00:00`
   - `2026-08-08T15:00:00`
   - `2026-08-08T16:00:00`
   - `2026-08-08T17:00:00`
   - `2026-08-08T18:00:00`
   - `2026-08-08T19:00:00`
   - `2026-08-08T20:00:00`
   - `2026-08-08T21:00:00`
   - `2026-08-08T22:00:00`
   - `2026-08-08T23:00:00`
   - `2026-08-09T00:00:00`
   - `2026-08-09T01:00:00`
   - `2026-08-09T02:00:00`
   - `2026-08-09T03:00:00`
   - `2026-08-09T04:00:00`
   - `2026-08-09T05:00:00`
   - `2026-08-09T06:00:00`
   - `2026-08-09T07:00:00`
   - `2026-08-09T08:00:00`
   - `2026-08-09T09:00:00`
   - `2026-08-09T10:00:00`
   - `2026-08-09T11:00:00`
   - `2026-08-09T12:00:00`
   - `2026-08-09T13:00:00`
   - `2026-08-09T14:00:00`
   - `2026-08-09T15:00:00`
   - `2026-08-09T16:00:00`
   - `2026-08-09T17:00:00`
   - `2026-08-09T18:00:00`
   - `2026-08-09T19:00:00`
   - `2026-08-09T20:00:00`
   - `2026-08-09T21:00:00`
   - `2026-08-09T22:00:00`
   - `2026-08-09T23:00:00`

15. previous: `2026-08-14T21:00:00`; current: `2026-08-17T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-08-14T22:00:00`
   - `2026-08-14T23:00:00`
   - `2026-08-15T00:00:00`
   - `2026-08-15T01:00:00`
   - `2026-08-15T02:00:00`
   - `2026-08-15T03:00:00`
   - `2026-08-15T04:00:00`
   - `2026-08-15T05:00:00`
   - `2026-08-15T06:00:00`
   - `2026-08-15T07:00:00`
   - `2026-08-15T08:00:00`
   - `2026-08-15T09:00:00`
   - `2026-08-15T10:00:00`
   - `2026-08-15T11:00:00`
   - `2026-08-15T12:00:00`
   - `2026-08-15T13:00:00`
   - `2026-08-15T14:00:00`
   - `2026-08-15T15:00:00`
   - `2026-08-15T16:00:00`
   - `2026-08-15T17:00:00`
   - `2026-08-15T18:00:00`
   - `2026-08-15T19:00:00`
   - `2026-08-15T20:00:00`
   - `2026-08-15T21:00:00`
   - `2026-08-15T22:00:00`
   - `2026-08-15T23:00:00`
   - `2026-08-16T00:00:00`
   - `2026-08-16T01:00:00`
   - `2026-08-16T02:00:00`
   - `2026-08-16T03:00:00`
   - `2026-08-16T04:00:00`
   - `2026-08-16T05:00:00`
   - `2026-08-16T06:00:00`
   - `2026-08-16T07:00:00`
   - `2026-08-16T08:00:00`
   - `2026-08-16T09:00:00`
   - `2026-08-16T10:00:00`
   - `2026-08-16T11:00:00`
   - `2026-08-16T12:00:00`
   - `2026-08-16T13:00:00`
   - `2026-08-16T14:00:00`
   - `2026-08-16T15:00:00`
   - `2026-08-16T16:00:00`
   - `2026-08-16T17:00:00`
   - `2026-08-16T18:00:00`
   - `2026-08-16T19:00:00`
   - `2026-08-16T20:00:00`
   - `2026-08-16T21:00:00`
   - `2026-08-16T22:00:00`
   - `2026-08-16T23:00:00`

16. previous: `2026-08-21T21:00:00`; current: `2026-08-24T00:00:00`; duration_seconds: `183600`; diagnostic: `RECURRENT_WEEKLY_BOUNDARY_UNPROVEN`.

   Missing timestamps (50):

   - `2026-08-21T22:00:00`
   - `2026-08-21T23:00:00`
   - `2026-08-22T00:00:00`
   - `2026-08-22T01:00:00`
   - `2026-08-22T02:00:00`
   - `2026-08-22T03:00:00`
   - `2026-08-22T04:00:00`
   - `2026-08-22T05:00:00`
   - `2026-08-22T06:00:00`
   - `2026-08-22T07:00:00`
   - `2026-08-22T08:00:00`
   - `2026-08-22T09:00:00`
   - `2026-08-22T10:00:00`
   - `2026-08-22T11:00:00`
   - `2026-08-22T12:00:00`
   - `2026-08-22T13:00:00`
   - `2026-08-22T14:00:00`
   - `2026-08-22T15:00:00`
   - `2026-08-22T16:00:00`
   - `2026-08-22T17:00:00`
   - `2026-08-22T18:00:00`
   - `2026-08-22T19:00:00`
   - `2026-08-22T20:00:00`
   - `2026-08-22T21:00:00`
   - `2026-08-22T22:00:00`
   - `2026-08-22T23:00:00`
   - `2026-08-23T00:00:00`
   - `2026-08-23T01:00:00`
   - `2026-08-23T02:00:00`
   - `2026-08-23T03:00:00`
   - `2026-08-23T04:00:00`
   - `2026-08-23T05:00:00`
   - `2026-08-23T06:00:00`
   - `2026-08-23T07:00:00`
   - `2026-08-23T08:00:00`
   - `2026-08-23T09:00:00`
   - `2026-08-23T10:00:00`
   - `2026-08-23T11:00:00`
   - `2026-08-23T12:00:00`
   - `2026-08-23T13:00:00`
   - `2026-08-23T14:00:00`
   - `2026-08-23T15:00:00`
   - `2026-08-23T16:00:00`
   - `2026-08-23T17:00:00`
   - `2026-08-23T18:00:00`
   - `2026-08-23T19:00:00`
   - `2026-08-23T20:00:00`
   - `2026-08-23T21:00:00`
   - `2026-08-23T22:00:00`
   - `2026-08-23T23:00:00`

## H4 Acquisition

- Direct native MT5 H4 rows: 2001
- first timestamp: `2025-05-15T08:00:00`
- last timestamp: `2026-08-28T20:00:00`
- monotonically increasing: yes
- duplicate timestamps: 0
- future timestamps: 0
- current/open candles: 0
- invalid accepted OHLC rows: 0
- negative-volume rows: 0
- native_timeframe: true
- metadata contract: schema 1, provider `MT5`, `EURUSD/H4`, requested/returned 2001/2001, raw/valid 2011/2011, dropped 0, connected true, headroom 10, volume `MT5_TICK_VOLUME`, and the same safe server/company/package/build fields reported above

## H4 Gap Analysis

Contract view: 69 total gap events; `WEEKEND=67`, `SANITIZED_PROVIDER_ROW=0`, `MARKET_SESSION_CLOSED=0`, `PROVIDER_GAP=2`, `INVALID_GAP=0`.

Diagnostic-only view: `WEEKEND=67`, `INTRAWEEK_PROVIDER_GAP=2`, recurrent weekly boundaries among contract provider gaps = 0, and other anomalies = 0. Both residual provider gaps remain blocking.

All exact contract `PROVIDER_GAP` observations:

1. previous: `2025-12-24T16:00:00`; current: `2025-12-26T00:00:00`; duration_seconds: `115200`; diagnostic: `INTRAWEEK_PROVIDER_GAP`.

   Missing timestamps (7):

   - `2025-12-24T20:00:00`
   - `2025-12-25T00:00:00`
   - `2025-12-25T04:00:00`
   - `2025-12-25T08:00:00`
   - `2025-12-25T12:00:00`
   - `2025-12-25T16:00:00`
   - `2025-12-25T20:00:00`

2. previous: `2025-12-31T04:00:00`; current: `2026-01-02T08:00:00`; duration_seconds: `187200`; diagnostic: `INTRAWEEK_PROVIDER_GAP`.

   Missing timestamps (12):

   - `2025-12-31T08:00:00`
   - `2025-12-31T12:00:00`
   - `2025-12-31T16:00:00`
   - `2025-12-31T20:00:00`
   - `2026-01-01T00:00:00`
   - `2026-01-01T04:00:00`
   - `2026-01-01T08:00:00`
   - `2026-01-01T12:00:00`
   - `2026-01-01T16:00:00`
   - `2026-01-01T20:00:00`
   - `2026-01-02T00:00:00`
   - `2026-01-02T04:00:00`

## D1 Acquisition

- Direct native MT5 D1 rows: 2001
- first timestamp: `2018-12-11T00:00:00`
- last timestamp: `2026-08-28T00:00:00`
- monotonically increasing: yes
- duplicate timestamps: 0
- future timestamps: 0
- current/open candles: 0
- invalid accepted OHLC rows: 0
- negative-volume rows: 0
- native_timeframe: true
- metadata contract: schema 1, provider `MT5`, `EURUSD/D1`, requested/returned 2001/2001, raw/valid 2011/2011, dropped 0, connected true, headroom 10, volume `MT5_TICK_VOLUME`, and the same safe server/company/package/build fields reported above

## D1 Gap Analysis

Contract view: 409 total gap events; `WEEKEND=397`, `SANITIZED_PROVIDER_ROW=0`, `MARKET_SESSION_CLOSED=0`, `PROVIDER_GAP=12`, `INVALID_GAP=0`.

Per the audit rule for native D1 without a calendar/session authority, all 12 contract provider gaps are diagnostic `OTHER_UNPROVEN_GAP`. No date is asserted to be a holiday. D1 residual gaps: 12; all remain blocking.

All exact contract `PROVIDER_GAP` observations:

1. previous: `2018-12-24T00:00:00`; current: `2018-12-26T00:00:00`; duration_seconds: `172800`; diagnostic: `OTHER_UNPROVEN_GAP`.

   Missing timestamps (1):

   - `2018-12-25T00:00:00`

2. previous: `2018-12-28T00:00:00`; current: `2019-01-02T00:00:00`; duration_seconds: `432000`; diagnostic: `OTHER_UNPROVEN_GAP`.

   Missing timestamps (4):

   - `2018-12-29T00:00:00`
   - `2018-12-30T00:00:00`
   - `2018-12-31T00:00:00`
   - `2019-01-01T00:00:00`

3. previous: `2019-12-24T00:00:00`; current: `2019-12-26T00:00:00`; duration_seconds: `172800`; diagnostic: `OTHER_UNPROVEN_GAP`.

   Missing timestamps (1):

   - `2019-12-25T00:00:00`

4. previous: `2019-12-31T00:00:00`; current: `2020-01-02T00:00:00`; duration_seconds: `172800`; diagnostic: `OTHER_UNPROVEN_GAP`.

   Missing timestamps (1):

   - `2020-01-01T00:00:00`

5. previous: `2020-12-24T00:00:00`; current: `2020-12-28T00:00:00`; duration_seconds: `345600`; diagnostic: `OTHER_UNPROVEN_GAP`.

   Missing timestamps (3):

   - `2020-12-25T00:00:00`
   - `2020-12-26T00:00:00`
   - `2020-12-27T00:00:00`

6. previous: `2020-12-31T00:00:00`; current: `2021-01-04T00:00:00`; duration_seconds: `345600`; diagnostic: `OTHER_UNPROVEN_GAP`.

   Missing timestamps (3):

   - `2021-01-01T00:00:00`
   - `2021-01-02T00:00:00`
   - `2021-01-03T00:00:00`

7. previous: `2023-12-22T00:00:00`; current: `2023-12-26T00:00:00`; duration_seconds: `345600`; diagnostic: `OTHER_UNPROVEN_GAP`.

   Missing timestamps (3):

   - `2023-12-23T00:00:00`
   - `2023-12-24T00:00:00`
   - `2023-12-25T00:00:00`

8. previous: `2023-12-29T00:00:00`; current: `2024-01-02T00:00:00`; duration_seconds: `345600`; diagnostic: `OTHER_UNPROVEN_GAP`.

   Missing timestamps (3):

   - `2023-12-30T00:00:00`
   - `2023-12-31T00:00:00`
   - `2024-01-01T00:00:00`

9. previous: `2024-12-24T00:00:00`; current: `2024-12-26T00:00:00`; duration_seconds: `172800`; diagnostic: `OTHER_UNPROVEN_GAP`.

   Missing timestamps (1):

   - `2024-12-25T00:00:00`

10. previous: `2024-12-31T00:00:00`; current: `2025-01-02T00:00:00`; duration_seconds: `172800`; diagnostic: `OTHER_UNPROVEN_GAP`.

   Missing timestamps (1):

   - `2025-01-01T00:00:00`

11. previous: `2025-12-24T00:00:00`; current: `2025-12-26T00:00:00`; duration_seconds: `172800`; diagnostic: `OTHER_UNPROVEN_GAP`.

   Missing timestamps (1):

   - `2025-12-25T00:00:00`

12. previous: `2025-12-31T00:00:00`; current: `2026-01-02T00:00:00`; duration_seconds: `172800`; diagnostic: `OTHER_UNPROVEN_GAP`.

   Missing timestamps (1):

   - `2026-01-01T00:00:00`

## OHLC Contract

All three direct 2001-row frames passed the physical OHLC checks: exact row count, strict chronological order, zero duplicate timestamps, zero future/open candles, zero accepted malformed OHLC rows, and zero negative volumes. Sanitization dropped no rows in H1, H4, or D1. Provider metadata consistently bound each frame to `MT5`, the exact external symbol `EURUSD`, its native timeframe, and `MT5_TICK_VOLUME`.

## Temporary Rolling Dataset

Each provider frame was passed to `RollingDataset` with `include_existing=False`, `max_rows=2000`, and a path under an automatically removed external system temporary directory. No canonical path or registry was touched.

- H1: 2000 physical rows; construction PASS; `validate_dataset_frame` WARNING/blocking solely because 16 gaps remain contract `PROVIDER_GAP`; errors: none
- H4: 2000 physical rows; construction PASS; `validate_dataset_frame` WARNING/blocking solely because 2 gaps remain contract `PROVIDER_GAP`; errors: none
- D1: 2000 physical rows; construction PASS; `validate_dataset_frame` WARNING/blocking solely because 12 gaps remain contract `PROVIDER_GAP`; errors: none
- all artifacts: 2000 rows, zero invalid OHLC, zero future timestamps, and all 2000 rows closed

The blocking result is the expected fail-closed contract while SessionAuthority is `UNKNOWN`; it was not suppressed.

## Indicator Reproducibility

Independent recalculation used existing tolerances `rtol=1e-6`, `atol=1e-9`. Every indicator passed in every timeframe with max absolute and relative error `0.0`.

| Indicator | Rows compared per H1/H4/D1 | H1 | H4 | D1 |
| --- | ---: | --- | --- | --- |
| RSI_14 | 1931 | PASS | PASS | PASS |
| MACD | 1871 | PASS | PASS | PASS |
| MACD_signal | 1826 | PASS | PASS | PASS |
| MACD_hist | 1826 | PASS | PASS | PASS |
| ATR_14 | 1931 | PASS | PASS | PASS |
| EMA20 | 1901 | PASS | PASS | PASS |
| EMA50 | 1751 | PASS | PASS | PASS |
| EMA200 | 1001 | PASS | PASS | PASS |
| BB_upper | 1981 | PASS | PASS | PASS |
| BB_lower | 1981 | PASS | PASS | PASS |
| returns | 1999 | PASS | PASS | PASS |
| volatility_24h | 1976 | PASS | PASS | PASS |

Indicator contract: PASS.

## Cross-Timeframe Validation

Existing ASTRA validation: PASS, non-blocking, with no errors or warnings.

- latest price scale ratio: 1.0
- H1→H4: PASS; 491 native H4 rows compared; max relative error for open/high/low/close = 0.0
- H4→D1: PASS; 331 native D1 rows compared; max relative error for open/high/low/close = 0.0

No alternate definition or relaxed threshold was introduced.

## IFC vs Yahoo

No Yahoo acquisition was performed. The Yahoo values below are the previously versioned evidence supplied for this audit.

| Measure | IFC/MT5 live audit | Yahoo known evidence |
| --- | ---: | ---: |
| H1 contract provider gaps | 16 | 17 |
| H1 residual intrawEEK gaps | 0 | 1 |
| H4 contract provider gaps | 2 | 74 |
| H4 residual gaps | 2 | 7 |
| D1 contract provider gaps | 12 | 5 |
| D1 residual gaps | 12 | 5 |
| invalid accepted OHLC | 0/0/0 | previous defects |
| native H4 | yes | no |
| native D1 | yes | yes |
| provenance | durable MT5 acquisition metadata | existing Yahoo evidence |

Continuity winner overall: IFC/MT5, driven by H1 and especially native H4 continuity, zero accepted invalid OHLC, native H4/D1, and durable acquisition provenance. Yahoo has fewer D1 residual gaps (5 versus 12). This is not a price-quality or execution-quality comparison.

## DataRouter Smoke

Executed only after the direct audit. `DataRouter("EURUSD", "H1").fetch(bars=5)` returned 5 in-memory rows with `source_used=MT5`, `route_used.provider=MT5`, and no prior-route errors. OANDA and Yahoo were not called.

## Session Authority Assessment

`NEEDS MORE EVIDENCE`.

The repeated H1 boundaries are suitable candidates for future session-contract design, but H4 has two residual weekday gaps and D1 has twelve unproven closures. ASTRA must not transform them into authorized closures without an explicit authoritative source, provider/symbol/timeframe scope, historical effective ranges, timezone/DST semantics, revision policy, and provenance binding. SessionAuthority remains `UNKNOWN`.

## Demo vs Production Caveat

This audit validates the IFC Markets Demo feed, the connected MT5 terminal, the hardened ASTRA `MT5Provider`, and current ASTRA data contracts. It does not demonstrate that a live/real feed is byte-for-byte identical or that future production infrastructure will use the same account/feed configuration. That remains a deployment consideration, not a reason to discard this demo-feed evidence.

## Remaining Blockers

- Two native H4 contract `PROVIDER_GAP` events lack authorized session evidence.
- Twelve native D1 contract `PROVIDER_GAP` events lack authorized session evidence.
- The sixteen H1 weekly patterns are diagnostically regular but still lack authority and remain contract-blocking.
- A historical, provenance-bound session/calendar authority has not been approved.
- This audit intentionally did not execute qualification or any downstream lifecycle step.

## Viability Decision

**NOT READY — IFC PROVIDER GAPS**

Connectivity, exact closed-bar acquisition, physical OHLC, temporary rolling artifacts, indicator reproducibility, cross-timeframe coherence, provider purity, router preference, and security all passed. Qualification remains blocked because unexplained/unproven provider gaps exist under the current fail-closed contract. No qualification, registration, activation, canonical write, training, WFV, promotion, scheduler, Oracle, or trading operation was executed.

# Oracle Legacy Forex Migration Verification

## Legacy State

The migration is scoped to the four known Oracle legacy rows: EURUSD, USDJPY,
GBPUSD, and AUDUSD. Each must be `active`, have
`activation_origin=legacy`, and have all qualification evidence fields set to
NULL. The active-symbol set must contain exactly those four symbols.

The precheck requires the three observed executable aliases and binds them to
their known SHA256 values:

- `latest_EURUSD.pkl`
- `latest_USDJPY.pkl`
- `latest_AUDUSD.pkl`

`latest_GBPUSD.pkl` must be absent. Its unexpected presence aborts before any
file, manifest, or database mutation.

The registry must contain exactly H1/H4/D1 for all four symbols. Every row must
still identify `provider_used=Yahoo`, `provider_class=FX_REFERENCE`, a complete
source provenance, a canonical `data/forex/<PAIR>_<TF>.csv` path, and a source
SHA256 equal to the physical file.

## Risk

The legacy rows and Yahoo reference datasets predate the managed qualification
and current MT5/IFC provider contracts. Leaving them executable could make
historical state appear production-eligible without current evidence. Direct
SQL edits or deletion would lose provenance and make recovery unsafe.

## Migration Contract

`scripts/migrate_oracle_legacy_forex.py` is dry-run by default. Dry-run performs
all prechecks and returns the proposed manifest in memory without modifying the
database or filesystem.

Mutation requires `--apply` and exact
`ASTRA_SCHEDULER_ENABLED=false`. Operators must separately verify that
`astra-scheduler-h1.timer`, `astra-scheduler-h4.timer`, and
`astra-scheduler-d1.timer` are disabled and inactive. The migration records
that requirement but never enables, disables, starts, or stops a timer or
service.

The apply sequence is explicitly recorded as `PRECHECK`,
`FILES_QUARANTINE`, `DB_MIGRATION`, and `VERIFY`. A durable manifest is written
atomically before file movement and after each completed step. Failures stop
the sequence and trigger safe compensation; an incomplete compensation is
recorded as fail-closed rather than hidden.

## Lifecycle Result

A new canonical lifecycle transition accepts only an existing row that is
simultaneously `active`, `legacy`, and completely without qualification
evidence. It returns the symbol to `candidate`, clears no real evidence because
none may exist, preserves identity/catalog/history fields, and updates only the
lifecycle timestamp and status.

The expected apply result is:

- EURUSD: `candidate`
- USDJPY: `candidate`
- GBPUSD: `disabled`, through canonical `disable_symbol()`
- AUDUSD: `disabled`, through canonical `disable_symbol()`

All transitions compare the current row with the precheck snapshot. Managed,
qualified, non-active, missing, or concurrently changed rows abort. No symbol
is qualified, activated, or promoted, and `get_active_symbols()` must be empty
at verification.

## Artifact Quarantine

The three expected `latest_*.pkl` aliases are moved with `os.replace` to:

`models/forex/legacy_quarantine/<migration-id>/`

Each record includes original path, quarantine path, byte size, and SHA256
before and after movement. Post-move SHA256 must match. No file is overwritten
or discarded. An existing destination aborts. Immutable `ensemble_*` artifacts
are not selected or modified.

## Dataset Quarantine

The twelve Yahoo CSVs are moved byte-for-byte to:

`data/forex_legacy_quarantine/<migration-id>/`

Only the exact EURUSD/USDJPY/GBPUSD/AUDUSD H1/H4/D1 canonical paths are in
scope. No data is downloaded, regenerated, converted to MT5, edited, or
deleted.

## Registry Preservation

All twelve registry rows remain present. Their status becomes the
non-executable value `quarantined`, `blob_path` points to the verified
quarantine file, and `last_error` becomes
`LEGACY_PROVIDER_QUARANTINED_FOR_MT5_MIGRATION`.

Provider, external ticker, provider class, source fetch timestamp, source
SHA256, acquisition metadata, candle metadata, and row identity are preserved.
The migration never relabels Yahoo evidence as MT5 and never reports the rows
as canonical ready data.

## Rollback

`--rollback <manifest>` restores a successful apply only while every database
row and quarantine file still matches the exact recorded post-migration state.
The manifest schema, scope, paths, lifecycle transitions, registry provenance,
alias hashes, sizes, and SHA256 values are revalidated before movement.

Rollback refuses to overwrite any newly created original path, any changed DB
row, a missing or changed quarantine file, a malformed manifest, or evidence
outside the exact migration scope. Files are restored only after complete
precheck and their SHA256 is verified again. Database restoration uses one
transaction and exact pre-migration snapshots. A separate durable rollback
manifest records the operation.

## Tests

- New migration contract: 18 passed, 0 failed.
- Focused migration/lifecycle/read-only/readiness/infrastructure suite:
  109 passed, 0 failed.
- Full suite: 1027 passed, 10 expected skips, 23 subtests passed, 0 failed.
- `python -m compileall -q .`: passed; the ignored `.pytest_cache` directory
  could not be enumerated, with exit status zero.
- `git diff --check`: passed.

Tests prove default dry-run immutability, scheduler precondition, strict legacy
transition eligibility, exact final states, alias and dataset hash preservation,
registry provenance, complete secret-free manifests, rollback, conflict refusal,
automatic compensation after an injected DB failure, and absence of network,
training, promotion, activation, prediction, outcomes, or trading effects.

## Expected Oracle State

No Oracle command or migration was executed during this implementation. A
future authorized apply is expected to leave EURUSD and USDJPY as candidates,
GBPUSD and AUDUSD disabled, no active symbols, no executable aliases for the
four symbols, all twelve Yahoo CSVs preserved outside the canonical dataset
path, and all twelve registry rows retained as quarantined legacy provenance.
Production readiness is expected to remain pending until new canonical
qualification and model evidence exists.

## Decision

ORACLE LEGACY FOREX MIGRATION READY — DRY-RUN AUTHORIZED

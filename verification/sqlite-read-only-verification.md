# SQLite Read-Only Verification

## Defect

`SQLiteDatabase` previously had only a writable construction path. Every
instance created its parent directory, ran `_init_schema()`, opened a normal
connection, selected WAL journal mode, and committed on context exit. A
snapshot inspection or audit could therefore rewrite physical SQLite bytes
despite changing no application row.

## Design

`SQLiteDatabase(db_path=None, read_only=False)` preserves the writable default.
The explicit `read_only=True` path resolves an existing database file, fails
closed if it is missing, and returns before directory creation or schema
initialization. `SQLiteReadOnlyError` supplies an adapter-level failure for
mutating APIs instead of relying on a native SQL error.

The implementation is confined to `infra/db/database.py`. No Forex source,
model contract, target, feature, threshold, lifecycle, promotion, or trading
logic changed.

## Connection Contract

Read-only connections use an absolute SQLite URI with
`mode=ro&immutable=1`, set `sqlite3.Row` as the row factory, and only close the
connection after use. They do not execute DDL, `PRAGMA journal_mode=WAL`,
commit, or rollback.

`immutable=1` prevents a clean WAL-configured database from creating
auxiliary files during inspection. To avoid ignoring uncheckpointed state,
construction fails closed with `SQLITE_READ_ONLY_UNCHECKPOINTED_STATE` if an
existing `-wal` or `-shm` sidecar is present. The caller must retry after the
writable owner has closed and checkpointed its state.

## Write Protection

`_require_writable()` raises
`SQLiteReadOnlyError: SQLITE_READ_ONLY_WRITE_FORBIDDEN` before a mutating SQL
connection can be acquired. `_writable_connection()` centralizes that guard.
Schema initialization, symbol registration/qualification/activation/disable,
dataset upserts, prediction and outcome persistence, retrain creation and
transitions, provenance finalization, model-quality writes, and scheduler-run
writes all use this guarded route. Pure-read methods retain the ordinary
read connection route.

Regression coverage directly rejects representative symbol registration,
dataset upsert, prediction persistence, model-quality persistence, retrain
creation, and model-provenance finalization calls.

## Physical Immutability

A temporary database was populated and all writable handles were released.
Representative read-only queries covered symbols, datasets, predictions,
outcomes, model quality, retrain runs, and model provenance. The main-file
SHA-256 was identical before and after, and neither `-wal` nor `-shm` was
created.

An additional local read-only check of
`memory_db/astra_autonomous.db` observed main-file SHA-256
`1d6aff3270278096e614f096dfedbc8d199dcc8559bade7dc736128ae7ac4383`
both before and after `get_symbol("EURUSD")`, with no sidecars before or
after. This proves the immutability of that explicit read-only operation. It
does not claim continuity with the `969809...` physical hash recorded during
the preceding outer-evaluation task because no new baseline hash was captured
at the start of this branch.

## RetrainManager Compatibility

`RetrainManager` already accepts a `database=` adapter. No manager change was
needed. A manager constructed with `SQLiteDatabase(..., read_only=True)`
successfully captured and revalidated a complete temporary H1/H4/D1 training
snapshot. Its database SHA and sidecar set were identical before and after.
Snapshot capture and validation therefore have a supported immutable database
path without changing broader retraining behavior.

## Backward Compatibility

The default remains `read_only=False`. Its constructor still creates parent
directories, initializes and migrates the schema, configures WAL, commits
writes, and supports existing persistence APIs. Related lifecycle,
closed-loop, recovery, manual-retrain, infrastructure, and scheduler tests
continued to pass without relaxed assertions.

## Tests

The test-first run produced five expected failures because the old constructor
did not accept `read_only=True`; the existing writable control passed. After
implementation:

- focused immutable SQLite contract: 6 passed;
- related persistence and RetrainManager suite: 158 passed, 2 known
  deprecation warnings;
- full suite: 841 passed, 10 skipped, 0 failed, 13 known deprecation warnings,
  and 23 subtests passed.

The 10 skips are unchanged: five repository-dataset integration tests require
`ASTRA_RUN_INTEGRATION_TESTS=1`, and five scheduler activation shell cases
require POSIX process semantics unavailable on Windows. `compileall` exited
zero; the pre-existing inaccessible `.pytest_cache` emitted a non-fatal
`Can't list` diagnostic. `git diff --check` passed.

## EURUSD Safety

No H1 matrix, target, current tail, outer fold, metric, training, prediction,
provider fetch, model artifact, promotion, activation, or trade was executed.
The local database read was limited to the EURUSD lifecycle row through the
new read-only connection. EURUSD remained `qualified`, and no Forex source
file changed.

## Decision

**SQLITE READ-ONLY CONTRACT READY — H1 PRODUCTION ENGINEERING UNBLOCKED**

The remaining gate is separately authorized H1 production-contract
engineering and genuinely new independent validation evidence; the consumed
current outer cannot be reused for tuning.

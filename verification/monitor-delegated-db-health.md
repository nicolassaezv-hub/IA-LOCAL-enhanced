# ASTRA Monitor Delegated Database Health

## Scope

This verification covers the production monitor false alarm caused by direct
SQLite WAL inspection from `astra-monitor.service`. Forex ML, targets,
features, models, gates, trading, scheduler timers, and database schema are
outside the change and remain untouched.

## Root cause

The live SQLite database uses WAL and shared-memory sidecars. The long-running
monitor executes under `ProtectSystem=strict` and has no writable exception for
`/opt/astra/memory_db`, so a direct `PRAGMA quick_check` cannot reliably open
the WAL/SHM state from that sandbox. The same database passes the direct
read-only one-shot check outside the sandbox. This is an access-context false
alarm, not evidence of database corruption.

## Delegated health contract

The local ASTRA API now exposes `GET /api/health/database` through its existing
bind and security policy. The trusted API process calls the canonical database
health probe and returns only:

- `state`: `DB_HEALTH_PASS`, `DB_HEALTH_FAILED`, or `DB_HEALTH_UNAVAILABLE`
- `classification`: a bounded safe classification identifier

The endpoint returns HTTP 200 only for `DB_HEALTH_PASS` and HTTP 503 otherwise.
It exposes no database contents, paths, credentials, or exception details.
The existing `/health` and `/api/health` responses remain unchanged.

The canonical probe opens only an existing database with SQLite `mode=rw`,
then enables and verifies `PRAGMA query_only` before running
`PRAGMA quick_check`. This allows the trusted process to observe the live
WAL/SHM state without creating a database, initializing schema, or issuing
SQL writes. Connections are closed deterministically.

The strict daemon no longer opens the live database for its periodic database
health check. It consumes the local API result and preserves fail-closed
states:

- explicit delegated failure alerts as `DB_HEALTH_FAILED`;
- an unavailable/invalid delegated result remains `DB_HEALTH_UNAVAILABLE` and
  is never declared healthy;
- complete API loss alerts as `API_UNREACHABLE` and makes database health
  unavailable.

## Direct one-shot behavior

`supervisor.py --check-once` remains immediate and continues using the direct
read-only SQLite probe for operator-controlled environments where WAL access is
available. It does not use the daemon startup grace.

## Startup and scheduler behavior

The daemon uses a bounded startup grace configured by
`ASTRA_MONITOR_STARTUP_GRACE_SECONDS`, clamped to 30-60 seconds and defaulting
to 45 seconds. Connection refusal during this window is an informational
startup state. After the window, normal fail-closed API alerts apply.

When existing configuration `ASTRA_SCHEDULER_ENABLED=false` is set because the
scheduler timers are intentionally disabled, the monitor emits
`SCHEDULER_MONITORING_DISABLED` at most once and suppresses stale-run warnings.
When enabled, the prior freshness checks and warnings remain active. No timer
or scheduler persistence behavior changed.

## Systemd and database safety

- `ProtectSystem=strict` is preserved.
- `astra-monitor.service` retains only `ReadWritePaths=/var/log/astra`.
- No writable exception for `/opt/astra/memory_db` was added.
- SQLite `immutable=1` is not used against the live database.
- No database schema, contents, initialization, or migration changed.

## Verification

- Delegated-monitor regression file: 17 passed, 0 failed.
- Focused monitor/API/infrastructure suite: 171 passed, 5 expected POSIX-only
  skips, 0 failed.
- Full suite: 1009 passed, 10 expected skips, 23 subtests passed, 0 failed.
- `python -m compileall -q .`: passed (the ignored `.pytest_cache` directory
  was unavailable to enumeration; exit status remained zero).
- `git diff --check`: passed.

## Decision

MONITOR DELEGATED HEALTH READY — ORACLE FINALIZATION AUTHORIZED

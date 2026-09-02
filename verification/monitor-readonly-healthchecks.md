# ASTRA Monitor Read-Only Healthchecks

## Oracle Failure Evidence

Oracle Cloud runs Ubuntu 24.04 ARM64 with `astra-api.service` and `astra-monitor.service` active. A direct request as user `astra` to `http://127.0.0.1:8000/health` returns HTTP 200 and `{"status":"ok"}`. The same user can open `/opt/astra/memory_db/astra_autonomous.db` normally and read-only, and `PRAGMA quick_check` returns `ok`.

Despite that, the monitor repeatedly reported `astra-api appears DOWN or unresponsive` and `SQLite operational error (DB locked or inaccessible): unable to open database file`. Its systemd unit has `ProtectSystem=strict` and only `/var/log/astra` in `ReadWritePaths`; `/opt/astra` is deliberately read-only.

## Root Cause

The SQLite false alarm was caused by the monitor using a normal `sqlite3.connect(path)` connection. That requests a read/write-capable SQLite open and may require writable auxiliary WAL/journal access, which conflicts with the intentionally read-only systemd view of `/opt/astra`. The application database and Unix ownership were healthy; granting the monitor write access would have weakened its observational role.

The precise API failure mechanism could not be recovered from the old logs because `check_api_health()` discarded every endpoint exception. It then emitted only a generic socket failure. The revised monitor preserves safe classifications for each endpoint, making a future distinction between endpoint status, timeout, refusal, network failure, and unexpected exception possible without logging request headers or secrets.

## SQLite Read-Only Contract

The monitor now resolves and reports the database path, then opens it with a URI of the form `file:///.../astra_autonomous.db?mode=ro`, `uri=True`, and the existing timeout. Immediately after opening it executes and verifies `PRAGMA query_only = ON`, then runs `PRAGMA quick_check`. The connection is closed deterministically without schema initialization, table creation, commit, rollback, repair, checkpoint, or deliberate WAL/SHM mutation.

`immutable=1` is not used because the monitored database is live and may change. Existing WAL/SHM state remains SQLite's responsibility under a read-only connection. If it cannot be inspected safely, the monitor fails with a diagnostic instead of trying to repair or mutate it.

The scheduler freshness lookup also uses the same read-only URI and `query_only` setup. A missing database under an accessible parent retains the established first-write behavior: it is reported as `DB_FILE_MISSING` but is not considered unhealthy and is not created by the monitor.

Database diagnostics distinguish:

- `DB_FILE_MISSING`
- `DB_PARENT_INACCESSIBLE`
- `SQLITE_READ_ONLY_CONNECT_FAILED`
- `SQLITE_QUERY_ONLY_FAILED`
- `SQLITE_QUICK_CHECK_FAILED`
- `SQLITE_DATABASE_CORRUPTION`
- `SQLITE_OPERATIONAL_LOCK_OR_ACCESS_ERROR`

Diagnostics include the resolved database path and phase, but never database contents.

## API Diagnostic Contract

Endpoints are checked in order: `/health`, then `/api/status`. HTTP 200 or the previously accepted 201 returns healthy immediately. Therefore a normal `/health` HTTP 200 cycle does not call `/api/status`, does not use the socket fallback, and emits no warning or error.

Failures are retained as safe classifications: HTTP status, timeout, connection refused, URL/network error, or exception type. Exception messages and request headers are not logged. If both HTTP endpoints fail but the host/port socket connects, the existing healthy fallback is preserved and a warning reports `HTTP_HEALTH_FAILED_SOCKET_REACHABLE` with host, port, and the two safe endpoint classifications. If HTTP and socket checks fail, the result is unhealthy with `API_HEALTH_FAILED`.

`--check-once` runs exactly one API check, database check, and scheduler freshness check. It returns 0 only when API and database health pass. Scheduler freshness remains advisory and cannot make one-shot mode fail, because scheduler timers may intentionally be disabled. Invocation without arguments still enters the existing infinite monitor loop.

## Systemd Sandbox Preservation

`infra/systemd/astra-monitor.service` was not modified. It still contains:

- `ProtectSystem=strict`
- `ReadWritePaths=/var/log/astra`

It does not include `/opt/astra/memory_db` or any equivalent writable database exception. User, group, restart policy, deployment architecture, and systemd ownership remain unchanged.

## Tests

The new monitor regression file contributes 17 passing test cases covering:

- read-only SQLite URI and `uri=True`;
- enabled and verified `query_only`;
- successful `quick_check`;
- no write-access dependency or schema-mutating SQL;
- missing file and inaccessible parent classifications;
- failed quick check, corrupt database, and read-only connection failure;
- immediate `/health` HTTP 200 success;
- `/api/status` success after `/health` failure;
- HTTP failure plus reachable socket warning/pass;
- HTTP plus socket failure and secret-safe diagnostics;
- one-shot exit behavior for API failure, database failure, and advisory scheduler state;
- default infinite-loop dispatch compatibility;
- strict systemd sandbox with no writable database path.

Validation results:

- Monitor-focused: 17 passed, 0 failed.
- Monitor plus infrastructure/deployment: 118 passed, 5 expected POSIX-only skips, 0 failed.
- Full suite: 992 passed, 10 expected skips, 0 failed, 23 subtests passed.
- Full-suite warnings: 2417 pre-existing deprecation warnings.
- `python -m compileall -q .`: passed; the pre-existing inaccessible `.pytest_cache` listing warning remains environmental.
- `git diff --check`: passed.

## Deployment Impact

Only the diagnostic supervisor and its tests changed. The production API, database schema, scheduler behavior, deployment architecture, Forex models, Shadow runtime, target, features, gates, and trading behavior are unchanged.

Redeployment may replace and restart the monitor service using the existing deployment process. The monitor requires no additional filesystem write permission. After redeploy, `supervisor.py --check-once` can provide one bounded API/DB diagnostic while treating scheduler freshness as advisory.

## Decision

`MONITOR HEALTHCHECK HARDENING READY — ORACLE REDEPLOY AUTHORIZED`

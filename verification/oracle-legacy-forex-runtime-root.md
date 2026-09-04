# Oracle Legacy Forex Runtime Root Verification

## Defect

The migration previously used the directory containing its source file as both
the Git checkout and the mutable ASTRA runtime root. That assumption is false
in Oracle: deployed runtime state lives under `/opt/astra`, while Git metadata
lives under `/home/ubuntu/astra-source` and `/opt/astra` contains no `.git`.

Running from the deployed tree therefore produced correct runtime paths but
made `git rev-parse HEAD` fail. Running from the source checkout made Git work
but targeted datasets, models, quarantine directories, and manifests in the
wrong installation tree.

## Explicit Runtime-Root Contract

The CLI now requires `--project-root PATH`. Every mutable or audited path is
derived only from the resolved runtime root:

- datasets: `<project-root>/data/forex`
- models: `<project-root>/models/forex`
- model quarantine:
  `<project-root>/models/forex/legacy_quarantine/<migration-id>`
- dataset quarantine:
  `<project-root>/data/forex_legacy_quarantine/<migration-id>`
- manifest: `<project-root>/reports/deployment/...`

Before dry-run, apply, or rollback, the root must already exist and contain
`data/forex`, `models/forex`, and `memory_db`. PRECHECK does not create these
structures. When `ASTRA_HOME` is configured, its resolved absolute path must
equal `--project-root`; mismatch fails closed for every mode.

The database remains selected by ASTRA's canonical external environment
configuration. It is not redirected to the source checkout or inferred from
Git metadata.

## Explicit Source-SHA Contract

The CLI accepts `--source-git-sha SHA`. The value is normalized to lowercase
and must contain exactly 40 hexadecimal characters. When supplied, no Git
subprocess is executed. The value is recorded verbatim after normalization in
the migration manifest.

If omitted for local development, `git rev-parse HEAD` is permitted only from
the actual source checkout containing `.git`. It is never attempted from the
runtime root and performs no network access.

The operator must pass the exact SHA of the deployed checkout containing the
migration code. A branch name, abbreviated SHA, malformed value, or SHA from a
different build is not accepted as explicit source evidence.

## Dry-Run Immutability

With explicit `--project-root` and `--source-git-sha`, dry-run validates the
selected runtime entirely in memory. It does not write the database, CSVs,
models, aliases, quarantine directories, report directories, or manifests.
Tests compare the complete runtime path inventory and database snapshot before
and after dry-run.

## Apply and Rollback Binding

Apply records `runtime_project_root` and `source_git_sha` in the durable
manifest. All original and quarantine paths are validated beneath that root.

Rollback requires an explicit runtime root, validates it against `ASTRA_HOME`,
and then requires exact equality with the manifest's
`runtime_project_root` before moving any file or changing any row. A manifest
from another ASTRA installation fails with
`ROLLBACK_RUNTIME_ROOT_MISMATCH`. The prior file-hash, lifecycle, registry,
conflict, and transactional rollback protections remain unchanged.

## Oracle Invocation

Dry-run only, after deploying and confirming the exact checked-out SHA:

```bash
python scripts/migrate_oracle_legacy_forex.py \
  --project-root /opt/astra \
  --source-git-sha <DEPLOYED_40_CHARACTER_GIT_SHA>
```

This report does not authorize `--apply`. The scheduler/timer and legacy-state
preconditions from the migration report remain mandatory.

## Tests

- Migration regression file: 31 passed, 0 failed. This includes all 18 prior
  migration tests plus 13 runtime-root/source-SHA regression cases.
- Focused migration/lifecycle/read-only/readiness/infrastructure suite:
  122 passed, 0 failed.
- Full suite: 1040 passed, 10 expected skips, 23 subtests passed, 0 failed.
- `python -m compileall -q .`: passed; the ignored `.pytest_cache` directory
  could not be enumerated, with exit status zero.
- `git diff --check`: passed.

The new cases prove separation of source and runtime trees, operation without
`.git` in the runtime, suppression of Git invocation for an explicit SHA,
strict SHA validation, root existence and structure checks, `ASTRA_HOME`
binding, runtime-only dataset/model/quarantine/manifest resolution, dry-run
immutability, apply binding, and rollback rejection for a different root.

## Decision

ORACLE LEGACY FOREX RUNTIME ROOT FIX READY — DRY-RUN AUTHORIZED

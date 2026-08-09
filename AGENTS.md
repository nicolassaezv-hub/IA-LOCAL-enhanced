# AGENTS.md — ASTRA v7.1.0

## Mission

ASTRA is a modular local/cloud AI platform with a production-focused Forex intelligence subsystem.
The current goal is **hardening and completing the existing architecture**, not redesigning it.

Work incrementally, preserve behavior, keep diffs scoped, and validate every change.

## Production target

Primary deployment target:

- Oracle Cloud Infrastructure
- Ubuntu 24.04 LTS
- ARM64 / `aarch64`
- Oracle Ampere A1 (`VM.Standard.A1.Flex`)
- 2 OCPU
- 12 GB RAM
- Python 3.12
- 24/7 Linux operation

For the current VM facts, read:

- `docs/infraestructure/ORACLE_VM.md`

Do not embed IP addresses, SSH private keys, passwords, API keys, tokens, or other secrets in source code or documentation.

## Repository map

Important entry points and subsystems:

- `main.py` — main CLI / orchestration entry point
- `workspace/server.py` — FastAPI Workplace backend
- `forex/` — Forex intelligence subsystem
- `forex/prediction/integrated_pipeline.py` — integrated prediction pipeline
- `forex/prediction/roadmap_v_integration.py` — Roadmap V integration layer
- `forex/data/` — providers, rolling datasets, bulk generation and updates
- `scheduler/autonomous_scheduler.py` — autonomous H1/H4/D1 scheduler
- `robustness/` — dependency, provider, model and data validation
- `deployment/` — first-run, pipeline and production-readiness reports
- `infra/` — Linux deployment, database abstraction, systemd, monitoring and backup
- `memory_db/` — autonomous persistence layer
- `models/` — serialized ML artifacts
- `tests/` and `test_*.py` — automated tests
- `docs/` — project documentation
- `legacy/` — historical compatibility code; avoid changing unless explicitly required

Read the relevant implementation before editing. Do not infer behavior only from filenames or documentation.

## Sources of truth

Use this priority when information conflicts:

1. Explicit task instructions.
2. Current executable code and tests.
3. `docs/infraestructure/ORACLE_VM.md` for the real production VM.
4. `MANUAL.md`, `README.md`, and other documentation.

Some documentation predates the current Oracle deployment and may contain stale VM specifications or version labels. Verify against current code and the Oracle VM document before changing production behavior.

## Core architecture invariants

Do not remove or silently bypass these systems:

- Forex Prediction Pipeline
- Decision Engine
- Risk Engine
- Regime Detection
- Multi-Timeframe coherence
- Outcome Tracker
- Adaptive Retraining / Retrain Manager
- Rolling Dataset management
- Market Sentinel
- Model selection / validation logic
- Data and model integrity checks
- Deployment / readiness reporting
- Workplace / FastAPI interface
- Autonomous scheduler
- Monitoring and backup infrastructure

If a task requires changing one of these, explain the reason and add or update tests.

## Forex invariants

Preserve these behaviors unless the task explicitly changes them:

- Main production timeframes are `H1`, `H4`, and `D1`.
- Default rolling dataset window is `2000`.
- The scheduler must remain provider-agnostic and Linux-compatible.
- Forex data routing may use MT5 when available and Yahoo as fallback.
- Crypto routing may use Binance with Yahoo fallback where implemented.
- MT5 is Windows-only and must not become a Linux production requirement.
- H4 Yahoo data is derived from 1H data where implemented.
- Multi-timeframe joins must not introduce lookahead bias.
- The Decision Engine remains the final authority for whether a model signal is actionable.
- Risk logic must not be weakened to make tests pass.
- Do not fabricate live-market success or production-readiness evidence.

Do not change trading thresholds, model behavior, feature definitions, risk logic, or financial assumptions as an unrelated cleanup.

## Linux / ARM64 rules

Production changes must work on Ubuntu 24.04 ARM64.

Do not introduce a required dependency on:

- Windows GUI automation
- Windows COM
- MetaTrader5 Python package on Linux
- `.bat` files
- `.exe` files
- Windows-only filesystem paths

Windows utilities may remain for local compatibility, but Linux runtime paths must not depend on them.

When modifying dependencies, explicitly consider ARM64 compatibility for ML packages such as:

- NumPy
- pandas
- SciPy
- scikit-learn
- XGBoost
- LightGBM
- SHAP
- FAISS

Do not replace working ML libraries merely because installation is inconvenient. Diagnose the compatibility problem first.

## Secrets and sensitive files

Never commit, print, copy into reports, or expose values from:

- `.env`
- `astra.env`
- `infra/config/astra.env`
- `*.key`
- `*.pem`
- SSH private keys
- API credentials
- database credentials
- cloud credentials

Use environment variables and example files containing placeholders only.

If a secret appears to already exist in version-controlled content, report it before modifying unrelated code.

## Runtime and generated artifacts

Treat these as data/runtime artifacts unless a task explicitly targets them:

- `*.db`
- logs
- backups
- generated deployment reports
- caches
- `__pycache__/`
- `.pytest_cache/`
- uploaded user files
- generated CSV datasets
- serialized `*.pkl` models

Do not delete, regenerate, retrain, or overwrite models/datasets merely to make a test pass.

Prefer temporary test fixtures for tests.

## Legacy and cleanup

Do not perform broad deletion or repository cleanup without explicit approval.

Files such as old Windows launchers, `.exe`, `.bat`, duplicated documentation, historical reports, and `legacy/` content may be candidates for later cleanup, but first:

1. prove they are unused,
2. report references,
3. propose the deletion separately.

Avoid drive-by refactors.

## Editing protocol

For every task:

1. Inspect relevant files and nearby tests.
2. Reproduce the bug or establish the current behavior when possible.
3. State the smallest viable change.
4. Modify only files needed for the task.
5. Add/update tests when behavior changes.
6. Run targeted tests.
7. Run the repository validation commands below.
8. Report changed files, tests, remaining warnings, and unresolved risks.

Do not claim a fix is complete when validation was not run.

## Validation commands

At minimum after Python changes:

```bash
python -m compileall -q .
pytest -q
```

When relevant, also run:

```bash
python check_startup.py
python test_complete_pipeline.py
python scheduler/autonomous_scheduler.py --status
```

For infrastructure/deployment tasks, run the applicable tests in:

```bash
pytest -q tests/test_infrastructure.py
```

Use narrower tests first while iterating, then run the broader suite before completion.

If a test cannot run because an optional external service is unavailable, distinguish:

- actual product failure,
- missing optional dependency/service,
- environment limitation.

Do not hide failures by weakening assertions.

## Current baseline caveats

At the start of hardening, verify whether these known issues are still present before assuming they are fixed:

- `creando.py` may import market-universe symbols that no longer exist.
- The full-Forex benchmark recording in `main.py` may be located after an unreachable `return`.
- The Redis test may fail when Redis is not installed even though Redis is optional.
- The First Run Wizard may behave as a synthetic smoke test rather than a full production initialization.
- Version labels may be inconsistent across `MANUAL.md`, `CHANGELOG.md`, scheduler and infrastructure files.
- Serialized ML models may emit version-compatibility warnings.

Fix these only in scoped tasks, with tests.

## Git behavior

Do not commit, push, merge, rebase, amend, or open a pull request unless the task explicitly asks for it.

Keep the working tree changes focused on the requested task.

Before finishing, show or summarize the diff and identify any unrelated pre-existing changes.

## Code style

Follow the style already used in the touched module.

Prefer:

- clear type hints where they improve correctness,
- `pathlib` for portable filesystem work,
- structured logging over new ad-hoc prints in backend code,
- explicit exceptions and useful error messages,
- small functions with focused responsibilities,
- backward-compatible interfaces where practical.

Do not introduce a new framework or architecture unless explicitly requested.

## Documentation

Update documentation when a change alters:

- commands,
- configuration,
- deployment,
- API behavior,
- scheduler behavior,
- production requirements,
- file locations,
- environment variables.

Do not duplicate large blocks of documentation across multiple files when one canonical document can be referenced.

## Definition of done

A task is complete only when:

- the requested behavior is implemented,
- existing architecture is preserved unless explicitly changed,
- no secrets were introduced,
- relevant tests were added or updated,
- validation commands were run,
- failures/warnings are reported accurately,
- Linux/ARM64 production impact is considered,
- the final response lists changed files and verification results.

# ASTRA Forex Production Verification

## Baseline

- Classification: PASS
- Repository: `nicolassaezv-hub/IA-LOCAL-enhanced`
- Source branch: `working/v7.1.0-final-source-of-truth`
- Verification branch: `codex/forex-production-verification-20260828`
- Baseline SHA: `1552d1dc6b36b4011e4f172fbd4bf18443a3446d`
- Python version selected by `python`: `3.14.6`
- Python executable: `C:\Python314\python.exe`
- OS: `Windows-11-10.0.26200-SP0`
- Architecture: `AMD64`
- Production target was not accessed or modified.

## Git State

- Classification: PASS
- Initial working tree: clean.
- Initial branch: `working/v7.1.0-final-source-of-truth` tracking its origin branch.
- Initial and verification HEAD: `1552d1dc6b36b4011e4f172fbd4bf18443a3446d`.
- Remote fetch/push repository: `https://github.com/nicolassaezv-hub/IA-LOCAL-enhanced.git`.
- Verification branch was created directly from the required baseline.

## Focused Contract Tests

- Classification: FAIL
- Command exit code: `1`.
- Passed: `0` (pytest did not start).
- Failed tests: `0` (pytest did not start).
- Skipped: `0` (pytest did not start).
- Observed command duration: approximately `1.17s`.
- Blocker: the `python` selected by the shell has no `pytest` installation.

Command:

```text
python -m pytest -q tests/test_wfv_statistical_contract.py tests/test_manual_quality_retrain.py tests/test_productive_first_run_hardening.py tests/test_symbol_lifecycle.py tests/test_b1_closed_loop_persistence.py tests/test_interrupted_state_recovery.py tests/test_a08_first_run_readiness.py
```

Complete output:

```text
C:\Python314\python.exe: No module named pytest
```

Installed Python interpreters reported by the Windows launcher:

```text
 -V:3.14 *        C:\Users\nicol\AppData\Local\Python\pythoncore-3.14-64\python.exe
 -V:3.12          C:\Users\nicol\AppData\Local\Programs\Python\Python312\python.exe
 -V:3.7           C:\Users\nicol\AppData\Local\Programs\Python\Python37\python.exe
```

The exact required command resolves to Python 3.14.6, not the production-target Python 3.12 environment. No alternate interpreter was substituted because the verification contract required the exact command and required retraining to stop unless the focused suite passed.

## Full Test Suite

- Classification: PENDING
- Not executed because the focused contractual suite did not pass.
- This is an environment gate result, not evidence of a product test failure.

## Scheduler Status

- Classification: FAIL
- Command exit code: `1`.
- No status JSON was produced.
- Active symbols, expected/ready datasets, registry inconsistencies, latest H1 run, stale runs, prediction counts, and scheduler errors could not be evaluated.

Command:

```text
python scheduler/autonomous_scheduler.py --status
```

Complete traceback:

```text
Traceback (most recent call last):
  File "C:\Users\nicol\Downloads\IA-LOCAL-v710-final - WORKING\IA-LOCAL-v710-final\scheduler\autonomous_scheduler.py", line 39, in <module>
    from forex.data.data_router import DataRouter
  File "C:\Users\nicol\Downloads\IA-LOCAL-v710-final - WORKING\IA-LOCAL-v710-final\forex\data\data_router.py", line 6, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'
```

## Production Readiness — Offline Probe

- Classification: FAIL
- Command exit code: `1`.
- No readiness result or JSON was produced.
- `global_status`, counters, blocking reasons, datasets, models, scheduler, provider configuration, filesystem, and resource checks remain unevaluated.

Complete traceback:

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import json; from deployment.production_readiness import run_production_readiness; r=run_production_readiness(probe_providers=False); print(json.dumps(r.to_dict(), indent=2, default=str))
                                                                                         ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\nicol\Downloads\IA-LOCAL-v710-final - WORKING\IA-LOCAL-v710-final\deployment\production_readiness.py", line 555, in run_production_readiness
    from forex.prediction.model_storage import ModelStorage
  File "C:\Users\nicol\Downloads\IA-LOCAL-v710-final - WORKING\IA-LOCAL-v710-final\forex\prediction\__init__.py", line 15, in <module>
    from .dataset_builder        import DatasetBuilder, get_pair_config
  File "C:\Users\nicol\Downloads\IA-LOCAL-v710-final - WORKING\IA-LOCAL-v710-final\forex\prediction\dataset_builder.py", line 13, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'
```

## Production Readiness — Operational Provider Probe

- Classification: FAIL
- Command exit code: `1`.
- The command failed during local imports before any provider/network probe was attempted.
- Provider connectivity therefore remains PENDING; this result is not evidence of a provider or network failure.

Complete traceback:

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import json; from deployment.production_readiness import run_production_readiness; r=run_production_readiness(probe_providers=True); print(json.dumps(r.to_dict(), indent=2, default=str))
                                                                                         ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\nicol\Downloads\IA-LOCAL-v710-final - WORKING\IA-LOCAL-v710-final\deployment\production_readiness.py", line 555, in run_production_readiness
    from forex.prediction.model_storage import ModelStorage
  File "C:\Users\nicol\Downloads\IA-LOCAL-v710-final - WORKING\IA-LOCAL-v710-final\forex\prediction\__init__.py", line 15, in <module>
    from .dataset_builder        import DatasetBuilder, get_pair_config
  File "C:\Users\nicol\Downloads\IA-LOCAL-v710-final - WORKING\IA-LOCAL-v710-final\forex\prediction\dataset_builder.py", line 13, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'
```

## EURUSD Pre-Retrain State

- Classification: PENDING
- Not audited because the focused contractual suite did not pass, as required by the verification contract.
- Alias existence/hash/size, model audit, retrain history, datasets, candle counts, provenance, and eligibility were not inspected.

## EURUSD Manual Quality Retrain

- Classification: PENDING
- Not executed.
- The focused suite did not pass and the EURUSD pre-retrain safety conditions were not established.
- No `request_id`, run, candidate artifact, promotion, or runtime state was created.

## WFV Statistical Evidence

- Classification: PENDING
- No retrain was executed, so no new folds, TP/FP counts, signal counts, aggregate precision, pooled precision, evidence sufficiency, or WFV decision were produced.

## Calibration / Validation Evidence

- Classification: PENDING
- No retrain was executed, so no calibration, validation, or `model_valid` evidence was produced.

## EURUSD Post-Retrain State

- Classification: PENDING
- Not applicable because no retrain was executed.

## Alias Integrity

- Classification: PENDING
- No code path capable of staging or promoting a model was invoked.
- The EURUSD alias was not inspected or intentionally modified during this run.

## Dataset / Registry Evidence

- Classification: PENDING
- Scheduler and readiness commands failed before producing registry or dataset evidence because `pandas` is absent from the active Python environment.
- No CSV, database, dataset, or model was modified.

## Scheduler Evidence

- Classification: FAIL
- Scheduler status could not import its data layer because `pandas` is absent.
- No H1 cycle was run and no timer or systemd unit was activated.

## Remaining Production Blockers

- Classification: FAIL
- The shell's active `python` is Python 3.14.6 at `C:\Python314\python.exe`.
- That interpreter lacks at least `pytest` and `pandas`.
- It also differs from ASTRA's production-target Python 3.12 runtime.
- Until the intended project environment is activated or dependencies are installed for the selected interpreter, contractual tests, scheduler status, readiness, provider probing, and safe retraining cannot be verified.
- No evidence was collected that would justify classifying the code, statistical quality, data/provenance, model eligibility, or provider/network as failed; those areas remain pending behind the environment blocker.

## Final Classification

NOT READY — ENVIRONMENT

## Python 3.12 Environment Recovery

- Classification: PASS
- Python 3.12 availability: `Python 3.12.6` at `C:\Users\nicol\AppData\Local\Programs\Python\Python312\python.exe`.
- Existing `.venv`: absent.
- `.venv/` ignore rule confirmed from `.gitignore:74`.
- Created with `py -3.12 -m venv .venv`.
- Virtual-environment interpreter: `Python 3.12.6`.
- pip upgraded inside `.venv` from `24.2` to `26.2.1`.
- Installed only `requirements-dev.txt` and its declared includes.
- pytest: `9.1.1`.
- Required import probe: PASS (`pandas`, `numpy`, `sklearn`, `xgboost`, `lightgbm`, `optuna`, `yfinance`).
- pandas: `3.0.5`.
- numpy: `2.5.2`.
- No global Python installation was modified and Python 3.14 was not used for ASTRA after environment recovery.

Import probe output:

```text
IMPORTS_OK
pandas 3.0.5
numpy 2.5.2
```

## Focused Contract Tests — Python 3.12 Retry

- Classification: FAIL
- Command exit code: `1`.
- Passed: `47`.
- Failed assertions: `0` observed.
- Setup errors: `168`.
- Skipped: `0`.
- Warnings: `2`.
- Duration: `103.01s`.
- The first 15 WFV statistical tests passed before tests requiring pytest temporary fixtures encountered the environment error.
- All reported errors share the same root cause: the OS denies enumeration of pytest's global temporary root `C:\Users\nicol\AppData\Local\Temp\pytest-of-Nicoo`.
- This is classified as an environment/ACL failure, not evidence of a Forex assertion failure.
- The two warnings report the same access problem for the repository `.pytest_cache`.

Representative complete root-cause traceback:

```text
root = WindowsPath('C:/Users/nicol/AppData/Local/Temp/pytest-of-Nicoo')
prefix = 'pytest-'

def find_prefixed(root: Path, prefix: str) -> Iterator[os.DirEntry[str]]:
    """Find all elements in root that begin with the prefix, case-insensitive."""
    l_prefix = prefix.lower()
>   for x in os.scandir(root):
             ^^^^^^^^^^^^^^^^
E   PermissionError: [WinError 5] Acceso denegado: 'C:\\Users\\nicol\\AppData\\Local\\Temp\\pytest-of-Nicoo'

.venv\Lib\site-packages\_pytest\pathlib.py:175: PermissionError
```

Pytest summary:

```text
47 passed, 2 warnings, 168 errors in 103.01s (0:01:43)
```

No retry with altered pytest arguments was used to authorize retraining. The verification contract states that any focused-suite failure blocks retraining for this run.

## Full Suite — Python 3.12

- Classification: PENDING
- Not executed because the focused suite did not pass completely.

## Scheduler Status — Python 3.12

- Classification: FAIL
- Command exit code: `0`; the command itself completed and produced valid JSON.
- Scheduler health is false because the local runtime registry contains no active symbols and no H1 execution evidence.
- Active symbols: `0`.
- Expected datasets: `0`.
- Verified-ready datasets: `0`.
- Registry inconsistencies: `0`.
- Predictions: `0`.
- Last run: `null`.
- No stale/interrupted run was reported because no last run exists.

Complete JSON:

```json
{
  "symbols_active": 0,
  "datasets_ready": 0,
  "datasets_error": 0,
  "predictions_total": 0,
  "degraded_models": 0,
  "last_run": null,
  "healthy": false,
  "db_engine": "sqlite",
  "db_path": "C:\\Users\\nicol\\Downloads\\IA-LOCAL-v710-final - WORKING\\IA-LOCAL-v710-final\\memory_db\\astra_autonomous.db",
  "datasets_verified_ready": 0,
  "datasets_registry_inconsistent": 0,
  "datasets_expected": 0,
  "health_evidence": "registry_and_persisted_csv_verified"
}
```

No H1 cycle was executed.

## Production Readiness — Python 3.12

- Classification: FAIL
- Offline command exit code: `0`; readiness completed normally and returned `NOT READY`.
- Total checks: `35`.
- Passed: `25`.
- Failed: `1`.
- Warned: `6`.
- Pending: `3`.
- Blocking count: `4`.

Complete offline summary and blocking evidence:

```json
{
  "timestamp": "2026-08-29T03:09:55.237225+00:00",
  "ready": false,
  "status": "error",
  "global_status": "NOT READY",
  "summary": {
    "ready": false,
    "status": "error",
    "total_checks": 35,
    "passed": 25,
    "failed": 1,
    "warned": 6,
    "pending": 3,
    "blocking_count": 4,
    "global_status": "NOT READY"
  },
  "blocking_reasons": [
    "Autenticación API: ASTRA_API_KEY ausente",
    "Conexión y registry: 0 símbolo(s) activo(s)",
    "Ejecución registrada: No H1 scheduler run has been recorded",
    "Adquisición operacional verificada: Probe de red no ejecutado; disponibilidad de import no prueba operación"
  ],
  "warnings": [
    "redis (opcional): No instalado (opcional)",
    "faiss-cpu (opcional): No instalado (opcional)",
    "torch (opcional): No instalado (opcional)",
    "tensorflow (opcional): No instalado (opcional)",
    "MetaTrader5 (opcional): No instalado (opcional)",
    "Estructura de directorios: Faltan: logs"
  ]
}
```

Complete check inventory:

- PASS — Python 3.12.6 on Windows AMD64.
- PASS — pandas 3.0.5, numpy 2.5.2, scikit-learn 1.9.0, xgboost 3.4.1, lightgbm 4.7.0, optuna 4.9.0, requests 2.34.2, fastapi 0.141.1, uvicorn 0.52.4, colorama 0.4.6, rich, orjson 3.12.0, filelock 3.32.4, psutil 7.2.2, openai 3.6.0, and yfinance 1.7.0.
- WARN — optional redis, faiss-cpu, torch, tensorflow, and MetaTrader5 are not installed.
- PASS — `infra/config/astra.env` exists; no contents or secrets were recorded.
- FAIL — `ASTRA_API_KEY` is absent.
- PASS — chat SDK configuration is available; no key value was exposed.
- PENDING — database/registry query verified `0` active symbols.
- PENDING — no H1 scheduler run has been recorded.
- PASS — Yahoo is importable; MT5 is not importable and remains optional on this platform.
- PENDING — operational acquisition was not probed in the offline run.
- WARN — `logs` directory is absent.
- PASS — declared write permissions on existing directories.
- PASS — four systemd service manifests are present; no service was activated.
- PASS — FastAPI static contract is present.
- PASS — approximately 4.5 GB RAM and 192.2 GB disk were available.

## Operational Provider Probe

- Classification: FAIL
- Command exit code: `0`; readiness completed normally and returned `NOT READY`.
- No market request could be associated with a production symbol because the registry has no active production route.
- This is a configuration/registry failure, not demonstrated external network failure.
- Total checks: `35`.
- Passed: `25`.
- Failed: `2`.
- Warned: `6`.
- Pending: `2`.
- Blocking count: `4`.

Complete operational summary and blocking evidence:

```json
{
  "timestamp": "2026-08-29T03:10:18.038345+00:00",
  "ready": false,
  "status": "error",
  "global_status": "NOT READY",
  "summary": {
    "ready": false,
    "status": "error",
    "total_checks": 35,
    "passed": 25,
    "failed": 2,
    "warned": 6,
    "pending": 2,
    "blocking_count": 4,
    "global_status": "NOT READY"
  },
  "blocking_reasons": [
    "Autenticación API: ASTRA_API_KEY ausente",
    "Conexión y registry: 0 símbolo(s) activo(s)",
    "Ejecución registrada: No H1 scheduler run has been recorded",
    "Adquisición operacional verificada: none: No active production route is configured"
  ],
  "warnings": [
    "redis (opcional): No instalado (opcional)",
    "faiss-cpu (opcional): No instalado (opcional)",
    "torch (opcional): No instalado (opcional)",
    "tensorflow (opcional): No instalado (opcional)",
    "MetaTrader5 (opcional): No instalado (opcional)",
    "Estructura de directorios: Faltan: logs"
  ]
}
```

Provider checks:

- PASS — Yahoo importable; MT5 unavailable/optional on Windows verification host.
- FAIL — operational acquisition: `none: No active production route is configured` (`VERIFIED_FAILED`).

No provider configuration was changed to force a pass.

## EURUSD Pre-Retrain

- Classification: PENDING
- Not executed because the focused suite did not pass completely.
- The scheduler/readiness evidence also shows zero active symbols, so the required EURUSD production registry state was not established.
- Alias, hashes, model audit, retrain history, provenance, datasets, candle counts, and eligibility were not inspected.

## EURUSD Manual Retrain

- Classification: PENDING
- The command with request ID `verify-eurusd-20260828-02` was not executed.
- No retrain run, candidate, staging, promotion, or database mutation was created.

## WFV Evidence

- Classification: PENDING
- No retrain was executed, so no WFV fold or aggregate evidence was generated.

## Post-Retrain Integrity

- Classification: PENDING
- No retrain occurred; post-retrain alias/provenance comparison is therefore not applicable.

## Updated Remaining Blockers

- Classification: FAIL
- ENVIRONMENT — pytest cannot access its global temporary root due Windows ACL (`WinError 5`), producing 168 setup errors and preventing a clean contractual-suite result.
- ENVIRONMENT — pytest also cannot write `.pytest_cache`; this is warning-only but corroborates local filesystem ACL restrictions.
- CONFIGURATION — `ASTRA_API_KEY` is absent.
- DATA/PROVENANCE — the local database registry has zero active production symbols and therefore zero expected/verified datasets.
- SCHEDULER — no H1 scheduler run has been recorded.
- PROVIDER/ROUTING — no active production route exists, so operational acquisition cannot be verified.
- The recovered Python 3.12 environment and declared required imports themselves pass.
- No code defect, statistical-quality failure, or model-eligibility failure was established because their gated checks could not complete.

## Updated Final Classification

NOT READY — MULTIPLE BLOCKERS

## Pytest Isolated Temp Retry

- Classification: PASS
- External temp root: `C:\Users\nicol\astra_pytest_temp`.
- The root is outside the repository.
- A single probe file was created successfully and then removed successfully.
- No system ACL was changed.
- pytest was run with only these infrastructure adjustments:
  - `-p no:cacheprovider`
  - `--basetemp=C:\Users\nicol\astra_pytest_temp\focused` or `...\full`
- `.venv\Scripts\python.exe` remained Python `3.12.6`.
- No DB, CSV, PKL, environment file, test, or product source file was changed.

The isolated run proves that the preceding `WinError 5` result came from pytest's default global temp/cache locations rather than from Forex test assertions.

## Focused Suite Final Result

- Classification: PASS — CONTRACT TESTS
- Passed: `215`.
- Failed: `0`.
- Errors: `0`.
- Skipped: `0`.
- Warnings: `7`.
- Duration: `111.91s`.

```text
215 passed, 7 warnings in 111.91s (0:01:51)
```

Warnings are deprecations only:

- Five `datetime.utcnow()` warnings from `deployment/pipeline_report.py`.
- Two `datetime.utcnow()` warnings from `forex/portfolio/portfolio_ranker.py`.

No code assertion, dependency-compatibility, or test-semantic failure was observed.

## Full Suite Result

- Classification: PASS — CONTRACT TESTS
- Passed: `639`.
- Failed: `0`.
- Errors: `0`.
- Skipped: `10`.
- Warnings: `13`.
- Subtests passed: `23`.
- Duration: `170.28s`.

```text
639 passed, 10 skipped, 13 warnings, 23 subtests passed in 170.28s (0:02:50)
```

Expected skips:

- Five repository-dataset integration tests are opt-in through `ASTRA_RUN_INTEGRATION_TESTS=1`.
- Five scheduler activation shell-harness tests require POSIX process semantics.

Warnings are deprecations only:

- Two FastAPI `on_event` deprecations.
- Nine `datetime.utcnow()` warnings from `deployment/pipeline_report.py`.
- Two `datetime.utcnow()` warnings from `forex/portfolio/portfolio_ranker.py`.

## Existing Legacy Dataset Inventory

- Classification: WARN
- Root: `forex/data`.
- Existing requested datasets: `12/12`.
- These are legacy/local paths, not the canonical production paths defined by `runtime_paths.py`.

- `forex/data/EURUSD_H1.csv`: 5,542 bytes; 100 rows; first `2026-01-01 00:00:00`; last `2026-01-05 03:00:00`; columns `timestamp, open, high, low, close, volume, pair`; SHA256 `ad2b72cd5228e67f21a74f134d15ee866ccdc2967042244f87c60027b61ca847`.
- `forex/data/EURUSD_H4.csv`: 12,577 bytes; 121 rows; first `2026-07-07 20:00:00`; last `2026-08-04 04:00:00`; columns `timestamp, open, high, low, close, volume, pair`; SHA256 `9c64a673c7b4c9d50b0023d2da697a67867bc5d020f8f0f4f0861dd758cfd956`.
- `forex/data/EURUSD_D1.csv`: 6,397 bytes; 67 rows; first `2026-05-04`; last `2026-08-04`; columns `timestamp, open, high, low, close, volume, pair`; SHA256 `22e7dc1fbc22751781c65aa8afd0642f21af634421040939e7ebc16bf2613e81`.
- `forex/data/USDJPY_H1.csv`: 10,560 bytes; 102 rows; first `2026-07-28 23:00:00`; last `2026-08-04 05:00:00`; columns `timestamp, open, high, low, close, volume, pair`; SHA256 `d2176503c3df0b86bc945700b3245df227332c531a99e2be33b7206ca4b0cdf1`.
- `forex/data/USDJPY_H4.csv`: 12,510 bytes; 121 rows; first `2026-07-07 20:00:00`; last `2026-08-04 04:00:00`; columns `timestamp, open, high, low, close, volume, pair`; SHA256 `b039c3ea3d22d77f4980193eb61c13a362a209fa3314ac5404f771e57d57873d`.
- `forex/data/USDJPY_D1.csv`: 6,326 bytes; 67 rows; first `2026-05-04`; last `2026-08-04`; columns `timestamp, open, high, low, close, volume, pair`; SHA256 `bd1bf7962f5b0ee99d6de2cd02b3c06ae2220be88b3583329211d28ac9ac59a5`.
- `forex/data/GBPUSD_H1.csv`: 10,654 bytes; 102 rows; first `2026-07-28 23:00:00`; last `2026-08-04 05:00:00`; columns `timestamp, open, high, low, close, volume, pair`; SHA256 `1442445a9fecf4fb1d9370d729ccd9b00b0b6d7ba6c88de8e27c769cb4a5f99d`.
- `forex/data/GBPUSD_H4.csv`: 12,632 bytes; 121 rows; first `2026-07-07 20:00:00`; last `2026-08-04 04:00:00`; columns `timestamp, open, high, low, close, volume, pair`; SHA256 `fe0da91413f4204660856668c1429acda4f7a2131f58b14958b8db2bdcc948eb`.
- `forex/data/GBPUSD_D1.csv`: 6,393 bytes; 67 rows; first `2026-05-04`; last `2026-08-04`; columns `timestamp, open, high, low, close, volume, pair`; SHA256 `8d007dbc67864ab5b4f4df3f88dac5fe9ff89033d7414293233f6c6e2022a80a`.
- `forex/data/AUDUSD_H1.csv`: 10,703 bytes; 102 rows; first `2026-07-28 23:00:00`; last `2026-08-04 05:00:00`; columns `timestamp, open, high, low, close, volume, pair`; SHA256 `a086b9087681a0a7214668073b1a6f9c4e96b3446d3d522aad6e73b6fe18b2a9`.
- `forex/data/AUDUSD_H4.csv`: 12,692 bytes; 121 rows; first `2026-07-09 20:00:00`; last `2026-08-06 04:00:00`; columns `timestamp, open, high, low, close, volume, pair`; SHA256 `c4e6978381615a718d42c261941779ac2e5a65e348d12d8ccabf633b0e510480`.
- `forex/data/AUDUSD_D1.csv`: 6,431 bytes; 67 rows; first `2026-05-04`; last `2026-08-04`; columns `timestamp, open, high, low, close, volume, pair`; SHA256 `5333388fedceaad4b2e5df9b1410297e8eea34ea57fd40ba1177741f1762cb7c`.

These row counts are below the normal 2,000-row rolling production contract and are not treated as canonical readiness evidence.

## Existing Canonical Dataset Inventory

- Classification: FAIL
- `runtime_paths.forex_dataset_root()` resolves to `data/forex` under the repository root.
- Canonical root exists: no.
- Existing requested canonical datasets: `0/12`.

Absent canonical paths:

- `data/forex/EURUSD_H1.csv`, `EURUSD_H4.csv`, `EURUSD_D1.csv`.
- `data/forex/USDJPY_H1.csv`, `USDJPY_H4.csv`, `USDJPY_D1.csv`.
- `data/forex/GBPUSD_H1.csv`, `GBPUSD_H4.csv`, `GBPUSD_D1.csv`.
- `data/forex/AUDUSD_H1.csv`, `AUDUSD_H4.csv`, `AUDUSD_D1.csv`.

No directory or dataset was created during the audit.

## Existing Model Inventory

- Classification: WARN
- Requested production aliases found: `2/4`.
- No artifact was deserialized; inventory used filesystem metadata and streaming SHA256 only.

- `models/forex/latest_EURUSD.pkl`: exists; 1,571,452 bytes; SHA256 `cf22ead0e88f5a71c730e4462e3ac7e29503e9652067c73ffa2cb41f649a9c07`.
- `models/forex/latest_USDJPY.pkl`: exists; 1,105,395 bytes; SHA256 `9692aff3eac992ce9b50c61c04fa7bdeee3f307cef34753e8812fc088c19af42`.
- `models/forex/latest_GBPUSD.pkl`: absent.
- `models/forex/latest_AUDUSD.pkl`: absent.

Alias presence alone is not production eligibility evidence because the registry and provenance tables are empty.

## Existing Database State

- Classification: WARN
- Database: `memory_db/astra_autonomous.db`.
- Exists: yes.
- Size: 114,688 bytes.
- Opened through SQLite URI `mode=ro` and closed after queries.
- Tables: `config`, `dataset_registry`, `model_provenance`, `model_quality`, `outcomes`, `predictions`, `retrain_runs`, `scheduler_runs`, `sqlite_sequence`, `supported_symbols`.
- `supported_symbols`: 0.
- Symbol status counts: candidate 0; qualified 0; active 0; disabled 0.
- `dataset_registry`: 0.
- `retrain_runs`: 0.
- `model_provenance`: 0.
- `scheduler_runs`: 0.
- `predictions`: 0.

The schema exists, but the audited runtime state is empty. No row was inserted, updated, or deleted.

## ASTRA_API_KEY Metadata

- `variable declared`: no.
- `value configured`: no.
- No environment value was read or displayed.

## Runtime Bootstrap Gap Analysis

- Classification: A — artifacts exist but the new registry is empty.
- Demonstrated existing artifacts:
  - 12 legacy/local CSV datasets under `forex/data`.
  - 2 model aliases under `models/forex`.
  - SQLite schema at `memory_db/astra_autonomous.db`.
- Demonstrated missing canonical/runtime evidence:
  - canonical dataset root `data/forex` is absent;
  - zero active/candidate/qualified/disabled symbols;
  - zero dataset registry rows;
  - zero model provenance rows;
  - zero retrain, scheduler, and prediction rows;
  - `ASTRA_API_KEY` is neither declared nor configured;
  - no active production provider route can be selected.
- This is not called corruption: the evidence shows a legacy-artifact/new-runtime bootstrap gap.
- No migration, registration, qualification, activation, copying, retraining, or scheduler execution was attempted.

Current component classification:

- Code: PASS — CONTRACT TESTS.
- Test infrastructure: PASS with isolated external pytest temp root.
- Runtime bootstrap/data registry: FAIL/PENDING.
- Model eligibility/provenance: PENDING; aliases exist but have no canonical registry provenance.
- Provider operation: PENDING behind absent active route.
- API authentication configuration: FAIL locally.

Current overall classification:

NOT READY — MULTIPLE BLOCKERS

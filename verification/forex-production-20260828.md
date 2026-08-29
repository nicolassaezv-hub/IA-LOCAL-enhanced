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

## Controlled EURUSD Bootstrap

- Classification: FAIL — stopped fail-closed at qualification.
- Initial branch/HEAD: `codex/forex-production-verification-20260828` at `2e7cd18d1b75732a1822dbe44cb675e5e7dd4523`.
- Python: `.venv\Scripts\python.exe`, version `3.12.6`.
- Initial Git state: clean apart from ignored local runtime artifacts.
- Scope remained EURUSD only; USDJPY, GBPUSD, and AUDUSD were not registered, qualified, initialized, or trained.
- EURUSD was registered through `scripts/manage_symbol_lifecycle.py register-candidate EURUSD`.
- Registration returned `ok=true`, symbol id `1`, status `candidate`, and `activation_origin=managed`.
- Qualification returned exit code `1` and `result=FAIL`; all later mutating gates were skipped.

## EURUSD Qualification

- Classification: FAIL.
- Qualification timestamp: `2026-08-29T03:49:09.200428+00:00`.
- Catalog version: `6f2a7b3f0266099c311dcbb3defa55981e12483ed7c2766104f5b44ccef1a855`.
- Evidence path: `data/qualification/EURUSD/evidence.json`.
- Evidence SHA256: `8b4f4d12d7f7098d281d914062eae07aa07d213754ec42883c370b5e4d69688c`.
- MT5 was unavailable for every timeframe. Data acquisition then succeeded through the catalogued Yahoo fallback, producing 2,000-row isolated candidate CSVs, but validation failed before provider fields could be persisted in the per-timeframe evidence object.

H1 evidence:

- Result: FAIL.
- Provider route used: Yahoo fallback after `MT5 unavailable`.
- Row count written to isolated qualification CSV: 2,000.
- First timestamp: `2026-05-04 19:00:00`.
- Last timestamp: `2026-08-28 21:00:00`.
- Candidate CSV SHA256: `6e82fb2a4a1be9b340b205ae653212385b12c3ed7b7f6c8000db4a3d6c39b814`.
- Validation errors:
  - `RSI_14` independent recalculation mismatch (`max_abs=0.308891`, `max_rel=0.00597543`).
  - `MACD` mismatch (`max_abs=1.23649e-08`, `max_rel=6.64948e-05`).
  - `ATR_14` mismatch (`max_abs=5.1949e-09`, `max_rel=5.18474e-06`).

H4 evidence:

- Result: FAIL.
- Provider route used: Yahoo fallback after `MT5 unavailable`.
- Row count written to isolated qualification CSV: 2,000.
- First timestamp: `2025-04-29 04:00:00`.
- Last timestamp: `2026-08-28 16:00:00`.
- Candidate CSV SHA256: `869f533f78abf20513878930f9f0ab226403f4f70dbe0a12e482d5fde08a9338`.
- Validation errors:
  - `RSI_14` mismatch (`max_abs=0.704857`, `max_rel=0.0144445`).
  - `MACD` mismatch (`max_abs=5.87117e-08`, `max_rel=0.000186085`).
  - `MACD_signal` mismatch (`max_abs=2.70489e-09`, `max_rel=4.05187e-06`).
  - `ATR_14` mismatch (`max_abs=1.13328e-08`, `max_rel=3.43244e-06`).

D1 evidence:

- Result: FAIL.
- Provider route used: Yahoo fallback after `MT5 unavailable`.
- Row count written to isolated qualification CSV: 2,000.
- First timestamp: `2018-12-21`.
- Last timestamp: `2026-08-28`.
- Candidate CSV SHA256: `b055a4f2ef2ea2f827906e24bcacc51adbb022023b30fe2b66deb0db99acfcff`.
- Validation errors:
  - 52 malformed/non-positive OHLC rows.
  - `RSI_14` mismatch (`max_abs=1.30266`, `max_rel=0.0317327`).
  - `MACD` mismatch (`max_abs=3.04178e-07`, `max_rel=0.000704016`).
  - `MACD_signal` mismatch (`max_abs=1.40137e-08`, `max_rel=7.16263e-06`).
  - `MACD_hist` mismatch (`max_abs=4.48439e-09`, `max_rel=0.000141573`).
  - `ATR_14` mismatch (`max_abs=8.86883e-08`, `max_rel=1.23451e-05`).

Cross-timeframe evidence:

- Status: FAIL, blocking.
- Error: `Missing validated timeframe frames: ['D1', 'H1', 'H4']`.
- No cross-timeframe details were accepted because every individual timeframe failed validation.

Post-qualification lifecycle state:

- `status=candidate`.
- `qualification_evidence_path=null` in `supported_symbols`.
- `qualification_sha256=null` in `supported_symbols`.
- `qualified_at=null`.
- The failed evidence remains isolated under `data/qualification/EURUSD`; it was not adopted into production registry state.

## Canonical Dataset Creation

- Classification: FAIL/PENDING — deliberately not executed after qualification failure.
- `data/forex/EURUSD_H1.csv`: absent.
- `data/forex/EURUSD_H4.csv`: absent.
- `data/forex/EURUSD_D1.csv`: absent.
- `dataset_registry` rows for EURUSD: `0`.
- The rolling-update command was not invoked and no legacy CSV was copied.

## Legacy Model Quarantine

- Classification: PASS.
- Original alias SHA256 before move: `cf22ead0e88f5a71c730e4462e3ac7e29503e9652067c73ffa2cb41f649a9c07`.
- Original `models/forex/latest_EURUSD.pkl`: absent after quarantine.
- Preserved path: `models/forex/legacy_unverified/latest_EURUSD_cf22ead0e88f5a71c730e4462e3ac7e29503e9652067c73ffa2cb41f649a9c07.pkl`.
- Preserved SHA256: `cf22ead0e88f5a71c730e4462e3ac7e29503e9652067c73ffa2cb41f649a9c07`.
- The preserved artifact remains ignored by Git and can be restored explicitly if required.
- `latest_USDJPY.pkl` was not moved or modified; its SHA256 remains `9692aff3eac992ce9b50c61c04fa7bdeee3f307cef34753e8812fc088c19af42`.

## Initial Training Evidence

- Classification: PENDING/NOT EXECUTED.
- The initial-training entrypoint was not invoked because EURUSD did not reach `qualified` and canonical datasets were not created.
- `retrain_runs` rows for EURUSD: `0`.
- `model_provenance` rows for EURUSD: `0`.
- No candidate model was staged or published.

## Quality Gate Evidence

- Classification: PENDING.
- No training dataset reached the quality-gate entrypoint.

## WFV Evidence

- Classification: PENDING.
- No WFV folds, TP/FP counts, signals, aggregate precision, pooled precision, evidence-sufficiency decision, or WFV result were generated.

## Calibration and Validation

- Classification: PENDING.
- Calibration, validation precision, `model_valid`, and `model_deployed` were not evaluated.

## Initial Model Promotion

- Classification: PENDING/NOT EXECUTED.
- `models/forex/latest_EURUSD.pkl` remains absent.
- The quarantined legacy alias remains intact.
- No provenance record claims EURUSD is production eligible.

## EURUSD Activation

- Classification: FAIL/NOT ATTEMPTED.
- Activation was not invoked because qualification failed.
- Final lifecycle status: `candidate`, not `qualified` or `active`.
- `activation_origin` remains `managed` from registration metadata; this does not mean the symbol was activated.

## Single H1 Runtime Cycle

- Classification: PENDING/NOT EXECUTED.
- No session-only `ASTRA_API_KEY` was generated because the activation gate was never reached.
- No H1 scheduler command was executed.
- `scheduler_runs`: `0`.
- `predictions`: `0`.

## Post-Bootstrap Production Readiness

- Classification: PENDING/NOT EXECUTED.
- The post-bootstrap readiness probe was not run because the controlled bootstrap stopped at qualification.
- The last demonstrated readiness state from the preceding phase remains `NOT READY`; this run produced no evidence that could remove its blockers.

## Final EURUSD Runtime State

- Symbol: `candidate`.
- Qualification: failed; failed evidence isolated and not adopted.
- Canonical datasets: 0/3.
- Dataset registry rows: 0.
- Executable latest EURUSD alias: absent.
- Legacy EURUSD artifact: preserved with original SHA.
- Retrain runs: 0.
- Model provenance rows: 0.
- Scheduler runs: 0.
- Predictions: 0.
- Fail-closed behavior: PASS.

## Remaining Blockers

- Qualification provider data failed the independent dataset contract for all three timeframes.
- D1 contains 52 malformed/non-positive OHLC rows.
- H1/H4/D1 indicator columns differ from independent recalculation beyond the contract tolerances.
- Cross-timeframe validation cannot run successfully without three individually validated frames.
- EURUSD cannot become qualified, receive canonical production datasets, train, promote, activate, or enter H1 scheduling until qualification evidence passes honestly.
- No threshold, provider configuration, dataset, model, test, or product code was altered to force a pass.

## Final Viability Decision

NOT READY — MULTIPLE CONTRACT DEFECTS

## EURUSD Qualification Root-Cause Analysis

- Analysis date: `2026-08-29`.
- Scope: read-only analysis of the existing isolated qualification artifacts plus in-memory Yahoo queries. Qualification was not repeated, and no DB, CSV, model, alias, threshold, or production source was changed.
- Git baseline: branch `codex/forex-production-verification-20260828`, HEAD `4ba2cb38963a5c6da7c53c158f13d07e3d05d7a6`.
- Python: `.venv\Scripts\python.exe`, version `3.12.6`.
- EURUSD remained `status=candidate`; its qualification evidence, qualification SHA, and qualified timestamp remained null in the registry.
- The existing failed artifacts remained under `data/qualification/EURUSD/` and were only read.
- Yahoo connectivity: PASS. Both requested D1 downloads completed successfully. `MT5 unavailable` caused the expected provider fallback, not a network failure.
- The qualification failure has two independent families of causes:
  - the rolling writer calculates recursive indicators on 2,001 rows and then persists the last 2,000, while the qualification oracle restarts those calculations on only the persisted 2,000 and begins comparing before all EWM initial-state differences meet its strict tolerance;
  - Yahoo's raw D1 OHLC includes malformed envelopes, and both the Yahoo adapter and rolling dataset contract accept those rows before qualification rejects them.

## Indicator Context Reproduction

`RollingDataset.apply()` currently executes these operations in this order:

1. merge, de-duplicate, sort, and remove incomplete candles;
2. `recalculate_tail_indicators(candidate, k=len(candidate))` over all 2,001 qualification bars;
3. `candidate.tail(2000)`;
4. persist and validate the rolling dataset.

The requested reproduction recalculated each existing 2,000-row CSV with `recalculate_tail_indicators(frame.copy(), k=len(frame))`. For H1, H4, and D1, every requested recalculated indicator was bit-for-bit equal to `_independent_indicators(frame)` over every comparable row: maximum absolute error `0`, maximum relative error `0`, no mismatch index, and final-row error `0`. This proves that the formulas agree and isolates the mismatch to EWM initialization context/order of operations.

The following measurements compare the persisted value against the recalculation on only the persisted 2,000 rows. `rows` begins at the current `_indicator_start()`; `first` and `last` are zero-based indices that fail `rtol=1e-6, atol=1e-9`; `-` means every value in the validation range passes. `last_abs` is the absolute error at row 1,999.

```text
H1 indicator   rows  max_abs         max_rel         first  last  last_abs
RSI_14         1931  0.308890601189  0.00597542577   69     201   1.94689e-12
MACD           1871  1.23648887e-08  6.64947940e-05  129    154   2.84495e-16
MACD_signal    1826  5.69660176e-10  9.25437334e-07  -      -     2.32236e-16
MACD_hist      1826  1.82291085e-10  4.15357820e-05  -      -     5.22585e-17
ATR_14         1931  5.19490446e-09  5.18474224e-06  69     75    2.86229e-17
EMA20          1901  1.23228909e-08  1.04686597e-08  -      -     0
EMA50          1751  1.24096051e-08  1.06512600e-08  -      -     0
EMA200         1001  1.24251309e-08  1.08787987e-08  -      -     5.63327e-13

H4 indicator   rows  max_abs         max_rel         first  last  last_abs
RSI_14         1931  0.704857494214  0.0144445021    69     193   3.12639e-13
MACD           1871  5.87116798e-08  0.000186084869  129    176   4.52546e-16
MACD_signal    1826  2.70489245e-09  4.05186925e-06  174    180   4.59322e-16
MACD_hist      1826  8.65565524e-10  2.07877252e-05  -      -     9.31330e-17
ATR_14         1931  1.13327742e-08  3.43244114e-06  69     76    4.03323e-17
EMA20          1901  5.85122635e-08  5.18302193e-08  -      -     0
EMA50          1751  5.89240055e-08  5.08447993e-08  -      -     2.22045e-16
EMA200         1001  5.89977256e-08  5.05132816e-08  -      -     2.67786e-12

D1 indicator   rows  max_abs         max_rel         first  last  last_abs
RSI_14         1931  1.30265962064   0.0317327291    69     209   0
MACD           1871  3.04178416e-07  0.000704015566  129    181   2.97505e-16
MACD_signal    1826  1.40137344e-08  7.16262566e-06  174    187   2.55872e-16
MACD_hist      1826  4.48439321e-09  0.000141573332  174    188   4.09557e-17
ATR_14         1931  8.86882680e-08  1.23451440e-05  69     87    1.73472e-18
EMA20          1901  3.03145265e-07  2.70366052e-07  -      -     0
EMA50          1751  3.05278451e-07  2.75987231e-07  -      -     0
EMA200         1001  3.05660384e-07  2.92184305e-07  -      -     1.38756e-11
```

The apparent nonzero `max_rel` for passing rows is compatible with `np.allclose` because the acceptance formula combines relative and absolute tolerance. The important invariant is that recalculation on the persisted slice and the independent oracle are exactly equal; persisted-with-one-prior-row context and slice-only recalculation are not.

## Indicator Convergence Analysis

At each requested start index, the persisted values were compared to `_independent_indicators(frame)` through the last row. The first tested passing index is below; every earlier requested index failed and that index plus every later requested index passed.

| Indicator | H1 first tested pass | H4 first tested pass | D1 first tested pass | Current `_indicator_start()` |
|---|---:|---:|---:|---:|
| `RSI_14` | 300 | 200 | 300 | 69 |
| `MACD` | 200 | 200 | 200 | 129 |
| `MACD_signal` | 200 | 200 | 200 | 174 |
| `MACD_hist` | 200 | 200 | 200 | 174 |
| `ATR_14` | 100 | 100 | 100 | 69 |
| `EMA20` | 70 | 70 | 100 | 99 |
| `EMA50` | 150 | 200 | 300 | 249 |
| `EMA200` | 750 | 750 | 1000 | 999 |

The exact requested index vectors were `70, 100, 150, 200, 300, 500, 750, 1000, 1250, 1500`. A first tested pass does not imply that the immediately preceding integer fails. Direct comparison at the actual configured starts explains the qualification result: H1 fails RSI/MACD/ATR; H4 fails RSI/MACD/MACD_signal/ATR; D1 fails RSI/MACD/MACD_signal/MACD_hist/ATR. Other requested indicators pass at their configured starts.

The current warm-up is not mathematically sufficient for the demanded tolerance. It is generally `minimum_history * 5 - 1`. For a recursive EWM, an initial-state difference decays as `(1-alpha)^n`. To reduce only that decay factor to at most `1e-6` requires approximately 187 updates for RSI(14), 97 for ATR span 14, 180 for the slow MACD EMA(26), 139 for EMA20, 346 for EMA50, and 1,382 for EMA200. At the current starts the corresponding residual factors are about `6.02e-3` for RSI and `4.6e-5` to `5.2e-5` for the span-based EWMs, not `1e-6`. Relative error near zero can require still more context. The current data happen to converge earlier for some columns, but the warm-up has no general mathematical guarantee at `rtol=1e-6, atol=1e-9`.

## Yahoo D1 Invalid OHLC Analysis

The 52 persisted D1 failures are malformed OHLC envelopes, not non-positive prices and not `low > high` rows.

| Exact failed conditions | Rows |
|---|---:|
| `close > high` | 16 |
| `close < low` | 13 |
| `open > high` and `close > high` | 12 |
| `open < low` and `close < low` | 11 |
| Any `open/high/low/close <= 0` | 0 |
| `low > high` | 0 |

Weekday distribution: Monday 17, Thursday 12, Wednesday 10, Tuesday 8, Friday 5. Representative rows show the four observed combinations:

| Timestamp | Weekday | Open | High | Low | Close | Failure |
|---|---|---:|---:|---:|---:|---|
| `2019-03-04` | Monday | 1.137527 | 1.137527 | 1.131055 | 1.137592 | `close > high` |
| `2020-05-20` | Wednesday | 1.093016 | 1.099904 | 1.092920 | 1.092777 | `close < low` |
| `2022-04-29` | Friday | 1.050420 | 1.059042 | 1.050542 | 1.050420 | `open < low`, `close < low` |
| `2022-12-26` | Monday | 1.066780 | 1.063717 | 1.060895 | 1.066780 | `open > high`, `close > high` |

The malformed rows span `2019-03-04` through `2026-08-17`; they are not a single outage or one calendar cluster. Direct download reproduced all 52 timestamps exactly.

## Yahoo auto_adjust Comparison

Read-only `yfinance 1.7.0` downloads used the same provider start calculation (`2018-06-01`, interval `1d`) and completed successfully.

| Mode | Raw/closed rows | Invalid in full response | Invalid in final 2,001 | Invalid in final 2,000 | Overlap with persisted 52 |
|---|---:|---:|---:|---:|---:|
| `auto_adjust=True` | 2,145 | 56 | 52 | 52 | 52/52 |
| `auto_adjust=False` | 2,145 | 56 | 52 | 52 | 52/52 |

- The invalid timestamp sets are identical between adjustment modes. Turning adjustment off does not solve the defect.
- Yahoo availability and connectivity are therefore PASS.
- `repair=True` is supported by this installed yfinance version and was tested only in memory. It returned 2,150 closed rows, but 44 remained invalid in the full response and 40 remained invalid in the final 2,001. Standard repair is not sufficient for ASTRA's OHLC contract and must not be treated as an automatic fix.

Safe-filter simulation on `auto_adjust=True`:

- Closed rows before provider `tail`: 2,145.
- Unequivocally invalid rows: 56.
- Valid rows remaining: 2,089.
- Valid headroom above the requested 2,001: 88.
- At least 2,000 valid rows are available: yes.
- The last 2,000 valid rows span `2018-10-09` through `2026-08-28`.
- Causal gap classification after filtering: 388 `WEEKEND`, 52 `INVALID_GAP` intervals containing 53 removed malformed rows, 4 pre-existing `PROVIDER_GAP`, and 0 proven `EXPECTED_MARKET_CLOSURE` under the current code contract.
- The four pre-existing non-weekend gaps are `2019-05-21 -> 2019-05-23`, `2024-12-31 -> 2025-01-02`, `2025-12-24 -> 2025-12-26`, and `2025-12-31 -> 2026-01-02`. Some are plausibly market closures, but ASTRA has no market-calendar proof and currently labels all four `PROVIDER_GAP`.
- The current `classify_gaps()` has no knowledge of sanitization provenance. On the safely filtered final 2,000 it labels 411 gaps `WEEKEND` and 33 `PROVIDER_GAP`; 29 of those provider gaps were actually created by dropping malformed Yahoo rows and 4 were already present in raw Yahoo timestamps.
- Therefore filtering alone supplies enough rows but does not yield qualification PASS: the 33 current `PROVIDER_GAP` classifications remain blocking. This is a new visible blocker after the malformed rows are removed, not a reason to retain invalid OHLC.

## Provider Headroom Analysis

`YahooProvider.fetch(EURUSD, D1, bars=2001)` computes:

- `needed_bars = 2001`;
- `days_needed = int(2001 * 1.5) + 10 = 3011` calendar days;
- provider start `2018-06-01` for this run;
- 2,145 normalized and closed D1 rows before `tail(bars)`;
- 2,089 valid rows if the OHLC contract is applied before the tail.

The calendar headroom was sufficient for this observed response. The implementation nevertheless returns `df.tail(2001)` before any finite/positive/envelope sanitation. Consequently it returned 2,001 rows containing 52 malformed rows, only 1,949 valid rows. The problem is ordering and absent validation, not insufficient raw history in this run. The code also does not assert that at least `bars` valid rows remain after a future sanitation step; a safe implementation must filter first, verify the post-filter count, and only then take the final requested tail or fail closed.

## Contract Validation Matrix

Legend: YES means enforced by the named functions; PARTIAL means only a subset is enforced; NO means accepted or not checked. Yahoo closed-candle behavior occurs in `fetch()` after `_normalize_df` for D1/H4, not in `_normalize_df` itself.

| Rule | `YahooProvider._normalize_df` | `RollingDataset.normalize_dataset / validate_dataset` | `validate_dataset_frame` |
|---|---|---|---|
| finite OHLC | PARTIAL: drops NaN OHLC, accepts infinity | YES | YES |
| OHLC > 0 | NO | NO | YES |
| `low <= high` | NO | NO | YES |
| open within low/high | NO | NO | YES |
| close within low/high | NO | NO | YES |
| duplicate timestamp | NO | YES | YES |
| closed candle | NO in `_normalize_df`; D1/H4 only in `fetch()` | NO in named validators; `apply()` filters separately | YES |
| indicators | NO | PARTIAL: presence and some finite values, not numerical correctness | YES: independent formula/tolerance comparison |
| exact 2,000 rows | NO; returns at most requested `bars` | NO: only `len <= max_rows` | YES |

This matrix identifies two inevitable late failures. Yahoo normalization and rolling validation accept malformed positive OHLC envelopes that qualification rejects. Separately, rolling writes context-dependent indicator values that the qualification oracle attempts to reproduce without that context and with an insufficient warm-up.

## Root-Cause Classification

- A. NETWORK FAILURE: not supported; both Yahoo comparison downloads succeeded.
- B. YAHOO AVAILABILITY FAILURE: not supported; Yahoo returned 2,145 D1 rows in both modes.
- C. PROVIDER RAW DATA QUALITY: confirmed; the raw Yahoo response itself contains 56 malformed envelope rows, including the exact 52 in the final 2,000.
- D. YAHOO ADAPTER NORMALIZATION DEFECT: confirmed; `_normalize_df` drops NaN but accepts infinity, non-positive prices, and malformed OHLC envelopes, and `fetch()` tails before enforcing the downstream contract.
- E. ROLLING DATASET CONTRACT DEFECT: confirmed; rolling validation accepts the same malformed OHLC and persists recursive indicators before reducing to the contractual 2,000-row artifact.
- F. QUALIFICATION VALIDATOR DEFECT: confirmed; `_indicator_start()` is not mathematically sufficient for its strict EWM comparison and produces false indicator failures when persisted values legitimately contain the one-row prior context.
- Selected classification: **G. MULTIPLE CONTRACT DEFECTS (C + D + E + F)**.

The cross-timeframe failure is derivative: all three frames were excluded after their individual failures. It is not an independent provider/network cause.

## Recommended Minimal Fix

Indicator options:

- OPTION 1 — recalculate after reducing to rolling 2,000: recommended as the smallest deterministic artifact contract. It makes the persisted CSV self-contained and exactly reproducible by the independent oracle. It introduces no future data and therefore no lookahead leakage. It changes early-window recursive values relative to context-preserving history, so focused feature/model compatibility tests and fresh training evidence are required; last-row errors observed here are already negligible.
- OPTION 2 — retain prior context and use a mathematically correct validation warm-up: preserves the more history-aware recursive state but is harder to guarantee under relative tolerance near zero, discards more rows from independent validation, and leaves the artifact non-reproducible without documenting its hidden initial state. Merely relaxing tolerances is not acceptable.
- OPTION 3 — make provider context explicit and validate using exactly that context: best preserves full-history semantics and reproducibility, but requires persisting/proving the context and updating rolling provenance. It is more robust than an arbitrary warm-up but materially larger than the minimum fix.

D1 options:

- OPTION A — reject the entire Yahoo frame as soon as any malformed OHLC is found: safest and simplest fail-closed adapter contract, but it leaves EURUSD D1 unavailable with the observed Yahoo data.
- OPTION B — drop only unequivocally invalid raw rows before `tail(bars)`, request/verify enough headroom, and retain explicit sanitization-gap provenance: recommended ingestion direction because this run demonstrates 2,089 valid bars. It must still fail closed on fewer than 2,001 valid rows. It does not by itself make qualification pass because current gap validation turns the removed observations into blocking provider gaps; gap provenance/market-closure validation needs an explicit, separately tested contract rather than a relaxed threshold.
- OPTION C — expand high/low or otherwise synthesize repaired OHLC: not recommended without authoritative provider evidence. Although many discrepancies are small, silently changing prices would fabricate market observations and yfinance `repair=True` still leaves 40 invalid final rows.

Recommended combined minimum: **indicator OPTION 1 plus D1 OPTION B with post-filter count verification and explicit fail-closed gap provenance**. Until the resulting gap contract is implemented and tested honestly, EURUSD must remain a candidate and viability remains `NOT READY — MULTIPLE CONTRACT DEFECTS`.

## Missing Regression Tests

- Rolling indicator context versus persisted slice: initialize 2,001 OHLC rows, persist 2,000, and assert the chosen indicator contract is independently reproducible at `rtol=1e-6, atol=1e-9`.
- Qualification 2,001-to-2,000 ordering: prove whether tailing occurs before or after indicator calculation and prevent a hidden prior-row EWM state from contradicting the validation oracle.
- Per-indicator convergence: cover RSI, MACD, MACD signal/histogram, ATR, EMA20/50/200 with a nonconstant real-like series and assert the configured warm-up is mathematically sufficient rather than merely passing constant fixtures.
- Yahoo D1 malformed OHLC: include positive but invalid rows where open/close lie outside low/high; existing tests only prove the final qualification rejection, not adapter behavior.
- Yahoo normalization finite/positive/envelope contract: cover NaN, infinity, zero/negative OHLC, `low > high`, and open/close outside the envelope before provider tailing.
- Provider sanitation with headroom: inject more rows than requested, remove malformed rows before the tail, verify exactly 2,001 valid closed rows remain, and fail closed when they do not.
- Sanitization gap provenance: distinguish `INVALID_GAP`, `WEEKEND`, proven `EXPECTED_MARKET_CLOSURE`, and unexplained `PROVIDER_GAP` without silently reclassifying or ignoring missing observations.
- Real-like Yahoo fallback qualification: MT5 unavailable, Yahoo returns 2,145 rows with the reproduced malformed pattern, and the flow either produces an honestly valid 2,000-row isolated artifact or fails at the adapter with a precise cause.
- `auto_adjust=True/False` parity and `repair=True` insufficiency fixtures, without live-network dependence.
- Contract-consistency test spanning `_normalize_df`, rolling validation, and qualification so no earlier layer accepts data that must inevitably be rejected downstream.

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

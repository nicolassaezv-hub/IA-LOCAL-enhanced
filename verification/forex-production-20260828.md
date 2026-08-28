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

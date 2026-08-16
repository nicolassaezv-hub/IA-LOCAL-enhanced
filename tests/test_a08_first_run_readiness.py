"""A-08: evidence-based, fail-closed first-run and production readiness."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd

from deployment.production_readiness import (
    _existing_sqlite_path,
    evaluate_dataset_registry_entry,
    run_production_readiness,
)
from forex.data.indicator_delta import recalculate_tail_indicators
from forex.data.rolling_dataset import ROLLING_WINDOW, validate_dataset
from infra.db.database import SQLiteDatabase
from robustness.first_run_wizard import FirstRunWizard
import runtime_paths


def _frame(rows: int, *, indicators: bool = True) -> pd.DataFrame:
    values = pd.Series(range(rows), dtype=float)
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=rows, freq="h"),
        "open": 1.08 + values / 10000,
        "high": 1.085 + values / 10000,
        "low": 1.075 + values / 10000,
        "close": 1.082 + values / 10000,
        "volume": 1000.0,
        "pair": "EURUSD",
    })
    return recalculate_tail_indicators(frame, k=len(frame)) if indicators else frame


def _database(tmp_path: Path) -> SQLiteDatabase:
    db = SQLiteDatabase(str(tmp_path / "readiness.db"))
    db.add_symbol("EURUSD", "EUR/USD", 0.0001)
    return db


def _register(
    db: SQLiteDatabase,
    path: Path,
    frame: pd.DataFrame | None,
    *,
    status: str = "ready",
    candle_count: int | None = None,
    last_timestamp: str | None = None,
) -> dict:
    entry = {
        "symbol": "EURUSD",
        "timeframe": "H1",
        "status": status,
        "candle_count": len(frame) if candle_count is None and frame is not None else candle_count,
        "rolling_window_size": ROLLING_WINDOW,
        "last_candle_timestamp": (
            str(frame["timestamp"].iloc[-1])
            if last_timestamp is None and frame is not None
            else last_timestamp
        ),
        "blob_path": str(path),
    }
    return db.upsert_dataset_registry(entry)


def _dataset_check(report, name: str = "Dataset EURUSD/H1") -> dict:
    return next(check for check in report.to_dict()["checks"] if check["check"] == name)


def _model_check(report) -> dict:
    return next(check for check in report.to_dict()["checks"] if check["check"] == "Modelo EURUSD/H1")


def _run_for_h1(tmp_path: Path, db: SQLiteDatabase, **kwargs):
    return run_production_readiness(
        base_dir=tmp_path,
        db=db,
        required_timeframes=("H1",),
        **kwargs,
    )


def test_false_positive_ready_metadata_with_missing_csv_is_blocked(tmp_path):
    """Historical defect: plausible metadata must not override broken bytes."""
    db = _database(tmp_path)
    missing = tmp_path / "EURUSD_H1.csv"
    _register(
        db,
        missing,
        None,
        candle_count=ROLLING_WINDOW,
        last_timestamp="2020-03-24 07:00:00",
    )

    report = _run_for_h1(tmp_path, db, require_models=False)
    check = _dataset_check(report)

    assert report.ready is False
    assert check["status"] == "fail"
    assert check["evidence_state"] == "INVALID"
    assert "does not exist" in check["detail"]


def test_2000_ohlcv_rows_without_required_indicators_are_not_ready(tmp_path):
    db = _database(tmp_path)
    path = tmp_path / "EURUSD_H1.csv"
    frame = _frame(ROLLING_WINDOW, indicators=False)
    frame.to_csv(path, index=False)
    _register(db, path, frame)

    report = _run_for_h1(tmp_path, db, require_models=False)

    assert report.ready is False
    assert _dataset_check(report)["status"] == "fail"
    assert "Missing required indicator columns" in _dataset_check(report)["detail"]


def test_valid_short_dataset_remains_pending(tmp_path):
    db = _database(tmp_path)
    path = tmp_path / "EURUSD_H1.csv"
    frame = _frame(150)
    validate_dataset(frame, ROLLING_WINDOW)
    frame.to_csv(path, index=False)
    _register(db, path, frame, status="pending")

    report = _run_for_h1(tmp_path, db, require_models=False)
    check = _dataset_check(report)

    assert report.ready is False
    assert check["status"] == "pending"
    assert check["evidence_state"] == "PENDING"
    assert "Persisted candle count is 150" in check["detail"]


def test_exactly_2000_valid_closed_candles_satisfy_dataset_contract(tmp_path):
    path = tmp_path / "EURUSD_H1.csv"
    frame = _frame(ROLLING_WINDOW)
    validate_dataset(frame, ROLLING_WINDOW)
    frame.to_csv(path, index=False)
    entry = {
        "symbol": "EURUSD",
        "timeframe": "H1",
        "status": "ready",
        "candle_count": ROLLING_WINDOW,
        "rolling_window_size": ROLLING_WINDOW,
        "last_candle_timestamp": str(frame["timestamp"].iloc[-1]),
        "blob_path": str(path),
    }

    evidence = evaluate_dataset_registry_entry(entry, base_dir=tmp_path)

    assert evidence == {
        "ready": True,
        "status": "ready",
        "path": str(path.resolve()),
        "actual_candle_count": ROLLING_WINDOW,
        "reasons": [],
    }


def test_registry_metadata_mismatch_with_csv_is_blocking(tmp_path):
    db = _database(tmp_path)
    path = tmp_path / "EURUSD_H1.csv"
    frame = _frame(ROLLING_WINDOW)
    frame.to_csv(path, index=False)
    _register(
        db,
        path,
        frame,
        candle_count=ROLLING_WINDOW - 1,
        last_timestamp="1999-01-01 00:00:00",
    )

    report = _run_for_h1(tmp_path, db, require_models=False)
    detail = _dataset_check(report)["detail"]

    assert report.ready is False
    assert "Registry candle_count" in detail
    assert "last_candle_timestamp" in detail


def test_scheduler_health_revalidates_ready_registry_bytes(tmp_path):
    from scheduler.autonomous_scheduler import get_status

    db = _database(tmp_path)
    _register(
        db,
        tmp_path / "missing.csv",
        None,
        candle_count=ROLLING_WINDOW,
        last_timestamp="2020-03-24 07:00:00",
    )

    health = get_status(db)

    assert health["healthy"] is False
    assert health["datasets_registry_inconsistent"] == 1
    assert health["datasets_verified_ready"] == 0
    assert health["health_evidence"] == "registry_and_persisted_csv_verified"


def test_dummy_or_synthetic_named_dataset_cannot_be_production_ready(tmp_path):
    db = _database(tmp_path)
    path = tmp_path / "synthetic_EURUSD_H1.csv"
    frame = _frame(ROLLING_WINDOW)
    frame.to_csv(path, index=False)
    _register(db, path, frame)

    report = _run_for_h1(tmp_path, db, require_models=False)
    check = _dataset_check(report)

    assert report.ready is False
    assert check["status"] == "fail"
    assert "non-production" in check["detail"] or "marker" in check["detail"]


def test_missing_mandatory_model_is_blocking(tmp_path):
    db = _database(tmp_path)
    report = _run_for_h1(tmp_path, db, require_models=True)
    check = _model_check(report)

    assert report.ready is False
    assert check["status"] == "fail"
    assert check["evidence_state"] == "MISSING"


def test_historical_model_does_not_replace_missing_canonical_latest(tmp_path):
    db = _database(tmp_path)
    models = tmp_path / "models" / "forex"
    models.mkdir(parents=True)
    (models / "ensemble_EURUSD_20260811T120000.pkl").write_bytes(
        b"valid-historical-model" * 200
    )

    def historical_must_not_be_checked(_path, _symbol):
        raise AssertionError("historical model must not be certified")

    report = _run_for_h1(
        tmp_path,
        db,
        require_models=True,
        model_checker=historical_must_not_be_checked,
    )
    check = _model_check(report)

    assert report.ready is False
    assert check["status"] == "fail"
    assert check["evidence_state"] == "MISSING"


def test_corrupt_model_fails_integrity_without_loading_real_models(tmp_path):
    db = _database(tmp_path)
    models = tmp_path / "models" / "forex"
    models.mkdir(parents=True)
    corrupt = models / "latest_EURUSD.pkl"
    corrupt.write_bytes(b"not-a-pickle" * 200)

    report = _run_for_h1(tmp_path, db, require_models=True)
    check = _model_check(report)

    assert report.ready is False
    assert check["status"] == "fail"
    assert check["evidence_state"] == "INVALID/CORRUPT"
    assert "Error al cargar" in check["detail"]


def test_missing_optional_dependency_is_warning_and_does_not_crash(tmp_path):
    db = _database(tmp_path)
    from deployment import production_readiness as readiness_module

    real_try_import = readiness_module._try_import

    def optional_redis_missing(module):
        if module == "redis":
            return False, "No instalado"
        return real_try_import(module)

    with patch.object(readiness_module, "_try_import", side_effect=optional_redis_missing):
        report = _run_for_h1(tmp_path, db, require_models=False)

    redis_check = next(
        check for check in report.to_dict()["checks"]
        if check["check"] == "redis (opcional)"
    )
    assert redis_check["status"] == "warn"
    assert redis_check["blocking"] is False
    assert report.ready is False  # other critical evidence remains pending


def test_exception_inside_critical_check_fails_closed(tmp_path):
    db = _database(tmp_path)
    models = tmp_path / "models" / "forex"
    models.mkdir(parents=True)
    artifact = models / "latest_EURUSD.pkl"
    artifact.write_bytes(b"boundary-stub" * 200)

    def exploding_checker(_path, _symbol):
        raise RuntimeError("integrity boundary unavailable")

    report = _run_for_h1(
        tmp_path,
        db,
        require_models=True,
        model_checker=exploding_checker,
    )
    check = _model_check(report)

    assert report.ready is False
    assert check["status"] == "fail"
    assert "integrity boundary unavailable" in check["detail"]


def test_repeated_readiness_is_deterministic_and_does_not_modify_resources(tmp_path):
    db = _database(tmp_path)
    path = tmp_path / "EURUSD_H1.csv"
    frame = _frame(ROLLING_WINDOW)
    frame.to_csv(path, index=False)
    _register(db, path, frame)
    before_bytes = path.read_bytes()
    before_mtime = path.stat().st_mtime_ns

    first = _run_for_h1(tmp_path, db, require_models=False)
    second = _run_for_h1(tmp_path, db, require_models=False)

    assert first.ready == second.ready
    assert first.status == second.status
    assert _dataset_check(first) == _dataset_check(second)
    assert path.read_bytes() == before_bytes
    assert path.stat().st_mtime_ns == before_mtime


def test_readiness_creates_no_dataset_model_or_configuration(tmp_path):
    db = _database(tmp_path)
    before = sorted(
        (path.relative_to(tmp_path), path.read_bytes())
        for path in tmp_path.rglob("*") if path.is_file()
    )

    report = _run_for_h1(tmp_path, db, require_models=True)

    after = sorted(
        (path.relative_to(tmp_path), path.read_bytes())
        for path in tmp_path.rglob("*") if path.is_file()
    )
    assert report.ready is False
    assert after == before
    assert not (tmp_path / "astra.env").exists()
    assert not (tmp_path / "models").exists()
    assert not (tmp_path / "CSVs").exists()


def test_first_run_wizard_does_not_create_placeholder_model(tmp_path):
    wizard = FirstRunWizard(project_root=tmp_path)

    step = wizard.step_7_train_initial_models()

    assert step.status == "PENDING"
    assert "no placeholder model was created" in step.detail
    assert not list(tmp_path.rglob("*.json"))


def test_first_run_and_readiness_share_canonical_database_registry(tmp_path):
    db_path = tmp_path / "canonical.db"
    dataset_path = tmp_path / "EURUSD_H1.csv"
    frame = _frame(ROLLING_WINDOW)
    frame.to_csv(dataset_path, index=False)
    scheduler_backends = []

    def initialize_registry(db):
        scheduler_backends.append(Path(db.db_path).resolve())
        db.add_symbol("EURUSD", "EUR/USD", 0.0001)
        _register(db, dataset_path, frame)
        return [{"action": "generated"}]

    with patch.dict(
        "os.environ",
        {"ASTRA_DB_ENGINE": "sqlite", "ASTRA_DB_PATH": str(db_path)},
    ), patch(
        "scheduler.autonomous_scheduler.run_init",
        side_effect=initialize_registry,
    ):
        first_run = FirstRunWizard(project_root=tmp_path).step_6_generate_initial_csvs()
        readiness = run_production_readiness(
            base_dir=tmp_path,
            required_timeframes=("H1",),
            require_models=False,
        )

    assert first_run.status == "PASS"
    assert scheduler_backends == [db_path.resolve()]
    assert _dataset_check(readiness)["status"] == "pass"
    assert not (tmp_path / "memory_db" / "memoria.db").exists()


def test_readiness_and_factory_share_project_relative_database_across_cwd(
    monkeypatch, tmp_path
):
    from infra.db.database import get_database

    project_root = tmp_path / "opt" / "astra"
    unrelated_cwd = tmp_path / "service-cwd"
    unrelated_cwd.mkdir(parents=True)
    monkeypatch.setattr(runtime_paths, "PROJECT_ROOT", project_root)
    monkeypatch.setenv("ASTRA_DB_ENGINE", "sqlite")
    monkeypatch.setenv("ASTRA_DB_PATH", "memory_db/astra_autonomous.db")

    database = get_database()
    database.add_symbol("EURUSD", "EUR/USD", 0.0001)
    canonical_path = Path(database.db_path)
    monkeypatch.chdir(unrelated_cwd)

    report = run_production_readiness(
        base_dir=project_root,
        required_timeframes=(),
        require_models=False,
        probe_providers=False,
    )
    database_check = next(
        check for check in report.to_dict()["checks"]
        if check["category"] == "4. Base de datos"
    )
    provider_check = next(
        check for check in report.to_dict()["checks"]
        if check["check"] == "Adquisición operacional verificada"
    )

    assert canonical_path == project_root / "memory_db" / "astra_autonomous.db"
    assert _existing_sqlite_path(project_root) == canonical_path
    assert database_check["status"] == "pass"
    assert database_check["detail"] == "1 símbolo(s) activo(s)"
    assert provider_check["status"] == "pending"
    assert provider_check["evidence_state"] == "UNVERIFIED"
    assert not (unrelated_cwd / "memory_db").exists()


def test_first_run_wizard_does_not_convert_not_ready_report_to_pass(tmp_path):
    wizard = FirstRunWizard(project_root=tmp_path)
    result = {
        "ready": False,
        "status": "pending",
        "deployment_status": "SUCCESS",
        "readiness_status": "PENDING",
        "blocking_reasons": ["provider operation unverified"],
    }

    with patch(
        "deployment.first_run_validator.run_first_deployment_check",
        return_value=result,
    ) as readiness:
        step = wizard.step_10_run_deployment_validation()

    assert step.status == "PENDING"
    assert "provider operation unverified" in step.detail
    readiness.assert_called_once_with(
        symbols=["EURUSD"],
        timeframe="H1",
        force=True,
        probe_providers=True,
    )


def test_provider_operation_is_pending_without_explicit_probe(tmp_path):
    db = _database(tmp_path)

    def probe_must_not_run():
        raise AssertionError("probe_providers=False must not acquire data")

    report = _run_for_h1(
        tmp_path,
        db,
        require_models=False,
        provider_probe=probe_must_not_run,
    )
    provider_check = next(
        check for check in report.to_dict()["checks"]
        if check["check"] == "Adquisición operacional verificada"
    )

    assert provider_check["status"] == "pending"
    assert provider_check["evidence_state"] == "UNVERIFIED"
    assert report.ready is False


def test_completed_h1_noop_is_not_operational_scheduler_evidence(tmp_path):
    db = _database(tmp_path)
    run = db.create_scheduler_run({"timeframe": "H1"})
    db.update_scheduler_run(run["id"], {
        "status": "completed",
        "symbols_processed": 0,
        "predictions_generated": 0,
        "errors_count": 0,
    })

    report = _run_for_h1(tmp_path, db, require_models=False)
    check = next(
        item for item in report.to_dict()["checks"]
        if item["category"] == "7. Scheduler"
    )

    assert check["status"] == "pending"
    assert check["evidence_state"] == "COMPLETED_NOOP"
    assert "symbols_processed=0" in check["detail"]


def test_completed_h1_hold_cycle_is_valid_scheduler_evidence(tmp_path):
    db = _database(tmp_path)
    run = db.create_scheduler_run({"timeframe": "H1"})
    db.update_scheduler_run(run["id"], {
        "status": "completed",
        "symbols_processed": 1,
        "predictions_generated": 0,
        "errors_count": 0,
    })

    report = _run_for_h1(tmp_path, db, require_models=False)
    check = next(
        item for item in report.to_dict()["checks"]
        if item["category"] == "7. Scheduler"
    )

    assert check["status"] == "pass"
    assert check["evidence_state"] == "PROCESSED_CYCLE"
    assert "predictions_generated=0" in check["detail"]

def test_explicit_provider_probe_uses_mocked_boundary_without_network(tmp_path):
    db = _database(tmp_path)
    calls = []

    def probe():
        calls.append("called")
        return {"operational": True, "provider": "stub", "detail": "closed candle returned"}

    report = _run_for_h1(
        tmp_path,
        db,
        require_models=False,
        probe_providers=True,
        provider_probe=probe,
    )
    provider_check = next(
        check for check in report.to_dict()["checks"]
        if check["check"] == "Adquisición operacional verificada"
    )

    assert calls == ["called"]
    assert provider_check["status"] == "pass"
    assert provider_check["evidence_state"] == "VERIFIED_OPERATIONAL"


class _ProviderRouterStub:
    outcomes = {}
    calls = []

    def __init__(self, pair, timeframe):
        self.pair = pair
        self.timeframe = timeframe
        self.asset_type = "crypto" if pair.startswith(("BTC", "ETH")) else "forex"
        self.source_used = None

    def fetch(self, *, bars, raise_on_failure):
        type(self).calls.append((self.pair, self.timeframe, bars, raise_on_failure))
        outcome = type(self).outcomes[self.asset_type]
        if isinstance(outcome, Exception):
            raise outcome
        self.source_used = "Binance" if self.asset_type == "crypto" else "Yahoo"
        return pd.DataFrame({"close": [1.0] * outcome})


def _provider_check(report):
    return next(
        check for check in report.to_dict()["checks"]
        if check["category"] == "8. Proveedores"
        and check["check"].startswith("Adquisici")
    )


def test_active_forex_ok_and_crypto_failure_blocks_readiness(tmp_path):
    db = _database(tmp_path)
    db.add_symbol("BTCUSDT", "BTC/USDT", 0.01)
    _ProviderRouterStub.outcomes = {
        "forex": 2,
        "crypto": RuntimeError("crypto provider unavailable"),
    }
    _ProviderRouterStub.calls = []

    with patch("forex.data.data_router.DataRouter", _ProviderRouterStub):
        report = _run_for_h1(
            tmp_path,
            db,
            require_models=False,
            probe_providers=True,
        )

    check = _provider_check(report)
    assert report.ready is False
    assert check["status"] == "fail"
    assert check["evidence_state"] == "VERIFIED_FAILED"
    assert "crypto provider unavailable" in check["detail"]
    assert {call[0] for call in _ProviderRouterStub.calls} == {"EURUSD", "BTCUSDT"}
    assert all(call[2:] == (2, True) for call in _ProviderRouterStub.calls)


def test_all_active_provider_routes_are_operational(tmp_path):
    db = _database(tmp_path)
    db.add_symbol("GBPUSD", "GBP/USD", 0.0001)
    db.add_symbol("BTCUSDT", "BTC/USDT", 0.01)
    _ProviderRouterStub.outcomes = {"forex": 2, "crypto": 2}
    _ProviderRouterStub.calls = []

    with patch("forex.data.data_router.DataRouter", _ProviderRouterStub):
        report = _run_for_h1(
            tmp_path,
            db,
            require_models=False,
            probe_providers=True,
        )

    check = _provider_check(report)
    assert check["status"] == "pass"
    assert check["evidence_state"] == "VERIFIED_OPERATIONAL"
    assert {call[0] for call in _ProviderRouterStub.calls} == {"EURUSD", "BTCUSDT"}


def test_basic_self_test_health_remains_diagnostic_only():
    from check_system import run_self_test

    with patch("check_system._check", side_effect=lambda label, _fn: ("ok", label)):
        result = run_self_test(verbose=False)

    assert result["diagnostic_passed"] is True
    assert result["healthy"] is True
    assert result["production_ready"] is False
    assert result["readiness_scope"] == "diagnostic_only"

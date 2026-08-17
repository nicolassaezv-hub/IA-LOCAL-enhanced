"""Regression coverage for interrupted scheduler/bootstrap durable state."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from deployment.production_readiness import run_production_readiness
from forex.prediction.model_storage import ModelStorage
from forex.prediction.retrain_manager import RetrainManager
from infra.db.database import SQLiteDatabase
from scheduler.run_state import is_scheduler_run_stale


FIXED_NOW = datetime(2026, 8, 16, 6, 0, tzinfo=timezone.utc)


def _legacy_alias(monkeypatch, manager: RetrainManager, storage: ModelStorage):
    with monkeypatch.context() as patch:
        patch.setattr(
            RetrainManager,
            "_initial_eligibility_error",
            staticmethod(lambda _metadata: ""),
        )
        manager.promote_initial_model(
            SimpleNamespace(version="legacy", sufficient=True),
            pair="EURUSD",
            dataset_provenance={"path": "EURUSD_H1.csv"},
            metadata={"precision": 0.70},
        )
    return storage.base_dir / "latest_EURUSD.pkl"


def _bootstrap_manager(monkeypatch, tmp_path, *, timeout=None, now=None):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    storage = ModelStorage(tmp_path / "models" / "forex")
    config = {} if timeout is None else {"running_timeout_seconds": timeout}
    manager = RetrainManager(
        database=database,
        storage=storage,
        config=config,
        now_func=(lambda: now) if now is not None else None,
    )
    latest = _legacy_alias(monkeypatch, manager, storage)
    run = manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance={"registry_id": 1}
    )
    return database, storage, manager, latest, run


def _claim(database, run, when):
    claimed = database.claim_retrain_run(run["run_id"], "test-owner", when)
    assert claimed is not None
    return claimed


def test_stale_running_bootstrap_reuses_identity_and_runs_normally(monkeypatch, tmp_path):
    database, _storage, manager, _latest, run = _bootstrap_manager(
        monkeypatch, tmp_path, now=FIXED_NOW
    )
    stale = (FIXED_NOW - timedelta(minutes=61)).isoformat()
    _claim(database, run, stale)

    recovered = manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance={"registry_id": 2}
    )

    assert recovered["run_id"] == run["run_id"]
    assert recovered["evidence_key"] == run["evidence_key"]
    assert recovered["status"] == "PENDING"
    promoted = manager.execute_retrain(
        recovered["run_id"],
        lambda *_args: SimpleNamespace(version="replacement", sufficient=True),
        validator=lambda model: model.sufficient is True,
    )
    assert promoted["status"] == "PROMOTED"
    assert manager.audit_pair_model("EURUSD")["eligible"] is True


@pytest.mark.parametrize(
    "gate", ["WFV_GATE", "VALIDATION_GATE", "CALIBRATION_GATE", "QUALITY_GATE"]
)
def test_failed_bootstrap_quality_gates_remain_one_shot(
    monkeypatch, tmp_path, gate
):
    database, _storage, manager, _latest, run = _bootstrap_manager(
        monkeypatch, tmp_path, now=FIXED_NOW
    )
    database.update_retrain_run(run["run_id"], {
        "status": "FAILED",
        "error": f"ValueError: QUALITY_GATE: {gate}",
        "updated_at": (FIXED_NOW - timedelta(days=1)).isoformat(),
    })

    repeated = manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance={"registry_id": 999}
    )

    assert repeated["run_id"] == run["run_id"]
    assert repeated["status"] == "FAILED"
    assert gate in repeated["error"]
    assert len([
        item for item in database.get_retrain_runs("EURUSD")
        if item["trigger"] == "bootstrap_revalidation"
    ]) == 1


def test_stale_bootstrap_with_changed_source_checksum_never_retries(
    monkeypatch, tmp_path
):
    database, storage, manager, latest, run = _bootstrap_manager(
        monkeypatch, tmp_path, now=FIXED_NOW
    )
    stale = (FIXED_NOW - timedelta(minutes=61)).isoformat()
    _claim(database, run, stale)
    replacement = storage.stage_model(
        SimpleNamespace(version="unrelated", sufficient=True),
        name="unrelated",
        version="v2",
    )
    latest.write_bytes(replacement.read_bytes())

    assert manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance={"registry_id": 2}
    ) is None
    stored = next(
        item for item in database.get_retrain_runs("EURUSD")
        if item["run_id"] == run["run_id"]
    )
    assert stored["status"] == "FAILED"
    assert "CHECKSUM_MISMATCH" in stored["error"]


def test_recent_running_bootstrap_is_not_taken_over(monkeypatch, tmp_path):
    database, _storage, manager, _latest, run = _bootstrap_manager(
        monkeypatch, tmp_path, now=FIXED_NOW
    )
    _claim(database, run, (FIXED_NOW - timedelta(minutes=59)).isoformat())

    repeated = manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance={"registry_id": 2}
    )

    assert repeated["run_id"] == run["run_id"]
    assert repeated["status"] == "RUNNING"


def test_bootstrap_stale_timeout_can_be_extended_by_environment(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("ASTRA_RETRAIN_RUNNING_TIMEOUT_SECONDS", "7200")
    database, _storage, manager, _latest, run = _bootstrap_manager(
        monkeypatch, tmp_path, now=FIXED_NOW
    )
    _claim(database, run, (FIXED_NOW - timedelta(minutes=61)).isoformat())

    repeated = manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance={"registry_id": 2}
    )

    assert repeated["run_id"] == run["run_id"]
    assert repeated["status"] == "RUNNING"


@pytest.mark.parametrize(
    ("minutes_old", "expected_stale"),
    [(59, False), (61, True)],
)
def test_scheduler_stale_boundary_uses_fixed_utc_clock(
    monkeypatch, minutes_old, expected_stale
):
    monkeypatch.delenv("ASTRA_SCHEDULER_STALE_SECONDS", raising=False)
    run = {
        "status": "running",
        "started_at": (FIXED_NOW - timedelta(minutes=minutes_old)).isoformat(),
    }

    assert is_scheduler_run_stale(run, now=FIXED_NOW) is expected_stale


def test_scheduler_stale_timeout_can_be_extended_by_environment(monkeypatch):
    monkeypatch.setenv("ASTRA_SCHEDULER_STALE_SECONDS", "7200")
    run = {
        "status": "running",
        "started_at": (FIXED_NOW - timedelta(minutes=61)).isoformat(),
    }

    assert is_scheduler_run_stale(run, now=FIXED_NOW) is False


def test_stale_scheduler_run_is_interrupted_before_new_cycle(monkeypatch, tmp_path):
    from scheduler import autonomous_scheduler

    database = SQLiteDatabase(str(tmp_path / "scheduler.sqlite"))
    stale = database.create_scheduler_run({
        "timeframe": "H4",
        "started_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "status": "running",
    })
    monkeypatch.setattr(autonomous_scheduler, "detect_new_symbols", lambda _db: [])

    result = autonomous_scheduler.run_cycle(database, "H4")
    runs = {item["id"]: item for item in database.get_scheduler_runs()}

    assert runs[stale["id"]]["status"] == "interrupted"
    assert runs[stale["id"]]["finished_at"]
    assert runs[stale["id"]]["recovered_at"]
    assert "not completed" in runs[stale["id"]]["interruption_reason"]
    assert runs[result["run_id"]]["status"] == "completed"


def test_recent_scheduler_run_is_not_recovered_accidentally(monkeypatch, tmp_path):
    from scheduler import autonomous_scheduler

    database = SQLiteDatabase(str(tmp_path / "scheduler.sqlite"))
    active = database.create_scheduler_run({
        "timeframe": "D1",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
    })
    monkeypatch.setattr(autonomous_scheduler, "detect_new_symbols", lambda _db: [])

    autonomous_scheduler.run_cycle(database, "H4")
    stored = {item["id"]: item for item in database.get_scheduler_runs()}[active["id"]]

    assert stored["status"] == "running"
    assert stored["recovered_at"] is None


def test_readiness_reports_stale_running_scheduler_as_blocking(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "readiness.sqlite"))
    database.add_symbol("EURUSD", "EUR/USD", 0.0001)
    database.create_scheduler_run({
        "timeframe": "H1",
        "started_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "status": "running",
    })

    report = run_production_readiness(
        base_dir=tmp_path,
        db=database,
        required_timeframes=(),
        require_models=False,
    )
    check = next(
        item for item in report.to_dict()["checks"]
        if item["category"] == "7. Scheduler"
    )

    assert check["status"] == "fail"
    assert check["evidence_state"] == "STALE/INTERRUPTED"
    assert report.ready is False


def test_readiness_blocks_integrity_valid_but_legacy_ineligible(
    monkeypatch, tmp_path
):
    database = SQLiteDatabase(str(tmp_path / "readiness.sqlite"))
    database.add_symbol("EURUSD", "EUR/USD", 0.0001)
    storage = ModelStorage(tmp_path / "models" / "forex")
    manager = RetrainManager(database=database, storage=storage)
    _legacy_alias(monkeypatch, manager, storage)

    report = run_production_readiness(
        base_dir=tmp_path,
        db=database,
        required_timeframes=(),
        model_checker=lambda *_args: {"status": "ok", "issues": []},
    )
    check = next(
        item for item in report.to_dict()["checks"]
        if item["check"] == "Modelo EURUSD/H1"
    )

    assert check["status"] == "fail"
    assert check["evidence_state"] == "INTEGRITY_VALID_NOT_PRODUCTION_ELIGIBLE"
    assert "WFV_EVIDENCE_MISSING" in check["detail"]


def test_readiness_accepts_integrity_valid_promoted_eligible_model(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "readiness.sqlite"))
    database.add_symbol("EURUSD", "EUR/USD", 0.0001)
    storage = ModelStorage(tmp_path / "models" / "forex")
    manager = RetrainManager(database=database, storage=storage)
    now = datetime.now(timezone.utc).isoformat()
    run = database.create_retrain_run({
        "run_id": "retrain_eligible",
        "evidence_key": "eligible-evidence",
        "symbol": "EURUSD",
        "timeframe": "H1",
        "trigger": "manual",
        "status": "PENDING",
        "dataset_provenance": {"registry_id": 1},
        "outcome_ids": [],
        "created_at": now,
        "updated_at": now,
    })
    promoted = manager.execute_retrain(
        run["run_id"],
        lambda *_args: SimpleNamespace(version="eligible", sufficient=True),
        validator=lambda model: model.sufficient is True,
    )
    assert promoted["status"] == "PROMOTED"

    report = run_production_readiness(
        base_dir=tmp_path,
        db=database,
        required_timeframes=(),
        model_checker=lambda *_args: {"status": "ok", "issues": []},
    )
    check = next(
        item for item in report.to_dict()["checks"]
        if item["check"] == "Modelo EURUSD/H1"
    )
    assert check["status"] == "pass"
    assert check["evidence_state"] == "VALID"


@pytest.mark.parametrize(
    ("result", "expected_code", "expected_ok"),
    [
        ({"init_results": [{"action": "ready"}], "deployment": {"ready": True}}, 0, True),
        ({"init_results": [{"action": "ready"}], "deployment": {"ready": False}}, 2, False),
        ({"init_results": [{"action": "ready"}], "deployment_error": "internal"}, 1, False),
    ],
)
def test_init_cli_exit_code_matches_deployment_result(
    monkeypatch, capsys, result, expected_code, expected_ok
):
    from scheduler import autonomous_scheduler

    monkeypatch.setattr(sys, "argv", ["autonomous_scheduler.py", "--init"])
    monkeypatch.setattr(autonomous_scheduler, "get_database", lambda: object())
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_init_with_deployment_check",
        lambda _db: result,
    )

    if expected_code:
        with pytest.raises(SystemExit) as exited:
            autonomous_scheduler.main()
        assert exited.value.code == expected_code
    else:
        autonomous_scheduler.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is expected_ok
    assert payload["init"] == result["init_results"]


@pytest.mark.parametrize(
    ("errors_count", "expected_code", "expected_ok"),
    [
        (0, 0, True),
        (3, 2, False),
    ],
)
def test_timeframe_cli_exit_code_matches_cycle_errors(
    monkeypatch, capsys, errors_count, expected_code, expected_ok
):
    from scheduler import autonomous_scheduler

    cycle = {
        "run_id": 42,
        "timeframe": "H1",
        "symbols_processed": 4,
        "predictions_generated": 0,
        "errors_count": errors_count,
        "results": [{"symbol": "EURUSD", "update": {"action": "updated"}}],
    }
    monkeypatch.setattr(
        sys,
        "argv",
        ["autonomous_scheduler.py", "--timeframe", "H1"],
    )
    monkeypatch.setattr(autonomous_scheduler, "get_database", lambda: object())
    monkeypatch.setattr(autonomous_scheduler, "run_cycle", lambda *_a: cycle)

    if expected_code:
        with pytest.raises(SystemExit) as exited:
            autonomous_scheduler.main()
        assert exited.value.code == expected_code
    else:
        autonomous_scheduler.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is expected_ok
    assert payload["cycle"] == cycle


def test_timeframe_cli_internal_exception_is_json_error_and_exit_one(
    monkeypatch, capsys
):
    from scheduler import autonomous_scheduler

    monkeypatch.setattr(
        sys,
        "argv",
        ["autonomous_scheduler.py", "--timeframe", "H1"],
    )
    monkeypatch.setattr(autonomous_scheduler, "get_database", lambda: object())
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_cycle",
        lambda *_a: (_ for _ in ()).throw(RuntimeError("cycle persistence failed")),
    )

    with pytest.raises(SystemExit) as exited:
        autonomous_scheduler.main()

    assert exited.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "ok": False,
        "error": "RuntimeError: cycle persistence failed",
    }

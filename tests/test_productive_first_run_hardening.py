"""Regressions for productive first-run eligibility and report semantics."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from deployment.pipeline_report import run_pipeline_report
from forex.prediction.model_storage import ModelStorage
from forex.prediction.retrain_manager import RetrainManager
from infra.db.database import SQLiteDatabase


def _csv(path):
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=2, freq="h"),
        "open": [1.0, 1.1],
        "high": [1.1, 1.2],
        "low": [0.9, 1.0],
        "close": [1.05, 1.15],
        "volume": [100.0, 100.0],
        "pair": ["EURUSD", "EURUSD"],
    })
    frame.to_csv(path, index=False)
    return frame


def _patch_report_data(monkeypatch, frame):
    from forex.prediction import csv_adapter, dataset_builder, feature_engineering
    from forex.prediction import roadmap_v_integration

    monkeypatch.setattr(csv_adapter, "adapt_csv", lambda *_a, **_k: frame)
    monkeypatch.setattr(feature_engineering, "build_features", lambda value: value)

    class Builder:
        def __init__(self, _frame):
            pass

        def build(self, **_kwargs):
            return pd.DataFrame({"close": range(100)}), pd.Series([0] * 100)

    monkeypatch.setattr(dataset_builder, "DatasetBuilder", Builder)
    monkeypatch.setattr(
        roadmap_v_integration,
        "run_quality_gate",
        lambda *_a, **_k: (
            True,
            SimpleNamespace(global_score=90.0, critical_count=0),
        ),
    )


def _legacy_initial_alias(monkeypatch, manager, storage, pair="EURUSD"):
    with monkeypatch.context() as patch:
        patch.setattr(
            RetrainManager,
            "_initial_eligibility_error",
            staticmethod(lambda _metadata: ""),
        )
        patch.setattr(
            RetrainManager,
            "_production_eligibility_error",
            classmethod(lambda _cls, *_args, **_kwargs: ""),
        )
        manager.promote_initial_model(
            SimpleNamespace(version="legacy", sufficient=True),
            pair=pair,
            dataset_provenance={"path": f"{pair}_H1.csv"},
            metadata={"precision": 0.70},
        )
    latest = storage.base_dir / f"latest_{pair}.pkl"
    return latest, latest.read_bytes()


def _patch_bootstrap_training(monkeypatch, *, wfv_passed=True, validation=True):
    from forex.prediction import integrated_pipeline, roadmap_v_integration

    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=320, freq="h"),
        "close": range(320),
        "pair": ["EURUSD"] * 320,
    })
    X = pd.DataFrame({"feature": range(300)})
    y = pd.Series([0, 1] * 150)

    class Builder:
        def __init__(self, _frame):
            pass

        def build(self, **_kwargs):
            return X, y

    wfv = {
        "folds": [{"fold": 1, "precision": 0.70}],
        "avg_precision": 0.70,
        "median_precision": 0.70,
        "wfv_passed": wfv_passed,
    }
    trainer = SimpleNamespace(
        model=SimpleNamespace(version="replacement", sufficient=True),
        model_valid=bool(wfv_passed and validation),
        calibration_sufficient=True,
        validation_sufficient=validation,
    )
    monkeypatch.setattr(integrated_pipeline, "_load", lambda *_a, **_k: frame)
    monkeypatch.setattr(integrated_pipeline, "build_features", lambda value: value)
    monkeypatch.setattr(integrated_pipeline, "DatasetBuilder", Builder)
    monkeypatch.setattr(
        integrated_pipeline,
        "train_with_wfv",
        lambda *_a, **_k: (trainer, dict(wfv), 0.80, 0.70 if validation else 0.0),
    )
    monkeypatch.setattr(
        roadmap_v_integration,
        "run_quality_gate",
        lambda *_a, **_k: (
            True,
            SimpleNamespace(global_score=90.0, critical_count=0),
        ),
    )
    return frame


def _bootstrap_pipeline(storage, database):
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

    pipeline = object.__new__(ForexIntegratedPipeline)
    pipeline._horizon = 12
    pipeline._rr_ratio = 1.0
    pipeline.storage = storage
    pipeline.closed_loop_database = database
    return pipeline


def test_first_deployment_quality_rejection_fails_stage_5_and_stops_prediction(
    monkeypatch, tmp_path
):
    from forex.prediction import integrated_pipeline, model_storage

    path = tmp_path / "EURUSD_H1.csv"
    frame = _csv(path)
    _patch_report_data(monkeypatch, frame)
    calls = []

    class Storage:
        def latest_exists(self, pair=None):
            return False

    class Pipeline:
        def train(self, filepath, **kwargs):
            calls.append(kwargs)
            return {
                "model_valid": True,
                "model_deployed": False,
                "model": "NO guardado",
                "wfv": {"wfv_passed": False, "model_deployed": False},
            }

        def predict(self, *_args, **_kwargs):
            raise AssertionError("Stage 6 must not run after a quality rejection")

    monkeypatch.setattr(model_storage, "ModelStorage", Storage)
    monkeypatch.setattr(integrated_pipeline, "ForexIntegratedPipeline", Pipeline)

    report = run_pipeline_report("EURUSD", csv_path=str(path), db=object())

    assert calls == [{"pair": "EURUSD", "use_wfv": True, "force": False}]
    assert len(report.stages) == 5
    assert report.stages[4].status == "fail"
    assert report.stages[4].cause == "MODEL_NOT_DEPLOYED / QUALITY_GATE"


@pytest.mark.parametrize("action,persisted,expected", [
    ("HOLD", None, "pass"),
    ("BUY", None, "fail"),
    (
        "BUY",
        {"prediction_id": "pred-1", "symbol": "EURUSD", "action": "BUY"},
        "pass",
    ),
])
def test_stage_10_uses_final_action_and_prediction_identity(
    monkeypatch, tmp_path, action, persisted, expected
):
    import deployment.pipeline_report as pipeline_report
    from forex.prediction import integrated_pipeline, model_storage, outcome_tracker
    from forex.prediction import retrain_manager

    path = tmp_path / "EURUSD_H1.csv"
    frame = _csv(path)
    _patch_report_data(monkeypatch, frame)

    class Storage:
        def latest_exists(self, pair=None):
            return True

        def load_model_with_features(self, pair=None):
            return SimpleNamespace(sufficient=True), ["close"]

    class Manager:
        def __init__(self, **_kwargs):
            pass

        def audit_pair_model(self, _pair):
            return {"eligible": True, "reason": "PRODUCTION_ELIGIBLE"}

    class Pipeline:
        def predict(self, *_args, **_kwargs):
            result = {"action": action, "confidence": 0.7}
            if action in {"BUY", "SELL"}:
                result["prediction_id"] = "pred-1"
            return result

    tracker_databases = []

    class Stats:
        def to_dict(self):
            return {"total_predictions": 0, "evaluated": 0}

    class Tracker:
        def __init__(self, *, database=None):
            tracker_databases.append(database)

        def get_stats(self, pair=""):
            assert pair == "EURUSD"
            return Stats()

    class Database:
        engine = "sqlite"

        def get_prediction(self, prediction_id):
            assert prediction_id == "pred-1"
            return persisted

    class Response:
        status_code = 200
        content = b"x" * 1001

    database = Database()
    monkeypatch.setattr(model_storage, "ModelStorage", Storage)
    monkeypatch.setattr(retrain_manager, "RetrainManager", Manager)
    monkeypatch.setattr(integrated_pipeline, "ForexIntegratedPipeline", Pipeline)
    monkeypatch.setattr(outcome_tracker, "OutcomeTracker", Tracker)
    monkeypatch.setattr(pipeline_report, "_loopback_get", lambda *_a, **_k: Response())

    report = run_pipeline_report("EURUSD", csv_path=str(path), db=database)

    assert tracker_databases == [database]
    assert report.stages[6].status == "pass"
    assert report.stages[6].data["total_predictions"] == 0
    assert report.stages[9].status == expected


def test_force_cannot_bypass_wfv_for_pair_specific_initial_promotion(
    monkeypatch
):
    from forex.prediction import integrated_pipeline
    from forex.prediction import roadmap_v_integration

    frame = pd.DataFrame({"close": range(300), "pair": ["EURUSD"] * 300})
    X = pd.DataFrame({"feature": range(300)})
    y = pd.Series([0, 1] * 150)

    class Builder:
        def __init__(self, _frame):
            pass

        def build(self, **_kwargs):
            return X, y

    trainer = SimpleNamespace(
        model=SimpleNamespace(sufficient=True),
        model_valid=True,
        calibration_sufficient=True,
        validation_sufficient=True,
    )
    monkeypatch.setattr(integrated_pipeline, "_load", lambda *_a, **_k: frame)
    monkeypatch.setattr(integrated_pipeline, "build_features", lambda value: value)
    monkeypatch.setattr(integrated_pipeline, "DatasetBuilder", Builder)
    monkeypatch.setattr(
        integrated_pipeline,
        "train_with_wfv",
        lambda *_a, **_k: (
            trainer,
            {"folds": [{"fold": 1}], "wfv_passed": False},
            0.8,
            0.8,
        ),
    )
    monkeypatch.setattr(
        roadmap_v_integration,
        "run_quality_gate",
        lambda *_a, **_k: (True, SimpleNamespace()),
    )
    pipeline = object.__new__(integrated_pipeline.ForexIntegratedPipeline)
    pipeline._horizon = 12
    pipeline._rr_ratio = 1.0
    pipeline.predictor = SimpleNamespace(invalidate_cache=lambda **_k: None)
    pipeline.storage = object()
    pipeline._promote_initial_training = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("WFV rejection must not reach RetrainManager promotion")
    )

    result = pipeline.train("EURUSD_H1.csv", pair="EURUSD", force=True)

    assert result["model_deployed"] is False
    assert result["model"] == "NO guardado"


def test_initial_promotion_requires_wfv_evidence_without_touching_alias(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    storage = ModelStorage(tmp_path / "models")
    manager = RetrainManager(database=database, storage=storage)

    with pytest.raises(ValueError, match="WFV_EVIDENCE_MISSING"):
        manager.promote_initial_model(
            {"version": 1},
            pair="EURUSD",
            dataset_provenance={"path": "EURUSD_H1.csv"},
        )

    assert storage.latest_exists("EURUSD") is False
    assert database.get_retrain_runs() == []


def test_preexisting_bootstrap_alias_is_preserved_and_flagged_for_revalidation(
    monkeypatch, tmp_path
):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    storage = ModelStorage(tmp_path / "models")
    manager = RetrainManager(database=database, storage=storage)
    monkeypatch.setattr(manager, "_initial_eligibility_error", lambda _metadata: "")
    monkeypatch.setattr(
        manager, "_production_eligibility_error", lambda *_args, **_kwargs: ""
    )
    manager.promote_initial_model(
        {"version": "bootstrap"},
        pair="EURUSD",
        dataset_provenance={"path": "EURUSD_H1.csv"},
        metadata={"precision": 0.70},
    )
    latest = storage.base_dir / "latest_EURUSD.pkl"
    before = latest.read_bytes()
    monkeypatch.undo()
    manager = RetrainManager(database=database, storage=storage)

    audit = manager.audit_pair_model("EURUSD")
    reconciliation = manager.reconcile()

    assert latest.read_bytes() == before
    assert audit["eligible"] is False
    assert audit["reason"] == "WFV_EVIDENCE_MISSING"
    assert audit["bootstrap_revalidation"] is True
    assert audit["source_model_path"] == str(latest)
    assert audit["source_model_sha256"] == storage.checksum(latest)
    assert any(
        issue["code"] == "initial_training_not_production_eligible"
        and issue["reason"] == "WFV_EVIDENCE_MISSING"
        for issue in reconciliation["issues"]
    )


def test_bootstrap_revalidation_promotes_full_contract_candidate(
    monkeypatch, tmp_path
):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    storage = ModelStorage(tmp_path / "models")
    manager = RetrainManager(database=database, storage=storage)
    latest, before = _legacy_initial_alias(monkeypatch, manager, storage)
    _patch_bootstrap_training(monkeypatch)
    pipeline = _bootstrap_pipeline(storage, database)

    result = pipeline.bootstrap_revalidate(
        str(tmp_path / "EURUSD_H1.csv"), pair="EURUSD", manager=manager
    )

    assert result["retrain_status"] == "PROMOTED"
    assert result["trigger"] == "bootstrap_revalidation"
    assert result["model_deployed"] is True
    assert latest.read_bytes() != before
    assert manager.audit_pair_model("EURUSD")["reason"] == "PRODUCTION_ELIGIBLE"
    run = database.get_retrain_runs("EURUSD")[0]
    assert run["trigger"] == "bootstrap_revalidation"
    assert run["timeframe"] == "H1"
    assert run["source_model_path"] == str(latest)
    assert run["source_model_sha256"]
    assert json.loads(run["outcome_ids"]) == []
    provenance = json.loads(run["dataset_provenance"])
    assert provenance["timeframe"] == "H1"
    assert provenance["training_horizon_candles"] == 12
    assert run["evidence_key"]


def test_scheduler_reconciliation_executes_bootstrap_revalidation(
    monkeypatch, tmp_path
):
    from forex.prediction import outcome_tracker
    from scheduler import autonomous_scheduler

    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    storage = ModelStorage(tmp_path / "models" / "forex")
    manager = RetrainManager(database=database, storage=storage)
    _legacy_initial_alias(monkeypatch, manager, storage)
    frame = _patch_bootstrap_training(monkeypatch)
    path = tmp_path / "EURUSD_H1.csv"
    frame.to_csv(path, index=False)
    database.upsert_dataset_registry({
        "symbol": "EURUSD",
        "timeframe": "H1",
        "status": "ready",
        "candle_count": len(frame),
        "rolling_window_size": 2000,
        "last_candle_timestamp": str(frame["timestamp"].iloc[-1]),
        "blob_path": str(path),
    })

    class Tracker:
        def __init__(self, *, database):
            self.database = database

        def evaluate_from_csv(self, *_a, **_k):
            return 0

    monkeypatch.setattr(autonomous_scheduler, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(outcome_tracker, "OutcomeTracker", Tracker)

    result = autonomous_scheduler.run_closed_loop_maintenance(
        database, "EURUSD", "H1"
    )

    assert result["action"] == "maintained"
    assert result["bootstrap_revalidation"]["retrain_status"] == "PROMOTED"
    assert RetrainManager(database=database, storage=storage).audit_pair_model(
        "EURUSD"
    )["eligible"] is True


def test_run_cycle_bootstraps_legacy_alias_before_prediction(monkeypatch, tmp_path):
    from forex.prediction import integrated_pipeline, outcome_tracker
    from robustness import model_integrity_checker
    from scheduler import autonomous_scheduler

    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    database.add_symbol("EURUSD")
    storage = ModelStorage(tmp_path / "models" / "forex")
    manager = RetrainManager(database=database, storage=storage)
    _legacy_initial_alias(monkeypatch, manager, storage)
    frame = _patch_bootstrap_training(monkeypatch)
    path = tmp_path / "EURUSD_H1.csv"
    frame.to_csv(path, index=False)
    database.upsert_dataset_registry({
        "symbol": "EURUSD",
        "timeframe": "H1",
        "status": "ready",
        "candle_count": len(frame),
        "rolling_window_size": 2000,
        "last_candle_timestamp": str(frame["timestamp"].iloc[-1]),
        "blob_path": str(path),
    })
    events = []

    class Tracker:
        def __init__(self, *, database):
            self.database = database

        def evaluate_from_csv(self, *_a, **_k):
            return 0

    original_bootstrap = integrated_pipeline.ForexIntegratedPipeline.bootstrap_revalidate

    def bootstrap(self, *args, **kwargs):
        events.append("bootstrap_started")
        result = original_bootstrap(self, *args, **kwargs)
        events.append("bootstrap_finished")
        return result

    def predict(_db, symbol, timeframe):
        audit = RetrainManager(database=database, storage=storage).audit_pair_model(symbol)
        assert audit["eligible"] is True
        events.append("prediction")
        return {"action": "predicted", "prediction": {"symbol": symbol}}

    monkeypatch.setattr(autonomous_scheduler, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(autonomous_scheduler, "detect_new_symbols", lambda _db: [])
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_rolling_update",
        lambda *_a, **_k: {"action": "updated"},
    )
    monkeypatch.setattr(autonomous_scheduler, "run_prediction", predict)
    monkeypatch.setattr(outcome_tracker, "OutcomeTracker", Tracker)
    monkeypatch.setattr(
        model_integrity_checker,
        "check_model_before_cycle",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("legacy alias must reach maintenance before executable checks")
        ),
    )
    monkeypatch.setattr(
        integrated_pipeline.ForexIntegratedPipeline,
        "bootstrap_revalidate",
        bootstrap,
    )

    result = autonomous_scheduler.run_cycle(database, "H1")

    assert events == ["bootstrap_started", "bootstrap_finished", "prediction"]
    assert result["symbols_processed"] == 1
    assert result["predictions_generated"] == 1
    assert result["results"][1]["closed_loop"]["bootstrap_revalidation"][
        "retrain_status"
    ] == "PROMOTED"


def test_h1_updates_all_active_symbols_before_model_eligibility_gate(
    monkeypatch, tmp_path
):
    from robustness import model_integrity_checker
    from scheduler import autonomous_scheduler

    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    symbols = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD")
    for symbol in symbols:
        database.add_symbol(symbol)

    events = []
    predictions = []

    def audit(_manager, symbol):
        events.append(("gate", symbol))
        if symbol == "GBPUSD":
            return {"eligible": False, "reason": "MODEL_NOT_DEPLOYED"}
        return {"eligible": True, "reason": "PRODUCTION_ELIGIBLE"}

    def update(_db, symbol, timeframe):
        events.append(("update", symbol))
        assert timeframe == "H1"
        return {"action": "updated"}

    def predict(_db, symbol, timeframe):
        predictions.append(symbol)
        return {"action": "predicted", "prediction": {"symbol": symbol}}

    monkeypatch.setattr(autonomous_scheduler, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(autonomous_scheduler, "detect_new_symbols", lambda _db: [])
    monkeypatch.setattr(autonomous_scheduler, "run_rolling_update", update)
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_closed_loop_maintenance",
        lambda *_a, **_k: {"action": "maintained"},
    )
    monkeypatch.setattr(autonomous_scheduler, "run_prediction", predict)
    monkeypatch.setattr(RetrainManager, "reconcile", lambda _self: {"issues": []})
    monkeypatch.setattr(RetrainManager, "audit_pair_model", audit)
    monkeypatch.setattr(
        model_integrity_checker,
        "check_model_before_cycle",
        lambda *_a, **_k: True,
    )

    result = autonomous_scheduler.run_cycle(database, "H1")

    assert result["symbols_processed"] == 4
    assert result["errors_count"] == 1
    assert [event for event in events if event[0] == "update"] == [
        ("update", symbol) for symbol in symbols
    ]
    for symbol in symbols:
        assert events.index(("update", symbol)) < events.index(("gate", symbol))
    assert predictions == ["EURUSD", "USDJPY", "AUDUSD"]
    gbp_predict = next(
        item["predict"] for item in result["results"]
        if item.get("symbol") == "GBPUSD" and "predict" in item
    )
    assert gbp_predict == {
        "action": "skip",
        "reason": "model_not_production_eligible",
        "audit_reason": "MODEL_NOT_DEPLOYED",
    }


def test_h1_counts_independent_update_and_model_gate_failures_once_each(
    monkeypatch, tmp_path
):
    from scheduler import autonomous_scheduler

    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    database.add_symbol("GBPUSD")

    monkeypatch.setattr(autonomous_scheduler, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(autonomous_scheduler, "detect_new_symbols", lambda _db: [])
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_rolling_update",
        lambda *_a, **_k: {"action": "error", "error": "provider unavailable"},
    )
    monkeypatch.setattr(RetrainManager, "reconcile", lambda _self: {"issues": []})
    monkeypatch.setattr(
        RetrainManager,
        "audit_pair_model",
        lambda _self, _symbol: {
            "eligible": False,
            "reason": "MODEL_NOT_DEPLOYED",
        },
    )
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_prediction",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("blocked model must not reach prediction")
        ),
    )

    result = autonomous_scheduler.run_cycle(database, "H1")

    assert result["symbols_processed"] == 1
    assert result["errors_count"] == 2
    stored = database.get_scheduler_runs()[0]
    assert stored["status"] == "partial"
    assert stored["errors_count"] == 2


def test_h1_closed_loop_failure_counts_once_and_preserves_prediction(
    monkeypatch, tmp_path
):
    from robustness import model_integrity_checker
    from scheduler import autonomous_scheduler

    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    database.add_symbol("EURUSD")

    monkeypatch.setattr(autonomous_scheduler, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(autonomous_scheduler, "detect_new_symbols", lambda _db: [])
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_rolling_update",
        lambda *_a, **_k: {"action": "updated"},
    )
    monkeypatch.setattr(RetrainManager, "reconcile", lambda _self: {"issues": []})
    monkeypatch.setattr(
        RetrainManager,
        "audit_pair_model",
        lambda _self, _symbol: {
            "eligible": True,
            "reason": "PRODUCTION_ELIGIBLE",
        },
    )
    monkeypatch.setattr(
        model_integrity_checker,
        "check_model_before_cycle",
        lambda *_a, **_k: True,
    )
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_closed_loop_maintenance",
        lambda *_a, **_k: {"action": "error", "error": "tracker failed"},
    )
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_prediction",
        lambda *_a, **_k: {"action": "predicted", "prediction": {}},
    )

    result = autonomous_scheduler.run_cycle(database, "H1")

    assert result["errors_count"] == 1
    assert result["predictions_generated"] == 1


@pytest.mark.parametrize("failure", ["CHECKSUM_MISMATCH", "ARTIFACT_INVALID"])
def test_run_cycle_blocks_integrity_failures_before_bootstrap_and_prediction(
    monkeypatch, tmp_path, failure
):
    from forex.prediction import integrated_pipeline
    from scheduler import autonomous_scheduler

    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    database.add_symbol("EURUSD")
    storage = ModelStorage(tmp_path / "models" / "forex")
    manager = RetrainManager(database=database, storage=storage)
    latest = storage.base_dir / "latest_EURUSD.pkl"
    if failure == "CHECKSUM_MISMATCH":
        _legacy_initial_alias(monkeypatch, manager, storage)
        unrelated = storage.stage_model(
            SimpleNamespace(version="unrelated", sufficient=True),
            name="unrelated",
            version="v1",
        )
        latest.write_bytes(unrelated.read_bytes())
    else:
        latest.write_bytes(b"not a model")
    assert manager.audit_pair_model("EURUSD")["reason"] == failure

    monkeypatch.setattr(autonomous_scheduler, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(autonomous_scheduler, "detect_new_symbols", lambda _db: [])
    update_calls = []
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_rolling_update",
        lambda _db, symbol, timeframe: (
            update_calls.append((symbol, timeframe)) or {"action": "updated"}
        ),
    )
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_prediction",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("integrity failure must not reach prediction")
        ),
    )
    monkeypatch.setattr(
        integrated_pipeline.ForexIntegratedPipeline,
        "bootstrap_revalidate",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("integrity failure must not reach bootstrap")
        ),
    )

    result = autonomous_scheduler.run_cycle(database, "H1")

    assert update_calls == [("EURUSD", "H1")]
    assert result["symbols_processed"] == 1
    assert result["predictions_generated"] == 0
    assert result["errors_count"] == 1
    predict_result = next(
        item["predict"] for item in result["results"] if "predict" in item
    )
    assert predict_result["action"] == "skip"
    assert predict_result["reason"] in {
        "model_provenance_reconciliation_failed",
        "model_not_production_eligible",
    }


def test_failed_legacy_bootstrap_updates_data_without_new_retrain_or_prediction(
    monkeypatch, tmp_path
):
    from scheduler import autonomous_scheduler

    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    database.add_symbol("EURUSD")
    storage = ModelStorage(tmp_path / "models" / "forex")
    manager = RetrainManager(database=database, storage=storage)
    _legacy_initial_alias(monkeypatch, manager, storage)
    frame = _patch_bootstrap_training(monkeypatch)
    path = tmp_path / "EURUSD_H1.csv"
    frame.to_csv(path, index=False)
    database.upsert_dataset_registry({
        "symbol": "EURUSD",
        "timeframe": "H1",
        "status": "ready",
        "candle_count": len(frame),
        "rolling_window_size": 2000,
        "last_candle_timestamp": str(frame["timestamp"].iloc[-1]),
        "blob_path": str(path),
    })
    failed = manager.ensure_bootstrap_revalidation(
        "EURUSD",
        dataset_provenance={"registry_id": 1},
    )
    database.update_retrain_run(failed["run_id"], {
        "status": "FAILED",
        "error": "quality evidence failed",
        "updated_at": failed["updated_at"],
    })
    run_ids_before = {
        run["run_id"] for run in database.get_retrain_runs("EURUSD")
    }
    updates = []

    monkeypatch.setattr(autonomous_scheduler, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(autonomous_scheduler, "detect_new_symbols", lambda _db: [])
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_rolling_update",
        lambda _db, symbol, timeframe: (
            updates.append((symbol, timeframe)) or {"action": "updated"}
        ),
    )
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_prediction",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("failed bootstrap must not reach prediction")
        ),
    )

    result = autonomous_scheduler.run_cycle(database, "H1")

    assert updates == [("EURUSD", "H1")]
    assert result["symbols_processed"] == 1
    assert result["predictions_generated"] == 0
    assert result["errors_count"] == 1
    assert {
        run["run_id"] for run in database.get_retrain_runs("EURUSD")
    } == run_ids_before
    stored_failed = next(
        run for run in database.get_retrain_runs("EURUSD")
        if run["run_id"] == failed["run_id"]
    )
    assert stored_failed["status"] == "FAILED"
    predict_result = next(
        item["predict"] for item in result["results"] if "predict" in item
    )
    assert predict_result == {
        "action": "skip",
        "reason": "bootstrap_revalidation_not_production_eligible",
    }


def test_integrity_gate_runs_after_dataset_update_and_blocks_prediction(
    monkeypatch, tmp_path
):
    from robustness import model_integrity_checker
    from scheduler import autonomous_scheduler

    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    database.add_symbol("EURUSD")
    events = []

    monkeypatch.setattr(autonomous_scheduler, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(autonomous_scheduler, "detect_new_symbols", lambda _db: [])
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_rolling_update",
        lambda *_a, **_k: events.append("update") or {"action": "updated"},
    )
    monkeypatch.setattr(RetrainManager, "reconcile", lambda _self: {"issues": []})
    monkeypatch.setattr(
        RetrainManager,
        "audit_pair_model",
        lambda _self, _symbol: {
            "eligible": True,
            "reason": "PRODUCTION_ELIGIBLE",
        },
    )
    monkeypatch.setattr(
        model_integrity_checker,
        "check_model_before_cycle",
        lambda *_a, **_k: events.append("integrity") or False,
    )
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_prediction",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("invalid model must not reach prediction")
        ),
    )

    result = autonomous_scheduler.run_cycle(database, "H1")

    assert events == ["update", "integrity"]
    assert result["symbols_processed"] == 1
    assert result["errors_count"] == 1
    predict_result = next(
        item["predict"] for item in result["results"] if "predict" in item
    )
    assert predict_result == {
        "action": "skip",
        "reason": "model_integrity_check_failed",
    }


def test_bootstrap_quality_failure_preserves_alias_and_stops_stage_6(
    monkeypatch, tmp_path
):
    import deployment.pipeline_report as pipeline_report
    from forex.prediction import integrated_pipeline, model_storage

    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    storage = ModelStorage(tmp_path / "models")
    manager = RetrainManager(database=database, storage=storage)
    latest, before = _legacy_initial_alias(monkeypatch, manager, storage)
    frame = _patch_bootstrap_training(monkeypatch, validation=False)
    csv_path = tmp_path / "EURUSD_H1.csv"
    frame.iloc[:2].to_csv(csv_path, index=False)
    _patch_report_data(monkeypatch, frame)
    monkeypatch.setattr(model_storage, "ModelStorage", lambda: storage)
    monkeypatch.setattr(
        integrated_pipeline.ForexIntegratedPipeline,
        "predict",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("Stage 6 must not run after bootstrap quality failure")
        ),
    )

    report = pipeline_report.run_pipeline_report(
        "EURUSD", csv_path=str(csv_path), db=database
    )

    assert len(report.stages) == 5
    assert report.stages[4].status == "fail"
    assert report.stages[4].cause == "QUALITY_GATE"
    assert latest.read_bytes() == before
    assert database.get_retrain_runs("EURUSD")[0]["status"] == "FAILED"
    assert manager.audit_pair_model("EURUSD")["eligible"] is False


def test_bootstrap_promotion_failure_preserves_alias(monkeypatch, tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    storage = ModelStorage(tmp_path / "models")
    manager = RetrainManager(database=database, storage=storage)
    latest, before = _legacy_initial_alias(monkeypatch, manager, storage)
    _patch_bootstrap_training(monkeypatch)
    pipeline = _bootstrap_pipeline(storage, database)
    monkeypatch.setattr(
        storage,
        "promote_artifact",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("promotion failed")),
    )

    result = pipeline.bootstrap_revalidate(
        str(tmp_path / "EURUSD_H1.csv"), pair="EURUSD", manager=manager
    )

    assert result["retrain_status"] == "FAILED"
    assert latest.read_bytes() == before
    assert manager.audit_pair_model("EURUSD")["eligible"] is False


@pytest.mark.parametrize("active_status", ["PENDING", "RUNNING", "VALIDATED"])
def test_bootstrap_revalidation_evidence_is_idempotent(
    monkeypatch, tmp_path, active_status
):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    storage = ModelStorage(tmp_path / "models")
    manager = RetrainManager(database=database, storage=storage)
    _legacy_initial_alias(monkeypatch, manager, storage)
    provenance = {"registry_id": 1, "snapshot": "current"}

    first = manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance=provenance
    )
    if active_status != "PENDING":
        database.update_retrain_run(first["run_id"], {
            "status": active_status,
            "updated_at": first["updated_at"],
        })
    second = manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance=provenance
    )

    assert first["run_id"] == second["run_id"]
    assert first["evidence_key"] == second["evidence_key"]
    assert len(database.get_retrain_runs("EURUSD")) == 2  # initial + bootstrap
    active = [
        run for run in database.get_retrain_runs("EURUSD")
        if run["trigger"] == "bootstrap_revalidation"
        and run["status"] in {"PENDING", "RUNNING", "VALIDATED"}
    ]
    assert len(active) == 1
    assert active[0]["status"] == active_status


def test_failed_bootstrap_is_one_shot_when_only_candle_provenance_changes(
    monkeypatch, tmp_path
):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    storage = ModelStorage(tmp_path / "models")
    manager = RetrainManager(database=database, storage=storage)
    _legacy_initial_alias(monkeypatch, manager, storage)
    provenance_a = {
        "registry_id": 1,
        "blob_path": "EURUSD_H1.csv",
        "last_candle_timestamp": "2026-01-01T10:00:00",
        "last_updated": "2026-01-01T10:01:00",
    }
    provenance_b = {
        **provenance_a,
        "last_candle_timestamp": "2026-01-01T11:00:00",
        "last_updated": "2026-01-01T11:01:00",
    }

    first = manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance=provenance_a
    )
    database.update_retrain_run(first["run_id"], {
        "status": "FAILED",
        "error": "quality evidence failed",
        "updated_at": first["updated_at"],
    })
    second = manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance=provenance_b
    )

    assert second["run_id"] == first["run_id"]
    assert second["evidence_key"] == first["evidence_key"]
    assert second["status"] == "FAILED"
    assert json.loads(second["dataset_provenance"]) == provenance_a
    bootstrap_runs = [
        run for run in database.get_retrain_runs("EURUSD")
        if run["trigger"] == "bootstrap_revalidation"
        and run["source_model_sha256"] == first["source_model_sha256"]
    ]
    assert len(bootstrap_runs) == 1


def test_corrupt_or_ambiguous_alias_never_auto_revalidates(monkeypatch, tmp_path):
    corrupt_db = SQLiteDatabase(str(tmp_path / "corrupt.sqlite"))
    corrupt_storage = ModelStorage(tmp_path / "corrupt-models")
    corrupt_manager = RetrainManager(database=corrupt_db, storage=corrupt_storage)
    corrupt = corrupt_storage.base_dir / "latest_EURUSD.pkl"
    corrupt.write_bytes(b"not a model")

    assert corrupt_manager.audit_pair_model("EURUSD")["reason"] == "ARTIFACT_INVALID"
    assert corrupt_manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance={"snapshot": "current"}
    ) is None
    assert corrupt_db.get_retrain_runs() == []

    database = SQLiteDatabase(str(tmp_path / "ambiguous.sqlite"))
    storage = ModelStorage(tmp_path / "ambiguous-models")
    manager = RetrainManager(database=database, storage=storage)
    _legacy_initial_alias(monkeypatch, manager, storage)
    provenance = database.get_model_provenance("EURUSD")[0]
    monkeypatch.setattr(
        database, "get_model_provenance", lambda _symbol=None: [provenance, dict(provenance)]
    )

    assert manager.audit_pair_model("EURUSD")["reason"] == "PROVENANCE_AMBIGUOUS"
    assert manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance={"snapshot": "current"}
    ) is None


def test_checksum_mismatch_never_auto_revalidates(monkeypatch, tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    storage = ModelStorage(tmp_path / "models")
    manager = RetrainManager(database=database, storage=storage)
    latest, _before = _legacy_initial_alias(monkeypatch, manager, storage)
    unrelated = storage.stage_model(
        SimpleNamespace(version="unrelated", sufficient=True),
        name="unrelated",
        version="v1",
    )
    latest.write_bytes(unrelated.read_bytes())

    assert manager.audit_pair_model("EURUSD")["reason"] == "CHECKSUM_MISMATCH"
    assert manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance={"snapshot": "current"}
    ) is None
    assert all(
        run["trigger"] != "bootstrap_revalidation"
        for run in database.get_retrain_runs("EURUSD")
    )


def test_calibration_success_does_not_override_failed_validation(monkeypatch):
    import numpy as np
    from forex.prediction import xgb_trainer

    class Estimator:
        def fit(self, *_args, **_kwargs):
            return self

    class Calibrated:
        sufficient = True
        threshold = 0.5

        def __init__(self, _base):
            pass

        def fit(self, *_args, **_kwargs):
            return self

        def predict(self, X):
            return np.zeros(len(X), dtype=int)

    monkeypatch.setattr(xgb_trainer, "_HAS_XGB", False)
    monkeypatch.setattr(xgb_trainer, "_HAS_LGB", False)
    monkeypatch.setattr(xgb_trainer, "CalibratedEnsemble", Calibrated)
    trainer = xgb_trainer.ForexEnsembleTrainer(pair="EURUSD")
    monkeypatch.setattr(trainer, "_build_rf", lambda *_a, **_k: Estimator())
    X = pd.DataFrame({"feature": range(100)})
    y = pd.Series([0, 1] * 50)

    _accuracy, precision = trainer.train(X, y, save=False)

    assert trainer.calibration_sufficient is True
    assert precision == 0.0
    assert trainer.validation_sufficient is False
    assert trainer.model_valid is False


def test_clamped_calibration_reports_metrics_at_effective_threshold(capsys):
    import numpy as np
    from forex.prediction.xgb_trainer import CalibratedEnsemble

    class Base:
        @staticmethod
        def predict_proba(X):
            probabilities = np.asarray(X["probability"], dtype=float)
            return np.column_stack([1.0 - probabilities, probabilities])

    X_cal = pd.DataFrame({"probability": [0.8] * 10 + [0.9]})
    y_cal = pd.Series([1] * 9 + [0, 1])

    calibrated = CalibratedEnsemble(Base()).fit(X_cal, y_cal)
    output = capsys.readouterr().out

    assert "Umbral óptimo 1.000 > 0.9" in output
    assert calibrated.threshold == pytest.approx(0.90)
    assert calibrated.precision_at_threshold == pytest.approx(10 / 11)
    assert calibrated.precision_at_threshold != pytest.approx(1.0)
    assert calibrated.recall_at_threshold == pytest.approx(1.0)
    assert calibrated.recall_at_threshold != pytest.approx(1 / 10)
    assert calibrated.signals_at_threshold == 11
    assert "precision=90.91% recall=100.00% señales=11/11" in output
    assert "CALIBRACIÓN APROBADA" in output
    assert "MODELO VÁLIDO" not in output
    assert calibrated.sufficient is True


def test_clamped_calibration_rejects_insufficient_effective_metrics(capsys):
    import numpy as np
    from forex.prediction.xgb_trainer import CalibratedEnsemble

    class Base:
        @staticmethod
        def predict_proba(X):
            probabilities = np.asarray(X["probability"], dtype=float)
            return np.column_stack([1.0 - probabilities, probabilities])

    class IdentityCalibration:
        @staticmethod
        def fit(_probabilities, _targets):
            return None

        @staticmethod
        def predict(probabilities):
            return probabilities

    X_cal = pd.DataFrame({
        "probability": [1.0] + [0.1] * 9 + [0.9, 0.9],
    })
    y_cal = pd.Series([1] * 10 + [0, 0])
    calibrated = CalibratedEnsemble(Base())
    calibrated.cal_1 = IdentityCalibration()

    calibrated.fit(X_cal, y_cal)
    output = capsys.readouterr().out

    assert "Umbral óptimo 1.000 > 0.9" in output
    assert calibrated.threshold == pytest.approx(0.90)
    assert calibrated.precision_at_threshold == pytest.approx(1 / 3)
    assert calibrated.recall_at_threshold == pytest.approx(1 / 10)
    assert calibrated.signals_at_threshold == 3
    assert calibrated.sufficient is False
    assert "← CALIBRACIÓN NO APROBADA" in output


def test_loopback_api_auth_never_returns_or_logs_secret(monkeypatch):
    import deployment.pipeline_report as pipeline_report
    import requests

    captured = {}
    secret = "unit-test-placeholder"

    def get(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return SimpleNamespace(status_code=200, content=b"ok")

    monkeypatch.setenv("ASTRA_API_KEY", secret)
    monkeypatch.setenv("ASTRA_API_HOST", "0.0.0.0")
    monkeypatch.setattr(requests, "get", get)

    response = pipeline_report._loopback_get(
        "/api/datasets/status", authenticated=True
    )

    assert captured["url"].startswith("http://127.0.0.1:")
    assert captured["headers"]["Authorization"] == f"Bearer {secret}"
    assert secret not in repr(response)


@pytest.mark.parametrize(
    "wfv_passed,validation,promotion_status",
    [
        (False, True, "PROMOTED"),
        (True, False, "PROMOTED"),
        (True, True, "FAILED"),
    ],
)
def test_multi_horizon_rejected_candidate_emits_zero_votes(
    monkeypatch, wfv_passed, validation, promotion_status
):
    from forex.prediction import integrated_pipeline

    frame = pd.DataFrame({"close": range(320), "pair": ["EURUSD"] * 320})
    X = pd.DataFrame({"feature": range(300)})
    y = pd.Series([0, 1] * 150)
    prediction_calls = []

    class Candidate:
        sufficient = True

        def predict_proba(self, _X):
            prediction_calls.append("vote")
            return [[0.2, 0.8]]

    class Builder:
        def __init__(self, _frame):
            pass

        def build(self, **_kwargs):
            return X, y

        def predict_features(self, **_kwargs):
            return X.iloc[:1]

    class Storage:
        def latest_exists(self, pair=None):
            return False

        def load_model(self, pair=None):
            raise AssertionError("a rejected candidate must not be loaded for voting")

    trainer = SimpleNamespace(
        model=Candidate(),
        model_valid=bool(wfv_passed and validation),
        calibration_sufficient=True,
        validation_sufficient=validation,
    )
    wfv = {
        "folds": [{"fold": 1, "precision": 0.70}],
        "avg_precision": 0.70,
        "median_precision": 0.70,
        "wfv_passed": wfv_passed,
    }
    monkeypatch.setattr(integrated_pipeline, "_load", lambda *_a, **_k: frame)
    monkeypatch.setattr(integrated_pipeline, "build_features", lambda value: value)
    monkeypatch.setattr(integrated_pipeline, "DatasetBuilder", Builder)
    monkeypatch.setattr(
        integrated_pipeline,
        "train_with_wfv",
        lambda *_a, **_k: (trainer, dict(wfv), 0.80, 0.70),
    )
    pipeline = object.__new__(integrated_pipeline.ForexIntegratedPipeline)
    pipeline._horizon = 12
    pipeline._rr_ratio = 1.0
    pipeline.min_confidence = 0.65
    pipeline.storage = Storage()
    pipeline._promote_initial_training = (
        lambda *_a, **_k: {"status": promotion_status}
    )

    result = pipeline.predict_multi_horizon("EURUSD_H1.csv", pair="EURUSD")

    assert "error" in result
    assert prediction_calls == []

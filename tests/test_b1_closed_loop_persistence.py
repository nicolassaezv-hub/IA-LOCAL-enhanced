"""B1 (A10 + A17) closed-loop and persistence regression contract."""
from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import pandas as pd
import pytest

from forex.prediction.model_storage import ModelStorage
from forex.prediction.model_quality_history import ModelQualityHistory
from forex.prediction.outcome_tracker import OutcomeTracker
from forex.prediction.retrain_manager import RetrainManager
from forex.prediction.reliability_score import ReliabilityScorer
from forex.prediction.risk_engine import RiskEngine
from infra.db.database import (
    PersistenceConflictError,
    SQLiteDatabase,
    stable_prediction_id,
)


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def closed_loop(tmp_path):
    db_path = tmp_path / "closed-loop.db"
    database = SQLiteDatabase(str(db_path))
    tracker = OutcomeTracker(database=database)
    return database, tracker, db_path


def _candles(*rows):
    return pd.DataFrame(
        {"timestamp": [row[0] for row in rows], "close": [row[1] for row in rows]}
    )


def _record(
    tracker: OutcomeTracker,
    *,
    action: str = "BUY",
    candle: datetime = BASE,
    horizon: int = 2,
    entry: float = 100.0,
) -> str:
    return tracker.record_prediction(
        "EURUSD",
        "H1",
        action,
        entry,
        reliability_score=80.0,
        candle_timestamp=candle,
        prediction_timestamp=candle + timedelta(minutes=1),
        raw_action=action,
        horizon_candles=horizon,
        model_identity="source-model-sha",
        dataset_provenance={"registry_id": 1, "last_candle_timestamp": candle.isoformat()},
    )


def _seed_finalized_outcomes(database: SQLiteDatabase, count: int) -> list[int]:
    outcome_ids = []
    for index in range(count):
        candle = (BASE + timedelta(hours=index)).isoformat()
        prediction_id = stable_prediction_id("EURUSD", "H1", candle, "BUY")
        database.save_prediction({
            "prediction_id": prediction_id,
            "symbol": "EURUSD",
            "timeframe": "H1",
            "action": "BUY",
            "direction": "BUY",
            "entry_price": 100.0,
            "predicted_at": candle,
            "candle_timestamp": candle,
            "horizon_candles": 1,
            "model_identity": "source-model-sha",
            "dataset_provenance": {"registry_id": 1},
        })
        stored = database.save_outcome({
            "prediction_id": prediction_id,
            "symbol": "EURUSD",
            "timeframe": "H1",
            "action": "BUY",
            "entry_price": 100.0,
            "observed_price": 101.0,
            "observed_return": 0.01,
            "result": "win",
            "status": "FINALIZED",
            "prediction_timestamp": candle,
            "evaluation_timestamp": (BASE + timedelta(hours=index + 1)).isoformat(),
            "model_identity": "source-model-sha",
            "dataset_provenance": {"registry_id": 1},
        })
        outcome_ids.append(stored["id"])
    return outcome_ids


def _manager(tmp_path, database, *, minimum=2):
    storage = ModelStorage(tmp_path / "models")
    manager = RetrainManager(
        database=database,
        storage=storage,
        config={"min_new_outcomes": minimum},
    )
    return manager, storage


def _initial_eligibility_metadata() -> dict:
    return {
        "eligibility": {
            "calibration_passed": True,
            "validation_passed": True,
            "validation_precision": 0.70,
            "wfv_passed": True,
        },
        "wfv": {
            "folds": [{"fold": 1, "precision": 0.70}],
            "avg_precision": 0.70,
            "median_precision": 0.70,
            "wfv_passed": True,
        },
    }


def _pending_run(tmp_path, database, *, minimum=2):
    _seed_finalized_outcomes(database, minimum)
    manager, storage = _manager(tmp_path, database, minimum=minimum)
    initial = manager.promote_initial_model(
        {"version": 1},
        pair="EURUSD",
        dataset_provenance={"registry_id": 1, "snapshot": "initial-v1"},
        metadata=_initial_eligibility_metadata(),
    )
    assert initial["status"] == "PROMOTED"
    run = manager.ensure_pending_from_outcomes(
        "EURUSD",
        dataset_provenance={"registry_id": 1, "snapshot": "dataset-v1"},
    )
    assert run and run["status"] == "PENDING"
    return manager, storage, run


def test_pair_specific_load_never_falls_back_to_generic_latest(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    manager, storage = _manager(tmp_path, database)
    storage.save_model(
        {"symbol": "GENERIC_EURUSD"}, name="legacy", version="generic"
    )
    manager.promote_initial_model(
        {"symbol": "EURUSD"},
        pair="EURUSD",
        dataset_provenance={"path": "EURUSD_H1.csv"},
        feature_names=["close"],
        metadata=_initial_eligibility_metadata(),
    )

    assert storage.load_model("EURUSD") == {"symbol": "EURUSD"}
    assert storage.load_model() == {"symbol": "GENERIC_EURUSD"}
    assert storage.latest_exists("EURUSD") is True
    assert storage.latest_exists("USDJPY") is False
    with pytest.raises(FileNotFoundError, match="USDJPY"):
        storage.load_model("USDJPY")
    with pytest.raises(FileNotFoundError, match="USDJPY"):
        storage.load_model_with_features("USDJPY")


def test_pipeline_model_identity_never_crosses_symbol(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    manager, storage = _manager(tmp_path, database)
    storage.save_model(
        {"symbol": "GENERIC_EURUSD"}, name="legacy", version="generic-eurusd"
    )
    manager.promote_initial_model(
        {"symbol": "EURUSD"},
        pair="EURUSD",
        dataset_provenance={"path": "EURUSD_H1.csv"},
        metadata=_initial_eligibility_metadata(),
    )
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

    pipeline = object.__new__(ForexIntegratedPipeline)
    pipeline.storage = storage

    assert pipeline._model_identity("USDJPY") is None
    assert pipeline._model_identity("USD/JPY") is None


def test_pair_promotion_requires_canonical_provenance_boundary(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    manager, storage = _manager(tmp_path, database)
    artifact = storage.stage_model(
        {"version": 1}, name="unpromoted", version="v1"
    )

    with pytest.raises(RuntimeError, match="RetrainManager provenance"):
        storage.promote_artifact(artifact, pair="EURUSD")
    with pytest.raises(RuntimeError, match="cannot publish production aliases"):
        storage.save_model({"version": 1}, pair="EURUSD")
    assert not (storage.base_dir / "latest_EURUSD.pkl").exists()
    assert database.get_model_provenance() == []

    run = manager.promote_initial_model(
        {"version": 1},
        pair="EURUSD",
        dataset_provenance={"path": "EURUSD_H1.csv", "rows": 2000},
        metadata=_initial_eligibility_metadata(),
    )

    latest = storage.base_dir / "latest_EURUSD.pkl"
    provenance = database.get_model_provenance("EURUSD")
    assert run["trigger"] == "initial_training"
    assert run["status"] == "PROMOTED"
    assert json.loads(run["outcome_ids"]) == []
    assert len(provenance) == 1
    assert provenance[0]["status"] == "INITIAL_TRAINING"
    assert provenance[0]["artifact_sha256"] == storage.checksum(latest)
    before = latest.read_bytes()
    with pytest.raises(RuntimeError, match="cannot publish production aliases"):
        storage.save_model({"version": 2}, pair="EURUSD")
    assert latest.read_bytes() == before
    assert len(database.get_model_provenance("EURUSD")) == 1


def test_scheduler_service_delegates_to_canonical_closed_loop(monkeypatch):
    import scheduler.autonomous_scheduler as canonical_scheduler
    import scheduler_service

    calls = []

    class Database:
        @staticmethod
        def get_supported_symbols():
            return [{"symbol_code": "EURUSD"}, {"symbol_code": "USDJPY"}]

    def canonical(database, symbol, timeframe):
        calls.append((database, symbol, timeframe))
        return {"action": "maintained", "outcomes_finalized": 0}

    database = Database()
    monkeypatch.setattr(
        canonical_scheduler, "run_closed_loop_maintenance", canonical
    )

    results = scheduler_service.run_closed_loop_job(database)

    assert calls == [
        (database, "EURUSD", "H1"),
        (database, "USDJPY", "H1"),
    ]
    assert [result["symbol"] for result in results] == ["EURUSD", "USDJPY"]


def test_model_quality_absence_and_thirty_day_window_are_explicit(monkeypatch):
    import forex.prediction.model_quality_history as quality_module

    now = datetime(2026, 8, 11, tzinfo=timezone.utc)
    recent = now - timedelta(days=5)
    old = now - timedelta(days=31)
    rows = [
        {
            "symbol": "EURUSD",
            "timeframe": "H1",
            "model_identity": "model-v1",
            "result": "win" if index < 6 else "loss",
            "prediction_timestamp": recent.isoformat(),
            "evaluation_timestamp": (recent + timedelta(hours=1)).isoformat(),
        }
        for index in range(10)
    ] + [
        {
            "symbol": "EURUSD",
            "timeframe": "H1",
            "model_identity": "model-v1",
            "result": "loss",
            "prediction_timestamp": old.isoformat(),
            "evaluation_timestamp": (old + timedelta(hours=1)).isoformat(),
        }
        for _index in range(20)
    ]

    class Database:
        def get_finalized_outcomes(self, symbol=None, timeframe=None, after_id=0):
            return [
                row for row in rows
                if (symbol is None or row["symbol"] == symbol)
                and (timeframe is None or row["timeframe"] == timeframe)
            ]

    monkeypatch.setattr(quality_module, "_utc_now", lambda: now)
    history = ModelQualityHistory(database=Database())

    assert history.get_accuracy("USDJPY", "H1") is None
    assert history.get_win_rate("USDJPY", "H1") is None
    assert history.get_sample_count("USDJPY", "H1") == 0
    assert history.get_sample_count("EURUSD", "H1") == 10
    assert history.get_accuracy("EURUSD", "H1") == pytest.approx(60.0)
    assert history.list_history()[0]["samples"] == 10


def test_missing_quality_evidence_reaches_risk_consumer_as_none(monkeypatch):
    import forex.prediction.prediction_context as context_module
    import forex.prediction.roadmap_v_integration as roadmap

    captured = []
    frame = pd.DataFrame({"close": [1.1], "atr_14": [0.01]})
    monkeypatch.setattr(context_module, "_atr_stats", lambda _df: (0.01, 50.0, "normal"))
    monkeypatch.setattr(context_module, "_circuit_breaker_state", lambda: (False, {"open": True}))
    monkeypatch.setattr(context_module, "_news_state", lambda _pair: (False, ""))
    monkeypatch.setattr(context_module, "_model_performance", lambda *_args: (None, 0))
    monkeypatch.setattr(
        roadmap,
        "run_regime_detection",
        lambda *_args, **_kwargs: type("Regime", (), {
            "primary": "ranging",
            "confidence": 80.0,
            "volatility_level": "normal",
            "atr_percentile": 50.0,
        })(),
    )
    monkeypatch.setattr(
        roadmap,
        "run_mtf_coherence",
        lambda *_args, **_kwargs: type("MTF", (), {
            "coherence_score": 80.0,
            "coherent": True,
            "forced_hold": False,
        })(),
    )
    monkeypatch.setattr(
        roadmap,
        "run_reliability_score",
        lambda **_kwargs: type("Reliability", (), {"reliability_score": 80.0})(),
    )

    def risk_consumer(**kwargs):
        captured.append(kwargs["model_win_rate"])
        return RiskEngine().assess(**{
            key: value for key, value in kwargs.items()
            if key not in {"verbose", "config"}
        })

    monkeypatch.setattr(roadmap, "run_risk_engine", risk_consumer)

    context = context_module.build_context(
        frame,
        pair="EURUSD",
        timeframe="H1",
        signal="BUY",
        model_confidence=0.8,
        h4_df=frame,
        d1_df=frame,
    )

    assert captured == [None]
    assert context.risk.valid is False
    assert "non_finite_risk_input" in context.risk.blocking_reasons

    reliability = ReliabilityScorer().compute(
        model_confidence=0.8,
        model_win_rate=None,
        model_recent_predictions=0,
    )
    history_component = next(
        component for component in reliability.components
        if component.name == "model_history"
    )
    assert history_component.score is None
    assert history_component.weighted_score == 0.0
    assert reliability.breakdown["model_history"]["score"] is None


@pytest.mark.parametrize("action", ["BUY", "SELL"])
def test_final_buy_sell_prediction_is_persisted_once(closed_loop, action):
    database, tracker, _ = closed_loop
    first = _record(tracker, action=action)
    second = _record(tracker, action=action)

    assert first == second
    rows = database.get_predictions("EURUSD", "H1")
    assert len(rows) == 1
    assert rows[0]["action"] == action


def test_raw_buy_with_final_hold_never_creates_operational_outcome(closed_loop):
    database, tracker, _ = closed_loop
    candle = BASE.isoformat()
    database.save_prediction({
        "symbol": "EURUSD",
        "timeframe": "H1",
        "action": "HOLD",
        "raw_action": "BUY",
        "entry_price": 100.0,
        "candle_timestamp": candle,
        "predicted_at": candle,
    })

    finalized = tracker.evaluate_pending(
        _candles((BASE + timedelta(hours=1), 105.0)),
        available_at=BASE + timedelta(hours=2),
    )

    assert finalized == 0
    assert database.get_outcomes() == []
    assert tracker.get_stats("EURUSD").total_predictions == 0


def test_prediction_does_not_mature_without_complete_closed_horizon(closed_loop):
    database, tracker, _ = closed_loop
    prediction_id = _record(tracker, horizon=2)
    candles = _candles(
        (BASE + timedelta(hours=1), 101.0),
        (BASE + timedelta(hours=2), 102.0),
    )

    assert tracker.evaluate_pending(
        candles, available_at=BASE + timedelta(hours=2, minutes=30)
    ) == 0
    assert database.get_prediction(prediction_id)["status"] == "PENDING"
    assert database.get_outcomes() == []


def test_real_closed_future_candles_finalize_outcome(closed_loop):
    database, tracker, _ = closed_loop
    prediction_id = _record(tracker, horizon=2)
    candles = _candles(
        (BASE + timedelta(hours=1), 101.0),
        (BASE + timedelta(hours=2), 102.0),
    )

    assert tracker.evaluate_pending(
        candles, available_at=BASE + timedelta(hours=3)
    ) == 1
    outcome = database.get_outcomes()[0]
    assert outcome["prediction_id"] == prediction_id
    assert outcome["status"] == "FINALIZED"
    assert outcome["result"] == "win"
    assert outcome["observed_price"] == 102.0


def test_missing_intermediate_candle_keeps_outcome_pending(closed_loop):
    database, tracker, _ = closed_loop
    prediction_id = _record(tracker, horizon=3)
    candles_with_gap = _candles(
        (BASE + timedelta(hours=1), 101.0),
        (BASE + timedelta(hours=3), 103.0),
        (BASE + timedelta(hours=4), 104.0),
    )

    assert tracker.evaluate_pending(
        candles_with_gap, available_at=BASE + timedelta(hours=5)
    ) == 0
    assert database.get_prediction(prediction_id)["status"] == "PENDING"

    contiguous_candles = _candles(
        (BASE + timedelta(hours=1), 101.0),
        (BASE + timedelta(hours=2), 102.0),
        (BASE + timedelta(hours=3), 103.0),
        (BASE + timedelta(hours=4), 104.0),
    )
    assert tracker.evaluate_pending(
        contiguous_candles, available_at=BASE + timedelta(hours=5)
    ) == 1
    assert database.get_outcomes()[0]["observed_price"] == 103.0


def test_absent_future_data_stays_pending_without_synthetic_outcome(closed_loop):
    database, tracker, _ = closed_loop
    prediction_id = _record(tracker, horizon=2)

    assert tracker.evaluate_pending(
        _candles((BASE, 100.0)), available_at=BASE + timedelta(days=10)
    ) == 0
    assert database.get_prediction(prediction_id)["status"] == "PENDING"
    assert database.get_outcomes() == []


def test_outcome_tracker_is_idempotent(closed_loop):
    database, tracker, _ = closed_loop
    _record(tracker, horizon=1)
    candles = _candles((BASE + timedelta(hours=1), 101.0))

    assert tracker.evaluate_pending(candles, available_at=BASE + timedelta(hours=2)) == 1
    assert tracker.evaluate_pending(candles, available_at=BASE + timedelta(hours=2)) == 0
    assert len(database.get_outcomes()) == 1


def test_prediction_and_outcome_survive_sqlite_reopen(closed_loop):
    database, tracker, db_path = closed_loop
    prediction_id = _record(tracker, horizon=1)
    tracker.evaluate_pending(
        _candles((BASE + timedelta(hours=1), 101.0)),
        available_at=BASE + timedelta(hours=2),
    )

    reopened = SQLiteDatabase(str(db_path))
    assert reopened.get_prediction(prediction_id)["status"] == "FINALIZED"
    assert reopened.get_outcomes()[0]["prediction_id"] == prediction_id


def test_performance_is_a_restart_stable_projection_without_double_count(closed_loop):
    database, tracker, db_path = closed_loop
    _record(tracker, horizon=1)
    candles = _candles((BASE + timedelta(hours=1), 101.0))
    tracker.evaluate_pending(candles, available_at=BASE + timedelta(hours=2))
    tracker.evaluate_pending(candles, available_at=BASE + timedelta(hours=3))

    before = tracker.get_stats("EURUSD")
    after = OutcomeTracker(db_path).get_stats("EURUSD")
    assert before.evaluated == after.evaluated == 1
    assert before.correct == after.correct == 1
    assert before.win_rate == after.win_rate == 1.0


def test_retrain_is_not_eligible_without_sufficient_outcomes(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    _seed_finalized_outcomes(database, 1)
    manager, _ = _manager(tmp_path, database, minimum=2)

    assert manager.ensure_pending_from_outcomes(
        "EURUSD", dataset_provenance={"snapshot": "v1"}
    ) is None
    assert database.get_retrain_runs() == []


def test_same_outcomes_do_not_create_duplicate_retrain(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    _seed_finalized_outcomes(database, 2)
    manager, _ = _manager(tmp_path, database, minimum=2)

    first = manager.ensure_pending_from_outcomes(
        "EURUSD", dataset_provenance={"snapshot": "v1"}
    )
    second = manager.ensure_pending_from_outcomes(
        "EURUSD", dataset_provenance={"snapshot": "v1"}
    )
    assert first["run_id"] == second["run_id"]
    assert len(database.get_retrain_runs()) == 1


def test_new_eligible_outcomes_create_persistent_pending_run(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    expected_ids = _seed_finalized_outcomes(database, 2)
    manager, _ = _manager(tmp_path, database, minimum=2)

    run = manager.ensure_pending_from_outcomes(
        "EURUSD", dataset_provenance={"snapshot": "v1"}
    )
    assert run["status"] == "PENDING"
    assert json.loads(run["outcome_ids"]) == expected_ids


def test_training_failure_preserves_previous_latest(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    manager, storage, run = _pending_run(tmp_path, database)
    latest = storage.base_dir / "latest_EURUSD.pkl"
    previous = latest.read_bytes()

    result = manager.execute_retrain(
        run["run_id"],
        lambda *_args: (_ for _ in ()).throw(RuntimeError("training failed")),
    )

    assert result["status"] == "FAILED"
    assert latest.read_bytes() == previous


def test_validation_failure_preserves_previous_latest(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    manager, storage, run = _pending_run(tmp_path, database)
    latest = storage.base_dir / "latest_EURUSD.pkl"
    previous = latest.read_bytes()

    result = manager.execute_retrain(
        run["run_id"], lambda *_args: {"model": {"version": 2}},
        validator=lambda _model: False,
    )

    assert result["status"] == "FAILED"
    assert latest.read_bytes() == previous


def test_promotion_failure_preserves_latest_and_never_claims_success(tmp_path, monkeypatch):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    manager, storage, run = _pending_run(tmp_path, database)
    latest = storage.base_dir / "latest_EURUSD.pkl"
    previous = latest.read_bytes()

    def fail_promotion(*_args, **_kwargs):
        raise OSError("promotion failed")

    monkeypatch.setattr(storage, "promote_artifact", fail_promotion)
    result = manager.execute_retrain(
        run["run_id"], lambda *_args: {"model": {"version": 2}}
    )

    assert result["status"] == "FAILED"
    assert latest.read_bytes() == previous
    assert [row["status"] for row in database.get_model_provenance()] == [
        "INITIAL_TRAINING"
    ]


def test_db_finalize_failure_rolls_back_promoted_alias(tmp_path, monkeypatch):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    manager, storage, run = _pending_run(tmp_path, database)
    latest = storage.base_dir / "latest_EURUSD.pkl"
    previous = latest.read_bytes()

    monkeypatch.setattr(
        database,
        "finalize_model_promotion",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down")),
    )
    result = manager.execute_retrain(
        run["run_id"], lambda *_args: {"model": {"version": 2}}
    )

    assert result["status"] == "FAILED"
    assert latest.read_bytes() == previous
    assert [row["status"] for row in database.get_model_provenance()] == [
        "INITIAL_TRAINING"
    ]


def test_successful_retrain_validates_promotes_and_persists_provenance(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    manager, storage, run = _pending_run(tmp_path, database)

    result = manager.execute_retrain(
        run["run_id"],
        lambda *_args: {"model": {"version": 2}, "metadata": {"accuracy": 0.7}},
        validator=lambda model: model["version"] == 2,
    )

    latest = storage.base_dir / "latest_EURUSD.pkl"
    assert result["status"] == "PROMOTED"
    assert joblib.load(latest)["model"]["version"] == 2
    provenance = database.get_model_provenance("EURUSD")[0]
    assert provenance["retrain_run_id"] == run["run_id"]
    assert provenance["artifact_sha256"] == storage.checksum(latest)


def test_model_provenance_links_source_dataset_outcomes_and_run(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    manager, _storage, run = _pending_run(tmp_path, database)
    result = manager.execute_retrain(
        run["run_id"], lambda *_args: {"model": {"version": 2}}
    )

    provenance = database.get_model_provenance("EURUSD")[0]
    assert provenance["source_model_path"] == run["source_model_path"]
    assert provenance["source_model_sha256"] == run["source_model_sha256"]
    assert json.loads(provenance["dataset_provenance"])["snapshot"] == "dataset-v1"
    assert json.loads(provenance["outcome_ids"]) == json.loads(run["outcome_ids"])
    assert provenance["retrain_run_id"] == result["run_id"]


def test_promoted_db_record_with_missing_latest_is_detected_fail_closed(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    manager, storage, run = _pending_run(tmp_path, database)
    manager.execute_retrain(run["run_id"], lambda *_args: {"model": {"version": 2}})
    (storage.base_dir / "latest_EURUSD.pkl").unlink()

    report = manager.reconcile()
    assert report["healthy"] is False
    assert report["issues"] == [{
        "run_id": run["run_id"],
        "symbol": "EURUSD",
        "code": "latest_missing",
    }]


def test_interrupted_running_retrain_is_recovered_deterministically(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    manager, _storage, run = _pending_run(tmp_path, database)
    stale = datetime.now(timezone.utc) - timedelta(hours=7)
    database.update_retrain_run(run["run_id"], {
        "status": "RUNNING",
        "owner_token": "foreign-process",
        "heartbeat_at": stale.isoformat(),
        "updated_at": stale.isoformat(),
    })

    first = manager.reconcile()
    second = manager.reconcile()
    recovered = database.get_retrain_runs()[0]
    assert first["recovered"] == [run["run_id"]]
    assert second["recovered"] == []
    assert recovered["status"] == "FAILED"
    assert "interrupted" in recovered["error"]


def test_fresh_foreign_running_retrain_is_left_running(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    manager, _storage, run = _pending_run(tmp_path, database)
    fresh = datetime.now(timezone.utc).isoformat()
    database.update_retrain_run(run["run_id"], {
        "status": "RUNNING",
        "owner_token": "foreign-process",
        "heartbeat_at": fresh,
        "updated_at": fresh,
    })

    report = manager.reconcile()

    assert report["recovered"] == []
    assert database.get_retrain_runs()[0]["status"] == "RUNNING"


def test_prediction_id_rejects_conflicting_immutable_evidence(closed_loop):
    database, tracker, _ = closed_loop
    prediction_id = _record(tracker, horizon=2)
    original = database.get_prediction(prediction_id)

    with pytest.raises(PersistenceConflictError, match="entry_price"):
        database.save_prediction({
            "prediction_id": prediction_id,
            "symbol": original["symbol"],
            "timeframe": original["timeframe"],
            "action": original["action"],
            "raw_action": original["raw_action"],
            "confidence": original["confidence"],
            "entry_price": 100.01,
            "stop_loss": original["stop_loss"],
            "take_profit": original["take_profit"],
            "features_snapshot": json.loads(original["features_snapshot"]),
            "pipeline_version": original["pipeline_version"],
            "predicted_at": original["predicted_at"],
            "candle_timestamp": original["candle_timestamp"],
            "horizon_candles": original["horizon_candles"],
            "model_identity": original["model_identity"],
            "dataset_provenance": json.loads(original["dataset_provenance"]),
        })


def test_outcome_key_rejects_conflicting_immutable_evidence(closed_loop):
    database, tracker, _ = closed_loop
    prediction_id = _record(tracker, horizon=1)
    tracker.evaluate_pending(
        _candles((BASE + timedelta(hours=1), 101.0)),
        available_at=BASE + timedelta(hours=2),
    )
    original = database.get_outcomes()[0]

    with pytest.raises(PersistenceConflictError, match="observed_price"):
        database.save_outcome({
            "prediction_id": prediction_id,
            "outcome_key": original["outcome_key"],
            "symbol": original["symbol"],
            "timeframe": original["timeframe"],
            "actual_direction": original["actual_direction"],
            "pnl_pips": original["pnl_pips"],
            "hit_tp": original["hit_tp"],
            "hit_sl": original["hit_sl"],
            "prediction_timestamp": original["prediction_timestamp"],
            "evaluation_timestamp": original["evaluation_timestamp"],
            "action": original["action"],
            "entry_price": original["entry_price"],
            "observed_price": 101.01,
            "observed_return": original["observed_return"],
            "result": original["result"],
            "status": original["status"],
            "model_identity": original["model_identity"],
            "dataset_provenance": json.loads(original["dataset_provenance"]),
        })


def test_identical_outcome_evidence_is_idempotent(closed_loop):
    database, tracker, _ = closed_loop
    prediction_id = _record(tracker, horizon=1)
    evidence = {
        "prediction_id": prediction_id,
        "outcome_key": prediction_id,
        "symbol": "EURUSD",
        "timeframe": "H1",
        "actual_direction": "BUY",
        "prediction_timestamp": BASE.isoformat(),
        "evaluation_timestamp": (BASE + timedelta(hours=2)).isoformat(),
        "action": "BUY",
        "entry_price": 100.0,
        "observed_price": 101.0,
        "observed_return": 0.01,
        "result": "win",
        "status": "FINALIZED",
        "model_identity": "source-model-sha",
        "dataset_provenance": {
            "registry_id": 1,
            "last_candle_timestamp": BASE.isoformat(),
            "regime": "",
            "mtf_coherent": False,
            "news_active": False,
        },
    }

    first = database.save_outcome(evidence)
    second = database.save_outcome(evidence)

    assert first["id"] == second["id"]
    assert len(database.get_outcomes()) == 1


def test_new_outcomes_schema_uses_text_prediction_id(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    with database._connection() as connection:
        columns = {
            row[1]: row[2] for row in connection.execute("PRAGMA table_info(outcomes)")
        }

    assert columns["prediction_id"] == "TEXT"


def test_concurrent_duplicate_prediction_insert_is_unique(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    prediction = {
        "symbol": "EURUSD",
        "timeframe": "H1",
        "action": "BUY",
        "entry_price": 100.0,
        "candle_timestamp": BASE.isoformat(),
        "predicted_at": BASE.isoformat(),
        "horizon_candles": 2,
    }

    with ThreadPoolExecutor(max_workers=4) as executor:
        ids = list(executor.map(
            lambda _index: database.save_prediction(prediction)["prediction_id"],
            range(8),
        ))

    assert len(set(ids)) == 1
    assert len(database.get_predictions("EURUSD", "H1")) == 1


def test_concurrent_duplicate_retrain_attempt_trains_once(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "db.sqlite"))
    manager, _storage, run = _pending_run(tmp_path, database)
    calls = []

    def train(*_args):
        calls.append("trained")
        return {"model": {"version": 2}}

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(
            lambda _index: manager.execute_retrain(run["run_id"], train),
            range(2),
        ))

    assert calls == ["trained"]
    assert database.get_retrain_runs()[0]["status"] == "PROMOTED"
    assert {result["status"] for result in results} <= {"RUNNING", "PROMOTED"}


def test_closed_loop_connections_release_temp_directory(tmp_path):
    directory = tmp_path / "release"
    directory.mkdir()
    db_path = directory / "closed-loop.db"
    database = SQLiteDatabase(str(db_path))
    tracker = OutcomeTracker(database=database)
    _record(tracker, horizon=1)
    tracker.evaluate_pending(
        _candles((BASE + timedelta(hours=1), 101.0)),
        available_at=BASE + timedelta(hours=2),
    )
    database.get_outcome_performance("EURUSD", "H1")

    db_path.unlink()
    assert not db_path.exists()
    directory.rmdir()

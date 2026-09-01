"""Operational contracts for the EURUSD/USDJPY Forex shadow runtime."""
from __future__ import annotations

import inspect
import sqlite3
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from forex.prediction import shadow_runtime as shadow
from infra.db.database import PersistenceConflictError, SQLiteDatabase
from scheduler import autonomous_scheduler


RUNTIME_ENV = {
    "ASTRA_FOREX_SHADOW_MODE": "1",
    "ASTRA_FOREX_SHADOW_SYMBOLS": "EURUSD,USDJPY",
    "ASTRA_FOREX_RUNTIME_SYMBOLS": "EURUSD,USDJPY",
    "ASTRA_FOREX_RUNTIME_PROVIDER": "MT5",
    "ASTRA_SHADOW_RETRAIN_CANDLES": "168",
}


class _SerializableModel:
    def predict_proba(self, frame):
        return [[0.25, 0.75] for _ in range(len(frame))]


def _database(tmp_path: Path) -> SQLiteDatabase:
    return SQLiteDatabase(str(tmp_path / "shadow.db"))


def _set_lifecycle(database: SQLiteDatabase, symbol: str, status: str) -> dict:
    row = database.register_candidate(symbol, None, None, None)
    if status != "candidate":
        with sqlite3.connect(database.db_path) as connection:
            connection.execute(
                "UPDATE supported_symbols SET status=? WHERE symbol_code=?",
                (status, symbol),
            )
    return database.get_symbol(symbol)


def _model_metadata(symbol: str, generation: int = 1) -> dict:
    return {
        "symbol": symbol,
        "mode": "shadow",
        "model_contract": shadow.SHADOW_MODEL_CONTRACT,
        "target_profile": shadow.SHADOW_TARGET_PROFILE,
        "target_definition_version": 1,
        "horizon": shadow.SHADOW_HORIZON,
        "feature_profile": shadow.SHADOW_FEATURE_PROFILE,
        "feature_names_sha256": "a" * 64,
        "model_family": "RandomForestClassifier",
        "model_config": shadow.fixed_shadow_rf_config(),
        "training_dataset_hashes": {"H1": "1" * 64, "H4": "4" * 64, "D1": "d" * 64},
        "training_timestamp": "2026-08-01T00:00:00+00:00",
        "training_last_candle": "2026-07-31T23:00:00+00:00",
        "artifact_sha256": "f" * 64,
        "model_generation": generation,
        "model_identity": f"shadow_{symbol}_g{generation:04d}_{'f' * 16}",
    }


def _persist(
    database: SQLiteDatabase,
    symbol: str,
    candle: str,
    action: str,
    *,
    generation: int = 1,
    score: float = 0.8,
    percentile: float = 0.9,
) -> dict:
    return shadow.persist_shadow_prediction(
        database,
        symbol=symbol,
        candle_timestamp=candle,
        entry_price=1.1 if symbol == "EURUSD" else 150.0,
        decision={
            "action": action,
            "direction_score": score,
            "decision_percentile": percentile,
            "decision_extremeness": abs(percentile - 0.5) * 2,
        },
        model_metadata=_model_metadata(symbol, generation),
        dataset_provenance={"H1": {"source_sha256": "1" * 64}},
    )


def _future_candles(
    entry: str,
    entry_price: float,
    closes: list[float],
) -> pd.DataFrame:
    start = pd.Timestamp(entry)
    return pd.DataFrame({
        "timestamp": [start + timedelta(hours=index) for index in range(1, len(closes) + 1)],
        "close": closes,
    })


def test_runtime_symbol_parser_is_exact_and_deduplicated():
    assert shadow.parse_symbol_list(" EURUSD,USDJPY,EURUSD ") == (
        "EURUSD",
        "USDJPY",
    )
    with pytest.raises(ValueError, match="RUNTIME_SYMBOL_UNSUPPORTED"):
        shadow.parse_symbol_list("EURUSD,GBPUSD")


def test_shadow_is_disabled_by_default():
    config = shadow.ShadowRuntimeConfig.from_environment({})
    assert config.enabled is False
    assert config.shadow_symbols == ("EURUSD", "USDJPY")


@pytest.mark.parametrize("symbol", ["EURUSD", "USDJPY"])
def test_qualified_runtime_symbols_are_shadow_eligible(tmp_path, symbol):
    database = _database(tmp_path)
    _set_lifecycle(database, symbol, "qualified")
    config = shadow.ShadowRuntimeConfig.from_environment(RUNTIME_ENV)
    assert shadow.shadow_eligible(database, symbol, config) is True


@pytest.mark.parametrize("status", ["candidate", "disabled", "active"])
def test_nonqualified_lifecycle_is_not_shadow_eligible(tmp_path, status):
    database = _database(tmp_path)
    _set_lifecycle(database, "EURUSD", status)
    config = shadow.ShadowRuntimeConfig.from_environment(RUNTIME_ENV)
    assert shadow.shadow_eligible(database, "EURUSD", config) is False


def test_disabled_shadow_mode_makes_qualified_symbol_ineligible(tmp_path):
    database = _database(tmp_path)
    _set_lifecycle(database, "EURUSD", "qualified")
    config = shadow.ShadowRuntimeConfig.from_environment({**RUNTIME_ENV, "ASTRA_FOREX_SHADOW_MODE": "0"})
    assert shadow.shadow_eligible(database, "EURUSD", config) is False


def test_production_prediction_still_requires_active_lifecycle(tmp_path):
    database = _database(tmp_path)
    _set_lifecycle(database, "EURUSD", "qualified")
    assert autonomous_scheduler.run_prediction(database, "EURUSD", "H1") == {
        "action": "skip",
        "reason": "symbol_not_active",
        "symbol": "EURUSD",
        "status": "qualified",
    }
    assert shadow.run_shadow_prediction is not autonomous_scheduler.run_prediction


def test_production_model_integrity_gate_is_unchanged(monkeypatch):
    class Database:
        pass

    monkeypatch.setattr(
        "robustness.model_integrity_checker.check_model_before_cycle",
        lambda *_args, **_kwargs: False,
    )
    result = autonomous_scheduler._evaluate_h1_model_gate(Database(), "EURUSD", "H1")
    assert result == {
        "prediction_eligible": False,
        "reason": "model_integrity_check_failed",
    }


def test_shadow_storage_is_separate_and_never_resolves_production_alias(tmp_path):
    storage = shadow.ShadowModelStorage(tmp_path / "models" / "forex" / "shadow")
    assert storage.path_for("EURUSD") == tmp_path / "models" / "forex" / "shadow" / "EURUSD.pkl"
    assert "latest_EURUSD.pkl" not in str(storage.path_for("EURUSD"))
    assert storage.path_for("USDJPY") != storage.path_for("EURUSD")


def test_shadow_storage_cannot_create_latest_alias(tmp_path):
    storage = shadow.ShadowModelStorage(tmp_path / "models" / "forex" / "shadow")
    with pytest.raises(ValueError, match="SHADOW_STORAGE_PATH_INVALID"):
        storage.path_for("latest_EURUSD")
    assert not (tmp_path / "models" / "forex" / "latest_EURUSD.pkl").exists()


def test_shadow_storage_roundtrip_binds_checksum_identity_and_generation(tmp_path):
    storage = shadow.ShadowModelStorage(tmp_path / "models" / "forex" / "shadow")
    names = ["feature"]
    metadata = _model_metadata("EURUSD")
    metadata["feature_names_sha256"] = shadow.feature_names_sha256(names)
    metadata.update({
        "decision_policy": shadow.SHADOW_DECISION_POLICY,
        "score_type": shadow.SHADOW_SCORE_TYPE,
        "confidence_semantics": shadow.SHADOW_CONFIDENCE_SEMANTICS,
    })
    saved = storage.save("EURUSD", {
        "model": _SerializableModel(),
        "feature_names": names,
        "oof_score_reference": [index / 599 for index in range(600)],
        "metadata": metadata,
    })
    observed = storage.load("EURUSD")
    assert observed["metadata"]["artifact_sha256"] == saved["metadata"]["artifact_sha256"]
    assert observed["metadata"]["model_identity"] == shadow.shadow_model_identity(
        "EURUSD", 1, observed["metadata"]["artifact_sha256"]
    )
    assert observed["metadata"]["model_generation"] == 1


def test_shadow_registry_requires_ready_h1_h4_d1(monkeypatch, tmp_path):
    database = _database(tmp_path)
    _set_lifecycle(database, "EURUSD", "qualified")
    for timeframe in ("H1", "H4"):
        database.upsert_dataset_registry({
            "symbol": "EURUSD",
            "timeframe": timeframe,
            "candle_count": 2000,
            "rolling_window_size": 2000,
            "blob_path": str(tmp_path / f"EURUSD_{timeframe}.csv"),
            "status": "ready",
            "provider_used": "MT5",
            "external_ticker": "EURUSD",
            "provider_class": "MT5Provider",
            "source_fetched_at": "2026-08-01T00:00:00+00:00",
            "source_sha256": "a" * 64,
            "acquisition_metadata": None,
        })
    monkeypatch.setattr(shadow, "registry_entry_readiness", lambda *_a, **_k: {"ready": True})
    with pytest.raises(ValueError, match="SHADOW_DATASET_D1_NOT_READY"):
        shadow.require_shadow_registry(database, "EURUSD", project_root=tmp_path)


def test_pinned_mt5_fetch_does_not_construct_data_router(monkeypatch):
    calls = []

    class Provider:
        last_acquisition_metadata = {"provider": "MT5"}

        def fetch(self, pair, tf, bars):
            calls.append((pair, tf, bars))
            frame = pd.DataFrame({"close": [1.0]})
            return frame

    monkeypatch.setattr(shadow, "MT5Provider", Provider)
    frame, source = shadow.fetch_pinned_market_data("EURUSD", "H1", 2001, "MT5")
    assert calls == [("EURUSD", "H1", 2001)]
    assert source == "MT5"
    assert frame.attrs["acquisition_metadata"] == {"provider": "MT5"}
    assert "DataRouter" not in inspect.getsource(shadow.fetch_pinned_market_data)


def test_mt5_unavailable_fails_closed_without_fallback(monkeypatch):
    class Provider:
        def fetch(self, *_args, **_kwargs):
            raise RuntimeError("MT5_PACKAGE_UNAVAILABLE")

    monkeypatch.setattr(shadow, "MT5Provider", Provider)
    with pytest.raises(RuntimeError, match="MT5_PACKAGE_UNAVAILABLE"):
        shadow.fetch_pinned_market_data("USDJPY", "H1", 2001, "MT5")


def test_same_candle_and_generation_persists_at_most_once(tmp_path):
    database = _database(tmp_path)
    _set_lifecycle(database, "EURUSD", "qualified")
    first = _persist(database, "EURUSD", "2026-08-01T10:00:00+00:00", "BUY")
    second = _persist(database, "EURUSD", "2026-08-01T10:00:00+00:00", "BUY")
    assert first["prediction_id"] == second["prediction_id"]
    assert len(database.get_predictions("EURUSD", "H1", limit=100)) == 1


def test_same_shadow_identity_rejects_conflicting_decision(tmp_path):
    database = _database(tmp_path)
    _set_lifecycle(database, "EURUSD", "qualified")
    _persist(database, "EURUSD", "2026-08-01T10:00:00+00:00", "BUY")
    with pytest.raises(PersistenceConflictError):
        _persist(database, "EURUSD", "2026-08-01T10:00:00+00:00", "SELL")


def test_hold_is_persisted_but_never_enters_directional_pending_loop(tmp_path):
    database = _database(tmp_path)
    _set_lifecycle(database, "EURUSD", "qualified")
    saved = _persist(database, "EURUSD", "2026-08-01T10:00:00+00:00", "HOLD")
    assert saved["action"] == "HOLD"
    assert saved["execution_mode"] == "shadow"
    assert saved["status"] == "PENDING"
    assert database.get_pending_predictions("EURUSD") == []
    assert shadow.mature_shadow_outcomes(
        database,
        "EURUSD",
        _future_candles(saved["candle_timestamp"], 1.1, [1.2] * 12),
        available_at="2026-08-01T23:00:00+00:00",
    ) == 0


@pytest.mark.parametrize(
    ("action", "last_close", "correct"),
    [("BUY", 1.2, True), ("SELL", 1.0, True), ("SELL", 1.2, False)],
)
def test_directional_outcome_matures_after_exactly_twelve_closed_h1_candles(
    tmp_path, action, last_close, correct
):
    database = _database(tmp_path)
    _set_lifecycle(database, "EURUSD", "qualified")
    entry = "2026-08-01T10:00:00+00:00"
    saved = _persist(database, "EURUSD", entry, action)
    closes = [1.1] * 11 + [last_close]
    candles = _future_candles(entry, 1.1, closes)
    assert shadow.mature_shadow_outcomes(
        database, "EURUSD", candles.iloc[:11], available_at="2026-08-01T22:00:00+00:00"
    ) == 0
    assert shadow.mature_shadow_outcomes(
        database, "EURUSD", candles, available_at="2026-08-01T23:00:00+00:00"
    ) == 1
    outcome = database.get_shadow_outcomes("EURUSD")[0]
    assert outcome["prediction_id"] == saved["prediction_id"]
    assert bool(outcome["direction_correct"]) is correct
    assert outcome["evaluation_candle"] == candles.iloc[-1]["timestamp"].isoformat()
    assert outcome["execution_mode"] == "shadow"


def test_symbol_outcomes_are_isolated(tmp_path):
    database = _database(tmp_path)
    _set_lifecycle(database, "EURUSD", "qualified")
    _set_lifecycle(database, "USDJPY", "qualified")
    entry = "2026-08-01T10:00:00+00:00"
    _persist(database, "EURUSD", entry, "BUY")
    _persist(database, "USDJPY", entry, "SELL")
    candles = _future_candles(entry, 1.1, [1.2] * 12)
    assert shadow.mature_shadow_outcomes(
        database, "EURUSD", candles, available_at="2026-08-01T23:00:00+00:00"
    ) == 1
    assert len(database.get_shadow_outcomes("EURUSD")) == 1
    assert database.get_shadow_outcomes("USDJPY") == []


def test_shadow_models_are_independent_per_symbol(tmp_path):
    storage = shadow.ShadowModelStorage(tmp_path / "shadow")
    assert storage.path_for("EURUSD") != storage.path_for("USDJPY")
    assert shadow.shadow_model_identity("EURUSD", 1, "a" * 64) != shadow.shadow_model_identity(
        "USDJPY", 1, "a" * 64
    )


@pytest.mark.parametrize(
    ("expected", "observed"),
    [("EURUSD", "USDJPY"), ("USDJPY", "EURUSD")],
)
def test_cross_fx_rows_are_rejected(expected, observed):
    frame = pd.DataFrame({"pair": [expected, observed], "close": [1.0, 1.0]})
    with pytest.raises(ValueError, match="SHADOW_CROSS_SYMBOL_DATA"):
        shadow.require_single_symbol_frame(frame, expected, timeframe="H1")


def test_retrain_cadence_is_exactly_168_new_h1_candles():
    cutoff = pd.Timestamp("2026-08-01T00:00:00Z")
    timestamps = pd.date_range(cutoff + timedelta(hours=1), periods=168, freq="h")
    assert shadow.count_new_h1_candles(cutoff, timestamps[:167]) == 167
    assert shadow.shadow_retrain_due(cutoff, timestamps[:167], cadence=168) is False
    assert shadow.shadow_retrain_due(cutoff, timestamps, cadence=168) is True


def test_retrain_decision_has_no_performance_input():
    signature = inspect.signature(shadow.shadow_retrain_due)
    assert set(signature.parameters) == {"training_cutoff", "h1_timestamps", "cadence"}


def test_model_generation_increments_only_from_prior_artifact():
    assert shadow.next_shadow_generation(None) == 1
    assert shadow.next_shadow_generation({"model_generation": 1}) == 2
    assert shadow.next_shadow_generation({"model_generation": 9}) == 10


def test_historical_prediction_retains_old_model_identity(tmp_path):
    database = _database(tmp_path)
    _set_lifecycle(database, "EURUSD", "qualified")
    first = _persist(database, "EURUSD", "2026-08-01T10:00:00+00:00", "BUY", generation=1)
    second = _persist(database, "EURUSD", "2026-08-01T11:00:00+00:00", "SELL", generation=2)
    rows = database.get_predictions("EURUSD", "H1", limit=100)
    by_id = {row["prediction_id"]: row for row in rows}
    assert by_id[first["prediction_id"]]["model_identity"] == _model_metadata("EURUSD", 1)["model_identity"]
    assert by_id[second["prediction_id"]]["model_identity"] == _model_metadata("EURUSD", 2)["model_identity"]


def test_shadow_module_has_no_trading_activation_or_promotion_dependency():
    source = inspect.getsource(shadow)
    forbidden = (
        "place_order",
        "order_send",
        "DecisionEngine",
        "activate_qualified_symbol",
        "promote_initial_model",
        "finalize_model_promotion",
        "latest_",
    )
    assert not any(token in source for token in forbidden)


def test_shadow_persistence_does_not_change_lifecycle_or_create_production_model(tmp_path):
    database = _database(tmp_path)
    _set_lifecycle(database, "USDJPY", "qualified")
    _persist(database, "USDJPY", "2026-08-01T10:00:00+00:00", "BUY")
    assert database.get_symbol("USDJPY")["status"] == "qualified"
    assert not (tmp_path / "models" / "forex" / "latest_USDJPY.pkl").exists()


def test_shadow_metrics_separate_hold_coverage_and_directional_accuracy(tmp_path):
    database = _database(tmp_path)
    _set_lifecycle(database, "EURUSD", "qualified")
    entry = "2026-08-01T10:00:00+00:00"
    _persist(database, "EURUSD", entry, "BUY")
    _persist(database, "EURUSD", "2026-08-01T11:00:00+00:00", "HOLD")
    candles = _future_candles(entry, 1.1, [1.2] * 12)
    shadow.mature_shadow_outcomes(
        database, "EURUSD", candles, available_at="2026-08-01T23:00:00+00:00"
    )
    metrics = shadow.shadow_metrics(database, "EURUSD")
    assert metrics["total_predictions"] == 2
    assert metrics["buy_count"] == 1
    assert metrics["sell_count"] == 0
    assert metrics["hold_count"] == 1
    assert metrics["coverage"] == 0.5
    assert metrics["evaluated_directional"] == 1
    assert metrics["pooled_directional_accuracy"] == 1.0


def test_status_includes_both_runtime_symbols(tmp_path):
    database = _database(tmp_path)
    _set_lifecycle(database, "EURUSD", "qualified")
    _set_lifecycle(database, "USDJPY", "candidate")
    runtime = shadow.ShadowForexRuntime(
        database,
        project_root=tmp_path,
        config=shadow.ShadowRuntimeConfig.from_environment(RUNTIME_ENV),
    )
    status = runtime.status()
    assert status["shadow_mode"] is True
    assert status["runtime_symbols"] == ["EURUSD", "USDJPY"]
    assert set(status["symbols"]) == {"EURUSD", "USDJPY"}
    assert status["symbols"]["EURUSD"]["lifecycle"] == "qualified"
    assert status["symbols"]["USDJPY"]["lifecycle"] == "candidate"


def test_legacy_scheduler_symbol_scope_is_unchanged_when_config_absent():
    rows = [
        {"symbol_code": "EURUSD", "status": "qualified"},
        {"symbol_code": "GBPUSD", "status": "active"},
        {"symbol_code": "USDJPY", "status": "qualified"},
    ]

    class Database:
        def get_data_symbols(self):
            return rows

    config = shadow.ShadowRuntimeConfig.from_environment({})
    assert autonomous_scheduler._select_cycle_symbols(Database(), config) == rows


def test_configured_scheduler_scope_is_exactly_eurusd_usdjpy():
    rows = [
        {"symbol_code": "EURUSD", "status": "qualified"},
        {"symbol_code": "GBPUSD", "status": "active"},
        {"symbol_code": "USDJPY", "status": "qualified"},
        {"symbol_code": "AUDUSD", "status": "active"},
    ]

    class Database:
        def get_data_symbols(self):
            return rows

    config = shadow.ShadowRuntimeConfig.from_environment(RUNTIME_ENV)
    selected = autonomous_scheduler._select_cycle_symbols(Database(), config)
    assert [row["symbol_code"] for row in selected] == ["EURUSD", "USDJPY"]


def test_h1_scheduler_shadow_path_pins_mt5_and_processes_only_runtime_symbols(
    monkeypatch, tmp_path
):
    database = _database(tmp_path)
    _set_lifecycle(database, "EURUSD", "qualified")
    _set_lifecycle(database, "USDJPY", "qualified")
    _set_lifecycle(database, "GBPUSD", "active")
    monkeypatch.setenv("ASTRA_FOREX_SHADOW_MODE", "1")
    monkeypatch.setenv("ASTRA_FOREX_SHADOW_SYMBOLS", "EURUSD,USDJPY")
    monkeypatch.setenv("ASTRA_FOREX_RUNTIME_SYMBOLS", "EURUSD,USDJPY")
    monkeypatch.setenv("ASTRA_FOREX_RUNTIME_PROVIDER", "MT5")
    updates = []
    maintained = []
    monkeypatch.setattr(
        autonomous_scheduler,
        "run_rolling_update",
        lambda _db, symbol, timeframe, *, provider=None: (
            updates.append((symbol, timeframe, provider)) or {"action": "updated"}
        ),
    )
    monkeypatch.setattr(
        shadow.ShadowForexRuntime,
        "maintain_h1",
        lambda _runtime, symbol: (
            maintained.append(symbol)
            or {"prediction": {"action": "predicted"}}
        ),
    )
    result = autonomous_scheduler.run_cycle(database, "H1")
    assert updates == [
        ("EURUSD", "H1", "MT5"),
        ("USDJPY", "H1", "MT5"),
    ]
    assert maintained == ["EURUSD", "USDJPY"]
    assert result["symbols_processed"] == 2
    assert result["predictions_generated"] == 2
    assert result["errors_count"] == 0


def test_shadow_contract_uses_frozen_operational_baseline_only():
    assert shadow.SHADOW_MODEL_CONTRACT == "shadow_multiframe_directional_v1"
    assert shadow.SHADOW_TARGET_PROFILE == "fixed_horizon_direction_v1"
    assert shadow.SHADOW_HORIZON == 12
    assert shadow.SHADOW_FEATURE_PROFILE == "stationary_v1"
    assert shadow.SHADOW_DECISION_POLICY == "shadow_oof_quartile_abstention_v1"
    assert shadow.fixed_shadow_rf_config() == {
        "n_estimators": 300,
        "max_depth": 8,
        "min_samples_leaf": 15,
        "class_weight_strategy": "TRAIN_NEGATIVE_TO_POSITIVE_RATIO",
        "random_state": 42,
        "n_jobs": -1,
    }

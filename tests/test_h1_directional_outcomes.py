"""Terminal-direction outcome semantics for the H1 production contract."""
from __future__ import annotations

import pandas as pd
import pytest

from forex.prediction.h1_directional import (
    H1_CONFIDENCE_SEMANTICS,
    H1_DECISION_POLICY,
    H1_FEATURE_PROFILE,
    H1_HORIZON,
    H1_MODEL_CONTRACT,
    H1_SCORE_TYPE,
    H1_TARGET_DEFINITION_VERSION,
    H1_TARGET_PROFILE,
    H1_TERMINAL_DIRECTION_EVALUATION,
)
from forex.prediction.outcome_tracker import OutcomeTracker
from infra.db.database import SQLiteDatabase


def _active_database(path):
    from forex.data.symbol_catalog import get_symbol_spec

    database = SQLiteDatabase(str(path))
    spec = get_symbol_spec("EURUSD")
    database.register_candidate(
        spec.symbol_code, spec.display_name, spec.asset_class, spec.pip_value
    )
    with database._connection() as connection:
        connection.execute(
            "UPDATE supported_symbols SET status='active' WHERE symbol_code='EURUSD'"
        )
    return database


def _candles(final_close: float, *, missing_position: int | None = None):
    timestamps = pd.date_range("2026-01-01 01:00:00", periods=12, freq="h", tz="UTC")
    closes = [1.0 + index * 0.00001 for index in range(12)]
    closes[-1] = final_close
    frame = pd.DataFrame({"timestamp": timestamps, "close": closes})
    if missing_position is not None:
        frame = frame.drop(index=missing_position).reset_index(drop=True)
    return frame


def _record(tracker: OutcomeTracker, action: str, *, h1: bool = True) -> str:
    kwargs = {}
    if h1:
        kwargs = {
            "model_contract": H1_MODEL_CONTRACT,
            "target_profile": H1_TARGET_PROFILE,
            "target_definition_version": H1_TARGET_DEFINITION_VERSION,
            "feature_profile": H1_FEATURE_PROFILE,
            "score_type": H1_SCORE_TYPE,
            "direction_score": 0.8 if action == "BUY" else 0.2,
            "decision_percentile": 0.8 if action == "BUY" else 0.2,
            "decision_policy": H1_DECISION_POLICY,
            "confidence_semantics": H1_CONFIDENCE_SEMANTICS,
        }
    return tracker.record_prediction(
        pair="EURUSD",
        timeframe="H1",
        signal=action,
        entry_price=1.0,
        reliability_score=0.6,
        candle_timestamp="2026-01-01 00:00:00+00:00",
        prediction_timestamp="2026-01-01 01:00:00+00:00",
        horizon_candles=H1_HORIZON,
        model_identity="synthetic-h1" if h1 else "legacy",
        dataset_provenance={"snapshot_sha256": "synthetic"},
        **kwargs,
    )


@pytest.mark.parametrize(
    ("action", "final_close", "expected"),
    [
        ("BUY", 1.01, "win"),
        ("BUY", 1.00, "loss"),
        ("BUY", 0.99, "loss"),
        ("SELL", 0.99, "win"),
        ("SELL", 1.00, "win"),
        ("SELL", 1.01, "loss"),
    ],
)
def test_h1_outcomes_match_exact_fixed_horizon_target(
    tmp_path, action, final_close, expected
):
    database = _active_database(tmp_path / f"{action}-{final_close}.sqlite")
    tracker = OutcomeTracker(database=database)
    prediction_id = _record(tracker, action)

    finalized = tracker.evaluate_pending(
        _candles(final_close),
        pair="EURUSD",
        available_at="2026-01-01 13:00:00+00:00",
    )

    assert finalized == 1
    outcome = database.get_finalized_outcomes("EURUSD", "H1")[0]
    assert outcome["prediction_id"] == prediction_id
    assert outcome["result"] == expected
    assert outcome["evaluation_semantics"] == H1_TERMINAL_DIRECTION_EVALUATION
    assert outcome["model_contract"] == H1_MODEL_CONTRACT
    assert outcome["target_profile"] == H1_TARGET_PROFILE
    assert outcome["horizon_candles"] == 12
    assert outcome["hit_tp"] is None
    assert outcome["hit_sl"] is None


def test_legacy_sell_exact_zero_remains_strict_loss(tmp_path):
    database = _active_database(tmp_path / "legacy-zero.sqlite")
    tracker = OutcomeTracker(database=database)
    _record(tracker, "SELL", h1=False)

    assert tracker.evaluate_pending(
        _candles(1.0),
        pair="EURUSD",
        available_at="2026-01-01 13:00:00+00:00",
    ) == 1

    outcome = database.get_finalized_outcomes("EURUSD", "H1")[0]
    assert outcome["result"] == "loss"
    assert outcome["actual_direction"] == "HOLD"
    assert outcome["evaluation_semantics"] is None
    assert outcome["hit_tp"] == 0
    assert outcome["hit_sl"] == 0


def test_hold_never_enters_pending_outcome_loop(tmp_path):
    tracker = OutcomeTracker(database=_active_database(tmp_path / "hold.sqlite"))

    with pytest.raises(ValueError, match="only final BUY/SELL"):
        tracker.record_prediction(
            pair="EURUSD",
            timeframe="H1",
            signal="HOLD",
            entry_price=1.0,
            candle_timestamp="2026-01-01 00:00:00+00:00",
            horizon_candles=12,
            model_contract=H1_MODEL_CONTRACT,
            target_profile=H1_TARGET_PROFILE,
        )

    assert tracker.get_pending("EURUSD") == []


def test_h1_requires_all_twelve_exact_closed_candles(tmp_path):
    database = _active_database(tmp_path / "maturity.sqlite")
    tracker = OutcomeTracker(database=database)
    _record(tracker, "BUY")

    assert tracker.evaluate_pending(
        _candles(1.01).iloc[:-1],
        pair="EURUSD",
        available_at="2026-01-01 13:00:00+00:00",
    ) == 0
    assert tracker.evaluate_pending(
        _candles(1.01),
        pair="EURUSD",
        available_at="2026-01-01 12:59:59+00:00",
    ) == 0
    assert tracker.evaluate_pending(
        _candles(1.01),
        pair="EURUSD",
        available_at="2026-01-01 13:00:00+00:00",
    ) == 1


def test_missing_intermediate_candle_prevents_h1_finalization(tmp_path):
    database = _active_database(tmp_path / "missing-candle.sqlite")
    tracker = OutcomeTracker(database=database)
    _record(tracker, "SELL")

    assert tracker.evaluate_pending(
        _candles(0.99, missing_position=5),
        pair="EURUSD",
        available_at="2026-01-01 13:00:00+00:00",
    ) == 0
    assert database.get_finalized_outcomes("EURUSD", "H1") == []

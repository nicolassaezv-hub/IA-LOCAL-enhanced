"""Causal and isolation contracts for the Forex historical replay."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from forex.replay.historical_replay import (
    EVENT_PRIORITY,
    HistoricalReplayConfig,
    ReplayDuplicateError,
    ReplayLookaheadError,
    ReplayPredictionBook,
    assert_symbol_isolation,
    assert_training_causal,
    build_event_queue,
    candle_available_at,
    descriptive_metrics,
    initial_rolling_cut,
    replay_prediction_id,
    retrain_due,
    snapshot_paths,
    source_sha256,
    verify_snapshots,
    visible_source,
)


START = pd.Timestamp("2026-07-01T00:00:00Z")
END = pd.Timestamp("2026-09-01T00:00:00Z")


def _frame(start: str, periods: int, frequency: str, symbol: str = "EURUSD"):
    timestamp = pd.date_range(start, periods=periods, freq=frequency, tz="UTC")
    close = pd.Series(range(periods), dtype=float) + 100.0
    return pd.DataFrame({
        "timestamp": timestamp,
        "open": close,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": 1.0,
        "pair": symbol,
    })


@pytest.mark.parametrize(
    ("timeframe", "delta"),
    (("H1", "1h"), ("H4", "4h"), ("D1", "1d")),
)
def test_future_candles_hidden_before_available_at(timeframe, delta):
    timestamp = pd.Timestamp("2026-07-01T00:00:00Z")
    assert candle_available_at(timestamp, timeframe) == timestamp + pd.Timedelta(delta)
    frame = _frame("2026-07-01", 2, {"H1": "1h", "H4": "4h", "D1": "1d"}[timeframe])
    assert visible_source(frame, timeframe, timestamp).empty


def test_same_time_event_order_is_d1_h4_h1():
    timestamp = pd.Timestamp("2026-07-01T00:00:00Z")
    sources = {
        ("EURUSD", timeframe): pd.DataFrame({"timestamp": [timestamp - pd.Timedelta({"D1": "1d", "H4": "4h", "H1": "1h"}[timeframe])]})
        for timeframe in ("H1", "H4", "D1")
    }
    queue = build_event_queue(sources, timestamp, timestamp + pd.Timedelta(seconds=1))
    assert [event.timeframe for event in queue] == ["D1", "H4", "H1"]
    assert EVENT_PRIORITY == {"D1": 0, "H4": 1, "H1": 2}


def test_initial_rolling_dataset_is_exactly_2000_and_future_is_excluded():
    frame = _frame("2026-03-01", 3000, "1h")
    cut = initial_rolling_cut(frame, "H1", START)
    assert len(cut) == 2000
    assert candle_available_at(cut["timestamp"].iloc[-1], "H1") <= START
    assert (pd.to_datetime(cut["timestamp"], utc=True) < START).all()


def test_initial_cut_fails_closed_with_insufficient_history():
    with pytest.raises(ValueError, match="REPLAY_INITIAL_HISTORY_INSUFFICIENT"):
        initial_rolling_cut(_frame("2026-06-01", 100, "1h"), "H1", START)


def test_training_causality_accepts_only_visible_feature_and_terminal_target():
    evidence = assert_training_causal(
        max_feature_timestamp="2026-06-30T22:00:00Z",
        max_target_timestamp="2026-06-30T23:00:00Z",
        replay_clock=START,
    )
    assert evidence["lookahead_violation"] is False


@pytest.mark.parametrize("field", ("max_feature_timestamp", "max_target_timestamp"))
def test_training_causality_rejects_initial_or_retrain_lookahead(field):
    arguments = {
        "max_feature_timestamp": "2026-06-30T23:00:00Z",
        "max_target_timestamp": "2026-06-30T23:00:00Z",
        "replay_clock": START,
    }
    arguments[field] = "2026-07-01T00:00:01Z"
    with pytest.raises(ReplayLookaheadError, match="TRAINING_LOOKAHEAD"):
        assert_training_causal(**arguments)


def test_event_queue_contains_metadata_only_not_ohlc():
    sources = {("EURUSD", "H1"): _frame("2026-06-30T23:00:00Z", 2, "1h")}
    event = build_event_queue(sources, START, END)[0]
    assert set(vars(event)) == {"available_at", "symbol", "timeframe", "row_position"}


def test_one_prediction_per_symbol_candle_generation_and_duplicate_prevention():
    book = ReplayPredictionBook()
    prediction = {
        "symbol": "EURUSD", "candle_timestamp": START.isoformat(),
        "model_generation": 1, "action": "HOLD", "execution_mode": "shadow_replay",
    }
    assert book.record(prediction) is True
    with pytest.raises(ReplayDuplicateError):
        book.record(prediction)
    assert book.duplicate_attempts == 1
    assert len(book.predictions) == 1


def test_replay_prediction_id_is_deterministic_and_generation_bound():
    first = replay_prediction_id("EURUSD", START, 1)
    assert first == replay_prediction_id("EURUSD", START, 1)
    assert first != replay_prediction_id("EURUSD", START, 2)


def test_hold_is_persisted_but_never_creates_directional_outcome():
    book = ReplayPredictionBook()
    book.record({
        "symbol": "EURUSD", "candle_timestamp": START.isoformat(),
        "model_generation": 1, "action": "HOLD", "execution_mode": "shadow_replay",
        "entry_price": 100.0,
    })
    finalized = book.mature("EURUSD", _frame(START.isoformat(), 13, "1h"), START + pd.Timedelta(hours=13))
    assert finalized == []
    assert len(book.predictions) == 1


@pytest.mark.parametrize(
    ("action", "terminal_close", "correct"),
    (("BUY", 112.0, True), ("SELL", 112.0, False), ("SELL", 100.0, True)),
)
def test_directional_outcome_matures_at_exactly_t_plus_12(action, terminal_close, correct):
    candles = _frame(START.isoformat(), 13, "1h")
    candles.loc[12, "close"] = terminal_close
    book = ReplayPredictionBook()
    book.record({
        "symbol": "EURUSD", "candle_timestamp": START.isoformat(),
        "model_generation": 1, "model_identity": "model-1", "action": action,
        "execution_mode": "shadow_replay", "entry_price": 100.0,
    })
    assert book.mature("EURUSD", candles.iloc[:12], START + pd.Timedelta(hours=12)) == []
    outcomes = book.mature("EURUSD", candles, START + pd.Timedelta(hours=13))
    assert len(outcomes) == 1
    assert outcomes[0]["evaluation_candle"] == pd.Timestamp(candles.iloc[12]["timestamp"]).isoformat()
    assert outcomes[0]["direction_correct"] is correct


def test_post_window_maturity_does_not_create_predictions():
    book = ReplayPredictionBook()
    book.record({
        "symbol": "EURUSD", "candle_timestamp": (END - pd.Timedelta(hours=1)).isoformat(),
        "model_generation": 1, "model_identity": "model-1", "action": "BUY",
        "execution_mode": "shadow_replay", "entry_price": 100.0,
    })
    count = len(book.predictions)
    book.mature("EURUSD", _frame((END - pd.Timedelta(hours=1)).isoformat(), 13, "1h"), END + pd.Timedelta(hours=12))
    assert len(book.predictions) == count


def test_retrain_is_due_at_exactly_168_new_h1_and_not_performance_driven():
    cutoff = pd.Timestamp("2026-07-01T00:00:00Z")
    timestamps = pd.date_range(cutoff + pd.Timedelta(hours=1), periods=168, freq="1h")
    assert retrain_due(cutoff, timestamps[:167], cadence=168) is False
    assert retrain_due(cutoff, timestamps, cadence=168) is True
    assert "accuracy" not in retrain_due.__code__.co_varnames


def test_generations_and_old_prediction_identity_are_preserved():
    book = ReplayPredictionBook()
    for generation in (1, 2):
        book.record({
            "symbol": "EURUSD",
            "candle_timestamp": (START + pd.Timedelta(hours=generation)).isoformat(),
            "model_generation": generation,
            "model_identity": f"model-{generation}",
            "action": "HOLD",
            "execution_mode": "shadow_replay",
        })
    assert [row["model_generation"] for row in book.predictions] == [1, 2]
    assert [row["model_identity"] for row in book.predictions] == ["model-1", "model-2"]


def test_symbol_isolation_rejects_cross_fx_data():
    assert_symbol_isolation(_frame("2026-01-01", 2, "1h", "EURUSD"), "EURUSD")
    with pytest.raises(ValueError, match="REPLAY_CROSS_SYMBOL_DATA"):
        assert_symbol_isolation(_frame("2026-01-01", 2, "1h", "USDJPY"), "EURUSD")


def test_replay_configuration_is_temporary_and_has_no_production_override(tmp_path):
    config = HistoricalReplayConfig(start=START, end=END, symbols=("EURUSD", "USDJPY"), root=tmp_path)
    assert config.database_path.is_relative_to(tmp_path)
    assert config.model_root.is_relative_to(tmp_path)
    assert config.dataset_root.is_relative_to(tmp_path)
    assert "production" not in HistoricalReplayConfig.__dataclass_fields__


def test_source_hash_is_deterministic_and_content_bound():
    frame = _frame("2026-01-01", 10, "1h")
    digest = source_sha256(frame)
    assert digest == source_sha256(frame.copy())
    changed = frame.copy()
    changed.loc[0, "close"] += 1.0
    assert digest != source_sha256(changed)


def test_real_artifact_snapshots_detect_mutation_without_writing(tmp_path):
    paths = [tmp_path / "db.sqlite", tmp_path / "EURUSD.csv", tmp_path / "EURUSD.pkl"]
    for index, path in enumerate(paths):
        path.write_bytes(f"artifact-{index}".encode())
    before = snapshot_paths(paths)
    assert verify_snapshots(before) == []
    paths[1].write_bytes(b"changed")
    assert verify_snapshots(before) == [str(paths[1].resolve())]


def test_descriptive_metrics_count_hold_coverage_accuracy_and_returns():
    predictions = [
        {"action": "BUY", "model_generation": 1},
        {"action": "SELL", "model_generation": 1},
        {"action": "HOLD", "model_generation": 2},
    ]
    outcomes = [
        {"action": "BUY", "direction_correct": True, "future_return": 0.02, "model_generation": 1},
        {"action": "SELL", "direction_correct": False, "future_return": 0.01, "model_generation": 1},
    ]
    metrics = descriptive_metrics(predictions, outcomes)
    assert metrics["buy_count"] == metrics["sell_count"] == metrics["hold_count"] == 1
    assert metrics["coverage"] == pytest.approx(2 / 3)
    assert metrics["pooled_directional_accuracy"] == 0.5
    assert metrics["average_future_return_after_buy"] == 0.02
    assert metrics["average_future_return_after_sell"] == 0.01
    assert metrics["predictive_sanity_label"] == "AT_OR_BELOW_50_REFERENCE"


def test_replay_contract_has_no_promotion_activation_or_trading_dependency():
    module = Path("forex/replay/historical_replay.py").read_text(encoding="utf-8")
    forbidden = ("promote", "activate_qualified_symbol", "place_order", "send_order")
    assert all(token not in module for token in forbidden)


def test_hash_helper_is_sha256_not_process_hash():
    frame = _frame("2026-01-01", 2, "1h")
    assert len(source_sha256(frame)) == hashlib.sha256().digest_size * 2

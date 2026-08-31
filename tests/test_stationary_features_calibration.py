"""Contracts for experimental stationary features and calibration strategies."""

import hashlib
import json
import math

import numpy as np
import pandas as pd
import pytest

from forex.prediction import dataset_builder as dataset_module
from forex.prediction.dataset_builder import DatasetBuilder
from forex.prediction import xgb_trainer


def _frame(rows: int = 120) -> pd.DataFrame:
    position = np.arange(rows, dtype=float)
    close = 1.08 + position * 0.0002 + np.sin(position / 5.0) * 0.0005
    open_ = close * (1.0 + np.sin(position / 3.0) * 0.0001)
    high = np.maximum(open_, close) * 1.0004
    low = np.minimum(open_, close) * 0.9996
    ema20 = pd.Series(close).ewm(span=20, adjust=False).mean().to_numpy()
    ema50 = pd.Series(close).ewm(span=50, adjust=False).mean().to_numpy()
    ema200 = pd.Series(close).ewm(span=200, adjust=False).mean().to_numpy()
    rolling_mean = {
        window: pd.Series(close).rolling(window, min_periods=1).mean().to_numpy()
        for window in (5, 10, 20)
    }
    rolling_std = {
        window: pd.Series(close).rolling(window, min_periods=2).std().fillna(0.0001).to_numpy()
        for window in (5, 10, 20)
    }
    returns = pd.Series(close).pct_change().fillna(0.0).to_numpy()
    volume = 1000.0 + (position % 17) * 10.0
    tick_flow = np.cumsum(np.sign(np.diff(close, prepend=close[0])) * volume)
    tick_flow_ema = pd.Series(tick_flow).ewm(span=20, adjust=False).mean().to_numpy()
    data = {
        "timestamp": pd.date_range("2026-01-01", periods=rows, freq="h"),
        "open": open_, "high": high, "low": low, "close": close,
        "returns": returns, "session": ["Tokyo", "London", "NewYork"] * (rows // 3) + ["Tokyo"] * (rows % 3),
        "pair": ["EURUSD"] * rows, "volume": volume,
        "spread": np.full(rows, 0.0001), "RSI_14": 50.0 + np.sin(position / 7.0) * 20.0,
        "MACD": ema20 - ema50, "MACD_signal": (ema20 - ema50) * 0.8,
        "MACD_hist": (ema20 - ema50) * 0.2, "ATR_14": (high - low) * 1.2,
        "EMA20": ema20, "EMA50": ema50, "EMA200": ema200,
        "volatility_24h": pd.Series(returns).rolling(5, min_periods=1).std().fillna(0.0),
        "BB_upper": rolling_mean[20] + 2 * rolling_std[20],
        "BB_lower": rolling_mean[20] - 2 * rolling_std[20],
        "trend_strength": ema20 - ema200,
        "momentum_5": close - np.roll(close, 5),
        "momentum_10": close - np.roll(close, 10),
        "bb_width": 4 * rolling_std[20], "bb_pct_b": np.linspace(0.1, 0.9, rows),
        "bb_squeeze": 0.8 + np.sin(position / 9.0) * 0.1,
        "body_strength": np.abs(close - open_) / (high - low),
        "upper_shadow": (high - np.maximum(open_, close)) / (high - low),
        "lower_shadow": (np.minimum(open_, close) - low) / (high - low),
        "tick_vol_flow": tick_flow, "tick_vol_flow_ema": tick_flow_ema,
        "tick_vol_flow_diverge": tick_flow - tick_flow_ema,
        "obv": tick_flow, "obv_ema": tick_flow_ema,
        "obv_diverge": tick_flow - tick_flow_ema,
        "volume_relative": volume / pd.Series(volume).rolling(20, min_periods=1).mean(),
        "h4_rsi": 50.0 + np.cos(position / 10.0) * 10.0,
        "h4_atr": (high - low) * 4.0, "h4_ema20": ema20 * 0.999,
        "h4_ema50": ema50 * 0.998, "h4_ema200": ema200 * 0.997,
        "h4_macd": (ema20 - ema50) * 4.0, "h4_return5": returns * 4.0,
        "h4_close": close * 0.9995, "h4_trend": (ema20 > ema200).astype(int),
        "d1_rsi": 48.0 + np.sin(position / 20.0) * 8.0,
        "d1_atr": (high - low) * 12.0, "d1_ema20": ema20 * 0.995,
        "d1_ema50": ema50 * 0.994, "d1_ema200": ema200 * 0.990,
        "d1_macd": (ema20 - ema50) * 12.0, "d1_return5": returns * 12.0,
        "d1_close": close * 0.995, "d1_trend": (ema20 > ema200).astype(int),
    }
    for lag in (1, 2, 3, 5, 10):
        data[f"close_lag_{lag}"] = pd.Series(close).shift(lag).fillna(close[0])
        data[f"returns_lag_{lag}"] = pd.Series(returns).shift(lag).fillna(0.0)
    for window in (5, 10, 20):
        data[f"rolling_mean_{window}"] = rolling_mean[window]
        data[f"rolling_std_{window}"] = rolling_std[window]
    return pd.DataFrame(data)


def _build_x(frame: pd.DataFrame, profile: str) -> pd.DataFrame:
    builder = DatasetBuilder(frame)
    builder.process_time().encode_session().encode_pair()
    return builder.build_X(feature_profile=profile)


def _build_training(frame: pd.DataFrame, profile: str):
    builder = DatasetBuilder(frame)

    def resolved_targets(*, horizon, rr_ratio):
        del horizon, rr_ratio
        builder.df["target"] = np.arange(len(builder.df)) % 2
        return builder

    builder.create_target = resolved_targets
    return builder.build(horizon=12, rr_ratio=1.0, feature_profile=profile)


def test_legacy_is_default_and_preserves_exact_feature_order():
    frame = _frame()
    implicit = _build_x(frame, "legacy")
    builder = DatasetBuilder(frame)
    builder.process_time().encode_session().encode_pair()
    default = builder.build_X()

    assert list(default.columns) == list(implicit.columns)
    assert list(default.columns[:18]) == [
        "open", "high", "low", "close", "returns", "hour", "day_of_week",
        "session", "volume", "spread", "RSI_14", "MACD", "MACD_signal",
        "MACD_hist", "ATR_14", "EMA20", "EMA50", "EMA200",
    ]


def test_unknown_feature_profile_fails_closed():
    with pytest.raises(ValueError, match="FEATURE_PROFILE_UNSUPPORTED"):
        _build_x(_frame(), "future_profile")


def test_stationary_v1_excludes_raw_ohlc_levels():
    columns = set(_build_x(_frame(), "stationary_v1").columns)
    assert columns.isdisjoint({"open", "high", "low", "close"})


def test_stationary_v1_excludes_raw_ema_and_band_levels():
    columns = set(_build_x(_frame(), "stationary_v1").columns)
    assert columns.isdisjoint({"EMA20", "EMA50", "EMA200", "BB_upper", "BB_lower"})


def test_stationary_v1_excludes_raw_close_lags():
    columns = set(_build_x(_frame(), "stationary_v1").columns)
    assert not any(column.startswith("close_lag_") for column in columns)


def test_stationary_v1_excludes_raw_rolling_levels():
    columns = set(_build_x(_frame(), "stationary_v1").columns)
    assert not any(column.startswith("rolling_mean_") for column in columns)
    assert not any(column.startswith("rolling_std_") for column in columns)


def test_stationary_v1_excludes_mtf_absolute_levels():
    columns = set(_build_x(_frame(), "stationary_v1").columns)
    assert columns.isdisjoint({
        "h4_close", "h4_ema20", "h4_ema50", "h4_ema200", "h4_atr", "h4_macd",
        "d1_close", "d1_ema20", "d1_ema50", "d1_ema200", "d1_atr", "d1_macd",
    })


def test_stationary_v1_excludes_cumulative_levels():
    columns = set(_build_x(_frame(), "stationary_v1").columns)
    assert columns.isdisjoint({"tick_vol_flow", "tick_vol_flow_ema", "obv", "obv_ema"})
    assert "tick_vol_flow_diverge" in columns


def test_stationary_v1_includes_normalized_replacements():
    columns = set(_build_x(_frame(), "stationary_v1").columns)
    assert {
        "open_vs_close", "high_vs_close", "low_vs_close", "range_pct", "body_pct",
        "close_vs_ema20", "close_vs_ema50", "close_vs_ema200", "ema20_vs_50",
        "ema50_vs_200", "trend_strength_pct", "close_vs_lag_1", "close_vs_lag_10",
        "close_vs_rollmean_5", "close_vs_rollmean_20", "rolling_std_pct_5",
        "rolling_std_pct_20", "momentum_pct_5", "momentum_pct_10", "bb_width_pct",
        "atr_pct", "macd_pct", "macd_signal_pct", "macd_hist_pct",
        "h4_close_vs_ema20", "h4_close_vs_ema50", "h4_close_vs_ema200",
        "h4_ema20_vs_50", "h4_ema50_vs_200", "h4_atr_pct", "h4_macd_pct",
        "d1_close_vs_ema20", "d1_close_vs_ema50", "d1_close_vs_ema200",
        "d1_ema20_vs_50", "d1_ema50_vs_200", "d1_atr_pct", "d1_macd_pct",
    } <= columns


def test_stationary_v1_transformations_are_row_local_or_trailing_only():
    frame = _frame()
    baseline = _build_x(frame, "stationary_v1")
    changed = frame.copy()
    last = changed.index[-1]
    for column in (
        "open", "high", "low", "close", "EMA20", "EMA50", "EMA200",
        "BB_upper", "BB_lower", "ATR_14", "MACD", "MACD_signal", "MACD_hist",
        "h4_close", "h4_ema20", "h4_ema50", "h4_ema200", "h4_atr", "h4_macd",
        "d1_close", "d1_ema20", "d1_ema50", "d1_ema200", "d1_atr", "d1_macd",
    ):
        changed.loc[last, column] *= 1.2
    mutated = _build_x(changed, "stationary_v1")

    pd.testing.assert_frame_equal(baseline.iloc[:-1], mutated.iloc[:-1])


def test_predict_features_supports_stationary_profile():
    predicted = DatasetBuilder(_frame()).predict_features(
        n_rows=3, feature_profile="stationary_v1"
    )
    assert len(predicted) == 3
    assert "open_vs_close" in predicted.columns
    assert "close" not in predicted.columns


def test_stationary_train_predict_columns_align_exactly():
    frame = _frame()
    X, _y = _build_training(frame, "stationary_v1")
    predicted = DatasetBuilder(frame).predict_features(
        n_rows=2,
        train_columns=list(X.columns),
        feature_profile="stationary_v1",
    )
    assert list(predicted.columns) == list(X.columns)


def test_stationary_pipeline_has_no_nan_or_infinity():
    X, _y = _build_training(_frame(), "stationary_v1")
    assert not X.empty
    assert np.isfinite(X.to_numpy(dtype=float)).all()


def test_feature_profile_identity_is_deterministic_and_ordered():
    names = list(_build_x(_frame(), "stationary_v1").columns)
    expected = hashlib.sha256(
        json.dumps(names, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert dataset_module.feature_names_sha256(names) == expected
    assert dataset_module.feature_names_sha256(list(names)) == expected
    assert dataset_module.feature_names_sha256(list(reversed(names))) != expected


class _ProbabilityBase:
    @staticmethod
    def predict_proba(X):
        probability = np.asarray(X["probability"], dtype=float)
        return np.column_stack([1.0 - probability, probability])


class _IdentityCalibration:
    def fit(self, _probabilities, _targets):
        return self

    @staticmethod
    def predict(probabilities):
        return np.asarray(probabilities, dtype=float)


def test_calibration_strategy_default_remains_isotonic():
    trainer = xgb_trainer.ForexEnsembleTrainer(
        pair="EURUSD", tuned_params_override={}
    )
    assert trainer.calibration_method == "isotonic"
    with pytest.raises(ValueError, match="CALIBRATION_METHOD_UNSUPPORTED"):
        xgb_trainer.ForexEnsembleTrainer(calibration_method="future")


def test_sigmoid_calibrator_exposes_existing_prediction_interface():
    X_cal = pd.DataFrame({"probability": np.linspace(0.05, 0.95, 80)})
    y_cal = pd.Series(([0] * 40) + ([1] * 40))
    calibrated = xgb_trainer.CalibratedEnsemble(
        _ProbabilityBase(), method="sigmoid"
    ).fit(X_cal, y_cal)

    probabilities = calibrated.predict_proba(X_cal)
    predictions = calibrated.predict(X_cal)
    assert calibrated.method == "sigmoid"
    assert probabilities.shape == (80, 2)
    assert np.allclose(probabilities.sum(axis=1), 1.0)
    assert set(np.unique(predictions)) <= {0, 1}
    assert 0.0 <= calibrated.threshold <= 0.9
    assert isinstance(calibrated.sufficient, bool)


def test_calibration_evidence_rejects_two_signals_without_changing_sufficient():
    X_cal = pd.DataFrame({"probability": [1.0] * 2 + [0.1] * 70})
    y_cal = pd.Series([1] * 2 + [1] * 18 + [0] * 52)
    calibrated = xgb_trainer.CalibratedEnsemble(_ProbabilityBase())
    calibrated.cal_1 = _IdentityCalibration()
    calibrated.fit(X_cal, y_cal)

    assert calibrated.sufficient is True
    assert calibrated.calibration_size == 72
    assert calibrated.minimum_calibration_signals == 8
    assert calibrated.signals_at_threshold == 2
    assert calibrated.calibration_evidence_sufficient is False


def test_calibration_evidence_accepts_existing_floor_when_met():
    X_cal = pd.DataFrame({"probability": [1.0] * 10 + [0.1] * 62})
    y_cal = pd.Series([1] * 10 + [1] * 10 + [0] * 52)
    calibrated = xgb_trainer.CalibratedEnsemble(_ProbabilityBase())
    calibrated.cal_1 = _IdentityCalibration()
    calibrated.fit(X_cal, y_cal)

    assert calibrated.sufficient is True
    assert calibrated.signals_at_threshold == 10
    assert calibrated.calibration_evidence_sufficient is True


def test_calibration_evidence_floor_constants_are_explicit():
    assert xgb_trainer.MIN_CALIBRATION_ROWS == 60
    assert xgb_trainer.MIN_CALIBRATION_SIGNAL_RATE == pytest.approx(0.10)
    assert math.ceil(72 * xgb_trainer.MIN_CALIBRATION_SIGNAL_RATE) == 8

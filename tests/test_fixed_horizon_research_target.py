"""Contracts for the non-production fixed-horizon Forex hypothesis."""

import numpy as np
import pandas as pd

from forex.prediction import dataset_builder as dataset_module
from forex.prediction.dataset_builder import DatasetBuilder
from forex.prediction.research_hypotheses import (
    FixedHorizonRandomForestClassifier,
    current_outer_research_gate,
    fixed_h1_random_forest_config,
    mean_reversion_score,
)


def _frame(rows: int = 48) -> pd.DataFrame:
    position = np.arange(rows, dtype=float)
    close = 100.0 + np.sin(position / 3.0) + position * 0.02
    open_ = close - np.cos(position / 4.0) * 0.05
    high = np.maximum(open_, close) + 0.25
    low = np.minimum(open_, close) - 0.25
    close_series = pd.Series(close)
    return pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=rows, freq="h"),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "returns": close_series.pct_change().fillna(0.0),
        "session": (
            ["Tokyo", "London", "NewYork"] * (rows // 3)
            + ["Tokyo"] * (rows % 3)
        ),
        "pair": ["EURUSD"] * rows,
        "volume": 1000.0 + position,
        "spread": 0.01 + position * 0.00001,
        "ATR_14": np.full(rows, 0.2),
        "EMA20": close_series.ewm(span=20, adjust=False).mean(),
        "EMA50": close_series.ewm(span=50, adjust=False).mean(),
        "EMA200": close_series.ewm(span=200, adjust=False).mean(),
    })


def test_default_target_profile_reproduces_explicit_first_touch_behavior():
    implicit_X, implicit_y = DatasetBuilder(_frame()).build(
        horizon=3,
        rr_ratio=1.0,
    )
    explicit_X, explicit_y = DatasetBuilder(_frame()).build(
        horizon=3,
        rr_ratio=1.0,
        target_profile="first_touch_v1",
    )

    pd.testing.assert_frame_equal(explicit_X, implicit_X)
    pd.testing.assert_series_equal(explicit_y, implicit_y)


def test_fixed_horizon_target_labels_positive_negative_and_zero_returns():
    frame = _frame(rows=6)
    frame["close"] = [100.0, 101.0, 100.0, 100.0, 99.0, 99.0]
    builder = DatasetBuilder(frame).create_target(
        horizon=1,
        target_profile="fixed_horizon_direction_v1",
    )

    assert builder.df["target"].tolist() == [1, 0, 0, 0, 0, -1]


def test_fixed_horizon_target_marks_last_horizon_rows_unavailable():
    builder = DatasetBuilder(_frame(rows=8)).create_target(
        horizon=3,
        target_profile="fixed_horizon_direction_v1",
    )

    assert builder.df["target"].iloc[-3:].tolist() == [-1, -1, -1]
    assert set(builder.df["target"].iloc[:-3].unique()).issubset({0, 1})


def test_fixed_horizon_build_keeps_every_structurally_available_label():
    baseline = DatasetBuilder(_frame())
    baseline.process_time().encode_session().encode_pair()
    structurally_available = baseline.build_X("stationary_v1")
    structurally_available = structurally_available.replace(
        [np.inf, -np.inf], np.nan
    ).dropna().iloc[:-4]
    X, y = DatasetBuilder(_frame()).build(
        horizon=4,
        feature_profile="stationary_v1",
        target_profile="fixed_horizon_direction_v1",
    )

    assert X.index.tolist() == structurally_available.index.tolist()
    assert len(y) == len(X)
    assert set(y.unique()).issubset({0, 1})


def test_fixed_horizon_target_does_not_inspect_beyond_exact_horizon():
    baseline = _frame(rows=8)
    baseline.loc[:, "close"] = [100.0, 100.0, 101.0, 100.0, 99.0, 99.0, 99.0, 99.0]
    changed = baseline.copy()
    changed.loc[3, "close"] = 1000000.0

    first = DatasetBuilder(baseline).create_target(
        horizon=2,
        target_profile="fixed_horizon_direction_v1",
    )
    second = DatasetBuilder(changed).create_target(
        horizon=2,
        target_profile="fixed_horizon_direction_v1",
    )

    assert first.df.loc[0, "target"] == 1
    assert second.df.loc[0, "target"] == first.df.loc[0, "target"]


def test_stationary_feature_at_t_is_unchanged_by_future_values():
    baseline = _frame()
    changed = baseline.copy()
    changed.loc[30:, ["open", "high", "low", "close"]] *= 10.0

    first = DatasetBuilder(baseline)
    first.process_time().encode_session().encode_pair()
    second = DatasetBuilder(changed)
    second.process_time().encode_session().encode_pair()

    pd.testing.assert_series_equal(
        first.build_X("stationary_v1").loc[20],
        second.build_X("stationary_v1").loc[20],
    )


def test_target_profile_metadata_identity_is_deterministic():
    expected = {
        "target_profile": "fixed_horizon_direction_v1",
        "horizon": 12,
        "target_definition_version": 1,
    }

    assert dataset_module.target_profile_metadata(
        "fixed_horizon_direction_v1", horizon=12
    ) == expected


def test_unknown_target_profile_fails_closed():
    with np.testing.assert_raises_regex(
        ValueError, "TARGET_PROFILE_UNSUPPORTED"
    ):
        DatasetBuilder(_frame()).build(target_profile="future_target")
    assert dataset_module.target_profile_metadata(
        "fixed_horizon_direction_v1", horizon=12
    ) == expected


def test_predict_features_is_independent_of_training_target_profile():
    frame = _frame()
    expected = DatasetBuilder(frame).predict_features(
        n_rows=3,
        feature_profile="stationary_v1",
    )
    builder = DatasetBuilder(frame)
    builder.create_target(
        horizon=12,
        target_profile="fixed_horizon_direction_v1",
    )

    actual = builder.predict_features(
        n_rows=3,
        feature_profile="stationary_v1",
    )
    pd.testing.assert_frame_equal(actual, expected)


def test_stationary_feature_contract_is_unchanged_for_fixed_horizon_target():
    frame = _frame()
    baseline = DatasetBuilder(frame)
    baseline.process_time().encode_session().encode_pair()
    expected = baseline.build_X("stationary_v1")
    expected = expected.replace([np.inf, -np.inf], np.nan).dropna().iloc[:-12]
    expected = DatasetBuilder.filter_low_variance(expected, threshold=0.0)

    actual, _ = DatasetBuilder(frame).build(
        horizon=12,
        feature_profile="stationary_v1",
        target_profile="fixed_horizon_direction_v1",
    )

    assert list(actual.columns) == list(expected.columns)
    assert dataset_module.feature_names_sha256(actual.columns) == (
        dataset_module.feature_names_sha256(expected.columns)
    )


def test_fixed_random_forest_wrapper_exposes_frozen_benchmark_contract():
    config = fixed_h1_random_forest_config()

    assert config == {
        "n_estimators": 300,
        "max_depth": 8,
        "min_samples_leaf": 15,
        "class_weight_strategy": "TRAIN_NEGATIVE_TO_POSITIVE_RATIO",
        "random_state": 42,
        "n_jobs": -1,
    }

    X = pd.DataFrame({"feature": np.arange(40, dtype=float)})
    y = pd.Series(([0] * 24) + ([1] * 16))
    model = FixedHorizonRandomForestClassifier().fit(X, y)

    assert model.resolved_config_["class_weight"] == {0: 1.0, 1: 1.5}
    assert model.predict_proba(X).shape == (40, 2)
    assert set(model.predict(X)).issubset({0, 1})


def test_mean_reversion_score_matches_frozen_binary_sign_convention():
    close = pd.Series([100.0, 101.0, 100.0, 102.0, 100.0])

    score = mean_reversion_score(close, horizon=2)

    assert score.iloc[:2].isna().all()
    assert score.iloc[2:].tolist() == [1.0, 0.0, 1.0]


def test_current_outer_gate_is_strictly_preregistered_and_conjunctive():
    comparator = [
        {"auc": 0.51, "ap_lift": 0.01},
        {"auc": 0.52, "ap_lift": 0.02},
    ]
    passing = [
        {"auc": 0.56, "ap_lift": 0.03},
        {"auc": 0.55, "ap_lift": 0.04},
    ]

    assert current_outer_research_gate(passing, comparator) is True

    for failing in (
        passing[:1],
        [{"auc": 0.50, "ap_lift": 0.03}, passing[1]],
        [{"auc": 0.54, "ap_lift": 0.03}, {"auc": 0.55, "ap_lift": 0.04}],
        [{"auc": 0.56, "ap_lift": 0.0}, passing[1]],
        [{"auc": 0.52, "ap_lift": 0.03}, {"auc": 0.56, "ap_lift": 0.04}],
    ):
        assert current_outer_research_gate(failing, comparator) is False

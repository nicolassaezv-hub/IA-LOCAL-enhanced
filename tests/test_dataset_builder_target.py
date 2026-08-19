import pandas as pd

from forex.prediction.dataset_builder import DatasetBuilder


def _target_for(future_bars, *, horizon=None):
    rows = [
        {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "ATR_14": 1.0}
    ]
    rows.extend(
        {
            "open": 100.0,
            "high": high,
            "low": low,
            "close": 100.0,
            "ATR_14": 1.0,
        }
        for high, low in future_bars
    )
    builder = DatasetBuilder(pd.DataFrame(rows))
    builder.create_target(
        horizon=len(future_bars) if horizon is None else horizon,
        rr_ratio=1.0,
    )
    return int(builder.df.loc[0, "target"])


def test_create_target_labels_buy_when_only_tp_is_touched():
    assert _target_for([(101.0, 99.5)]) == 1


def test_create_target_labels_sell_when_only_sl_is_touched():
    assert _target_for([(100.5, 99.0)]) == 0


def test_create_target_leaves_same_bar_tp_sl_ambiguous():
    assert _target_for([(101.0, 99.0)]) == -1


def test_create_target_keeps_first_tp_before_later_sl():
    assert _target_for([(101.0, 99.5), (100.5, 99.0)]) == 1


def test_create_target_keeps_first_sl_before_later_tp():
    assert _target_for([(100.5, 99.0), (101.0, 99.5)]) == 0


def test_create_target_leaves_timeout_unresolved():
    assert _target_for([(100.5, 99.5), (100.75, 99.25)]) == -1


def test_build_excludes_ambiguous_target_without_third_class():
    frame = pd.DataFrame(
        [
            {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "ATR_14": 1.0},
            {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "ATR_14": 1.0},
            {"open": 100.0, "high": 101.0, "low": 99.5, "close": 100.0, "ATR_14": 1.0},
        ]
    )

    X, y = DatasetBuilder(frame).build(horizon=1, rr_ratio=1.0)

    assert X.index.tolist() == [1]
    assert y.tolist() == [1]
    assert set(y.unique()).issubset({0, 1})


def test_create_target_does_not_change_predict_features():
    frame = pd.DataFrame(
        [
            {"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "ATR_14": 1.0},
            {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.2, "ATR_14": 1.0},
            {"open": 100.2, "high": 100.8, "low": 99.8, "close": 100.4, "ATR_14": 1.0},
        ]
    )
    before = DatasetBuilder(frame).predict_features(n_rows=2)

    builder = DatasetBuilder(frame)
    builder.create_target(horizon=1, rr_ratio=1.0)
    after = builder.predict_features(n_rows=2)

    pd.testing.assert_frame_equal(after, before)

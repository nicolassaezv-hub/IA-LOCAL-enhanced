"""Regresiones del hallazgo A-02: alineación MTF sin lookahead."""

import importlib

import pandas as pd
import pytest

from forex.data.yahoo_provider import _closed_before, _resample_h4
from forex.prediction.csv_adapter import adapt_csv, merge_mtf_context


def _write_csv(tmp_path, name, rows):
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def _h1_rows(timestamps):
    return pd.DataFrame({
        "timestamp": pd.to_datetime(timestamps),
        "open": 1.0,
        "high": 1.1,
        "low": 0.9,
        "close": 1.0,
    })


def test_h4_open_at_midnight_is_available_only_after_its_close(tmp_path):
    h1 = _h1_rows(["2026-01-01 01:00", "2026-01-01 03:00", "2026-01-01 04:00"])
    h4_path = _write_csv(tmp_path, "EURUSD_H4.csv", {
        "timestamp": ["2025-12-31 20:00", "2026-01-01 00:00"],
        "close": [400.0, 444.0],
        "RSI_14": [40.0, 44.0],
    })

    result = merge_mtf_context(h1, path_h4=h4_path)

    assert result["h4_close"].tolist() == [400.0, 400.0, 444.0]


def test_d1_is_available_only_after_the_day_has_closed(tmp_path):
    h1 = _h1_rows(["2026-01-01 01:00", "2026-01-01 23:00", "2026-01-02 00:00"])
    d1_path = _write_csv(tmp_path, "EURUSD_D1.csv", {
        "timestamp": ["2025-12-31 00:00", "2026-01-01 00:00"],
        "close": [100.0, 111.0],
        "RSI_14": [10.0, 11.0],
    })

    result = merge_mtf_context(h1, path_d1=d1_path)

    assert result["d1_close"].tolist() == [100.0, 100.0, 111.0]


def test_first_h1_is_not_backfilled_from_a_future_h4(tmp_path):
    h1_path = _write_csv(tmp_path, "EURUSD_H1.csv", {
        "timestamp": ["2026-01-01 01:00", "2026-01-01 04:00"],
        "open": [1.0, 1.0],
        "high": [1.1, 1.1],
        "low": [0.9, 0.9],
        "close": [1.0, 1.0],
    })
    h4_path = _write_csv(tmp_path, "EURUSD_H4.csv", {
        "timestamp": ["2026-01-01 00:00"],
        "close": [444.0],
        "RSI_14": [44.0],
    })

    result = adapt_csv(
        h1_path,
        pair="EURUSD",
        filter_gaps=False,
        path_h4=h4_path,
    )

    assert pd.isna(result.loc[0, "h4_close"])
    assert result.loc[1, "h4_close"] == 444.0


def test_yahoo_excludes_incomplete_h4_and_d1_candles():
    timestamps = pd.date_range("2026-01-01 00:00", periods=7, freq="h")
    raw_h1 = pd.DataFrame({
        "timestamp": timestamps,
        "open": range(7),
        "high": range(1, 8),
        "low": range(7),
        "close": range(1, 8),
        "volume": 1.0,
        "pair": "EURUSD",
    })

    h4 = _resample_h4(raw_h1, now=pd.Timestamp("2026-01-01 12:00"))

    assert h4["timestamp"].tolist() == [pd.Timestamp("2026-01-01 00:00")]
    assert h4.loc[0, "close"] == 4

    raw_d1 = pd.DataFrame({
        "timestamp": pd.to_datetime(["2026-01-01 00:00", "2026-01-02 00:00"]),
        "close": [111.0, 222.0],
    })
    d1 = _closed_before(
        raw_d1,
        pd.Timedelta(days=1),
        now=pd.Timestamp("2026-01-02 12:00"),
    )

    assert d1["close"].tolist() == [111.0]


def test_yahoo_rejects_h4_with_a_missing_hour_even_if_it_has_four_rows():
    raw_h1 = pd.DataFrame({
        "timestamp": pd.to_datetime([
            "2026-01-01 00:00",
            "2026-01-01 01:00",
            "2026-01-01 02:00",
            "2026-01-01 02:30",
        ]),
        "open": range(4),
        "high": range(1, 5),
        "low": range(4),
        "close": range(1, 5),
        "volume": 1.0,
        "pair": "EURUSD",
    })

    result = _resample_h4(raw_h1, now=pd.Timestamp("2026-01-01 12:00"))

    assert result.empty


@pytest.mark.parametrize(
    "module_name",
    ["forex.prediction.csv_adapter", "forex.csv_adapter"],
)
def test_all_mtf_adapter_entry_points_use_close_time(tmp_path, module_name):
    module = importlib.import_module(module_name)
    h1 = _h1_rows(["2026-01-01 01:00", "2026-01-01 04:00"])
    h4_path = _write_csv(tmp_path, "entry_H4.csv", {
        "timestamp": ["2026-01-01 00:00"],
        "close": [444.0],
        "RSI_14": [44.0],
    })

    result = module.merge_mtf_context(h1, path_h4=h4_path)

    assert pd.isna(result.loc[0, "h4_close"])
    assert result.loc[1, "h4_close"] == 444.0

"""Regressions for the provider/rolling/qualification artifact contract."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from forex.data.data_router import DataRouter
from forex.data.indicator_delta import (
    INDICATOR_MIN_HISTORY,
    recalculate_tail_indicators,
)
from forex.data.rolling_dataset import (
    ROLLING_WINDOW,
    DatasetValidationError,
    RollingDataset,
)
from forex.data.symbol_catalog import route_for_provider
from forex.data.symbol_lifecycle import qualify_candidate
from forex.data.yahoo_provider import YahooProvider
from infra.db.database import SQLiteDatabase
from scheduler import autonomous_scheduler
from scripts.validate_symbol_universe import (
    _independent_indicators,
    validate_dataset_frame,
)


pytestmark = pytest.mark.unit

CONTRACT_INDICATORS = tuple(INDICATOR_MIN_HISTORY)
NOW = pd.Timestamp("2026-08-21 12:00:00", tz="UTC")


def _market_frame(
    count: int,
    *,
    start: str = "2015-01-01",
    freq: str = "h",
    pair: str = "EURUSD",
) -> pd.DataFrame:
    index = np.arange(count, dtype=float)
    center = 1.1 + index * 2e-5 + np.sin(index / 11.0) * 7e-4
    opened = center + np.sin(index / 5.0) * 8e-5
    closed = center + np.cos(index / 7.0) * 9e-5
    return pd.DataFrame({
        "timestamp": pd.date_range(start, periods=count, freq=freq),
        "open": opened,
        "high": np.maximum(opened, closed) + 4e-4,
        "low": np.minimum(opened, closed) - 4e-4,
        "close": closed,
        "volume": 1000.0 + index,
        "pair": pair,
    })


def _coherent_provider_frame(
    symbol: str,
    timeframe: str,
    count: int = 2001,
) -> pd.DataFrame:
    duration_hours = {"H1": 1, "H4": 4, "D1": 24}[timeframe]
    starts = pd.date_range(
        NOW.tz_localize(None) - pd.Timedelta(hours=duration_hours * count),
        periods=count,
        freq=f"{duration_hours}h",
    )
    epoch_hours = (
        starts.to_numpy(dtype="datetime64[ns]").astype(np.int64)
        / (60 * 60 * 1_000_000_000)
    )
    sampled = np.stack([
        1.1 + (epoch_hours + offset) * 1e-7
        for offset in range(duration_hours + 1)
    ])
    return pd.DataFrame({
        "timestamp": starts,
        "open": sampled[0],
        "high": sampled.max(axis=0) + 2e-6,
        "low": sampled.min(axis=0) - 2e-6,
        "close": sampled[-1],
        "volume": np.full(count, 1000.0 * duration_hours),
        "pair": symbol,
    })


def _as_yahoo_download(frame: pd.DataFrame) -> pd.DataFrame:
    raw = frame.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
    raw.index.name = "Date"
    return raw.rename(columns={column: column.title() for column in raw.columns})


def _ohlc_valid_mask(frame: pd.DataFrame) -> pd.Series:
    prices = frame[["open", "high", "low", "close"]].apply(
        pd.to_numeric, errors="coerce"
    )
    finite = pd.Series(
        np.isfinite(prices.to_numpy(float)).all(axis=1), index=frame.index
    )
    return (
        finite
        & (prices > 0).all(axis=1)
        & (prices["low"] <= prices["high"])
        & prices["open"].between(prices["low"], prices["high"])
        & prices["close"].between(prices["low"], prices["high"])
    )


def _yahoo_frame_with_invalid_rows() -> tuple[pd.DataFrame, list[pd.Timestamp]]:
    frame = _market_frame(2109, freq="D")
    positions = list(range(1900, 1909))
    frame.loc[positions[0], "close"] = frame.loc[positions[0], "high"] + 0.01
    frame.loc[positions[1], "close"] = frame.loc[positions[1], "low"] - 0.01
    frame.loc[positions[2], "open"] = frame.loc[positions[2], "high"] + 0.01
    frame.loc[positions[3], "open"] = frame.loc[positions[3], "low"] - 0.01
    frame.loc[positions[4], "low"] = frame.loc[positions[4], "high"] + 0.01
    frame.loc[positions[5], "open"] = 0.0
    frame.loc[positions[6], "high"] = -1.0
    frame.loc[positions[7], "close"] = np.inf
    frame.loc[positions[8], "low"] = np.nan
    return frame, [pd.Timestamp(frame.loc[position, "timestamp"]) for position in positions]


def _acquisition_metadata(
    *,
    timeframe: str = "D1",
    requested_bars: int = 2001,
    raw_closed_rows: int = 2001,
    valid_rows_before_tail: int = 2001,
    returned_rows: int = 2001,
    dropped: list[tuple[pd.Timestamp, str]] | None = None,
) -> dict:
    dropped_rows = [
        {"timestamp": pd.Timestamp(timestamp).isoformat(), "reason": reason}
        for timestamp, reason in (dropped or [])
    ]
    return {
        "schema_version": 1,
        "provider": "Yahoo",
        "symbol": "EURUSD",
        "timeframe": timeframe,
        "requested_bars": requested_bars,
        "raw_closed_rows": raw_closed_rows,
        "invalid_rows_dropped": len(dropped_rows),
        "valid_rows_before_tail": valid_rows_before_tail,
        "returned_rows": returned_rows,
        "dropped_rows": dropped_rows,
    }


def _assert_indicators_match_independent(frame: pd.DataFrame) -> None:
    expected = _independent_indicators(frame)
    for column in CONTRACT_INDICATORS:
        actual_values = pd.to_numeric(frame[column], errors="coerce").to_numpy(float)
        expected_values = expected[column].to_numpy(float)
        assert np.array_equal(np.isnan(actual_values), np.isnan(expected_values)), column
        assert np.allclose(
            actual_values,
            expected_values,
            rtol=1e-6,
            atol=1e-9,
            equal_nan=True,
        ), column


def test_rolling_2001_to_2000_artifact_matches_independent_indicators(tmp_path):
    path = tmp_path / "EURUSD_H1.csv"
    stored = RollingDataset("EURUSD", "H1", csv_path=path).apply(
        _market_frame(2001), include_existing=False, now="2030-01-01"
    )

    artifact = pd.read_csv(stored["path"])

    assert len(artifact) == ROLLING_WINDOW
    _assert_indicators_match_independent(artifact)


def test_rolling_artifact_has_no_hidden_ewm_context(tmp_path):
    common = _market_frame(2000, start="2015-01-02")
    prefix_a = common.iloc[[0]].copy()
    prefix_b = prefix_a.copy()
    prefix_a["timestamp"] = pd.Timestamp("2015-01-01 22:00:00")
    prefix_b["timestamp"] = prefix_a["timestamp"]
    prefix_a[["open", "high", "low", "close"]] = [0.8, 0.9, 0.7, 0.85]
    prefix_b[["open", "high", "low", "close"]] = [1.8, 1.9, 1.7, 1.85]

    artifacts = []
    for name, prefix in (("a", prefix_a), ("b", prefix_b)):
        source = pd.concat([prefix, common], ignore_index=True)
        path = tmp_path / f"{name}.csv"
        RollingDataset("EURUSD", "H1", csv_path=path).apply(
            source, include_existing=False, now="2030-01-01"
        )
        artifacts.append(pd.read_csv(path))

    pd.testing.assert_frame_equal(
        artifacts[0][["timestamp", "open", "high", "low", "close"]],
        artifacts[1][["timestamp", "open", "high", "low", "close"]],
    )
    for column in CONTRACT_INDICATORS:
        assert np.allclose(
            artifacts[0][column],
            artifacts[1][column],
            rtol=1e-6,
            atol=1e-9,
            equal_nan=True,
        ), column


@pytest.mark.parametrize(
    "mutation",
    [
        lambda frame: frame.__setitem__("open", frame["open"].mask(frame.index == 10, 0)),
        lambda frame: frame.__setitem__("open", frame["open"].mask(frame.index == 10, -1)),
        lambda frame: frame.__setitem__("high", frame["high"].mask(frame.index == 10, np.inf)),
        lambda frame: frame.__setitem__("low", frame["low"].mask(frame.index == 10, np.nan)),
        lambda frame: frame.__setitem__("low", frame["low"].mask(frame.index == 10, frame["high"] + 1)),
        lambda frame: frame.__setitem__("open", frame["open"].mask(frame.index == 10, frame["low"] - 1)),
        lambda frame: frame.__setitem__("open", frame["open"].mask(frame.index == 10, frame["high"] + 1)),
        lambda frame: frame.__setitem__("close", frame["close"].mask(frame.index == 10, frame["low"] - 1)),
        lambda frame: frame.__setitem__("close", frame["close"].mask(frame.index == 10, frame["high"] + 1)),
    ],
    ids=(
        "zero",
        "negative",
        "infinity",
        "nan",
        "low-above-high",
        "open-below-low",
        "open-above-high",
        "close-below-low",
        "close-above-high",
    ),
)
def test_rolling_contract_rejects_ohlc_rejected_by_qualification(tmp_path, mutation):
    frame = _market_frame(40)
    mutation(frame)

    with pytest.raises(DatasetValidationError):
        RollingDataset("EURUSD", "H1", csv_path=tmp_path / "bad.csv").apply(
            frame, include_existing=False, now="2030-01-01"
        )


def test_yahoo_sanitizes_before_tail_and_preserves_valid_values():
    source, dropped_timestamps = _yahoo_frame_with_invalid_rows()
    provider = YahooProvider()
    provider._available = True

    with patch("yfinance.download", return_value=_as_yahoo_download(source)):
        result = provider.fetch("EURUSD", "D1", bars=2001)

    assert len(result) == 2001
    assert _ohlc_valid_mask(result).all()
    expected = source.loc[_ohlc_valid_mask(source)].tail(2001)
    compared = result.merge(
        expected[["timestamp", "open", "high", "low", "close"]],
        on="timestamp",
        suffixes=("_actual", "_expected"),
        validate="one_to_one",
    )
    assert len(compared) == 2001
    for column in ("open", "high", "low", "close"):
        assert np.array_equal(
            compared[f"{column}_actual"].to_numpy(),
            compared[f"{column}_expected"].to_numpy(),
        )

    metadata = provider.last_acquisition_metadata
    assert metadata["provider"] == "Yahoo"
    assert metadata["symbol"] == "EURUSD"
    assert metadata["timeframe"] == "D1"
    assert metadata["requested_bars"] == 2001
    assert metadata["raw_closed_rows"] == 2109
    assert metadata["invalid_rows_dropped"] == 9
    assert metadata["valid_rows_before_tail"] == 2100
    assert metadata["returned_rows"] == 2001
    assert {pd.Timestamp(item["timestamp"]) for item in metadata["dropped_rows"]} == set(
        dropped_timestamps
    )
    assert {item["reason"] for item in metadata["dropped_rows"]} == {
        "INVALID_OHLC_ENVELOPE",
        "NON_FINITE_OHLC",
        "NON_POSITIVE_OHLC",
    }


def test_yahoo_fails_closed_when_valid_rows_are_insufficient():
    source = _market_frame(2001, freq="D")
    source.loc[source.index[-1], "close"] = source.loc[source.index[-1], "high"] + 1
    provider = YahooProvider()
    provider._available = True

    with patch("yfinance.download", return_value=_as_yahoo_download(source)):
        with pytest.raises(
            RuntimeError, match="INSUFFICIENT_VALID_BARS_AFTER_SANITIZATION"
        ):
            provider.fetch("EURUSD", "D1", bars=2001)


def test_data_router_exposes_selected_provider_acquisition_metadata():
    source, _ = _yahoo_frame_with_invalid_rows()
    yahoo = YahooProvider()
    yahoo._available = True

    class UnavailableProvider:
        def is_available(self):
            return False

    with patch(
        "forex.data.mt5_provider.get_mt5_provider",
        return_value=UnavailableProvider(),
    ), patch(
        "forex.data.yahoo_provider.get_yahoo_provider", return_value=yahoo
    ), patch("yfinance.download", return_value=_as_yahoo_download(source)):
        router = DataRouter("EURUSD", "D1")
        result = router.fetch(2001, raise_on_failure=True)

    assert len(result) == 2001
    assert router.source_used == "Yahoo"
    assert router.last_acquisition_metadata == yahoo.last_acquisition_metadata


def _validated_gap_frame(
    missing_positions: tuple[int, ...],
) -> tuple[pd.DataFrame, list[pd.Timestamp]]:
    source = _market_frame(2000 + len(missing_positions), freq="D")
    missing = [pd.Timestamp(source.loc[position, "timestamp"]) for position in missing_positions]
    frame = source.drop(index=list(missing_positions)).reset_index(drop=True)
    return recalculate_tail_indicators(frame, k=len(frame)), missing


def test_exact_sanitization_provenance_makes_gap_known_not_provider_gap():
    frame, missing = _validated_gap_frame((96,))
    metadata = _acquisition_metadata(
        raw_closed_rows=2001,
        valid_rows_before_tail=2000,
        returned_rows=2000,
        dropped=[(missing[0], "INVALID_OHLC_ENVELOPE")],
    )

    stage, validated = validate_dataset_frame(
        frame,
        "EURUSD",
        "D1",
        now="2030-01-01",
        acquisition_metadata=metadata,
    )

    assert validated is not None
    assert stage["blocking"] is False
    assert stage["details"]["gaps"]["classifications"] == {
        "SANITIZED_PROVIDER_ROW": 1
    }


def test_same_gap_without_sanitization_provenance_is_provider_gap_blocking():
    frame, _ = _validated_gap_frame((96,))

    stage, _ = validate_dataset_frame(
        frame, "EURUSD", "D1", now="2030-01-01"
    )

    assert stage["blocking"] is True
    assert stage["details"]["gaps"]["classifications"]["PROVIDER_GAP"] == 1


def test_partial_sanitization_provenance_remains_provider_gap_blocking():
    frame, missing = _validated_gap_frame((96, 97))
    metadata = _acquisition_metadata(
        raw_closed_rows=2002,
        valid_rows_before_tail=2000,
        returned_rows=2000,
        dropped=[(missing[0], "INVALID_OHLC_ENVELOPE")],
    )

    stage, _ = validate_dataset_frame(
        frame,
        "EURUSD",
        "D1",
        now="2030-01-01",
        acquisition_metadata=metadata,
    )

    assert stage["blocking"] is True
    assert stage["details"]["gaps"]["classifications"]["PROVIDER_GAP"] == 1
    assert "SANITIZED_PROVIDER_ROW" not in stage["details"]["gaps"]["classifications"]


def test_weekend_does_not_hide_unexplained_weekday_timestamp():
    timestamps = pd.Series([
        pd.Timestamp("2026-07-31 22:00:00"),
        pd.Timestamp("2026-08-03 01:00:00"),
    ])

    from scripts.validate_symbol_universe import classify_gaps

    gaps = classify_gaps(timestamps, "H1", "FOREX")

    assert [gap["classification"] for gap in gaps] == ["PROVIDER_GAP"]


def test_untrusted_expected_market_closure_metadata_cannot_unblock_gap():
    frame, missing = _validated_gap_frame((96,))
    metadata = _acquisition_metadata()
    metadata["expected_market_closures"] = [missing[0].isoformat()]

    stage, validated = validate_dataset_frame(
        frame,
        "EURUSD",
        "D1",
        now="2030-01-01",
        acquisition_metadata=metadata,
    )

    assert validated is not None
    assert stage["blocking"] is True
    assert stage["details"]["gaps"]["classifications"] == {
        "PROVIDER_GAP": 1
    }


def test_fake_yahoo_router_rolling_qualification_contract_is_consistent(tmp_path):
    source, _ = _yahoo_frame_with_invalid_rows()
    yahoo = YahooProvider()
    yahoo._available = True

    class UnavailableProvider:
        def is_available(self):
            return False

    with patch(
        "forex.data.mt5_provider.get_mt5_provider",
        return_value=UnavailableProvider(),
    ), patch(
        "forex.data.yahoo_provider.get_yahoo_provider", return_value=yahoo
    ), patch("yfinance.download", return_value=_as_yahoo_download(source)):
        router = DataRouter("EURUSD", "D1")
        acquired = router.fetch(2001, raise_on_failure=True)

    path = tmp_path / "EURUSD_D1.csv"
    RollingDataset("EURUSD", "D1", csv_path=path).apply(
        acquired, include_existing=False, now="2030-01-01"
    )
    artifact = pd.read_csv(path)
    stage, validated = validate_dataset_frame(
        artifact,
        "EURUSD",
        "D1",
        now="2030-01-01",
        acquisition_metadata=router.last_acquisition_metadata,
    )

    assert len(artifact) == ROLLING_WINDOW
    assert _ohlc_valid_mask(artifact).all()
    _assert_indicators_match_independent(artifact)
    assert validated is not None
    assert stage["blocking"] is False
    assert stage["status"] in {"PASS", "WARNING"}


def test_qualification_evidence_retains_acquisition_metadata(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "astra.db"))
    database.register_candidate("NZDUSD", "NZD/USD", "FOREX", 0.0001)

    class Router:
        def __init__(self, symbol: str, timeframe: str):
            self.symbol = symbol
            self.timeframe = timeframe
            self.source_used = "Yahoo"
            self.route_used = route_for_provider(symbol, "Yahoo")
            self.attempt_errors = ("MT5 unavailable",)
            self.last_acquisition_metadata = {
                **_acquisition_metadata(timeframe=timeframe),
                "symbol": symbol,
            }

        def fetch(self, bars: int, raise_on_failure: bool):
            assert raise_on_failure is True
            return _coherent_provider_frame(self.symbol, self.timeframe, bars)

    evidence = qualify_candidate(
        database,
        "NZDUSD",
        project_root=tmp_path,
        router_factory=Router,
        now=NOW,
    )

    assert evidence["result"] == "PASS"
    for timeframe, item in evidence["timeframes"].items():
        assert item["acquisition_metadata"]["provider"] == "Yahoo"
        assert item["acquisition_metadata"]["symbol"] == "NZDUSD"
        assert item["acquisition_metadata"]["timeframe"] == timeframe


def test_scheduler_persists_acquisition_metadata_and_readiness_verifies_it(
    tmp_path,
):
    database = SQLiteDatabase(str(tmp_path / "astra.db"))
    frame = _market_frame(2001)
    metadata = _acquisition_metadata(
        timeframe="H1",
        raw_closed_rows=2002,
        valid_rows_before_tail=2001,
        returned_rows=2001,
        dropped=[(pd.Timestamp("2014-12-31 23:00:00"), "INVALID_OHLC_ENVELOPE")],
    )
    frame.attrs["acquisition_metadata"] = metadata

    with patch.object(autonomous_scheduler, "PROJECT_ROOT", tmp_path), patch.object(
        autonomous_scheduler,
        "fetch_market_data",
        return_value=(frame, "Yahoo"),
    ):
        result = autonomous_scheduler.run_rolling_update(database, "EURUSD", "H1")
        entry = database.get_dataset_registry("EURUSD", "H1")[0]
        readiness = autonomous_scheduler.registry_entry_readiness(
            entry, project_root=tmp_path
        )

    assert result["status"] == "ready"
    assert entry["acquisition_metadata"]["invalid_rows_dropped"] == 1
    assert entry["acquisition_metadata"]["dataset_sha256"] == entry["source_sha256"]
    assert readiness["ready"] is True
    assert readiness["acquisition_metadata_state"] == "VERIFIED"


def test_dataset_registry_migration_adds_metadata_idempotently(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE supported_symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol_code TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                pip_value REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'candidate',
                added_at TEXT NOT NULL
            );
            CREATE TABLE dataset_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                candle_count INTEGER DEFAULT 0,
                rolling_window_size INTEGER DEFAULT 2000,
                last_candle_timestamp TEXT,
                blob_path TEXT,
                status TEXT DEFAULT 'pending',
                last_error TEXT,
                last_updated TEXT,
                UNIQUE(symbol, timeframe)
            );
        """)

    SQLiteDatabase(str(path))
    database = SQLiteDatabase(str(path))
    with sqlite3.connect(path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(dataset_registry)")
        }
    assert "acquisition_metadata" in columns

    metadata = _acquisition_metadata(timeframe="H1")
    entry = database.upsert_dataset_registry({
        "symbol": "EURUSD",
        "timeframe": "H1",
        "acquisition_metadata": metadata,
    })
    assert entry["acquisition_metadata"] == metadata
    assert database.get_dataset_registry("EURUSD", "H1")[0][
        "acquisition_metadata"
    ] == metadata

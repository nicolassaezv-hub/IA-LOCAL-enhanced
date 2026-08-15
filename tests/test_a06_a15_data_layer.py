"""Isolated regressions for audit findings A-06 and A-15."""
from __future__ import annotations

import ast
import os
import stat
import sys
import threading
import types
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest
from filelock import FileLock

from forex.data.data_router import DataProviderError, DataRouter
from forex.data.binance_provider import BinanceProvider
from forex.data.mt5_provider import MT5Provider
from forex.data.indicator_delta import (
    INDICATOR_MIN_HISTORY,
    recalculate_tail_indicators,
)
from forex.data.rolling_dataset import (
    ROLLING_WINDOW,
    DatasetValidationError,
    RollingDataset,
    validate_dataset,
)
from scheduler import autonomous_scheduler


REQUIRED_TECHNICAL_COLUMNS = set(INDICATOR_MIN_HISTORY)


def frame(count: int, *, freq: str = "h", start: str = "2020-01-01") -> pd.DataFrame:
    timestamps = pd.date_range(start, periods=count, freq=freq)
    values = pd.Series(range(count), dtype=float)
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": 1.0 + values / 10000,
        "high": 1.1 + values / 10000,
        "low": 0.9 + values / 10000,
        "close": 1.05 + values / 10000,
        "volume": 1000.0,
        "pair": "EURUSD",
    })


class FakeDatabase:
    def __init__(self, entries=None):
        self.entries = dict(entries or {})
        self.upserts = []

    def get_dataset_registry(self, symbol, timeframe):
        entry = self.entries.get((symbol, timeframe))
        return [dict(entry)] if entry else []

    def upsert_dataset_registry(self, entry):
        copied = dict(entry)
        self.upserts.append(copied)
        self.entries[(entry["symbol"], entry["timeframe"])] = copied
        return copied


def scheduler_update(tmp_path, rows: pd.DataFrame, timeframe="H1"):
    db = FakeDatabase()
    with patch.object(autonomous_scheduler, "PROJECT_ROOT", tmp_path), patch.object(
        autonomous_scheduler,
        "fetch_market_data",
        return_value=(rows, "TestProvider"),
    ):
        result = autonomous_scheduler.run_rolling_update(db, "EURUSD", timeframe)
    return db, result, tmp_path / "data" / "forex" / f"EURUSD_{timeframe}.csv"


def test_window_over_2000_keeps_exact_latest_2000(tmp_path):
    rd = RollingDataset("EURUSD", "H1", csv_path=tmp_path / "data.csv")
    rd.update_frame(frame(2100))
    stored = pd.read_csv(rd.csv_path, parse_dates=["timestamp"])
    assert len(stored) == ROLLING_WINDOW
    assert stored.iloc[0]["timestamp"] == frame(2100).iloc[-ROLLING_WINDOW]["timestamp"]


def test_1999_closed_candles_are_pending(tmp_path):
    db, result, _ = scheduler_update(tmp_path, frame(1999))
    assert result["action"] == "pending"
    assert db.upserts[-1]["status"] == "pending"
    assert db.upserts[-1]["candle_count"] == 1999


def test_2000_closed_candles_are_ready(tmp_path):
    db, result, path = scheduler_update(tmp_path, frame(2000))
    assert result["status"] == "ready"
    assert db.upserts[-1]["status"] == "ready"
    assert db.upserts[-1]["candle_count"] == ROLLING_WINDOW
    calculated = pd.read_csv(path, parse_dates=["timestamp"])
    validate_dataset(calculated, ROLLING_WINDOW)
    for column, minimum_history in INDICATOR_MIN_HISTORY.items():
        values = pd.to_numeric(
            calculated[column].iloc[minimum_history - 1:], errors="coerce"
        )
        assert np.isfinite(values).any(), column


def test_duplicate_timestamps_are_deduplicated(tmp_path):
    rows = pd.concat([frame(2000), frame(2000).iloc[[-1]]], ignore_index=True)
    rd = RollingDataset("EURUSD", "H1", csv_path=tmp_path / "data.csv")
    rd.update_frame(rows)
    stored = pd.read_csv(rd.csv_path)
    assert len(stored) == ROLLING_WINDOW
    assert stored["timestamp"].nunique() == ROLLING_WINDOW


def test_out_of_order_timestamps_are_sorted(tmp_path):
    rows = frame(2000).sample(frac=1, random_state=7)
    rd = RollingDataset("EURUSD", "H1", csv_path=tmp_path / "data.csv")
    rd.update_frame(rows)
    stored = pd.read_csv(rd.csv_path, parse_dates=["timestamp"])
    assert stored["timestamp"].is_monotonic_increasing


def test_incoming_duplicate_timestamp_wins_deterministically(tmp_path):
    path = tmp_path / "data.csv"
    initial = frame(2000)
    rd = RollingDataset("EURUSD", "H1", csv_path=path)
    rd.update_frame(initial)
    correction = initial.iloc[[-1]].copy()
    correction["close"] = 9.99
    rd.update_frame(correction)
    stored = pd.read_csv(path)
    assert len(stored) == ROLLING_WINDOW
    assert stored.iloc[-1]["close"] == pytest.approx(9.99)


def test_invalid_timestamp_rejects_update_and_preserves_file(tmp_path):
    path = tmp_path / "data.csv"
    rd = RollingDataset("EURUSD", "H1", csv_path=path)
    rd.update_frame(frame(2000))
    original = path.read_bytes()
    invalid = frame(1)
    invalid["timestamp"] = ["not-a-timestamp"]
    with pytest.raises(DatasetValidationError, match="Invalid timestamps"):
        rd.update_frame(invalid)
    assert path.read_bytes() == original


def test_replace_failure_preserves_previous_csv(tmp_path):
    path = tmp_path / "data.csv"
    rd = RollingDataset("EURUSD", "H1", csv_path=path)
    rd.update_frame(frame(2000))
    original = path.read_bytes()
    with patch("forex.data.rolling_dataset.os.replace", side_effect=OSError("crash")):
        with pytest.raises(OSError, match="crash"):
            rd.update_frame(frame(1, start="2025-01-01"))
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(f".{path.name}.*.tmp"))


def test_atomic_success_leaves_no_temporary_file(tmp_path):
    path = tmp_path / "data.csv"
    RollingDataset("EURUSD", "H1", csv_path=path).update_frame(frame(2000))
    assert not list(tmp_path.glob(f".{path.name}.*.tmp"))


def test_runtime_dataset_directory_supports_lock_and_atomic_temp_contract(tmp_path):
    runtime_dir = tmp_path / "opt" / "astra" / "data" / "forex"
    runtime_dir.mkdir(parents=True)
    runtime_dir.chmod(0o750)
    if os.name == "posix":
        assert stat.S_IMODE(runtime_dir.stat().st_mode) == 0o750

    path = runtime_dir / "EURUSD_H1.csv"
    dataset = RollingDataset("EURUSD", "H1", csv_path=path, lock_timeout=0.1)
    from forex.data import rolling_dataset as rolling_module

    real_write = rolling_module.atomic_write_csv
    lock_observed_during_transaction = False

    def observe_lock(rows, target):
        nonlocal lock_observed_during_transaction
        lock_observed_during_transaction = dataset.lock_path.exists()
        return real_write(rows, target)

    with patch.object(rolling_module, "atomic_write_csv", side_effect=observe_lock):
        dataset.update_frame(frame(2000))

    assert path.is_file()
    assert dataset.lock_path.parent == runtime_dir.resolve()
    assert lock_observed_during_transaction
    assert not list(runtime_dir.glob(f".{path.name}.*.tmp"))
    # Backends differ on retaining the lock inode, but the advisory lock must
    # be released so the next scheduler transaction can acquire it immediately.
    with FileLock(str(dataset.lock_path), timeout=0.1):
        pass


def test_two_writers_on_same_dataset_do_not_corrupt_or_lose_rows(tmp_path):
    path = tmp_path / "shared.csv"
    RollingDataset("EURUSD", "H1", csv_path=path).update_frame(frame(2000))
    updates = [frame(1, start="2025-01-01"), frame(1, start="2025-01-02")]
    errors = []

    def write(rows):
        try:
            RollingDataset("EURUSD", "H1", csv_path=path).update_frame(rows)
        except Exception as exc:  # pragma: no cover - assertion captures details
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(rows,)) for rows in updates]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    stored = pd.read_csv(path, parse_dates=["timestamp"])
    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    assert len(stored) == ROLLING_WINDOW
    assert stored["timestamp"].is_monotonic_increasing
    assert set(pd.to_datetime(["2025-01-01", "2025-01-02"])).issubset(
        set(stored["timestamp"])
    )


def test_writers_for_different_datasets_use_independent_locks(tmp_path):
    paths = [tmp_path / "one.csv", tmp_path / "two.csv"]
    barrier = threading.Barrier(2)
    errors = []
    from forex.data import rolling_dataset as rolling_module

    real_write = rolling_module.atomic_write_csv

    def synchronized_write(rows, path):
        barrier.wait(timeout=3)
        return real_write(rows, path)

    def write(path):
        try:
            RollingDataset("EURUSD", "H1", csv_path=path).update_frame(frame(10))
        except Exception as exc:  # pragma: no cover - assertion captures details
            errors.append(exc)

    with patch.object(rolling_module, "atomic_write_csv", side_effect=synchronized_write):
        threads = [threading.Thread(target=write, args=(path,)) for path in paths]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    assert all(path.is_file() for path in paths)


def test_indicator_error_preserves_previous_dataset(tmp_path):
    path = tmp_path / "indicators.csv"
    rows = frame(2000)
    rows["RSI_14"] = 50.0
    rd = RollingDataset("EURUSD", "H1", csv_path=path)
    rd.update_frame(rows)
    original = path.read_bytes()
    with patch(
        "forex.data.indicator_delta.recalculate_tail_indicators",
        side_effect=RuntimeError("indicator failure"),
    ):
        with pytest.raises(RuntimeError, match="indicator failure"):
            rd.update_frame(frame(1, start="2025-01-01"))
    assert path.read_bytes() == original


def test_initialize_from_ohlcv_calculates_required_indicators(tmp_path):
    path = tmp_path / "initialized.csv"
    rd = RollingDataset("EURUSD", "H1", csv_path=path)

    assert rd.initialize(frame(2000))

    stored = pd.read_csv(path)
    assert REQUIRED_TECHNICAL_COLUMNS.issubset(stored.columns)
    assert not stored[list(REQUIRED_TECHNICAL_COLUMNS)].isna().all().any()


def test_short_dataset_materializes_indicators_and_allows_warmup_nan():
    calculated = recalculate_tail_indicators(frame(1), k=1)

    assert REQUIRED_TECHNICAL_COLUMNS.issubset(calculated.columns)
    assert calculated[list(REQUIRED_TECHNICAL_COLUMNS)].isna().all().all()
    validate_dataset(calculated, ROLLING_WINDOW)


def test_initialize_indicator_failure_preserves_previous_bytes(tmp_path):
    path = tmp_path / "initialized.csv"
    rd = RollingDataset("EURUSD", "H1", csv_path=path)
    assert rd.initialize(frame(2000))
    original = path.read_bytes()

    with patch(
        "forex.data.indicator_delta.recalculate_tail_indicators",
        side_effect=RuntimeError("indicator failure"),
    ):
        assert not rd.initialize(frame(2000, start="2021-01-01"))

    assert path.read_bytes() == original


def test_validate_rejects_missing_required_indicator_during_warmup():
    calculated = recalculate_tail_indicators(frame(1), k=1)
    calculated = calculated.drop(columns=["ATR_14"])

    with pytest.raises(
        DatasetValidationError,
        match="Missing required indicator columns.*ATR_14",
    ):
        validate_dataset(calculated, ROLLING_WINDOW)


@pytest.mark.parametrize(
    ("column", "minimum_history"),
    INDICATOR_MIN_HISTORY.items(),
)
def test_validate_rejects_all_nan_indicator_once_calculable(
    column,
    minimum_history,
):
    calculated = recalculate_tail_indicators(
        frame(minimum_history), k=minimum_history
    )
    calculated[column] = np.nan

    with pytest.raises(
        DatasetValidationError,
        match=rf"Indicator {column} contains no valid values.*minimum history: {minimum_history}",
    ):
        validate_dataset(calculated, ROLLING_WINDOW)


def test_validate_rejects_all_non_finite_indicator_once_calculable():
    minimum_history = INDICATOR_MIN_HISTORY["MACD_signal"]
    calculated = recalculate_tail_indicators(
        frame(minimum_history), k=minimum_history
    )
    calculated["MACD_signal"] = np.inf

    with pytest.raises(
        DatasetValidationError,
        match="Indicator MACD_signal contains no valid values",
    ):
        validate_dataset(calculated, ROLLING_WINDOW)


class Provider:
    def __init__(self, result=None, *, available=True, error=None):
        self.result = result
        self.available = available
        self.error = error
        self.calls = []

    def is_available(self):
        return self.available

    def fetch(self, pair, timeframe, bars, **kwargs):
        self.calls.append((pair, timeframe, bars, kwargs))
        if self.error:
            raise self.error
        return self.result


def test_mt5_exception_executes_and_reports_yahoo_fallback(capsys):
    provider = MT5Provider()
    fallback = Mock(return_value=frame(2))
    mt5 = types.SimpleNamespace(
        copy_rates_from_pos=Mock(side_effect=RuntimeError("terminal down"))
    )

    with patch.object(provider, "_ensure_init", return_value=True), patch.object(
        provider, "_fallback", fallback
    ), patch.dict(sys.modules, {"MetaTrader5": mt5}):
        result = provider.fetch("EURUSD", "H1", 2000, allow_fallback=True)

    assert result is fallback.return_value
    fallback.assert_called_once_with("EURUSD", "H1", 2000)
    assert "usando fallback Yahoo" in capsys.readouterr().out


def test_mt5_exception_without_fallback_reports_only_mt5_error(capsys):
    provider = MT5Provider()
    fallback = Mock()
    mt5 = types.SimpleNamespace(
        copy_rates_from_pos=Mock(side_effect=RuntimeError("terminal down"))
    )

    with patch.object(provider, "_ensure_init", return_value=True), patch.object(
        provider, "_fallback", fallback
    ), patch.dict(sys.modules, {"MetaTrader5": mt5}):
        result = provider.fetch("EURUSD", "H1", 2000, allow_fallback=False)

    output = capsys.readouterr().out
    assert result is None
    fallback.assert_not_called()
    assert "Error MT5: terminal down" in output
    assert "Yahoo" not in output


def test_data_router_uses_available_primary_forex_provider():
    primary = Provider(frame(2))
    fallback = Provider(frame(2))
    with patch("forex.data.mt5_provider.get_mt5_provider", return_value=primary), patch(
        "forex.data.yahoo_provider.get_yahoo_provider", return_value=fallback
    ):
        router = DataRouter("EURUSD", "H1")
        result = router.fetch(2001, raise_on_failure=True)
    assert len(result) == 2
    assert router.source_used == "MT5"
    assert primary.calls[0][3] == {"allow_fallback": False}
    assert fallback.calls == []


def test_data_router_uses_real_fallback_when_primary_fails():
    primary = Provider(error=RuntimeError("primary down"))
    fallback = Provider(frame(2))
    with patch("forex.data.mt5_provider.get_mt5_provider", return_value=primary), patch(
        "forex.data.yahoo_provider.get_yahoo_provider", return_value=fallback
    ):
        router = DataRouter("EURUSD", "H1")
        result = router.fetch(2001, raise_on_failure=True)
    assert len(result) == 2
    assert router.source_used == "Yahoo"
    assert len(primary.calls) == len(fallback.calls) == 1


def test_data_router_uses_binance_before_crypto_fallback():
    primary = Provider(frame(2))
    fallback = Provider(frame(2))
    with patch("forex.data.binance_provider.get_binance_provider", return_value=primary), patch(
        "forex.data.yahoo_provider.get_yahoo_provider", return_value=fallback
    ):
        router = DataRouter("BTCUSDT", "H4")
        result = router.fetch(2001, raise_on_failure=True)
    assert len(result) == 2
    assert router.source_used == "Binance"
    assert fallback.calls == []


def test_binance_provider_paginates_beyond_api_limit():
    hour_ms = 60 * 60 * 1000
    first_ms = int(pd.Timestamp("2020-01-01", tz="UTC").timestamp() * 1000)
    klines = []
    for index in range(2002):
        opened = first_ms + index * hour_ms
        klines.append([
            opened, "1", "2", "0.5", "1.5", "10", opened + hour_ms - 1,
            "0", 1, "0", "0", "0",
        ])

    calls = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    requests_module = types.ModuleType("requests")

    def get(_url, *, params, timeout):
        calls.append((dict(params), timeout))
        eligible = klines
        if "endTime" in params:
            eligible = [row for row in klines if row[0] <= params["endTime"]]
        return Response(eligible[-params["limit"]:])

    requests_module.get = get
    provider = BinanceProvider()
    provider._available = True
    with patch.dict(sys.modules, {"requests": requests_module}):
        result = provider.fetch("BTCUSDT", "H1", bars=2001)
    assert len(result) == 2001
    assert result["timestamp"].is_monotonic_increasing
    assert len(calls) == 3
    assert all(call[0]["limit"] <= 1000 for call in calls)


def test_data_router_all_failures_are_explicit_without_synthetic_data():
    primary = Provider(result=None)
    fallback = Provider(error=RuntimeError("fallback down"))
    with patch("forex.data.mt5_provider.get_mt5_provider", return_value=primary), patch(
        "forex.data.yahoo_provider.get_yahoo_provider", return_value=fallback
    ):
        router = DataRouter("EURUSD", "H1")
        with pytest.raises(DataProviderError, match="MT5 returned no data") as error:
            router.fetch(2001, raise_on_failure=True)
    assert "fallback down" in str(error.value)
    assert router.source_used == "none"


def test_productive_scheduler_has_no_direct_yahoo_dependency():
    source_path = Path(autonomous_scheduler.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert "yfinance" not in source.lower()
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "forex.data.data_router"
        for node in imports
    )


def test_cli_init_uses_the_existing_deployment_integration_hook():
    source = Path(autonomous_scheduler.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    main_function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    called_names = {
        node.func.id
        for node in ast.walk(main_function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    definitions = {
        node.name: node.lineno
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    entrypoint = next(
        node for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and any(
            isinstance(name, ast.Name) and name.id == "__name__"
            for name in ast.walk(node.test)
        )
    )
    assert "run_init_with_deployment_check" in called_names
    assert definitions["run_init_with_deployment_check"] < entrypoint.lineno


def test_registry_updates_only_after_successful_atomic_write(tmp_path):
    existing_path = tmp_path / "data" / "forex" / "EURUSD_H1.csv"
    existing_path.parent.mkdir(parents=True)
    initial = frame(2000)
    initial.to_csv(existing_path, index=False)
    entry = {
        "symbol": "EURUSD",
        "timeframe": "H1",
        "status": "ready",
        "candle_count": 2000,
        "rolling_window_size": 2000,
        "last_candle_timestamp": str(initial["timestamp"].iloc[-1]),
        "blob_path": str(existing_path),
    }
    db = FakeDatabase({("EURUSD", "H1"): entry})
    original = existing_path.read_bytes()
    with patch.object(autonomous_scheduler, "PROJECT_ROOT", tmp_path), patch.object(
        autonomous_scheduler,
        "fetch_market_data",
        return_value=(frame(1, start="2025-01-01"), "TestProvider"),
    ), patch("forex.data.rolling_dataset.os.replace", side_effect=OSError("disk")):
        result = autonomous_scheduler.run_rolling_update(db, "EURUSD", "H1")
    assert result["action"] == "error"
    assert db.upserts == []
    assert db.entries[("EURUSD", "H1")] == entry
    assert existing_path.read_bytes() == original


def test_legacy_registry_is_read_only_and_successful_update_moves_registry(tmp_path):
    legacy_path = tmp_path / "forex" / "data" / "EURUSD_H1.csv"
    legacy_path.parent.mkdir(parents=True)
    initial = frame(2000)
    initial.to_csv(legacy_path, index=False)
    original = legacy_path.read_bytes()
    entry = {
        "symbol": "EURUSD",
        "timeframe": "H1",
        "status": "ready",
        "candle_count": 2000,
        "rolling_window_size": 2000,
        "last_candle_timestamp": str(initial["timestamp"].iloc[-1]),
        "blob_path": str(legacy_path),
    }
    db = FakeDatabase({("EURUSD", "H1"): entry})

    with patch.object(autonomous_scheduler, "PROJECT_ROOT", tmp_path), patch.object(
        autonomous_scheduler,
        "fetch_market_data",
        return_value=(frame(2000), "TestProvider"),
    ):
        result = autonomous_scheduler.run_rolling_update(db, "EURUSD", "H1")

    canonical = tmp_path / "data" / "forex" / "EURUSD_H1.csv"
    assert result["action"] == "generated"
    assert canonical.is_file()
    assert legacy_path.read_bytes() == original
    assert Path(db.upserts[-1]["blob_path"]).resolve() == canonical.resolve()


def test_legacy_dataset_path_remains_readable_without_becoming_a_writer(tmp_path):
    legacy_path = tmp_path / "forex" / "data" / "EURUSD_H1.csv"
    legacy_path.parent.mkdir(parents=True)
    frame(10).to_csv(legacy_path, index=False)

    with patch.object(autonomous_scheduler, "PROJECT_ROOT", tmp_path):
        loaded = autonomous_scheduler.load_dataset_csv("EURUSD", "H1")

    assert len(loaded) == 10
    assert not (tmp_path / "data" / "forex" / "EURUSD_H1.csv").exists()


def test_dataset_updater_default_uses_canonical_runtime_helper(tmp_path):
    from forex.data import dataset_updater as updater_module

    runtime_root = tmp_path / "data" / "forex"
    with patch.object(updater_module, "forex_dataset_root", return_value=runtime_root):
        updater = updater_module.DatasetUpdater()

    assert updater.data_dir == runtime_root
    assert updater._csv_path("EURUSD", "H1") == str(
        runtime_root / "EURUSD_H1.csv"
    )


def test_registry_upsert_happens_after_atomic_replace(tmp_path):
    from forex.data import rolling_dataset as rolling_module

    write_completed = False
    real_write = rolling_module.atomic_write_csv

    def tracked_write(rows, path):
        nonlocal write_completed
        result = real_write(rows, path)
        write_completed = True
        return result

    class OrderedDatabase(FakeDatabase):
        def upsert_dataset_registry(self, entry):
            assert write_completed
            return super().upsert_dataset_registry(entry)

    db = OrderedDatabase()
    with patch.object(autonomous_scheduler, "PROJECT_ROOT", tmp_path), patch.object(
        autonomous_scheduler,
        "fetch_market_data",
        return_value=(frame(2000), "TestProvider"),
    ), patch.object(rolling_module, "atomic_write_csv", side_effect=tracked_write):
        result = autonomous_scheduler.run_rolling_update(db, "EURUSD", "H1")
    assert result["status"] == "ready"
    assert len(db.upserts) == 1


def test_registry_count_and_path_match_persisted_rows(tmp_path):
    db, result, path = scheduler_update(tmp_path, frame(2050))
    entry = db.upserts[-1]
    persisted = pd.read_csv(path)
    assert result["status"] == "ready"
    assert entry["candle_count"] == len(persisted) == ROLLING_WINDOW
    assert Path(entry["blob_path"]).resolve() == path.resolve()
    assert entry["last_candle_timestamp"] == str(
        pd.to_datetime(persisted["timestamp"].iloc[-1])
    )


@pytest.mark.parametrize("timeframe,freq", [("H1", "h"), ("H4", "4h"), ("D1", "D")])
def test_all_productive_timeframes_use_2000_window(tmp_path, timeframe, freq):
    db, result, path = scheduler_update(
        tmp_path, frame(2050, freq=freq, start="2010-01-01"), timeframe
    )
    assert result["status"] == "ready"
    assert len(pd.read_csv(path)) == ROLLING_WINDOW
    assert db.upserts[-1]["rolling_window_size"] == ROLLING_WINDOW


@pytest.mark.parametrize("timeframe", ["H4", "D1"])
def test_higher_timeframe_cycles_never_predict(timeframe):
    db = Mock()
    db.create_scheduler_run.return_value = {"id": 1}
    db.get_supported_symbols.return_value = [{"symbol_code": "EURUSD"}]
    with patch.object(autonomous_scheduler, "detect_new_symbols", return_value=[]), patch.object(
        autonomous_scheduler, "run_rolling_update", return_value={"action": "updated"}
    ), patch.object(autonomous_scheduler, "run_prediction") as predict:
        autonomous_scheduler.run_cycle(db, timeframe)
    predict.assert_not_called()


def test_open_h4_and_d1_candles_are_excluded(tmp_path):
    now = pd.Timestamp("2026-01-02 02:00")
    for timeframe, timestamps in {
        "H4": ["2026-01-01 20:00", "2026-01-02 00:00"],
        "D1": ["2025-12-31 00:00", "2026-01-02 00:00"],
    }.items():
        rows = frame(2)
        rows["timestamp"] = pd.to_datetime(timestamps)
        path = tmp_path / f"{timeframe}.csv"
        RollingDataset("EURUSD", timeframe, csv_path=path).update_frame(rows, now=now)
        stored = pd.read_csv(path)
        assert len(stored) == 1


def test_provider_failure_preserves_ready_registry_and_csv(tmp_path):
    path = tmp_path / "EURUSD_H1.csv"
    initial = frame(2000)
    initial.to_csv(path, index=False)
    entry = {
        "symbol": "EURUSD",
        "timeframe": "H1",
        "status": "ready",
        "candle_count": 2000,
        "rolling_window_size": 2000,
        "last_candle_timestamp": str(initial["timestamp"].iloc[-1]),
        "blob_path": str(path),
    }
    db = FakeDatabase({("EURUSD", "H1"): entry})
    with patch.object(
        autonomous_scheduler,
        "fetch_market_data",
        side_effect=DataProviderError("all providers failed"),
    ):
        result = autonomous_scheduler.run_rolling_update(db, "EURUSD", "H1")
    assert result == {"action": "error", "error": "all providers failed"}
    assert db.upserts == []
    assert len(pd.read_csv(path)) == ROLLING_WINDOW

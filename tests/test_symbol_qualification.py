from __future__ import annotations

import ast
import sqlite3
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from scripts import validate_symbol_universe as qualification


pytestmark = pytest.mark.unit


class FakeDatabase:
    def __init__(self, symbols=None, entries=None):
        self.symbols = list(symbols or [])
        self.entries = dict(entries or {})

    def get_active_symbols(self):
        return [dict(row) for row in self.symbols if row.get("status") == "active"]

    def get_data_symbols(self):
        return [
            dict(row)
            for row in self.symbols
            if row.get("status") in {"qualified", "active"}
        ]

    def get_supported_symbols(self):
        return [dict(row) for row in self.symbols]

    def get_dataset_registry(self, symbol=None, tf=None):
        if symbol is not None and tf is not None:
            entry = self.entries.get((symbol, tf))
            return [dict(entry)] if entry else []
        return [dict(entry) for entry in self.entries.values()]


def active_symbol(symbol: str, pip_value: float = 0.0001) -> dict:
    spec = qualification.get_symbol_spec(symbol)
    return {
        "id": 1,
        "symbol_code": symbol,
        "display_name": spec.display_name,
        "asset_class": spec.asset_class,
        "pip_value": pip_value,
        "status": "active",
        "added_at": "2026-01-01T00:00:00",
    }


def ready_frame(
    symbol: str = "EURUSD",
    timeframe: str = "H1",
    *,
    count: int = qualification.ROLLING_WINDOW,
    now: pd.Timestamp = pd.Timestamp("2026-08-01 00:00:00"),
) -> pd.DataFrame:
    duration = qualification.TIMEFRAME_DURATION[timeframe]
    first = now - duration * count
    timestamps = pd.date_range(first, periods=count, freq=duration)
    offsets = np.linspace(0.0, 0.05, count)
    frame = pd.DataFrame({
        "timestamp": timestamps,
        "open": 1.0 + offsets,
        "high": 1.002 + offsets,
        "low": 0.998 + offsets,
        "close": 1.001 + offsets,
        "volume": np.full(count, 1000.0),
        "pair": symbol,
    })
    for column, values in qualification._independent_indicators(frame).items():
        frame[column] = values
    return frame


def write_ready_dataset(
    root: Path,
    symbol: str,
    timeframe: str,
    *,
    now: pd.Timestamp,
) -> tuple[dict, pd.DataFrame]:
    frame = ready_frame(symbol, timeframe, now=now)
    path = root / "data" / "forex" / f"{symbol}_{timeframe}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    source_sha256 = qualification.sha256_file(path)
    entry = {
        "id": 1,
        "symbol": symbol,
        "timeframe": timeframe,
        "candle_count": qualification.ROLLING_WINDOW,
        "rolling_window_size": qualification.ROLLING_WINDOW,
        "last_candle_timestamp": str(frame["timestamp"].iloc[-1]),
        "blob_path": str(path),
        "status": "ready",
        "last_error": None,
        "last_updated": "2026-08-01T00:00:00",
        "provider_used": "Yahoo",
        "external_ticker": qualification.get_symbol_spec(symbol).fallback.external_ticker,
        "provider_class": "FX_REFERENCE",
        "source_fetched_at": "2026-08-01T00:00:00+00:00",
        "source_sha256": source_sha256,
        "legacy_provenance_pending": 0,
    }
    return entry, frame


@pytest.mark.parametrize(
    "symbol",
    qualification.DECLARED_CODE_SYMBOLS,
    ids=qualification.DECLARED_CODE_SYMBOLS,
)
def test_symbol_contract(symbol):
    spec = qualification.route_spec(symbol)

    assert spec.symbol == symbol
    assert spec.declarations
    assert spec.asset_class in {"FOREX", "METAL", "COMMODITY", "CRYPTO", "INDEX"}
    assert spec.astra_supported is True
    assert (spec.h1_supported, spec.h4_supported, spec.d1_supported) == (
        True,
        True,
        True,
    )


def test_declared_universe_includes_every_source_and_required_candidate():
    universe = set(qualification.DECLARED_CODE_SYMBOLS)

    assert set(qualification.PAIR_CONFIG) <= universe
    assert universe == set(qualification.catalog_codes())
    assert {"USOUSD", "UKOUSD", "BTCUSDT", "ETHUSDT"} <= universe
    assert not ({"USOIL", "UKOIL", "BTCUSD", "ETHUSD"} & universe)


@pytest.mark.parametrize("timeframe", ["H1", "H4", "D1"])
def test_timeframe_contract_is_explicit(timeframe):
    spec = qualification.route_spec("EURUSD")
    assert getattr(spec, f"{timeframe.lower()}_supported") is True
    assert timeframe in qualification.TIMEFRAME_DURATION


def test_provider_mapping_reports_primary_fallback_and_external_tickers():
    forex = qualification.route_spec("EURUSD")
    crypto = qualification.route_spec("BTCUSDT")
    metal = qualification.route_spec("XAUUSD")

    assert (forex.provider_primary, forex.provider_fallback) == ("MT5", "Yahoo")
    assert forex.fallback_external_ticker == "EURUSD=X"
    assert (crypto.provider_primary, crypto.primary_external_ticker) == (
        "Binance",
        "BTCUSDT",
    )
    assert metal.fallback_external_ticker is None
    assert any("GC=F" in reason for reason in metal.blocked_routes)


@pytest.mark.parametrize("symbol", ["USOIL", "UKOIL"])
def test_legacy_oil_names_are_not_canonical_aliases(symbol):
    harness = qualification.SymbolQualificationHarness(FakeDatabase())
    stage, _spec = harness._routing_stage(symbol)

    assert stage["status"] == "FAIL"
    assert any("Unsupported symbol" in error for error in stage["errors"])


@pytest.mark.parametrize("symbol", ["BTCUSD", "ETHUSD"])
def test_usd_crypto_names_are_not_silently_treated_as_usdt(symbol):
    harness = qualification.SymbolQualificationHarness(FakeDatabase())
    stage, spec = harness._routing_stage(symbol)

    assert spec.primary_ticker_catalogued is False
    assert stage["status"] == "FAIL"
    assert any("Unsupported symbol" in error for error in stage["errors"])


def test_ready_frame_contract_checks_all_2000_rows_and_indicators():
    now = pd.Timestamp("2026-08-01 00:00:00")
    stage, normalized = qualification.validate_dataset_frame(
        ready_frame(now=now), "EURUSD", "H1", now=now
    )

    assert stage["status"] == "PASS"
    assert len(normalized) == qualification.ROLLING_WINDOW
    assert stage["details"]["physical_rows"] == qualification.ROLLING_WINDOW
    assert all(
        result["status"] == "PASS"
        for result in stage["details"]["indicators"]
    )


def test_rolling_ready_requires_exactly_2000_rows():
    now = pd.Timestamp("2026-08-01 00:00:00")
    stage, _ = qualification.validate_dataset_frame(
        ready_frame(count=1999, now=now), "EURUSD", "H1", now=now
    )

    assert stage["status"] == "FAIL"
    assert any("expected 2000" in error for error in stage["errors"])


def test_duplicate_timestamp_is_rejected():
    now = pd.Timestamp("2026-08-01 00:00:00")
    frame = ready_frame(now=now)
    frame.loc[frame.index[-1], "timestamp"] = frame.loc[frame.index[-2], "timestamp"]

    stage, _ = qualification.validate_dataset_frame(frame, "EURUSD", "H1", now=now)

    assert stage["status"] == "FAIL"
    assert any("Duplicate timestamps" in error for error in stage["errors"])


def test_open_candle_is_rejected():
    now = pd.Timestamp("2026-08-01 00:00:00")
    frame = ready_frame(now=now)
    frame.loc[frame.index[-1], "timestamp"] = now - pd.Timedelta(minutes=30)

    stage, _ = qualification.validate_dataset_frame(frame, "EURUSD", "H1", now=now)

    assert stage["status"] == "FAIL"
    assert any("Open candles present" in error for error in stage["errors"])


def test_malformed_ohlc_is_rejected():
    now = pd.Timestamp("2026-08-01 00:00:00")
    frame = ready_frame(now=now)
    frame.loc[100, "high"] = frame.loc[100, "low"] - 0.1

    stage, _ = qualification.validate_dataset_frame(frame, "EURUSD", "H1", now=now)

    assert stage["status"] == "FAIL"
    assert any("Malformed/non-positive OHLC" in error for error in stage["errors"])


def test_out_of_order_timestamp_is_rejected():
    now = pd.Timestamp("2026-08-01 00:00:00")
    frame = ready_frame(now=now)
    frame.loc[[100, 101], "timestamp"] = frame.loc[[101, 100], "timestamp"].to_numpy()

    stage, _ = qualification.validate_dataset_frame(frame, "EURUSD", "H1", now=now)

    assert stage["status"] == "FAIL"
    assert any("monotonically increasing" in error for error in stage["errors"])


def test_independent_indicator_mismatch_is_rejected():
    now = pd.Timestamp("2026-08-01 00:00:00")
    frame = ready_frame(now=now)
    frame.loc[1500:, "RSI_14"] += 5.0

    stage, _ = qualification.validate_dataset_frame(frame, "EURUSD", "H1", now=now)

    assert stage["status"] == "FAIL"
    assert any("Indicator RSI_14 differs" in error for error in stage["errors"])


def test_cross_timeframe_aggregation_compares_real_ohlc_components():
    lower = ready_frame(count=8, now=pd.Timestamp("2026-08-01 08:00:00"))
    higher_rows = []
    for start in (0, 4):
        group = lower.iloc[start:start + 4]
        higher_rows.append({
            "timestamp": group["timestamp"].iloc[0],
            "open": group["open"].iloc[0],
            "high": group["high"].max(),
            "low": group["low"].min(),
            "close": group["close"].iloc[-1],
        })

    result = qualification._aggregate_comparison(
        lower,
        pd.DataFrame(higher_rows),
        lower_duration=pd.Timedelta(hours=1),
        candles_per_group=4,
    )

    assert result["status"] == "PASS"
    assert result["rows_compared"] == 2


@pytest.mark.parametrize(
    ("timestamps", "asset_class", "expected"),
    [
        (
            pd.Series(["2026-07-31", "2026-08-03"]),
            "FOREX",
            "WEEKEND",
        ),
        (
            pd.Series(["2026-08-01 00:00", "2026-08-01 02:00"]),
            "CRYPTO",
            "PROVIDER_GAP",
        ),
        (
            pd.Series(["2026-08-01 00:00", "2026-08-01 00:30"]),
            "CRYPTO",
            "INVALID_GAP",
        ),
    ],
    ids=("weekend", "provider", "invalid"),
)
def test_gap_classification_is_explicit(timestamps, asset_class, expected):
    gaps = qualification.classify_gaps(timestamps, "H1", asset_class)

    assert [gap["classification"] for gap in gaps] == [expected]


def test_registry_and_physical_file_must_match(tmp_path):
    now = pd.Timestamp("2026-08-01 00:00:00")
    entry, frame = write_ready_dataset(tmp_path, "EURUSD", "H1", now=now)
    db = FakeDatabase([active_symbol("EURUSD")], {("EURUSD", "H1"): entry})
    harness = qualification.SymbolQualificationHarness(db, project_root=tmp_path, now=now)

    stage, loaded = harness._timeframe_stage("EURUSD", "H1", frame, {
        "provider_used": "Yahoo",
        "external_ticker": "EURUSD=X",
        "provider_class": "FX_REFERENCE",
    })

    assert stage["status"] == "PASS"
    assert len(loaded) == qualification.ROLLING_WINDOW
    assert stage["details"]["provider_provenance"]["status"] == "MATCH"


def test_provider_overlap_without_the_latest_2000_candles_blocks_qualification(tmp_path):
    now = pd.Timestamp("2026-08-01 00:00:00")
    entry, _ = write_ready_dataset(tmp_path, "EURUSD", "H1", now=now)
    db = FakeDatabase([active_symbol("EURUSD")], {("EURUSD", "H1"): entry})
    harness = qualification.SymbolQualificationHarness(db, project_root=tmp_path, now=now)
    newer_provider_frame = ready_frame(
        "EURUSD", "H1", now=now + pd.Timedelta(hours=1)
    )

    stage, _ = harness._timeframe_stage(
        "EURUSD",
        "H1",
        newer_provider_frame,
        {
            "provider_used": "Yahoo",
            "external_ticker": "EURUSD=X",
            "provider_class": "FX_REFERENCE",
        },
    )

    assert stage["status"] == "WARNING"
    assert stage["blocking"] is True
    assert stage["details"]["provider_provenance"]["status"] == "MISMATCH"
    assert stage["details"]["provider_provenance"]["timestamp_sets_equal"] is False


def test_cross_symbol_paths_and_pair_values_are_isolated(tmp_path):
    now = pd.Timestamp("2026-08-01 00:00:00")
    entries = {}
    expected_paths = {}
    for symbol in ("EURUSD", "GBPUSD"):
        for timeframe in qualification.TIMEFRAMES:
            entry, _frame = write_ready_dataset(tmp_path, symbol, timeframe, now=now)
            entries[(symbol, timeframe)] = entry
            expected_paths[(symbol, timeframe)] = entry["blob_path"]
    db = FakeDatabase(
        [active_symbol("EURUSD"), active_symbol("GBPUSD")], entries
    )
    harness = qualification.SymbolQualificationHarness(db, project_root=tmp_path, now=now)

    results = harness.run(("EURUSD", "GBPUSD"))["symbols"]

    assert [result["symbol"] for result in results] == ["EURUSD", "GBPUSD"]
    for result in results:
        symbol = result["symbol"]
        for timeframe in qualification.TIMEFRAMES:
            details = result["stages"][timeframe]["details"]
            assert details["physical_path"] == expected_paths[(symbol, timeframe)]
            assert details["observed_pairs"] == [symbol]


class Provider:
    def __init__(self, frame=None, *, error=None):
        self.frame = frame
        self.error = error
        self.calls = []

    def is_available(self):
        return True

    def fetch(self, symbol, timeframe, bars, **kwargs):
        self.calls.append((symbol, timeframe, bars, kwargs))
        if self.error:
            raise self.error
        frame = self.frame(symbol, timeframe, bars) if callable(self.frame) else self.frame
        return frame.copy()


def test_provider_fallback_is_reported_without_network():
    now = pd.Timestamp.now(tz="UTC").floor("h").tz_localize(None)
    primary = Provider(error=RuntimeError("MT5 unavailable"))
    fallback = Provider(
        lambda symbol, timeframe, _bars: ready_frame(
            symbol, timeframe, count=2001, now=now
        )
    )
    harness = qualification.SymbolQualificationHarness(
        FakeDatabase(), probe_providers=True
    )

    with patch(
        "forex.data.mt5_provider.get_mt5_provider", return_value=primary
    ), patch(
        "forex.data.yahoo_provider.get_yahoo_provider", return_value=fallback
    ):
        stage, frames, metadata = harness._probe_stage(
            "EURUSD", qualification.route_spec("EURUSD")
        )

    assert stage["status"] == "PASS"
    assert set(frames) == set(qualification.TIMEFRAMES)
    assert all(item["provider_used"] == "Yahoo" for item in metadata.values())
    assert all("MT5" in item["attempt_errors"][0] for item in metadata.values())


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        (
            lambda frame: frame.assign(
                timestamp=frame["timestamp"].mask(
                    frame.index == frame.index[-1], frame["timestamp"].iloc[-2]
                )
            ),
            "duplicate timestamps",
        ),
        (
            lambda frame: frame.iloc[
                [*range(len(frame) - 2), len(frame) - 1, len(frame) - 2]
            ].reset_index(drop=True),
            "chronologically ordered",
        ),
    ],
    ids=("duplicates", "out-of-order"),
)
def test_provider_probe_does_not_repair_invalid_ordering(mutation, expected_error):
    frame = mutation(ready_frame(count=2001))

    with pytest.raises(ValueError, match=expected_error):
        qualification._normalize_probe_frame(frame, "EURUSD", "H1")


def test_unsupported_symbol_fails_closed_without_provider_call():
    harness = qualification.SymbolQualificationHarness(
        FakeDatabase(), probe_providers=True
    )

    with patch.object(
        qualification.DataRouter,
        "fetch",
        side_effect=AssertionError("unsupported symbol must not reach a provider"),
    ):
        result = harness.qualify_symbol("ZZZQQQ")

    assert result["stages"]["ROUTING"]["status"] == "FAIL"
    assert result["stages"]["PROVIDER"]["status"] == "FAIL"
    assert result["final"] == "FAIL"


def test_active_registry_row_does_not_turn_an_unknown_symbol_into_provider_support():
    unknown = {
        "id": 1,
        "symbol_code": "ZZZQQQ",
        "display_name": "Unknown",
        "asset_class": "UNKNOWN",
        "pip_value": 0.0001,
        "status": "active",
        "added_at": "2026-01-01T00:00:00",
    }
    harness = qualification.SymbolQualificationHarness(
        FakeDatabase([unknown]), probe_providers=True
    )

    with patch.object(
        qualification.DataRouter,
        "fetch",
        side_effect=AssertionError("an active unknown symbol must not reach a provider"),
    ):
        result = harness.qualify_symbol("ZZZQQQ")

    assert result["stages"]["REGISTRY"]["status"] == "PASS"
    assert result["stages"]["ROUTING"]["status"] == "FAIL"
    assert result["final"] == "FAIL"


def test_all_mode_is_sorted_and_sequential():
    harness = qualification.SymbolQualificationHarness(FakeDatabase())
    observed = []

    def qualify(symbol):
        observed.append(symbol)
        final = qualification._new_stage("FINAL")
        return {
            "symbol": symbol,
            "asset_class": "FOREX",
            "route": {},
            "stages": {"FINAL": final},
            "final": "PASS",
        }

    harness.qualify_symbol = qualify
    requested = ("USDJPY", "EURUSD", "GBPUSD")
    harness.run(requested)

    assert observed == list(requested)


def test_harness_source_has_no_prediction_model_or_training_calls():
    source_path = Path(qualification.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert not any(module.startswith("forex.prediction") for module in imports)
    assert "run_prediction(" not in source
    assert "train(" not in source
    assert "save_model" not in source


def test_json_report_is_atomic_and_parseable(tmp_path):
    report = {
        "symbols": [],
        "totals": {"PASS": 0, "WARNING": 0, "FAIL": 0},
    }
    path = tmp_path / "reports" / "qualification.json"

    result = qualification.write_json_report(report, path)

    assert Path(result) == path.resolve()
    assert json_load(path) == report
    assert not list(path.parent.glob(f".{path.name}.*.tmp"))


def test_default_registry_reader_opens_existing_sqlite_database_read_only(tmp_path):
    path = tmp_path / "astra.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE supported_symbols (
                symbol_code TEXT,
                display_name TEXT,
                pip_value REAL,
                status TEXT,
                added_at TEXT
            );
            CREATE TABLE dataset_registry (
                symbol TEXT,
                timeframe TEXT
            );
            INSERT INTO supported_symbols VALUES
                ('EURUSD', 'EUR/USD', 0.0001, 'active', '2026-01-01');
            INSERT INTO dataset_registry VALUES ('EURUSD', 'H1');
        """)
    original_connect = sqlite3.connect
    calls = []

    def connect(database, *args, **kwargs):
        calls.append((database, kwargs.copy()))
        return original_connect(database, *args, **kwargs)

    with patch.object(qualification.sqlite3, "connect", side_effect=connect):
        database = qualification.ReadOnlySQLiteDatabase(path)
        assert database.get_data_symbols()[0]["symbol_code"] == "EURUSD"
        assert database.get_dataset_registry("EURUSD", "H1") == [
            {"symbol": "EURUSD", "timeframe": "H1"}
        ]

    assert calls
    assert all("mode=ro" in str(database_uri) for database_uri, _ in calls)
    assert all(options.get("uri") is True for _, options in calls)


def json_load(path: Path):
    import json

    return json.loads(path.read_text(encoding="utf-8"))

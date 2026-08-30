"""Production-grade, fail-closed MT5 acquisition contract tests."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from forex.data.data_router import DataRouter
from forex.data.mt5_provider import (
    MT5DataContractError,
    MT5InitializationError,
    MT5Provider,
    MT5ProviderError,
    MT5SymbolError,
    MT5_HEADROOM,
)


pytestmark = pytest.mark.unit

NOW = pd.Timestamp("2026-08-31 12:30:00", tz="UTC")


def _rate(timestamp: str, index: int, *, invalid: bool = False) -> dict:
    opened = 1.1 + index * 0.0001
    high = opened + 0.0005
    closed = opened + 0.0002
    if invalid:
        closed = high + 1.0
    return {
        "time": int(pd.Timestamp(timestamp, tz="UTC").timestamp()),
        "open": opened,
        "high": high,
        "low": opened - 0.0005,
        "close": closed,
        "tick_volume": 100 + index,
        "spread": 12,
        "real_volume": 0,
    }


def _rates(
    timestamps: list[str], *, invalid: set[int] | None = None
) -> list[dict]:
    return [
        _rate(timestamp, index, invalid=index in (invalid or set()))
        for index, timestamp in enumerate(timestamps)
    ]


def _module(rates=None) -> types.ModuleType:
    module = types.ModuleType("MetaTrader5")
    module.__version__ = "5.0.unit-test"
    module.TIMEFRAME_H1 = 101
    module.TIMEFRAME_H4 = 104
    module.TIMEFRAME_D1 = 124
    module.initialize = Mock(return_value=True)
    module.shutdown = Mock(return_value=None)
    module.last_error = Mock(return_value=(1, "Success"))
    module.terminal_info = Mock(
        return_value=SimpleNamespace(build=5001, company="MetaQuotes Test")
    )
    module.account_info = Mock(
        return_value=SimpleNamespace(
            login=123456789,
            server="IFCMarkets-Demo",
            company="IFC Markets",
            trade_mode=0,
            balance=999999.0,
            equity=999999.0,
            password="must-never-appear",
        )
    )
    module.symbol_info = Mock(return_value=SimpleNamespace(visible=True))
    module.symbol_select = Mock(return_value=True)
    module.copy_rates_from_pos = Mock(return_value=rates)
    return module


def _fetch(
    module: types.ModuleType,
    *,
    timeframe: str = "H1",
    bars: int = 3,
    allow_fallback: bool = False,
):
    provider = MT5Provider()
    with patch.dict(sys.modules, {"MetaTrader5": module}):
        result = provider.fetch(
            "EURUSD",
            timeframe,
            bars,
            allow_fallback=allow_fallback,
            now=NOW,
        )
    return provider, result


def _closed_h1_with_current() -> list[dict]:
    return _rates([
        "2026-08-31 09:00:00",
        "2026-08-31 10:00:00",
        "2026-08-31 11:00:00",
        "2026-08-31 12:00:00",
    ])


def test_mt5_package_unavailable_reports_unavailable():
    provider = MT5Provider()

    with patch.dict(sys.modules, {"MetaTrader5": None}):
        assert provider.is_available() is False
        assert provider.availability_state == "PACKAGE_UNAVAILABLE"


def test_mt5_initialize_false_fails_safely():
    module = _module(_closed_h1_with_current())
    module.initialize.return_value = False
    module.last_error.return_value = (-10003, "terminal unavailable")

    with pytest.raises(MT5InitializationError, match="last_error_code=-10003"):
        _fetch(module)


def test_mt5_account_not_connected_fails_safely():
    module = _module(_closed_h1_with_current())
    module.account_info.return_value = None

    with pytest.raises(MT5InitializationError, match="ACCOUNT_NOT_CONNECTED"):
        _fetch(module)


def test_mt5_partial_initialization_cannot_bypass_account_check_on_retry():
    module = _module(_closed_h1_with_current())
    module.account_info.return_value = None
    provider = MT5Provider()

    with patch.dict(sys.modules, {"MetaTrader5": module}):
        for _attempt in range(2):
            with pytest.raises(
                MT5InitializationError, match="ACCOUNT_NOT_CONNECTED"
            ):
                provider.fetch("EURUSD", "H1", 3, now=NOW)

    assert module.initialize.call_count == 2
    assert module.account_info.call_count == 2
    assert module.shutdown.call_count == 2


def test_mt5_symbol_missing_fails_safely():
    module = _module(_closed_h1_with_current())
    module.symbol_info.return_value = None

    with pytest.raises(MT5SymbolError, match="MT5_SYMBOL_UNAVAILABLE"):
        _fetch(module)


def test_mt5_symbol_select_failure_is_explicit():
    module = _module(_closed_h1_with_current())
    module.symbol_info.return_value = SimpleNamespace(visible=False)
    module.symbol_select.return_value = False

    with pytest.raises(MT5SymbolError, match="MT5_SYMBOL_SELECT_FAILURE"):
        _fetch(module)

    module.symbol_select.assert_called_once_with("EURUSD", True)


@pytest.mark.parametrize("rates", [None, []], ids=("none", "empty"))
def test_mt5_copy_rates_missing_or_empty_fails_safely(rates):
    module = _module(rates)

    with pytest.raises(MT5ProviderError, match="MT5_COPY_RATES_EMPTY"):
        _fetch(module)


def test_mt5_position_zero_current_open_candle_is_excluded():
    module = _module(_closed_h1_with_current())

    provider, result = _fetch(module)

    assert len(result) == 3
    assert result["timestamp"].tolist() == [
        pd.Timestamp("2026-08-31 09:00:00"),
        pd.Timestamp("2026-08-31 10:00:00"),
        pd.Timestamp("2026-08-31 11:00:00"),
    ]
    assert pd.Timestamp("2026-08-31 12:00:00") not in set(result["timestamp"])
    assert provider.last_acquisition_metadata["returned_rows"] == 3


def test_mt5_requests_bars_plus_headroom_from_position_zero():
    module = _module(_closed_h1_with_current())

    _provider, _result = _fetch(module, bars=3)

    module.copy_rates_from_pos.assert_called_once_with(
        "EURUSD", module.TIMEFRAME_H1, 0, 3 + MT5_HEADROOM
    )


def test_mt5_insufficient_closed_rows_fails_closed():
    module = _module(_rates([
        "2026-08-31 10:00:00",
        "2026-08-31 11:00:00",
        "2026-08-31 12:00:00",
    ]))

    with pytest.raises(
        MT5DataContractError,
        match="INSUFFICIENT_VALID_BARS_AFTER_SANITIZATION",
    ):
        _fetch(module, bars=3)


def test_mt5_invalid_ohlc_is_sanitized_without_repair():
    module = _module(
        _rates(
            [
                "2026-08-31 08:00:00",
                "2026-08-31 09:00:00",
                "2026-08-31 10:00:00",
                "2026-08-31 11:00:00",
                "2026-08-31 12:00:00",
            ],
            invalid={1},
        )
    )

    provider, result = _fetch(module, bars=3)

    assert len(result) == 3
    metadata = provider.last_acquisition_metadata
    assert metadata["raw_closed_rows"] == 4
    assert metadata["invalid_rows_dropped"] == 1
    assert metadata["valid_rows_before_tail"] == 3
    assert metadata["dropped_rows"][0]["reason"] == "INVALID_OHLC_ENVELOPE"


def test_mt5_insufficient_after_sanitization_fails_closed():
    module = _module(
        _rates(
            [
                "2026-08-31 09:00:00",
                "2026-08-31 10:00:00",
                "2026-08-31 11:00:00",
                "2026-08-31 12:00:00",
            ],
            invalid={1},
        )
    )

    with pytest.raises(
        MT5DataContractError,
        match="INSUFFICIENT_VALID_BARS_AFTER_SANITIZATION",
    ):
        _fetch(module, bars=3)


def test_mt5_duplicate_timestamps_are_rejected():
    module = _module(_rates([
        "2026-08-31 09:00:00",
        "2026-08-31 10:00:00",
        "2026-08-31 10:00:00",
        "2026-08-31 11:00:00",
    ]))

    with pytest.raises(MT5DataContractError, match="TIMESTAMPS_DUPLICATED"):
        _fetch(module)


def test_mt5_out_of_order_timestamps_are_rejected():
    module = _module(_rates([
        "2026-08-31 09:00:00",
        "2026-08-31 11:00:00",
        "2026-08-31 10:00:00",
        "2026-08-31 12:00:00",
    ]))

    with pytest.raises(MT5DataContractError, match="NOT_CHRONOLOGICAL"):
        _fetch(module)


def test_mt5_epoch_seconds_normalize_to_utc_naive():
    module = _module(_closed_h1_with_current())

    _provider, result = _fetch(module)

    assert result["timestamp"].dt.tz is None
    assert result["timestamp"].iloc[0] == pd.Timestamp("2026-08-31 09:00:00")
    assert result["timestamp"].is_monotonic_increasing


@pytest.mark.parametrize(
    ("timeframe", "constant", "timestamps"),
    [
        (
            "H1",
            "TIMEFRAME_H1",
            ["2026-08-31 09:00", "2026-08-31 10:00", "2026-08-31 11:00"],
        ),
        (
            "H4",
            "TIMEFRAME_H4",
            ["2026-08-30 20:00", "2026-08-31 00:00", "2026-08-31 04:00"],
        ),
        (
            "D1",
            "TIMEFRAME_D1",
            ["2026-08-27 00:00", "2026-08-28 00:00", "2026-08-29 00:00"],
        ),
    ],
)
def test_mt5_uses_native_timeframe_constants(timeframe, constant, timestamps):
    module = _module(_rates(timestamps))

    provider, result = _fetch(module, timeframe=timeframe, bars=2)

    assert len(result) == 2
    assert module.copy_rates_from_pos.call_args.args[1] == getattr(module, constant)
    assert provider.last_acquisition_metadata["native_timeframe"] is True


def test_mt5_metadata_is_complete_safe_and_volume_is_tick_volume():
    module = _module(_closed_h1_with_current())

    provider, result = _fetch(module)

    metadata = provider.last_acquisition_metadata
    assert {
        "schema_version",
        "provider",
        "symbol",
        "timeframe",
        "requested_bars",
        "raw_closed_rows",
        "invalid_rows_dropped",
        "valid_rows_before_tail",
        "returned_rows",
        "dropped_rows",
        "native_timeframe",
        "terminal_connected",
        "server",
        "company",
        "trade_mode",
        "mt5_package_version",
        "terminal_build",
        "symbol_external",
        "headroom_requested",
        "volume_provenance",
    } <= set(metadata)
    assert metadata["provider"] == "MT5"
    assert metadata["server"] == "IFCMarkets-Demo"
    assert metadata["symbol_external"] == "EURUSD"
    assert metadata["volume_provenance"] == "MT5_TICK_VOLUME"
    assert result["volume"].iloc[0] == 100
    assert result.attrs["acquisition_metadata"] == metadata
    serialized = json.dumps(metadata, sort_keys=True).lower()
    for prohibited in (
        "123456789",
        "must-never-appear",
        "login",
        "password",
        "balance",
        "equity",
        "account",
    ):
        assert prohibited not in serialized


def test_mt5_allow_fallback_is_deprecated_but_never_calls_yahoo():
    module = _module(None)
    provider = MT5Provider()

    with patch.dict(sys.modules, {"MetaTrader5": module}), patch(
        "forex.data.yahoo_provider.get_yahoo_provider"
    ) as yahoo, pytest.warns(DeprecationWarning, match="provider-pure"), pytest.raises(
        MT5ProviderError, match="MT5_COPY_RATES_EMPTY"
    ):
        provider.fetch("EURUSD", "H1", 3, allow_fallback=True, now=NOW)

    yahoo.assert_not_called()


class ProviderDouble:
    def __init__(self, result=None, *, available=True, error=None):
        self.result = result
        self.available = available
        self.error = error
        self.calls = []
        self.last_acquisition_metadata = None

    def is_available(self):
        return self.available

    def fetch(self, pair, timeframe, bars, **kwargs):
        self.calls.append((pair, timeframe, bars, kwargs))
        if self.error:
            raise self.error
        return None if self.result is None else self.result.copy()


def _provider_frame(marker: float) -> pd.DataFrame:
    values = pd.Series([marker, marker + 0.001, marker + 0.002])
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=3, freq="h"),
        "open": values,
        "high": values + 0.0005,
        "low": values - 0.0005,
        "close": values + 0.0002,
        "volume": [100, 100, 100],
        "pair": "EURUSD",
    })


def _router_patches(mt5, oanda, yahoo):
    return (
        patch("forex.data.mt5_provider.get_mt5_provider", return_value=mt5),
        patch("forex.data.oanda_provider.get_oanda_provider", return_value=oanda),
        patch("forex.data.yahoo_provider.get_yahoo_provider", return_value=yahoo),
    )


def test_router_mt5_success_does_not_call_oanda_or_yahoo():
    mt5 = ProviderDouble(_provider_frame(1.0))
    oanda = ProviderDouble(_provider_frame(2.0))
    yahoo = ProviderDouble(_provider_frame(3.0))
    patches = _router_patches(mt5, oanda, yahoo)

    with patches[0], patches[1], patches[2]:
        router = DataRouter("EURUSD", "H1")
        result = router.fetch(3, raise_on_failure=True)

    assert router.source_used == "MT5"
    assert result["open"].iloc[0] == 1.0
    assert oanda.calls == []
    assert yahoo.calls == []


def test_router_mt5_failure_proceeds_to_oanda():
    mt5 = ProviderDouble(error=MT5ProviderError("MT5_COPY_RATES_FAILURE"))
    oanda = ProviderDouble(_provider_frame(2.0))
    yahoo = ProviderDouble(_provider_frame(3.0))
    patches = _router_patches(mt5, oanda, yahoo)

    with patches[0], patches[1], patches[2]:
        router = DataRouter("EURUSD", "H1")
        result = router.fetch(3, raise_on_failure=True)

    assert router.source_used == "OANDA"
    assert result["open"].iloc[0] == 2.0
    assert len(mt5.calls) == len(oanda.calls) == 1
    assert yahoo.calls == []


def test_router_never_mixes_mt5_and_oanda_rows():
    mt5 = ProviderDouble(result=None)
    oanda_frame = _provider_frame(2.0)
    oanda = ProviderDouble(oanda_frame)
    yahoo = ProviderDouble(_provider_frame(3.0))
    patches = _router_patches(mt5, oanda, yahoo)

    with patches[0], patches[1], patches[2]:
        router = DataRouter("EURUSD", "H1")
        result = router.fetch(3, raise_on_failure=True)

    pd.testing.assert_frame_equal(result.reset_index(drop=True), oanda_frame)
    assert (result["open"] >= 2.0).all()
    assert yahoo.calls == []


def test_windows_forex_requirement_is_optional_and_documented():
    requirement = Path("requirements-forex-windows.txt").read_text(encoding="utf-8")
    production = Path("requirements.txt").read_text(encoding="utf-8")
    core = Path("requirements-core.txt").read_text(encoding="utf-8")
    manual = Path("MANUAL.md").read_text(encoding="utf-8")

    assert "MetaTrader5" in requirement
    assert "Windows" in requirement
    assert 'platform_system == "Windows"' in requirement
    assert "MetaTrader5" not in production
    assert "MetaTrader5" not in core
    assert "requirements-forex-windows.txt" in manual
    assert "MetaTrader 5 terminal" in manual

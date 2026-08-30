"""Regression tests for provenance-bound MT5 server-time normalization."""
from __future__ import annotations

import json
import sys
import types
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from forex.data.data_router import DataRouter
from forex.data.mt5_provider import (
    MT5DataContractError,
    MT5Provider,
)


pytestmark = pytest.mark.unit


def _server_rate(wall_time: str, index: int = 0) -> dict:
    opened = 1.10 + index * 0.0001
    return {
        # Preserve server wall-clock digits in the epoch-like MT5 integer.
        "time": int(pd.Timestamp(wall_time, tz="UTC").timestamp()),
        "open": opened,
        "high": opened + 0.0005,
        "low": opened - 0.0005,
        "close": opened + 0.0002,
        "tick_volume": 100 + index,
    }


def _module(
    wall_times: list[str], *, server: str = "IFCMarkets-Demo"
) -> types.ModuleType:
    module = types.ModuleType("MetaTrader5")
    module.__version__ = "5.0.time-contract-test"
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
            server=server,
            company="IFC Markets",
            trade_mode=0,
            balance=999999.0,
            equity=999999.0,
            password="must-never-appear",
        )
    )
    module.symbol_info = Mock(return_value=SimpleNamespace(visible=True))
    module.symbol_select = Mock(return_value=True)
    module.copy_rates_from_pos = Mock(
        return_value=[
            _server_rate(wall_time, index)
            for index, wall_time in enumerate(wall_times)
        ]
    )
    return module


def _fetch(
    module: types.ModuleType,
    *,
    timeframe: str = "H1",
    bars: int | None = None,
    now: str = "2027-01-01 00:00:00+00:00",
):
    requested = len(module.copy_rates_from_pos.return_value) if bars is None else bars
    provider = MT5Provider()
    with patch.dict(sys.modules, {"MetaTrader5": module}):
        result = provider.fetch(
            "EURUSD", timeframe, requested, now=pd.Timestamp(now)
        )
    return provider, result


def test_ifc_summer_server_wall_time_converts_to_utc_with_cest():
    module = _module(["2026-08-21 21:00", "2026-08-24 00:00"])

    _provider, result = _fetch(module)

    assert result["timestamp"].tolist() == [
        pd.Timestamp("2026-08-21 19:00"),
        pd.Timestamp("2026-08-23 22:00"),
    ]
    assert result["timestamp"].iloc[0] != pd.Timestamp("2026-08-21 21:00")


def test_ifc_winter_server_wall_time_converts_to_utc_with_cet():
    module = _module(["2025-12-24 16:00"])

    _provider, result = _fetch(module)

    assert result["timestamp"].tolist() == [pd.Timestamp("2025-12-24 15:00")]


@pytest.mark.parametrize(
    ("wall_time", "error_code"),
    [
        ("2026-10-25 02:30", "MT5_CANDLE_TIMESTAMP_AMBIGUOUS"),
        ("2026-03-29 02:30", "MT5_CANDLE_TIMESTAMP_NONEXISTENT"),
    ],
)
def test_ifc_dst_ambiguous_or_nonexistent_time_fails_closed(
    wall_time, error_code
):
    module = _module([wall_time])

    with pytest.raises(MT5DataContractError, match=error_code):
        _fetch(module)


def test_unknown_mt5_server_clock_profile_fails_before_copying_rates():
    module = _module(["2026-08-21 21:00"], server="Unknown-Broker-Demo")

    with pytest.raises(
        MT5DataContractError, match="MT5_SERVER_CLOCK_PROFILE_UNKNOWN"
    ):
        _fetch(module)

    module.copy_rates_from_pos.assert_not_called()


def test_cest_closed_candle_is_retained_and_current_candle_is_removed():
    module = _module([
        "2026-08-21 20:00",
        "2026-08-21 21:00",
        "2026-08-21 22:00",
    ])

    _provider, result = _fetch(
        module,
        bars=2,
        now="2026-08-21 20:30:00+00:00",
    )

    assert result["timestamp"].tolist() == [
        pd.Timestamp("2026-08-21 18:00"),
        pd.Timestamp("2026-08-21 19:00"),
    ]
    assert pd.Timestamp("2026-08-21 20:00") not in set(result["timestamp"])


def test_ifc_timezone_metadata_is_provenance_bound_and_secret_free():
    module = _module(["2026-08-21 21:00"])

    provider, result = _fetch(module)

    metadata = provider.last_acquisition_metadata
    assert metadata == result.attrs["acquisition_metadata"]
    assert metadata["timestamp_source_domain"] == "MT5_SERVER_TIME"
    assert metadata["source_timezone"] == "Europe/Berlin"
    assert metadata["timezone_profile_id"] == "ifcmarkets-demo-europe-berlin"
    assert metadata["timezone_profile_version"] == 1
    assert metadata["timezone_evidence_hash"] == (
        "00ad79892885f8034eb37f01eceede35"
        "5b43486cbca18b9b69c45f87f8eed331"
    )
    assert metadata["timezone_authority_type"] == (
        "BROKER_DOCUMENTATION_AND_LIVE_TERMINAL"
    )
    assert metadata["timezone_source_identity"] == (
        "IFC_MARKETS_PLATFORM_CET_CEST_AND_TERMINAL_AUDIT_2026_08_30"
    )
    assert metadata["timestamp_normalization"] == "SERVER_WALL_TIME_TO_UTC"
    assert metadata["observed_server"] == "IFCMarkets-Demo"
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


def test_router_falls_back_to_oanda_when_mt5_clock_profile_is_unknown():
    module = _module(["2026-08-21 21:00"], server="Unknown-Broker-Demo")
    oanda_frame = pd.DataFrame({
        "timestamp": [pd.Timestamp("2026-08-21 19:00")],
        "open": [1.1],
        "high": [1.2],
        "low": [1.0],
        "close": [1.15],
        "volume": [100],
        "pair": ["EURUSD"],
    })
    oanda = SimpleNamespace(
        is_available=Mock(return_value=True),
        fetch=Mock(return_value=oanda_frame),
        last_acquisition_metadata=None,
    )
    yahoo = SimpleNamespace(
        is_available=Mock(return_value=True),
        fetch=Mock(side_effect=AssertionError("Yahoo must not be called")),
        last_acquisition_metadata=None,
    )
    mt5_provider = MT5Provider()

    with patch.dict(sys.modules, {"MetaTrader5": module}), patch(
        "forex.data.mt5_provider.get_mt5_provider", return_value=mt5_provider
    ), patch(
        "forex.data.oanda_provider.get_oanda_provider", return_value=oanda
    ), patch(
        "forex.data.yahoo_provider.get_yahoo_provider", return_value=yahoo
    ):
        router = DataRouter("EURUSD", "H1")
        result = router.fetch(1, raise_on_failure=True)

    assert router.source_used == "OANDA"
    assert result.equals(oanda_frame)
    assert "MT5_SERVER_CLOCK_PROFILE_UNKNOWN" in router.attempt_errors[0]
    oanda.fetch.assert_called_once()
    yahoo.fetch.assert_not_called()

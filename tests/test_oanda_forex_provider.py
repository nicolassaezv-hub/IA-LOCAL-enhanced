"""OANDA v20 Forex provider, catalog routing, and fail-closed fallback tests."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from forex.data.data_router import DataRouter
from forex.data.oanda_provider import (
    OANDAAuthenticationError,
    OANDADataContractError,
    OANDAProvider,
)
from forex.data.rolling_dataset import ROLLING_WINDOW, RollingDataset
from forex.data.symbol_catalog import (
    CATALOG_VERSION,
    SYMBOL_CATALOG,
    provider_routes,
    route_for_provider,
)
from scripts.validate_symbol_universe import route_spec, validate_dataset_frame


pytestmark = pytest.mark.unit

BASELINE_CATALOG_VERSION = (
    "6f2a7b3f0266099c311dcbb3defa55981e12483ed7c2766104f5b44ccef1a855"
)
TOKEN = "unit-test-token"
ACCOUNT = "unit-test-account"


class Response:
    def __init__(self, payload=None, *, status_code=200, headers=None):
        self._payload = payload if payload is not None else {"candles": []}
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._payload


def _candle(
    timestamp: pd.Timestamp,
    index: int,
    *,
    complete: bool = True,
    invalid: bool = False,
) -> dict:
    base = 1.05 + index * 0.00001
    high = base + 0.0004
    close = base + 0.0001
    if invalid:
        close = high + 1.0
    return {
        "time": timestamp.isoformat().replace("+00:00", "Z"),
        "complete": complete,
        "volume": 100 + index,
        "mid": {
            "o": str(base),
            "h": str(high),
            "l": str(base - 0.0004),
            "c": str(close),
        },
    }


def _payload(
    count: int,
    *,
    start: str = "2025-01-01T00:00:00Z",
    freq: str = "h",
    incomplete: set[int] | None = None,
    invalid: set[int] | None = None,
) -> dict:
    timestamps = pd.date_range(start, periods=count, freq=freq)
    return {
        "candles": [
            _candle(
                timestamp,
                index,
                complete=index not in (incomplete or set()),
                invalid=index in (invalid or set()),
            )
            for index, timestamp in enumerate(timestamps)
        ]
    }


def _provider(environment: str = "practice") -> OANDAProvider:
    environment_values = {
        "OANDA_API_TOKEN": TOKEN,
        "OANDA_ACCOUNT_ID": ACCOUNT,
        "OANDA_ENVIRONMENT": environment,
    }
    with patch.dict("os.environ", environment_values, clear=False):
        return OANDAProvider()


def _frame(count: int, *, marker: float = 1.0) -> pd.DataFrame:
    timestamps = pd.date_range("2025-01-01", periods=count, freq="h")
    values = marker + np.arange(count, dtype=float) * 0.00001
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": values,
        "high": values + 0.0004,
        "low": values - 0.0004,
        "close": values + 0.0001,
        "volume": np.full(count, 100.0),
        "pair": "EURUSD",
    })


class ProviderDouble:
    def __init__(self, result=None, *, available=True, error=None, source="test"):
        self.result = result
        self.available = available
        self.error = error
        self.calls = []
        self.last_acquisition_metadata = None
        if isinstance(result, pd.DataFrame):
            self.last_acquisition_metadata = {
                "schema_version": 1,
                "provider": source,
                "symbol": "EURUSD",
                "timeframe": "H1",
                "requested_bars": len(result),
                "raw_closed_rows": len(result),
                "invalid_rows_dropped": 0,
                "valid_rows_before_tail": len(result),
                "returned_rows": len(result),
                "dropped_rows": [],
            }

    def is_available(self):
        return self.available

    def fetch(self, pair, timeframe, bars, **kwargs):
        self.calls.append((pair, timeframe, bars, kwargs))
        if self.error:
            raise self.error
        return None if self.result is None else self.result.copy()


def test_oanda_credentials_absent_is_unavailable():
    with patch.dict("os.environ", {}, clear=True):
        provider = OANDAProvider()

    assert provider.is_available() is False


def test_invalid_oanda_environment_is_unavailable():
    with patch.dict(
        "os.environ",
        {
            "OANDA_API_TOKEN": TOKEN,
            "OANDA_ACCOUNT_ID": ACCOUNT,
            "OANDA_ENVIRONMENT": "arbitrary",
        },
        clear=True,
    ):
        provider = OANDAProvider()

    assert provider.is_available() is False


@pytest.mark.parametrize(
    ("environment", "expected_base"),
    [
        ("practice", "https://api-fxpractice.oanda.com"),
        ("live", "https://api-fxtrade.oanda.com"),
    ],
)
def test_oanda_uses_fixed_official_environment_url(environment, expected_base):
    provider = _provider(environment)
    response = Response(_payload(3))

    with patch("requests.get", return_value=response) as request:
        provider.fetch("EURUSD", "H1", bars=2)

    assert request.call_args.args[0] == (
        f"{expected_base}/v3/accounts/{ACCOUNT}/instruments/EUR_USD/candles"
    )


def test_oanda_bearer_is_internal_and_never_persisted():
    provider = _provider()
    response = Response(_payload(3), headers={"RequestID": "request-123"})

    with patch("requests.get", return_value=response) as request:
        provider.fetch("EURUSD", "H1", bars=2)

    assert request.call_args.kwargs["headers"]["Authorization"] == f"Bearer {TOKEN}"
    serialized = json.dumps(provider.last_acquisition_metadata, sort_keys=True)
    assert TOKEN not in serialized
    assert ACCOUNT not in serialized
    assert provider.last_acquisition_metadata["request_id"] == "request-123"


@pytest.mark.parametrize(
    ("timeframe", "granularity"),
    [("H1", "H1"), ("H4", "H4"), ("D1", "D")],
)
def test_oanda_timeframes_are_native(timeframe, granularity):
    provider = _provider()
    response = Response(_payload(3, freq={"H1": "h", "H4": "4h", "D1": "D"}[timeframe]))

    with patch("requests.get", return_value=response) as request:
        provider.fetch("EURUSD", timeframe, bars=2)

    params = request.call_args.kwargs["params"]
    assert params["granularity"] == granularity
    assert params["price"] == "M"
    assert params["smooth"] == "false"
    assert params["alignmentTimezone"] == "America/New_York"
    assert params["dailyAlignment"] == 17
    assert provider.last_acquisition_metadata["native_timeframe"] is True


def test_oanda_excludes_incomplete_and_returns_exact_bars_after_headroom():
    provider = _provider()
    response = Response(_payload(4, incomplete={3}))

    with patch("requests.get", return_value=response) as request:
        result = provider.fetch("EURUSD", "H1", bars=3)

    assert len(result) == 3
    assert request.call_args.kwargs["params"]["count"] > 3
    assert provider.last_acquisition_metadata["returned_rows"] == 3


def test_oanda_sanitizes_invalid_ohlc_without_repairing_it():
    provider = _provider()
    response = Response(_payload(4, invalid={1}))

    with patch("requests.get", return_value=response):
        result = provider.fetch("EURUSD", "H1", bars=3)

    metadata = provider.last_acquisition_metadata
    assert len(result) == 3
    assert metadata["raw_closed_rows"] == 4
    assert metadata["invalid_rows_dropped"] == 1
    assert metadata["valid_rows_before_tail"] == 3
    assert metadata["dropped_rows"][0]["reason"] == "INVALID_OHLC_ENVELOPE"


def test_oanda_insufficient_valid_bars_fails_closed():
    provider = _provider()
    response = Response(_payload(3, invalid={1}))

    with patch("requests.get", return_value=response), pytest.raises(
        OANDADataContractError,
        match="INSUFFICIENT_VALID_BARS_AFTER_SANITIZATION",
    ):
        provider.fetch("EURUSD", "H1", bars=3)

    assert provider.last_acquisition_metadata["returned_rows"] == 2


def test_oanda_timestamps_are_normalized_to_utc_contract():
    provider = _provider()
    payload = _payload(2)
    payload["candles"][0]["time"] = "2025-01-01T02:00:00+02:00"

    with patch("requests.get", return_value=Response(payload)):
        result = provider.fetch("EURUSD", "H1", bars=2)

    assert result["timestamp"].iloc[0] == pd.Timestamp("2025-01-01T00:00:00")
    assert result["timestamp"].dt.tz is None
    assert result["timestamp"].is_monotonic_increasing


def test_oanda_metadata_is_complete_and_non_sensitive():
    provider = _provider("practice")

    with patch("requests.get", return_value=Response(_payload(3))):
        provider.fetch("EURUSD", "H4", bars=2)

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
        "external_instrument",
        "granularity",
        "price_component",
        "environment",
        "alignment_timezone",
        "daily_alignment",
        "native_timeframe",
    } <= set(metadata)
    assert metadata["provider"] == "OANDA"
    assert metadata["external_instrument"] == "EUR_USD"
    assert metadata["granularity"] == "H4"
    assert metadata["price_component"] == "M"
    assert "token" not in json.dumps(metadata).lower()
    assert ACCOUNT not in json.dumps(metadata)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "OANDA_AUTHENTICATION_FAILURE"),
        (403, "OANDA_AUTHENTICATION_FAILURE"),
        (404, "OANDA_INSTRUMENT_OR_ACCOUNT_ROUTE_FAILURE"),
        (429, "OANDA_RATE_LIMIT"),
        (500, "OANDA_PROVIDER_FAILURE"),
    ],
)
def test_oanda_http_errors_are_explicit_and_sanitized(status, expected):
    provider = _provider()

    with patch("requests.get", return_value=Response(status_code=status)), pytest.raises(
        Exception, match=expected
    ) as error:
        provider.fetch("EURUSD", "H1", bars=2)

    assert TOKEN not in str(error.value)
    assert ACCOUNT not in str(error.value)


def test_oanda_network_error_cannot_expose_request_credentials():
    import requests

    provider = _provider()
    unsafe_message = f"request failed for {ACCOUNT} using {TOKEN}"

    with patch(
        "requests.get", side_effect=requests.ConnectionError(unsafe_message)
    ), pytest.raises(Exception, match="OANDA_PROVIDER_FAILURE") as error:
        provider.fetch("EURUSD", "H1", bars=2)

    assert TOKEN not in str(error.value)
    assert ACCOUNT not in str(error.value)


def test_catalog_declares_ordered_forex_routes_and_preserves_other_assets():
    assert [route.provider for route in provider_routes("EURUSD")] == [
        "MT5",
        "OANDA",
        "Yahoo",
    ]
    assert [route.provider for route in provider_routes("USDJPY")] == [
        "MT5",
        "OANDA",
        "Yahoo",
    ]
    assert [route.provider for route in provider_routes("BTCUSDT")] == ["Binance"]
    assert [route.provider for route in provider_routes("XAUUSD")] == ["MT5"]
    assert [route.provider for route in provider_routes("SPX500")] == [
        "MT5",
        "Yahoo",
    ]
    assert route_for_provider("EURUSD", "OANDA").external_ticker == "EUR_USD"
    assert route_for_provider("USDJPY", "OANDA").external_ticker == "USD_JPY"
    assert route_for_provider("XAUUSD", "OANDA") is None
    reported = route_spec("EURUSD")
    assert reported.provider_secondary == "OANDA"
    assert reported.secondary_external_ticker == "EUR_USD"


def test_catalog_version_changes_deterministically_with_oanda_routes():
    payload = [asdict(spec) for spec in SYMBOL_CATALOG.values()]
    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    assert CATALOG_VERSION == expected
    assert CATALOG_VERSION != BASELINE_CATALOG_VERSION


def _router_patches(mt5, oanda, yahoo):
    return (
        patch("forex.data.mt5_provider.get_mt5_provider", return_value=mt5),
        patch("forex.data.oanda_provider.get_oanda_provider", return_value=oanda),
        patch("forex.data.yahoo_provider.get_yahoo_provider", return_value=yahoo),
    )


def test_router_uses_oanda_after_mt5_and_does_not_call_yahoo():
    mt5 = ProviderDouble(available=False)
    oanda = ProviderDouble(_frame(3, marker=2.0), source="OANDA")
    yahoo = ProviderDouble(_frame(3, marker=3.0), source="Yahoo")
    patches = _router_patches(mt5, oanda, yahoo)

    with patches[0], patches[1], patches[2]:
        router = DataRouter("EURUSD", "H1")
        result = router.fetch(3, raise_on_failure=True)

    assert router.source_used == "OANDA"
    assert route_for_provider("EURUSD", "OANDA") == router.route_used
    assert result["open"].iloc[0] == 2.0
    assert len(oanda.calls) == 1
    assert yahoo.calls == []


def test_router_uses_yahoo_when_mt5_and_oanda_are_unavailable():
    mt5 = ProviderDouble(available=False)
    oanda = ProviderDouble(available=False)
    yahoo = ProviderDouble(_frame(3, marker=3.0), source="Yahoo")
    patches = _router_patches(mt5, oanda, yahoo)

    with patches[0], patches[1], patches[2]:
        router = DataRouter("EURUSD", "H1")
        result = router.fetch(3, raise_on_failure=True)

    assert router.source_used == "Yahoo"
    assert result["open"].iloc[0] == 3.0
    assert router.attempt_errors[:2] == ("MT5 unavailable", "OANDA unavailable")


def test_router_continues_after_oanda_auth_failure_without_leaking_secret():
    mt5 = ProviderDouble(available=False)
    oanda = ProviderDouble(error=OANDAAuthenticationError("OANDA_AUTHENTICATION_FAILURE"))
    yahoo = ProviderDouble(_frame(3, marker=3.0), source="Yahoo")
    patches = _router_patches(mt5, oanda, yahoo)

    with patches[0], patches[1], patches[2]:
        router = DataRouter("EURUSD", "H1")
        result = router.fetch(3, raise_on_failure=True)

    assert router.source_used == "Yahoo"
    assert len(result) == 3
    assert any("OANDA_AUTHENTICATION_FAILURE" in item for item in router.attempt_errors)
    assert all(TOKEN not in item for item in router.attempt_errors)


def test_router_continues_after_oanda_data_contract_failure():
    mt5 = ProviderDouble(available=False)
    oanda = ProviderDouble(error=OANDADataContractError("bad OANDA candles"))
    yahoo = ProviderDouble(_frame(3, marker=3.0), source="Yahoo")
    patches = _router_patches(mt5, oanda, yahoo)

    with patches[0], patches[1], patches[2]:
        router = DataRouter("EURUSD", "H1")
        result = router.fetch(3, raise_on_failure=True)

    assert router.source_used == "Yahoo"
    assert len(result) == 3
    assert any("bad OANDA candles" in item for item in router.attempt_errors)


def test_router_fallback_is_whole_dataset_never_row_level_merge():
    mt5 = ProviderDouble(available=False)
    oanda = ProviderDouble(result=None)
    yahoo_frame = _frame(2001, marker=3.0)
    yahoo = ProviderDouble(yahoo_frame, source="Yahoo")
    patches = _router_patches(mt5, oanda, yahoo)

    with patches[0], patches[1], patches[2]:
        router = DataRouter("EURUSD", "H1")
        result = router.fetch(2001, raise_on_failure=True)

    pd.testing.assert_frame_equal(result.reset_index(drop=True), yahoo_frame)
    assert router.source_used == "Yahoo"
    assert (result["open"] >= 3.0).all()


def test_oanda_dataset_passes_router_rolling_and_qualification_contract(tmp_path):
    mt5 = ProviderDouble(available=False)
    oanda = _provider()
    yahoo = ProviderDouble(error=AssertionError("Yahoo must not be called"))
    response = Response(_payload(2002, incomplete={2001}))
    patches = _router_patches(mt5, oanda, yahoo)

    with patches[0], patches[1], patches[2], patch(
        "requests.get", return_value=response
    ):
        router = DataRouter("EURUSD", "H1")
        acquired = router.fetch(2001, raise_on_failure=True)

    path = tmp_path / "EURUSD_H1.csv"
    RollingDataset("EURUSD", "H1", csv_path=path).apply(
        acquired, include_existing=False, now="2030-01-01"
    )
    artifact = pd.read_csv(path)
    stage, validated = validate_dataset_frame(
        artifact,
        "EURUSD",
        "H1",
        now="2030-01-01",
        acquisition_metadata=router.last_acquisition_metadata,
        provider="OANDA",
    )

    assert router.source_used == "OANDA"
    assert router.route_used.provider_class == "BROKER_REST"
    assert len(acquired) == 2001
    assert len(artifact) == ROLLING_WINDOW
    assert validated is not None
    assert stage["blocking"] is False
    assert stage["details"]["acquisition_metadata"]["provider"] == "OANDA"
    assert yahoo.calls == []


def test_validation_rejects_cross_provider_metadata_claim(tmp_path):
    frame = _frame(2001)
    path = tmp_path / "EURUSD_H1.csv"
    RollingDataset("EURUSD", "H1", csv_path=path).apply(
        frame, include_existing=False, now="2030-01-01"
    )
    artifact = pd.read_csv(path)
    metadata = {
        "schema_version": 1,
        "provider": "Yahoo",
        "symbol": "EURUSD",
        "timeframe": "H1",
        "requested_bars": 2001,
        "raw_closed_rows": 2001,
        "invalid_rows_dropped": 0,
        "valid_rows_before_tail": 2001,
        "returned_rows": 2001,
        "dropped_rows": [],
    }

    stage, _validated = validate_dataset_frame(
        artifact,
        "EURUSD",
        "H1",
        now="2030-01-01",
        acquisition_metadata=metadata,
        provider="OANDA",
    )

    assert stage["blocking"] is True
    assert any("does not match OANDA" in error for error in stage["errors"])


def test_env_example_contains_only_empty_oanda_credentials():
    content = Path("env.example").read_text(encoding="utf-8")

    assert "OANDA_API_TOKEN=" in content
    assert "OANDA_ACCOUNT_ID=" in content
    assert "OANDA_ENVIRONMENT=practice" in content

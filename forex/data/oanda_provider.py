"""OANDA v20 REST provider for complete native Forex candles."""
from __future__ import annotations

import copy
import os
from typing import Any, Optional

import numpy as np
import pandas as pd

from forex.data.ohlc_contract import sanitize_ohlc_frame, validate_ohlc_frame
from forex.data.rolling_dataset import exclude_incomplete_candles
from forex.data.symbol_catalog import route_for_provider


_BASE_URLS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}
_GRANULARITIES = {"H1": "H1", "H4": "H4", "D1": "D"}
_MAX_CANDLES = 5000
_HEADROOM = 2
_TIMEOUT_SECONDS = 15


class OANDAProviderError(RuntimeError):
    """Raised when OANDA cannot complete a safe provider request."""


class OANDAAuthenticationError(OANDAProviderError):
    """Raised for rejected OANDA credentials without exposing them."""


class OANDADataContractError(OANDAProviderError):
    """Raised when the response cannot satisfy ASTRA's candle contract."""


def _safe_http_error(status_code: int) -> OANDAProviderError:
    if status_code in {401, 403}:
        return OANDAAuthenticationError("OANDA_AUTHENTICATION_FAILURE")
    if status_code == 404:
        return OANDAProviderError(
            "OANDA_INSTRUMENT_OR_ACCOUNT_ROUTE_FAILURE"
        )
    if status_code == 429:
        return OANDAProviderError("OANDA_RATE_LIMIT")
    if status_code >= 500:
        return OANDAProviderError(
            f"OANDA_PROVIDER_FAILURE status={status_code}"
        )
    return OANDAProviderError(f"OANDA_HTTP_FAILURE status={status_code}")


def _normalize_candles(candles: list[dict], pair: str) -> pd.DataFrame:
    rows = []
    for candle in candles:
        mid = candle.get("mid") if isinstance(candle, dict) else None
        if not isinstance(mid, dict):
            raise OANDADataContractError("OANDA_CANDLE_MID_COMPONENT_MISSING")
        rows.append({
            "timestamp": candle.get("time"),
            "open": mid.get("o"),
            "high": mid.get("h"),
            "low": mid.get("l"),
            "close": mid.get("c"),
            "volume": candle.get("volume"),
            "pair": pair.upper(),
        })
    frame = pd.DataFrame(
        rows,
        columns=(
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "pair",
        ),
    )
    parsed = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    if parsed.isna().any():
        raise OANDADataContractError("OANDA_CANDLE_TIMESTAMP_INVALID")
    frame["timestamp"] = parsed.dt.tz_localize(None)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    volume = frame["volume"].to_numpy(float)
    if not np.isfinite(volume).all() or (volume < 0).any():
        raise OANDADataContractError("OANDA_CANDLE_VOLUME_INVALID")
    if frame["timestamp"].duplicated().any():
        raise OANDADataContractError("OANDA_CANDLE_TIMESTAMPS_DUPLICATED")
    if not frame["timestamp"].is_monotonic_increasing:
        raise OANDADataContractError("OANDA_CANDLES_NOT_CHRONOLOGICAL")
    return frame


class OANDAProvider:
    """Fetch one coherent MID-price dataset from OANDA's v20 REST API."""

    def __init__(self):
        self._token = os.environ.get("OANDA_API_TOKEN", "").strip()
        self._account_id = os.environ.get("OANDA_ACCOUNT_ID", "").strip()
        self._environment = os.environ.get(
            "OANDA_ENVIRONMENT", "practice"
        ).strip().lower()
        self._last_acquisition_metadata: Optional[dict] = None

    @property
    def last_acquisition_metadata(self) -> Optional[dict]:
        return copy.deepcopy(self._last_acquisition_metadata)

    def is_available(self) -> bool:
        if (
            not self._token
            or not self._account_id
            or self._environment not in _BASE_URLS
        ):
            return False
        try:
            import requests  # noqa: F401
        except ImportError:
            return False
        return True

    def _metadata(
        self,
        *,
        pair: str,
        timeframe: str,
        instrument: str,
        granularity: str,
        requested_bars: int,
        raw_closed_rows: int,
        valid_rows_before_tail: int,
        returned_rows: int,
        dropped_rows: list[dict],
        request_id: str | None,
    ) -> dict:
        metadata = {
            "schema_version": 1,
            "provider": "OANDA",
            "symbol": pair.upper(),
            "timeframe": timeframe.upper(),
            "requested_bars": int(requested_bars),
            "raw_closed_rows": int(raw_closed_rows),
            "invalid_rows_dropped": int(len(dropped_rows)),
            "valid_rows_before_tail": int(valid_rows_before_tail),
            "returned_rows": int(returned_rows),
            "dropped_rows": dropped_rows,
            "external_instrument": instrument,
            "granularity": granularity,
            "price_component": "M",
            "environment": self._environment,
            "alignment_timezone": "America/New_York",
            "daily_alignment": 17,
            "native_timeframe": True,
        }
        if request_id:
            metadata["request_id"] = str(request_id)
        return metadata

    def fetch(
        self,
        pair: str,
        tf: str = "H1",
        bars: int = 500,
    ) -> Optional[pd.DataFrame]:
        self._last_acquisition_metadata = None
        if not self.is_available():
            return None
        timeframe = tf.upper()
        granularity = _GRANULARITIES.get(timeframe)
        if granularity is None:
            raise OANDADataContractError(
                f"OANDA_TIMEFRAME_UNSUPPORTED: {timeframe}"
            )
        requested = int(bars)
        if requested <= 0 or requested > _MAX_CANDLES:
            raise OANDADataContractError(
                f"OANDA_REQUESTED_BARS_OUT_OF_RANGE: {requested}"
            )
        route = route_for_provider(pair, "OANDA")
        if route is None:
            raise OANDADataContractError(
                f"OANDA_INSTRUMENT_NOT_CATALOGUED: {str(pair).upper()}"
            )

        import requests

        url = (
            f"{_BASE_URLS[self._environment]}/v3/accounts/"
            f"{self._account_id}/instruments/{route.external_ticker}/candles"
        )
        params = {
            "price": "M",
            "granularity": granularity,
            "count": min(requested + _HEADROOM, _MAX_CANDLES),
            "smooth": "false",
            "alignmentTimezone": "America/New_York",
            "dailyAlignment": 17,
        }
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=_TIMEOUT_SECONDS,
            )
        except requests.Timeout:
            raise OANDAProviderError("OANDA_PROVIDER_TIMEOUT") from None
        except requests.RequestException:
            raise OANDAProviderError("OANDA_PROVIDER_FAILURE") from None
        if response.status_code >= 400:
            raise _safe_http_error(int(response.status_code))
        try:
            payload: Any = response.json()
        except Exception:
            raise OANDAProviderError("OANDA_RESPONSE_JSON_INVALID") from None
        candles = payload.get("candles") if isinstance(payload, dict) else None
        if not isinstance(candles, list):
            raise OANDADataContractError("OANDA_CANDLES_PAYLOAD_INVALID")
        completed = [
            candle
            for candle in candles
            if isinstance(candle, dict) and candle.get("complete") is True
        ]
        if not completed:
            raise OANDADataContractError("OANDA_NO_COMPLETE_CANDLES")

        normalized = _normalize_candles(completed, pair)
        closed = exclude_incomplete_candles(normalized, timeframe)
        raw_closed_rows = len(closed)
        valid, dropped = sanitize_ohlc_frame(closed)
        validate_ohlc_frame(valid)
        returned_rows = min(len(valid), requested)
        request_id = response.headers.get("RequestID") or response.headers.get(
            "requestID"
        )
        self._last_acquisition_metadata = self._metadata(
            pair=pair,
            timeframe=timeframe,
            instrument=route.external_ticker,
            granularity=granularity,
            requested_bars=requested,
            raw_closed_rows=raw_closed_rows,
            valid_rows_before_tail=len(valid),
            returned_rows=returned_rows,
            dropped_rows=dropped,
            request_id=request_id,
        )
        if len(valid) < requested:
            raise OANDADataContractError(
                "INSUFFICIENT_VALID_BARS_AFTER_SANITIZATION: "
                f"{str(pair).upper()}/{timeframe} requested={requested} "
                f"valid={len(valid)} raw_closed={raw_closed_rows} "
                f"dropped={len(dropped)}"
            )
        result = valid.tail(requested).reset_index(drop=True)
        result.attrs["acquisition_metadata"] = self.last_acquisition_metadata
        return result


_provider = OANDAProvider()


def get_oanda_provider() -> OANDAProvider:
    return _provider


__all__ = [
    "OANDAAuthenticationError",
    "OANDADataContractError",
    "OANDAProvider",
    "OANDAProviderError",
    "get_oanda_provider",
]

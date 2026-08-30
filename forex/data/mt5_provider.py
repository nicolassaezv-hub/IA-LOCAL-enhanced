"""Fail-closed MetaTrader 5 provider for native Forex candles on Windows."""
from __future__ import annotations

import copy
import warnings
from typing import Any, Optional

import numpy as np
import pandas as pd

from forex.data.ohlc_contract import (
    OHLCContractError,
    sanitize_ohlc_frame,
    validate_ohlc_frame,
)
from forex.data.mt5_clock_profiles import (
    MT5ServerClockProfile,
    resolve_mt5_server_clock_profile,
)
from forex.data.rolling_dataset import exclude_incomplete_candles
from forex.data.symbol_catalog import route_for_provider


MT5_HEADROOM = 10
_TIMEFRAME_CONSTANTS = {
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
}


class MT5ProviderError(RuntimeError):
    """Raised when MT5 cannot provide a safe, coherent acquisition."""


class MT5UnavailableError(MT5ProviderError):
    """Raised when the Windows-only Python package is unavailable."""


class MT5InitializationError(MT5ProviderError):
    """Raised when the terminal or connected account is unavailable."""


class MT5SymbolError(MT5ProviderError):
    """Raised when the exact catalog symbol cannot be selected."""


class MT5DataContractError(MT5ProviderError):
    """Raised when returned rates violate ASTRA's dataset contract."""


def _is_mt5_available() -> bool:
    try:
        import MetaTrader5  # noqa: F401
    except (ImportError, ModuleNotFoundError):
        return False
    return True


def _last_error_code(mt5: Any) -> str:
    """Return only the numeric code; provider messages may contain account data."""
    try:
        error = mt5.last_error()
        code = error[0] if isinstance(error, (tuple, list)) and error else error
        return f" last_error_code={int(code)}"
    except Exception:
        return ""


def _normalize_mt5_df(
    rates: Any,
    pair: str,
    clock_profile: MT5ServerClockProfile,
) -> pd.DataFrame:
    """Convert authorized MT5 server wall time to ASTRA UTC-naive time."""
    frame = pd.DataFrame(rates)
    required = {"time", "open", "high", "low", "close", "tick_volume"}
    missing = required - set(frame.columns)
    if missing:
        raise MT5DataContractError(
            f"MT5_RATE_FIELDS_MISSING: {sorted(missing)}"
        )
    timestamps = pd.to_datetime(frame["time"], unit="s", errors="coerce")
    if timestamps.isna().any():
        raise MT5DataContractError("MT5_CANDLE_TIMESTAMPS_INVALID")
    try:
        ambiguous_probe = timestamps.dt.tz_localize(
            clock_profile.timezone,
            ambiguous="NaT",
            nonexistent="shift_forward",
        )
        if ambiguous_probe.isna().any():
            raise MT5DataContractError(
                "MT5_CANDLE_TIMESTAMP_AMBIGUOUS"
            )
        nonexistent_probe = timestamps.dt.tz_localize(
            clock_profile.timezone,
            ambiguous=True,
            nonexistent="NaT",
        )
        if nonexistent_probe.isna().any():
            raise MT5DataContractError(
                "MT5_CANDLE_TIMESTAMP_NONEXISTENT"
            )
        localized = timestamps.dt.tz_localize(
            clock_profile.timezone,
            ambiguous="raise",
            nonexistent="raise",
        )
    except MT5DataContractError:
        raise
    except Exception as exc:
        error_name = type(exc).__name__
        if error_name == "AmbiguousTimeError":
            raise MT5DataContractError(
                "MT5_CANDLE_TIMESTAMP_AMBIGUOUS"
            ) from None
        if error_name == "NonExistentTimeError":
            raise MT5DataContractError(
                "MT5_CANDLE_TIMESTAMP_NONEXISTENT"
            ) from None
        raise MT5DataContractError(
            "MT5_CANDLE_TIMEZONE_NORMALIZATION_FAILURE"
        ) from None
    frame["timestamp"] = localized.dt.tz_convert("UTC").dt.tz_localize(None)
    for column in ("open", "high", "low", "close", "tick_volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    volume = frame["tick_volume"].to_numpy(float)
    if not np.isfinite(volume).all() or (volume < 0).any():
        raise MT5DataContractError("MT5_TICK_VOLUME_INVALID")
    if frame["timestamp"].duplicated().any():
        raise MT5DataContractError("MT5_CANDLE_TIMESTAMPS_DUPLICATED")
    if not frame["timestamp"].is_monotonic_increasing:
        raise MT5DataContractError("MT5_CANDLES_NOT_CHRONOLOGICAL")
    frame["volume"] = frame["tick_volume"]
    frame["pair"] = pair.upper()
    return frame[
        ["timestamp", "open", "high", "low", "close", "volume", "pair"]
    ].reset_index(drop=True)


def _safe_attribute(value: Any, name: str) -> Any:
    observed = getattr(value, name, None) if value is not None else None
    return observed if isinstance(observed, (str, int, float, bool)) else None


class MT5Provider:
    """Pure MT5 provider; DataRouter exclusively owns all provider fallback."""

    def __init__(self):
        self._available: Optional[bool] = None
        self._initialized = False
        self._availability_state = "UNKNOWN"
        self._terminal_info: Any = None
        self._account_info: Any = None
        self._package_version: str | None = None
        self._last_acquisition_metadata: Optional[dict] = None

    @property
    def availability_state(self) -> str:
        return self._availability_state

    @property
    def last_acquisition_metadata(self) -> Optional[dict]:
        return copy.deepcopy(self._last_acquisition_metadata)

    def is_available(self) -> bool:
        if self._available is None:
            self._available = _is_mt5_available()
            self._availability_state = (
                "PACKAGE_AVAILABLE" if self._available else "PACKAGE_UNAVAILABLE"
            )
        return self._available

    def _ensure_init(self):
        if not self.is_available():
            raise MT5UnavailableError("MT5_PACKAGE_UNAVAILABLE")
        import MetaTrader5 as mt5

        if self._initialized and self._availability_state == "ACCOUNT_CONNECTED":
            return mt5
        try:
            initialized = bool(mt5.initialize())
        except Exception:
            raise MT5InitializationError("MT5_INITIALIZE_FAILURE") from None
        if not initialized:
            raise MT5InitializationError(
                "MT5_INITIALIZE_FAILURE" + _last_error_code(mt5)
            )
        self._initialized = True
        self._availability_state = "TERMINAL_INITIALIZED"
        try:
            self._terminal_info = mt5.terminal_info()
        except Exception:
            self._terminal_info = None
        try:
            self._account_info = mt5.account_info()
        except Exception:
            self._account_info = None
        if self._account_info is None:
            try:
                mt5.shutdown()
            except Exception:
                pass
            self._initialized = False
            self._availability_state = "PACKAGE_AVAILABLE"
            raise MT5InitializationError(
                "MT5_ACCOUNT_NOT_CONNECTED" + _last_error_code(mt5)
            )
        self._package_version = str(getattr(mt5, "__version__", "unknown"))
        self._availability_state = "ACCOUNT_CONNECTED"
        return mt5

    def _metadata(
        self,
        *,
        pair: str,
        timeframe: str,
        requested_bars: int,
        raw_closed_rows: int,
        valid_rows_before_tail: int,
        returned_rows: int,
        dropped_rows: list[dict],
        clock_profile: MT5ServerClockProfile,
    ) -> dict:
        observed_server = _safe_attribute(self._account_info, "server")
        return {
            "schema_version": 1,
            "provider": "MT5",
            "symbol": pair.upper(),
            "timeframe": timeframe,
            "requested_bars": int(requested_bars),
            "raw_closed_rows": int(raw_closed_rows),
            "invalid_rows_dropped": int(len(dropped_rows)),
            "valid_rows_before_tail": int(valid_rows_before_tail),
            "returned_rows": int(returned_rows),
            "dropped_rows": dropped_rows,
            "native_timeframe": True,
            "terminal_connected": True,
            "server": observed_server,
            "company": (
                _safe_attribute(self._account_info, "company")
                or _safe_attribute(self._terminal_info, "company")
            ),
            "trade_mode": _safe_attribute(self._account_info, "trade_mode"),
            "mt5_package_version": self._package_version,
            "terminal_build": _safe_attribute(self._terminal_info, "build"),
            "symbol_external": pair.upper(),
            "headroom_requested": MT5_HEADROOM,
            "volume_provenance": "MT5_TICK_VOLUME",
            "timestamp_source_domain": "MT5_SERVER_TIME",
            "source_timezone": clock_profile.timezone,
            "timezone_profile_id": clock_profile.profile_id,
            "timezone_profile_version": clock_profile.version,
            "timezone_evidence_hash": clock_profile.evidence_hash,
            "timezone_authority_type": clock_profile.authority_type,
            "timezone_source_identity": clock_profile.source_identity,
            "timezone_effective_from": clock_profile.effective_from,
            "timezone_effective_to": clock_profile.effective_to,
            "timestamp_normalization": "SERVER_WALL_TIME_TO_UTC",
            "observed_server": observed_server,
        }

    def fetch(
        self,
        pair: str,
        tf: str = "H1",
        bars: int = 500,
        allow_fallback: bool = False,
        *,
        now: Any = None,
    ) -> pd.DataFrame:
        """Return exactly ``bars`` complete, sanitized native MT5 candles."""
        self._last_acquisition_metadata = None
        if allow_fallback:
            warnings.warn(
                "MT5Provider is provider-pure; allow_fallback is deprecated "
                "and ignored. DataRouter owns fallback.",
                DeprecationWarning,
                stacklevel=2,
            )
        timeframe = tf.upper()
        constant_name = _TIMEFRAME_CONSTANTS.get(timeframe)
        if constant_name is None:
            raise MT5DataContractError(f"MT5_TIMEFRAME_UNSUPPORTED: {timeframe}")
        requested = int(bars)
        if requested <= 0:
            raise MT5DataContractError(
                f"MT5_REQUESTED_BARS_OUT_OF_RANGE: {requested}"
            )
        route = route_for_provider(pair, "MT5")
        if route is None:
            raise MT5SymbolError(
                f"MT5_SYMBOL_NOT_CATALOGUED: {str(pair).upper()}"
            )
        symbol = route.external_ticker
        mt5 = self._ensure_init()
        observed_server = _safe_attribute(self._account_info, "server")
        clock_profile = resolve_mt5_server_clock_profile(observed_server)
        if clock_profile is None:
            raise MT5DataContractError(
                "MT5_SERVER_CLOCK_PROFILE_UNKNOWN: "
                f"{observed_server or 'UNAVAILABLE'}"
            )
        timeframe_code = getattr(mt5, constant_name, None)
        if timeframe_code is None:
            raise MT5DataContractError(
                f"MT5_TIMEFRAME_CONSTANT_MISSING: {constant_name}"
            )
        try:
            symbol_info = mt5.symbol_info(symbol)
        except Exception:
            raise MT5SymbolError("MT5_SYMBOL_LOOKUP_FAILURE") from None
        if symbol_info is None:
            raise MT5SymbolError(
                "MT5_SYMBOL_UNAVAILABLE" + _last_error_code(mt5)
            )
        if not bool(getattr(symbol_info, "visible", False)):
            try:
                selected = bool(mt5.symbol_select(symbol, True))
            except Exception:
                selected = False
            if not selected:
                raise MT5SymbolError(
                    "MT5_SYMBOL_SELECT_FAILURE" + _last_error_code(mt5)
                )
        requested_from_mt5 = requested + MT5_HEADROOM
        try:
            rates = mt5.copy_rates_from_pos(
                symbol, timeframe_code, 0, requested_from_mt5
            )
        except Exception:
            raise MT5ProviderError(
                "MT5_COPY_RATES_FAILURE" + _last_error_code(mt5)
            ) from None
        if rates is None or len(rates) == 0:
            raise MT5ProviderError(
                "MT5_COPY_RATES_EMPTY" + _last_error_code(mt5)
            )

        normalized = _normalize_mt5_df(rates, symbol, clock_profile)
        closed = exclude_incomplete_candles(normalized, timeframe, now=now)
        raw_closed_rows = len(closed)
        valid, dropped = sanitize_ohlc_frame(closed)
        try:
            validate_ohlc_frame(valid)
        except OHLCContractError as exc:
            raise MT5DataContractError(
                f"MT5_OHLC_CONTRACT_FAILURE: {exc}"
            ) from None
        returned_rows = min(len(valid), requested)
        self._last_acquisition_metadata = self._metadata(
            pair=symbol,
            timeframe=timeframe,
            requested_bars=requested,
            raw_closed_rows=raw_closed_rows,
            valid_rows_before_tail=len(valid),
            returned_rows=returned_rows,
            dropped_rows=dropped,
            clock_profile=clock_profile,
        )
        if len(valid) < requested:
            raise MT5DataContractError(
                "INSUFFICIENT_VALID_BARS_AFTER_SANITIZATION: "
                f"{symbol}/{timeframe} requested={requested} valid={len(valid)} "
                f"raw_closed={raw_closed_rows} dropped={len(dropped)}"
            )
        result = valid.tail(requested).reset_index(drop=True)
        result.attrs["acquisition_metadata"] = self.last_acquisition_metadata
        return result

    def shutdown(self) -> None:
        if not self._initialized or not self.is_available():
            return
        try:
            import MetaTrader5 as mt5

            mt5.shutdown()
        except Exception:
            pass
        finally:
            self._initialized = False
            self._terminal_info = None
            self._account_info = None
            self._availability_state = "PACKAGE_AVAILABLE"


_provider = MT5Provider()


def get_mt5_provider() -> MT5Provider:
    return _provider


__all__ = [
    "MT5DataContractError",
    "MT5InitializationError",
    "MT5Provider",
    "MT5ProviderError",
    "MT5SymbolError",
    "MT5UnavailableError",
    "MT5_HEADROOM",
    "get_mt5_provider",
]

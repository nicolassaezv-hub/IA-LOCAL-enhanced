"""Provenance-gated market-time grids for canonical UTC candle datasets."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from forex.data.ifc_session_authority import IFC_FOREX_SESSION_AUTHORITY
from forex.data.mt5_clock_profiles import (
    IFC_MARKETS_DEMO_CLOCK_PROFILE,
    MT5ServerClockProfile,
    resolve_mt5_server_clock_profile,
)
from forex.data.ohlc_contract import acquisition_metadata_dict
from forex.data.session_authority import SessionAuthority


class MarketTimeGridError(ValueError):
    """Raised when an expected open cannot be mapped safely to UTC."""


@dataclass(frozen=True)
class MarketTimeGrid:
    """One broker-local candle grid backed by exact acquisition provenance."""

    profile: MT5ServerClockProfile
    session_authority: SessionAuthority

    @property
    def timezone(self) -> str:
        return self.profile.timezone

    def to_local(self, timestamp: Any) -> pd.Timestamp:
        moment = pd.Timestamp(timestamp)
        if pd.isna(moment):
            raise MarketTimeGridError("MARKET_GRID_TIMESTAMP_INVALID")
        if moment.tzinfo is None:
            moment = moment.tz_localize("UTC")
        else:
            moment = moment.tz_convert("UTC")
        return moment.tz_convert(self.timezone)

    @staticmethod
    def is_weekend(local_wall_time: Any) -> bool:
        return pd.Timestamp(local_wall_time).dayofweek >= 5

    def wall_time_to_utc(self, local_wall_time: Any) -> pd.Timestamp:
        wall = pd.Timestamp(local_wall_time)
        if pd.isna(wall) or wall.tzinfo is not None:
            raise MarketTimeGridError("MARKET_GRID_WALL_TIME_INVALID")
        values = pd.DatetimeIndex([wall])
        ambiguous = values.tz_localize(
            self.timezone, ambiguous="NaT", nonexistent="shift_forward"
        )
        if ambiguous.isna().any():
            raise MarketTimeGridError("MARKET_GRID_WALL_TIME_AMBIGUOUS")
        nonexistent = values.tz_localize(
            self.timezone, ambiguous=True, nonexistent="NaT"
        )
        if nonexistent.isna().any():
            raise MarketTimeGridError("MARKET_GRID_WALL_TIME_NONEXISTENT")
        return values.tz_localize(
            self.timezone, ambiguous="raise", nonexistent="raise"
        )[0].tz_convert("UTC").tz_localize(None)


def resolve_market_time_grid(
    acquisition_metadata: Any,
    *,
    provider: str | None,
    symbol: str | None,
    asset_class: str,
) -> MarketTimeGrid | None:
    """Resolve IFC market time only from the complete exact MT5 profile."""
    try:
        metadata = acquisition_metadata_dict(acquisition_metadata)
    except Exception:
        return None
    if metadata is None or provider != "MT5" or asset_class.upper() != "FOREX":
        return None
    if symbol is None or symbol.upper() != "EURUSD":
        return None
    profile = resolve_mt5_server_clock_profile(metadata.get("observed_server"))
    if profile is None or profile != IFC_MARKETS_DEMO_CLOCK_PROFILE:
        return None
    expected = {
        "provider": "MT5",
        "symbol": "EURUSD",
        "timestamp_source_domain": "MT5_SERVER_TIME",
        "source_timezone": profile.timezone,
        "timezone_profile_id": profile.profile_id,
        "timezone_profile_version": profile.version,
        "timezone_evidence_hash": profile.evidence_hash,
        "timestamp_normalization": "SERVER_WALL_TIME_TO_UTC",
        "observed_server": profile.server_identity,
    }
    if any(metadata.get(field) != value for field, value in expected.items()):
        return None
    return MarketTimeGrid(
        profile=profile,
        session_authority=IFC_FOREX_SESSION_AUTHORITY,
    )


__all__ = [
    "MarketTimeGrid",
    "MarketTimeGridError",
    "resolve_market_time_grid",
]

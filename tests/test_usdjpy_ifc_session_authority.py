"""USDJPY-specific, fail-closed IFC market-session contract tests."""
from __future__ import annotations

import pandas as pd
import pytest

import forex.data.ifc_session_authority as ifc_authority
from forex.data.market_time_grid import resolve_market_time_grid
from forex.data.mt5_clock_profiles import IFC_MARKETS_DEMO_CLOCK_PROFILE
from forex.data.session_authority import SessionState, classify_authorized_timestamp
from scripts.validate_symbol_universe import classify_gaps


pytestmark = pytest.mark.unit


def _metadata(symbol: str, timeframe: str = "H1") -> dict:
    profile = IFC_MARKETS_DEMO_CLOCK_PROFILE
    return {
        "schema_version": 1,
        "provider": "MT5",
        "symbol": symbol,
        "timeframe": timeframe,
        "requested_bars": 2001,
        "raw_closed_rows": 2001,
        "invalid_rows_dropped": 0,
        "valid_rows_before_tail": 2001,
        "returned_rows": 2001,
        "dropped_rows": [],
        "timestamp_source_domain": "MT5_SERVER_TIME",
        "source_timezone": profile.timezone,
        "timezone_profile_id": profile.profile_id,
        "timezone_profile_version": profile.version,
        "timezone_evidence_hash": profile.evidence_hash,
        "timestamp_normalization": "SERVER_WALL_TIME_TO_UTC",
        "observed_server": profile.server_identity,
    }


def _local_to_utc(values: list[str]) -> pd.Series:
    return pd.Series(
        pd.DatetimeIndex(values)
        .tz_localize("Europe/Berlin", ambiguous="raise", nonexistent="raise")
        .tz_convert("UTC")
        .tz_localize(None)
    )


def _classify_usdjpy(local_values: list[str], timeframe: str) -> list[dict]:
    return classify_gaps(
        _local_to_utc(local_values),
        timeframe,
        "FOREX",
        acquisition_metadata=_metadata("USDJPY", timeframe),
        provider="MT5",
        symbol="USDJPY",
    )


def test_eurusd_authority_remains_eurusd_scoped():
    authority = ifc_authority.IFC_FOREX_SESSION_AUTHORITY
    descriptor = authority.descriptor
    timestamp = _local_to_utc(["2026-08-21 22:00"]).iloc[0].tz_localize("UTC")

    assert descriptor.authority_id == "ifcmarkets-demo-eurusd-session-v1"
    assert descriptor.symbol == "EURUSD"
    assert classify_authorized_timestamp(
        authority,
        timestamp,
        asset_class="FOREX",
        provider="MT5",
        symbol="USDJPY",
        clock_profile_id=IFC_MARKETS_DEMO_CLOCK_PROFILE.profile_id,
        server_identity="IFCMarkets-Demo",
    ) == SessionState.UNKNOWN


def test_usdjpy_authority_is_exactly_scoped_and_rejects_another_symbol():
    authority = ifc_authority.IFC_USDJPY_SESSION_AUTHORITY
    descriptor = authority.descriptor
    timestamp = _local_to_utc(["2026-08-21 22:00"]).iloc[0].tz_localize("UTC")

    assert descriptor.authority_id == "ifcmarkets-demo-usdjpy-session-v1"
    assert descriptor.symbol == "USDJPY"
    assert descriptor.provider == "MT5"
    assert descriptor.server_identity == "IFCMarkets-Demo"
    assert descriptor.timezone == "Europe/Berlin"
    assert classify_authorized_timestamp(
        authority,
        timestamp,
        asset_class="FOREX",
        provider="MT5",
        symbol="GBPUSD",
        clock_profile_id=IFC_MARKETS_DEMO_CLOCK_PROFILE.profile_id,
        server_identity="IFCMarkets-Demo",
    ) == SessionState.UNKNOWN


def test_usdjpy_h1_trade_maintenance_does_not_invent_quote_closure():
    gaps = _classify_usdjpy(
        ["2026-08-24 22:00", "2026-08-25 00:00"], "H1"
    )

    assert gaps[0]["classification"] == "PROVIDER_GAP"
    assert gaps[0]["explanation_counts"] == {"UNEXPLAINED": 1}


def test_usdjpy_friday_quote_close_is_authorized():
    gaps = _classify_usdjpy(
        ["2026-08-21 21:00", "2026-08-24 00:00"], "H1"
    )

    assert gaps[0]["classification"] == "MARKET_SESSION_CLOSED"
    assert gaps[0]["explanation_counts"] == {
        "SESSION_CLOSED": 2,
        "WEEKEND": 48,
    }
    assert gaps[0]["session_authority_id"] == (
        "ifcmarkets-demo-usdjpy-session-v1"
    )


def test_usdjpy_weekend_only_gap_is_non_blocking_weekend():
    gaps = _classify_usdjpy(["2026-08-21", "2026-08-24"], "D1")

    assert gaps[0]["classification"] == "WEEKEND"
    assert gaps[0]["explanation_counts"] == {"WEEKEND": 2}


def test_usdjpy_open_session_missing_candle_remains_provider_gap():
    gaps = _classify_usdjpy(
        ["2026-08-24 10:00", "2026-08-24 12:00"], "H1"
    )

    assert gaps[0]["classification"] == "PROVIDER_GAP"
    assert gaps[0]["unexplained_local_timestamps"] == [
        "2026-08-24 11:00:00"
    ]


def test_unknown_usdjpy_session_evidence_remains_blocking():
    metadata = _metadata("USDJPY")
    metadata["timezone_evidence_hash"] = "0" * 64

    grid = resolve_market_time_grid(
        metadata, provider="MT5", symbol="USDJPY", asset_class="FOREX"
    )
    gaps = classify_gaps(
        _local_to_utc(["2026-08-21 21:00", "2026-08-24 00:00"]),
        "H1",
        "FOREX",
        acquisition_metadata=metadata,
        provider="MT5",
        symbol="USDJPY",
    )

    assert grid is None
    assert gaps[0]["classification"] == "PROVIDER_GAP"


@pytest.mark.parametrize(
    ("local_values", "special_delta_hours"),
    [
        (["2026-03-28", "2026-03-29", "2026-03-30"], 23),
        (["2026-10-24", "2026-10-25", "2026-10-26"], 25),
    ],
    ids=("spring", "autumn"),
)
def test_usdjpy_d1_dst_transitions_are_deterministic(
    local_values, special_delta_hours
):
    utc_values = _local_to_utc(local_values)
    gaps = classify_gaps(
        utc_values,
        "D1",
        "FOREX",
        acquisition_metadata=_metadata("USDJPY", "D1"),
        provider="MT5",
        symbol="USDJPY",
    )

    assert gaps == []
    assert special_delta_hours * 3600 in set(
        utc_values.diff().dropna().dt.total_seconds()
    )


def test_usdjpy_d1_weekly_grid_does_not_create_false_provider_gap():
    gaps = _classify_usdjpy(["2026-08-21", "2026-08-24"], "D1")

    assert len(gaps) == 1
    assert gaps[0]["classification"] == "WEEKEND"
    assert gaps[0]["explanation_counts"].get("UNEXPLAINED", 0) == 0


def test_usdjpy_h4_session_boundary_uses_broker_local_grid():
    gaps = _classify_usdjpy(
        ["2026-08-21 20:00", "2026-08-24 00:00"], "H4"
    )

    assert len(gaps) == 1
    assert gaps[0]["classification"] == "WEEKEND"
    assert gaps[0]["explanation_counts"] == {"WEEKEND": 12}


def test_existing_eurusd_authority_and_gap_behavior_are_unchanged():
    descriptor = ifc_authority.IFC_FOREX_SESSION_AUTHORITY.descriptor
    gaps = classify_gaps(
        _local_to_utc(["2026-08-21 21:00", "2026-08-24 00:00"]),
        "H1",
        "FOREX",
        acquisition_metadata=_metadata("EURUSD", "H1"),
        provider="MT5",
        symbol="EURUSD",
    )

    assert descriptor.evidence_hash == (
        "497038aeee0119de925e441aa125f9eae1dc86eacff26218f9b490f1d5b0f151"
    )
    assert gaps[0]["classification"] == "MARKET_SESSION_CLOSED"
    assert gaps[0]["session_authority_id"] == (
        "ifcmarkets-demo-eurusd-session-v1"
    )

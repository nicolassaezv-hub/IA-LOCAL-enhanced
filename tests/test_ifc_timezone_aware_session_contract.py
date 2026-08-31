"""Timezone-aware, provenance-bound IFC market-session contract tests."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pandas as pd
import pytest

from forex.data.ifc_session_authority import (
    IFC_CLOSURE_EVIDENCE,
    IFC_FOREX_SESSION_AUTHORITY,
    IFC_UNAUTHORIZED_HOLIDAY_DATES,
    _QUOTE_SESSION_EVIDENCE,
)
from forex.data.market_time_grid import resolve_market_time_grid
from forex.data.mt5_clock_profiles import IFC_MARKETS_DEMO_CLOCK_PROFILE
from forex.data.session_authority import (
    SessionState,
    classify_authorized_timestamp,
)
from scripts.validate_symbol_universe import classify_gaps


pytestmark = pytest.mark.unit


def _metadata(timeframe: str = "H1") -> dict:
    profile = IFC_MARKETS_DEMO_CLOCK_PROFILE
    return {
        "schema_version": 1,
        "provider": "MT5",
        "symbol": "EURUSD",
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


def _classify(
    local_values: list[str], timeframe: str, *, metadata: dict | None = None
) -> list[dict]:
    return classify_gaps(
        _local_to_utc(local_values),
        timeframe,
        "FOREX",
        acquisition_metadata=_metadata(timeframe) if metadata is None else metadata,
        provider="MT5",
        symbol="EURUSD",
    )


def _authorized_state(local_value: str) -> SessionState:
    utc_value = _local_to_utc([local_value]).iloc[0].tz_localize("UTC")
    return classify_authorized_timestamp(
        IFC_FOREX_SESSION_AUTHORITY,
        utc_value,
        asset_class="FOREX",
        provider="MT5",
        symbol="EURUSD",
        clock_profile_id=IFC_MARKETS_DEMO_CLOCK_PROFILE.profile_id,
        server_identity="IFCMarkets-Demo",
    )


def test_utc_friday_that_is_broker_local_saturday_is_weekend():
    grid = resolve_market_time_grid(
        _metadata(), provider="MT5", symbol="EURUSD", asset_class="FOREX"
    )

    local = grid.to_local(pd.Timestamp("2026-08-21 22:30:00", tz="UTC"))

    assert local.day_name() == "Saturday"
    assert grid.is_weekend(local.tz_localize(None)) is True


def test_utc_sunday_23_cet_winter_is_broker_local_monday_not_weekend():
    grid = resolve_market_time_grid(
        _metadata(), provider="MT5", symbol="EURUSD", asset_class="FOREX"
    )

    local = grid.to_local(pd.Timestamp("2026-01-04 23:00:00", tz="UTC"))

    assert local == pd.Timestamp("2026-01-05 00:00:00", tz="Europe/Berlin")
    assert grid.is_weekend(local.tz_localize(None)) is False


@pytest.mark.parametrize(
    ("local_values", "special_delta_hours"),
    [
        (["2026-03-28 00:00", "2026-03-29 00:00", "2026-03-30 00:00"], 23),
        (["2026-10-24 00:00", "2026-10-25 00:00", "2026-10-26 00:00"], 25),
    ],
    ids=("spring-23h-utc", "autumn-25h-utc"),
)
def test_consecutive_d1_local_midnights_across_dst_are_continuous(
    local_values, special_delta_hours
):
    utc_values = _local_to_utc(local_values)

    gaps = classify_gaps(
        utc_values,
        "D1",
        "FOREX",
        acquisition_metadata=_metadata("D1"),
        provider="MT5",
        symbol="EURUSD",
    )

    assert gaps == []
    deltas = set(utc_values.diff().dropna().dt.total_seconds())
    assert deltas <= {23 * 3600, 24 * 3600, 25 * 3600}
    assert special_delta_hours * 3600 in deltas


@pytest.mark.parametrize(
    ("local_value", "expected"),
    [
        ("2026-08-21 21:00", SessionState.OPEN),
        ("2026-08-21 22:00", SessionState.CLOSED),
        ("2026-08-21 23:00", SessionState.CLOSED),
        ("2026-08-22 12:00", SessionState.CLOSED),
        ("2026-08-23 12:00", SessionState.CLOSED),
        ("2026-08-24 00:00", SessionState.OPEN),
        ("2026-08-25 23:30", SessionState.OPEN),
        ("2026-08-27 23:30", SessionState.OPEN),
    ],
)
def test_ifc_quote_session_states(local_value, expected):
    assert _authorized_state(local_value) == expected


def test_current_quote_session_is_not_projected_beyond_its_evidence_range():
    assert _authorized_state("2025-08-22 22:00") == SessionState.UNKNOWN


def test_h1_sixteen_weekly_events_have_no_provider_gap():
    local_grid = pd.date_range(
        "2026-05-04 05:00", "2026-08-28 21:00", freq="h"
    )
    observed_local = local_grid[
        (local_grid.dayofweek < 4)
        | ((local_grid.dayofweek == 4) & (local_grid.hour < 22))
    ]
    observed_utc = (
        observed_local.tz_localize("Europe/Berlin")
        .tz_convert("UTC")
        .tz_localize(None)
    )

    gaps = classify_gaps(
        pd.Series(observed_utc),
        "H1",
        "FOREX",
        acquisition_metadata=_metadata("H1"),
        provider="MT5",
        symbol="EURUSD",
    )

    assert len(gaps) == 16
    assert {gap["classification"] for gap in gaps} == {"MARKET_SESSION_CLOSED"}
    assert all(gap["explanation_counts"] == {"SESSION_CLOSED": 2, "WEEKEND": 48} for gap in gaps)


def test_h1_live_acceptance_is_invariant_to_rolling_window_boundaries():
    local_grid = pd.date_range(
        "2026-05-01 00:00", "2026-08-31 02:00", freq="h"
    )
    observed_local = local_grid[
        (local_grid.dayofweek < 4)
        | ((local_grid.dayofweek == 4) & (local_grid.hour < 22))
    ]

    def rolling_gaps(through: str) -> list[dict]:
        window = observed_local[observed_local <= pd.Timestamp(through)][-2001:]
        observed_utc = (
            window.tz_localize("Europe/Berlin")
            .tz_convert("UTC")
            .tz_localize(None)
        )
        assert len(observed_utc) == 2001
        return classify_gaps(
            pd.Series(observed_utc),
            "H1",
            "FOREX",
            acquisition_metadata=_metadata("H1"),
            provider="MT5",
            symbol="EURUSD",
        )

    before_reopen = rolling_gaps("2026-08-28 21:00")
    after_reopen = rolling_gaps("2026-08-31 02:00")

    assert len(after_reopen) == len(before_reopen) + 1
    for gaps in (before_reopen, after_reopen):
        assert gaps
        assert all(
            gap["classification"] == "MARKET_SESSION_CLOSED"
            for gap in gaps
        )
        assert all(
            gap["explanation_counts"].get("UNEXPLAINED", 0) == 0
            for gap in gaps
        )


def test_h4_ordinary_weekend_uses_broker_local_calendar():
    gaps = _classify(
        ["2026-08-21 20:00", "2026-08-24 00:00"], "H4"
    )

    assert gaps[0]["classification"] == "WEEKEND"
    assert gaps[0]["explanation_counts"] == {"WEEKEND": 12}


@pytest.mark.parametrize(
    ("previous", "current"),
    [
        ("2025-12-24 16:00", "2025-12-26 00:00"),
        ("2025-12-31 04:00", "2026-01-02 08:00"),
    ],
    ids=("christmas-2025", "new-year-2025-2026"),
)
def test_h4_documented_holiday_gaps_are_authorized(previous, current):
    gaps = _classify([previous, current], "H4")

    assert gaps[0]["classification"] == "MARKET_SESSION_CLOSED"
    assert gaps[0]["explanation_counts"].get("UNEXPLAINED", 0) == 0
    assert gaps[0]["session_evidence"]


@pytest.mark.parametrize(
    ("previous", "current"),
    [
        ("2018-12-24", "2018-12-26"),
        ("2018-12-28", "2019-01-02"),
        ("2019-12-24", "2019-12-26"),
        ("2019-12-31", "2020-01-02"),
        ("2023-12-22", "2023-12-26"),
        ("2023-12-29", "2024-01-02"),
        ("2024-12-24", "2024-12-26"),
        ("2024-12-31", "2025-01-02"),
        ("2025-12-24", "2025-12-26"),
        ("2025-12-31", "2026-01-02"),
    ],
)
def test_d1_documented_holiday_events_are_authorized(previous, current):
    gaps = _classify([previous, current], "D1")

    assert gaps[0]["classification"] == "MARKET_SESSION_CLOSED"
    assert gaps[0]["explanation_counts"].get("UNEXPLAINED", 0) == 0
    assert gaps[0]["session_evidence"]


@pytest.mark.parametrize(
    (
        "evidence_id",
        "start_local",
        "end_local",
        "inside_local",
        "previous",
        "current",
    ),
    [
        (
            "ifc-2020-christmas",
            "2020-12-24 19:00:00",
            "2020-12-28 00:00:00",
            "2020-12-25 12:00",
            "2020-12-24",
            "2020-12-28",
        ),
        (
            "ifc-2020-2021-new-year",
            "2020-12-31 07:00:00",
            "2021-01-04 00:00:00",
            "2021-01-01 12:00",
            "2020-12-31",
            "2021-01-04",
        ),
    ],
    ids=("christmas-2020", "new-year-2020-2021"),
)
def test_reviewed_ifc_2020_holidays_are_provenance_bound_and_authorized(
    evidence_id, start_local, end_local, inside_local, previous, current
):
    evidence = next(
        item for item in IFC_CLOSURE_EVIDENCE if item.evidence_id == evidence_id
    )

    assert evidence.source_identity == (
        "IFC_ARCHIVED_CHRISTMAS_NEW_YEAR_2020_2021"
    )
    assert evidence.publication_or_capture == (
        "published=2020-12-15;web_archive_capture=2023-07-05T15:34:45Z"
    )
    assert evidence.start_local == start_local
    assert evidence.end_local == end_local
    assert _authorized_state(inside_local) == SessionState.CLOSED

    utc_value = _local_to_utc([inside_local]).iloc[0].tz_localize("UTC")
    provenance = IFC_FOREX_SESSION_AUTHORITY.evidence_for_timestamp(utc_value)
    gaps = _classify([previous, current], "D1")

    assert provenance is not None
    assert provenance["evidence_id"] == evidence_id
    assert gaps[0]["classification"] == "MARKET_SESSION_CLOSED"
    assert gaps[0]["explanation_counts"].get("UNEXPLAINED", 0) == 0
    assert {item["evidence_id"] for item in gaps[0]["session_evidence"]} == {
        evidence_id
    }


def test_reviewed_ifc_2020_holidays_are_no_longer_explicitly_unauthorized():
    assert IFC_UNAUTHORIZED_HOLIDAY_DATES == frozenset()


@pytest.mark.parametrize(
    "local_value",
    [
        "2020-12-23 12:00",
        "2020-12-29 12:00",
        "2020-12-30 06:00",
        "2021-01-04 00:00",
        "2022-12-25 12:00",
        "2022-01-01 12:00",
    ],
)
def test_ifc_2020_holiday_evidence_is_not_recurring_or_extended(local_value):
    assert _authorized_state(local_value) == SessionState.UNKNOWN


@pytest.mark.parametrize(
    ("provider", "symbol", "server_identity"),
    [
        ("MT5", "EURUSD", "Other-MT5-Server"),
        ("MT5", "GBPUSD", "IFCMarkets-Demo"),
    ],
    ids=("wrong-server", "wrong-symbol"),
)
def test_ifc_2020_holiday_evidence_keeps_exact_scope(
    provider, symbol, server_identity
):
    utc_value = _local_to_utc(["2020-12-25 12:00"]).iloc[0].tz_localize("UTC")

    state = classify_authorized_timestamp(
        IFC_FOREX_SESSION_AUTHORITY,
        utc_value,
        asset_class="FOREX",
        provider=provider,
        symbol=symbol,
        clock_profile_id=IFC_MARKETS_DEMO_CLOCK_PROFILE.profile_id,
        server_identity=server_identity,
    )

    assert state == SessionState.UNKNOWN


def test_ifc_2020_binding_changes_the_evidence_bundle_hash():
    reviewed_2020_ids = {
        "ifc-2020-christmas",
        "ifc-2020-2021-new-year",
    }
    pre_binding_records = tuple(
        item
        for item in IFC_CLOSURE_EVIDENCE
        if item.evidence_id not in reviewed_2020_ids
    )
    pre_binding_hash = sha256(
        "\n".join((
            _QUOTE_SESSION_EVIDENCE,
            *(item.evidence_hash for item in pre_binding_records),
        )).encode("utf-8")
    ).hexdigest()

    assert IFC_FOREX_SESSION_AUTHORITY.descriptor.evidence_hash != pre_binding_hash


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("observed_server", "Other-MT5-Server"),
        ("source_timezone", "UTC"),
        ("timezone_evidence_hash", "0" * 64),
        ("timezone_profile_version", 999),
    ],
)
def test_unknown_broker_or_tampered_profile_cannot_enable_ifc_authority(field, value):
    metadata = _metadata("H4")
    metadata[field] = value

    grid = resolve_market_time_grid(
        metadata, provider="MT5", symbol="EURUSD", asset_class="FOREX"
    )
    gaps = _classify(
        ["2026-08-21 20:00", "2026-08-24 00:00"],
        "H4",
        metadata=metadata,
    )

    assert grid is None
    assert gaps[0]["classification"] == "PROVIDER_GAP"


def test_missing_acquisition_provenance_cannot_enable_broker_local_grid():
    utc_values = _local_to_utc([
        "2026-03-28 00:00", "2026-03-29 00:00", "2026-03-30 00:00"
    ])

    gaps = classify_gaps(
        utc_values, "D1", "FOREX", provider="MT5", symbol="EURUSD"
    )

    assert gaps
    assert all(gap["classification"] != "MARKET_SESSION_CLOSED" for gap in gaps)


@pytest.mark.parametrize("provider", ["Yahoo", "OANDA"])
def test_yahoo_and_oanda_keep_legacy_utc_weekend_behavior(provider):
    gaps = classify_gaps(
        pd.Series(["2026-08-21 20:00", "2026-08-24 00:00"]),
        "H4",
        "FOREX",
        acquisition_metadata={"provider": provider},
        provider=provider,
        symbol="EURUSD",
    )

    assert gaps[0]["classification"] == "WEEKEND"


def test_crypto_weekend_gap_remains_provider_gap():
    gaps = classify_gaps(
        pd.Series(["2026-08-21 20:00", "2026-08-24 00:00"]),
        "H4",
        "CRYPTO",
        acquisition_metadata={"provider": "Binance"},
        provider="Binance",
        symbol="BTCUSDT",
    )

    assert gaps[0]["classification"] == "PROVIDER_GAP"


def test_ifc_descriptor_is_exact_server_symbol_and_profile_scoped():
    descriptor = IFC_FOREX_SESSION_AUTHORITY.descriptor

    assert descriptor.provider == "MT5"
    assert descriptor.asset_class == "FOREX"
    assert descriptor.symbol == "EURUSD"
    assert descriptor.clock_profile_id == "ifcmarkets-demo-europe-berlin"
    assert descriptor.server_identity == "IFCMarkets-Demo"
    assert len(descriptor.evidence_hash) == 64


def test_metadata_copy_tampering_does_not_mutate_authoritative_profile():
    metadata = deepcopy(_metadata())
    metadata["timezone_profile_id"] = "attacker-profile"

    assert resolve_market_time_grid(
        metadata, provider="MT5", symbol="EURUSD", asset_class="FOREX"
    ) is None
    assert IFC_MARKETS_DEMO_CLOCK_PROFILE.profile_id == (
        "ifcmarkets-demo-europe-berlin"
    )

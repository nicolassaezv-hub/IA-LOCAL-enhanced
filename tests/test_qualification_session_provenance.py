"""Fail-closed qualification observability and session provenance contracts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from forex.data.ohlc_contract import validate_acquisition_metadata
from forex.data.session_authority import (
    SessionState,
    UnknownSessionAuthority,
)
from forex.data.symbol_catalog import route_for_provider
from forex.data.symbol_lifecycle import qualify_candidate
from forex.data.yahoo_provider import resample_h4_with_provenance
from infra.db.database import SQLiteDatabase
from scripts.validate_symbol_universe import classify_gaps, validate_dataset_frame


pytestmark = pytest.mark.unit

NOW = pd.Timestamp("2026-08-21 12:00:00", tz="UTC")


def _market_frame(
    symbol: str,
    timeframe: str,
    *,
    count: int = 2001,
    gap_position: int | None = None,
) -> pd.DataFrame:
    hours = {"H1": 1, "H4": 4, "D1": 24}[timeframe]
    periods = count + (1 if gap_position is not None else 0)
    timestamps = pd.date_range(
        NOW.tz_localize(None) - pd.Timedelta(hours=hours * periods),
        periods=periods,
        freq=f"{hours}h",
    )
    if gap_position is not None:
        timestamps = timestamps.delete(gap_position)
    index = np.arange(count, dtype=float)
    center = 1.1 + index * 2e-5 + np.sin(index / 11.0) * 7e-4
    opened = center + np.sin(index / 5.0) * 8e-5
    closed = center + np.cos(index / 7.0) * 9e-5
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": opened,
        "high": np.maximum(opened, closed) + 4e-4,
        "low": np.minimum(opened, closed) - 4e-4,
        "close": closed,
        "volume": np.full(count, 1000.0),
        "pair": symbol,
    })


def _metadata(
    symbol: str,
    timeframe: str,
    *,
    dropped_rows: list[dict] | None = None,
    resample_provenance: list[dict] | None = None,
) -> dict:
    dropped_rows = list(dropped_rows or [])
    metadata = {
        "schema_version": 1,
        "provider": "Yahoo",
        "symbol": symbol,
        "timeframe": timeframe,
        "requested_bars": 2001,
        "raw_closed_rows": 2001 + len(dropped_rows),
        "invalid_rows_dropped": len(dropped_rows),
        "valid_rows_before_tail": 2001,
        "returned_rows": 2001,
        "dropped_rows": dropped_rows,
    }
    if resample_provenance is not None:
        metadata["resample_provenance"] = resample_provenance
    return metadata


@pytest.fixture(scope="module")
def failed_qualification(tmp_path_factory):
    root = tmp_path_factory.mktemp("failed-qualification-evidence")
    database = SQLiteDatabase(str(root / "astra.db"))
    database.register_candidate("NZDUSD", "NZD/USD", "FOREX", 0.0001)
    frames = {
        "H1": _market_frame("NZDUSD", "H1", gap_position=1000),
        "H4": _market_frame("NZDUSD", "H4", gap_position=1012),
        "D1": _market_frame("NZDUSD", "D1"),
    }
    h1_dropped = [{
        "timestamp": "2010-01-01T00:00:00",
        "reason": "INVALID_OHLC_ENVELOPE",
    }]
    h4_missing = pd.Timestamp(frames["H4"].iloc[1011]["timestamp"]) + pd.Timedelta(hours=4)
    h4_expected = pd.date_range(h4_missing, periods=4, freq="h")
    h4_resample = [{
        "target_timestamp": h4_missing.isoformat(),
        "source_timeframe": "H1",
        "expected_source_timestamps": [item.isoformat() for item in h4_expected],
        "observed_source_timestamps": [],
        "missing_source_timestamps": [item.isoformat() for item in h4_expected],
        "sanitization_backed_missing_timestamps": [],
        "session_closed_timestamps": [],
        "unexplained_provider_missing_timestamps": [
            item.isoformat() for item in h4_expected
        ],
        "omission_reason": "UPSTREAM_PROVIDER_GAP",
    }]
    metadata = {
        "H1": _metadata("NZDUSD", "H1", dropped_rows=h1_dropped),
        "H4": _metadata(
            "NZDUSD", "H4", resample_provenance=h4_resample
        ),
        "D1": _metadata("NZDUSD", "D1"),
    }

    class Router:
        def __init__(self, symbol: str, timeframe: str):
            self.symbol = symbol
            self.timeframe = timeframe
            self.source_used = "Yahoo"
            self.route_used = route_for_provider(symbol, "Yahoo")
            self.attempt_errors = ("MT5 unavailable",)
            self.last_acquisition_metadata = metadata[timeframe]

        def fetch(self, bars: int, raise_on_failure: bool):
            assert bars == 2001
            assert raise_on_failure is True
            return frames[self.timeframe].copy()

    model = root / "models" / "forex" / "latest_NZDUSD.pkl"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"unchanged-model-sentinel")
    model_sha = hashlib.sha256(model.read_bytes()).hexdigest()
    evidence = qualify_candidate(
        database,
        "NZDUSD",
        project_root=root,
        router_factory=Router,
        now=NOW,
    )
    return {
        "root": root,
        "database": database,
        "evidence": evidence,
        "metadata": metadata,
        "model": model,
        "model_sha": model_sha,
    }


def test_failed_qualification_preserves_complete_acquisition_metadata(
    failed_qualification,
):
    item = failed_qualification["evidence"]["timeframes"]["H1"]

    assert item["result"] == "FAIL"
    assert item["provider"] == "Yahoo"
    assert item["provider_class"] == "FX_REFERENCE"
    assert item["external_ticker"] == "NZDUSD=X"
    assert item["source_fetched_at"] == NOW.isoformat()
    assert item["acquisition_metadata"] == failed_qualification["metadata"]["H1"]
    assert item["requested_bars"] == 2001
    assert item["raw_closed_rows"] == 2002
    assert item["invalid_rows_dropped"] == 1
    assert item["valid_rows_before_tail"] == 2001
    assert item["returned_rows"] == 2001
    assert item["dropped_rows"][0]["reason"] == "INVALID_OHLC_ENVELOPE"
    assert Path(item["csv_path"]).is_file()
    assert len(item["csv_sha256"]) == 64
    assert item["physical_rows"] == 2000
    persisted = json.loads(
        Path(failed_qualification["evidence"]["evidence_path"]).read_text(
            encoding="utf-8"
        )
    )
    assert persisted["timeframes"]["H1"]["acquisition_metadata"] == (
        failed_qualification["metadata"]["H1"]
    )


def test_failed_qualification_preserves_exact_gap_and_resample_items(
    failed_qualification,
):
    item = failed_qualification["evidence"]["timeframes"]["H4"]
    gaps = item["validation"]["details"]["gaps"]

    assert gaps["classifications"] == {"PROVIDER_GAP": 1}
    assert len(gaps["items"]) == 1
    gap = gaps["items"][0]
    assert gap["classification"] == "PROVIDER_GAP"
    assert gap["resample_provenance"] == item["acquisition_metadata"][
        "resample_provenance"
    ]
    assert item["warnings"] == item["validation"]["warnings"]
    assert item["errors"] == item["validation"]["errors"]


def test_failed_qualification_remains_candidate(failed_qualification):
    database = failed_qualification["database"]
    evidence = failed_qualification["evidence"]

    assert evidence["result"] == "FAIL"
    row = database.get_symbol("NZDUSD")
    assert row["status"] == "candidate"
    assert row["qualification_sha256"] is None
    assert row["qualification_evidence_path"] is None


def test_failed_qualification_does_not_write_canonical_or_models(
    failed_qualification,
):
    root = failed_qualification["root"]
    model = failed_qualification["model"]

    assert not (root / "data" / "forex").exists()
    assert hashlib.sha256(model.read_bytes()).hexdigest() == failed_qualification[
        "model_sha"
    ]


def test_failed_qualification_does_not_touch_dataset_registry(
    failed_qualification,
):
    assert failed_qualification["database"].get_dataset_registry() == []


def test_session_authority_absent_keeps_provider_gap_blocking():
    timestamps = pd.Series(["2026-08-17 00:00", "2026-08-17 02:00"])

    gaps = classify_gaps(timestamps, "H1", "FOREX")

    assert [item["classification"] for item in gaps] == ["PROVIDER_GAP"]
    stage, _ = validate_dataset_frame(
        _market_frame("EURUSD", "H1", count=2000, gap_position=1000),
        "EURUSD",
        "H1",
        now=NOW,
    )
    assert stage["blocking"] is True


def test_session_authority_unknown_keeps_provider_gap_blocking():
    timestamps = pd.Series(["2026-08-17 00:00", "2026-08-17 02:00"])

    gaps = classify_gaps(
        timestamps,
        "H1",
        "FOREX",
        session_authority=UnknownSessionAuthority(),
        provider="Yahoo",
    )

    assert [item["classification"] for item in gaps] == ["PROVIDER_GAP"]


def test_invalid_authority_cannot_unblock_gap():
    class InvalidAuthority:
        descriptor = {"authority_id": "unvalidated"}

        def classify_timestamp(self, timestamp):
            return SessionState.CLOSED

    gaps = classify_gaps(
        pd.Series(["2026-08-17 00:00", "2026-08-17 02:00"]),
        "H1",
        "FOREX",
        session_authority=InvalidAuthority(),
        provider="Yahoo",
    )

    assert [item["classification"] for item in gaps] == ["PROVIDER_GAP"]


def _h1_block(timestamps: list[str]) -> pd.DataFrame:
    count = len(timestamps)
    return pd.DataFrame({
        "timestamp": pd.to_datetime(timestamps),
        "open": np.arange(count, dtype=float) + 1.0,
        "high": np.arange(count, dtype=float) + 1.2,
        "low": np.arange(count, dtype=float) + 0.8,
        "close": np.arange(count, dtype=float) + 1.1,
        "volume": np.full(count, 100.0),
        "pair": "EURUSD",
    })


def test_h4_complete_source_block_resamples_normally():
    frame = _h1_block([
        "2026-08-17 00:00",
        "2026-08-17 01:00",
        "2026-08-17 02:00",
        "2026-08-17 03:00",
    ])

    h4, provenance = resample_h4_with_provenance(frame, now="2030-01-01")

    assert len(h4) == 1
    assert provenance == []


def test_h4_upstream_provider_gap_is_blocking():
    frame = _h1_block([
        "2026-08-17 00:00",
        "2026-08-17 01:00",
        "2026-08-17 03:00",
    ])

    h4, provenance = resample_h4_with_provenance(frame, now="2030-01-01")

    assert h4.empty
    assert provenance[0]["omission_reason"] == "UPSTREAM_PROVIDER_GAP"
    assert provenance[0]["unexplained_provider_missing_timestamps"] == [
        "2026-08-17T02:00:00"
    ]


def test_h4_mixed_known_and_unknown_missing_causes_remain_blocking():
    frame = _h1_block([
        "2026-08-17 00:00",
        "2026-08-17 03:00",
    ])
    dropped = [{
        "timestamp": "2026-08-17T01:00:00",
        "reason": "INVALID_OHLC_ENVELOPE",
    }]

    _h4, provenance = resample_h4_with_provenance(
        frame,
        now="2030-01-01",
        sanitization_dropped=dropped,
    )

    item = provenance[0]
    assert item["sanitization_backed_missing_timestamps"] == [
        "2026-08-17T01:00:00"
    ]
    assert item["unexplained_provider_missing_timestamps"] == [
        "2026-08-17T02:00:00"
    ]
    assert item["omission_reason"] == "UPSTREAM_PROVIDER_GAP"


def test_h4_provenance_lists_all_source_members():
    frame = _h1_block([
        "2026-08-17 00:00",
        "2026-08-17 01:00",
        "2026-08-17 03:00",
    ])

    _h4, provenance = resample_h4_with_provenance(frame, now="2030-01-01")

    item = provenance[0]
    assert item["target_timestamp"] == "2026-08-17T00:00:00"
    assert item["source_timeframe"] == "H1"
    assert item["expected_source_timestamps"] == [
        "2026-08-17T00:00:00",
        "2026-08-17T01:00:00",
        "2026-08-17T02:00:00",
        "2026-08-17T03:00:00",
    ]
    assert item["observed_source_timestamps"] == [
        "2026-08-17T00:00:00",
        "2026-08-17T01:00:00",
        "2026-08-17T03:00:00",
    ]
    assert item["missing_source_timestamps"] == ["2026-08-17T02:00:00"]


def test_acquisition_v1_retains_sanitization_and_resample_provenance():
    dropped = [{
        "timestamp": "2026-08-17T01:00:00",
        "reason": "INVALID_OHLC_ENVELOPE",
    }]
    _h4, provenance = resample_h4_with_provenance(
        _h1_block(["2026-08-17 00:00", "2026-08-17 03:00"]),
        now="2030-01-01",
        sanitization_dropped=dropped,
    )
    metadata = _metadata(
        "EURUSD",
        "H4",
        dropped_rows=dropped,
        resample_provenance=provenance,
    )

    validated = validate_acquisition_metadata(metadata)

    assert validated["schema_version"] == 1
    assert validated["dropped_rows"] == dropped
    assert validated["resample_provenance"] == provenance


def test_current_h4_missing_block_without_authority_remains_provider_gap():
    missing_target = pd.Timestamp("2026-08-17 04:00:00")
    expected = pd.date_range(missing_target, periods=4, freq="h")
    provenance = [{
        "target_timestamp": missing_target.isoformat(),
        "source_timeframe": "H1",
        "expected_source_timestamps": [item.isoformat() for item in expected],
        "observed_source_timestamps": [],
        "missing_source_timestamps": [item.isoformat() for item in expected],
        "sanitization_backed_missing_timestamps": [],
        "session_closed_timestamps": [],
        "unexplained_provider_missing_timestamps": [
            item.isoformat() for item in expected
        ],
        "omission_reason": "UPSTREAM_PROVIDER_GAP",
    }]
    metadata = _metadata(
        "EURUSD", "H4", resample_provenance=provenance
    )

    gaps = classify_gaps(
        pd.Series(["2026-08-17 00:00", "2026-08-17 08:00"]),
        "H4",
        "FOREX",
        acquisition_metadata=metadata,
    )

    assert gaps[0]["classification"] == "PROVIDER_GAP"
    assert gaps[0]["resample_provenance"] == provenance

"""Shared OHLC and acquisition-provenance contract for market datasets."""
from __future__ import annotations

import copy
import json
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd


PRICE_COLUMNS = ("open", "high", "low", "close")
SANITIZATION_REASONS = frozenset({
    "INVALID_OHLC_ENVELOPE",
    "NON_FINITE_OHLC",
    "NON_POSITIVE_OHLC",
})
ACQUISITION_METADATA_SCHEMA_VERSION = 1
H4_OMISSION_REASONS = frozenset({
    "INCOMPLETE_SOURCE_BLOCK",
    "SANITIZED_SOURCE_ROW",
    "SESSION_BOUNDARY",
    "UPSTREAM_PROVIDER_GAP",
})


class OHLCContractError(ValueError):
    """Raised when a frame violates ASTRA's canonical OHLC contract."""


def _price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = set(PRICE_COLUMNS) - set(frame.columns)
    if missing:
        raise OHLCContractError(f"Missing OHLC columns: {sorted(missing)}")
    return frame[list(PRICE_COLUMNS)].apply(pd.to_numeric, errors="coerce")


def invalid_ohlc_reasons(frame: pd.DataFrame) -> pd.Series:
    """Return one explicit, deterministic rejection reason per invalid row."""
    prices = _price_frame(frame)
    values = prices.to_numpy(float)
    finite = np.isfinite(values).all(axis=1)
    positive = (values > 0).all(axis=1)
    envelope = (
        (prices["low"] <= prices["high"])
        & prices["open"].between(prices["low"], prices["high"])
        & prices["close"].between(prices["low"], prices["high"])
    ).to_numpy(bool)

    reasons = pd.Series(index=frame.index, dtype="object")
    reasons.loc[~finite] = "NON_FINITE_OHLC"
    reasons.loc[finite & ~positive] = "NON_POSITIVE_OHLC"
    reasons.loc[finite & positive & ~envelope] = "INVALID_OHLC_ENVELOPE"
    return reasons


def validate_ohlc_frame(frame: pd.DataFrame) -> None:
    """Reject every row that downstream qualification would reject."""
    reasons = invalid_ohlc_reasons(frame).dropna()
    if reasons.empty:
        return
    counts = ", ".join(
        f"{reason}={count}" for reason, count in sorted(Counter(reasons).items())
    )
    raise OHLCContractError(
        f"Invalid OHLC rows rejected: {len(reasons)} ({counts})"
    )


def _timestamp_text(value: Any) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp.isoformat()


def sanitize_ohlc_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Drop only unequivocally invalid OHLC rows without changing valid values."""
    reasons = invalid_ohlc_reasons(frame)
    dropped = [
        {
            "timestamp": _timestamp_text(frame.at[index, "timestamp"]),
            "reason": str(reason),
        }
        for index, reason in reasons.dropna().items()
    ]
    valid = frame.loc[reasons.isna()].copy().reset_index(drop=True)
    return valid, dropped


def _validate_resample_provenance(items: Any) -> list[dict]:
    if not isinstance(items, list):
        raise OHLCContractError(
            "Acquisition metadata resample_provenance must be a list"
        )
    required = {
        "target_timestamp",
        "source_timeframe",
        "expected_source_timestamps",
        "observed_source_timestamps",
        "missing_source_timestamps",
        "sanitization_backed_missing_timestamps",
        "session_closed_timestamps",
        "unexplained_provider_missing_timestamps",
        "omission_reason",
    }
    targets: set[str] = set()
    normalized: list[dict] = []
    for raw in items:
        if not isinstance(raw, dict) or required - set(raw):
            raise OHLCContractError(
                "Acquisition metadata resample provenance item is incomplete"
            )
        item = copy.deepcopy(raw)
        target = _timestamp_text(item["target_timestamp"])
        if target in targets:
            raise OHLCContractError(
                "Acquisition metadata has duplicate resample targets"
            )
        targets.add(target)
        item["target_timestamp"] = target
        if item["source_timeframe"] != "H1":
            raise OHLCContractError("Resample provenance source must be H1")

        timestamp_fields = (
            "expected_source_timestamps",
            "observed_source_timestamps",
            "missing_source_timestamps",
            "sanitization_backed_missing_timestamps",
            "session_closed_timestamps",
            "unexplained_provider_missing_timestamps",
        )
        sets: dict[str, set[str]] = {}
        for field in timestamp_fields:
            values = item[field]
            if not isinstance(values, list):
                raise OHLCContractError(
                    f"Resample provenance {field} must be a list"
                )
            converted = [_timestamp_text(value) for value in values]
            if len(converted) != len(set(converted)):
                raise OHLCContractError(
                    f"Resample provenance {field} has duplicate timestamps"
                )
            item[field] = converted
            sets[field] = set(converted)

        expected = sets["expected_source_timestamps"]
        observed = sets["observed_source_timestamps"]
        missing = sets["missing_source_timestamps"]
        if len(expected) != 4 or observed & missing or observed | missing != expected:
            raise OHLCContractError(
                "Resample provenance expected/observed/missing sets are inconsistent"
            )
        expected_order = [
            _timestamp_text(pd.Timestamp(target) + pd.Timedelta(hours=offset))
            for offset in range(4)
        ]
        if item["expected_source_timestamps"] != expected_order:
            raise OHLCContractError(
                "Resample provenance expected source block is inconsistent"
            )
        causes = (
            sets["sanitization_backed_missing_timestamps"],
            sets["session_closed_timestamps"],
            sets["unexplained_provider_missing_timestamps"],
        )
        if any(cause - missing for cause in causes):
            raise OHLCContractError(
                "Resample provenance cause is not a missing source timestamp"
            )
        if any(
            causes[left] & causes[right]
            for left in range(3)
            for right in range(left + 1, 3)
        ):
            raise OHLCContractError("Resample provenance causes overlap")
        if set().union(*causes) != missing:
            raise OHLCContractError(
                "Resample provenance does not explain every missing timestamp"
            )
        reason = item["omission_reason"]
        if reason not in H4_OMISSION_REASONS:
            raise OHLCContractError("Resample provenance omission reason is invalid")
        sanitized, session_closed, unexplained = causes
        expected_reason = (
            "UPSTREAM_PROVIDER_GAP"
            if unexplained
            else "SESSION_BOUNDARY"
            if session_closed and not sanitized
            else "SANITIZED_SOURCE_ROW"
            if sanitized and not session_closed
            else "INCOMPLETE_SOURCE_BLOCK"
        )
        if reason != expected_reason:
            raise OHLCContractError(
                "Resample provenance omission reason contradicts its causes"
            )
        normalized.append(item)
    return normalized


def acquisition_metadata_dict(value: Any) -> dict | None:
    """Decode DB/evidence metadata without returning mutable shared state."""
    if value in (None, ""):
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise OHLCContractError("Acquisition metadata is not valid JSON") from exc
    if not isinstance(value, dict):
        raise OHLCContractError("Acquisition metadata must be an object")
    return copy.deepcopy(value)


def validate_acquisition_metadata(
    value: Any,
    *,
    provider: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    dataset_sha256: str | None = None,
) -> dict:
    """Validate additive acquisition metadata and its dataset association."""
    metadata = acquisition_metadata_dict(value)
    if metadata is None:
        raise OHLCContractError("Acquisition metadata is missing")

    required = {
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
    }
    missing = required - set(metadata)
    if missing:
        raise OHLCContractError(
            f"Acquisition metadata fields are missing: {sorted(missing)}"
        )
    if metadata["schema_version"] != ACQUISITION_METADATA_SCHEMA_VERSION:
        raise OHLCContractError("Acquisition metadata schema version is unsupported")

    for field in (
        "requested_bars",
        "raw_closed_rows",
        "invalid_rows_dropped",
        "valid_rows_before_tail",
        "returned_rows",
    ):
        value = metadata[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise OHLCContractError(f"Acquisition metadata {field} is invalid")

    dropped_rows = metadata["dropped_rows"]
    if not isinstance(dropped_rows, list):
        raise OHLCContractError("Acquisition metadata dropped_rows must be a list")
    if metadata["invalid_rows_dropped"] != len(dropped_rows):
        raise OHLCContractError("Acquisition metadata dropped-row count is inconsistent")
    if (
        metadata["raw_closed_rows"] - metadata["invalid_rows_dropped"]
        != metadata["valid_rows_before_tail"]
    ):
        raise OHLCContractError("Acquisition metadata valid-row count is inconsistent")
    if metadata["returned_rows"] > metadata["valid_rows_before_tail"]:
        raise OHLCContractError("Acquisition metadata returned-row count is inconsistent")
    if metadata["returned_rows"] > metadata["requested_bars"]:
        raise OHLCContractError("Acquisition metadata exceeds requested bars")

    timestamps: set[str] = set()
    for item in dropped_rows:
        if not isinstance(item, dict) or set(("timestamp", "reason")) - set(item):
            raise OHLCContractError("Acquisition metadata dropped row is incomplete")
        timestamp = _timestamp_text(item["timestamp"])
        if timestamp in timestamps:
            raise OHLCContractError("Acquisition metadata has duplicate dropped timestamps")
        timestamps.add(timestamp)
        if item["reason"] not in SANITIZATION_REASONS:
            raise OHLCContractError("Acquisition metadata has an unknown drop reason")
        item["timestamp"] = timestamp

    expected_closures = metadata.get("expected_market_closures", [])
    if not isinstance(expected_closures, list):
        raise OHLCContractError(
            "Acquisition metadata expected_market_closures must be a list"
        )
    normalized_closures: list[str] = []
    for item in expected_closures:
        timestamp = _timestamp_text(item)
        if timestamp in normalized_closures:
            raise OHLCContractError(
                "Acquisition metadata has duplicate expected market closures"
            )
        normalized_closures.append(timestamp)
    if expected_closures:
        metadata["expected_market_closures"] = normalized_closures

    if "resample_provenance" in metadata:
        metadata["resample_provenance"] = _validate_resample_provenance(
            metadata["resample_provenance"]
        )

    expected = (
        ("provider", provider),
        ("symbol", symbol.upper() if symbol else None),
        ("timeframe", timeframe.upper() if timeframe else None),
    )
    for field, wanted in expected:
        if wanted is not None and metadata[field] != wanted:
            raise OHLCContractError(
                f"Acquisition metadata {field} does not match {wanted}"
            )
    if dataset_sha256 is not None:
        if metadata.get("dataset_sha256") != dataset_sha256:
            raise OHLCContractError(
                "Acquisition metadata dataset_sha256 does not match the dataset"
            )
    return metadata


def encode_acquisition_metadata(value: Any) -> str | None:
    """Return stable JSON for additive SQLite persistence."""
    metadata = acquisition_metadata_dict(value)
    if metadata is None:
        return None
    return json.dumps(metadata, sort_keys=True, separators=(",", ":"))


__all__ = [
    "ACQUISITION_METADATA_SCHEMA_VERSION",
    "H4_OMISSION_REASONS",
    "OHLCContractError",
    "PRICE_COLUMNS",
    "SANITIZATION_REASONS",
    "acquisition_metadata_dict",
    "encode_acquisition_metadata",
    "invalid_ohlc_reasons",
    "sanitize_ohlc_frame",
    "validate_acquisition_metadata",
    "validate_ohlc_frame",
]

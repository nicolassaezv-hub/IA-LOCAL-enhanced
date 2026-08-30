#!/usr/bin/env python3
"""Read-only qualification harness for ASTRA's complete declared symbol universe."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import sqlite3
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from forex.data.data_router import DataRouter, _detect_asset_type
from forex.data.indicator_delta import INDICATOR_MIN_HISTORY
from forex.data.market_time_grid import (
    MarketTimeGrid,
    MarketTimeGridError,
    resolve_market_time_grid,
)
from forex.data.ohlc_contract import (
    acquisition_metadata_dict,
    invalid_ohlc_reasons,
    validate_acquisition_metadata,
)
from forex.data.session_authority import (
    SessionAuthority,
    SessionState,
    classify_authorized_timestamp,
)
from forex.data.rolling_dataset import ROLLING_WINDOW, exclude_incomplete_candles
from forex.data.symbol_catalog import UnsupportedSymbolError, catalog_codes, get_symbol_spec
from infra.db.database import DatabaseAdapter, configured_sqlite_path
from runtime_paths import forex_dataset_path
from scheduler.autonomous_scheduler import TIMEFRAMES


def _read_pair_config() -> dict[str, dict[str, float]]:
    """Read the ML declaration without importing the prediction package."""
    source = PROJECT_ROOT / "forex" / "prediction" / "dataset_builder.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "PAIR_CONFIG"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            return {
                "".join(
                    character
                    for character in str(symbol).upper()
                    if character.isalnum()
                ): dict(config)
                for symbol, config in value.items()
            }
    raise RuntimeError(f"PAIR_CONFIG not found in {source}")


PAIR_CONFIG = _read_pair_config()


PROBE_BARS = ROLLING_WINDOW + 1
REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
PRICE_COLUMNS = ("open", "high", "low", "close")
TIMEFRAME_DURATION = {
    "H1": pd.Timedelta(hours=1),
    "H4": pd.Timedelta(hours=4),
    "D1": pd.Timedelta(days=1),
}


class ReadOnlySQLiteDatabase:
    """Minimal registry reader that cannot initialize or mutate production DB state."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path).resolve()
        if not self.db_path.is_file():
            raise FileNotFoundError(f"SQLite database does not exist: {self.db_path}")

    def _query(self, query: str, parameters: tuple[Any, ...] = ()) -> list[dict]:
        uri = f"{self.db_path.as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def get_active_symbols(self) -> list[dict]:
        return self._query(
            "SELECT * FROM supported_symbols WHERE status='active' ORDER BY symbol_code"
        )

    def get_data_symbols(self) -> list[dict]:
        return self._query(
            "SELECT * FROM supported_symbols "
            "WHERE status IN ('qualified','active') ORDER BY symbol_code"
        )

    def get_dataset_registry(self, symbol: str = None, tf: str = None) -> list[dict]:
        query = "SELECT * FROM dataset_registry WHERE 1=1"
        parameters: list[Any] = []
        if symbol:
            query += " AND symbol=?"
            parameters.append(symbol)
        if tf:
            query += " AND timeframe=?"
            parameters.append(tf)
        query += " ORDER BY symbol, timeframe"
        return self._query(query, tuple(parameters))


def get_read_only_database() -> ReadOnlySQLiteDatabase:
    engine = os.environ.get("ASTRA_DB_ENGINE", "sqlite").lower()
    if engine != "sqlite":
        raise RuntimeError(
            f"Read-only qualification supports the current SQLite engine, not {engine!r}"
        )
    return ReadOnlySQLiteDatabase(configured_sqlite_path())


def normalize_symbol(value: str) -> str:
    return str(value or "").strip().upper()


def declared_code_universe() -> tuple[str, ...]:
    """Return the central operational catalog; PAIR_CONFIG is not authority."""
    return tuple(sorted(catalog_codes()))


DECLARED_CODE_SYMBOLS = declared_code_universe()


def expected_asset_class(symbol: str) -> str:
    try:
        return get_symbol_spec(symbol).asset_class
    except UnsupportedSymbolError:
        return "UNKNOWN"


def _routing_asset_class(asset_class: str) -> str:
    return "commodity" if asset_class == "METAL" else asset_class.lower()


@dataclass(frozen=True)
class RouteSpec:
    symbol: str
    asset_class: str
    astra_supported: bool
    declarations: tuple[str, ...]
    pair_config: bool
    provider_primary: str | None
    provider_secondary: str | None
    provider_fallback: str | None
    primary_external_ticker: str | None
    secondary_external_ticker: str | None
    fallback_external_ticker: str | None
    primary_ticker_catalogued: bool
    fallback_ticker_explicit: bool
    h1_supported: bool
    h4_supported: bool
    d1_supported: bool
    blocked_routes: tuple[str, ...]


def route_spec(symbol: str) -> RouteSpec:
    symbol = normalize_symbol(symbol)
    try:
        spec = get_symbol_spec(symbol)
    except UnsupportedSymbolError:
        return RouteSpec(
            symbol=symbol,
            asset_class="UNKNOWN",
            astra_supported=False,
            declarations=(),
            pair_config=symbol in PAIR_CONFIG,
            provider_primary=None,
            provider_secondary=None,
            provider_fallback=None,
            primary_external_ticker=None,
            secondary_external_ticker=None,
            fallback_external_ticker=None,
            primary_ticker_catalogued=False,
            fallback_ticker_explicit=False,
            h1_supported=False,
            h4_supported=False,
            d1_supported=False,
            blocked_routes=(),
        )
    declarations = ["symbol_catalog"]
    if spec.legacy_default_active:
        declarations.append("scheduler_default")
    if symbol in PAIR_CONFIG:
        declarations.append("pair_config")
    fallback = spec.fallback
    secondary = spec.secondary
    return RouteSpec(
        symbol=symbol,
        asset_class=spec.asset_class,
        astra_supported=True,
        declarations=tuple(declarations),
        pair_config=symbol in PAIR_CONFIG,
        provider_primary=spec.primary.provider,
        provider_secondary=secondary.provider if secondary else None,
        provider_fallback=fallback.provider if fallback else None,
        primary_external_ticker=spec.primary.external_ticker,
        secondary_external_ticker=(
            secondary.external_ticker if secondary else None
        ),
        fallback_external_ticker=fallback.external_ticker if fallback else None,
        primary_ticker_catalogued=True,
        fallback_ticker_explicit=fallback is not None,
        h1_supported="H1" in spec.supported_timeframes,
        h4_supported="H4" in spec.supported_timeframes,
        d1_supported="D1" in spec.supported_timeframes,
        blocked_routes=spec.blocked_routes,
    )


def _new_stage(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "PASS",
        "blocking": False,
        "errors": [],
        "warnings": [],
        "details": {},
    }


def _fail(stage: dict[str, Any], message: str) -> None:
    stage["status"] = "FAIL"
    stage["blocking"] = True
    stage["errors"].append(str(message))


def _warn(stage: dict[str, Any], message: str, *, blocking: bool) -> None:
    if stage["status"] != "FAIL":
        stage["status"] = "WARNING"
    stage["blocking"] = bool(stage["blocking"] or blocking)
    stage["warnings"].append(str(message))


def _utc_naive(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _independent_indicators(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Recalculate the persisted indicator contract without calling ASTRA helpers."""
    close = pd.to_numeric(frame["close"], errors="coerce")
    high = pd.to_numeric(frame["high"], errors="coerce")
    low = pd.to_numeric(frame["low"], errors="coerce")

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rsi = 100 - (100 / (1 + avg_gain / (avg_loss + 1e-10)))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = true_range.ewm(span=14, adjust=False).mean()

    bb_mid = close.rolling(window=20, min_periods=1).mean()
    bb_std = close.rolling(window=20, min_periods=1).std().fillna(0)
    returns = close.pct_change().fillna(0)

    return {
        "RSI_14": rsi,
        "MACD": macd,
        "MACD_signal": macd_signal,
        "MACD_hist": macd - macd_signal,
        "ATR_14": atr,
        "EMA20": close.ewm(span=20, adjust=False).mean(),
        "EMA50": close.ewm(span=50, adjust=False).mean(),
        "EMA200": close.ewm(span=200, adjust=False).mean(),
        "BB_upper": bb_mid + 2.0 * bb_std,
        "BB_lower": bb_mid - 2.0 * bb_std,
        "returns": returns,
        "volatility_24h": returns.rolling(24, min_periods=1).std().fillna(0),
    }


def _indicator_start(column: str) -> int:
    minimum = INDICATOR_MIN_HISTORY[column]
    if column == "returns":
        return 1
    if column == "volatility_24h":
        # The persisted first return may use the candle immediately before the
        # rolling-2000 slice.  The first independent 24-return window is index 24.
        return minimum
    if column in {"BB_upper", "BB_lower"}:
        return minimum - 1
    return min(ROLLING_WINDOW - 1, minimum * 5 - 1)


def validate_indicators(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], list[str]]:
    expected = _independent_indicators(frame)
    report: list[dict[str, Any]] = []
    failures: list[str] = []
    for column in INDICATOR_MIN_HISTORY:
        if column not in frame.columns:
            failures.append(f"Missing contractual indicator: {column}")
            report.append({
                "indicator": column,
                "rows_compared": 0,
                "max_abs_error": None,
                "max_rel_error": None,
                "status": "FAIL",
            })
            continue

        start = _indicator_start(column)
        actual = pd.to_numeric(frame[column].iloc[start:], errors="coerce").to_numpy(float)
        calculated = expected[column].iloc[start:].to_numpy(float)
        unexpected_non_finite = int((~np.isfinite(actual)).sum())
        if unexpected_non_finite:
            failures.append(
                f"Indicator {column} has {unexpected_non_finite} non-finite value(s) "
                "after its allowed warm-up"
            )
        comparable = np.isfinite(actual) & np.isfinite(calculated)
        rows_compared = int(comparable.sum())
        if rows_compared == 0:
            failures.append(f"Indicator {column} has no independently comparable rows")
            report.append({
                "indicator": column,
                "rows_compared": 0,
                "max_abs_error": None,
                "max_rel_error": None,
                "status": "FAIL",
            })
            continue

        difference = np.abs(actual[comparable] - calculated[comparable])
        denominator = np.maximum(np.abs(calculated[comparable]), 1e-12)
        max_abs = float(difference.max())
        max_rel = float((difference / denominator).max())
        passed = bool(np.allclose(
            actual[comparable], calculated[comparable], rtol=1e-6, atol=1e-9
        ))
        if not passed:
            failures.append(
                f"Indicator {column} differs from independent recalculation "
                f"(max_abs={max_abs:.6g}, max_rel={max_rel:.6g})"
            )
        report.append({
            "indicator": column,
            "rows_compared": rows_compared,
            "max_abs_error": max_abs,
            "max_rel_error": max_rel,
            "status": "PASS" if passed else "FAIL",
        })
    return report, failures


def _classify_gaps_legacy(
    timestamps: pd.Series,
    timeframe: str,
    asset_class: str,
    *,
    acquisition_metadata: dict[str, Any] | str | None = None,
    session_authority: SessionAuthority | None = None,
    provider: str | None = None,
) -> list[dict[str, Any]]:
    duration = TIMEFRAME_DURATION[timeframe]
    values = pd.Series(pd.to_datetime(timestamps, utc=True)).dt.tz_localize(None)
    metadata = acquisition_metadata_dict(acquisition_metadata)
    sanitized_timestamps = {
        _utc_naive(item["timestamp"])
        for item in (metadata or {}).get("dropped_rows", [])
        if isinstance(item, dict) and item.get("timestamp")
    }
    resample_items = (metadata or {}).get("resample_provenance", [])
    # Ordinary acquisition metadata is not an authority for market sessions.
    # EXPECTED_MARKET_CLOSURE must remain unavailable until ASTRA has an
    # explicitly authorized calendar/source contract.
    gaps: list[dict[str, Any]] = []
    for previous, current in zip(values.iloc[:-1], values.iloc[1:]):
        delta = current - previous
        if delta == duration:
            continue
        if delta <= pd.Timedelta(0) or delta < duration:
            classification = "INVALID_GAP"
        else:
            missing = list(pd.date_range(
                previous + duration,
                current - duration,
                freq=duration,
            ))
            expected_market = [
                timestamp
                for timestamp in missing
                if not (asset_class != "CRYPTO" and timestamp.dayofweek >= 5)
            ]
            if expected_market and all(
                timestamp in sanitized_timestamps for timestamp in expected_market
            ):
                classification = "SANITIZED_PROVIDER_ROW"
            elif expected_market and all(
                classify_authorized_timestamp(
                    session_authority,
                    timestamp,
                    asset_class=asset_class,
                    provider=provider,
                ) == SessionState.CLOSED
                for timestamp in expected_market
            ):
                # Only a validated authority may establish a market closure;
                # ordinary acquisition metadata can never supply this evidence.
                classification = "MARKET_SESSION_CLOSED"
            elif not expected_market and asset_class != "CRYPTO":
                classification = "WEEKEND"
            else:
                classification = "PROVIDER_GAP"
        gap = {
            "previous": str(previous),
            "current": str(current),
            "duration_seconds": float(delta.total_seconds()),
            "classification": classification,
        }
        if delta > duration and timeframe == "H4":
            missing_targets = {
                _utc_naive(timestamp).isoformat() for timestamp in missing
            }
            matching = [
                item
                for item in resample_items
                if isinstance(item, dict)
                and item.get("target_timestamp")
                and _utc_naive(item["target_timestamp"]).isoformat()
                in missing_targets
            ]
            if matching:
                gap["resample_provenance"] = matching
        gaps.append(gap)
    return gaps


def _classify_market_time_gaps(
    timestamps: pd.Series,
    timeframe: str,
    asset_class: str,
    *,
    grid: MarketTimeGrid,
    acquisition_metadata: dict[str, Any] | str | None,
    provider: str,
    symbol: str,
) -> list[dict[str, Any]]:
    """Classify missing opens on an authorized broker-local candle grid."""
    duration = TIMEFRAME_DURATION[timeframe]
    utc_values = pd.Series(pd.to_datetime(timestamps, utc=True))
    local_values = utc_values.dt.tz_convert(grid.timezone).dt.tz_localize(None)
    metadata = acquisition_metadata_dict(acquisition_metadata)
    sanitized_timestamps = {
        _utc_naive(item["timestamp"])
        for item in (metadata or {}).get("dropped_rows", [])
        if isinstance(item, dict) and item.get("timestamp")
    }
    resample_items = (metadata or {}).get("resample_provenance", [])
    authority = grid.session_authority
    descriptor = authority.descriptor
    gaps: list[dict[str, Any]] = []
    for index in range(1, len(utc_values)):
        previous_utc = utc_values.iloc[index - 1]
        current_utc = utc_values.iloc[index]
        previous_local = local_values.iloc[index - 1]
        current_local = local_values.iloc[index]
        utc_delta = current_utc - previous_utc
        local_delta = current_local - previous_local
        if local_delta == duration and utc_delta > pd.Timedelta(0):
            continue
        if (
            utc_delta <= pd.Timedelta(0)
            or local_delta <= pd.Timedelta(0)
            or local_delta < duration
        ):
            gaps.append({
                "previous": str(previous_utc.tz_localize(None)),
                "current": str(current_utc.tz_localize(None)),
                "duration_seconds": float(utc_delta.total_seconds()),
                "classification": "INVALID_GAP",
                "market_timezone": grid.timezone,
                "local_previous": str(previous_local),
                "local_current": str(current_local),
            })
            continue

        missing_local = list(pd.date_range(
            previous_local + duration,
            current_local - duration,
            freq=duration,
        ))
        explanation_counts: dict[str, int] = {}
        unexplained_local: list[str] = []
        missing_utc: list[pd.Timestamp] = []
        evidence_by_hash: dict[str, dict[str, Any]] = {}
        for local_timestamp in missing_local:
            if grid.is_weekend(local_timestamp):
                cause = "WEEKEND"
            else:
                try:
                    utc_timestamp = grid.wall_time_to_utc(local_timestamp)
                    missing_utc.append(utc_timestamp)
                except MarketTimeGridError:
                    cause = "UNEXPLAINED"
                    unexplained_local.append(str(local_timestamp))
                else:
                    if utc_timestamp in sanitized_timestamps:
                        cause = "SANITIZED"
                    else:
                        state = classify_authorized_timestamp(
                            authority,
                            utc_timestamp.tz_localize("UTC"),
                            asset_class=asset_class,
                            provider=provider,
                            symbol=symbol,
                            clock_profile_id=grid.profile.profile_id,
                            server_identity=grid.profile.server_identity,
                        )
                        if state == SessionState.CLOSED:
                            cause = "SESSION_CLOSED"
                            evidence = getattr(
                                authority, "evidence_for_timestamp", lambda _value: None
                            )(utc_timestamp.tz_localize("UTC"))
                            if isinstance(evidence, dict) and evidence.get(
                                "evidence_hash"
                            ):
                                evidence_by_hash[evidence["evidence_hash"]] = evidence
                        else:
                            cause = "UNEXPLAINED"
                            unexplained_local.append(str(local_timestamp))
            explanation_counts[cause] = explanation_counts.get(cause, 0) + 1

        if explanation_counts.get("UNEXPLAINED"):
            classification = "PROVIDER_GAP"
        elif explanation_counts.get("SESSION_CLOSED"):
            classification = "MARKET_SESSION_CLOSED"
        elif explanation_counts.get("SANITIZED"):
            classification = "SANITIZED_PROVIDER_ROW"
        else:
            classification = "WEEKEND"
        gap = {
            "previous": str(previous_utc.tz_localize(None)),
            "current": str(current_utc.tz_localize(None)),
            "duration_seconds": float(utc_delta.total_seconds()),
            "classification": classification,
            "market_timezone": grid.timezone,
            "local_previous": str(previous_local),
            "local_current": str(current_local),
            "timezone_profile_id": grid.profile.profile_id,
            "session_authority_id": descriptor.authority_id,
            "session_authority_evidence_hash": descriptor.evidence_hash,
            "explanation_counts": explanation_counts,
            "unexplained_local_timestamps": unexplained_local,
            "session_evidence": list(evidence_by_hash.values()),
        }
        if timeframe == "H4" and missing_utc:
            missing_targets = {
                timestamp.isoformat() for timestamp in missing_utc
            }
            matching = [
                item
                for item in resample_items
                if isinstance(item, dict)
                and item.get("target_timestamp")
                and _utc_naive(item["target_timestamp"]).isoformat()
                in missing_targets
            ]
            if matching:
                gap["resample_provenance"] = matching
        gaps.append(gap)
    return gaps


def classify_gaps(
    timestamps: pd.Series,
    timeframe: str,
    asset_class: str,
    *,
    acquisition_metadata: dict[str, Any] | str | None = None,
    session_authority: SessionAuthority | None = None,
    provider: str | None = None,
    symbol: str | None = None,
) -> list[dict[str, Any]]:
    """Classify gaps using broker time only when exact provenance authorizes it."""
    grid = resolve_market_time_grid(
        acquisition_metadata,
        provider=provider,
        symbol=symbol,
        asset_class=asset_class,
    )
    if grid is not None:
        return _classify_market_time_gaps(
            timestamps,
            timeframe,
            asset_class,
            grid=grid,
            acquisition_metadata=acquisition_metadata,
            provider=provider,
            symbol=symbol,
        )
    return _classify_gaps_legacy(
        timestamps,
        timeframe,
        asset_class,
        acquisition_metadata=acquisition_metadata,
        session_authority=session_authority,
        provider=provider,
    )


def _match_provider_frame(
    physical: pd.DataFrame,
    provider: pd.DataFrame,
) -> dict[str, Any]:
    columns = ["timestamp", *PRICE_COLUMNS]
    left = physical[columns].copy()
    right = provider[columns].copy()
    left["timestamp"] = pd.to_datetime(left["timestamp"], utc=True).dt.tz_localize(None)
    right["timestamp"] = pd.to_datetime(right["timestamp"], utc=True).dt.tz_localize(None)
    merged = left.merge(right, on="timestamp", suffixes=("_csv", "_provider"))
    timestamp_sets_equal = bool(
        len(left) == len(right)
        and len(merged) == len(left)
        and left["timestamp"].reset_index(drop=True).equals(
            right["timestamp"].reset_index(drop=True)
        )
    )
    if merged.empty:
        return {
            "status": "NO_OVERLAP",
            "rows_compared": 0,
            "max_relative_error": None,
            "physical_rows": int(len(left)),
            "provider_rows": int(len(right)),
            "timestamp_sets_equal": False,
        }
    errors = []
    for column in PRICE_COLUMNS:
        csv_values = pd.to_numeric(merged[f"{column}_csv"], errors="coerce").to_numpy(float)
        provider_values = pd.to_numeric(
            merged[f"{column}_provider"], errors="coerce"
        ).to_numpy(float)
        denominator = np.maximum(np.abs(provider_values), 1e-12)
        errors.extend((np.abs(csv_values - provider_values) / denominator).tolist())
    maximum = float(np.nanmax(errors)) if errors else 0.0
    matched = timestamp_sets_equal and maximum <= 1e-5
    return {
        "status": "MATCH" if matched else "MISMATCH",
        "rows_compared": int(len(merged)),
        "max_relative_error": maximum,
        "physical_rows": int(len(left)),
        "provider_rows": int(len(right)),
        "timestamp_sets_equal": timestamp_sets_equal,
    }


def _normalize_probe_frame(
    frame: pd.DataFrame,
    symbol: str,
    timeframe: str,
    *,
    now: Any = None,
) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("provider returned no rows")
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"provider frame missing columns: {sorted(missing)}")
    normalized = frame.copy()
    parsed = pd.to_datetime(normalized["timestamp"], utc=True, errors="coerce")
    if parsed.isna().any():
        raise ValueError("provider frame contains invalid timestamps")
    normalized["timestamp"] = parsed.dt.tz_localize(None)
    for column in REQUIRED_COLUMNS[1:]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    if normalized["timestamp"].duplicated().any():
        raise ValueError("provider frame contains duplicate timestamps")
    if not normalized["timestamp"].is_monotonic_increasing:
        raise ValueError("provider frame is not chronologically ordered")
    normalized = normalized.reset_index(drop=True)
    normalized = exclude_incomplete_candles(normalized, timeframe, now=now)
    if "pair" in normalized.columns:
        observed = {normalize_symbol(value) for value in normalized["pair"].dropna().unique()}
        if observed and observed != {symbol}:
            raise ValueError(f"provider returned another symbol: {sorted(observed)}")
    return normalized


def validate_dataset_frame(
    frame: pd.DataFrame,
    symbol: str,
    timeframe: str,
    *,
    now: Any = None,
    acquisition_metadata: dict[str, Any] | str | None = None,
    session_authority: SessionAuthority | None = None,
    provider: str | None = None,
) -> tuple[dict[str, Any], pd.DataFrame | None]:
    """Validate every physical row and return normalized evidence."""
    stage = _new_stage(timeframe)
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        _fail(stage, f"Missing required columns: {sorted(missing)}")
        return stage, None

    normalized = frame.copy()
    parsed = pd.to_datetime(normalized["timestamp"], utc=True, errors="coerce")
    invalid_timestamps = int(parsed.isna().sum())
    if invalid_timestamps:
        _fail(stage, f"Invalid timestamps: {invalid_timestamps}")
        return stage, None
    normalized["timestamp"] = parsed.dt.tz_localize(None)

    parsed_acquisition = None
    if acquisition_metadata is not None:
        try:
            parsed_acquisition = validate_acquisition_metadata(
                acquisition_metadata,
                provider=provider,
                symbol=symbol,
                timeframe=timeframe,
            )
            stage["details"]["acquisition_metadata"] = parsed_acquisition
        except Exception as exc:
            _fail(stage, f"Invalid acquisition metadata: {exc}")

    stage["details"]["physical_rows"] = int(len(normalized))
    if len(normalized) != ROLLING_WINDOW:
        _fail(stage, f"Physical rows are {len(normalized)}; expected {ROLLING_WINDOW}")
    duplicate_timestamps = int(normalized["timestamp"].duplicated().sum())
    duplicate_rows = int(normalized.duplicated().sum())
    stage["details"]["duplicate_timestamps"] = duplicate_timestamps
    stage["details"]["duplicate_rows"] = duplicate_rows
    if duplicate_timestamps:
        _fail(stage, f"Duplicate timestamps: {duplicate_timestamps}")
    if duplicate_rows:
        _fail(stage, f"Completely duplicated rows: {duplicate_rows}")
    if not normalized["timestamp"].is_monotonic_increasing:
        _fail(stage, "Timestamps are not monotonically increasing")
    if duplicate_timestamps == 0 and len(normalized) > 1:
        if not (normalized["timestamp"].diff().iloc[1:] > pd.Timedelta(0)).all():
            _fail(stage, "Timestamps are not strictly increasing")

    nan_inf: dict[str, dict[str, int]] = {}
    for column in normalized.columns:
        numeric = pd.to_numeric(normalized[column], errors="coerce")
        if column == "timestamp" or not pd.api.types.is_numeric_dtype(normalized[column]):
            continue
        values = numeric.to_numpy(float)
        nan_inf[column] = {
            "nan": int(np.isnan(values).sum()),
            "positive_inf": int(np.isposinf(values).sum()),
            "negative_inf": int(np.isneginf(values).sum()),
        }
    stage["details"]["nan_inf"] = nan_inf

    for column in REQUIRED_COLUMNS[1:]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        values = normalized[column].to_numpy(float)
        if not np.isfinite(values).all():
            _fail(stage, f"{column} contains NaN or infinity")

    if all(np.isfinite(normalized[column].to_numpy(float)).all() for column in PRICE_COLUMNS):
        invalid_count = int(invalid_ohlc_reasons(normalized).notna().sum())
        stage["details"]["invalid_ohlc_rows"] = invalid_count
        if invalid_count:
            _fail(stage, f"Malformed/non-positive OHLC rows: {invalid_count}")

    if np.isfinite(normalized["volume"].to_numpy(float)).all():
        negative_volume = int((normalized["volume"] < 0).sum())
        zero_volume = int((normalized["volume"] == 0).sum())
        stage["details"]["volume"] = {
            "negative_rows": negative_volume,
            "zero_rows": zero_volume,
            "provenance": "UNVERIFIED_PROVIDER_VOLUME",
        }
        if negative_volume:
            _fail(stage, f"Negative volume rows: {negative_volume}")
        if zero_volume:
            _warn(
                stage,
                f"Volume is zero in {zero_volume} row(s); provider volume may be unavailable",
                blocking=False,
            )

    if "spread" in normalized.columns:
        spread = pd.to_numeric(normalized["spread"], errors="coerce")
        if not np.isfinite(spread.to_numpy(float)).all() or (spread < 0).any():
            _fail(stage, "Spread contains invalid or negative values")
        proxy = (normalized["high"] - normalized["low"]) * 0.05
        derived = bool(np.allclose(spread, proxy, rtol=1e-9, atol=1e-12))
        stage["details"]["spread"] = {
            "provenance": "DERIVED_RANGE_PROXY" if derived else "UNVERIFIED",
            "is_broker_spread": False if derived else None,
        }

    if "pair" not in normalized.columns:
        _warn(stage, "CSV has no pair column to prove cross-symbol isolation", blocking=True)
    else:
        observed_pairs = {
            normalize_symbol(value) for value in normalized["pair"].dropna().unique()
        }
        stage["details"]["observed_pairs"] = sorted(observed_pairs)
        if observed_pairs != {symbol}:
            _fail(stage, f"CSV pair values do not match {symbol}: {sorted(observed_pairs)}")

    cutoff = _utc_naive(pd.Timestamp.now(tz="UTC") if now is None else now)
    future_count = int((normalized["timestamp"] > cutoff).sum())
    closed = exclude_incomplete_candles(normalized, timeframe, now=cutoff)
    stage["details"]["future_timestamps"] = future_count
    stage["details"]["closed_rows"] = int(len(closed))
    if future_count:
        _fail(stage, f"Future timestamps: {future_count}")
    if len(closed) != len(normalized):
        _fail(stage, f"Open candles present: {len(normalized) - len(closed)}")

    gaps = classify_gaps(
        normalized["timestamp"],
        timeframe,
        expected_asset_class(symbol),
        acquisition_metadata=parsed_acquisition,
        session_authority=session_authority,
        provider=provider,
        symbol=symbol,
    )
    classifications: dict[str, int] = {}
    for gap in gaps:
        key = gap["classification"]
        classifications[key] = classifications.get(key, 0) + 1
    stage["details"]["gaps"] = {
        "count": len(gaps),
        "largest_seconds": max(
            (gap["duration_seconds"] for gap in gaps), default=0.0
        ),
        "classifications": classifications,
        "items": gaps,
    }
    invalid_gaps = classifications.get("INVALID_GAP", 0)
    provider_gaps = classifications.get("PROVIDER_GAP", 0)
    sanitized_gaps = classifications.get("SANITIZED_PROVIDER_ROW", 0)
    session_closed_gaps = classifications.get("MARKET_SESSION_CLOSED", 0)
    if invalid_gaps:
        _fail(stage, f"Invalid gaps: {invalid_gaps}")
    if provider_gaps:
        _warn(stage, f"Provider gaps requiring review: {provider_gaps}", blocking=True)
    if sanitized_gaps:
        _warn(
            stage,
            f"Known gaps backed by provider sanitization provenance: {sanitized_gaps}",
            blocking=False,
        )
    if session_closed_gaps:
        _warn(
            stage,
            f"Gaps backed by authoritative market-session evidence: "
            f"{session_closed_gaps}",
            blocking=False,
        )

    close_values = normalized["close"].to_numpy(float)
    returns = np.abs(np.diff(np.log(close_values))) if len(close_values) > 1 else np.array([])
    threshold = 0.75 if expected_asset_class(symbol) == "CRYPTO" else 0.25
    outlier_indices = np.where(returns > threshold)[0]
    stage["details"]["price_outliers"] = [
        {
            "from": str(normalized["timestamp"].iloc[index]),
            "to": str(normalized["timestamp"].iloc[index + 1]),
            "absolute_log_return": float(returns[index]),
        }
        for index in outlier_indices
    ]
    if len(outlier_indices):
        _warn(
            stage,
            f"Large price moves flagged for review: {len(outlier_indices)}",
            blocking=False,
        )

    indicator_report, indicator_failures = validate_indicators(normalized)
    stage["details"]["indicators"] = indicator_report
    for failure in indicator_failures:
        _fail(stage, failure)
    return stage, normalized


def _aggregate_comparison(
    lower: pd.DataFrame,
    higher: pd.DataFrame,
    *,
    lower_duration: pd.Timedelta,
    candles_per_group: int,
) -> dict[str, Any]:
    indexed = lower.set_index("timestamp")
    comparisons = []
    for _, row in higher.iterrows():
        start = row["timestamp"]
        required = [start + lower_duration * offset for offset in range(candles_per_group)]
        if not all(timestamp in indexed.index for timestamp in required):
            continue
        group = indexed.loc[required]
        expected = {
            "open": float(group["open"].iloc[0]),
            "high": float(group["high"].max()),
            "low": float(group["low"].min()),
            "close": float(group["close"].iloc[-1]),
        }
        errors = {
            column: abs(float(row[column]) - value) / max(abs(value), 1e-12)
            for column, value in expected.items()
        }
        comparisons.append({"timestamp": str(start), "relative_errors": errors})
    maxima = {
        column: max(
            (item["relative_errors"][column] for item in comparisons), default=None
        )
        for column in PRICE_COLUMNS
    }
    passed = bool(comparisons) and all(
        value is not None and value <= 1e-5 for value in maxima.values()
    )
    return {
        "rows_compared": len(comparisons),
        "max_relative_error": maxima,
        "status": "PASS" if passed else ("NO_OVERLAP" if not comparisons else "MISMATCH"),
        "items": comparisons,
    }


def validate_cross_timeframes(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Apply the harness cross-timeframe contract to any isolated frame set."""
    stage = _new_stage("CROSS-TIMEFRAME")
    if set(frames) != set(TIMEFRAMES):
        _fail(
            stage,
            f"Missing validated timeframe frames: "
            f"{sorted(set(TIMEFRAMES) - set(frames))}",
        )
        return stage

    latest_prices = {
        timeframe: float(frames[timeframe]["close"].iloc[-1])
        for timeframe in TIMEFRAMES
    }
    scale_ratio = max(latest_prices.values()) / min(latest_prices.values())
    stage["details"]["latest_close"] = latest_prices
    stage["details"]["latest_scale_ratio"] = scale_ratio
    if not math.isfinite(scale_ratio) or scale_ratio > 1.5:
        _fail(stage, f"Cross-timeframe price scale mismatch: ratio={scale_ratio:.6g}")

    h1_h4 = _aggregate_comparison(
        frames["H1"],
        frames["H4"],
        lower_duration=pd.Timedelta(hours=1),
        candles_per_group=4,
    )
    h4_d1 = _aggregate_comparison(
        frames["H4"],
        frames["D1"],
        lower_duration=pd.Timedelta(hours=4),
        candles_per_group=6,
    )
    stage["details"]["h1_to_h4"] = h1_h4
    stage["details"]["h4_to_d1"] = h4_d1
    for label, comparison in (("H1→H4", h1_h4), ("H4→D1", h4_d1)):
        if comparison["status"] != "PASS":
            _warn(
                stage,
                f"{label} aggregation is {comparison['status']}; "
                "quantify provider/calendar differences before activation",
                blocking=True,
            )
    return stage


class SymbolQualificationHarness:
    """Sequential, read-only orchestrator for registry, provider and CSV evidence."""

    def __init__(
        self,
        database: DatabaseAdapter,
        *,
        project_root: Path | str = PROJECT_ROOT,
        probe_providers: bool = False,
        now: Any = None,
    ):
        self.database = database
        self.project_root = Path(project_root).resolve()
        self.probe_providers = probe_providers
        self.now = now
        self._data_rows = list(database.get_data_symbols())
        self._data_by_symbol = {
            normalize_symbol(row.get("symbol_code", "")): dict(row)
            for row in self._data_rows
            if row.get("symbol_code")
        }

    def universe(self) -> tuple[str, ...]:
        return tuple(sorted(set(DECLARED_CODE_SYMBOLS) | set(self._data_by_symbol)))

    def _registry_stage(self, symbol: str) -> dict[str, Any]:
        stage = _new_stage("REGISTRY")
        row = self._data_by_symbol.get(symbol)
        stage["details"]["row"] = row
        stage["details"]["source"] = "DatabaseAdapter.get_data_symbols"
        if row is None:
            _warn(
                stage,
                "Symbol is declared in code but is not qualified/active for data",
                blocking=True,
            )
            return stage
        if normalize_symbol(row.get("symbol_code", "")) != symbol:
            _fail(stage, "supported_symbols symbol_code does not match requested symbol")
        if not str(row.get("display_name") or "").strip():
            _fail(stage, "supported_symbols display_name is empty")
        try:
            pip_value = float(row.get("pip_value"))
            if not math.isfinite(pip_value) or pip_value <= 0:
                raise ValueError
        except (TypeError, ValueError):
            _fail(stage, f"supported_symbols pip_value is invalid: {row.get('pip_value')!r}")
        if str(row.get("status") or "").lower() not in {"qualified", "active"}:
            _fail(
                stage,
                f"supported_symbols status is not data-enabled: {row.get('status')!r}",
            )
        try:
            added_at = pd.Timestamp(row.get("added_at"))
            if pd.isna(added_at):
                raise ValueError
        except Exception:
            _fail(stage, f"supported_symbols added_at is invalid: {row.get('added_at')!r}")
        return stage

    def _routing_stage(self, symbol: str) -> tuple[dict[str, Any], RouteSpec]:
        stage = _new_stage("ROUTING")
        spec = route_spec(symbol)
        stage["details"].update(asdict(spec))
        try:
            router_asset = _detect_asset_type(symbol)
        except UnsupportedSymbolError:
            router_asset = "unsupported"
        stage["details"]["router_asset_type"] = router_asset
        if not spec.astra_supported:
            _fail(
                stage,
                "Unsupported symbol: no explicit provider-router/catalog route; "
                "PAIR_CONFIG or supported_symbols alone is not provider support",
            )
        expected_route = _routing_asset_class(spec.asset_class)
        if router_asset != expected_route:
            _fail(
                stage,
                f"Asset routing mismatch: expected {expected_route}, DataRouter uses {router_asset}",
            )
        if spec.astra_supported and spec.provider_fallback is None:
            _warn(
                stage,
                "No semantically exact fallback is configured; primary provider is required",
                blocking=False,
            )
        for blocked_route in spec.blocked_routes:
            _warn(
                stage,
                blocked_route,
                blocking=False,
            )
        if spec.provider_primary == "MT5":
            _warn(
                stage,
                "MT5 is Windows-only; Oracle Linux depends on configured "
                "non-MT5 provider routes",
                blocking=False,
            )
        return stage, spec

    def _probe_stage(
        self,
        symbol: str,
        spec: RouteSpec,
    ) -> tuple[dict[str, Any], dict[str, pd.DataFrame], dict[str, dict[str, Any]]]:
        stage = _new_stage("PROVIDER")
        frames: dict[str, pd.DataFrame] = {}
        metadata: dict[str, dict[str, Any]] = {}
        if not self.probe_providers:
            _warn(
                stage,
                "Provider probing was not requested; live legitimacy is unverified",
                blocking=True,
            )
            return stage, frames, metadata

        for timeframe in TIMEFRAMES:
            router = DataRouter(symbol, timeframe)
            try:
                fetched = router.fetch(bars=PROBE_BARS, raise_on_failure=True)
                normalized = _normalize_probe_frame(fetched, symbol, timeframe)
                closed = normalized.tail(ROLLING_WINDOW).reset_index(drop=True)
                if len(closed) != ROLLING_WINDOW:
                    raise ValueError(
                        f"provider returned {len(closed)} closed candles; expected {ROLLING_WINDOW}"
                    )
                if closed["timestamp"].duplicated().any():
                    raise ValueError("provider returned duplicate timestamps")
                if not closed["timestamp"].is_monotonic_increasing:
                    raise ValueError("provider timestamps are not chronological")
                probe_gaps = classify_gaps(
                    closed["timestamp"],
                    timeframe,
                    spec.asset_class,
                    acquisition_metadata=router.last_acquisition_metadata,
                    provider=router.source_used,
                    symbol=symbol,
                )
                invalid_probe_gaps = [
                    gap for gap in probe_gaps
                    if gap["classification"] == "INVALID_GAP"
                ]
                if invalid_probe_gaps:
                    raise ValueError(
                        f"provider returned {len(invalid_probe_gaps)} invalid timeframe gap(s)"
                    )
                numeric = closed[list(PRICE_COLUMNS)].to_numpy(float)
                if not np.isfinite(numeric).all() or (numeric <= 0).any():
                    raise ValueError("provider returned invalid prices")
                malformed = (
                    (closed["low"] > closed["high"])
                    | (closed["open"] < closed["low"])
                    | (closed["open"] > closed["high"])
                    | (closed["close"] < closed["low"])
                    | (closed["close"] > closed["high"])
                )
                if malformed.any():
                    raise ValueError(
                        f"provider returned {int(malformed.sum())} malformed OHLC rows"
                    )
                source = router.source_used or "unknown"
                route = router.route_used
                ticker = route.external_ticker if route else None
                frames[timeframe] = closed
                metadata[timeframe] = {
                    "provider_used": source,
                    "external_ticker": ticker,
                    "provider_class": route.provider_class if route else None,
                    "attempt_errors": list(router.attempt_errors),
                    "acquisition_metadata": router.last_acquisition_metadata,
                    "closed_rows": len(closed),
                    "gaps": probe_gaps,
                    "first_timestamp": str(closed["timestamp"].iloc[0]),
                    "last_timestamp": str(closed["timestamp"].iloc[-1]),
                }
            except Exception as exc:
                _fail(
                    stage,
                    f"{timeframe}: {type(exc).__name__}: {exc}; "
                    f"attempts={list(router.attempt_errors)}",
                )
                metadata[timeframe] = {
                    "provider_used": router.source_used,
                    "attempt_errors": list(router.attempt_errors),
                    "error": f"{type(exc).__name__}: {exc}",
                }
        stage["details"]["timeframes"] = metadata
        return stage, frames, metadata

    def _timeframe_stage(
        self,
        symbol: str,
        timeframe: str,
        provider_frame: pd.DataFrame | None,
        provider_metadata: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], pd.DataFrame | None]:
        entries = self.database.get_dataset_registry(symbol, timeframe)
        if len(entries) != 1:
            stage = _new_stage(timeframe)
            _fail(
                stage,
                f"dataset_registry returned {len(entries)} rows; expected exactly one",
            )
            stage["details"]["registry_rows"] = entries
            return stage, None
        entry = dict(entries[0])
        stage = _new_stage(timeframe)
        stage["details"]["registry"] = entry

        if str(entry.get("symbol") or "") != symbol:
            _fail(stage, f"Registry symbol mismatch: {entry.get('symbol')!r}")
        if str(entry.get("timeframe") or "").upper() != timeframe:
            _fail(stage, f"Registry timeframe mismatch: {entry.get('timeframe')!r}")
        if str(entry.get("status") or "").lower() != "ready":
            _fail(stage, f"Registry status is not ready: {entry.get('status')!r}")
        if entry.get("candle_count") != ROLLING_WINDOW:
            _fail(stage, f"Registry candle_count is {entry.get('candle_count')!r}")
        if entry.get("rolling_window_size") != ROLLING_WINDOW:
            _fail(
                stage,
                f"Registry rolling_window_size is {entry.get('rolling_window_size')!r}",
            )
        if entry.get("last_error"):
            _warn(stage, f"Registry records last_error: {entry['last_error']}", blocking=True)
        try:
            last_updated = pd.Timestamp(entry.get("last_updated"))
            if pd.isna(last_updated):
                raise ValueError
        except Exception:
            _fail(stage, f"Registry last_updated is invalid: {entry.get('last_updated')!r}")

        canonical = forex_dataset_path(
            symbol, timeframe, project_root=self.project_root
        ).resolve()
        raw_blob_path = entry.get("blob_path")
        if not raw_blob_path:
            _fail(stage, "Registry blob_path is missing")
            return stage, None
        physical_path = Path(raw_blob_path)
        if not physical_path.is_absolute():
            physical_path = self.project_root / physical_path
        physical_path = physical_path.resolve()
        stage["details"]["canonical_path"] = str(canonical)
        stage["details"]["physical_path"] = str(physical_path)
        if physical_path != canonical:
            _fail(stage, f"Registry path is not canonical: {physical_path} != {canonical}")
        if not physical_path.is_file():
            _fail(stage, f"CSV does not exist: {physical_path}")
            return stage, None
        if physical_path.stat().st_size <= 0:
            _fail(stage, f"CSV is empty: {physical_path}")
            return stage, None

        try:
            frame = pd.read_csv(physical_path, encoding="utf-8")
        except Exception as exc:
            _fail(stage, f"CSV cannot be parsed completely as UTF-8: {type(exc).__name__}: {exc}")
            return stage, None

        frame_stage, normalized = validate_dataset_frame(
            frame,
            symbol,
            timeframe,
            now=self.now,
            acquisition_metadata=entry.get("acquisition_metadata"),
            provider=entry.get("provider_used"),
        )
        stage["errors"].extend(frame_stage["errors"])
        stage["warnings"].extend(frame_stage["warnings"])
        stage["blocking"] = bool(stage["blocking"] or frame_stage["blocking"])
        if frame_stage["status"] == "FAIL":
            stage["status"] = "FAIL"
        elif frame_stage["status"] == "WARNING" and stage["status"] != "FAIL":
            stage["status"] = "WARNING"
        stage["details"].update(frame_stage["details"])
        if normalized is None or normalized.empty:
            return stage, normalized

        physical_last = normalized["timestamp"].iloc[-1]
        try:
            registry_last = _utc_naive(entry.get("last_candle_timestamp"))
        except Exception:
            registry_last = None
            _fail(stage, "Registry last_candle_timestamp is invalid")
        if registry_last is not None and registry_last != physical_last:
            _fail(
                stage,
                f"Registry last timestamp differs from CSV: {registry_last} != {physical_last}",
            )

        persisted_provenance = {
            field: entry.get(field)
            for field in (
                "provider_used",
                "external_ticker",
                "provider_class",
                "source_fetched_at",
                "source_sha256",
            )
        }
        stage["details"]["persisted_provenance"] = persisted_provenance
        missing_provenance = [
            field for field, value in persisted_provenance.items() if not value
        ]
        if missing_provenance:
            legacy_pending = entry.get("legacy_provenance_pending") in (1, True)
            _warn(
                stage,
                (
                    "LEGACY_PROVENANCE_PENDING: " if legacy_pending else ""
                ) + f"Registry provenance is incomplete: {missing_provenance}",
                blocking=not legacy_pending,
            )
        else:
            route = next(
                (
                    candidate
                    for candidate in (
                        get_symbol_spec(symbol).primary,
                        get_symbol_spec(symbol).fallback,
                    )
                    if candidate is not None
                    and candidate.provider == persisted_provenance["provider_used"]
                ),
                None,
            )
            if (
                route is None
                or route.external_ticker != persisted_provenance["external_ticker"]
                or route.provider_class != persisted_provenance["provider_class"]
            ):
                _fail(stage, "Registry provenance does not match the canonical route")
            actual_sha256 = sha256_file(physical_path)
            stage["details"]["physical_sha256"] = actual_sha256
            if persisted_provenance["source_sha256"] != actual_sha256:
                _fail(stage, "Registry source_sha256 differs from the physical CSV")

        if provider_frame is not None:
            provenance = _match_provider_frame(normalized, provider_frame)
            provenance.update(provider_metadata or {})
            stage["details"]["provider_provenance"] = provenance
            if provenance["status"] != "MATCH":
                _warn(
                    stage,
                    "Stored CSV could not be matched to the live provider route",
                    blocking=True,
                )
        return stage, normalized

    def _cross_timeframe_stage(
        self,
        frames: dict[str, pd.DataFrame],
    ) -> dict[str, Any]:
        return validate_cross_timeframes(frames)

    @staticmethod
    def _final_stage(stages: dict[str, dict[str, Any]]) -> dict[str, Any]:
        final = _new_stage("FINAL")
        failed = [name for name, stage in stages.items() if stage["status"] == "FAIL"]
        blockers = [name for name, stage in stages.items() if stage["blocking"]]
        if failed:
            final["status"] = "FAIL"
            final["blocking"] = True
            final["errors"] = [f"Failed stages: {', '.join(failed)}"]
        elif blockers:
            final["status"] = "WARNING"
            final["blocking"] = True
            final["warnings"] = [f"Blocking warning stages: {', '.join(blockers)}"]
        final["details"] = {"failed_stages": failed, "blocking_stages": blockers}
        return final

    def qualify_symbol(self, symbol: str) -> dict[str, Any]:
        symbol = normalize_symbol(symbol)
        stages: dict[str, dict[str, Any]] = {}
        stages["REGISTRY"] = self._registry_stage(symbol)
        routing_stage, spec = self._routing_stage(symbol)
        stages["ROUTING"] = routing_stage
        if routing_stage["status"] == "FAIL":
            provider_stage = _new_stage("PROVIDER")
            _fail(provider_stage, "Provider probe skipped because routing is invalid")
            provider_frames: dict[str, pd.DataFrame] = {}
            provider_metadata: dict[str, dict[str, Any]] = {}
        else:
            provider_stage, provider_frames, provider_metadata = self._probe_stage(symbol, spec)
        stages["PROVIDER"] = provider_stage

        physical_frames: dict[str, pd.DataFrame] = {}
        for timeframe in TIMEFRAMES:
            timeframe_stage, frame = self._timeframe_stage(
                symbol,
                timeframe,
                provider_frames.get(timeframe),
                provider_metadata.get(timeframe),
            )
            stages[timeframe] = timeframe_stage
            if (
                frame is not None
                and not frame.empty
                and timeframe_stage["status"] != "FAIL"
            ):
                physical_frames[timeframe] = frame
        stages["CROSS-TIMEFRAME"] = self._cross_timeframe_stage(physical_frames)
        stages["FINAL"] = self._final_stage(stages)
        return {
            "symbol": symbol,
            "asset_class": spec.asset_class,
            "route": asdict(spec),
            "stages": stages,
            "final": stages["FINAL"]["status"],
        }

    def run(self, symbols: Iterable[str]) -> dict[str, Any]:
        results = []
        for symbol in symbols:
            normalized = normalize_symbol(symbol)
            try:
                results.append(self.qualify_symbol(normalized))
            except Exception as exc:
                stage = _new_stage("FINAL")
                _fail(stage, f"Unexpected per-symbol error: {type(exc).__name__}: {exc}")
                results.append({
                    "symbol": normalized,
                    "asset_class": expected_asset_class(normalized),
                    "route": asdict(route_spec(normalized)),
                    "stages": {"FINAL": stage},
                    "final": "FAIL",
                })

        totals = {"PASS": 0, "WARNING": 0, "FAIL": 0}
        for result in results:
            totals[result["final"]] += 1
        return {
            "title": "ASTRA SYMBOL QUALIFICATION",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project_root": str(self.project_root),
            "probe_providers": self.probe_providers,
            "rolling_window": ROLLING_WINDOW,
            "timeframes": list(TIMEFRAMES),
            "symbols": results,
            "totals": totals,
        }


def print_report(report: dict[str, Any]) -> None:
    for result in report["symbols"]:
        print("=" * 66)
        print(f"SYMBOL {result['symbol']} ({result['asset_class']})")
        print("=" * 66)
        for name in ("REGISTRY", "ROUTING", "PROVIDER", "H1", "H4", "D1", "CROSS-TIMEFRAME", "FINAL"):
            stage = result["stages"].get(name)
            if stage is None:
                continue
            suffix = " [BLOCKS ACTIVATION]" if stage["blocking"] else ""
            print(f"  {name:<16} {stage['status']}{suffix}")
            for message in stage["errors"]:
                print(f"    ERROR: {message}")
            for message in stage["warnings"]:
                print(f"    WARNING: {message}")
        print()

    print("=" * 82)
    print("ASTRA SYMBOL QUALIFICATION")
    print("=" * 82)
    print(f"{'SYMBOL':<10} {'CLASS':<10} {'H1':<7} {'H4':<7} {'D1':<7} {'PROVIDER':<10} {'CSV':<7} {'REGISTRY':<10} {'FINAL':<8}")
    for result in report["symbols"]:
        stages = result["stages"]
        csv_statuses = [stages.get(tf, {}).get("status", "FAIL") for tf in TIMEFRAMES]
        csv_status = "PASS" if all(status == "PASS" for status in csv_statuses) else (
            "FAIL" if "FAIL" in csv_statuses else "WARNING"
        )
        print(
            f"{result['symbol']:<10} {result['asset_class']:<10} "
            f"{stages.get('H1', {}).get('status', 'FAIL'):<7} "
            f"{stages.get('H4', {}).get('status', 'FAIL'):<7} "
            f"{stages.get('D1', {}).get('status', 'FAIL'):<7} "
            f"{stages.get('PROVIDER', {}).get('status', 'FAIL'):<10} "
            f"{csv_status:<7} "
            f"{stages.get('REGISTRY', {}).get('status', 'FAIL'):<10} "
            f"{result['final']:<8}"
        )
    totals = report["totals"]
    print()
    print(f"TOTAL: PASS={totals['PASS']} WARNING={totals['WARNING']} FAIL={totals['FAIL']}")


def write_json_report(report: dict[str, Any], path: Path | str) -> str:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(report, temporary, indent=2, ensure_ascii=False, default=str)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
        return str(target)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only qualification of ASTRA symbols, providers and datasets"
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--symbol", help="Qualify one symbol")
    selection.add_argument("--all", action="store_true", help="Qualify every declared/active symbol sequentially")
    parser.add_argument(
        "--probe-providers",
        action="store_true",
        help="Fetch real provider candles in memory; never writes datasets or registry",
    )
    parser.add_argument("--report-json", type=Path, help="Optional atomic JSON report path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, database: DatabaseAdapter | None = None) -> int:
    args = parse_args(argv)
    try:
        db = database if database is not None else get_read_only_database()
        harness = SymbolQualificationHarness(db, probe_providers=args.probe_providers)
        if args.all:
            symbols = harness.universe()
        else:
            symbols = (normalize_symbol(args.symbol),)
        report = harness.run(symbols)
        print_report(report)
        if args.report_json:
            print(f"JSON report: {write_json_report(report, args.report_json)}")
    except Exception as exc:
        print(f"INTERNAL ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0 if report["totals"]["PASS"] == len(report["symbols"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())

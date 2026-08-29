"""Rolling dataset storage with validation, locking and atomic replacement."""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from filelock import FileLock

from forex.data.indicator_delta import INDICATOR_MIN_HISTORY
from forex.data.ohlc_contract import OHLCContractError, validate_ohlc_frame


logger = logging.getLogger(__name__)

ROLLING_WINDOW = 2000
_DEFAULT_MAX_ROWS = ROLLING_WINDOW
_REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
_INDICATOR_COLUMNS = frozenset(INDICATOR_MIN_HISTORY)
_TIMEFRAME_DURATION = {
    "M1": pd.Timedelta(minutes=1),
    "M5": pd.Timedelta(minutes=5),
    "M15": pd.Timedelta(minutes=15),
    "M30": pd.Timedelta(minutes=30),
    "H1": pd.Timedelta(hours=1),
    "H4": pd.Timedelta(hours=4),
    "D1": pd.Timedelta(days=1),
}


class DatasetValidationError(ValueError):
    """Raised when a candidate dataset cannot safely replace the current CSV."""


def _utc_naive_timestamp(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp


def normalize_dataset(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    """Normalize one provider/existing frame and reject ambiguous bad rows."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise DatasetValidationError("Dataset is empty")

    missing = set(_REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise DatasetValidationError(f"Missing required columns: {sorted(missing)}")

    normalized = df.copy()
    parsed = pd.to_datetime(normalized["timestamp"], utc=True, errors="coerce")
    invalid_timestamps = int(parsed.isna().sum())
    if invalid_timestamps:
        raise DatasetValidationError(
            f"Invalid timestamps rejected: {invalid_timestamps} row(s)"
        )
    normalized["timestamp"] = parsed.dt.tz_localize(None)

    for column in ("open", "high", "low", "close", "volume"):
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    invalid_ohlcv = normalized[list(_REQUIRED_COLUMNS[1:])].isna().any(axis=1)
    if invalid_ohlcv.any():
        raise DatasetValidationError(
            f"Invalid OHLCV values rejected: {int(invalid_ohlcv.sum())} row(s)"
        )
    try:
        validate_ohlc_frame(normalized)
    except OHLCContractError as exc:
        raise DatasetValidationError(str(exc)) from exc

    normalized["pair"] = pair.upper()
    return normalized


def exclude_incomplete_candles(
    df: pd.DataFrame,
    timeframe: str,
    *,
    now: object = None,
) -> pd.DataFrame:
    """Keep only candles whose close time is not in the future."""
    duration = _TIMEFRAME_DURATION.get(timeframe.upper())
    if duration is None or df.empty:
        return df
    cutoff = _utc_naive_timestamp(
        pd.Timestamp.now(tz="UTC") if now is None else now
    )
    return df.loc[df["timestamp"] + duration <= cutoff].reset_index(drop=True)


def validate_dataset(df: pd.DataFrame, max_rows: int) -> None:
    """Validate invariants required before replacing a rolling CSV."""
    if df.empty:
        raise DatasetValidationError("No closed candles remain after validation")
    if len(df) > max_rows:
        raise DatasetValidationError(
            f"Dataset has {len(df)} rows; rolling limit is {max_rows}"
        )
    if df["timestamp"].duplicated().any():
        raise DatasetValidationError("Duplicate timestamps remain after merge")
    if not df["timestamp"].is_monotonic_increasing:
        raise DatasetValidationError("Timestamps are not chronological")
    numeric = df[list(_REQUIRED_COLUMNS[1:])].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise DatasetValidationError("OHLCV data contains non-finite values")
    try:
        validate_ohlc_frame(df)
    except OHLCContractError as exc:
        raise DatasetValidationError(str(exc)) from exc
    missing_indicators = _INDICATOR_COLUMNS - set(df.columns)
    if missing_indicators:
        raise DatasetValidationError(
            "Missing required indicator columns: "
            f"{sorted(missing_indicators)}"
        )
    for column, minimum_history in INDICATOR_MIN_HISTORY.items():
        if len(df) < minimum_history:
            # The required column exists, but its normal calculation window is
            # not available yet. Initial NaN values are legitimate warm-up.
            continue
        calculable_values = pd.to_numeric(
            df[column].iloc[minimum_history - 1:], errors="coerce"
        ).to_numpy(dtype=float)
        if not np.isfinite(calculable_values).any():
            raise DatasetValidationError(
                f"Indicator {column} contains no valid values despite "
                f"{len(df)} rows (minimum history: {minimum_history})"
            )


def atomic_write_csv(df: pd.DataFrame, path: Path | str) -> str:
    """Write a CSV beside its target, fsync it, then atomically replace target."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            df.to_csv(temporary, index=False)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
        return str(target.resolve())
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove temporary dataset %s", temporary_path)


class RollingDataset:
    """Maintain one bounded CSV through a per-dataset atomic transaction."""

    def __init__(
        self,
        pair: str,
        tf: str,
        csv_dir: str = None,
        max_rows: int = _DEFAULT_MAX_ROWS,
        *,
        csv_path: Path | str | None = None,
        lock_timeout: float = 30.0,
    ):
        self.pair = pair.upper()
        self.tf = tf.upper()
        self.max_rows = max_rows
        if csv_path is None:
            base = (
                Path(csv_dir)
                if csv_dir
                else Path(__file__).parent.parent.parent / "CSVs" / self.tf
            )
            self.csv_path = base / f"{self.pair}.csv"
        else:
            self.csv_path = Path(csv_path)
        self.csv_path = self.csv_path.resolve()
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.csv_path.with_suffix(self.csv_path.suffix + ".lock")
        self.lock_timeout = lock_timeout
        self._df: Optional[pd.DataFrame] = None

    def load(self) -> bool:
        """Load the CSV in memory. Return False for a missing or invalid file."""
        if not self.csv_path.exists():
            return False
        try:
            self._df = normalize_dataset(pd.read_csv(self.csv_path), self.pair)
            return True
        except Exception as exc:
            logger.error("Could not load %s: %s", self.csv_path, exc)
            self._df = None
            return False

    def apply(
        self,
        new_data: pd.DataFrame,
        *,
        include_existing: bool = True,
        now: object = None,
    ) -> dict:
        """Merge and persist data as one locked transaction.

        Duplicate timestamps use ``keep='last'`` after concatenating existing
        rows before provider rows. Therefore the last provider observation wins.
        """
        incoming = normalize_dataset(new_data, self.pair)
        with FileLock(str(self.lock_path), timeout=self.lock_timeout):
            existing = None
            if include_existing and self.csv_path.exists():
                existing = normalize_dataset(pd.read_csv(self.csv_path), self.pair)

            frames = [frame for frame in (existing, incoming) if frame is not None]
            candidate = pd.concat(frames, ignore_index=True, sort=False)
            candidate = candidate.drop_duplicates(subset=["timestamp"], keep="last")
            candidate = candidate.sort_values("timestamp").reset_index(drop=True)
            candidate = exclude_incomplete_candles(candidate, self.tf, now=now)
            candidate = candidate.tail(self.max_rows).reset_index(drop=True)

            from forex.data.indicator_delta import recalculate_tail_indicators

            candidate = recalculate_tail_indicators(candidate, k=len(candidate))
            validate_dataset(candidate, self.max_rows)

            old_timestamps = (
                set(existing["timestamp"].tolist()) if existing is not None else set()
            )
            added = sum(ts not in old_timestamps for ts in candidate["timestamp"])
            resolved_path = atomic_write_csv(candidate, self.csv_path)
            self._df = candidate

        return {
            "path": resolved_path,
            "rows": len(candidate),
            "added": added,
            "last_timestamp": candidate["timestamp"].iloc[-1],
        }

    def initialize(self, df: pd.DataFrame) -> bool:
        """Create an initial CSV using the same safe transaction as updates."""
        try:
            self.apply(df, include_existing=False)
            return True
        except Exception as exc:
            logger.error("Could not initialize %s/%s: %s", self.pair, self.tf, exc)
            return False

    def update(self, new_candle: dict) -> bool:
        """Merge one candle, preserving the historical boolean API."""
        try:
            self.apply(pd.DataFrame([new_candle]), include_existing=True)
            return True
        except Exception as exc:
            logger.error("Could not update %s/%s: %s", self.pair, self.tf, exc)
            return False

    def update_frame(self, new_data: pd.DataFrame, *, now: object = None) -> dict:
        """Strict bulk update API used by schedulers and auto-updaters."""
        return self.apply(new_data, include_existing=True, now=now)

    def validate(self) -> dict:
        """Return current dataset integrity without mutating the file."""
        if self._df is None and not self.load():
            return {"ok": False, "error": "CSV does not exist or is invalid"}
        try:
            validate_dataset(self._df, self.max_rows)
            issues = []
        except DatasetValidationError as exc:
            issues = [str(exc)]
        return {
            "ok": not issues,
            "rows": len(self._df),
            "max_rows": self.max_rows,
            "pair": self.pair,
            "tf": self.tf,
            "issues": issues,
            "last_ts": (
                str(self._df["timestamp"].iloc[-1])
                if len(self._df) > 0 else "N/A"
            ),
        }

    def get_df(self) -> Optional[pd.DataFrame]:
        if self._df is None:
            self.load()
        return self._df

    def info(self) -> str:
        validation = self.validate()
        if not validation["ok"]:
            return (
                f"[RollingDataset] {self.pair}/{self.tf} "
                f"invalid: {validation.get('error', validation.get('issues'))}"
            )
        return (
            f"[RollingDataset] {self.pair}/{self.tf} "
            f"{validation['rows']}/{validation['max_rows']} rows - "
            f"last: {validation['last_ts']}"
        )


def get_rolling_dataset(
    pair: str,
    tf: str,
    csv_dir: str = None,
    max_rows: int = _DEFAULT_MAX_ROWS,
) -> RollingDataset:
    return RollingDataset(pair, tf, csv_dir, max_rows)

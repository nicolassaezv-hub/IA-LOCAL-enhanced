"""Fail-closed observational Forex runtime for EURUSD and USDJPY.

This module is deliberately separate from the production prediction,
activation, model-alias, and execution paths.  Its Random Forest is an
operational baseline for end-to-end observation, not evidence of statistical
optimality or production eligibility.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd

from forex.data.mt5_provider import MT5Provider
from forex.data.symbol_catalog import route_for_provider
from forex.prediction.csv_adapter import adapt_csv
from forex.prediction.dataset_builder import DatasetBuilder, feature_names_sha256
from forex.prediction.feature_engineering import build_features
from forex.prediction.h1_directional import (
    build_oof_decision_reference,
    fit_frozen_h1_random_forest,
    h1_oof_positions,
)
from infra.db.database import PersistenceConflictError
from runtime_paths import forex_model_root
from scheduler.autonomous_scheduler import registry_entry_readiness


SHADOW_RUNTIME_SYMBOLS = ("EURUSD", "USDJPY")
SHADOW_MODEL_CONTRACT = "shadow_multiframe_directional_v1"
SHADOW_TARGET_PROFILE = "fixed_horizon_direction_v1"
SHADOW_HORIZON = 12
SHADOW_FEATURE_PROFILE = "stationary_v1"
SHADOW_DECISION_POLICY = "shadow_oof_quartile_abstention_v1"
SHADOW_SCORE_TYPE = "rf_raw_p_up_v1"
SHADOW_CONFIDENCE_SEMANTICS = "shadow_oof_percentile_extremeness_v1"
SHADOW_MODEL_STAGE = "experimental_observation"
SHADOW_EXECUTION_MODE = "shadow"
SHADOW_EVALUATION_SEMANTICS = "terminal_direction_at_12_closed_h1_v1"
DEFAULT_SHADOW_RETRAIN_CANDLES = 168
REQUIRED_TIMEFRAMES = ("H1", "H4", "D1")

_RF_CONFIG = {
    "n_estimators": 300,
    "max_depth": 8,
    "min_samples_leaf": 15,
    "class_weight_strategy": "TRAIN_NEGATIVE_TO_POSITIVE_RATIO",
    "random_state": 42,
    "n_jobs": -1,
}


def fixed_shadow_rf_config() -> dict:
    return dict(_RF_CONFIG)


def _clean_symbol(value: str) -> str:
    return "".join(character for character in str(value).upper() if character.isalnum())


def parse_symbol_list(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    parsed: list[str] = []
    for raw in str(value).split(","):
        symbol = _clean_symbol(raw)
        if not symbol:
            continue
        if symbol not in SHADOW_RUNTIME_SYMBOLS:
            raise ValueError(f"RUNTIME_SYMBOL_UNSUPPORTED: {symbol}")
        if symbol not in parsed:
            parsed.append(symbol)
    return tuple(parsed)


def _boolean(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(f"SHADOW_MODE_INVALID: {value!r}")


@dataclass(frozen=True)
class ShadowRuntimeConfig:
    enabled: bool
    shadow_symbols: tuple[str, ...]
    runtime_symbols: tuple[str, ...]
    runtime_scope_configured: bool
    provider: str
    retrain_candles: int

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "ShadowRuntimeConfig":
        source = os.environ if environment is None else environment
        shadow_value = source.get("ASTRA_FOREX_SHADOW_SYMBOLS")
        runtime_value = source.get("ASTRA_FOREX_RUNTIME_SYMBOLS")
        shadow_symbols = (
            parse_symbol_list(shadow_value)
            if shadow_value is not None
            else SHADOW_RUNTIME_SYMBOLS
        )
        runtime_symbols = (
            parse_symbol_list(runtime_value)
            if runtime_value is not None
            else SHADOW_RUNTIME_SYMBOLS
        )
        provider = str(source.get("ASTRA_FOREX_RUNTIME_PROVIDER", "MT5")).upper()
        if provider != "MT5":
            raise ValueError(f"RUNTIME_PROVIDER_UNSUPPORTED: {provider}")
        try:
            cadence = int(
                source.get(
                    "ASTRA_SHADOW_RETRAIN_CANDLES",
                    str(DEFAULT_SHADOW_RETRAIN_CANDLES),
                )
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("SHADOW_RETRAIN_CADENCE_INVALID") from exc
        if cadence <= 0:
            raise ValueError("SHADOW_RETRAIN_CADENCE_INVALID")
        return cls(
            enabled=_boolean(source.get("ASTRA_FOREX_SHADOW_MODE")),
            shadow_symbols=shadow_symbols,
            runtime_symbols=runtime_symbols,
            runtime_scope_configured=runtime_value is not None,
            provider=provider,
            retrain_candles=cadence,
        )


def shadow_eligible(database, symbol: str, config: ShadowRuntimeConfig) -> bool:
    code = _clean_symbol(symbol)
    if (
        not config.enabled
        or code not in config.shadow_symbols
        or code not in config.runtime_symbols
    ):
        return False
    row = database.get_symbol(code) if code else None
    return bool(
        isinstance(row, dict)
        and str(row.get("status") or "").lower() == "qualified"
    )


def _require_shadow_eligible(database, symbol: str, config: ShadowRuntimeConfig) -> dict:
    code = _clean_symbol(symbol)
    row = database.get_symbol(code) if code else None
    status = str((row or {}).get("status") or "unregistered").lower()
    if not shadow_eligible(database, code, config):
        raise ValueError(f"SHADOW_SYMBOL_NOT_ELIGIBLE: {code} status={status}")
    return row


def _require_qualified(database, symbol: str) -> dict:
    code = _clean_symbol(symbol)
    row = database.get_symbol(code) if code else None
    status = str((row or {}).get("status") or "unregistered").lower()
    if status != "qualified" or code not in SHADOW_RUNTIME_SYMBOLS:
        raise ValueError(f"SHADOW_SYMBOL_NOT_QUALIFIED: {code} status={status}")
    return row


def fetch_pinned_market_data(
    symbol: str, timeframe: str, count: int, provider: str
) -> tuple[pd.DataFrame, str]:
    """Fetch directly from the configured authority, with no fallback router."""
    if str(provider).upper() != "MT5":
        raise ValueError(f"RUNTIME_PROVIDER_UNSUPPORTED: {provider}")
    authority = MT5Provider()
    frame = authority.fetch(_clean_symbol(symbol), str(timeframe).upper(), int(count))
    metadata = authority.last_acquisition_metadata
    if metadata is not None:
        frame.attrs["acquisition_metadata"] = metadata
    return frame, "MT5"


class _PinnedMT5QualificationRouter:
    """Qualification adapter exposing one MT5 route and no fallback chain."""

    def __init__(self, symbol: str, timeframe: str):
        self.symbol = _clean_symbol(symbol)
        self.timeframe = str(timeframe).upper()
        self._metadata: dict | None = None
        self._route = None

    def fetch(self, *, bars: int, raise_on_failure: bool = True) -> pd.DataFrame:
        del raise_on_failure
        frame, source = fetch_pinned_market_data(
            self.symbol, self.timeframe, bars, "MT5"
        )
        self._metadata = frame.attrs.get("acquisition_metadata")
        self._route = route_for_provider(self.symbol, source)
        if self._route is None:
            raise ValueError("SHADOW_MT5_ROUTE_MISSING")
        return frame

    @property
    def last_acquisition_metadata(self) -> dict | None:
        return dict(self._metadata) if self._metadata is not None else None

    @property
    def route_used(self):
        return self._route

    @property
    def attempt_errors(self) -> tuple:
        return ()


def pinned_mt5_qualification_router(symbol: str, timeframe: str):
    return _PinnedMT5QualificationRouter(symbol, timeframe)


def require_single_symbol_frame(
    frame: pd.DataFrame, symbol: str, *, timeframe: str
) -> pd.DataFrame:
    code = _clean_symbol(symbol)
    if not isinstance(frame, pd.DataFrame) or frame.empty or "pair" not in frame.columns:
        raise ValueError(f"SHADOW_{timeframe}_SYMBOL_PROVENANCE_MISSING")
    observed = {
        _clean_symbol(value) for value in frame["pair"].dropna().astype(str).unique()
    }
    if observed != {code}:
        raise ValueError(
            f"SHADOW_CROSS_SYMBOL_DATA: expected={code} observed={sorted(observed)}"
        )
    return frame


def require_shadow_registry(
    database,
    symbol: str,
    *,
    project_root: Path | str,
) -> dict[str, dict]:
    code = _clean_symbol(symbol)
    entries: dict[str, dict] = {}
    for timeframe in REQUIRED_TIMEFRAMES:
        rows = database.get_dataset_registry(code, timeframe)
        if len(rows) != 1:
            raise ValueError(f"SHADOW_DATASET_{timeframe}_NOT_READY")
        entries[timeframe] = rows[0]
    for timeframe, entry in entries.items():
        readiness = registry_entry_readiness(entry, project_root=project_root)
        metadata = entry.get("acquisition_metadata")
        complete_provenance = all(
            entry.get(field)
            for field in (
                "provider_used",
                "external_ticker",
                "provider_class",
                "source_fetched_at",
                "source_sha256",
            )
        )
        metadata_complete = bool(
            isinstance(metadata, dict)
            and metadata.get("provider") == "MT5"
            and metadata.get("terminal_connected") is True
            and metadata.get("server")
        )
        if (
            readiness.get("ready") is not True
            or entry.get("candle_count") != 2000
            or entry.get("rolling_window_size") != 2000
            or entry.get("provider_used") != "MT5"
            or entry.get("legacy_provenance_pending") not in (0, False)
            or not complete_provenance
            or not metadata_complete
        ):
            raise ValueError(f"SHADOW_DATASET_{timeframe}_NOT_READY")
    return entries


def _entry_path(entry: dict, project_root: Path) -> Path:
    path = Path(str(entry["blob_path"]))
    return path if path.is_absolute() else project_root / path


def load_shadow_multiframe(
    entries: dict[str, dict], symbol: str, *, project_root: Path | str
) -> pd.DataFrame:
    root = Path(project_root)
    paths = {
        timeframe: _entry_path(entries[timeframe], root)
        for timeframe in REQUIRED_TIMEFRAMES
    }
    for timeframe, path in paths.items():
        frame = pd.read_csv(path)
        require_single_symbol_frame(frame, symbol, timeframe=timeframe)
    merged = adapt_csv(
        str(paths["H1"]),
        pair=_clean_symbol(symbol),
        path_h4=str(paths["H4"]),
        path_d1=str(paths["D1"]),
    )
    require_single_symbol_frame(merged, symbol, timeframe="H1_MERGED")
    return build_features(merged)


def _utc_iso(value: Any) -> str:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("SHADOW_TIMESTAMP_INVALID")
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.isoformat()


def shadow_model_identity(symbol: str, generation: int, artifact_sha256: str) -> str:
    code = _clean_symbol(symbol)
    if code not in SHADOW_RUNTIME_SYMBOLS or int(generation) <= 0:
        raise ValueError("SHADOW_MODEL_IDENTITY_INVALID")
    digest = str(artifact_sha256).lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError("SHADOW_MODEL_IDENTITY_INVALID")
    return f"shadow_{code}_g{int(generation):04d}_{digest[:16]}"


def next_shadow_generation(metadata: dict | None) -> int:
    if metadata is None:
        return 1
    generation = metadata.get("model_generation")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation <= 0:
        raise ValueError("SHADOW_MODEL_GENERATION_INVALID")
    return generation + 1


class ShadowModelStorage:
    """Atomic, checksum-verifying storage confined to the shadow directory."""

    def __init__(self, base_dir: Path | str):
        self.base_dir = Path(base_dir)

    def path_for(self, symbol: str) -> Path:
        code = _clean_symbol(symbol)
        if code not in SHADOW_RUNTIME_SYMBOLS or code != str(symbol).upper().strip():
            raise ValueError("SHADOW_STORAGE_PATH_INVALID")
        return self.base_dir / f"{code}.pkl"

    @staticmethod
    def _serialize(payload: dict) -> bytes:
        stream = io.BytesIO()
        joblib.dump(payload, stream)
        return stream.getvalue()

    def save(self, symbol: str, payload: dict) -> dict:
        metadata = dict(payload.get("metadata") or {})
        code = _clean_symbol(symbol)
        if metadata.get("symbol") != code or metadata.get("mode") != "shadow":
            raise ValueError("SHADOW_ARTIFACT_METADATA_INVALID")
        generation = metadata.get("model_generation")
        if not isinstance(generation, int) or generation <= 0:
            raise ValueError("SHADOW_MODEL_GENERATION_INVALID")
        payload_bytes = self._serialize(payload)
        artifact_sha256 = hashlib.sha256(payload_bytes).hexdigest()
        identity = shadow_model_identity(code, generation, artifact_sha256)
        envelope = {
            "schema_version": 1,
            "symbol": code,
            "mode": "shadow",
            "artifact_sha256": artifact_sha256,
            "model_identity": identity,
            "model_generation": generation,
            "payload": payload_bytes,
        }
        target = self.path_for(code)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{code}.", suffix=".tmp", dir=target.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            joblib.dump(envelope, temporary)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return self.load(code)

    def load(self, symbol: str) -> dict:
        code = _clean_symbol(symbol)
        path = self.path_for(code)
        if not path.is_file():
            raise FileNotFoundError(f"SHADOW_MODEL_MISSING: {code}")
        envelope = joblib.load(path)
        if not isinstance(envelope, dict) or envelope.get("symbol") != code:
            raise ValueError("SHADOW_ARTIFACT_INVALID")
        payload_bytes = envelope.get("payload")
        if not isinstance(payload_bytes, bytes):
            raise ValueError("SHADOW_ARTIFACT_INVALID")
        observed_sha = hashlib.sha256(payload_bytes).hexdigest()
        if observed_sha != envelope.get("artifact_sha256"):
            raise ValueError("SHADOW_ARTIFACT_SHA_MISMATCH")
        identity = shadow_model_identity(
            code, envelope.get("model_generation"), observed_sha
        )
        if identity != envelope.get("model_identity"):
            raise ValueError("SHADOW_MODEL_IDENTITY_MISMATCH")
        payload = joblib.load(io.BytesIO(payload_bytes))
        if not isinstance(payload, dict):
            raise ValueError("SHADOW_ARTIFACT_INVALID")
        metadata = dict(payload.get("metadata") or {})
        metadata.update({
            "artifact_sha256": observed_sha,
            "model_identity": identity,
            "artifact_path": str(path),
        })
        payload["metadata"] = metadata
        _validate_shadow_artifact(payload, code)
        return payload

    def exists(self, symbol: str) -> bool:
        return self.path_for(symbol).is_file()


def _validate_shadow_artifact(bundle: dict, symbol: str) -> None:
    metadata = bundle.get("metadata")
    model = bundle.get("model")
    feature_names = bundle.get("feature_names")
    reference = bundle.get("oof_score_reference")
    exact = {
        "symbol": symbol,
        "mode": "shadow",
        "model_contract": SHADOW_MODEL_CONTRACT,
        "target_profile": SHADOW_TARGET_PROFILE,
        "target_definition_version": 1,
        "horizon": SHADOW_HORIZON,
        "feature_profile": SHADOW_FEATURE_PROFILE,
        "model_family": "RandomForestClassifier",
        "decision_policy": SHADOW_DECISION_POLICY,
        "score_type": SHADOW_SCORE_TYPE,
        "confidence_semantics": SHADOW_CONFIDENCE_SEMANTICS,
    }
    if not isinstance(metadata, dict) or any(
        metadata.get(field) != expected for field, expected in exact.items()
    ):
        raise ValueError("SHADOW_ARTIFACT_CONTRACT_MISMATCH")
    if (
        not isinstance(feature_names, list)
        or not feature_names
        or feature_names_sha256(feature_names) != metadata.get("feature_names_sha256")
        or not callable(getattr(model, "predict_proba", None))
    ):
        raise ValueError("SHADOW_ARTIFACT_FEATURE_CONTRACT_MISMATCH")
    reference_array = np.asarray(reference, dtype=float)
    if (
        reference_array.shape != (600,)
        or not np.isfinite(reference_array).all()
        or np.any(reference_array[1:] < reference_array[:-1])
    ):
        raise ValueError("SHADOW_OOF_REFERENCE_INVALID")


def count_new_h1_candles(training_cutoff: Any, h1_timestamps) -> int:
    cutoff = pd.Timestamp(training_cutoff)
    if cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize("UTC")
    else:
        cutoff = cutoff.tz_convert("UTC")
    timestamps = pd.to_datetime(pd.Index(h1_timestamps), utc=True, errors="coerce")
    if timestamps.isna().any():
        raise ValueError("SHADOW_H1_TIMESTAMPS_INVALID")
    return int(pd.Index(timestamps[timestamps > cutoff]).nunique())


def shadow_retrain_due(training_cutoff, h1_timestamps, cadence) -> bool:
    return count_new_h1_candles(training_cutoff, h1_timestamps) >= int(cadence)


def _decision(score: float, sorted_reference) -> dict:
    value = float(score)
    reference = np.asarray(sorted_reference, dtype=float)
    if (
        reference.shape != (600,)
        or not math.isfinite(value)
        or not 0.0 <= value <= 1.0
        or np.any(reference[1:] < reference[:-1])
    ):
        raise ValueError("SHADOW_DECISION_EVIDENCE_INVALID")
    percentile = float(np.searchsorted(reference, value, side="right") / len(reference))
    action = "BUY" if percentile >= 0.75 else "SELL" if percentile <= 0.25 else "HOLD"
    return {
        "action": action,
        "direction_score": value,
        "decision_percentile": percentile,
        "decision_extremeness": float(np.clip(2.0 * abs(percentile - 0.5), 0.0, 1.0)),
    }


def _shadow_prediction_id(symbol: str, candle: Any, generation: int) -> str:
    identity = "|".join((
        _clean_symbol(symbol),
        "H1",
        _utc_iso(candle),
        SHADOW_MODEL_CONTRACT,
        str(int(generation)),
    ))
    return "shadow_pred_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]


def persist_shadow_prediction(
    database,
    *,
    symbol: str,
    candle_timestamp: Any,
    entry_price: float,
    decision: dict,
    model_metadata: dict,
    dataset_provenance: dict,
) -> dict:
    code = _clean_symbol(symbol)
    _require_qualified(database, code)
    action = str(decision.get("action") or "").upper()
    if action not in ("BUY", "SELL", "HOLD"):
        raise ValueError("SHADOW_ACTION_INVALID")
    exact = {
        "symbol": code,
        "mode": "shadow",
        "model_contract": SHADOW_MODEL_CONTRACT,
        "target_profile": SHADOW_TARGET_PROFILE,
        "horizon": SHADOW_HORIZON,
        "feature_profile": SHADOW_FEATURE_PROFILE,
    }
    if any(model_metadata.get(field) != value for field, value in exact.items()):
        raise ValueError("SHADOW_MODEL_METADATA_INVALID")
    generation = model_metadata.get("model_generation")
    identity = model_metadata.get("model_identity")
    if not isinstance(generation, int) or generation <= 0 or not identity:
        raise ValueError("SHADOW_MODEL_METADATA_INVALID")
    try:
        price = float(entry_price)
        score = float(decision["direction_score"])
        percentile = float(decision["decision_percentile"])
        extremeness = float(decision["decision_extremeness"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("SHADOW_DECISION_EVIDENCE_INVALID") from exc
    if (
        price <= 0.0
        or not all(math.isfinite(value) for value in (price, score, percentile, extremeness))
        or not all(0.0 <= value <= 1.0 for value in (score, percentile, extremeness))
    ):
        raise ValueError("SHADOW_DECISION_EVIDENCE_INVALID")
    candle_iso = _utc_iso(candle_timestamp)
    prediction_id = _shadow_prediction_id(code, candle_iso, generation)
    existing = database.get_prediction(prediction_id)
    evidence = {
        "prediction_id": prediction_id,
        "symbol": code,
        "pair": code,
        "timeframe": "H1",
        "action": action,
        "direction": action,
        "confidence": extremeness,
        "entry_price": price,
        "predicted_at": datetime.now(timezone.utc).isoformat(),
        "candle_timestamp": candle_iso,
        "horizon_candles": SHADOW_HORIZON,
        "model_identity": identity,
        "model_contract": SHADOW_MODEL_CONTRACT,
        "target_profile": SHADOW_TARGET_PROFILE,
        "target_definition_version": 1,
        "feature_profile": SHADOW_FEATURE_PROFILE,
        "score_type": SHADOW_SCORE_TYPE,
        "direction_score": score,
        "decision_percentile": percentile,
        "decision_policy": SHADOW_DECISION_POLICY,
        "confidence_semantics": SHADOW_CONFIDENCE_SEMANTICS,
        "execution_mode": SHADOW_EXECUTION_MODE,
        "model_stage": SHADOW_MODEL_STAGE,
        "model_generation": generation,
        "dataset_provenance": dict(dataset_provenance),
        "status": "PENDING",
    }
    if existing is not None:
        immutable = (
            "symbol", "timeframe", "action", "candle_timestamp", "model_identity",
            "model_generation", "execution_mode", "direction_score",
            "decision_percentile", "entry_price",
        )
        conflicts = [
            field for field in immutable
            if existing.get(field) != evidence.get(field)
        ]
        if conflicts:
            raise PersistenceConflictError(
                f"conflicting shadow prediction evidence: {', '.join(conflicts)}"
            )
        return existing
    return database.save_prediction(evidence)


def mature_shadow_outcomes(
    database,
    symbol: str,
    candles: pd.DataFrame,
    *,
    available_at: Any,
) -> int:
    code = _clean_symbol(symbol)
    frame = candles.loc[:, ["timestamp", "close"]].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna().drop_duplicates("timestamp", keep="last").sort_values("timestamp")
    cutoff = pd.Timestamp(available_at)
    if cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize("UTC")
    else:
        cutoff = cutoff.tz_convert("UTC")
    closed = frame.loc[frame["timestamp"] + timedelta(hours=1) <= cutoff]
    existing = {
        row["prediction_id"] for row in database.get_shadow_outcomes(code)
    }
    finalized = 0
    predictions = database.get_predictions(code, "H1", limit=100000)
    for prediction in reversed(predictions):
        if (
            prediction.get("execution_mode") != "shadow"
            or prediction.get("status") != "PENDING"
            or str(prediction.get("action") or "").upper() not in ("BUY", "SELL")
            or prediction["prediction_id"] in existing
        ):
            continue
        if (
            prediction.get("model_contract") != SHADOW_MODEL_CONTRACT
            or prediction.get("target_profile") != SHADOW_TARGET_PROFILE
            or prediction.get("feature_profile") != SHADOW_FEATURE_PROFILE
            or prediction.get("horizon_candles") != SHADOW_HORIZON
            or prediction.get("decision_policy") != SHADOW_DECISION_POLICY
        ):
            continue
        entry_candle = pd.Timestamp(prediction["candle_timestamp"])
        if entry_candle.tzinfo is None:
            entry_candle = entry_candle.tz_localize("UTC")
        else:
            entry_candle = entry_candle.tz_convert("UTC")
        future = closed.loc[closed["timestamp"] > entry_candle].head(SHADOW_HORIZON)
        if len(future) < SHADOW_HORIZON:
            continue
        evaluation = future.iloc[-1]
        entry_price = float(prediction["entry_price"])
        future_close = float(evaluation["close"])
        future_return = (future_close - entry_price) / entry_price
        action = str(prediction["action"]).upper()
        correct = future_close > entry_price if action == "BUY" else future_close <= entry_price
        database.save_shadow_outcome({
            "prediction_id": prediction["prediction_id"],
            "symbol": code,
            "timeframe": "H1",
            "action": action,
            "entry_candle": _utc_iso(entry_candle),
            "evaluation_candle": _utc_iso(evaluation["timestamp"]),
            "entry_price": entry_price,
            "future_close": future_close,
            "future_return": future_return,
            "direction_correct": correct,
            "model_identity": prediction["model_identity"],
            "model_generation": int(prediction["model_generation"]),
            "execution_mode": "shadow",
            "status": "FINALIZED",
            "evaluation_semantics": SHADOW_EVALUATION_SEMANTICS,
            "finalized_at": datetime.now(timezone.utc).isoformat(),
        })
        existing.add(prediction["prediction_id"])
        finalized += 1
    return finalized


def _metrics_group(predictions: list[dict], outcomes: list[dict]) -> dict:
    buy = [row for row in predictions if row.get("action") == "BUY"]
    sell = [row for row in predictions if row.get("action") == "SELL"]
    hold = [row for row in predictions if row.get("action") == "HOLD"]
    buy_outcomes = [row for row in outcomes if row.get("action") == "BUY"]
    sell_outcomes = [row for row in outcomes if row.get("action") == "SELL"]
    evaluated = buy_outcomes + sell_outcomes

    def precision(rows: list[dict]) -> float:
        return (
            sum(bool(row.get("direction_correct")) for row in rows) / len(rows)
            if rows else 0.0
        )

    timestamps = sorted(
        str(row["candle_timestamp"]) for row in predictions
        if row.get("candle_timestamp")
    )
    return {
        "total_predictions": len(predictions),
        "buy_count": len(buy),
        "sell_count": len(sell),
        "hold_count": len(hold),
        "coverage": (len(buy) + len(sell)) / len(predictions) if predictions else 0.0,
        "evaluated_directional": len(evaluated),
        "evaluated_buy": len(buy_outcomes),
        "evaluated_sell": len(sell_outcomes),
        "correct_buy": sum(bool(row.get("direction_correct")) for row in buy_outcomes),
        "correct_sell": sum(bool(row.get("direction_correct")) for row in sell_outcomes),
        "buy_precision": precision(buy_outcomes),
        "sell_precision": precision(sell_outcomes),
        "pooled_directional_accuracy": precision(evaluated),
        "average_future_return_after_buy": (
            float(np.mean([row["future_return"] for row in buy_outcomes]))
            if buy_outcomes else 0.0
        ),
        "average_future_return_after_sell": (
            float(np.mean([row["future_return"] for row in sell_outcomes]))
            if sell_outcomes else 0.0
        ),
        "prediction_start": timestamps[0] if timestamps else None,
        "prediction_end": timestamps[-1] if timestamps else None,
    }


def shadow_metrics(database, symbol: str, model_identity: str | None = None) -> dict:
    code = _clean_symbol(symbol)
    predictions = [
        row for row in database.get_predictions(code, "H1", limit=100000)
        if row.get("execution_mode") == "shadow"
        and (model_identity is None or row.get("model_identity") == model_identity)
    ]
    outcomes = database.get_shadow_outcomes(code, model_identity)
    result = {
        "symbol": code,
        "execution_mode": "shadow",
        "model_identity": model_identity,
        **_metrics_group(predictions, outcomes),
    }
    if model_identity is None:
        identities = sorted({row["model_identity"] for row in predictions})
        result["by_model_identity"] = {
            identity: _metrics_group(
                [row for row in predictions if row["model_identity"] == identity],
                [row for row in outcomes if row["model_identity"] == identity],
            )
            for identity in identities
        }
    return result


class ShadowForexRuntime:
    def __init__(
        self,
        database,
        *,
        project_root: Path | str,
        config: ShadowRuntimeConfig | None = None,
        storage: ShadowModelStorage | None = None,
    ):
        self.database = database
        self.project_root = Path(project_root)
        self.config = config or ShadowRuntimeConfig.from_environment()
        self.storage = storage or ShadowModelStorage(
            forex_model_root(self.project_root) / "shadow"
        )

    def _entries(self, symbol: str) -> dict[str, dict]:
        return require_shadow_registry(
            self.database, symbol, project_root=self.project_root
        )

    def _h1_timestamps(self, entry: dict) -> pd.Series:
        frame = pd.read_csv(_entry_path(entry, self.project_root), usecols=["timestamp"])
        return frame["timestamp"]

    def train(self, symbol: str) -> dict:
        code = _clean_symbol(symbol)
        _require_shadow_eligible(self.database, code, self.config)
        entries = self._entries(code)
        previous = self.storage.load(code) if self.storage.exists(code) else None
        timestamps = self._h1_timestamps(entries["H1"])
        if previous is not None and not shadow_retrain_due(
            previous["metadata"]["training_last_candle"],
            timestamps,
            self.config.retrain_candles,
        ):
            return {"action": "not_due", **previous["metadata"]}

        frame = load_shadow_multiframe(
            entries, code, project_root=self.project_root
        )
        builder = DatasetBuilder(frame)
        X, y = builder.build(
            horizon=SHADOW_HORIZON,
            feature_profile=SHADOW_FEATURE_PROFILE,
            target_profile=SHADOW_TARGET_PROFILE,
        )
        if len(X) <= 0 or set(pd.Series(y).unique()) != {0, 1}:
            raise ValueError("SHADOW_TRAINING_BINARY_EVIDENCE_INSUFFICIENT")
        positions = h1_oof_positions(len(X))
        oof_scores: list[float] = []
        diagnostics: list[dict] = []
        targets = pd.Series(np.asarray(y), index=X.index)
        for fold, position in enumerate(positions, start=1):
            train_slice = slice(position["train_start"], position["train_end"])
            validation_slice = slice(
                position["validation_start"], position["validation_end"]
            )
            fold_model, _ = fit_frozen_h1_random_forest(
                X.iloc[train_slice], targets.iloc[train_slice]
            )
            scores = fold_model.predict_proba(X.iloc[validation_slice])[:, 1]
            oof_scores.extend(float(value) for value in scores)
            diagnostics.append({
                "fold": fold,
                **position,
                "validation_rows": len(scores),
            })
        reference = build_oof_decision_reference(oof_scores)
        model, resolved_config = fit_frozen_h1_random_forest(X, targets)
        feature_names = [str(name) for name in X.columns]
        generation = next_shadow_generation(
            previous["metadata"] if previous is not None else None
        )
        metadata = {
            "symbol": code,
            "mode": "shadow",
            "model_contract": SHADOW_MODEL_CONTRACT,
            "target_profile": SHADOW_TARGET_PROFILE,
            "target_definition_version": 1,
            "horizon": SHADOW_HORIZON,
            "feature_profile": SHADOW_FEATURE_PROFILE,
            "feature_names_sha256": feature_names_sha256(feature_names),
            "model_family": "RandomForestClassifier",
            "model_config": resolved_config,
            "decision_policy": SHADOW_DECISION_POLICY,
            "score_type": SHADOW_SCORE_TYPE,
            "confidence_semantics": SHADOW_CONFIDENCE_SEMANTICS,
            "training_dataset_hashes": {
                timeframe: entries[timeframe]["source_sha256"]
                for timeframe in REQUIRED_TIMEFRAMES
            },
            "training_dataset_provenance": {
                timeframe: {
                    key: entries[timeframe].get(key)
                    for key in (
                        "provider_used", "external_ticker", "provider_class",
                        "source_fetched_at", "source_sha256",
                        "last_candle_timestamp", "candle_count",
                    )
                }
                for timeframe in REQUIRED_TIMEFRAMES
            },
            "training_timestamp": datetime.now(timezone.utc).isoformat(),
            "training_last_candle": _utc_iso(entries["H1"]["last_candle_timestamp"]),
            "training_rows": len(X),
            "training_class_counts": {
                0: int(np.sum(np.asarray(y) == 0)),
                1: int(np.sum(np.asarray(y) == 1)),
            },
            "oof_diagnostics": diagnostics,
            "model_generation": generation,
        }
        saved = self.storage.save(code, {
            "model": model,
            "feature_names": feature_names,
            "oof_score_reference": reference["oof_score_reference"],
            "metadata": metadata,
        })
        return {"action": "trained", **saved["metadata"]}

    def run_shadow_prediction(self, symbol: str) -> dict:
        code = _clean_symbol(symbol)
        _require_shadow_eligible(self.database, code, self.config)
        entries = self._entries(code)
        bundle = self.storage.load(code)
        frame = load_shadow_multiframe(
            entries, code, project_root=self.project_root
        )
        feature_names = bundle["feature_names"]
        features = DatasetBuilder(frame).predict_features(
            n_rows=1,
            train_columns=feature_names,
            feature_profile=SHADOW_FEATURE_PROFILE,
        )
        if (
            [str(name) for name in features.columns] != feature_names
            or feature_names_sha256(features.columns)
            != bundle["metadata"]["feature_names_sha256"]
        ):
            raise ValueError("SHADOW_PREDICTION_FEATURE_CONTRACT_MISMATCH")
        score = float(bundle["model"].predict_proba(features)[:, 1][0])
        decision = _decision(score, bundle["oof_score_reference"])
        candle_timestamp = frame["timestamp"].iloc[-1]
        entry_price = float(frame["close"].iloc[-1])
        provenance = {
            timeframe: {
                "registry_id": entries[timeframe].get("id"),
                "source_sha256": entries[timeframe].get("source_sha256"),
                "last_candle_timestamp": entries[timeframe].get(
                    "last_candle_timestamp"
                ),
                "provider_used": entries[timeframe].get("provider_used"),
            }
            for timeframe in REQUIRED_TIMEFRAMES
        }
        saved = persist_shadow_prediction(
            self.database,
            symbol=code,
            candle_timestamp=candle_timestamp,
            entry_price=entry_price,
            decision=decision,
            model_metadata=bundle["metadata"],
            dataset_provenance=provenance,
        )
        return {"action": "predicted", "prediction": saved}

    def maintain_h1(self, symbol: str) -> dict:
        code = _clean_symbol(symbol)
        _require_shadow_eligible(self.database, code, self.config)
        entries = self._entries(code)
        h1_path = _entry_path(entries["H1"], self.project_root)
        candles = pd.read_csv(h1_path, usecols=["timestamp", "close"])
        try:
            finalized = mature_shadow_outcomes(
                self.database,
                code,
                candles,
                available_at=datetime.now(timezone.utc),
            )
            training = self.train(code)
            prediction = self.run_shadow_prediction(code)
            now = datetime.now(timezone.utc).isoformat()
            self.database.upsert_shadow_scheduler_state({
                "symbol": code,
                "timeframe": "H1",
                "last_success": now,
                "last_error": None,
            })
            return {
                "action": "maintained",
                "outcomes_finalized": finalized,
                "training": training,
                "prediction": prediction,
            }
        except Exception as exc:
            self.database.upsert_shadow_scheduler_state({
                "symbol": code,
                "timeframe": "H1",
                "last_success": None,
                "last_error": f"{type(exc).__name__}: {exc}",
            })
            raise

    def metrics(self, symbol: str) -> dict:
        return shadow_metrics(self.database, symbol)

    def status(self) -> dict:
        result = {
            "shadow_mode": self.config.enabled,
            "runtime_symbols": list(self.config.runtime_symbols),
            "runtime_provider": self.config.provider,
            "symbols": {},
        }
        for code in self.config.runtime_symbols:
            row = self.database.get_symbol(code)
            entries = {
                timeframe: self.database.get_dataset_registry(code, timeframe)
                for timeframe in REQUIRED_TIMEFRAMES
            }
            ready = {}
            for timeframe, rows in entries.items():
                ready[timeframe] = bool(
                    len(rows) == 1
                    and registry_entry_readiness(
                        rows[0], project_root=self.project_root
                    ).get("ready") is True
                    and rows[0].get("provider_used") == "MT5"
                )
            bundle = None
            artifact_error = None
            if self.storage.exists(code):
                try:
                    bundle = self.storage.load(code)
                except Exception as exc:
                    artifact_error = f"{type(exc).__name__}: {exc}"
            predictions = [
                item for item in self.database.get_predictions(code, "H1", limit=100000)
                if item.get("execution_mode") == "shadow"
            ]
            outcomes = self.database.get_shadow_outcomes(code)
            outcome_ids = {item["prediction_id"] for item in outcomes}
            directional = [
                item for item in predictions if item.get("action") in ("BUY", "SELL")
            ]
            metadata = bundle["metadata"] if bundle is not None else {}
            candles_since = 0
            if bundle is not None and entries["H1"]:
                try:
                    candles_since = count_new_h1_candles(
                        metadata["training_last_candle"],
                        self._h1_timestamps(entries["H1"][0]),
                    )
                except Exception:
                    candles_since = 0
            states = self.database.get_shadow_scheduler_state(code, "H1")
            state = states[0] if states else {}
            result["symbols"][code] = {
                "lifecycle": (row or {}).get("status", "unregistered"),
                "H1_ready": ready["H1"],
                "H4_ready": ready["H4"],
                "D1_ready": ready["D1"],
                "provider": self.config.provider,
                "last_H1_candle": (
                    entries["H1"][0].get("last_candle_timestamp")
                    if entries["H1"] else None
                ),
                "shadow_model_exists": bundle is not None,
                "shadow_model_error": artifact_error,
                "shadow_model_generation": metadata.get("model_generation"),
                "model_training_cutoff": metadata.get("training_last_candle"),
                "candles_until_retrain": (
                    max(0, self.config.retrain_candles - candles_since)
                    if bundle is not None else 0
                ),
                "last_prediction_candle": (
                    predictions[0].get("candle_timestamp") if predictions else None
                ),
                "pending_outcomes": sum(
                    item["prediction_id"] not in outcome_ids for item in directional
                ),
                "finalized_outcomes": len(outcomes),
                "last_scheduler_success": state.get("last_success"),
                "last_scheduler_error": state.get("last_error"),
            }
        return result


def run_shadow_prediction(
    database,
    symbol: str,
    *,
    project_root: Path | str,
    config: ShadowRuntimeConfig | None = None,
) -> dict:
    return ShadowForexRuntime(
        database, project_root=project_root, config=config
    ).run_shadow_prediction(symbol)


__all__ = [
    "DEFAULT_SHADOW_RETRAIN_CANDLES",
    "REQUIRED_TIMEFRAMES",
    "SHADOW_CONFIDENCE_SEMANTICS",
    "SHADOW_DECISION_POLICY",
    "SHADOW_EXECUTION_MODE",
    "SHADOW_FEATURE_PROFILE",
    "SHADOW_HORIZON",
    "SHADOW_MODEL_CONTRACT",
    "SHADOW_MODEL_STAGE",
    "SHADOW_RUNTIME_SYMBOLS",
    "SHADOW_TARGET_PROFILE",
    "ShadowForexRuntime",
    "ShadowModelStorage",
    "ShadowRuntimeConfig",
    "count_new_h1_candles",
    "fetch_pinned_market_data",
    "fixed_shadow_rf_config",
    "load_shadow_multiframe",
    "mature_shadow_outcomes",
    "next_shadow_generation",
    "parse_symbol_list",
    "pinned_mt5_qualification_router",
    "persist_shadow_prediction",
    "require_shadow_registry",
    "require_single_symbol_frame",
    "run_shadow_prediction",
    "shadow_eligible",
    "shadow_metrics",
    "shadow_model_identity",
    "shadow_retrain_due",
]

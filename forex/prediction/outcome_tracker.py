"""Closed-loop prediction and outcome tracking.

The scheduler database is the canonical source for predictions, outcomes and
their performance.  Outcome maturity is based on persisted, closed candles;
elapsed wall-clock time or a spot-price lookup is never sufficient evidence.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from infra.db.database import SQLiteDatabase, stable_prediction_id


_TRADE_ACTIONS = ("BUY", "SELL")
_TIMEFRAME_DURATION = {
    "H1": timedelta(hours=1),
    "H4": timedelta(hours=4),
    "D1": timedelta(days=1),
}


def _utc_iso(value: Any) -> str:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("prediction candle timestamp is invalid")
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.isoformat()


def _decode_json(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


@dataclass
class PredictionRecord:
    id: int | None = None
    prediction_id: str = ""
    pair: str = ""
    timeframe: str = ""
    signal: str = "HOLD"
    entry_price: float = 0.0
    reliability_score: float = 0.0
    regime: str = ""
    mtf_coherent: bool = False
    news_active: bool = False
    timestamp: str = ""
    evaluated: bool = False
    actual_price: float = 0.0
    outcome: str = ""
    price_change: float = 0.0
    direction_correct: bool = False
    evaluation_time: str = ""
    status: str = "PENDING"

    def to_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class OutcomeStats:
    pair: str = ""
    total_predictions: int = 0
    evaluated: int = 0
    correct: int = 0
    incorrect: int = 0
    win_rate: float = 0.0
    avg_reliability: float = 0.0
    avg_price_change: float = 0.0
    best_reliability: float = 0.0
    worst_reliability: float = 0.0

    def to_dict(self) -> dict:
        return dict(self.__dict__)


class OutcomeTracker:
    """Persist final H1 decisions and mature them from real closed candles."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        database: SQLiteDatabase | None = None,
    ):
        if database is not None and db_path is not None:
            raise ValueError("provide database or db_path, not both")
        self.database = database or SQLiteDatabase(str(db_path) if db_path else None)
        self.db_path = self.database.db_path

    def record_prediction(
        self,
        pair: str,
        timeframe: str,
        signal: str,
        entry_price: float,
        reliability_score: float = 0.0,
        regime: str = "",
        mtf_coherent: bool = False,
        news_active: bool = False,
        *,
        candle_timestamp: Any | None = None,
        prediction_timestamp: Any | None = None,
        raw_action: str | None = None,
        horizon_candles: int | None = None,
        model_identity: str | None = None,
        dataset_provenance: dict | None = None,
        prediction_id: str | None = None,
    ) -> str:
        action = str(signal).upper().strip()
        if action not in _TRADE_ACTIONS:
            raise ValueError("only final BUY/SELL actions can enter the outcome loop")
        symbol = str(pair).upper().strip()
        tf = str(timeframe).upper().strip()
        if tf != "H1":
            raise ValueError("only final H1 predictions can enter the outcome loop")
        if not symbol or float(entry_price) <= 0:
            raise ValueError("prediction requires a symbol and positive entry price")
        if candle_timestamp is None:
            candle_timestamp = prediction_timestamp
        if candle_timestamp is None:
            raise ValueError("prediction requires its closed candle identity")
        candle_iso = _utc_iso(candle_timestamp)
        if horizon_candles is None:
            from .dataset_builder import get_pair_config

            horizon_candles = int(get_pair_config(symbol)["horizon"])
        if int(horizon_candles) <= 0:
            raise ValueError("outcome horizon must be a positive candle count")
        uid = prediction_id or stable_prediction_id(symbol, tf, candle_iso, action)
        saved = self.database.save_prediction({
            "prediction_id": uid,
            "symbol": symbol,
            "pair": symbol,
            "timeframe": tf,
            "action": action,
            "direction": action,
            "raw_action": raw_action,
            "confidence": float(reliability_score) / 100.0,
            "reliability_score": float(reliability_score),
            "entry_price": float(entry_price),
            "predicted_at": _utc_iso(prediction_timestamp or datetime.now(timezone.utc)),
            "candle_timestamp": candle_iso,
            "horizon_candles": int(horizon_candles),
            "model_identity": model_identity,
            "dataset_provenance": {
                **(dataset_provenance or {}),
                "regime": regime,
                "mtf_coherent": bool(mtf_coherent),
                "news_active": bool(news_active),
            },
            "status": "PENDING",
        })
        return str(saved["prediction_id"])

    @staticmethod
    def _closed_future_candles(
        candles: pd.DataFrame,
        *,
        after: str,
        timeframe: str,
        available_at: Any,
    ) -> pd.DataFrame:
        if not isinstance(candles, pd.DataFrame):
            candles = pd.DataFrame(candles)
        required = {"timestamp", "close"}
        if not required.issubset(candles.columns):
            raise ValueError("outcome evidence requires timestamp and close columns")
        duration = _TIMEFRAME_DURATION.get(timeframe.upper())
        if duration is None:
            raise ValueError(f"unsupported outcome timeframe: {timeframe}")
        frame = candles.loc[:, ["timestamp", "close"]].copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame = frame.dropna().drop_duplicates("timestamp", keep="last")
        frame = frame.loc[
            frame["close"].map(
                lambda value: math.isfinite(float(value)) and float(value) > 0.0
            )
        ]
        frame = frame.sort_values("timestamp")
        prediction_candle = pd.Timestamp(after)
        if prediction_candle.tzinfo is None:
            prediction_candle = prediction_candle.tz_localize("UTC")
        else:
            prediction_candle = prediction_candle.tz_convert("UTC")
        cutoff = pd.Timestamp(available_at)
        if cutoff.tzinfo is None:
            cutoff = cutoff.tz_localize("UTC")
        else:
            cutoff = cutoff.tz_convert("UTC")
        return frame.loc[
            (frame["timestamp"] > prediction_candle)
            & (frame["timestamp"] + duration <= cutoff)
        ]

    def evaluate_pending(
        self,
        candles: pd.DataFrame | Iterable[dict],
        *,
        pair: str = "",
        timeframe: str = "H1",
        available_at: Any | None = None,
        limit: int = 100,
    ) -> int:
        """Finalize mature predictions once their complete real horizon exists."""
        available_at = available_at or datetime.now(timezone.utc)
        finalized = 0
        for prediction in self.database.get_pending_predictions(pair or None, limit=limit):
            if prediction["timeframe"] != timeframe.upper():
                continue
            action = str(prediction.get("action") or prediction.get("direction") or "").upper()
            if action not in _TRADE_ACTIONS:
                continue
            horizon = prediction.get("horizon_candles")
            if not isinstance(horizon, int) or horizon <= 0:
                continue
            future = self._closed_future_candles(
                candles,
                after=prediction["candle_timestamp"],
                timeframe=prediction["timeframe"],
                available_at=available_at,
            )
            duration = _TIMEFRAME_DURATION[prediction["timeframe"]]
            prediction_candle = pd.Timestamp(prediction["candle_timestamp"])
            if prediction_candle.tzinfo is None:
                prediction_candle = prediction_candle.tz_localize("UTC")
            else:
                prediction_candle = prediction_candle.tz_convert("UTC")
            expected_timestamps = pd.DatetimeIndex(
                prediction_candle + step * duration
                for step in range(1, horizon + 1)
            )
            horizon_rows = future.set_index("timestamp").reindex(expected_timestamps)
            if horizon_rows["close"].isna().any():
                continue
            observed_row = horizon_rows.iloc[-1]
            entry_price = float(prediction["entry_price"])
            observed_price = float(observed_row["close"])
            price_change = observed_price - entry_price
            observed_return = price_change / entry_price
            correct = price_change > 0 if action == "BUY" else price_change < 0
            actual_direction = "BUY" if price_change > 0 else "SELL" if price_change < 0 else "HOLD"
            evaluation_time = expected_timestamps[-1] + duration
            self.database.save_outcome({
                "prediction_id": prediction["prediction_id"],
                "outcome_key": prediction["prediction_id"],
                "symbol": prediction["symbol"],
                "timeframe": prediction["timeframe"],
                "actual_direction": actual_direction,
                "prediction_timestamp": prediction["candle_timestamp"],
                "evaluation_timestamp": evaluation_time.isoformat(),
                "resolved_at": evaluation_time.isoformat(),
                "action": action,
                "entry_price": entry_price,
                "observed_price": observed_price,
                "observed_return": observed_return,
                "result": "win" if correct else "loss",
                "status": "FINALIZED",
                "model_identity": prediction.get("model_identity"),
                "dataset_provenance": _decode_json(prediction.get("dataset_provenance")),
            })
            finalized += 1
        return finalized

    def evaluate_from_csv(
        self,
        csv_path: str | Path,
        *,
        pair: str,
        timeframe: str = "H1",
        available_at: Any | None = None,
    ) -> int:
        path = Path(csv_path)
        if not path.is_file():
            raise FileNotFoundError(f"outcome dataset does not exist: {path}")
        candles = pd.read_csv(path, usecols=["timestamp", "close"])
        return self.evaluate_pending(
            candles,
            pair=pair,
            timeframe=timeframe,
            available_at=available_at,
        )

    def evaluate_prediction(self, *_args, **_kwargs):
        raise RuntimeError(
            "spot-price evaluation is disabled; provide persisted future candles "
            "through evaluate_pending()"
        )

    def auto_evaluate(self, *_args, **_kwargs):
        raise RuntimeError(
            "price_func evaluation is disabled; use evaluate_from_csv() with closed candles"
        )

    def get_pending(self, pair: str = "", limit: int = 50) -> list[dict]:
        return self.database.get_pending_predictions(pair or None, limit=limit)

    def get_stats(self, pair: str = "") -> OutcomeStats:
        predictions = [
            row for row in self.database.get_predictions(symbol=pair or None, limit=100000)
            if (row.get("action") or row.get("direction")) in _TRADE_ACTIONS
        ]
        performance = self.database.get_outcome_performance(pair or None, "H1")
        reliabilities = [
            float(row["confidence"]) * 100.0
            for row in predictions
            if row.get("confidence") is not None
        ]
        stats = OutcomeStats(
            pair=pair,
            total_predictions=len(predictions),
            evaluated=performance["evaluated"],
            correct=performance["correct"],
            incorrect=performance["incorrect"],
            win_rate=performance["win_rate"],
            avg_price_change=performance["avg_return"],
        )
        if reliabilities:
            stats.avg_reliability = sum(reliabilities) / len(reliabilities)
            stats.best_reliability = max(reliabilities)
            stats.worst_reliability = min(reliabilities)
        return stats

    def get_history(
        self, pair: str = "", limit: int = 50, evaluated_only: bool = False
    ) -> list[dict]:
        if evaluated_only:
            rows = self.database.get_finalized_outcomes(pair or None, "H1")
        else:
            rows = self.database.get_predictions(symbol=pair or None, limit=limit)
        return list(reversed(rows[-limit:]))


def cmd_outcome_stats(args: str = "") -> str:
    pair = args.strip().split()[0].upper() if args.strip() else ""
    stats = OutcomeTracker().get_stats(pair=pair)
    return (
        f"Outcome Stats — {pair or 'ALL'}\n"
        f"  Operational predictions: {stats.total_predictions}\n"
        f"  Finalized: {stats.evaluated}\n"
        f"  Wins/Losses: {stats.correct}/{stats.incorrect}\n"
        f"  Win Rate: {stats.win_rate:.1%}"
    )


def cmd_outcome_history(args: str = "") -> str:
    parts = args.strip().split()
    pair = parts[0].upper() if parts else ""
    limit = int(parts[1]) if len(parts) > 1 else 20
    history = OutcomeTracker().get_history(pair=pair, limit=limit, evaluated_only=True)
    if not history:
        return "Sin outcomes finalizados"
    lines = [f"Outcome History ({len(history)})"]
    for row in history:
        lines.append(
            f"  {row['evaluation_timestamp']} | {row['symbol']} {row['timeframe']} | "
            f"{row['action']} | {str(row['result']).upper()}"
        )
    return "\n".join(lines)

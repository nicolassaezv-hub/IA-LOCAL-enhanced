"""Verified model performance projected from canonical finalized outcomes."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from infra.db.database import SQLiteDatabase


_MIN_SAMPLES_FOR_TRUST = 10
_HISTORY_WINDOW_DAYS = 30


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp_in_history_window(value: object) -> bool:
    if not value:
        return False
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp >= _utc_now() - timedelta(days=_HISTORY_WINDOW_DAYS)


class ModelQualityHistory:
    """Read model quality without maintaining a parallel outcome database."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        database: SQLiteDatabase | None = None,
    ):
        if database is not None and db_path is not None:
            raise ValueError("provide database or db_path, not both")
        self._provided_database = database
        self._db_path = str(db_path) if db_path is not None else None

    @property
    def database(self) -> SQLiteDatabase:
        if self._provided_database is None:
            self._provided_database = SQLiteDatabase(self._db_path)
        return self._provided_database

    def record_prediction(self, *_args, **_kwargs):
        raise RuntimeError(
            "ModelQualityHistory is read-only; persist through OutcomeTracker"
        )

    def record_outcome(self, *_args, **_kwargs):
        raise RuntimeError(
            "ModelQualityHistory is read-only; finalize through OutcomeTracker"
        )

    def _matching_outcomes(
        self,
        pair: str,
        horizon: str,
        model_name: str = "",
    ) -> list[dict]:
        outcomes = self.database.get_finalized_outcomes(
            pair.upper(), horizon.upper()
        )
        outcomes = [
            row for row in outcomes
            if _timestamp_in_history_window(row.get("prediction_timestamp"))
        ]
        if model_name:
            outcomes = [
                row for row in outcomes
                if str(row.get("model_identity") or "") == model_name
            ]
        return outcomes

    def get_accuracy(
        self,
        pair: str,
        horizon: str = "H1",
        model_name: str = "",
    ) -> Optional[float]:
        outcomes = self._matching_outcomes(pair, horizon, model_name)
        if len(outcomes) < _MIN_SAMPLES_FOR_TRUST:
            return None
        wins = sum(row.get("result") == "win" for row in outcomes)
        return wins / len(outcomes) * 100.0

    def get_win_rate(self, pair: str, horizon: str = "H1") -> Optional[float]:
        return self.get_accuracy(pair, horizon)

    def get_sample_count(self, pair: str, horizon: str = "H1") -> int:
        return len(self._matching_outcomes(pair, horizon))

    def list_history(self, limit: int = 20) -> list[dict]:
        groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for row in self.database.get_finalized_outcomes():
            if not _timestamp_in_history_window(row.get("prediction_timestamp")):
                continue
            key = (
                row["symbol"],
                row["timeframe"],
                str(row.get("model_identity") or "unknown"),
            )
            groups[key].append(row)
        history = []
        for (pair, horizon, model), outcomes in groups.items():
            samples = len(outcomes)
            wins = sum(row.get("result") == "win" for row in outcomes)
            history.append({
                "pair": pair,
                "horizon": horizon,
                "model": model,
                "accuracy": wins / samples * 100.0,
                "samples": samples,
                "updated": max(row.get("evaluation_timestamp") or "" for row in outcomes),
            })
        return sorted(history, key=lambda row: row["updated"], reverse=True)[:limit]

    def status(self) -> str:
        items = self.list_history()
        if not items:
            return "Sin outcomes finalizados persistidos."
        lines = ["  Model Quality History (outcomes canónicos, ventana 30 días):"]
        for item in items[:10]:
            lines.append(
                f"    {item['pair']}/{item['horizon']} ({item['model']}) — "
                f"{item['accuracy']:.1f}% ({item['samples']} muestras)"
            )
        return "\n".join(lines)


_quality_history = ModelQualityHistory()


def get_quality_history() -> ModelQualityHistory:
    return _quality_history

"""Compatibility view over canonical promoted-model provenance."""
from __future__ import annotations

from pathlib import Path

from infra.db.database import SQLiteDatabase


class ModelCacheManager:
    """Expose active models without maintaining a second model registry."""

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

    def should_retrain(
        self, pair: str, horizon: str = "H1", csv_path: str = ""
    ) -> tuple[bool, str]:
        promoted = [
            row for row in self.database.get_model_provenance(pair.upper())
            if row["timeframe"] == horizon.upper()
            and row["status"] in {"PROMOTED", "INITIAL_TRAINING"}
        ]
        if not promoted:
            return True, "Sin modelo promovido con provenance canónica"
        return (
            False,
            "Modelo promovido vigente; adaptive retrain depende de outcomes nuevos persistidos",
        )

    def register_model(self, *_args, **_kwargs):
        raise RuntimeError(
            "Direct model-cache registration is disabled; use RetrainManager promotion"
        )

    def list_active_models(self) -> list[dict]:
        active: dict[tuple[str, str], dict] = {}
        for row in self.database.get_model_provenance():
            if row["status"] not in {"PROMOTED", "INITIAL_TRAINING"}:
                continue
            key = (row["symbol"], row["timeframe"])
            if key not in active:
                active[key] = {
                    "pair": row["symbol"],
                    "horizon": row["timeframe"],
                    "accuracy": None,
                    "row_count": None,
                    "created_at": row["promoted_at"],
                    "model_id": row["model_id"],
                    "artifact_path": row["artifact_path"],
                }
        return list(active.values())

    def status(self) -> str:
        models = self.list_active_models()
        if not models:
            return "Sin modelos promovidos registrados."
        lines = [f"  Model Cache ({len(models)} modelos promovidos):"]
        for model in models:
            lines.append(
                f"    {model['pair']}/{model['horizon']} — "
                f"{model['model_id']}  {model['created_at'][:10]}"
            )
        return "\n".join(lines)


_model_cache = ModelCacheManager()


def get_model_cache() -> ModelCacheManager:
    return _model_cache

"""Immutable SQLite access contract for audits and snapshot verification."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from forex.prediction.model_storage import ModelStorage
from forex.prediction.retrain_manager import RetrainManager
from infra.db import database as database_module


SQLiteDatabase = database_module.SQLiteDatabase


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sidecars(path: Path) -> set[str]:
    return {
        candidate.name
        for candidate in path.parent.iterdir()
        if candidate.name in {f"{path.name}-wal", f"{path.name}-shm"}
    }


def _candidate(database: SQLiteDatabase, symbol: str = "EURUSD") -> dict:
    from forex.data.symbol_catalog import get_symbol_spec

    spec = get_symbol_spec(symbol)
    return database.register_candidate(
        spec.symbol_code,
        spec.display_name,
        spec.asset_class,
        spec.pip_value,
    )


def _registry_entry(path: Path, timeframe: str = "H1") -> dict:
    return {
        "symbol": "EURUSD",
        "timeframe": timeframe,
        "candle_count": 2000,
        "rolling_window_size": 2000,
        "last_candle_timestamp": "2026-01-01 00:00:00",
        "blob_path": str(path),
        "status": "ready",
    }


def _retrain_run() -> dict:
    now = "2026-01-01T00:00:00+00:00"
    return {
        "run_id": "run-read-only",
        "evidence_key": "evidence-read-only",
        "symbol": "EURUSD",
        "timeframe": "H1",
        "trigger": "initial_training",
        "status": "PENDING",
        "dataset_provenance": {"snapshot": "fixture"},
        "outcome_ids": [],
        "created_at": now,
        "updated_at": now,
    }


def _populate_database(path: Path) -> SQLiteDatabase:
    database = SQLiteDatabase(str(path))
    _candidate(database)
    database.upsert_dataset_registry(_registry_entry(path.parent / "EURUSD_H1.csv"))
    database.save_prediction(
        {
            "symbol": "EURUSD",
            "timeframe": "H1",
            "action": "BUY",
            "candle_timestamp": "2026-01-01T00:00:00+00:00",
            "predicted_at": "2026-01-01T00:00:00+00:00",
        }
    )
    database.save_model_quality(
        {
            "symbol": "EURUSD",
            "timeframe": "H1",
            "accuracy": 0.5,
            "precision": 0.5,
        }
    )
    database.create_retrain_run(_retrain_run())
    return database


def test_read_only_existing_database_supports_representative_reads_immutably(
    tmp_path,
):
    path = tmp_path / "audit.sqlite"
    _populate_database(path)
    before_sha = _sha256(path)
    before_sidecars = _sidecars(path)

    database = SQLiteDatabase(str(path), read_only=True)

    assert database.get_symbol("EURUSD")["status"] == "candidate"
    assert [row["symbol_code"] for row in database.get_symbols_by_status("candidate")] == [
        "EURUSD"
    ]
    assert database.get_dataset_registry("EURUSD", "H1")[0]["status"] == "ready"
    assert database.get_predictions("EURUSD", "H1")[0]["action"] == "BUY"
    assert database.get_outcomes("EURUSD", "H1") == []
    assert database.get_model_quality("EURUSD", "H1")[0]["accuracy"] == 0.5
    assert database.get_retrain_runs("EURUSD")[0]["run_id"] == "run-read-only"
    assert database.get_model_provenance("EURUSD") == []

    assert _sha256(path) == before_sha
    assert _sidecars(path) == before_sidecars == set()


def test_read_only_missing_database_fails_closed_without_creating_parent(tmp_path):
    path = tmp_path / "missing-parent" / "missing.sqlite"

    with pytest.raises(FileNotFoundError, match="SQLITE_READ_ONLY_DATABASE_NOT_FOUND"):
        SQLiteDatabase(str(path), read_only=True)

    assert not path.exists()
    assert not path.parent.exists()


def test_read_only_constructor_does_not_initialize_schema(tmp_path):
    path = tmp_path / "empty.sqlite"
    sqlite3.connect(path).close()
    before_sha = _sha256(path)

    database = SQLiteDatabase(str(path), read_only=True)
    with database._connection() as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()

    assert tables == []
    assert _sha256(path) == before_sha
    assert _sidecars(path) == set()


def test_read_only_mutating_apis_raise_explicit_error(tmp_path):
    path = tmp_path / "guard.sqlite"
    _populate_database(path)
    database = SQLiteDatabase(str(path), read_only=True)
    error = database_module.SQLiteReadOnlyError

    mutations = [
        lambda: _candidate(database),
        lambda: database.upsert_dataset_registry(
            _registry_entry(tmp_path / "EURUSD_H1.csv")
        ),
        lambda: database.save_prediction(
            {
                "symbol": "EURUSD",
                "timeframe": "H1",
                "action": "SELL",
                "candle_timestamp": "2026-01-02T00:00:00+00:00",
            }
        ),
        lambda: database.save_model_quality(
            {"symbol": "EURUSD", "timeframe": "H1"}
        ),
        lambda: database.create_retrain_run(
            {**_retrain_run(), "run_id": "another-run", "evidence_key": "another"}
        ),
        lambda: database.finalize_model_promotion(
            "run-read-only", {"status": "PROMOTED"}
        ),
    ]

    for mutation in mutations:
        with pytest.raises(error, match="SQLITE_READ_ONLY_WRITE_FORBIDDEN"):
            mutation()


def test_writable_default_still_initializes_wal_schema_and_supports_writes(tmp_path):
    path = tmp_path / "writable.sqlite"

    database = SQLiteDatabase(str(path))
    symbol = _candidate(database)

    assert path.is_file()
    assert symbol["symbol_code"] == "EURUSD"
    assert database.get_symbol("EURUSD")["status"] == "candidate"
    with sqlite3.connect(path) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert journal_mode == "wal"
    assert "supported_symbols" in tables


def test_retrain_snapshot_validation_with_read_only_database_is_physically_immutable(
    tmp_path,
):
    from forex.data.indicator_delta import INDICATOR_MIN_HISTORY

    path = tmp_path / "snapshot.sqlite"
    writable = SQLiteDatabase(str(path))
    dataset_root = tmp_path / "data" / "forex"
    dataset_root.mkdir(parents=True)
    for timeframe, frequency in (("H1", "h"), ("H4", "4h"), ("D1", "D")):
        frame = pd.DataFrame(
            {
                "timestamp": pd.date_range("2010-01-01", periods=2000, freq=frequency),
                "open": 1.0,
                "high": 1.1,
                "low": 0.9,
                "close": 1.05,
                "volume": 100.0,
            }
        )
        for column in INDICATOR_MIN_HISTORY:
            frame[column] = 1.0
        dataset_path = (dataset_root / f"EURUSD_{timeframe}.csv").resolve()
        frame.to_csv(dataset_path, index=False)
        writable.upsert_dataset_registry(
            {
                "symbol": "EURUSD",
                "timeframe": timeframe,
                "candle_count": 2000,
                "rolling_window_size": 2000,
                "last_candle_timestamp": str(frame["timestamp"].iloc[-1]),
                "blob_path": str(dataset_path),
                "status": "ready",
            }
        )

    before_sha = _sha256(path)
    before_sidecars = _sidecars(path)
    read_only = SQLiteDatabase(str(path), read_only=True)
    manager = RetrainManager(
        database=read_only,
        storage=ModelStorage(tmp_path / "models"),
        dataset_root=dataset_root,
    )

    snapshot = manager.capture_training_snapshot("EURUSD")

    assert manager.validate_training_snapshot(snapshot) == snapshot
    assert snapshot["snapshot_sha256"]
    assert _sha256(path) == before_sha
    assert _sidecars(path) == before_sidecars == set()

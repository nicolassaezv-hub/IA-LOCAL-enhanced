"""Additive SQLite persistence for H1 directional score semantics."""
from __future__ import annotations

import hashlib
import sqlite3

import pytest

from forex.prediction.h1_directional import (
    H1_CONFIDENCE_SEMANTICS,
    H1_DECISION_POLICY,
    H1_FEATURE_PROFILE,
    H1_MODEL_CONTRACT,
    H1_SCORE_TYPE,
    H1_TARGET_DEFINITION_VERSION,
    H1_TARGET_PROFILE,
)
from infra.db.database import SQLiteDatabase, SQLiteReadOnlyError


H1_FIELDS = {
    "model_contract": H1_MODEL_CONTRACT,
    "target_profile": H1_TARGET_PROFILE,
    "target_definition_version": H1_TARGET_DEFINITION_VERSION,
    "feature_profile": H1_FEATURE_PROFILE,
    "score_type": H1_SCORE_TYPE,
    "direction_score": 0.8123456789,
    "decision_percentile": 0.80,
    "decision_policy": H1_DECISION_POLICY,
    "confidence_semantics": H1_CONFIDENCE_SEMANTICS,
}


def _prediction(**overrides):
    prediction = {
        "prediction_id": "pred-h1-round-trip",
        "symbol": "EURUSD",
        "timeframe": "H1",
        "action": "BUY",
        "confidence": 0.60,
        "entry_price": 1.10,
        "predicted_at": "2026-01-01T01:00:00+00:00",
        "candle_timestamp": "2026-01-01T00:00:00+00:00",
        "horizon_candles": 12,
        "model_identity": "synthetic-h1",
        "dataset_provenance": {"snapshot_sha256": "synthetic"},
        **H1_FIELDS,
    }
    prediction.update(overrides)
    return prediction


def _replace_predictions_with_legacy_schema(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            DROP INDEX IF EXISTS idx_predictions_uid;
            DROP INDEX IF EXISTS idx_predictions_pending;
            ALTER TABLE predictions RENAME TO predictions_current;
            CREATE TABLE predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id TEXT,
                symbol TEXT, timeframe TEXT, direction TEXT,
                action TEXT, raw_action TEXT,
                confidence REAL, entry_price REAL,
                stop_loss REAL, take_profit REAL,
                features_snapshot TEXT,
                pipeline_version TEXT,
                predicted_at TEXT, candle_timestamp TEXT,
                horizon_candles INTEGER,
                model_identity TEXT,
                dataset_provenance TEXT,
                status TEXT DEFAULT 'PENDING',
                resolved INTEGER DEFAULT 0
            );
            INSERT INTO predictions (
                prediction_id, symbol, timeframe, direction, action, confidence,
                predicted_at, candle_timestamp, horizon_candles, status, resolved
            ) VALUES (
                'legacy-row', 'EURUSD', 'H1', 'BUY', 'BUY', 0.70,
                '2026-01-01', '2026-01-01', 12, 'PENDING', 0
            );
            DROP TABLE predictions_current;
            """
        )


def test_prediction_schema_migrates_additively_and_preserves_legacy_row(tmp_path):
    path = tmp_path / "legacy.sqlite"
    SQLiteDatabase(str(path))
    _replace_predictions_with_legacy_schema(path)

    database = SQLiteDatabase(str(path))
    rows = database.get_predictions("EURUSD", "H1")
    with sqlite3.connect(path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(predictions)")
        }

    assert set(H1_FIELDS) <= columns
    assert rows[0]["prediction_id"] == "legacy-row"
    assert all(rows[0][field] is None for field in H1_FIELDS)


def test_h1_prediction_score_metadata_round_trips_exactly(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "round-trip.sqlite"))

    saved = database.save_prediction(_prediction())
    loaded = database.get_prediction(saved["prediction_id"])

    for field, value in H1_FIELDS.items():
        assert loaded[field] == value
    assert loaded["confidence"] == 0.60
    assert "est_prob_correct" not in loaded


def test_legacy_prediction_write_remains_backward_compatible(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "legacy-write.sqlite"))

    saved = database.save_prediction(
        {
            "symbol": "EURUSD",
            "timeframe": "H1",
            "action": "BUY",
            "confidence": 0.70,
            "candle_timestamp": "2026-01-01T00:00:00+00:00",
        }
    )

    assert saved["action"] == "BUY"
    assert saved["confidence"] == 0.70
    assert all(saved[field] is None for field in H1_FIELDS)


def test_read_only_h1_inspection_is_physically_immutable_and_rejects_write(tmp_path):
    path = tmp_path / "read-only.sqlite"
    writable = SQLiteDatabase(str(path))
    writable.save_prediction(_prediction())
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    before_sidecars = {
        candidate.name for candidate in path.parent.iterdir()
        if candidate.name in {f"{path.name}-wal", f"{path.name}-shm"}
    }

    read_only = SQLiteDatabase(str(path), read_only=True)
    loaded = read_only.get_prediction("pred-h1-round-trip")
    with pytest.raises(SQLiteReadOnlyError, match="SQLITE_READ_ONLY_WRITE_FORBIDDEN"):
        read_only.save_prediction(_prediction(prediction_id="forbidden"))

    assert loaded["model_contract"] == H1_MODEL_CONTRACT
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert {
        candidate.name for candidate in path.parent.iterdir()
        if candidate.name in {f"{path.name}-wal", f"{path.name}-shm"}
    } == before_sidecars == set()

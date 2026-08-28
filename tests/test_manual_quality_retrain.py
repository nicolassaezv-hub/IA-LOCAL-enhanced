"""Hardening contract for deliberate manual quality retraining."""
from __future__ import annotations

import ast
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from forex.prediction.model_storage import ModelStorage, _PROMOTION_AUTHORITY
from forex.prediction.retrain_manager import RetrainManager
from infra.db.database import PersistenceConflictError, SQLiteDatabase


_LEGACY_RETRAIN_COLUMNS = (
    "run_id",
    "evidence_key",
    "symbol",
    "timeframe",
    "trigger",
    "status",
    "source_model_path",
    "source_model_sha256",
    "dataset_provenance",
    "outcome_ids",
    "last_outcome_id",
    "artifact_path",
    "artifact_sha256",
    "latest_path",
    "error",
    "owner_token",
    "heartbeat_at",
    "created_at",
    "updated_at",
    "validated_at",
    "promoted_at",
)

_LEGACY_PROVENANCE_COLUMNS = (
    "model_id",
    "retrain_run_id",
    "symbol",
    "timeframe",
    "artifact_path",
    "artifact_sha256",
    "source_model_path",
    "source_model_sha256",
    "dataset_provenance",
    "outcome_ids",
    "trained_at",
    "validated_at",
    "promoted_at",
    "status",
)


def _set_active_fixture(database: SQLiteDatabase, symbol: str = "EURUSD") -> None:
    from forex.data.symbol_catalog import get_symbol_spec

    spec = get_symbol_spec(symbol)
    database.register_candidate(
        spec.symbol_code, spec.display_name, spec.asset_class, spec.pip_value
    )
    with database._connection() as connection:
        connection.execute(
            "UPDATE supported_symbols SET status='active' WHERE symbol_code=?",
            (symbol,),
        )


def _create_prepatch_database(path):
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE supported_symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol_code TEXT UNIQUE NOT NULL,
                display_name TEXT,
                pip_value REAL DEFAULT 0.0001,
                status TEXT DEFAULT 'active',
                added_at TEXT
            );
            CREATE TABLE retrain_runs (
                run_id TEXT PRIMARY KEY,
                evidence_key TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                trigger TEXT NOT NULL,
                status TEXT NOT NULL,
                source_model_path TEXT,
                source_model_sha256 TEXT,
                dataset_provenance TEXT,
                outcome_ids TEXT NOT NULL,
                last_outcome_id INTEGER,
                artifact_path TEXT,
                artifact_sha256 TEXT,
                latest_path TEXT,
                error TEXT,
                owner_token TEXT,
                heartbeat_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                validated_at TEXT,
                promoted_at TEXT
            );
            CREATE TABLE model_provenance (
                model_id TEXT PRIMARY KEY,
                retrain_run_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                artifact_sha256 TEXT NOT NULL,
                source_model_path TEXT,
                source_model_sha256 TEXT,
                dataset_provenance TEXT NOT NULL,
                outcome_ids TEXT NOT NULL,
                trained_at TEXT NOT NULL,
                validated_at TEXT NOT NULL,
                promoted_at TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE scheduler_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timeframe TEXT,
                started_at TEXT,
                finished_at TEXT,
                status TEXT,
                symbols_processed INTEGER,
                predictions_generated INTEGER,
                errors_count INTEGER,
                log_blob_path TEXT,
                interruption_reason TEXT,
                recovered_at TEXT
            );
            CREATE TABLE predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id TEXT,
                symbol TEXT,
                timeframe TEXT,
                direction TEXT,
                action TEXT,
                raw_action TEXT,
                confidence REAL,
                entry_price REAL,
                stop_loss REAL,
                take_profit REAL,
                features_snapshot TEXT,
                pipeline_version TEXT,
                predicted_at TEXT,
                candle_timestamp TEXT,
                horizon_candles INTEGER,
                model_identity TEXT,
                dataset_provenance TEXT,
                status TEXT DEFAULT 'PENDING',
                resolved INTEGER DEFAULT 0
            );
            CREATE TABLE outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id TEXT,
                outcome_key TEXT,
                symbol TEXT,
                timeframe TEXT,
                actual_direction TEXT,
                pnl_pips REAL,
                hit_tp INTEGER,
                hit_sl INTEGER,
                resolved_at TEXT,
                prediction_timestamp TEXT,
                evaluation_timestamp TEXT,
                action TEXT,
                entry_price REAL,
                observed_price REAL,
                observed_return REAL,
                result TEXT,
                status TEXT,
                model_identity TEXT,
                dataset_provenance TEXT
            );
        """)
        connection.executemany(
            "INSERT INTO supported_symbols "
            "(symbol_code,display_name,pip_value,status,added_at) "
            "VALUES (?,?,?,?,?)",
            [
                ("EURUSD", "EUR/USD", 0.0001, "active", "2025-01-01"),
                ("GBPUSD", "GBP/USD", 0.0001, "active", "2025-01-01"),
                ("USDJPY", "USD/JPY", 0.01, "active", "2025-01-01"),
                ("AUDUSD", "AUD/USD", 0.0001, "active", "2025-01-01"),
            ],
        )


def _insert_legacy_run(connection, **overrides):
    values = {
        "run_id": "run",
        "evidence_key": "evidence",
        "symbol": "EURUSD",
        "timeframe": "H1",
        "trigger": "initial_training",
        "status": "PROMOTED",
        "source_model_path": None,
        "source_model_sha256": None,
        "dataset_provenance": "{}",
        "outcome_ids": "[]",
        "last_outcome_id": None,
        "artifact_path": None,
        "artifact_sha256": None,
        "latest_path": None,
        "error": None,
        "owner_token": None,
        "heartbeat_at": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "validated_at": "2026-01-01T00:00:00+00:00",
        "promoted_at": "2026-01-01T00:00:00+00:00",
    }
    values.update(overrides)
    columns = ",".join(_LEGACY_RETRAIN_COLUMNS)
    placeholders = ",".join(f":{column}" for column in _LEGACY_RETRAIN_COLUMNS)
    connection.execute(
        f"INSERT INTO retrain_runs ({columns}) VALUES ({placeholders})", values
    )


def _insert_legacy_provenance(connection, **values):
    columns = ",".join(_LEGACY_PROVENANCE_COLUMNS)
    placeholders = ",".join(f":{column}" for column in _LEGACY_PROVENANCE_COLUMNS)
    connection.execute(
        f"INSERT INTO model_provenance ({columns}) VALUES ({placeholders})",
        values,
    )


def _legacy_alias(monkeypatch, manager, storage, pair="EURUSD"):
    _set_active_fixture(manager.database, pair)
    with monkeypatch.context() as patch:
        patch.setattr(
            RetrainManager,
            "_initial_eligibility_error",
            staticmethod(lambda _metadata: ""),
        )
        patch.setattr(
            RetrainManager,
            "_production_eligibility_error",
            classmethod(lambda _cls, *_args, **_kwargs: ""),
        )
        manager.promote_initial_model(
            SimpleNamespace(version="legacy", sufficient=True),
            pair=pair,
            dataset_provenance={"path": f"{pair}_H1.csv"},
            metadata={"precision": 0.70},
        )
    return storage.base_dir / f"latest_{pair}.pkl"


def _snapshot(manager, dataset_root, pair="EURUSD"):
    datasets = {}
    for timeframe in ("H1", "H4", "D1"):
        path = (dataset_root / f"{pair}_{timeframe}.csv").resolve()
        datasets[timeframe] = {
            "evidence_id": {"H1": 1, "H4": 2, "D1": 3}[timeframe],
            "canonical_path": str(path),
            "sha256": manager.storage.checksum(path),
            "row_count": 2000,
            "latest_candle_timestamp": "2026-08-14 00:00:00",
            "symbol": pair,
            "timeframe": timeframe,
            "rolling_ready": True,
        }
    result = {"symbol": pair, "timeframe": "H1", "datasets": datasets}
    result["snapshot_sha256"] = manager.dataset_provenance_sha256(result)
    return result


@pytest.fixture
def manual_env(tmp_path, monkeypatch):
    database = SQLiteDatabase(str(tmp_path / "manual.sqlite"))
    storage = ModelStorage(tmp_path / "models")
    dataset_root = tmp_path / "data" / "forex"
    dataset_root.mkdir(parents=True)
    for timeframe in ("H1", "H4", "D1"):
        (dataset_root / f"EURUSD_{timeframe}.csv").write_text(
            f"fixture-{timeframe}-v1", encoding="utf-8"
        )
    manager = RetrainManager(
        database=database,
        storage=storage,
        dataset_root=dataset_root,
    )
    latest = _legacy_alias(monkeypatch, manager, storage)

    def capture(pair):
        return _snapshot(manager, dataset_root, pair)

    def validate(expected):
        current = capture(expected.get("symbol", ""))
        if current != expected:
            raise ValueError(
                "DATASET_SNAPSHOT_CONFLICT: canonical H1/H4/D1 evidence changed"
            )
        return current

    monkeypatch.setattr(manager, "capture_training_snapshot", capture)
    monkeypatch.setattr(manager, "validate_training_snapshot", validate)
    return database, storage, manager, dataset_root, latest


def _eligible_result(symbol, timeframe, context, *, changes=None):
    metadata = {
        "symbol": symbol,
        "timeframe": timeframe,
        "promotion_type": context["trigger"],
        "dataset_provenance_sha256": RetrainManager.dataset_provenance_sha256(
            context["dataset_provenance"]
        ),
        "quality_gate": {"passed": True, "approved": True, "score": 90.0},
        "precision": 0.70,
        "wfv": {
            "folds": [
                {"fold": 1, "tp": 21, "fp": 9, "signals": 30,
                 "validation_size": 300, "precision": 0.70, "accuracy": 0.70},
                {"fold": 2, "tp": 21, "fp": 9, "signals": 30,
                 "validation_size": 300, "precision": 0.70, "accuracy": 0.70},
            ],
            "avg_precision": 0.70,
            "median_precision": 0.70,
            "total_tp": 42,
            "total_fp": 18,
            "total_signals": 60,
            "pooled_precision": 0.70,
            "evidence_sufficient": True,
            "wfv_passed": True,
        },
        "eligibility": {
            "quality_gate_passed": True,
            "wfv_passed": True,
            "calibration_passed": True,
            "validation_passed": True,
            "validation_precision": 0.70,
            "model_valid": True,
        },
    }
    if changes:
        for section, values in changes.items():
            if isinstance(values, dict):
                metadata.setdefault(section, {}).update(values)
            else:
                metadata[section] = values
    return {
        "model": SimpleNamespace(version="manual", sufficient=True),
        "feature_names": ["feature"],
        "metadata": metadata,
    }


def test_prepatch_sqlite_schema_migrates_additively_and_remains_auditable(
    tmp_path,
):
    db_path = tmp_path / "legacy.sqlite"
    model_root = tmp_path / "models"
    storage = ModelStorage(model_root)
    _create_prepatch_database(db_path)

    def artifact(symbol, run_id, trigger, provenance, *, legacy=False):
        metadata = (
            {"precision": 0.70, "promotion_type": "initial_training"}
            if legacy
            else _eligible_result(
                symbol,
                "H1",
                {"trigger": trigger, "dataset_provenance": provenance},
            )["metadata"]
        )
        candidate = storage.stage_model(
            SimpleNamespace(version=run_id, sufficient=True),
            name=f"ensemble_{symbol}_H1",
            version=run_id,
            metadata=metadata,
        )
        latest = storage.base_dir / f"latest_{symbol}.pkl"
        latest.write_bytes(candidate.read_bytes())
        return candidate, latest, storage.checksum(candidate)

    initial_provenance = {"path": "USDJPY_H1.csv", "rows": 2000}
    initial_artifact, initial_latest, initial_sha = artifact(
        "USDJPY", "initial_usdjpy", "initial_training", initial_provenance
    )
    legacy_provenance = {"path": "EURUSD_H1.csv", "rows": 2000}
    legacy_artifact, legacy_latest, legacy_sha = artifact(
        "EURUSD",
        "initial_eurusd_legacy",
        "initial_training",
        legacy_provenance,
        legacy=True,
    )
    bootstrap_provenance = {"path": "AUDUSD_H1.csv", "rows": 2000}
    bootstrap_artifact, bootstrap_latest, bootstrap_sha = artifact(
        "AUDUSD",
        "bootstrap_audusd",
        "bootstrap_revalidation",
        bootstrap_provenance,
    )

    with sqlite3.connect(db_path) as connection:
        for run in (
            {
                "run_id": "initial_usdjpy",
                "evidence_key": "initial-usdjpy-evidence",
                "symbol": "USDJPY",
                "trigger": "initial_training",
                "dataset_provenance": json.dumps(initial_provenance, sort_keys=True),
                "artifact_path": str(initial_artifact),
                "artifact_sha256": initial_sha,
                "latest_path": str(initial_latest),
            },
            {
                "run_id": "initial_eurusd_legacy",
                "evidence_key": "initial-eurusd-evidence",
                "symbol": "EURUSD",
                "trigger": "initial_training",
                "dataset_provenance": json.dumps(legacy_provenance, sort_keys=True),
                "artifact_path": str(legacy_artifact),
                "artifact_sha256": legacy_sha,
                "latest_path": str(legacy_latest),
            },
            {
                "run_id": "bootstrap_audusd",
                "evidence_key": "bootstrap-audusd-evidence",
                "symbol": "AUDUSD",
                "trigger": "bootstrap_revalidation",
                "dataset_provenance": json.dumps(
                    bootstrap_provenance, sort_keys=True
                ),
                "artifact_path": str(bootstrap_artifact),
                "artifact_sha256": bootstrap_sha,
                "latest_path": str(bootstrap_latest),
            },
        ):
            _insert_legacy_run(connection, **run)

        failed_error = "ValueError: QUALITY_GATE: VALIDATION_GATE"
        _insert_legacy_run(
            connection,
            run_id="bootstrap_eurusd_failed",
            evidence_key="bootstrap-eurusd-failed-evidence",
            symbol="EURUSD",
            trigger="bootstrap_revalidation",
            status="FAILED",
            source_model_path=str(legacy_latest),
            source_model_sha256=legacy_sha,
            dataset_provenance=json.dumps({"registry_id": 1}),
            artifact_path=None,
            artifact_sha256=None,
            latest_path=None,
            error=failed_error,
            validated_at=None,
            promoted_at=None,
        )
        _insert_legacy_run(
            connection,
            run_id="legacy_completed",
            evidence_key="legacy-completed-evidence",
            symbol="NZDUSD",
            trigger="manual",
            status="COMPLETED",
            dataset_provenance=json.dumps({"registry_id": 9}),
            artifact_path="legacy-candidate.pkl",
            artifact_sha256="c" * 64,
            latest_path="latest_NZDUSD.pkl",
        )

        for row in (
            {
                "model_id": "model_initial_usdjpy",
                "retrain_run_id": "initial_usdjpy",
                "symbol": "USDJPY",
                "artifact_path": str(initial_artifact),
                "artifact_sha256": initial_sha,
                "dataset_provenance": json.dumps(
                    initial_provenance, sort_keys=True
                ),
                "status": "INITIAL_TRAINING",
            },
            {
                "model_id": "model_initial_eurusd",
                "retrain_run_id": "initial_eurusd_legacy",
                "symbol": "EURUSD",
                "artifact_path": str(legacy_artifact),
                "artifact_sha256": legacy_sha,
                "dataset_provenance": json.dumps(
                    legacy_provenance, sort_keys=True
                ),
                "status": "INITIAL_TRAINING",
            },
            {
                "model_id": "model_bootstrap_audusd",
                "retrain_run_id": "bootstrap_audusd",
                "symbol": "AUDUSD",
                "artifact_path": str(bootstrap_artifact),
                "artifact_sha256": bootstrap_sha,
                "source_model_path": "latest_AUDUSD_legacy.pkl",
                "source_model_sha256": "a" * 64,
                "dataset_provenance": json.dumps(
                    bootstrap_provenance, sort_keys=True
                ),
                "status": "PROMOTED",
            },
        ):
            provenance_row = {
                "timeframe": "H1",
                "source_model_path": None,
                "source_model_sha256": None,
                "outcome_ids": "[]",
                "trained_at": "2026-01-01T00:00:00+00:00",
                "validated_at": "2026-01-01T00:00:00+00:00",
                "promoted_at": "2026-01-01T00:00:00+00:00",
                **row,
            }
            _insert_legacy_provenance(connection, **provenance_row)
        connection.execute(
            """
            INSERT INTO scheduler_runs (
                id, timeframe, started_at, finished_at, status,
                symbols_processed, predictions_generated, errors_count,
                log_blob_path, interruption_reason, recovered_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                41,
                "H1",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T01:00:00+00:00",
                "completed",
                4,
                3,
                0,
                "scheduler.log",
                None,
                None,
            ),
        )
        connection.row_factory = sqlite3.Row
        before_runs = {
            row["run_id"]: dict(row)
            for row in connection.execute("SELECT * FROM retrain_runs")
        }
        before_provenance = {
            row["model_id"]: dict(row)
            for row in connection.execute("SELECT * FROM model_provenance")
        }
        before_scheduler = dict(
            connection.execute(
                "SELECT * FROM scheduler_runs WHERE id=41"
            ).fetchone()
        )
        before_rootpages = {
            row["name"]: row["rootpage"]
            for row in connection.execute(
                """
                SELECT name, rootpage FROM sqlite_master
                WHERE type='table'
                  AND name IN ('retrain_runs','model_provenance','scheduler_runs')
                """
            )
        }

    first = SQLiteDatabase(str(db_path))
    second = SQLiteDatabase(str(db_path))

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        after_runs = {
            row["run_id"]: dict(row)
            for row in connection.execute("SELECT * FROM retrain_runs")
        }
        after_provenance = {
            row["model_id"]: dict(row)
            for row in connection.execute("SELECT * FROM model_provenance")
        }
        retrain_columns = {
            row["name"]: dict(row)
            for row in connection.execute("PRAGMA table_info(retrain_runs)")
        }
        provenance_columns = {
            row["name"]: dict(row)
            for row in connection.execute("PRAGMA table_info(model_provenance)")
        }
        indexes = {
            row["name"]: row["sql"]
            for row in connection.execute(
                """
                SELECT name, sql FROM sqlite_master
                WHERE type='index' AND name LIKE 'idx_manual_retrain_%'
                """
            )
        }
        after_rootpages = {
            row["name"]: row["rootpage"]
            for row in connection.execute(
                """
                SELECT name, rootpage FROM sqlite_master
                WHERE type='table'
                  AND name IN ('retrain_runs','model_provenance','scheduler_runs')
                """
            )
        }
        scheduler = dict(
            connection.execute(
                "SELECT * FROM scheduler_runs WHERE id=41"
            ).fetchone()
        )
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]

    assert first.db_path == second.db_path == str(db_path)
    assert integrity == "ok"
    assert before_rootpages == after_rootpages
    assert scheduler == before_scheduler
    assert set(after_runs) == set(before_runs)
    assert set(after_provenance) == set(before_provenance)
    for run_id, before in before_runs.items():
        assert {column: after_runs[run_id][column] for column in before} == before
        assert after_runs[run_id]["request_id"] is None
    for model_id, before in before_provenance.items():
        assert {
            column: after_provenance[model_id][column] for column in before
        } == before
        assert after_provenance[model_id]["trigger"] is None
    assert retrain_columns["request_id"]["notnull"] == 0
    assert retrain_columns["request_id"]["dflt_value"] is None
    assert provenance_columns["trigger"]["notnull"] == 0
    assert provenance_columns["trigger"]["dflt_value"] is None
    assert set(indexes) == {
        "idx_manual_retrain_request",
        "idx_manual_retrain_active",
    }
    assert all("WHERE trigger='manual_quality_retrain'" in sql for sql in indexes.values())
    assert after_runs["bootstrap_eurusd_failed"]["status"] == "FAILED"
    assert after_runs["bootstrap_eurusd_failed"]["error"] == failed_error
    assert after_runs["legacy_completed"]["status"] == "COMPLETED"

    manager = RetrainManager(database=first, storage=storage)
    assert manager.audit_pair_model("USDJPY")["eligible"] is True
    legacy_audit = manager.audit_pair_model("EURUSD")
    assert legacy_audit["reason"] == "WFV_EVIDENCE_MISSING"
    assert legacy_audit["bootstrap_revalidation"] is True
    assert manager.audit_pair_model("AUDUSD")["eligible"] is True
    failed_before = next(
        row for row in first.get_retrain_runs("EURUSD", limit=100000)
        if row["run_id"] == "bootstrap_eurusd_failed"
    )
    repeated = manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance={"registry_id": 999}
    )
    failed_after = next(
        row for row in first.get_retrain_runs("EURUSD", limit=100000)
        if row["run_id"] == "bootstrap_eurusd_failed"
    )
    assert repeated["run_id"] == "bootstrap_eurusd_failed"
    assert repeated["status"] == "FAILED"
    assert failed_after == failed_before


def _patch_pipeline_training(monkeypatch, *, failed_gate=None):
    from forex.prediction import integrated_pipeline, roadmap_v_integration

    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=320, freq="h"),
        "close": range(320),
        "pair": ["EURUSD"] * 320,
    })
    X = pd.DataFrame({"feature": range(300)})
    y = pd.Series([0, 1] * 150)

    class Builder:
        def __init__(self, _frame):
            pass

        def build(self, **_kwargs):
            return X, y

    approved = failed_gate != "QUALITY_GATE"
    trainer = SimpleNamespace(
        model=SimpleNamespace(version="manual", sufficient=True),
        model_valid=failed_gate != "MODEL_VALID_GATE",
        calibration_sufficient=failed_gate != "CALIBRATION_GATE",
        validation_sufficient=failed_gate != "VALIDATION_GATE",
    )
    if failed_gate == "WFV_GATE":
        wfv = {
            "folds": [
                {"fold": 1, "tp": 81, "fp": 64, "signals": 145,
                 "validation_size": 300, "precision": 81 / 145,
                 "accuracy": 0.4933},
                {"fold": 2, "tp": 1, "fp": 0, "signals": 1,
                 "validation_size": 300, "precision": 1.0,
                 "accuracy": 0.48},
            ],
            "avg_precision": round(((81 / 145) + 1.0) / 2, 4),
            "median_precision": round(((81 / 145) + 1.0) / 2, 4),
            "total_tp": 82,
            "total_fp": 64,
            "total_signals": 146,
            "pooled_precision": 82 / 146,
            "evidence_sufficient": False,
            "wfv_passed": False,
        }
    else:
        wfv = {
            "folds": [
                {"fold": 1, "tp": 21, "fp": 9, "signals": 30,
                 "validation_size": 300, "precision": 0.70, "accuracy": 0.70},
                {"fold": 2, "tp": 21, "fp": 9, "signals": 30,
                 "validation_size": 300, "precision": 0.70, "accuracy": 0.70},
            ],
            "avg_precision": 0.70,
            "median_precision": 0.70,
            "total_tp": 42,
            "total_fp": 18,
            "total_signals": 60,
            "pooled_precision": 0.70,
            "evidence_sufficient": True,
            "wfv_passed": True,
        }
    monkeypatch.setattr(integrated_pipeline, "_load", lambda *_a, **_k: frame)
    monkeypatch.setattr(integrated_pipeline, "build_features", lambda value: value)
    monkeypatch.setattr(integrated_pipeline, "DatasetBuilder", Builder)
    monkeypatch.setattr(
        integrated_pipeline,
        "train_with_wfv",
        lambda *_a, **_k: (trainer, dict(wfv), 0.80, 0.70),
    )
    monkeypatch.setattr(
        roadmap_v_integration,
        "run_quality_gate",
        lambda *_a, **_k: (
            approved,
            SimpleNamespace(
                approved=approved,
                global_score=90.0 if approved else 40.0,
                critical_count=0 if approved else 1,
                warning_count=0,
                recommendation="fixture quality result",
            ),
        ),
    )


def _pipeline(storage, database):
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

    pipeline = object.__new__(ForexIntegratedPipeline)
    pipeline.storage = storage
    pipeline.closed_loop_database = database
    pipeline._horizon = 12
    pipeline._rr_ratio = 1.0
    return pipeline


def test_manual_run_is_new_and_preserves_terminal_bootstrap(
    manual_env, monkeypatch
):
    database, storage, manager, _dataset_root, latest = manual_env
    bootstrap = manager.ensure_bootstrap_revalidation(
        "EURUSD", dataset_provenance={"registry_id": 1}
    )
    database.update_retrain_run(bootstrap["run_id"], {
        "status": "FAILED",
        "error": "ValueError: QUALITY_GATE: VALIDATION_GATE",
        "updated_at": bootstrap["updated_at"],
    })
    before_bootstrap = next(
        row for row in database.get_retrain_runs("EURUSD", limit=100000)
        if row["run_id"] == bootstrap["run_id"]
    )
    before_alias = latest.read_bytes()
    _patch_pipeline_training(monkeypatch)

    result = _pipeline(storage, database).manual_quality_retrain(
        pair="EURUSD", request_id="request-new", manager=manager
    )

    after_bootstrap = next(
        row for row in database.get_retrain_runs("EURUSD", limit=100000)
        if row["run_id"] == bootstrap["run_id"]
    )
    assert result["status"] == "PROMOTED"
    assert result["run_id"] != bootstrap["run_id"]
    assert result["run_id"].startswith("manual_quality_")
    assert result["trigger"] == "manual_quality_retrain"
    assert after_bootstrap == before_bootstrap
    assert latest.read_bytes() != before_alias


def test_manual_request_id_is_idempotent_and_conflicts_on_changed_evidence(
    manual_env,
):
    _database, _storage, manager, dataset_root, _latest = manual_env
    first = manager.ensure_manual_quality_retrain(
        "EURUSD", request_id="same-request"
    )
    repeated = manager.ensure_manual_quality_retrain(
        "EURUSD", request_id="same-request"
    )
    assert repeated["run_id"] == first["run_id"]

    (dataset_root / "EURUSD_H1.csv").write_text(
        "fixture-H1-v2", encoding="utf-8"
    )
    with pytest.raises(PersistenceConflictError, match="different evidence"):
        manager.ensure_manual_quality_retrain(
            "EURUSD", request_id="same-request"
        )


@pytest.mark.parametrize("request_id", ["", "   "])
def test_manual_request_id_rejects_empty_or_whitespace(manual_env, request_id):
    database, _storage, manager, _dataset_root, _latest = manual_env

    with pytest.raises(
        ValueError, match="MANUAL_QUALITY_RETRAIN_REQUIRES_REQUEST_ID"
    ):
        manager.ensure_manual_quality_retrain(
            "EURUSD", request_id=request_id
        )

    assert not [
        row for row in database.get_retrain_runs("EURUSD", limit=100000)
        if row["trigger"] == "manual_quality_retrain"
    ]


def test_manual_request_id_has_bounded_persisted_length(manual_env):
    database, _storage, manager, _dataset_root, _latest = manual_env

    with pytest.raises(
        ValueError, match="MANUAL_QUALITY_RETRAIN_REQUEST_ID_TOO_LONG"
    ):
        manager.ensure_manual_quality_retrain(
            "EURUSD", request_id="x" * 129
        )

    assert not [
        row for row in database.get_retrain_runs("EURUSD", limit=100000)
        if row["trigger"] == "manual_quality_retrain"
    ]


def test_new_request_after_failed_run_creates_new_run_without_reopening_old(
    manual_env,
):
    database, _storage, manager, _dataset_root, _latest = manual_env
    first = manager.ensure_manual_quality_retrain(
        "EURUSD", request_id="failed-request"
    )
    database.update_retrain_run(first["run_id"], {
        "status": "FAILED",
        "error": "ValueError: QUALITY_GATE: WFV_GATE",
        "updated_at": first["updated_at"],
    })
    failed_before = next(
        row for row in database.get_retrain_runs("EURUSD", limit=100000)
        if row["run_id"] == first["run_id"]
    )

    same = manager.ensure_manual_quality_retrain(
        "EURUSD", request_id="failed-request"
    )
    second = manager.ensure_manual_quality_retrain(
        "EURUSD", request_id="new-request"
    )
    failed_after = next(
        row for row in database.get_retrain_runs("EURUSD", limit=100000)
        if row["run_id"] == first["run_id"]
    )

    assert same["run_id"] == first["run_id"]
    assert same["status"] == "FAILED"
    assert second["run_id"] != first["run_id"]
    assert second["status"] == "PENDING"
    assert failed_after == failed_before


def test_two_concurrent_same_requests_return_one_idempotent_run(manual_env):
    database, _storage, manager, _dataset_root, _latest = manual_env

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(
            lambda _index: manager.ensure_manual_quality_retrain(
                "EURUSD", request_id="same-concurrent-request"
            ),
            range(2),
        ))

    assert results[0]["run_id"] == results[1]["run_id"]
    manual_runs = [
        row for row in database.get_retrain_runs("EURUSD", limit=100000)
        if row["trigger"] == "manual_quality_retrain"
    ]
    assert len(manual_runs) == 1


def test_manual_retrain_requires_existing_source_alias(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "manual.sqlite"))
    _set_active_fixture(database, "GBPUSD")
    storage = ModelStorage(tmp_path / "models")
    manager = RetrainManager(
        database=database,
        storage=storage,
        dataset_root=tmp_path / "data" / "forex",
    )

    with pytest.raises(ValueError, match="MANUAL_RETRAIN_REQUIRES_SOURCE_ALIAS"):
        manager.ensure_manual_quality_retrain(
            "GBPUSD", request_id="gbp-request"
        )

    assert database.get_retrain_runs("GBPUSD") == []
    assert storage.list_models() == []
    assert storage.latest_exists("GBPUSD") is False

    initial_provenance = {"path": "GBPUSD_H1.csv", "rows": 2000}
    initial_metadata = _eligible_result(
        "GBPUSD",
        "H1",
        {
            "trigger": "initial_training",
            "dataset_provenance": initial_provenance,
        },
    )["metadata"]
    promoted = manager.promote_initial_model(
        SimpleNamespace(version="gbpusd-initial", sufficient=True),
        pair="GBPUSD",
        timeframe="H1",
        dataset_provenance=initial_provenance,
        metadata=initial_metadata,
    )

    assert promoted["status"] == "PROMOTED"
    assert promoted["trigger"] == "initial_training"
    assert storage.latest_exists("GBPUSD") is True
    assert manager.audit_pair_model("GBPUSD")["eligible"] is True


@pytest.mark.parametrize(
    "failed_gate",
    [
        "QUALITY_GATE",
        "WFV_GATE",
        "CALIBRATION_GATE",
        "VALIDATION_GATE",
        "MODEL_VALID_GATE",
    ],
)
def test_each_candidate_gate_failure_is_durable_and_preserves_alias(
    manual_env, monkeypatch, failed_gate
):
    database, storage, manager, _dataset_root, latest = manual_env
    before = latest.read_bytes()
    _patch_pipeline_training(monkeypatch, failed_gate=failed_gate)

    result = _pipeline(storage, database).manual_quality_retrain(
        pair="EURUSD", request_id=f"request-{failed_gate}", manager=manager
    )

    assert result["status"] == "FAILED"
    assert failed_gate in result["error"]
    assert result["failed_gate"] == failed_gate
    assert latest.read_bytes() == before
    stored = next(
        row for row in database.get_retrain_runs("EURUSD", limit=100000)
        if row["run_id"] == result["run_id"]
    )
    assert stored["status"] == "FAILED"
    assert stored["source_model_sha256"] == manager.storage.checksum(latest)


def test_complete_manual_evidence_promotes_and_audits_eligible(
    manual_env, monkeypatch
):
    database, storage, manager, _dataset_root, latest = manual_env
    before = manager.storage.checksum(latest)
    _patch_pipeline_training(monkeypatch)

    result = _pipeline(storage, database).manual_quality_retrain(
        pair="EURUSD", request_id="all-pass", manager=manager
    )

    assert result["ok"] is True
    assert result["model_deployed"] is True
    assert result["eligibility"]["eligible"] is True
    assert manager.storage.checksum(latest) != before
    provenance = database.get_model_provenance("EURUSD")[0]
    assert provenance["trigger"] == "manual_quality_retrain"
    assert provenance["retrain_run_id"] == result["run_id"]
    repeated = manager.ensure_manual_quality_retrain(
        "EURUSD", request_id="all-pass"
    )
    assert repeated["run_id"] == result["run_id"]


def test_manual_provenance_without_new_trigger_is_never_eligible(
    manual_env, monkeypatch
):
    database, storage, manager, _dataset_root, _latest = manual_env
    _patch_pipeline_training(monkeypatch)
    result = _pipeline(storage, database).manual_quality_retrain(
        pair="EURUSD", request_id="manual-trigger-required", manager=manager
    )
    assert result["status"] == "PROMOTED"

    with database._connection() as connection:
        connection.execute(
            "UPDATE model_provenance SET trigger=NULL WHERE retrain_run_id=?",
            (result["run_id"],),
        )

    audit = manager.audit_pair_model("EURUSD")
    assert audit["eligible"] is False
    assert audit["reason"] == "TRIGGER_PROVENANCE_MISMATCH"


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("metadata", "QUALITY_GATE_EVIDENCE_MISSING"),
        ("wfv", "WFV_EVIDENCE_MISSING"),
        ("provenance", "DATASET_PROVENANCE_MISMATCH"),
    ],
)
def test_execute_retrain_rejects_incomplete_direct_candidates(
    manual_env, case, expected
):
    _database, _storage, manager, _dataset_root, latest = manual_env
    before = latest.read_bytes()
    run = manager.ensure_manual_quality_retrain(
        "EURUSD", request_id=f"direct-{case}"
    )

    def candidate(symbol, timeframe, context):
        if case == "metadata":
            return {"model": SimpleNamespace(sufficient=True)}
        result = _eligible_result(symbol, timeframe, context)
        if case == "wfv":
            result["metadata"].pop("wfv")
        else:
            result["metadata"]["dataset_provenance_sha256"] = "wrong"
        return result

    result = manager.execute_retrain(run["run_id"], candidate)

    assert result["status"] == "FAILED"
    assert expected in result["error"]
    assert latest.read_bytes() == before


def test_alias_change_during_training_fails_source_cas(manual_env):
    _database, storage, manager, _dataset_root, latest = manual_env
    run = manager.ensure_manual_quality_retrain(
        "EURUSD", request_id="alias-race"
    )

    concurrent_bytes = {}

    def candidate(symbol, timeframe, context):
        unrelated = storage.stage_model(
            SimpleNamespace(version="concurrent", sufficient=True),
            name="concurrent",
            version="v2",
        )
        storage.promote_artifact(
            unrelated,
            pair="EURUSD",
            expected_latest_path=latest,
            expected_latest_sha256=run["source_model_sha256"],
            _authority=_PROMOTION_AUTHORITY,
        )
        concurrent_bytes["value"] = latest.read_bytes()
        return _eligible_result(symbol, timeframe, context)

    result = manager.execute_retrain(run["run_id"], candidate)

    assert result["status"] == "FAILED"
    assert "SOURCE_ALIAS_CONFLICT" in result["error"]
    assert latest.read_bytes() == concurrent_bytes["value"]
    assert storage.checksum(latest) != run["source_model_sha256"]


def test_post_replace_failure_never_rolls_back_concurrent_alias(
    manual_env, monkeypatch
):
    database, storage, manager, _dataset_root, latest = manual_env
    run = manager.ensure_manual_quality_retrain(
        "EURUSD", request_id="post-replace-race"
    )
    concurrent_bytes = {}

    def fail_after_concurrent_promotion(_run_id, _provenance):
        installed_by_run = storage.checksum(latest)
        unrelated = storage.stage_model(
            SimpleNamespace(version="newer-concurrent", sufficient=True),
            name="newer_concurrent",
            version="v3",
        )
        storage.promote_artifact(
            unrelated,
            pair="EURUSD",
            expected_latest_path=latest,
            expected_latest_sha256=installed_by_run,
            _authority=_PROMOTION_AUTHORITY,
        )
        concurrent_bytes["value"] = latest.read_bytes()
        raise sqlite3.OperationalError("provenance unavailable")

    monkeypatch.setattr(
        database, "finalize_model_promotion", fail_after_concurrent_promotion
    )
    result = manager.execute_retrain(
        run["run_id"], _eligible_result
    )

    assert result["status"] == "FAILED"
    assert "provenance unavailable" in result["error"]
    assert latest.read_bytes() == concurrent_bytes["value"]
    assert storage.checksum(latest) != run["source_model_sha256"]


def test_dataset_change_during_training_fails_snapshot_cas(manual_env):
    _database, _storage, manager, dataset_root, latest = manual_env
    before = latest.read_bytes()
    run = manager.ensure_manual_quality_retrain(
        "EURUSD", request_id="dataset-race"
    )

    def candidate(symbol, timeframe, context):
        (dataset_root / "EURUSD_H4.csv").write_text(
            "fixture-H4-v2", encoding="utf-8"
        )
        return _eligible_result(symbol, timeframe, context)

    result = manager.execute_retrain(run["run_id"], candidate)

    assert result["status"] == "FAILED"
    assert "DATASET_SNAPSHOT_CONFLICT" in result["error"]
    assert latest.read_bytes() == before


def test_two_concurrent_manual_requests_create_one_active_run(manual_env):
    database, _storage, manager, _dataset_root, _latest = manual_env

    def ensure(request_id):
        try:
            return manager.ensure_manual_quality_retrain(
                "EURUSD", request_id=request_id
            )
        except PersistenceConflictError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(ensure, ("concurrent-a", "concurrent-b")))

    assert sum(isinstance(item, dict) for item in results) == 1
    assert sum(isinstance(item, PersistenceConflictError) for item in results) == 1
    active = [
        row for row in database.get_retrain_runs("EURUSD", limit=100000)
        if row["status"] in {"PENDING", "RUNNING", "VALIDATED"}
    ]
    assert len(active) == 1


def test_final_snapshot_and_alias_locks_have_deterministic_non_training_order(
    manual_env, monkeypatch
):
    from forex.prediction import model_storage as storage_module
    from forex.prediction import retrain_manager as manager_module

    _database, _storage, manager, _dataset_root, _latest = manual_env
    run = manager.ensure_manual_quality_retrain(
        "EURUSD", request_id="lock-order"
    )
    events = []
    held = []

    class RecordingLock:
        def __init__(self, path, timeout=-1):
            self.path = str(Path(path).resolve())
            self.timeout = timeout

        def __enter__(self):
            assert self.path not in held
            events.append(("acquire", self.path, tuple(held)))
            held.append(self.path)
            return self

        def __exit__(self, *_args):
            assert held[-1] == self.path
            held.pop()
            events.append(("release", self.path, tuple(held)))

    original_validate = manager.validate_training_snapshot

    def validate(snapshot):
        events.append(("validate", snapshot["snapshot_sha256"], tuple(held)))
        return original_validate(snapshot)

    monkeypatch.setattr(manager_module, "FileLock", RecordingLock)
    monkeypatch.setattr(storage_module, "FileLock", RecordingLock)
    monkeypatch.setattr(manager, "validate_training_snapshot", validate)

    def train(symbol, timeframe, context):
        events.append(("train", context["run_id"], tuple(held)))
        return _eligible_result(symbol, timeframe, context)

    result = manager.execute_retrain(run["run_id"], train)

    assert result["status"] == "PROMOTED"
    train_event = next(event for event in events if event[0] == "train")
    assert train_event[2] == ()
    acquisitions = [event for event in events if event[0] == "acquire"]
    dataset_acquisitions = [
        event for event in acquisitions if event[1].endswith(".csv.lock")
    ]
    model_acquisition = next(
        event for event in acquisitions if event[1].endswith(".promotion.lock")
    )
    assert [event[1] for event in dataset_acquisitions] == sorted(
        event[1] for event in dataset_acquisitions
    )
    assert len(dataset_acquisitions) == 3
    assert len(model_acquisition[2]) == 3
    assert all(path.endswith(".csv.lock") for path in model_acquisition[2])
    assert held == []


def test_canonical_snapshot_captures_and_revalidates_exact_mtf(tmp_path):
    from forex.data.indicator_delta import INDICATOR_MIN_HISTORY

    database = SQLiteDatabase(str(tmp_path / "snapshot.sqlite"))
    storage = ModelStorage(tmp_path / "models")
    dataset_root = tmp_path / "data" / "forex"
    dataset_root.mkdir(parents=True)
    manager = RetrainManager(
        database=database,
        storage=storage,
        dataset_root=dataset_root,
    )
    for timeframe, frequency in (("H1", "h"), ("H4", "4h"), ("D1", "D")):
        frame = pd.DataFrame({
            "timestamp": pd.date_range("2010-01-01", periods=2000, freq=frequency),
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.05,
            "volume": 100.0,
        })
        for column in INDICATOR_MIN_HISTORY:
            frame[column] = 1.0
        path = (dataset_root / f"EURUSD_{timeframe}.csv").resolve()
        frame.to_csv(path, index=False)
        database.upsert_dataset_registry({
            "symbol": "EURUSD",
            "timeframe": timeframe,
            "candle_count": 2000,
            "rolling_window_size": 2000,
            "last_candle_timestamp": str(frame["timestamp"].iloc[-1]),
            "blob_path": str(path),
            "status": "ready",
        })

    snapshot = manager.capture_training_snapshot("EURUSD")

    assert set(snapshot["datasets"]) == {"H1", "H4", "D1"}
    assert all(item["rolling_ready"] for item in snapshot["datasets"].values())
    assert manager.validate_training_snapshot(snapshot) == snapshot
    (dataset_root / "EURUSD_D1.csv").write_text("changed", encoding="utf-8")
    with pytest.raises(Exception):
        manager.validate_training_snapshot(snapshot)


def test_tune_is_diagnostic_then_train_is_only_initial_publisher(
    tmp_path, monkeypatch
):
    from forex.prediction import integrated_pipeline, roadmap_v_integration

    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=320, freq="h"),
        "close": range(320),
        "pair": ["EURUSD"] * 320,
    })
    X = pd.DataFrame({"feature": range(300)})
    y = pd.Series([0, 1] * 150)

    class Builder:
        def __init__(self, _frame):
            pass

        def build(self, **_kwargs):
            return X, y

        def predict_features(self, **_kwargs):
            return X.tail(1)

    class Tuner:
        @staticmethod
        def recommend_trials(_rows):
            return 1

        def __init__(self, **_kwargs):
            pass

        def tune(self, *_args, **_kwargs):
            return {"max_depth": 3}

    trainer = SimpleNamespace(
        model=SimpleNamespace(version="initial", sufficient=True),
        model_valid=True,
        calibration_sufficient=True,
        validation_sufficient=True,
    )
    wfv = {
        "folds": [
            {"fold": 1, "tp": 21, "fp": 9, "signals": 30,
             "validation_size": 300, "precision": 0.70, "accuracy": 0.70},
            {"fold": 2, "tp": 21, "fp": 9, "signals": 30,
             "validation_size": 300, "precision": 0.70, "accuracy": 0.70},
        ],
        "avg_precision": 0.70,
        "median_precision": 0.70,
        "total_tp": 42,
        "total_fp": 18,
        "total_signals": 60,
        "pooled_precision": 0.70,
        "evidence_sufficient": True,
        "wfv_passed": True,
    }
    monkeypatch.setattr(integrated_pipeline, "_load", lambda *_a, **_k: frame)
    monkeypatch.setattr(integrated_pipeline, "build_features", lambda value: value)
    monkeypatch.setattr(integrated_pipeline, "DatasetBuilder", Builder)
    monkeypatch.setattr(integrated_pipeline, "ForexHyperparameterTuner", Tuner)
    monkeypatch.setattr(
        integrated_pipeline,
        "train_with_wfv",
        lambda *_a, **_k: (trainer, dict(wfv), 0.80, 0.70),
    )
    monkeypatch.setattr(
        roadmap_v_integration,
        "run_quality_gate",
        lambda *_a, **_k: (
            True,
            SimpleNamespace(
                approved=True,
                global_score=90.0,
                critical_count=0,
                warning_count=0,
            ),
        ),
    )
    database = SQLiteDatabase(str(tmp_path / "pipeline.sqlite"))
    _set_active_fixture(database, "EURUSD")
    with database._connection() as connection:
        connection.execute(
            "UPDATE supported_symbols SET status='qualified' "
            "WHERE symbol_code='EURUSD'"
        )
    storage = ModelStorage(tmp_path / "models")
    pipeline = object.__new__(integrated_pipeline.ForexIntegratedPipeline)
    pipeline.storage = storage
    pipeline.closed_loop_database = database
    pipeline._horizon = 12
    pipeline._rr_ratio = 1.0
    pipeline.predictor = SimpleNamespace(
        invalidate_cache=lambda **_kwargs: None,
        signal=lambda *_args, **_kwargs: {},
    )
    filepath = str(tmp_path / "EURUSD_H1.csv")

    tune_result = pipeline.tune(filepath, pair="EURUSD")

    assert tune_result["model_deployed"] is False
    assert storage.latest_exists("EURUSD") is False
    assert database.get_model_provenance("EURUSD") == []

    train_result = pipeline.train(filepath, pair="EURUSD", use_wfv=True, force=False)

    assert train_result["model_deployed"] is True
    assert database.get_symbol("EURUSD")["status"] == "qualified"
    assert storage.latest_exists("EURUSD") is True
    provenance = database.get_model_provenance("EURUSD")
    assert len(provenance) == 1
    assert provenance[0]["status"] == "INITIAL_TRAINING"


@pytest.mark.parametrize(
    "failed_gate",
    ["QUALITY_GATE", "WFV_GATE", "CALIBRATION_GATE", "VALIDATION_GATE"],
)
def test_full_forex_tune_then_rejected_train_never_publishes(
    tmp_path, monkeypatch, failed_gate
):
    from forex.prediction import integrated_pipeline

    _patch_pipeline_training(monkeypatch, failed_gate=failed_gate)

    class Tuner:
        @staticmethod
        def recommend_trials(_rows):
            return 1

        def __init__(self, **_kwargs):
            pass

        def tune(self, *_args, **_kwargs):
            return {"max_depth": 3}

    monkeypatch.setattr(integrated_pipeline, "ForexHyperparameterTuner", Tuner)
    database = SQLiteDatabase(str(tmp_path / "full-forex.sqlite"))
    _set_active_fixture(database, "EURUSD")
    with database._connection() as connection:
        connection.execute(
            "UPDATE supported_symbols SET status='qualified' "
            "WHERE symbol_code='EURUSD'"
        )
    storage = ModelStorage(tmp_path / "models")
    pipeline = object.__new__(integrated_pipeline.ForexIntegratedPipeline)
    pipeline.storage = storage
    pipeline.closed_loop_database = database
    pipeline._horizon = 12
    pipeline._rr_ratio = 1.0
    pipeline.predictor = SimpleNamespace(
        invalidate_cache=lambda **_kwargs: None,
        signal=lambda *_args, **_kwargs: {},
    )
    filepath = str(tmp_path / "EURUSD_H1.csv")

    tune_result = pipeline.tune(filepath, pair="EURUSD")
    assert tune_result["model_deployed"] is False
    assert storage.latest_exists("EURUSD") is False

    try:
        train_result = pipeline.train(
            filepath, pair="EURUSD", use_wfv=True, force=False
        )
    except ValueError as exc:
        train_result = {"error": str(exc)}

    if failed_gate == "QUALITY_GATE":
        assert "error" in train_result
        assert "Quality gate" in train_result["error"]
    elif failed_gate == "WFV_GATE":
        assert train_result["model_deployed"] is False
        assert train_result["wfv"]["wfv_passed"] is False
        assert train_result["wfv"]["evidence_sufficient"] is False
        from forex.prediction.xgb_trainer import wfv_quality_passed
        assert wfv_quality_passed(train_result["wfv"]) is False
    else:
        assert failed_gate in json.dumps(train_result)
    assert storage.latest_exists("EURUSD") is False
    assert database.get_model_provenance("EURUSD") == []
    assert database.get_retrain_runs("EURUSD") == []


@pytest.mark.parametrize(
    ("mode", "exit_code"),
    [
        ("failed", 2),
        ("precondition", 2),
        ("conflict", 2),
        ("internal", 1),
    ],
)
def test_manual_quality_retrain_cli_json_exit_codes(
    monkeypatch, capsys, mode, exit_code
):
    from scheduler import autonomous_scheduler

    monkeypatch.setattr(autonomous_scheduler, "get_database", lambda: object())
    if mode == "failed":
        outcome = {
            "ok": False,
            "run_id": "manual_quality_1",
            "request_id": "request-cli",
            "symbol": "EURUSD",
            "trigger": "manual_quality_retrain",
            "status": "FAILED",
            "model_deployed": False,
            "eligibility": {"eligible": False},
            "failed_gate": "WFV_GATE",
            "error": "QUALITY_GATE: WFV_GATE",
        }
        monkeypatch.setattr(
            autonomous_scheduler,
            "run_manual_quality_retrain",
            lambda *_args: outcome,
        )
    elif mode == "precondition":
        monkeypatch.setattr(
            autonomous_scheduler,
            "run_manual_quality_retrain",
            lambda *_args: (_ for _ in ()).throw(
                ValueError("MANUAL_RETRAIN_REQUIRES_SOURCE_ALIAS")
            ),
        )
    elif mode == "conflict":
        monkeypatch.setattr(
            autonomous_scheduler,
            "run_manual_quality_retrain",
            lambda *_args: (_ for _ in ()).throw(
                PersistenceConflictError("request evidence conflict")
            ),
        )
    else:
        monkeypatch.setattr(
            autonomous_scheduler,
            "run_manual_quality_retrain",
            lambda *_args: (_ for _ in ()).throw(RuntimeError("unexpected")),
        )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "autonomous_scheduler.py",
            "--manual-quality-retrain",
            "EURUSD",
            "--request-id",
            "request-cli",
        ],
    )

    with pytest.raises(SystemExit) as exited:
        autonomous_scheduler.main()

    assert exited.value.code == exit_code
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["trigger"] == "manual_quality_retrain"


def test_manual_quality_retrain_cli_success_returns_zero(monkeypatch, capsys):
    from scheduler import autonomous_scheduler

    monkeypatch.setattr(autonomous_scheduler, "get_database", lambda: object())
    def run_with_progress(*_args):
        print("trainer progress")
        return {
            "ok": True,
            "run_id": "manual_quality_1",
            "request_id": "request-cli",
            "symbol": "EURUSD",
            "trigger": "manual_quality_retrain",
            "status": "PROMOTED",
            "model_deployed": True,
            "source_sha256": "a" * 64,
            "eligibility": {"eligible": True},
            "failed_gate": None,
            "error": "",
        }

    monkeypatch.setattr(
        autonomous_scheduler,
        "run_manual_quality_retrain",
        run_with_progress,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "autonomous_scheduler.py",
            "--manual-quality-retrain",
            "EURUSD",
            "--request-id",
            "request-cli",
        ],
    )

    autonomous_scheduler.main()

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["status"] == "PROMOTED"
    assert "trainer progress" not in captured.out
    assert "trainer progress" in captured.err


def test_existing_training_apis_cannot_select_a_force_promotion_path():
    project_root = Path(__file__).resolve().parents[1]
    server_source = (project_root / "workspace" / "server.py").read_text(
        encoding="utf-8"
    )
    server_tree = ast.parse(server_source)
    functions = {
        node.name: ast.get_source_segment(server_source, node)
        for node in server_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "_run_training_job" in functions["start_training"]
    assert "full forex" in functions["_run_training_job"]
    assert "full forex" in functions["retrain_force"]
    assert "force=True" not in functions["_run_training_job"]
    assert "force=True" not in functions["retrain_force"]

    pipeline_source = (
        project_root / "forex" / "prediction" / "integrated_pipeline.py"
    ).read_text(encoding="utf-8")
    pipeline_tree = ast.parse(pipeline_source)
    pipeline_class = next(
        node for node in pipeline_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ForexIntegratedPipeline"
    )
    methods = {
        node.name: ast.get_source_segment(pipeline_source, node)
        for node in pipeline_class.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "_promote_initial_training" not in methods["tune"]
    assert "_promote_initial_training" in methods["train"]

    main_source = (project_root / "main.py").read_text(encoding="utf-8")
    main_tree = ast.parse(main_source)
    full_forex = next(
        node for node in main_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_forex_full"
    )
    full_source = ast.get_source_segment(main_source, full_forex)
    assert full_source.index("pipeline.tune(") < full_source.index("pipeline.train(")

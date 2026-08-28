from __future__ import annotations

import json
import hashlib
import inspect
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from forex.data import symbol_lifecycle
from forex.data.data_router import DataRouter
from forex.data.rolling_dataset import RollingDataset
from forex.data.indicator_delta import recalculate_tail_indicators
from forex.data.symbol_catalog import (
    CATALOG_VERSION,
    SYMBOL_CATALOG,
    UnsupportedSymbolError,
    get_symbol_spec,
    operational_capabilities,
    route_for_provider,
)
from forex.scheduler.auto_updater import AutoUpdater
from forex.prediction.model_storage import ModelStorage
from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
from forex.prediction.outcome_tracker import OutcomeTracker
from forex.prediction.retrain_manager import RetrainManager
from forex.portfolio.opportunity_score import OpportunityRanker, SignalInput
from forex.portfolio.portfolio_ranker import PortfolioRanker
from infra.db.database import (
    PersistenceConflictError,
    SQLiteDatabase,
    SymbolLifecycleError,
)
from runtime_paths import forex_dataset_path, symbol_qualification_path
from scheduler.autonomous_scheduler import detect_new_symbols, run_cycle, run_prediction
from deployment.production_readiness import run_production_readiness
from scripts.manage_symbol_lifecycle import parse_args
from scripts.validate_symbol_universe import sha256_file


pytestmark = pytest.mark.unit
NOW = pd.Timestamp("2026-08-21 12:00:00", tz="UTC")


def _provider_frame(
    symbol: str,
    timeframe: str,
    count: int = 2001,
    *,
    reference_now: pd.Timestamp = NOW,
) -> pd.DataFrame:
    duration_hours = {"H1": 1, "H4": 4, "D1": 24}[timeframe]
    starts = pd.date_range(
        reference_now.tz_localize(None)
        - pd.Timedelta(hours=duration_hours * count),
        periods=count,
        freq=f"{duration_hours}h",
    )
    epoch_hours = (
        starts.to_numpy(dtype="datetime64[ns]").astype(np.int64)
        / (60 * 60 * 1_000_000_000)
    )
    sampled = np.stack([
        1.1 + (epoch_hours + offset) * 1e-7
        for offset in range(duration_hours + 1)
    ])
    opened = sampled[0]
    closed = sampled[-1]
    return pd.DataFrame({
        "timestamp": starts,
        "open": opened,
        "high": sampled.max(axis=0) + 2e-6,
        "low": sampled.min(axis=0) - 2e-6,
        "close": closed,
        "volume": np.full(count, 1000.0 * duration_hours),
        "pair": symbol,
    })


class FakeRouter:
    calls: list[tuple[str, str, int]] = []

    def __init__(self, symbol: str, timeframe: str):
        self.symbol = symbol
        self.timeframe = timeframe
        self.source_used = "Yahoo"
        self.route_used = route_for_provider(symbol, "Yahoo")
        self.attempt_errors = ("MT5 unavailable",)

    def fetch(self, bars: int, raise_on_failure: bool):
        assert raise_on_failure is True
        self.calls.append((self.symbol, self.timeframe, bars))
        return _provider_frame(self.symbol, self.timeframe, bars)


def _candidate_database(tmp_path: Path, symbol: str = "NZDUSD") -> SQLiteDatabase:
    database = SQLiteDatabase(str(tmp_path / "astra.db"))
    spec = get_symbol_spec(symbol)
    database.register_candidate(
        spec.symbol_code, spec.display_name, spec.asset_class, spec.pip_value
    )
    return database


def _pass_evidence(
    tmp_path: Path,
    symbol: str = "NZDUSD",
    *,
    timestamp: str | None = None,
) -> dict:
    timeframes = {}
    for timeframe in ("H1", "H4", "D1"):
        csv_path = tmp_path / f"{symbol}_{timeframe}.csv"
        csv_path.write_bytes(f"{symbol},{timeframe}\n".encode("utf-8"))
        timeframes[timeframe] = {
            "timeframe": timeframe,
            "result": "PASS",
            "row_count": 2000,
            "closed_count": 2000,
            "provider": "Yahoo",
            "external_ticker": f"{symbol}=X",
            "provider_class": "FX_REFERENCE",
            "source_fetched_at": NOW.isoformat(),
            "csv_path": str(csv_path.resolve()),
            "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        }
    payload = {
        "result": "PASS",
        "symbol": symbol,
        "qualification_timestamp": timestamp or NOW.isoformat(),
        "catalog_version": CATALOG_VERSION,
        "timeframes": timeframes,
        "cross_timeframe": {"status": "PASS", "blocking": False},
    }
    evidence_path = tmp_path / f"{symbol}_evidence.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    return {
        **payload,
        "evidence_path": str(evidence_path.resolve()),
        "evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
    }


def _set_status(database: SQLiteDatabase, status: str) -> None:
    with sqlite3.connect(database.db_path) as connection:
        connection.execute(
            "UPDATE supported_symbols SET status=? WHERE symbol_code='NZDUSD'",
            (status,),
        )


def _set_symbol_status(
    database: SQLiteDatabase, symbol: str, status: str
) -> None:
    with sqlite3.connect(database.db_path) as connection:
        connection.execute(
            "UPDATE supported_symbols SET status=? WHERE symbol_code=?",
            (status, symbol),
        )


def _populate_canonical(
    database: SQLiteDatabase,
    project_root: Path,
    symbol: str = "NZDUSD",
    *,
    now: pd.Timestamp = NOW,
) -> None:
    for timeframe in ("H1", "H4", "D1"):
        path = forex_dataset_path(symbol, timeframe, project_root=project_root)
        stored = RollingDataset(
            symbol, timeframe, max_rows=2000, csv_path=path
        ).apply(
            _provider_frame(symbol, timeframe),
            include_existing=False,
            now=now,
        )
        route = route_for_provider(symbol, "Yahoo")
        database.upsert_dataset_registry({
            "symbol": symbol,
            "timeframe": timeframe,
            "candle_count": 2000,
            "rolling_window_size": 2000,
            "last_candle_timestamp": str(stored["last_timestamp"]),
            "blob_path": str(path.resolve()),
            "status": "ready",
            "provider_used": route.provider,
            "external_ticker": route.external_ticker,
            "provider_class": route.provider_class,
            "source_fetched_at": now.isoformat(),
            "source_sha256": sha256_file(path),
        })


ELIGIBLE_MODEL_MANAGER = SimpleNamespace(
    audit_pair_model=lambda _symbol: {
        "eligible": True,
        "reason": "PRODUCTION_ELIGIBLE",
    }
)


def _eligibility_metadata(symbol: str, provenance: dict) -> dict:
    return {
        "symbol": symbol,
        "timeframe": "H1",
        "promotion_type": "initial_training",
        "dataset_provenance_sha256": (
            RetrainManager.dataset_provenance_sha256(provenance)
        ),
        "quality_gate": {"passed": True, "approved": True, "score": 90.0},
        "precision": 0.70,
        "eligibility": {
            "quality_gate_passed": True,
            "calibration_passed": True,
            "validation_passed": True,
            "validation_precision": 0.70,
            "wfv_passed": True,
            "model_valid": True,
        },
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
    }


def test_migration_preserves_existing_active_symbols_and_history(tmp_path):
    path = tmp_path / "legacy.db"
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
            CREATE TABLE dataset_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                candle_count INTEGER DEFAULT 0,
                rolling_window_size INTEGER DEFAULT 2000,
                last_candle_timestamp TEXT,
                blob_path TEXT,
                status TEXT DEFAULT 'pending',
                last_error TEXT,
                last_updated TEXT,
                UNIQUE(symbol, timeframe)
            );
        """)
        for code in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD"):
            spec = get_symbol_spec(code)
            connection.execute(
                "INSERT INTO supported_symbols "
                "(symbol_code,display_name,pip_value,status,added_at) "
                "VALUES (?,?,?,?,?)",
                (code, spec.display_name, spec.pip_value, "active", "2025-01-01"),
            )
        connection.execute(
            "INSERT INTO dataset_registry "
            "(symbol,timeframe,candle_count,status) VALUES ('EURUSD','H1',1777,'ready')"
        )

    database = SQLiteDatabase(str(path))

    assert [row["symbol_code"] for row in database.get_supported_symbols()] == [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD"
    ]
    assert all(row["asset_class"] == "FOREX" for row in database.get_supported_symbols())
    assert all(
        row["activation_origin"] == "legacy"
        for row in database.get_supported_symbols()
    )
    assert database.get_dataset_registry("EURUSD", "H1")[0]["candle_count"] == 1777
    with sqlite3.connect(path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(dataset_registry)")
        }
    assert {
        "provider_used", "external_ticker", "provider_class",
        "source_fetched_at", "source_sha256",
    } <= columns
    reopened = SQLiteDatabase(str(path))
    assert [
        row["symbol_code"] for row in reopened.get_supported_symbols()
    ] == ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    assert len(reopened.get_dataset_registry("EURUSD", "H1")) == 1

    activation = symbol_lifecycle.activate_qualified_symbol(
        reopened,
        "EURUSD",
        project_root=tmp_path,
    )
    assert activation["activation_result"] == "LEGACY_ACTIVE_GRANDFATHERED"
    assert activation["activation_origin"] == "legacy"
    readiness = run_production_readiness(
        base_dir=tmp_path,
        db=reopened,
        required_timeframes=(),
        require_models=True,
    )
    model_check = next(
        check for check in readiness.checks
        if check.check == "Modelo EURUSD/H1"
    )
    assert model_check.status == "fail"
    assert model_check.blocking is True
    assert readiness.global_status == "NOT READY"


def test_full_f605_migration_is_lossless_and_idempotent(tmp_path):
    path = tmp_path / "f605.db"
    tables = (
        "supported_symbols", "dataset_registry", "predictions", "outcomes",
        "retrain_runs", "model_provenance", "model_quality", "scheduler_runs",
        "config",
    )
    legacy_indexes = (
        "idx_predictions_uid",
        "idx_outcomes_key",
        "idx_predictions_pending",
        "idx_outcomes_finalized",
        "idx_manual_retrain_request",
        "idx_manual_retrain_active",
    )

    def snapshot(connection, baseline=None):
        result = {}
        for table in tables:
            columns = (
                baseline[table]["columns"]
                if baseline is not None
                else [
                    row[1]
                    for row in connection.execute(f"PRAGMA table_info({table})")
                ]
            )
            selected = ",".join(f'"{column}"' for column in columns)
            rows = connection.execute(
                f"SELECT {selected} FROM {table} ORDER BY 1"
            ).fetchall()
            payload = [dict(zip(columns, row)) for row in rows]
            result[table] = {
                "columns": columns,
                "count": len(rows),
                "identities": [row[0] for row in rows],
                "digest": hashlib.sha256(
                    json.dumps(payload, sort_keys=True).encode("utf-8")
                ).hexdigest(),
            }
        result["__sqlite_sequence__"] = connection.execute(
            "SELECT name,seq FROM sqlite_sequence ORDER BY name"
        ).fetchall()
        result["__legacy_indexes__"] = connection.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='index' "
            f"AND name IN ({','.join('?' for _ in legacy_indexes)}) ORDER BY name",
            legacy_indexes,
        ).fetchall()
        result["__object_names__"] = connection.execute(
            "SELECT type,name FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        ).fetchall()
        return result

    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE supported_symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT, symbol_code TEXT UNIQUE NOT NULL,
                display_name TEXT, pip_value REAL DEFAULT 0.0001,
                status TEXT DEFAULT 'active', added_at TEXT);
            CREATE TABLE dataset_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL, candle_count INTEGER DEFAULT 0,
                rolling_window_size INTEGER DEFAULT 2000,
                last_candle_timestamp TEXT, blob_path TEXT,
                status TEXT DEFAULT 'pending', last_error TEXT, last_updated TEXT,
                UNIQUE(symbol, timeframe));
            CREATE TABLE predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, prediction_id TEXT,
                symbol TEXT, timeframe TEXT, direction TEXT, action TEXT,
                raw_action TEXT, confidence REAL, entry_price REAL,
                stop_loss REAL, take_profit REAL, features_snapshot TEXT,
                pipeline_version TEXT, predicted_at TEXT, candle_timestamp TEXT,
                horizon_candles INTEGER, model_identity TEXT,
                dataset_provenance TEXT, status TEXT DEFAULT 'PENDING',
                resolved INTEGER DEFAULT 0);
            CREATE TABLE outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, prediction_id TEXT,
                outcome_key TEXT, symbol TEXT, timeframe TEXT,
                actual_direction TEXT, pnl_pips REAL, hit_tp INTEGER,
                hit_sl INTEGER, resolved_at TEXT, prediction_timestamp TEXT,
                evaluation_timestamp TEXT, action TEXT, entry_price REAL,
                observed_price REAL, observed_return REAL, result TEXT,
                status TEXT, model_identity TEXT, dataset_provenance TEXT);
            CREATE TABLE retrain_runs (
                run_id TEXT PRIMARY KEY, evidence_key TEXT UNIQUE NOT NULL,
                request_id TEXT, symbol TEXT NOT NULL, timeframe TEXT NOT NULL,
                trigger TEXT NOT NULL, status TEXT NOT NULL,
                source_model_path TEXT, source_model_sha256 TEXT,
                dataset_provenance TEXT, outcome_ids TEXT NOT NULL,
                last_outcome_id INTEGER, artifact_path TEXT,
                artifact_sha256 TEXT, latest_path TEXT, error TEXT,
                owner_token TEXT, heartbeat_at TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, validated_at TEXT, promoted_at TEXT);
            CREATE TABLE model_provenance (
                model_id TEXT PRIMARY KEY, retrain_run_id TEXT UNIQUE NOT NULL,
                trigger TEXT, symbol TEXT NOT NULL, timeframe TEXT NOT NULL,
                artifact_path TEXT NOT NULL, artifact_sha256 TEXT NOT NULL,
                source_model_path TEXT, source_model_sha256 TEXT,
                dataset_provenance TEXT NOT NULL, outcome_ids TEXT NOT NULL,
                trained_at TEXT NOT NULL, validated_at TEXT NOT NULL,
                promoted_at TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE model_quality (
                id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, timeframe TEXT,
                accuracy REAL, auc REAL, precision REAL, recall REAL,
                status TEXT DEFAULT 'active', retrain_count INTEGER DEFAULT 0,
                last_evaluated TEXT, UNIQUE(symbol, timeframe));
            CREATE TABLE scheduler_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timeframe TEXT,
                started_at TEXT, finished_at TEXT, status TEXT,
                symbols_processed INTEGER, predictions_generated INTEGER,
                errors_count INTEGER, log_blob_path TEXT,
                interruption_reason TEXT, recovered_at TEXT);
            CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT);
            CREATE UNIQUE INDEX idx_predictions_uid
                ON predictions(prediction_id) WHERE prediction_id IS NOT NULL;
            CREATE UNIQUE INDEX idx_outcomes_key
                ON outcomes(outcome_key) WHERE outcome_key IS NOT NULL;
            CREATE INDEX idx_predictions_pending
                ON predictions(status, symbol, timeframe, candle_timestamp);
            CREATE INDEX idx_outcomes_finalized
                ON outcomes(status, symbol, timeframe, id);
            CREATE UNIQUE INDEX idx_manual_retrain_request
                ON retrain_runs(symbol, timeframe, trigger, request_id)
                WHERE trigger='manual_quality_retrain' AND request_id IS NOT NULL;
            CREATE UNIQUE INDEX idx_manual_retrain_active
                ON retrain_runs(symbol, timeframe)
                WHERE trigger='manual_quality_retrain'
                AND status IN ('PENDING','RUNNING','VALIDATED');
        """)
        for code in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD"):
            spec = get_symbol_spec(code)
            connection.execute(
                "INSERT INTO supported_symbols "
                "(symbol_code,display_name,pip_value,status,added_at) "
                "VALUES (?,?,?,?,?)",
                (code, spec.display_name, spec.pip_value, "active", "2025-01-01"),
            )
            connection.execute(
                "INSERT INTO dataset_registry "
                "(symbol,timeframe,candle_count,rolling_window_size,"
                "last_candle_timestamp,blob_path,status,last_updated) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (code, "H1", 2000, 2000, "2025-01-02", f"/{code}.csv", "ready", "2025-01-02"),
            )
        connection.execute(
            "INSERT INTO predictions "
            "(prediction_id,symbol,timeframe,direction,action,confidence,"
            "entry_price,predicted_at,status,resolved) "
            "VALUES ('p1','EURUSD','H1','UP','BUY',0.7,1.1,'2025-01-02','FINALIZED',1)"
        )
        connection.execute(
            "INSERT INTO outcomes "
            "(prediction_id,outcome_key,symbol,timeframe,actual_direction,"
            "pnl_pips,status) VALUES ('p1','o1','EURUSD','H1','UP',10,'FINALIZED')"
        )
        connection.execute(
            "INSERT INTO retrain_runs "
            "(run_id,evidence_key,request_id,symbol,timeframe,trigger,status,"
            "dataset_provenance,outcome_ids,owner_token,heartbeat_at,created_at,updated_at) "
            "VALUES ('r1','e1','request-1','EURUSD','H1','outcome_evidence',"
            "'PROMOTED','{}','[1]','owner-1','2025-01-03','2025-01-03','2025-01-03')"
        )
        connection.execute(
            "INSERT INTO model_provenance "
            "(model_id,retrain_run_id,trigger,symbol,timeframe,artifact_path,"
            "artifact_sha256,dataset_provenance,outcome_ids,trained_at,validated_at,"
            "promoted_at,status) VALUES "
            "('m1','r1','outcome_evidence','EURUSD','H1','/m.pkl','abc','{}','[1]',"
            "'2025-01-03','2025-01-03','2025-01-03','PROMOTED')"
        )
        connection.execute(
            "INSERT INTO model_quality "
            "(symbol,timeframe,accuracy,auc,precision,recall,status,retrain_count,last_evaluated) "
            "VALUES ('EURUSD','H1',0.61,0.62,0.63,0.64,'active',3,'2025-01-03')"
        )
        connection.execute(
            "INSERT INTO scheduler_runs "
            "(timeframe,started_at,finished_at,status,symbols_processed,"
            "predictions_generated,errors_count,interruption_reason,recovered_at) "
            "VALUES ('H1','2025-01-04','2025-01-04','completed',4,1,0,"
            "'historical interruption','2025-01-04')"
        )
        connection.execute("INSERT INTO config VALUES ('scheduler_enabled','true')")
        before = snapshot(connection)

    SQLiteDatabase(str(path))
    with sqlite3.connect(path) as connection:
        after_first = snapshot(connection, before)
        registry = connection.execute(
            "SELECT provider_used, external_ticker, provider_class, "
            "source_fetched_at, source_sha256, legacy_provenance_pending "
            "FROM dataset_registry ORDER BY id"
        ).fetchall()
    SQLiteDatabase(str(path))
    with sqlite3.connect(path) as connection:
        after_second = snapshot(connection, before)

    for table in tables:
        assert after_first[table]["count"] == before[table]["count"]
        assert after_first[table]["identities"] == before[table]["identities"]
        assert after_first[table]["digest"] == before[table]["digest"]
        assert after_second[table]["count"] == before[table]["count"]
        assert after_second[table]["identities"] == before[table]["identities"]
        assert after_second[table]["digest"] == before[table]["digest"]
    assert after_first["__sqlite_sequence__"] == before["__sqlite_sequence__"]
    assert after_second["__sqlite_sequence__"] == before["__sqlite_sequence__"]
    assert after_first["__legacy_indexes__"] == before["__legacy_indexes__"]
    assert after_second["__legacy_indexes__"] == before["__legacy_indexes__"]
    expected_lifecycle_objects = {
        ("trigger", "supported_symbols_status_insert"),
        ("trigger", "supported_symbols_status_update"),
        ("trigger", "supported_symbols_origin_insert"),
        ("trigger", "supported_symbols_origin_update"),
    }
    assert (
        set(after_first["__object_names__"])
        - set(before["__object_names__"])
    ) == expected_lifecycle_objects
    assert after_second["__object_names__"] == after_first["__object_names__"]
    assert all(row[:5] == (None, None, None, None, None) for row in registry)
    assert all(row[5] == 1 for row in registry)


@pytest.mark.parametrize(
    ("status", "data_visible", "production_visible"),
    [
        ("candidate", False, False),
        ("qualified", True, False),
        ("active", True, True),
        ("disabled", False, False),
    ],
)
def test_data_and_production_symbol_visibility(
    tmp_path, status, data_visible, production_visible
):
    database = _candidate_database(tmp_path)
    _set_status(database, status)

    data_codes = {row["symbol_code"] for row in database.get_data_symbols()}
    active_codes = {row["symbol_code"] for row in database.get_active_symbols()}
    assert ("NZDUSD" in data_codes) is data_visible
    assert ("NZDUSD" in active_codes) is production_visible
    with patch(
        "scheduler.autonomous_scheduler.run_rolling_update",
        return_value={"action": "updated"},
    ) as update:
        generated = detect_new_symbols(database)
    assert len(generated) == (3 if data_visible else 0)
    assert update.call_count == (3 if data_visible else 0)


def test_legacy_updater_uses_data_symbols(
    monkeypatch, tmp_path
):
    from forex.scheduler import auto_updater

    database = SQLiteDatabase(str(tmp_path / "astra.db"))
    for symbol in ("EURUSD", "NZDUSD", "USDCHF"):
        symbol_lifecycle.register_candidate(database, symbol)
    with sqlite3.connect(database.db_path) as connection:
        connection.execute(
            "UPDATE supported_symbols SET status='active' WHERE symbol_code='EURUSD'"
        )
        connection.execute(
            "UPDATE supported_symbols SET status='qualified' WHERE symbol_code='NZDUSD'"
        )
        connection.execute(
            "UPDATE supported_symbols SET status='disabled' WHERE symbol_code='USDCHF'"
        )
    index_path = tmp_path / "astra_csv_index.json"
    index_path.write_text(
        json.dumps({
            symbol: {"pair": symbol, "tf": "H1"}
            for symbol in ("EURUSD", "NZDUSD", "USDCHF")
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(auto_updater, "_INDEX_PATH", index_path)

    updater = AutoUpdater(database=database)

    assert updater._load_active_pairs() == [
        {"pair": "EURUSD", "tf": "H1"},
        {"pair": "NZDUSD", "tf": "H1"},
    ]


@pytest.mark.parametrize("status", ["candidate", "qualified", "disabled"])
def test_registered_non_active_symbol_cannot_enter_retraining(tmp_path, status):
    database = _candidate_database(tmp_path)
    with sqlite3.connect(database.db_path) as connection:
        connection.execute(
            "UPDATE supported_symbols SET status=? WHERE symbol_code='NZDUSD'",
            (status,),
        )
    run = database.create_retrain_run({
        "run_id": f"blocked_{status}",
        "evidence_key": f"evidence_{status}",
        "symbol": "NZDUSD",
        "timeframe": "H1",
        "trigger": "outcome_evidence",
        "status": "PENDING",
        "dataset_provenance": {"complete": True},
        "outcome_ids": [],
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
    })
    manager = RetrainManager(
        database=database,
        storage=ModelStorage(tmp_path / "models"),
        dataset_root=tmp_path / "data" / "forex",
    )

    with pytest.raises(ValueError, match="SYMBOL_LIFECYCLE_BLOCKED"):
        manager.execute_retrain(run["run_id"], lambda *_args: pytest.fail("trained"))


@pytest.mark.parametrize("status", ["candidate", "qualified", "disabled"])
def test_registered_non_active_symbol_cannot_enter_prediction(tmp_path, status):
    database = _candidate_database(tmp_path)
    with sqlite3.connect(database.db_path) as connection:
        connection.execute(
            "UPDATE supported_symbols SET status=? WHERE symbol_code='NZDUSD'",
            (status,),
        )

    result = run_prediction(database, "NZDUSD", "H1")

    assert result == {
        "action": "skip",
        "reason": "symbol_not_active",
        "symbol": "NZDUSD",
        "status": status,
    }


def _guarded_pipeline(database: SQLiteDatabase) -> ForexIntegratedPipeline:
    pipeline = object.__new__(ForexIntegratedPipeline)
    pipeline.closed_loop_database = database
    pipeline.storage = SimpleNamespace(
        load_model_with_features=lambda **_kwargs: pytest.fail("model loaded")
    )
    pipeline.predictor = SimpleNamespace(
        signal=lambda *_args, **_kwargs: pytest.fail("prediction executed")
    )
    return pipeline


def test_qualified_direct_pipeline_predict_fails_before_model_or_decision(tmp_path):
    database = _candidate_database(tmp_path)
    _set_status(database, "qualified")
    pipeline = _guarded_pipeline(database)
    frame = pd.DataFrame({"pair": ["NZDUSD"], "close": [1.0]})

    with patch(
        "forex.prediction.integrated_pipeline._load", return_value=frame
    ), patch(
        "forex.prediction.integrated_pipeline.build_features",
        side_effect=AssertionError("features/decision path reached"),
    ), pytest.raises(SymbolLifecycleError, match="SYMBOL_NOT_ACTIVE.*qualified"):
        pipeline.predict("ignored.csv", pair="NZDUSD")

    assert database.get_predictions("NZDUSD") == []


def test_unregistered_direct_pipeline_predict_fails_closed(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "unregistered.db"))
    pipeline = _guarded_pipeline(database)
    frame = pd.DataFrame({"pair": ["EURUSD"], "close": [1.0]})

    with patch(
        "forex.prediction.integrated_pipeline._load", return_value=frame
    ), pytest.raises(SymbolLifecycleError, match="SYMBOL_NOT_ACTIVE.*unregistered"):
        pipeline.predict("ignored.csv", pair="EURUSD")


def test_data_only_symbol_without_ml_config_fails_predict_and_outcome(tmp_path):
    database = _candidate_database(tmp_path, "AUDCHF")
    _set_symbol_status(database, "AUDCHF", "qualified")
    pipeline = _guarded_pipeline(database)
    frame = pd.DataFrame({"pair": ["AUDCHF"], "close": [1.0]})

    with patch(
        "forex.prediction.integrated_pipeline._load", return_value=frame
    ), pytest.raises(ValueError, match="ML_CONFIG_NOT_DEFINED: AUDCHF"):
        pipeline.predict("ignored.csv", pair="AUDCHF")

    tracker = OutcomeTracker(database=database)
    with pytest.raises(ValueError, match="ML_CONFIG_NOT_DEFINED: AUDCHF"):
        tracker.record_prediction(
            "AUDCHF",
            "H1",
            "BUY",
            1.0,
            candle_timestamp=NOW,
            horizon_candles=10,
        )
    assert database.get_predictions("AUDCHF") == []


def test_qualified_direct_outcome_is_rejected_without_persistence(tmp_path):
    database = _candidate_database(tmp_path)
    _set_status(database, "qualified")
    tracker = OutcomeTracker(database=database)

    with pytest.raises(SymbolLifecycleError, match="SYMBOL_NOT_ACTIVE.*qualified"):
        tracker.record_prediction(
            "NZDUSD",
            "H1",
            "BUY",
            1.0,
            candle_timestamp=NOW,
            horizon_candles=10,
        )

    assert database.get_predictions("NZDUSD") == []


def test_opportunity_omits_qualified_without_contaminating_active(tmp_path):
    database = _candidate_database(tmp_path)
    _set_status(database, "qualified")
    eurusd = get_symbol_spec("EURUSD")
    database.register_candidate(
        eurusd.symbol_code,
        eurusd.display_name,
        eurusd.asset_class,
        eurusd.pip_value,
    )
    _set_symbol_status(database, "EURUSD", "active")
    signals = [
        SignalInput("EURUSD", "BUY", reliability_score=90, win_rate_pct=80),
        SignalInput("NZDUSD", "BUY", reliability_score=90, win_rate_pct=80),
    ]

    result = OpportunityRanker(database=database).rank(signals)

    assert result["total_active"] == 1
    assert result["total_rejected"] == 1
    assert result["rejected"][0]["pair"] == "NZDUSD"
    assert [item.pair for item in result["top_buy"]] == ["EURUSD"]


def test_portfolio_rejects_qualified_without_persisting_ranking(tmp_path):
    database = _candidate_database(tmp_path)
    _set_status(database, "qualified")
    portfolio_path = tmp_path / "portfolio.db"
    ranker = PortfolioRanker(
        db_path=str(portfolio_path),
        database=database,
    )

    result = ranker.rank([
        {
            "pair": "NZDUSD",
            "signal": "BUY",
            "reliability_score": 90.0,
        }
    ])

    assert result.total_active == 0
    assert result.total_rejected == 1
    assert result.ranking == []
    assert ranker.get_history() == []

    eurusd = get_symbol_spec("EURUSD")
    database.register_candidate(
        eurusd.symbol_code,
        eurusd.display_name,
        eurusd.asset_class,
        eurusd.pip_value,
    )
    _set_symbol_status(database, "EURUSD", "active")
    mixed = ranker.rank([
        {"pair": "EURUSD", "signal": "BUY", "reliability_score": 90.0},
        {"pair": "NZDUSD", "signal": "BUY", "reliability_score": 90.0},
    ])

    assert mixed.total_active == 1
    assert mixed.total_rejected == 1
    assert [item.pair for item in mixed.ranking] == ["EURUSD"]
    persisted = ranker.get_history()
    assert len(persisted) == 1
    assert [item["pair"] for item in persisted[0]["ranking"]["ranking"]] == [
        "EURUSD"
    ]


def test_candidate_cannot_activate_and_failed_evidence_cannot_qualify(tmp_path):
    import infra.db.database as database_module

    database = _candidate_database(tmp_path)

    assert not hasattr(database, "activate_symbol")
    assert not hasattr(database_module, "_authorize_symbol_activation")
    assert symbol_lifecycle.is_activation_authorization(SimpleNamespace(
        symbol="NZDUSD",
        evidence_sha256="a" * 64,
        model_reason="PRODUCTION_ELIGIBLE",
        freshness_sha256="b" * 64,
    )) is False
    with pytest.raises(PersistenceConflictError, match="opaque lifecycle authorization"):
        database._persist_authorized_activation("not-an-authorization")
    with pytest.raises(PersistenceConflictError, match="must be qualified"):
        symbol_lifecycle.activate_qualified_symbol(
            database,
            "NZDUSD",
            project_root=tmp_path,
            model_manager=ELIGIBLE_MODEL_MANAGER,
            router_factory=FakeRouter,
            now=NOW,
        )
    failed = {"result": "FAIL", "symbol": "NZDUSD"}
    with pytest.raises(PersistenceConflictError, match="Only PASS"):
        database.mark_qualified("NZDUSD", failed)
    forged = {
        "result": "PASS",
        "symbol": "NZDUSD",
        "evidence_path": str(tmp_path / "missing-evidence.json"),
        "evidence_sha256": "a" * 64,
        "qualification_timestamp": NOW.isoformat(),
        "catalog_version": CATALOG_VERSION,
    }
    with pytest.raises(PersistenceConflictError, match="file is missing"):
        database.mark_qualified("NZDUSD", forged)

    assert database.get_symbol("NZDUSD")["status"] == "candidate"


def test_qualified_without_h1_h4_d1_cannot_activate(tmp_path):
    database = _candidate_database(tmp_path)
    symbol_lifecycle.qualify_candidate(
        database,
        "NZDUSD",
        project_root=tmp_path,
        router_factory=FakeRouter,
        now=NOW,
    )

    with pytest.raises(PersistenceConflictError, match="canonical registry row"):
        symbol_lifecycle.activate_qualified_symbol(
            database,
            "NZDUSD",
            project_root=tmp_path,
            model_manager=ELIGIBLE_MODEL_MANAGER,
            router_factory=FakeRouter,
            now=NOW,
        )


def test_forged_one_row_pass_evidence_cannot_qualify(tmp_path):
    database = _candidate_database(tmp_path)

    with pytest.raises(PersistenceConflictError, match="validator"):
        database.mark_qualified("NZDUSD", _pass_evidence(tmp_path))

    assert database.get_symbol("NZDUSD")["status"] == "candidate"


def test_conflicting_metadata_and_unknown_symbols_are_rejected(tmp_path):
    database = _candidate_database(tmp_path)

    with pytest.raises(PersistenceConflictError, match="canonical catalog"):
        database.register_candidate("NZDUSD", "Wrong", "FOREX", 0.0001)
    with pytest.raises(UnsupportedSymbolError):
        symbol_lifecycle.register_candidate(database, "ZZZQQQ")


def test_database_triggers_reject_arbitrary_and_null_statuses(tmp_path):
    database = _candidate_database(tmp_path)

    with pytest.raises(sqlite3.IntegrityError, match="invalid supported_symbols status"):
        with sqlite3.connect(database.db_path) as connection:
            connection.execute(
                "UPDATE supported_symbols SET status='invented' WHERE symbol_code='NZDUSD'"
            )
    with pytest.raises(sqlite3.IntegrityError, match="invalid supported_symbols status"):
        with sqlite3.connect(database.db_path) as connection:
            connection.execute(
                "UPDATE supported_symbols SET status=NULL WHERE symbol_code='NZDUSD'"
            )


@pytest.mark.parametrize("legacy_status", [None, "unexpected"])
def test_legacy_invalid_status_aborts_without_rewriting_row(
    tmp_path, legacy_status
):
    path = tmp_path / "invalid-legacy.db"
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
            CREATE TABLE dataset_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                candle_count INTEGER DEFAULT 0,
                rolling_window_size INTEGER DEFAULT 2000,
                last_candle_timestamp TEXT,
                blob_path TEXT,
                status TEXT DEFAULT 'pending',
                last_error TEXT,
                last_updated TEXT,
                UNIQUE(symbol, timeframe)
            );
        """)
        connection.execute(
            "INSERT INTO supported_symbols "
            "(symbol_code,display_name,pip_value,status,added_at) "
            "VALUES ('EURUSD','EUR/USD',0.0001,?,'2025-01-01')",
            (legacy_status,),
        )

    with pytest.raises(PersistenceConflictError, match="migration aborted"):
        SQLiteDatabase(str(path))
    with sqlite3.connect(path) as connection:
        preserved = connection.execute(
            "SELECT symbol_code,status FROM supported_symbols"
        ).fetchone()

    assert preserved == ("EURUSD", legacy_status)


def test_legacy_provenance_is_transitional_and_update_completes_it(
    monkeypatch, tmp_path
):
    from deployment.production_readiness import evaluate_dataset_registry_entry
    from scheduler import autonomous_scheduler

    path = tmp_path / "legacy-provenance.db"
    canonical = forex_dataset_path("EURUSD", "H1", project_root=tmp_path)
    stored = RollingDataset(
        "EURUSD", "H1", max_rows=2000, csv_path=canonical
    ).apply(_provider_frame("EURUSD", "H1"), include_existing=False, now=NOW)
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE supported_symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol_code TEXT UNIQUE NOT NULL, display_name TEXT,
                pip_value REAL DEFAULT 0.0001, status TEXT DEFAULT 'active',
                added_at TEXT);
            CREATE TABLE dataset_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL, candle_count INTEGER DEFAULT 0,
                rolling_window_size INTEGER DEFAULT 2000,
                last_candle_timestamp TEXT, blob_path TEXT,
                status TEXT DEFAULT 'pending', last_error TEXT,
                last_updated TEXT, UNIQUE(symbol,timeframe));
        """)
        connection.execute(
            "INSERT INTO supported_symbols "
            "(symbol_code,display_name,pip_value,status,added_at) "
            "VALUES ('EURUSD','EUR/USD',0.0001,'active','2025-01-01')"
        )
        connection.execute(
            "INSERT INTO dataset_registry "
            "(symbol,timeframe,candle_count,rolling_window_size,"
            "last_candle_timestamp,blob_path,status,last_updated) "
            "VALUES ('EURUSD','H1',2000,2000,?,?, 'ready','2025-01-02')",
            (str(stored["last_timestamp"]), str(canonical)),
        )
    database = SQLiteDatabase(str(path))
    before = database.get_dataset_registry("EURUSD", "H1")[0]
    evidence = evaluate_dataset_registry_entry(before, base_dir=tmp_path)

    assert evidence["ready"] is True, json.dumps(evidence, indent=2)
    assert evidence["provenance_state"] == "LEGACY_PROVENANCE_PENDING"
    assert before["legacy_provenance_pending"] == 1

    monkeypatch.setattr(autonomous_scheduler, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        autonomous_scheduler,
        "fetch_market_data",
        lambda *_args: (_provider_frame("EURUSD", "H1"), "Yahoo"),
    )
    result = autonomous_scheduler.run_rolling_update(database, "EURUSD", "H1")
    after = database.get_dataset_registry("EURUSD", "H1")[0]

    assert result["action"] == "updated"
    assert after["legacy_provenance_pending"] == 0
    assert all(
        after[field]
        for field in (
            "provider_used", "external_ticker", "provider_class",
            "source_fetched_at", "source_sha256",
        )
    )


def test_new_registry_row_with_null_provenance_fails_closed(tmp_path):
    from deployment.production_readiness import evaluate_dataset_registry_entry

    database = _candidate_database(tmp_path)
    path = forex_dataset_path("NZDUSD", "H1", project_root=tmp_path)
    stored = RollingDataset(
        "NZDUSD", "H1", max_rows=2000, csv_path=path
    ).apply(_provider_frame("NZDUSD", "H1"), include_existing=False, now=NOW)
    database.upsert_dataset_registry({
        "symbol": "NZDUSD",
        "timeframe": "H1",
        "candle_count": 2000,
        "rolling_window_size": 2000,
        "last_candle_timestamp": str(stored["last_timestamp"]),
        "blob_path": str(path),
        "status": "ready",
    })

    entry = database.get_dataset_registry("NZDUSD", "H1")[0]
    evidence = evaluate_dataset_registry_entry(entry, base_dir=tmp_path)

    assert entry["legacy_provenance_pending"] == 0
    assert evidence["ready"] is False
    assert any("provenance is incomplete" in reason for reason in evidence["reasons"])


@pytest.mark.parametrize("symbol", ["BTCUSDT", "XAUUSD", "USOUSD"])
def test_catalogued_variable_length_symbols_register_as_candidate(tmp_path, symbol):
    database = SQLiteDatabase(str(tmp_path / f"{symbol}.db"))

    row = symbol_lifecycle.register_candidate(database, symbol)

    assert row["symbol_code"] == symbol
    assert row["status"] == "candidate"
    assert database.get_supported_symbols() == []


def test_deprecated_add_symbol_never_activates_even_a_legacy_default(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "default.db"))

    row = database.add_symbol("EURUSD")

    assert row["status"] == "candidate"
    assert database.get_supported_symbols() == []


def test_lifecycle_cli_accepts_catalog_lengths_and_has_no_add_symbol_bypass():
    assert parse_args(["register-candidate", "BTCUSDT"]).symbol == "BTCUSDT"
    assert parse_args(["qualify-symbol", "XAUUSD"]).symbol == "XAUUSD"
    assert parse_args(["activate-symbol", "USOUSD"]).symbol == "USOUSD"
    with pytest.raises(SystemExit):
        parse_args(["--add-symbol", "NZDUSD"])


def test_blocking_mapping_decisions_are_exact():
    assert route_for_provider("USDCHF", "Yahoo").external_ticker == "CHF=X"
    assert get_symbol_spec("USOUSD").symbol_code == "USOUSD"
    assert get_symbol_spec("UKOUSD").symbol_code == "UKOUSD"
    assert get_symbol_spec("BTCUSDT").primary.external_ticker == "BTCUSDT"
    assert get_symbol_spec("ETHUSDT").primary.external_ticker == "ETHUSDT"
    for rejected in ("USOIL", "UKOIL", "BTCUSD", "ETHUSD"):
        with pytest.raises(UnsupportedSymbolError):
            get_symbol_spec(rejected)
    for spot, future in (("XAUUSD", "GC=F"), ("XAGUSD", "SI=F")):
        assert route_for_provider(spot, "Yahoo") is None
        assert any(future in reason for reason in get_symbol_spec(spot).blocked_routes)


def test_candidate_qualification_is_isolated_and_generates_no_ml_state(tmp_path):
    FakeRouter.calls = []
    database = _candidate_database(tmp_path)

    evidence = symbol_lifecycle.qualify_candidate(
        database,
        "NZDUSD",
        project_root=tmp_path,
        router_factory=FakeRouter,
        now=NOW,
    )

    assert evidence["result"] == "PASS"
    assert database.get_symbol("NZDUSD")["status"] == "qualified"
    assert [call[1] for call in FakeRouter.calls] == ["H1", "H4", "D1"]
    for timeframe in ("H1", "H4", "D1"):
        item = evidence["timeframes"][timeframe]
        assert item["row_count"] == item["closed_count"] == 2000
        assert Path(item["csv_path"]) == symbol_qualification_path(
            "NZDUSD", timeframe, project_root=tmp_path
        ).resolve()
        assert not forex_dataset_path(
            "NZDUSD", timeframe, project_root=tmp_path
        ).exists()
    assert database.get_dataset_registry("NZDUSD") == []
    assert database.get_predictions("NZDUSD") == []
    assert not (tmp_path / "models").exists()


def test_stale_qualification_is_rejected(tmp_path):
    database = _candidate_database(tmp_path)
    evidence = symbol_lifecycle.qualify_candidate(
        database,
        "NZDUSD",
        project_root=tmp_path,
        router_factory=FakeRouter,
        now=NOW,
    )
    assert evidence["result"] == "PASS"

    with pytest.raises(PersistenceConflictError, match="stale"):
        symbol_lifecycle.load_current_evidence(
            database,
            "NZDUSD",
            now=NOW + pd.Timedelta(hours=25),
            max_age_seconds=24 * 60 * 60,
        )


def test_activation_publishes_provenance_before_visibility(tmp_path):
    database = _candidate_database(tmp_path)
    symbol_lifecycle.qualify_candidate(
        database,
        "NZDUSD",
        project_root=tmp_path,
        router_factory=FakeRouter,
        now=NOW,
    )
    _populate_canonical(database, tmp_path)

    activated = symbol_lifecycle.activate_qualified_symbol(
        database,
        "NZDUSD",
        project_root=tmp_path,
        now=NOW + pd.Timedelta(minutes=5),
        router_factory=FakeRouter,
        model_manager=ELIGIBLE_MODEL_MANAGER,
    )

    assert activated["status"] == "active"
    assert activated["activation_origin"] == "managed"
    assert symbol_lifecycle.activate_qualified_symbol(
        database,
        "NZDUSD",
        project_root=tmp_path,
        now=NOW + pd.Timedelta(hours=25),
    ) == activated
    assert database.get_supported_symbols()[0]["symbol_code"] == "NZDUSD"
    for timeframe in ("H1", "H4", "D1"):
        entry = database.get_dataset_registry("NZDUSD", timeframe)[0]
        assert entry["status"] == "ready"
        assert entry["candle_count"] == entry["rolling_window_size"] == 2000
        assert entry["provider_used"] == "Yahoo"
        assert entry["external_ticker"] == "NZDUSD=X"
        assert entry["provider_class"] == "FX_REFERENCE"
        assert len(entry["source_sha256"]) == 64


def test_active_without_model_fails_closed(tmp_path):
    database = _candidate_database(tmp_path)
    symbol_lifecycle.qualify_candidate(
        database,
        "NZDUSD",
        project_root=tmp_path,
        router_factory=FakeRouter,
        now=NOW,
    )
    _populate_canonical(database, tmp_path)
    missing_model = SimpleNamespace(
        audit_pair_model=lambda _symbol: {
            "eligible": False,
            "reason": "MODEL_NOT_DEPLOYED",
        }
    )

    with pytest.raises(PersistenceConflictError, match="MODEL_NOT_DEPLOYED"):
        symbol_lifecycle.activate_qualified_symbol(
            database,
            "NZDUSD",
            project_root=tmp_path,
            now=NOW,
            router_factory=FakeRouter,
            model_manager=missing_model,
        )

    assert database.get_symbol("NZDUSD")["status"] == "qualified"


def test_qualified_can_publish_explicit_initial_model_without_becoming_active(
    tmp_path,
):
    database = _candidate_database(tmp_path)
    _set_status(database, "qualified")
    manager = RetrainManager(
        database=database,
        storage=ModelStorage(tmp_path / "models"),
        dataset_root=tmp_path / "data" / "forex",
    )
    provenance = {"snapshot": "qualified-initial-training"}

    result = manager.promote_initial_model(
        {"version": 1},
        pair="NZDUSD",
        dataset_provenance=provenance,
        metadata=_eligibility_metadata("NZDUSD", provenance),
    )

    assert result["status"] == "PROMOTED"
    assert database.get_symbol("NZDUSD")["status"] == "qualified"
    assert (tmp_path / "models" / "latest_NZDUSD.pkl").is_file()


def test_data_supported_without_ml_config_can_qualify_but_not_activate(tmp_path):
    assert operational_capabilities("AUDCHF") == {
        "data_supported": True,
        "ml_configured": False,
    }
    assert operational_capabilities("BTCUSDT")["ml_configured"] is True
    database = _candidate_database(tmp_path, "AUDCHF")
    evidence = symbol_lifecycle.qualify_candidate(
        database,
        "AUDCHF",
        project_root=tmp_path,
        router_factory=FakeRouter,
        now=NOW,
    )

    assert evidence["result"] == "PASS"
    assert database.get_symbol("AUDCHF")["status"] == "qualified"
    with pytest.raises(ValueError, match="ML_CONFIG_NOT_DEFINED"):
        symbol_lifecycle.activate_qualified_symbol(
            database,
            "AUDCHF",
            project_root=tmp_path,
            router_factory=FakeRouter,
            model_manager=ELIGIBLE_MODEL_MANAGER,
            now=NOW,
        )
    manager = RetrainManager(
        database=database,
        storage=ModelStorage(tmp_path / "models"),
    )
    with pytest.raises(ValueError, match="ML_CONFIG_NOT_DEFINED"):
        manager.promote_initial_model(
            {"version": 1},
            pair="AUDCHF",
            dataset_provenance={"snapshot": "data-only"},
            metadata={},
        )


def test_qualification_age_does_not_replace_provider_freshness(tmp_path):
    database = _candidate_database(tmp_path)
    symbol_lifecycle.qualify_candidate(
        database, "NZDUSD", project_root=tmp_path,
        router_factory=FakeRouter, now=NOW,
    )
    _populate_canonical(database, tmp_path)

    class LaterRouter(FakeRouter):
        def fetch(self, bars: int, raise_on_failure: bool):
            return _provider_frame(
                self.symbol,
                self.timeframe,
                bars,
                reference_now=NOW + pd.Timedelta(hours=23),
            )

    with pytest.raises(PersistenceConflictError, match="DATASET_NOT_PROVIDER_CURRENT"):
        symbol_lifecycle.activate_qualified_symbol(
            database,
            "NZDUSD",
            project_root=tmp_path,
            router_factory=LaterRouter,
            model_manager=ELIGIBLE_MODEL_MANAGER,
            now=NOW + pd.Timedelta(hours=23),
        )


def test_weekend_no_new_candle_is_fresh_when_provider_confirms_same_tail(tmp_path):
    database = _candidate_database(tmp_path)
    symbol_lifecycle.qualify_candidate(
        database, "NZDUSD", project_root=tmp_path,
        router_factory=FakeRouter, now=NOW,
    )
    _populate_canonical(database, tmp_path)

    activated = symbol_lifecycle.activate_qualified_symbol(
        database,
        "NZDUSD",
        project_root=tmp_path,
        router_factory=FakeRouter,
        model_manager=ELIGIBLE_MODEL_MANAGER,
        now=NOW + pd.Timedelta(days=2),
    )

    assert activated["status"] == "active"


def test_provider_failure_blocks_activation(tmp_path):
    database = _candidate_database(tmp_path)
    symbol_lifecycle.qualify_candidate(
        database, "NZDUSD", project_root=tmp_path,
        router_factory=FakeRouter, now=NOW,
    )
    _populate_canonical(database, tmp_path)

    class FailedRouter(FakeRouter):
        def fetch(self, bars: int, raise_on_failure: bool):
            raise RuntimeError("provider unavailable")

    with pytest.raises(PersistenceConflictError, match="PROVIDER_FRESHNESS_UNCONFIRMED"):
        symbol_lifecycle.activate_qualified_symbol(
            database,
            "NZDUSD",
            project_root=tmp_path,
            router_factory=FailedRouter,
            model_manager=ELIGIBLE_MODEL_MANAGER,
            now=NOW,
        )


def test_locally_modified_dataset_with_recomputed_hash_fails_provider_reprobe(
    tmp_path,
):
    database = _candidate_database(tmp_path)
    symbol_lifecycle.qualify_candidate(
        database, "NZDUSD", project_root=tmp_path,
        router_factory=FakeRouter, now=NOW,
    )
    _populate_canonical(database, tmp_path)
    path = forex_dataset_path("NZDUSD", "H1", project_root=tmp_path)
    frame = pd.read_csv(path)
    frame.loc[frame.index[-1], ["open", "high", "low", "close"]] += 1e-3
    frame = recalculate_tail_indicators(frame, k=len(frame))
    frame.to_csv(path, index=False)
    entry = database.get_dataset_registry("NZDUSD", "H1")[0]
    entry["source_sha256"] = sha256_file(path)
    database.upsert_dataset_registry(entry)

    with pytest.raises(PersistenceConflictError, match="DATASET_NOT_PROVIDER_CURRENT"):
        symbol_lifecycle.activate_qualified_symbol(
            database,
            "NZDUSD",
            project_root=tmp_path,
            router_factory=FakeRouter,
            model_manager=ELIGIBLE_MODEL_MANAGER,
            now=NOW,
        )


def test_fifty_qualified_are_data_only_and_ignored_by_readiness(
    monkeypatch, tmp_path
):
    database = SQLiteDatabase(str(tmp_path / "astra.db"))
    qualified = [code for code in SYMBOL_CATALOG if code != "EURUSD"][:50]
    for code in qualified:
        spec = get_symbol_spec(code)
        database.register_candidate(
            code, spec.display_name, spec.asset_class, spec.pip_value
        )
        with database._connection() as connection:
            connection.execute(
                "UPDATE supported_symbols SET status='qualified' WHERE symbol_code=?",
                (code,),
            )
    spec = get_symbol_spec("EURUSD")
    database.register_candidate(
        "EURUSD", spec.display_name, spec.asset_class, spec.pip_value
    )
    with database._connection() as connection:
        connection.execute(
            "UPDATE supported_symbols SET status='active' WHERE symbol_code='EURUSD'"
        )

    updates = []
    audits = []
    predictions = []
    monkeypatch.setattr(
        "scheduler.autonomous_scheduler.detect_new_symbols", lambda _db: []
    )
    monkeypatch.setattr(
        "scheduler.autonomous_scheduler.run_rolling_update",
        lambda _db, symbol, timeframe: (
            updates.append((symbol, timeframe)) or {"action": "updated"}
        ),
    )
    monkeypatch.setattr(
        "scheduler.autonomous_scheduler._evaluate_h1_model_gate",
        lambda _db, symbol, _timeframe: (
            audits.append(symbol)
            or {"prediction_eligible": True, "reason": "production_eligible"}
        ),
    )
    monkeypatch.setattr(
        "scheduler.autonomous_scheduler.run_closed_loop_maintenance",
        lambda *_args: {"action": "maintained"},
    )
    monkeypatch.setattr(
        "scheduler.autonomous_scheduler.run_prediction",
        lambda _db, symbol, _timeframe: (
            predictions.append(symbol) or {"action": "predicted"}
        ),
    )

    result = run_cycle(database, "H1")
    readiness = run_production_readiness(
        base_dir=tmp_path,
        db=database,
        required_timeframes=(),
        require_models=False,
    )

    assert len(qualified) == 50
    assert result["symbols_processed"] == 51
    assert result["errors_count"] == 0
    assert {symbol for symbol, _tf in updates} == {*qualified, "EURUSD"}
    assert audits == ["EURUSD"]
    assert predictions == ["EURUSD"]
    registry_check = next(
        check for check in readiness.checks
        if check.check == "Conexión y registry"
    )
    assert registry_check.detail == "1 símbolo(s) activo(s)"


def test_qualification_paths_are_isolated_per_symbol(tmp_path):
    first = symbol_qualification_path("NZDUSD", "H1", project_root=tmp_path)
    second = symbol_qualification_path("EURGBP", "H1", project_root=tmp_path)

    assert first != second
    assert first.parent.name == "NZDUSD"
    assert second.parent.name == "EURGBP"


def test_normal_qualification_module_has_no_model_or_prediction_calls():
    source = inspect.getsource(symbol_lifecycle.qualify_candidate)

    assert "forex.prediction" not in source
    assert "train(" not in source
    assert "save_model" not in source
    assert "save_prediction" not in source


def test_catalog_has_one_unique_metadata_record_per_symbol():
    assert len(SYMBOL_CATALOG) == len(set(SYMBOL_CATALOG))
    assert all(
        set(spec.supported_timeframes) == {"H1", "H4", "D1"}
        for spec in SYMBOL_CATALOG.values()
    )
    assert len(CATALOG_VERSION) == 64
    assert sum(
        operational_capabilities(symbol)["ml_configured"]
        for symbol in SYMBOL_CATALOG
    ) == 17


def test_data_router_rejects_unknown_and_usd_crypto_without_provider_calls():
    for symbol in ("ZZZQQQ", "BTCUSD", "ETHUSD"):
        with pytest.raises(UnsupportedSymbolError):
            DataRouter(symbol, "H1")

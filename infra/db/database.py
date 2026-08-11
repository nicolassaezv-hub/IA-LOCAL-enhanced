"""
ASTRA Database Abstraction Layer
=================================
Decoupled persistence layer — SQLite now, PostgreSQL later.
All business logic uses DatabaseAdapter, never the concrete implementation.
"""
import os
import sqlite3
import json
import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

logger = logging.getLogger(__name__)

DEFAULT_SQLITE_DB_PATH = "memory_db/astra_autonomous.db"


class DatabaseAdapter(ABC):
    """Abstract database interface — all ASTRA code uses this."""

    @abstractmethod
    def get_supported_symbols(self) -> list[dict]: ...
    @abstractmethod
    def add_symbol(self, code: str, name: str, pip: float) -> dict: ...
    @abstractmethod
    def get_dataset_registry(self, symbol: str = None, tf: str = None) -> list[dict]: ...
    @abstractmethod
    def upsert_dataset_registry(self, entry: dict) -> dict: ...
    @abstractmethod
    def save_prediction(self, pred: dict) -> dict: ...
    @abstractmethod
    def get_predictions(self, symbol: str = None, tf: str = None, limit: int = 50) -> list[dict]: ...
    @abstractmethod
    def save_outcome(self, outcome: dict) -> dict: ...
    @abstractmethod
    def get_outcomes(self, symbol: str = None, tf: str = None) -> list[dict]: ...
    @abstractmethod
    def save_model_quality(self, mq: dict) -> dict: ...
    @abstractmethod
    def get_model_quality(self, symbol: str = None, tf: str = None) -> list[dict]: ...
    @abstractmethod
    def create_scheduler_run(self, run: dict) -> dict: ...
    @abstractmethod
    def update_scheduler_run(self, run_id: int, updates: dict) -> dict: ...
    @abstractmethod
    def get_scheduler_runs(self, limit: int = 20) -> list[dict]: ...
    @abstractmethod
    def get_system_health(self) -> dict: ...


class SQLiteDatabase(DatabaseAdapter):
    """SQLite implementation with short-lived, operation-owned connections."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.environ.get(
            "ASTRA_DB_PATH", DEFAULT_SQLITE_DB_PATH
        )
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Own one connection for one operation and always release its handle."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        with self._connection() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS supported_symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol_code TEXT UNIQUE NOT NULL,
                display_name TEXT,
                pip_value REAL DEFAULT 0.0001,
                status TEXT DEFAULT 'active',
                added_at TEXT
            );
            CREATE TABLE IF NOT EXISTS dataset_registry (
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
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT, timeframe TEXT, direction TEXT,
                confidence REAL, entry_price REAL,
                stop_loss REAL, take_profit REAL,
                features_snapshot TEXT,
                pipeline_version TEXT,
                predicted_at TEXT, resolved INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id INTEGER,
                symbol TEXT, timeframe TEXT,
                actual_direction TEXT, pnl_pips REAL,
                hit_tp INTEGER, hit_sl INTEGER,
                resolved_at TEXT
            );
            CREATE TABLE IF NOT EXISTS model_quality (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT, timeframe TEXT,
                accuracy REAL, auc REAL, precision REAL, recall REAL,
                status TEXT DEFAULT 'active', retrain_count INTEGER DEFAULT 0,
                last_evaluated TEXT,
                UNIQUE(symbol, timeframe)
            );
            CREATE TABLE IF NOT EXISTS scheduler_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timeframe TEXT, started_at TEXT, finished_at TEXT,
                status TEXT, symbols_processed INTEGER, predictions_generated INTEGER,
                errors_count INTEGER, log_blob_path TEXT
            );
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """)

    def get_supported_symbols(self) -> list[dict]:
        with self._connection() as c:
            rows = c.execute("SELECT * FROM supported_symbols WHERE status='active'").fetchall()
        return [dict(r) for r in rows]

    def add_symbol(self, code: str, name: str = None, pip: float = 0.0001) -> dict:
        with self._connection() as c:
            c.execute(
                "INSERT OR IGNORE INTO supported_symbols (symbol_code, display_name, pip_value, status, added_at) VALUES (?,?,?,?,?)",
                (code, name or code, pip, "active", datetime.now().isoformat())
            )
            row = c.execute("SELECT * FROM supported_symbols WHERE symbol_code=?", (code,)).fetchone()
        return dict(row)

    def get_dataset_registry(self, symbol: str = None, tf: str = None) -> list[dict]:
        q = "SELECT * FROM dataset_registry WHERE 1=1"
        params = []
        if symbol:
            q += " AND symbol=?"; params.append(symbol)
        if tf:
            q += " AND timeframe=?"; params.append(tf)
        with self._connection() as c:
            rows = c.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def upsert_dataset_registry(self, entry: dict) -> dict:
        with self._connection() as c:
            c.execute("""
                INSERT INTO dataset_registry (symbol, timeframe, candle_count, rolling_window_size,
                    last_candle_timestamp, blob_path, status, last_error, last_updated)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(symbol, timeframe) DO UPDATE SET
                    candle_count=excluded.candle_count,
                    rolling_window_size=excluded.rolling_window_size,
                    last_candle_timestamp=excluded.last_candle_timestamp,
                    blob_path=excluded.blob_path,
                    status=excluded.status,
                    last_error=excluded.last_error,
                    last_updated=excluded.last_updated
            """, (
                entry["symbol"], entry["timeframe"], entry.get("candle_count", 0),
                entry.get("rolling_window_size", 2000), entry.get("last_candle_timestamp"),
                entry.get("blob_path"), entry.get("status", "ready"),
                entry.get("last_error"), datetime.now().isoformat()
            ))
            row = c.execute("SELECT * FROM dataset_registry WHERE symbol=? AND timeframe=?",
                            (entry["symbol"], entry["timeframe"])).fetchone()
        return dict(row)

    def save_prediction(self, pred: dict) -> dict:
        with self._connection() as c:
            c.execute("""
                INSERT INTO predictions (symbol, timeframe, direction, confidence, entry_price,
                    stop_loss, take_profit, features_snapshot, pipeline_version, predicted_at, resolved)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                pred.get("symbol"), pred.get("timeframe"), pred.get("direction"),
                pred.get("confidence", 0), pred.get("entry_price", 0),
                pred.get("stop_loss", 0), pred.get("take_profit", 0),
                json.dumps(pred.get("features_snapshot", {})),
                pred.get("pipeline_version", "v6.0.1"),
                pred.get("predicted_at", datetime.now().isoformat()), 0
            ))
            row = c.execute("SELECT * FROM predictions ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row)

    def get_predictions(self, symbol: str = None, tf: str = None, limit: int = 50) -> list[dict]:
        q = "SELECT * FROM predictions WHERE 1=1"
        params = []
        if symbol:
            q += " AND symbol=?"; params.append(symbol)
        if tf:
            q += " AND timeframe=?"; params.append(tf)
        q += f" ORDER BY id DESC LIMIT {limit}"
        with self._connection() as c:
            rows = c.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def save_outcome(self, outcome: dict) -> dict:
        with self._connection() as c:
            c.execute("""
                INSERT INTO outcomes (prediction_id, symbol, timeframe, actual_direction,
                    pnl_pips, hit_tp, hit_sl, resolved_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                outcome.get("prediction_id"), outcome.get("symbol"), outcome.get("timeframe"),
                outcome.get("actual_direction"), outcome.get("pnl_pips", 0),
                int(outcome.get("hit_tp", False)), int(outcome.get("hit_sl", False)),
                outcome.get("resolved_at", datetime.now().isoformat())
            ))
            row = c.execute("SELECT * FROM outcomes ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row)

    def get_outcomes(self, symbol: str = None, tf: str = None) -> list[dict]:
        q = "SELECT * FROM outcomes WHERE 1=1"
        params = []
        if symbol:
            q += " AND symbol=?"; params.append(symbol)
        if tf:
            q += " AND timeframe=?"; params.append(tf)
        with self._connection() as c:
            rows = c.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def save_model_quality(self, mq: dict) -> dict:
        with self._connection() as c:
            c.execute("""
                INSERT INTO model_quality (symbol, timeframe, accuracy, auc, precision, recall,
                    status, retrain_count, last_evaluated)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(symbol, timeframe) DO UPDATE SET
                    accuracy=excluded.accuracy, auc=excluded.auc,
                    precision=excluded.precision, recall=excluded.recall,
                    status=excluded.status, retrain_count=excluded.retrain_count,
                    last_evaluated=excluded.last_evaluated
            """, (
                mq["symbol"], mq["timeframe"], mq.get("accuracy", 0), mq.get("auc", 0),
                mq.get("precision", 0), mq.get("recall", 0),
                mq.get("status", "active"), mq.get("retrain_count", 0),
                datetime.now().isoformat()
            ))
            row = c.execute("SELECT * FROM model_quality WHERE symbol=? AND timeframe=?",
                            (mq["symbol"], mq["timeframe"])).fetchone()
        return dict(row)

    def get_model_quality(self, symbol: str = None, tf: str = None) -> list[dict]:
        q = "SELECT * FROM model_quality WHERE 1=1"
        params = []
        if symbol:
            q += " AND symbol=?"; params.append(symbol)
        if tf:
            q += " AND timeframe=?"; params.append(tf)
        with self._connection() as c:
            rows = c.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def create_scheduler_run(self, run: dict) -> dict:
        with self._connection() as c:
            cur = c.execute("""
                INSERT INTO scheduler_runs (timeframe, started_at, status, symbols_processed,
                    predictions_generated, errors_count, finished_at, log_blob_path)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                run.get("timeframe"), run.get("started_at", datetime.now().isoformat()),
                run.get("status", "running"), 0, 0, 0, None, run.get("log_blob_path")
            ))
            row = c.execute("SELECT * FROM scheduler_runs WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(row)

    def update_scheduler_run(self, run_id: int, updates: dict) -> dict:
        fields = []
        values = []
        for k, v in updates.items():
            fields.append(f"{k}=?")
            values.append(v)
        values.append(run_id)
        with self._connection() as c:
            c.execute(f"UPDATE scheduler_runs SET {','.join(fields)} WHERE id=?", values)
            row = c.execute("SELECT * FROM scheduler_runs WHERE id=?", (run_id,)).fetchone()
        return dict(row)

    def get_scheduler_runs(self, limit: int = 20) -> list[dict]:
        with self._connection() as c:
            rows = c.execute(
                f"SELECT * FROM scheduler_runs ORDER BY id DESC LIMIT {limit}"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_system_health(self) -> dict:
        with self._connection() as c:
            symbols = c.execute("SELECT COUNT(*) FROM supported_symbols WHERE status='active'").fetchone()[0]
            datasets = c.execute("SELECT COUNT(*) FROM dataset_registry WHERE status='ready'").fetchone()[0]
            errors = c.execute("SELECT COUNT(*) FROM dataset_registry WHERE status='error'").fetchone()[0]
            preds = c.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
            degraded = c.execute("SELECT COUNT(*) FROM model_quality WHERE status IN ('degraded','retrain_blocked')").fetchone()[0]
            last_run = c.execute("SELECT * FROM scheduler_runs ORDER BY id DESC LIMIT 1").fetchone()
        return {
            "symbols_active": symbols,
            "datasets_ready": datasets,
            "datasets_error": errors,
            "predictions_total": preds,
            "degraded_models": degraded,
            "last_run": dict(last_run) if last_run else None,
            "healthy": errors == 0 and degraded == 0,
            "db_engine": "sqlite",
            "db_path": self.db_path
        }


class PostgreSQLDatabase(DatabaseAdapter):
    """PostgreSQL stub — implement with psycopg2 when migrating."""
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "PostgreSQL adapter not yet implemented. "
            "TODO: install psycopg2 and implement all abstract methods "
            "using the same SQL logic but with PostgreSQL syntax. "
            "The DatabaseAdapter interface stays the same — only this class changes."
        )
    def get_supported_symbols(self): raise NotImplementedError()
    def add_symbol(self, code, name, pip): raise NotImplementedError()
    def get_dataset_registry(self, symbol=None, tf=None): raise NotImplementedError()
    def upsert_dataset_registry(self, entry): raise NotImplementedError()
    def save_prediction(self, pred): raise NotImplementedError()
    def get_predictions(self, symbol=None, tf=None, limit=50): raise NotImplementedError()
    def save_outcome(self, outcome): raise NotImplementedError()
    def get_outcomes(self, symbol=None, tf=None): raise NotImplementedError()
    def save_model_quality(self, mq): raise NotImplementedError()
    def get_model_quality(self, symbol=None, tf=None): raise NotImplementedError()
    def create_scheduler_run(self, run): raise NotImplementedError()
    def update_scheduler_run(self, run_id, updates): raise NotImplementedError()
    def get_scheduler_runs(self, limit=20): raise NotImplementedError()
    def get_system_health(self): raise NotImplementedError()


def get_database() -> DatabaseAdapter:
    """Factory: returns the correct database adapter based on ASTRA_DB_ENGINE env var."""
    engine = os.environ.get("ASTRA_DB_ENGINE", "sqlite").lower()
    if engine == "postgresql" or engine == "postgres":
        return PostgreSQLDatabase()
    return SQLiteDatabase()

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
import hashlib
import math
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from astra_version import ASTRA_VERSION
from runtime_paths import configured_project_path

logger = logging.getLogger(__name__)

DEFAULT_SQLITE_DB_PATH = "memory_db/astra_autonomous.db"
# Release of the ASTRA runtime that generated/persisted the prediction.
_PIPELINE_VERSION = f"v{ASTRA_VERSION}"
SYMBOL_STATUSES = ("candidate", "qualified", "active", "disabled")
ACTIVATION_ORIGINS = ("legacy", "managed")


def configured_sqlite_path() -> Path:
    """Return the environment-selected SQLite path under the ASTRA project root."""
    return configured_project_path("ASTRA_DB_PATH", DEFAULT_SQLITE_DB_PATH)


class PersistenceConflictError(RuntimeError):
    """Raised when one stable identity is reused for conflicting evidence."""


class SymbolLifecycleError(ValueError):
    """Raised when a production consumer receives a non-active symbol."""


class SQLiteReadOnlyError(RuntimeError):
    """Raised before a mutating SQLite API can use a read-only adapter."""


def require_active_symbol(symbol: str, *, database=None) -> dict:
    """Return the authoritative active row or fail closed before production use."""
    code = str(symbol or "").strip().upper()
    authority = database if database is not None else get_database()
    getter = getattr(authority, "get_symbol", None)
    row = getter(code) if callable(getter) and code else None
    if row is None:
        raise SymbolLifecycleError(
            f"SYMBOL_NOT_ACTIVE: {code or '<empty>'} status=unregistered"
        )
    status = str(row.get("status") or "").strip().lower()
    if status != "active":
        raise SymbolLifecycleError(f"SYMBOL_NOT_ACTIVE: {code} status={status}")
    return row


def stable_prediction_id(
    symbol: str,
    timeframe: str,
    candle_timestamp: str,
    action: str,
) -> str:
    """Build the restart-stable identity of one final candle decision."""
    identity = "|".join(
        (
            str(symbol).upper().strip(),
            str(timeframe).upper().strip(),
            str(candle_timestamp).strip(),
            str(action).upper().strip(),
        )
    )
    if not all(identity.split("|")):
        raise ValueError("prediction identity requires symbol, timeframe, candle and action")
    return "pred_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]


def _float_evidence_equal(stored, requested) -> bool:
    """Compare persisted floats without masking financially meaningful changes."""
    if stored is None or requested is None:
        return stored is None and requested is None
    try:
        return math.isclose(
            float(stored), float(requested), rel_tol=1e-12, abs_tol=1e-12
        )
    except (TypeError, ValueError):
        return False


def _json_evidence_equal(stored, requested) -> bool:
    try:
        stored_value = json.loads(stored) if isinstance(stored, str) else stored
        requested_value = json.loads(requested) if isinstance(requested, str) else requested
    except (TypeError, json.JSONDecodeError):
        return False
    return stored_value == requested_value


class DatabaseAdapter(ABC):
    """Abstract database interface — all ASTRA code uses this."""

    @abstractmethod
    def get_active_symbols(self) -> list[dict]: ...
    @abstractmethod
    def get_data_symbols(self) -> list[dict]: ...
    @abstractmethod
    def get_supported_symbols(self) -> list[dict]: ...
    @abstractmethod
    def add_symbol(self, code: str, name: str, pip: float) -> dict: ...
    @abstractmethod
    def get_symbol(self, code: str) -> dict | None: ...
    @abstractmethod
    def get_symbols_by_status(self, status: str) -> list[dict]: ...
    @abstractmethod
    def register_candidate(
        self, code: str, name: str, asset_class: str, pip: float
    ) -> dict: ...
    @abstractmethod
    def mark_qualified(self, code: str, evidence: dict) -> dict: ...
    @abstractmethod
    def _persist_authorized_activation(
        self, authorization: object
    ) -> dict: ...
    @abstractmethod
    def disable_symbol(self, code: str) -> dict: ...
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

    def __init__(self, db_path: str = None, read_only: bool = False):
        # An explicit argument remains caller-owned for compatibility.  Only the
        # environment/default contract defines relative paths from PROJECT_ROOT.
        self.db_path = db_path or str(configured_sqlite_path())
        self.read_only = bool(read_only)
        self._read_only_uri: str | None = None
        if self.read_only:
            absolute_path = Path(self.db_path).expanduser().resolve()
            if not absolute_path.is_file():
                raise FileNotFoundError(
                    f"SQLITE_READ_ONLY_DATABASE_NOT_FOUND: {absolute_path}"
                )
            sidecars = (
                Path(f"{absolute_path}-wal"),
                Path(f"{absolute_path}-shm"),
            )
            if any(sidecar.exists() for sidecar in sidecars):
                raise SQLiteReadOnlyError(
                    "SQLITE_READ_ONLY_UNCHECKPOINTED_STATE: immutable access "
                    f"requires no WAL/SHM sidecars for {absolute_path}"
                )
            # immutable=1 prevents a clean WAL database from creating auxiliary
            # files during audits. Existing WAL/SHM state is rejected above so
            # uncheckpointed evidence can never be silently ignored.
            self._read_only_uri = f"{absolute_path.as_uri()}?mode=ro&immutable=1"
            return
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Own one connection for one operation and always release its handle."""
        if self.read_only:
            conn = sqlite3.connect(self._read_only_uri, uri=True)
            try:
                conn.row_factory = sqlite3.Row
                yield conn
            finally:
                conn.close()
            return

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

    def _require_writable(self) -> None:
        if self.read_only:
            raise SQLiteReadOnlyError(
                "SQLITE_READ_ONLY_WRITE_FORBIDDEN: mutating API called on "
                f"read-only database {Path(self.db_path).resolve()}"
            )

    @contextmanager
    def _writable_connection(self) -> Iterator[sqlite3.Connection]:
        """Open a writable operation or reject it before executing any SQL."""
        self._require_writable()
        with self._connection() as conn:
            yield conn

    def _init_schema(self):
        with self._writable_connection() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS supported_symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol_code TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                pip_value REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'candidate'
                    CHECK(status IN ('candidate','qualified','active','disabled')),
                added_at TEXT NOT NULL,
                updated_at TEXT,
                qualification_evidence_path TEXT,
                qualification_sha256 TEXT,
                qualified_at TEXT,
                qualification_catalog_version TEXT,
                activation_origin TEXT NOT NULL DEFAULT 'managed'
                    CHECK(activation_origin IN ('legacy','managed'))
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
                provider_used TEXT,
                external_ticker TEXT,
                provider_class TEXT,
                source_fetched_at TEXT,
                source_sha256 TEXT,
                acquisition_metadata TEXT,
                legacy_provenance_pending INTEGER NOT NULL DEFAULT 0,
                UNIQUE(symbol, timeframe)
            );
            CREATE TABLE IF NOT EXISTS predictions (
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
                model_contract TEXT,
                target_profile TEXT,
                target_definition_version INTEGER,
                feature_profile TEXT,
                score_type TEXT,
                direction_score REAL,
                decision_percentile REAL,
                decision_policy TEXT,
                confidence_semantics TEXT,
                status TEXT DEFAULT 'PENDING',
                resolved INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id TEXT,
                outcome_key TEXT,
                symbol TEXT, timeframe TEXT,
                actual_direction TEXT, pnl_pips REAL,
                hit_tp INTEGER, hit_sl INTEGER,
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
                dataset_provenance TEXT,
                horizon_candles INTEGER,
                model_contract TEXT,
                target_profile TEXT,
                target_definition_version INTEGER,
                feature_profile TEXT,
                score_type TEXT,
                direction_score REAL,
                decision_percentile REAL,
                decision_policy TEXT,
                confidence_semantics TEXT,
                evaluation_semantics TEXT
            );
            CREATE TABLE IF NOT EXISTS retrain_runs (
                run_id TEXT PRIMARY KEY,
                evidence_key TEXT UNIQUE NOT NULL,
                request_id TEXT,
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
            CREATE TABLE IF NOT EXISTS model_provenance (
                model_id TEXT PRIMARY KEY,
                retrain_run_id TEXT UNIQUE NOT NULL,
                trigger TEXT,
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
                errors_count INTEGER, log_blob_path TEXT,
                interruption_reason TEXT, recovered_at TEXT
            );
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """)
            self._migrate_symbol_lifecycle_schema(c)
            self._migrate_closed_loop_schema(c)

    @staticmethod
    def _add_columns(c: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
        present = {row[1] for row in c.execute(f"PRAGMA table_info({table})")}
        for name, declaration in columns.items():
            if name not in present:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")

    def _migrate_symbol_lifecycle_schema(self, c: sqlite3.Connection) -> None:
        """Add lifecycle/provenance fields without replacing historical rows."""
        invalid_statuses = [
            row[0]
            for row in c.execute(
                "SELECT DISTINCT status FROM supported_symbols "
                "WHERE status IS NULL OR status NOT IN "
                "('candidate','qualified','active','disabled')"
            ).fetchall()
        ]
        if invalid_statuses:
            raise PersistenceConflictError(
                "Unsupported existing symbol statuses; migration aborted without "
                f"rewriting rows: {invalid_statuses}"
            )

        existing_symbol_columns = {
            row[1] for row in c.execute("PRAGMA table_info(supported_symbols)")
        }
        origin_is_prepatch = "activation_origin" not in existing_symbol_columns
        self._add_columns(c, "supported_symbols", {
            "asset_class": "TEXT",
            "updated_at": "TEXT",
            "qualification_evidence_path": "TEXT",
            "qualification_sha256": "TEXT",
            "qualified_at": "TEXT",
            "qualification_catalog_version": "TEXT",
            "activation_origin": "TEXT NOT NULL DEFAULT 'managed'",
        })
        if origin_is_prepatch:
            c.execute(
                "UPDATE supported_symbols SET activation_origin='legacy' "
                "WHERE status='active'"
            )
        existing_registry_columns = {
            row[1] for row in c.execute("PRAGMA table_info(dataset_registry)")
        }
        provenance_is_legacy = "provider_used" not in existing_registry_columns
        self._add_columns(c, "dataset_registry", {
            "provider_used": "TEXT",
            "external_ticker": "TEXT",
            "provider_class": "TEXT",
            "source_fetched_at": "TEXT",
            "source_sha256": "TEXT",
            "acquisition_metadata": "TEXT",
            "legacy_provenance_pending": "INTEGER NOT NULL DEFAULT 0",
        })
        if provenance_is_legacy:
            c.execute(
                "UPDATE dataset_registry SET legacy_provenance_pending=1 "
                "WHERE provider_used IS NULL AND external_ticker IS NULL "
                "AND provider_class IS NULL AND source_fetched_at IS NULL "
                "AND source_sha256 IS NULL AND EXISTS ("
                "SELECT 1 FROM supported_symbols AS symbol "
                "WHERE symbol.symbol_code=dataset_registry.symbol "
                "AND symbol.status='active')"
            )

        from forex.data.symbol_catalog import SYMBOL_CATALOG

        for code, spec in SYMBOL_CATALOG.items():
            c.execute(
                "UPDATE supported_symbols SET asset_class=COALESCE(asset_class, ?) "
                "WHERE symbol_code=?",
                (spec.asset_class, code),
            )
        c.execute(
            "UPDATE supported_symbols SET asset_class='UNKNOWN' "
            "WHERE asset_class IS NULL OR TRIM(asset_class)=''"
        )
        c.executescript("""
            DROP TRIGGER IF EXISTS supported_symbols_status_insert;
            DROP TRIGGER IF EXISTS supported_symbols_status_update;
            DROP TRIGGER IF EXISTS supported_symbols_origin_insert;
            DROP TRIGGER IF EXISTS supported_symbols_origin_update;
            CREATE TRIGGER supported_symbols_status_insert
            BEFORE INSERT ON supported_symbols
            WHEN NEW.status IS NULL OR
                 NEW.status NOT IN ('candidate','qualified','active','disabled')
            BEGIN
                SELECT RAISE(ABORT, 'invalid supported_symbols status');
            END;
            CREATE TRIGGER supported_symbols_status_update
            BEFORE UPDATE OF status ON supported_symbols
            WHEN NEW.status IS NULL OR
                 NEW.status NOT IN ('candidate','qualified','active','disabled')
            BEGIN
                SELECT RAISE(ABORT, 'invalid supported_symbols status');
            END;
            CREATE TRIGGER supported_symbols_origin_insert
            BEFORE INSERT ON supported_symbols
            WHEN NEW.activation_origin IS NULL OR
                 NEW.activation_origin NOT IN ('legacy','managed')
            BEGIN
                SELECT RAISE(ABORT, 'invalid supported_symbols activation_origin');
            END;
            CREATE TRIGGER supported_symbols_origin_update
            BEFORE UPDATE OF activation_origin ON supported_symbols
            WHEN NEW.activation_origin IS NULL OR
                 NEW.activation_origin NOT IN ('legacy','managed')
            BEGIN
                SELECT RAISE(ABORT, 'invalid supported_symbols activation_origin');
            END;
        """)

    def _migrate_closed_loop_schema(self, c: sqlite3.Connection) -> None:
        """Apply additive, repeatable B1 migrations to existing SQLite files."""
        self._add_columns(c, "scheduler_runs", {
            "interruption_reason": "TEXT",
            "recovered_at": "TEXT",
        })
        self._add_columns(c, "predictions", {
            "prediction_id": "TEXT",
            "action": "TEXT",
            "raw_action": "TEXT",
            "candle_timestamp": "TEXT",
            "horizon_candles": "INTEGER",
            "model_identity": "TEXT",
            "dataset_provenance": "TEXT",
            "model_contract": "TEXT",
            "target_profile": "TEXT",
            "target_definition_version": "INTEGER",
            "feature_profile": "TEXT",
            "score_type": "TEXT",
            "direction_score": "REAL",
            "decision_percentile": "REAL",
            "decision_policy": "TEXT",
            "confidence_semantics": "TEXT",
            "status": "TEXT DEFAULT 'PENDING'",
        })
        self._add_columns(c, "outcomes", {
            "outcome_key": "TEXT",
            "prediction_timestamp": "TEXT",
            "evaluation_timestamp": "TEXT",
            "action": "TEXT",
            "entry_price": "REAL",
            "observed_price": "REAL",
            "observed_return": "REAL",
            "result": "TEXT",
            "status": "TEXT",
            "model_identity": "TEXT",
            "dataset_provenance": "TEXT",
            "horizon_candles": "INTEGER",
            "model_contract": "TEXT",
            "target_profile": "TEXT",
            "target_definition_version": "INTEGER",
            "feature_profile": "TEXT",
            "score_type": "TEXT",
            "direction_score": "REAL",
            "decision_percentile": "REAL",
            "decision_policy": "TEXT",
            "confidence_semantics": "TEXT",
            "evaluation_semantics": "TEXT",
        })
        self._add_columns(c, "retrain_runs", {
            "owner_token": "TEXT",
            "heartbeat_at": "TEXT",
            "request_id": "TEXT",
        })
        self._add_columns(c, "model_provenance", {
            "trigger": "TEXT",
        })
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_predictions_uid "
            "ON predictions(prediction_id) WHERE prediction_id IS NOT NULL"
        )
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_outcomes_key "
            "ON outcomes(outcome_key) WHERE outcome_key IS NOT NULL"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_predictions_pending "
            "ON predictions(status, symbol, timeframe, candle_timestamp)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_outcomes_finalized "
            "ON outcomes(status, symbol, timeframe, id)"
        )
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_manual_retrain_request "
            "ON retrain_runs(symbol, timeframe, trigger, request_id) "
            "WHERE trigger='manual_quality_retrain' AND request_id IS NOT NULL"
        )
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_manual_retrain_active "
            "ON retrain_runs(symbol, timeframe) "
            "WHERE trigger='manual_quality_retrain' "
            "AND status IN ('PENDING','RUNNING','VALIDATED')"
        )

    def get_active_symbols(self) -> list[dict]:
        return self.get_symbols_by_status("active")

    def get_data_symbols(self) -> list[dict]:
        with self._connection() as c:
            rows = c.execute(
                "SELECT * FROM supported_symbols "
                "WHERE status IN ('qualified','active') ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_supported_symbols(self) -> list[dict]:
        """Deprecated compatibility alias for production-active symbols."""
        return self.get_active_symbols()

    @staticmethod
    def _validate_symbol_status(status: str) -> str:
        normalized = str(status or "").strip().lower()
        if normalized not in SYMBOL_STATUSES:
            raise ValueError(f"Invalid symbol status: {status!r}")
        return normalized

    def get_symbol(self, code: str) -> dict | None:
        normalized = str(code or "").strip().upper()
        with self._connection() as c:
            row = c.execute(
                "SELECT * FROM supported_symbols WHERE symbol_code=?", (normalized,)
            ).fetchone()
        return dict(row) if row else None

    def get_symbols_by_status(self, status: str) -> list[dict]:
        normalized = self._validate_symbol_status(status)
        with self._connection() as c:
            rows = c.execute(
                "SELECT * FROM supported_symbols WHERE status=?",
                (normalized,),
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _catalog_metadata(code, name, asset_class, pip):
        from forex.data.symbol_catalog import get_symbol_spec

        spec = get_symbol_spec(code)
        requested_name = spec.display_name if name is None else str(name).strip()
        requested_class = (
            spec.asset_class if asset_class is None else str(asset_class).upper()
        )
        requested_pip = spec.pip_value if pip is None else float(pip)
        if (
            requested_name != spec.display_name
            or requested_class != spec.asset_class
            or not _float_evidence_equal(requested_pip, spec.pip_value)
        ):
            raise PersistenceConflictError(
                f"Metadata for {spec.symbol_code} conflicts with canonical catalog"
            )
        return (
            spec.symbol_code,
            requested_name,
            requested_class,
            requested_pip,
            spec,
        )

    def register_candidate(
        self,
        code: str,
        name: str,
        asset_class: str,
        pip: float,
    ) -> dict:
        code, name, asset_class, pip, _ = self._catalog_metadata(
            code, name, asset_class, pip
        )
        now = datetime.now(timezone.utc).isoformat()
        with self._writable_connection() as c:
            existing = c.execute(
                "SELECT * FROM supported_symbols WHERE symbol_code=?", (code,)
            ).fetchone()
            if existing:
                row = dict(existing)
                if (
                    row.get("display_name") != name
                    or str(row.get("asset_class") or "").upper() != asset_class
                    or not _float_evidence_equal(row.get("pip_value"), pip)
                ):
                    raise PersistenceConflictError(
                        f"Existing metadata for {code} conflicts with candidate request"
                    )
                return row
            c.execute(
                "INSERT INTO supported_symbols "
                "(symbol_code, display_name, asset_class, pip_value, status, "
                "added_at, updated_at, activation_origin) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (code, name, asset_class, pip, "candidate", now, now, "managed"),
            )
            row = c.execute(
                "SELECT * FROM supported_symbols WHERE symbol_code=?", (code,)
            ).fetchone()
        return dict(row)

    def add_symbol(
        self, code: str, name: str = None, pip: float = None
    ) -> dict:
        """Deprecated compatibility wrapper; every new row starts candidate."""
        code, name, asset_class, pip, _ = self._catalog_metadata(
            code, name, None, pip
        )
        return self.register_candidate(code, name, asset_class, pip)

    def mark_qualified(self, code: str, evidence: dict) -> dict:
        code, _, _, _, _ = self._catalog_metadata(code, None, None, None)
        if evidence.get("result") != "PASS" or evidence.get("symbol") != code:
            raise PersistenceConflictError(
                "Only PASS evidence for the same symbol can qualify"
            )
        required = (
            "evidence_path",
            "evidence_sha256",
            "qualification_timestamp",
            "catalog_version",
        )
        if any(not evidence.get(field) for field in required):
            raise PersistenceConflictError("Qualification evidence is incomplete")
        evidence_path = Path(evidence["evidence_path"]).resolve()
        if not evidence_path.is_file():
            raise PersistenceConflictError("Qualification evidence file is missing")
        actual_evidence_sha256 = hashlib.sha256(
            evidence_path.read_bytes()
        ).hexdigest()
        if actual_evidence_sha256 != evidence["evidence_sha256"]:
            raise PersistenceConflictError("Qualification evidence hash differs")
        try:
            persisted_evidence = json.loads(
                evidence_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PersistenceConflictError(
                "Qualification evidence JSON is invalid"
            ) from exc

        from forex.data.symbol_catalog import (
            CATALOG_VERSION,
            SUPPORTED_TIMEFRAMES,
            route_for_provider,
        )

        identity_fields = (
            "result", "symbol", "catalog_version", "qualification_timestamp"
        )
        if any(
            persisted_evidence.get(field) != evidence.get(field)
            for field in identity_fields
        ) or persisted_evidence.get("catalog_version") != CATALOG_VERSION:
            raise PersistenceConflictError(
                "Qualification evidence identity/catalog differs"
            )
        try:
            qualified_at = datetime.fromisoformat(
                persisted_evidence["qualification_timestamp"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PersistenceConflictError(
                "Qualification timestamp is invalid"
            ) from exc
        if qualified_at.tzinfo is None:
            raise PersistenceConflictError(
                "Qualification timestamp must be timezone-aware"
            )
        timeframe_evidence = persisted_evidence.get("timeframes")
        if not isinstance(timeframe_evidence, dict) or set(timeframe_evidence) != set(
            SUPPORTED_TIMEFRAMES
        ):
            raise PersistenceConflictError(
                "Qualification evidence requires exact H1/H4/D1 results"
            )
        import pandas as pd
        from scripts.validate_symbol_universe import (
            validate_cross_timeframes,
            validate_dataset_frame,
        )

        validated_frames = {}
        for timeframe in SUPPORTED_TIMEFRAMES:
            item = timeframe_evidence[timeframe]
            csv_path = Path(str(item.get("csv_path") or "")).resolve()
            route = route_for_provider(code, item.get("provider"))
            if (
                item.get("timeframe") != timeframe
                or item.get("result") != "PASS"
                or item.get("row_count") != 2000
                or item.get("closed_count") != 2000
                or not item.get("provider")
                or not item.get("external_ticker")
                or not item.get("provider_class")
                or not item.get("source_fetched_at")
                or route is None
                or route.external_ticker != item.get("external_ticker")
                or route.provider_class != item.get("provider_class")
                or not csv_path.is_file()
                or hashlib.sha256(csv_path.read_bytes()).hexdigest()
                != item.get("csv_sha256")
            ):
                raise PersistenceConflictError(
                    f"Qualification evidence is incomplete for {timeframe}"
                )
            if csv_path.parent != evidence_path.parent:
                raise PersistenceConflictError(
                    f"Qualification CSV is outside the evidence directory for {timeframe}"
                )
            try:
                frame = pd.read_csv(csv_path, encoding="utf-8")
                stage, validated = validate_dataset_frame(
                    frame,
                    code,
                    timeframe,
                    now=qualified_at,
                    acquisition_metadata=item.get("acquisition_metadata"),
                    provider=item.get("provider"),
                )
            except Exception as exc:
                raise PersistenceConflictError(
                    f"Qualification validator failed for {timeframe}: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
            if stage["status"] == "FAIL" or stage["blocking"] or validated is None:
                raise PersistenceConflictError(
                    f"Qualification validator rejected {timeframe}: "
                    f"{stage['errors'] or stage['warnings']}"
                )
            if len(validated) != 2000 or int(stage["details"]["closed_rows"]) != 2000:
                raise PersistenceConflictError(
                    f"Qualification validator did not prove 2000 closed rows for {timeframe}"
                )
            validated_frames[timeframe] = validated

        cross = persisted_evidence.get("cross_timeframe") or {}
        if (
            cross.get("status") not in {"PASS", "WARNING"}
            or cross.get("blocking") is not False
        ):
            raise PersistenceConflictError(
                "Qualification cross-timeframe evidence did not pass"
            )
        recomputed_cross = validate_cross_timeframes(validated_frames)
        if recomputed_cross["status"] == "FAIL" or recomputed_cross["blocking"]:
            raise PersistenceConflictError(
                "Canonical cross-timeframe validator rejected qualification bytes"
            )
        with self._writable_connection() as c:
            row = c.execute(
                "SELECT * FROM supported_symbols WHERE symbol_code=?", (code,)
            ).fetchone()
            if row is None:
                raise PersistenceConflictError(f"Symbol {code} is not registered")
            current = dict(row)
            if current["status"] not in {"candidate", "qualified"}:
                raise PersistenceConflictError(
                    f"Cannot qualify {code} from status {current['status']}"
                )
            now = datetime.now(timezone.utc).isoformat()
            c.execute(
                "UPDATE supported_symbols SET status='qualified', "
                "qualification_evidence_path=?, qualification_sha256=?, qualified_at=?, "
                "qualification_catalog_version=?, updated_at=? WHERE symbol_code=?",
                (
                    evidence["evidence_path"],
                    evidence["evidence_sha256"],
                    evidence["qualification_timestamp"],
                    evidence["catalog_version"],
                    now,
                    code,
                ),
            )
            updated = c.execute(
                "SELECT * FROM supported_symbols WHERE symbol_code=?", (code,)
            ).fetchone()
        return dict(updated)

    def _persist_authorized_activation(self, authorization: object) -> dict:
        from forex.data.symbol_lifecycle import is_activation_authorization

        if not is_activation_authorization(authorization):
            raise PersistenceConflictError(
                "Activation requires an opaque lifecycle authorization"
            )
        code, _, _, _, _ = self._catalog_metadata(
            authorization.symbol, None, None, None
        )
        with self._writable_connection() as c:
            row = c.execute(
                "SELECT * FROM supported_symbols WHERE symbol_code=?", (code,)
            ).fetchone()
            if row is None:
                raise PersistenceConflictError(f"Symbol {code} is not registered")
            current = dict(row)
            if current["status"] == "active":
                if current.get("qualification_sha256") == authorization.evidence_sha256:
                    return current
                raise PersistenceConflictError("Active symbol evidence hash differs")
            if current["status"] != "qualified":
                raise PersistenceConflictError(
                    f"Cannot activate {code} from status {current['status']}"
                )
            if (
                not authorization.evidence_sha256
                or current.get("qualification_sha256")
                != authorization.evidence_sha256
            ):
                raise PersistenceConflictError("Qualification evidence hash differs")
            registry_rows = c.execute(
                "SELECT * FROM dataset_registry WHERE symbol=?", (code,)
            ).fetchall()
            registry_by_timeframe = {
                row["timeframe"]: dict(row) for row in registry_rows
            }
            required_timeframes = {"H1", "H4", "D1"}
            if set(registry_by_timeframe) != required_timeframes:
                raise PersistenceConflictError(
                    "Activation requires canonical H1/H4/D1 registry rows"
                )
            for timeframe, registry in registry_by_timeframe.items():
                if (
                    registry.get("status") != "ready"
                    or registry.get("candle_count") != 2000
                    or registry.get("rolling_window_size") != 2000
                    or any(
                        not registry.get(field)
                        for field in (
                            "blob_path",
                            "provider_used",
                            "external_ticker",
                            "provider_class",
                            "source_fetched_at",
                            "source_sha256",
                        )
                    )
                    or registry.get("legacy_provenance_pending") not in (0, False)
                ):
                    raise PersistenceConflictError(
                        f"Activation registry contract is incomplete for {timeframe}"
                    )
            c.execute(
                "UPDATE supported_symbols SET status='active', "
                "activation_origin='managed', updated_at=? "
                "WHERE symbol_code=?",
                (datetime.now(timezone.utc).isoformat(), code),
            )
            updated = c.execute(
                "SELECT * FROM supported_symbols WHERE symbol_code=?", (code,)
            ).fetchone()
        return dict(updated)

    def disable_symbol(self, code: str) -> dict:
        code, _, _, _, _ = self._catalog_metadata(code, None, None, None)
        with self._writable_connection() as c:
            row = c.execute(
                "SELECT * FROM supported_symbols WHERE symbol_code=?", (code,)
            ).fetchone()
            if row is None:
                raise PersistenceConflictError(f"Symbol {code} is not registered")
            if row["status"] != "disabled":
                c.execute(
                    "UPDATE supported_symbols SET status='disabled', updated_at=? "
                    "WHERE symbol_code=?",
                    (datetime.now(timezone.utc).isoformat(), code),
                )
            updated = c.execute(
                "SELECT * FROM supported_symbols WHERE symbol_code=?", (code,)
            ).fetchone()
        return dict(updated)

    def get_dataset_registry(self, symbol: str = None, tf: str = None) -> list[dict]:
        q = "SELECT * FROM dataset_registry WHERE 1=1"
        params = []
        if symbol:
            q += " AND symbol=?"; params.append(symbol)
        if tf:
            q += " AND timeframe=?"; params.append(tf)
        with self._connection() as c:
            rows = c.execute(q, params).fetchall()
        from forex.data.ohlc_contract import acquisition_metadata_dict

        decoded = []
        for row in rows:
            item = dict(row)
            item["acquisition_metadata"] = acquisition_metadata_dict(
                item.get("acquisition_metadata")
            )
            decoded.append(item)
        return decoded

    def upsert_dataset_registry(self, entry: dict) -> dict:
        from forex.data.ohlc_contract import encode_acquisition_metadata

        acquisition_metadata = encode_acquisition_metadata(
            entry.get("acquisition_metadata")
        )
        with self._writable_connection() as c:
            c.execute("""
                INSERT INTO dataset_registry (symbol, timeframe, candle_count, rolling_window_size,
                    last_candle_timestamp, blob_path, status, last_error, last_updated,
                    provider_used, external_ticker, provider_class, source_fetched_at,
                    source_sha256, acquisition_metadata, legacy_provenance_pending)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(symbol, timeframe) DO UPDATE SET
                    candle_count=excluded.candle_count,
                    rolling_window_size=excluded.rolling_window_size,
                    last_candle_timestamp=excluded.last_candle_timestamp,
                    blob_path=excluded.blob_path,
                    status=excluded.status,
                    last_error=excluded.last_error,
                    last_updated=excluded.last_updated,
                    provider_used=excluded.provider_used,
                    external_ticker=excluded.external_ticker,
                    provider_class=excluded.provider_class,
                    source_fetched_at=excluded.source_fetched_at,
                    source_sha256=excluded.source_sha256,
                    acquisition_metadata=excluded.acquisition_metadata,
                    legacy_provenance_pending=excluded.legacy_provenance_pending
            """, (
                entry["symbol"], entry["timeframe"], entry.get("candle_count", 0),
                entry.get("rolling_window_size", 2000), entry.get("last_candle_timestamp"),
                entry.get("blob_path"), entry.get("status", "ready"),
                entry.get("last_error"), datetime.now(timezone.utc).isoformat(),
                entry.get("provider_used"), entry.get("external_ticker"),
                entry.get("provider_class"), entry.get("source_fetched_at"),
                entry.get("source_sha256"),
                acquisition_metadata,
                0,
            ))
            row = c.execute("SELECT * FROM dataset_registry WHERE symbol=? AND timeframe=?",
                            (entry["symbol"], entry["timeframe"])).fetchone()
        result = dict(row)
        from forex.data.ohlc_contract import acquisition_metadata_dict

        result["acquisition_metadata"] = acquisition_metadata_dict(
            result.get("acquisition_metadata")
        )
        return result

    def save_prediction(self, pred: dict) -> dict:
        symbol = str(pred.get("symbol") or pred.get("pair") or "").upper().strip()
        timeframe = str(pred.get("timeframe") or "").upper().strip()
        action = str(pred.get("action") or pred.get("direction") or "").upper().strip()
        predicted_at = str(
            pred.get("predicted_at") or datetime.now(timezone.utc).isoformat()
        )
        candle_timestamp = str(
            pred.get("candle_timestamp") or predicted_at
        ).strip()
        prediction_id = pred.get("prediction_id") or stable_prediction_id(
            symbol, timeframe, candle_timestamp, action
        )
        status = pred.get("status") or (
            "PENDING" if action in ("BUY", "SELL") else "INELIGIBLE"
        )
        features_snapshot = json.dumps(pred.get("features_snapshot", {}), sort_keys=True)
        dataset_provenance = json.dumps(
            pred.get("dataset_provenance") or {}, sort_keys=True
        )
        immutable_evidence = {
            "symbol": symbol,
            "timeframe": timeframe,
            "action": action,
            "raw_action": pred.get("raw_action"),
            "confidence": pred.get("confidence", 0),
            "entry_price": pred.get("entry_price", 0),
            "stop_loss": pred.get("stop_loss", 0),
            "take_profit": pred.get("take_profit", 0),
            "features_snapshot": features_snapshot,
            "pipeline_version": pred.get("pipeline_version", _PIPELINE_VERSION),
            "predicted_at": predicted_at,
            "candle_timestamp": candle_timestamp,
            "horizon_candles": pred.get("horizon_candles"),
            "model_identity": pred.get("model_identity"),
            "dataset_provenance": dataset_provenance,
            "model_contract": pred.get("model_contract"),
            "target_profile": pred.get("target_profile"),
            "target_definition_version": pred.get("target_definition_version"),
            "feature_profile": pred.get("feature_profile"),
            "score_type": pred.get("score_type"),
            "direction_score": pred.get("direction_score"),
            "decision_percentile": pred.get("decision_percentile"),
            "decision_policy": pred.get("decision_policy"),
            "confidence_semantics": pred.get("confidence_semantics"),
        }
        with self._writable_connection() as c:
            c.execute("""
                INSERT INTO predictions (
                    prediction_id, symbol, timeframe, direction, action, raw_action,
                    confidence, entry_price, stop_loss, take_profit, features_snapshot,
                    pipeline_version, predicted_at, candle_timestamp, horizon_candles,
                    model_identity, dataset_provenance, model_contract, target_profile,
                    target_definition_version, feature_profile, score_type,
                    direction_score, decision_percentile, decision_policy,
                    confidence_semantics, status, resolved
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT DO NOTHING
            """, (
                prediction_id, symbol, timeframe, action, action,
                pred.get("raw_action"),
                pred.get("confidence", 0), pred.get("entry_price", 0),
                pred.get("stop_loss", 0), pred.get("take_profit", 0),
                features_snapshot,
                pred.get("pipeline_version", _PIPELINE_VERSION),
                predicted_at,
                candle_timestamp, pred.get("horizon_candles"),
                pred.get("model_identity"),
                dataset_provenance,
                pred.get("model_contract"), pred.get("target_profile"),
                pred.get("target_definition_version"), pred.get("feature_profile"),
                pred.get("score_type"), pred.get("direction_score"),
                pred.get("decision_percentile"), pred.get("decision_policy"),
                pred.get("confidence_semantics"),
                status, 0,
            ))
            row = c.execute(
                "SELECT * FROM predictions WHERE prediction_id=?", (prediction_id,)
            ).fetchone()
            if not row:
                raise RuntimeError("prediction upsert did not persist evidence")
            stored = dict(row)
            stored["action"] = stored["action"] or stored["direction"]
            float_fields = {
                "confidence", "entry_price", "stop_loss", "take_profit",
                "direction_score", "decision_percentile",
            }
            json_fields = {"features_snapshot", "dataset_provenance"}
            integer_fields = {"horizon_candles", "target_definition_version"}
            conflicts = []
            for field, expected in immutable_evidence.items():
                actual = stored.get(field)
                if field in float_fields:
                    matches = _float_evidence_equal(actual, expected)
                elif field in json_fields:
                    matches = _json_evidence_equal(actual, expected)
                elif field in integer_fields and actual is not None and expected is not None:
                    matches = int(actual) == int(expected)
                else:
                    matches = actual == expected
                if not matches:
                    conflicts.append(field)
            if conflicts:
                raise PersistenceConflictError(
                    f"conflicting prediction evidence for {prediction_id}: "
                    f"{', '.join(conflicts)}"
                )
        return stored

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
        prediction_id = str(outcome.get("prediction_id") or "").strip()
        if not prediction_id:
            raise ValueError("outcome requires source prediction_id")
        outcome_key = str(outcome.get("outcome_key") or prediction_id)
        status = str(outcome.get("status") or "FINALIZED").upper()
        if status != "FINALIZED" or outcome.get("result") not in ("win", "loss"):
            raise ValueError("operational outcome must be FINALIZED with win/loss result")
        try:
            entry_price = float(outcome["entry_price"])
            observed_price = float(outcome["observed_price"])
            observed_return = float(outcome["observed_return"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("finalized outcome requires observed price and return") from exc
        if (
            entry_price <= 0.0
            or observed_price <= 0.0
            or not math.isfinite(entry_price)
            or not math.isfinite(observed_price)
            or not math.isfinite(observed_return)
            or not outcome.get("prediction_timestamp")
            or not outcome.get("evaluation_timestamp")
        ):
            raise ValueError("finalized outcome evidence is incomplete or invalid")
        hit_tp = None if outcome.get("hit_tp", False) is None else int(
            outcome.get("hit_tp", False)
        )
        hit_sl = None if outcome.get("hit_sl", False) is None else int(
            outcome.get("hit_sl", False)
        )
        with self._writable_connection() as c:
            source = c.execute(
                "SELECT * FROM predictions WHERE prediction_id=?", (prediction_id,)
            ).fetchone()
            if not source:
                raise ValueError(f"source prediction does not exist: {prediction_id}")
            source_action = str(source["action"] or source["direction"] or "").upper()
            if source_action not in ("BUY", "SELL"):
                raise ValueError("non-operational predictions cannot have outcomes")
            requested_action = str(outcome.get("action") or "").upper()
            if requested_action != source_action:
                raise PersistenceConflictError(
                    f"outcome action conflicts with prediction {prediction_id}"
                )
            symbol = str(outcome.get("symbol") or "").upper()
            timeframe = str(outcome.get("timeframe") or "").upper()
            dataset_provenance = json.dumps(
                outcome.get("dataset_provenance") or {}, sort_keys=True
            )
            inherited_fields = (
                "horizon_candles", "model_contract", "target_profile",
                "target_definition_version", "feature_profile", "score_type",
                "direction_score", "decision_percentile", "decision_policy",
                "confidence_semantics",
            )
            for field in inherited_fields:
                if field in outcome and outcome.get(field) != source[field]:
                    raise PersistenceConflictError(
                        f"outcome {field} conflicts with prediction {prediction_id}"
                    )
            immutable_evidence = {
                "prediction_id": prediction_id,
                "outcome_key": outcome_key,
                "symbol": symbol,
                "timeframe": timeframe,
                "actual_direction": outcome.get("actual_direction"),
                "pnl_pips": outcome.get("pnl_pips", 0),
                "hit_tp": hit_tp,
                "hit_sl": hit_sl,
                "prediction_timestamp": outcome.get("prediction_timestamp"),
                "evaluation_timestamp": outcome.get("evaluation_timestamp"),
                "action": requested_action,
                "entry_price": entry_price,
                "observed_price": observed_price,
                "observed_return": observed_return,
                "result": outcome.get("result"),
                "model_identity": outcome.get("model_identity"),
                "dataset_provenance": dataset_provenance,
                **{field: source[field] for field in inherited_fields},
                "evaluation_semantics": outcome.get("evaluation_semantics"),
            }
            row = c.execute(
                "SELECT * FROM outcomes WHERE outcome_key=? OR prediction_id=?",
                (outcome_key, prediction_id),
            ).fetchone()
            if row is None:
                c.execute("""
                    INSERT INTO outcomes (
                        prediction_id, outcome_key, symbol, timeframe, actual_direction,
                        pnl_pips, hit_tp, hit_sl, resolved_at, prediction_timestamp,
                        evaluation_timestamp, action, entry_price, observed_price,
                        observed_return, result, status, model_identity, dataset_provenance,
                        horizon_candles, model_contract, target_profile,
                        target_definition_version, feature_profile, score_type,
                        direction_score, decision_percentile, decision_policy,
                        confidence_semantics, evaluation_semantics
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT DO NOTHING
                """, (
                    prediction_id, outcome_key, symbol, timeframe,
                    outcome.get("actual_direction"), outcome.get("pnl_pips", 0),
                    hit_tp, hit_sl,
                    outcome.get("resolved_at", datetime.now(timezone.utc).isoformat()),
                    outcome.get("prediction_timestamp"), outcome.get("evaluation_timestamp"),
                    requested_action, entry_price,
                    observed_price, observed_return,
                    outcome.get("result"), status,
                    outcome.get("model_identity"),
                    dataset_provenance,
                    *[source[field] for field in inherited_fields],
                    outcome.get("evaluation_semantics"),
                ))
                row = c.execute(
                    "SELECT * FROM outcomes WHERE outcome_key=? OR prediction_id=?",
                    (outcome_key, prediction_id),
                ).fetchone()
            if not row:
                raise RuntimeError("outcome upsert did not persist evidence")
            stored = dict(row)
            float_fields = {
                "pnl_pips", "entry_price", "observed_price", "observed_return",
                "direction_score", "decision_percentile",
            }
            json_fields = {"dataset_provenance"}
            integer_fields = {
                "hit_tp", "hit_sl", "horizon_candles",
                "target_definition_version",
            }
            conflicts = []
            for field, expected in immutable_evidence.items():
                actual = stored.get(field)
                if field == "prediction_id":
                    matches = str(actual) == expected
                elif field in float_fields:
                    matches = _float_evidence_equal(actual, expected)
                elif field in json_fields:
                    matches = _json_evidence_equal(actual, expected)
                elif field in integer_fields:
                    matches = (
                        actual is None and expected is None
                    ) or (
                        actual is not None
                        and expected is not None
                        and int(actual) == int(expected)
                    )
                else:
                    matches = actual == expected
                if not matches:
                    conflicts.append(field)
            if stored["status"] != status:
                conflicts.append("status")
            if conflicts:
                raise PersistenceConflictError(
                    f"conflicting outcome evidence for {prediction_id}: "
                    f"{', '.join(conflicts)}"
                )
            c.execute(
                "UPDATE predictions SET resolved=1, status='FINALIZED' "
                "WHERE prediction_id=?", (prediction_id,)
            )
        return stored

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

    def get_prediction(self, prediction_id: str) -> dict | None:
        with self._connection() as c:
            row = c.execute(
                "SELECT * FROM predictions WHERE prediction_id=?", (prediction_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_pending_predictions(self, symbol: str = None, limit: int = 100) -> list[dict]:
        query = (
            "SELECT * FROM predictions WHERE status='PENDING' "
            "AND action IN ('BUY','SELL')"
        )
        params: list = []
        if symbol:
            query += " AND symbol=?"
            params.append(symbol.upper())
        query += " ORDER BY id ASC LIMIT ?"
        params.append(limit)
        with self._connection() as c:
            rows = c.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_finalized_outcomes(
        self, symbol: str = None, timeframe: str = None, after_id: int = 0
    ) -> list[dict]:
        query = "SELECT * FROM outcomes WHERE status='FINALIZED' AND id>?"
        params: list = [after_id]
        if symbol:
            query += " AND symbol=?"
            params.append(symbol.upper())
        if timeframe:
            query += " AND timeframe=?"
            params.append(timeframe.upper())
        query += " ORDER BY id ASC"
        with self._connection() as c:
            rows = c.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_outcome_performance(self, symbol: str = None, timeframe: str = None) -> dict:
        query = (
            "SELECT COUNT(*), COALESCE(SUM(CASE WHEN result='win' THEN 1 ELSE 0 END),0), "
            "AVG(observed_return) FROM outcomes WHERE status='FINALIZED'"
        )
        params: list = []
        if symbol:
            query += " AND symbol=?"
            params.append(symbol.upper())
        if timeframe:
            query += " AND timeframe=?"
            params.append(timeframe.upper())
        with self._connection() as c:
            row = c.execute(query, params).fetchone()
        total, wins, average_return = row
        return {
            "evaluated": int(total),
            "correct": int(wins),
            "incorrect": int(total - wins),
            "win_rate": float(wins / total) if total else 0.0,
            "avg_return": float(average_return or 0.0),
        }

    def create_retrain_run(self, run: dict) -> dict:
        with self._writable_connection() as c:
            c.execute("""
                INSERT INTO retrain_runs (
                    run_id, evidence_key, request_id, symbol, timeframe, trigger, status,
                    source_model_path, source_model_sha256, dataset_provenance,
                    outcome_ids, last_outcome_id, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(evidence_key) DO NOTHING
            """, (
                run["run_id"], run["evidence_key"], run.get("request_id"),
                run["symbol"], run["timeframe"],
                run["trigger"], run.get("status", "PENDING"),
                run.get("source_model_path"), run.get("source_model_sha256"),
                json.dumps(run.get("dataset_provenance") or {}, sort_keys=True),
                json.dumps(run.get("outcome_ids") or []), run.get("last_outcome_id"),
                run["created_at"], run["updated_at"],
            ))
            row = c.execute(
                "SELECT * FROM retrain_runs WHERE evidence_key=?", (run["evidence_key"],)
            ).fetchone()
        return dict(row)

    def create_manual_quality_retrain_run(self, run: dict) -> dict:
        """Atomically enforce idempotency and one active run per symbol/H1."""
        trigger = "manual_quality_retrain"
        if run.get("trigger") != trigger or not run.get("request_id"):
            raise ValueError("manual quality retrain requires trigger and request_id")
        with self._writable_connection() as c:
            c.execute("BEGIN IMMEDIATE")
            existing_request = c.execute(
                """
                SELECT * FROM retrain_runs
                WHERE symbol=? AND timeframe=? AND trigger=? AND request_id=?
                ORDER BY created_at DESC LIMIT 1
                """,
                (
                    run["symbol"], run["timeframe"], trigger, run["request_id"],
                ),
            ).fetchone()
            if existing_request is not None:
                if existing_request["evidence_key"] != run["evidence_key"]:
                    raise PersistenceConflictError(
                        "manual quality retrain request_id conflicts with different evidence"
                    )
                return dict(existing_request)

            active = c.execute(
                """
                SELECT * FROM retrain_runs
                WHERE symbol=? AND timeframe=?
                  AND status IN ('PENDING','RUNNING','VALIDATED')
                ORDER BY created_at DESC LIMIT 1
                """,
                (run["symbol"], run["timeframe"]),
            ).fetchone()
            if active is not None:
                raise PersistenceConflictError(
                    "an active retrain already exists for symbol/timeframe: "
                    f"{active['run_id']}"
                )

            c.execute("""
                INSERT INTO retrain_runs (
                    run_id, evidence_key, request_id, symbol, timeframe, trigger,
                    status, source_model_path, source_model_sha256,
                    dataset_provenance, outcome_ids, last_outcome_id,
                    created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                run["run_id"], run["evidence_key"], run["request_id"],
                run["symbol"], run["timeframe"], run["trigger"],
                run.get("status", "PENDING"), run.get("source_model_path"),
                run.get("source_model_sha256"),
                json.dumps(run.get("dataset_provenance") or {}, sort_keys=True),
                json.dumps(run.get("outcome_ids") or []), run.get("last_outcome_id"),
                run["created_at"], run["updated_at"],
            ))
            row = c.execute(
                "SELECT * FROM retrain_runs WHERE run_id=?", (run["run_id"],)
            ).fetchone()
        return dict(row)

    def update_retrain_run(self, run_id: str, updates: dict) -> dict:
        allowed = {
            "status", "artifact_path", "artifact_sha256", "latest_path", "error",
            "updated_at", "validated_at", "promoted_at", "owner_token", "heartbeat_at",
        }
        invalid = set(updates) - allowed
        if invalid:
            raise ValueError(f"unsupported retrain fields: {sorted(invalid)}")
        if not updates:
            raise ValueError("retrain update cannot be empty")
        fields = ", ".join(f"{key}=?" for key in updates)
        with self._writable_connection() as c:
            c.execute(
                f"UPDATE retrain_runs SET {fields} WHERE run_id=?",
                [*updates.values(), run_id],
            )
            row = c.execute(
                "SELECT * FROM retrain_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if not row:
                raise KeyError(f"unknown retrain run {run_id}")
        return dict(row)

    def transition_interrupted_retrain_run(
        self,
        run_id: str,
        *,
        expected_heartbeat: str | None,
        status: str,
        error: str,
        transitioned_at: str,
    ) -> dict | None:
        """CAS a stale RUNNING retrain so a concurrent heartbeat wins safely."""
        if status not in {"PENDING", "FAILED"}:
            raise ValueError(f"invalid interrupted retrain transition: {status}")
        with self._writable_connection() as c:
            c.execute("""
                UPDATE retrain_runs
                SET status=?, owner_token=NULL, heartbeat_at=NULL, error=?, updated_at=?
                WHERE run_id=? AND status='RUNNING'
                  AND COALESCE(heartbeat_at, updated_at) IS ?
            """, (status, error, transitioned_at, run_id, expected_heartbeat))
            transitioned = c.execute("SELECT changes()").fetchone()[0] == 1
            row = c.execute(
                "SELECT * FROM retrain_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        if not row:
            raise KeyError(f"unknown retrain run {run_id}")
        return dict(row) if transitioned else None

    def claim_retrain_run(
        self, run_id: str, owner_token: str, claimed_at: str
    ) -> dict | None:
        """Atomically claim a pending run; only one process can win."""
        with self._writable_connection() as c:
            c.execute("""
                UPDATE retrain_runs
                SET status='RUNNING', owner_token=?, heartbeat_at=?, updated_at=?, error=NULL
                WHERE run_id=? AND status='PENDING'
            """, (owner_token, claimed_at, claimed_at, run_id))
            claimed = c.execute("SELECT changes()").fetchone()[0] == 1
            row = c.execute(
                "SELECT * FROM retrain_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        if not row:
            raise KeyError(f"unknown retrain run {run_id}")
        return dict(row) if claimed else None

    def get_retrain_runs(self, symbol: str = None, limit: int = 100) -> list[dict]:
        query = "SELECT * FROM retrain_runs"
        params: list = []
        if symbol:
            query += " WHERE symbol=?"
            params.append(symbol.upper())
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connection() as c:
            rows = c.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def finalize_model_promotion(self, run_id: str, provenance: dict) -> dict:
        """Atomically certify provenance and the corresponding retrain state."""
        provenance_status = provenance.get("status", "PROMOTED")
        if provenance_status not in {"PROMOTED", "INITIAL_TRAINING"}:
            raise ValueError(f"invalid model provenance status: {provenance_status}")
        with self._writable_connection() as c:
            run = c.execute(
                "SELECT * FROM retrain_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if not run:
                raise KeyError(f"unknown retrain run {run_id}")
            if run["status"] == "PROMOTED":
                existing = c.execute(
                    "SELECT * FROM model_provenance WHERE retrain_run_id=?", (run_id,)
                ).fetchone()
                if not existing:
                    raise PersistenceConflictError(
                        f"promoted run {run_id} has no model provenance"
                    )
                return dict(run)
            if run["status"] != "VALIDATED":
                raise PersistenceConflictError(
                    f"cannot promote retrain run {run_id} from {run['status']}"
                )
            c.execute("""
                INSERT INTO model_provenance (
                    model_id, retrain_run_id, trigger, symbol, timeframe, artifact_path,
                    artifact_sha256, source_model_path, source_model_sha256,
                    dataset_provenance, outcome_ids, trained_at, validated_at,
                    promoted_at, status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(retrain_run_id) DO NOTHING
            """, (
                provenance["model_id"], run_id, provenance.get("trigger"),
                provenance["symbol"],
                provenance["timeframe"], provenance["artifact_path"],
                provenance["artifact_sha256"], provenance.get("source_model_path"),
                provenance.get("source_model_sha256"),
                json.dumps(provenance["dataset_provenance"], sort_keys=True),
                json.dumps(provenance["outcome_ids"]), provenance["trained_at"],
                provenance["validated_at"], provenance["promoted_at"],
                provenance_status,
            ))
            stored = c.execute(
                "SELECT * FROM model_provenance WHERE retrain_run_id=?", (run_id,)
            ).fetchone()
            if (
                not stored
                or stored["artifact_sha256"] != provenance["artifact_sha256"]
                or stored["artifact_path"] != provenance["artifact_path"]
            ):
                raise PersistenceConflictError(
                    f"conflicting model provenance for {run_id}"
                )
            c.execute("""
                UPDATE retrain_runs
                SET status='PROMOTED', latest_path=?, promoted_at=?, updated_at=?, error=NULL
                WHERE run_id=? AND status='VALIDATED'
            """, (
                provenance["latest_path"], provenance["promoted_at"],
                provenance["promoted_at"], run_id,
            ))
            if c.execute("SELECT changes()").fetchone()[0] != 1:
                raise PersistenceConflictError(f"retrain promotion race for {run_id}")
            promoted_run = c.execute(
                "SELECT * FROM retrain_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        return dict(promoted_run)

    def get_model_provenance(self, symbol: str = None) -> list[dict]:
        query = "SELECT * FROM model_provenance"
        params: list = []
        if symbol:
            query += " WHERE symbol=?"
            params.append(symbol.upper())
        query += " ORDER BY promoted_at DESC"
        with self._connection() as c:
            rows = c.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def save_model_quality(self, mq: dict) -> dict:
        with self._writable_connection() as c:
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
        with self._writable_connection() as c:
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
        with self._writable_connection() as c:
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
    def get_active_symbols(self): raise NotImplementedError()
    def get_data_symbols(self): raise NotImplementedError()
    def add_symbol(self, code, name, pip): raise NotImplementedError()
    def get_symbol(self, code): raise NotImplementedError()
    def get_symbols_by_status(self, status): raise NotImplementedError()
    def register_candidate(self, code, name, asset_class, pip): raise NotImplementedError()
    def mark_qualified(self, code, evidence): raise NotImplementedError()
    def _persist_authorized_activation(self, authorization): raise NotImplementedError()
    def disable_symbol(self, code): raise NotImplementedError()
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

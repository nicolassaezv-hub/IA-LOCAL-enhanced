from __future__ import annotations

import hashlib
import json
import socket
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from forex.data.symbol_catalog import get_symbol_spec
from infra.db.database import PersistenceConflictError, SQLiteDatabase
from runtime_paths import forex_dataset_path, forex_model_root
from scripts import migrate_oracle_legacy_forex as migration


pytestmark = pytest.mark.unit

SYMBOLS = ("EURUSD", "USDJPY", "GBPUSD", "AUDUSD")
TIMEFRAMES = ("H1", "H4", "D1")
FIXED_NOW = datetime(2026, 9, 2, 17, 30, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _insert_symbol(
    database: SQLiteDatabase,
    symbol: str,
    *,
    status: str = "active",
    activation_origin: str = "legacy",
    evidence_path: str | None = None,
) -> None:
    spec = get_symbol_spec(symbol)
    with sqlite3.connect(database.db_path) as connection:
        connection.execute(
            "INSERT INTO supported_symbols "
            "(symbol_code,display_name,asset_class,pip_value,status,added_at,"
            "updated_at,qualification_evidence_path,qualification_sha256,"
            "qualified_at,qualification_catalog_version,activation_origin) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                symbol,
                spec.display_name,
                spec.asset_class,
                spec.pip_value,
                status,
                "2025-01-01T00:00:00+00:00",
                "2025-01-02T00:00:00+00:00",
                evidence_path,
                "evidence-sha" if evidence_path else None,
                "2025-01-02T00:00:00+00:00" if evidence_path else None,
                "legacy-catalog" if evidence_path else None,
                activation_origin,
            ),
        )


def _legacy_state(tmp_path: Path, monkeypatch):
    database = SQLiteDatabase(str(tmp_path / "astra.db"))
    for symbol in SYMBOLS:
        _insert_symbol(database, symbol)

    dataset_bytes = {}
    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            path = forex_dataset_path(symbol, timeframe, project_root=tmp_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            content = f"legacy-yahoo,{symbol},{timeframe}\n".encode("utf-8")
            path.write_bytes(content)
            dataset_bytes[(symbol, timeframe)] = content
            database.upsert_dataset_registry({
                "symbol": symbol,
                "timeframe": timeframe,
                "candle_count": 2000,
                "rolling_window_size": 2000,
                "last_candle_timestamp": "2026-08-31T20:00:00+00:00",
                "blob_path": str(path.resolve()),
                "status": "ready",
                "last_error": None,
                "provider_used": "Yahoo",
                "external_ticker": f"{symbol}=X",
                "provider_class": "FX_REFERENCE",
                "source_fetched_at": "2026-08-31T20:05:00+00:00",
                "source_sha256": _sha256(path),
                "acquisition_metadata": {"provider": "Yahoo"},
            })

    alias_bytes = {}
    model_root = forex_model_root(tmp_path)
    model_root.mkdir(parents=True, exist_ok=True)
    for symbol in ("EURUSD", "USDJPY", "AUDUSD"):
        path = model_root / f"latest_{symbol}.pkl"
        content = f"legacy-model-{symbol}".encode("utf-8")
        path.write_bytes(content)
        alias_bytes[symbol] = content
    monkeypatch.setattr(
        migration,
        "EXPECTED_ALIAS_SHA256",
        {
            symbol: hashlib.sha256(content).hexdigest()
            for symbol, content in alias_bytes.items()
        },
    )
    monkeypatch.setenv("ASTRA_SCHEDULER_ENABLED", "false")
    return database, dataset_bytes, alias_bytes


def _database_snapshot(database: SQLiteDatabase) -> dict:
    return {
        "symbols": {
            row["symbol_code"]: row for row in database.get_symbols_by_status("active")
        },
        "registry": {
            f"{row['symbol']}:{row['timeframe']}": row
            for row in database.get_dataset_registry()
        },
    }


def _apply(database: SQLiteDatabase, tmp_path: Path) -> dict:
    return migration.run_migration(
        database=database,
        project_root=tmp_path,
        apply=True,
        now=FIXED_NOW,
        source_git_sha="a" * 40,
    )


def test_dry_run_is_default_and_changes_no_database_or_files(tmp_path, monkeypatch):
    database, dataset_bytes, alias_bytes = _legacy_state(tmp_path, monkeypatch)
    before = _database_snapshot(database)

    result = migration.run_migration(
        database=database,
        project_root=tmp_path,
        now=FIXED_NOW,
        source_git_sha="a" * 40,
    )

    assert result["mode"] == "DRY_RUN"
    assert result["result"] == "DRY_RUN"
    assert _database_snapshot(database) == before
    assert not (tmp_path / "reports").exists()
    for (symbol, timeframe), content in dataset_bytes.items():
        assert forex_dataset_path(symbol, timeframe, project_root=tmp_path).read_bytes() == content
    for symbol, content in alias_bytes.items():
        assert (forex_model_root(tmp_path) / f"latest_{symbol}.pkl").read_bytes() == content


def test_apply_rejects_enabled_scheduler_before_mutation(tmp_path, monkeypatch):
    database, _, _ = _legacy_state(tmp_path, monkeypatch)
    before = _database_snapshot(database)
    monkeypatch.setenv("ASTRA_SCHEDULER_ENABLED", "true")

    with pytest.raises(PersistenceConflictError, match="SCHEDULER_MUST_BE_DISABLED"):
        _apply(database, tmp_path)

    assert _database_snapshot(database) == before
    assert not (tmp_path / "reports").exists()


def test_explicit_legacy_active_transition_returns_candidate(tmp_path):
    database = SQLiteDatabase(str(tmp_path / "transition.db"))
    _insert_symbol(database, "EURUSD")
    before = database.get_symbol("EURUSD")

    after = database.migrate_legacy_active_to_candidate("EURUSD")

    assert after["status"] == "candidate"
    assert after["activation_origin"] == "legacy"
    for field in (
        "qualification_evidence_path",
        "qualification_sha256",
        "qualified_at",
        "qualification_catalog_version",
    ):
        assert after[field] is None
    for field in (
        "symbol_code", "display_name", "asset_class", "pip_value", "added_at"
    ):
        assert after[field] == before[field]
    assert after["updated_at"] != before["updated_at"]


@pytest.mark.parametrize(
    ("setup", "message"),
    [
        ("missing", "not registered"),
        ("managed", "activation_origin"),
        ("evidence", "qualification evidence"),
        ("candidate", "status candidate"),
    ],
)
def test_explicit_legacy_active_transition_rejects_invalid_state(
    tmp_path, setup, message
):
    database = SQLiteDatabase(str(tmp_path / f"{setup}.db"))
    if setup != "missing":
        _insert_symbol(
            database,
            "EURUSD",
            status="candidate" if setup == "candidate" else "active",
            activation_origin="managed" if setup == "managed" else "legacy",
            evidence_path="/evidence.json" if setup == "evidence" else None,
        )

    with pytest.raises(PersistenceConflictError, match=message):
        database.migrate_legacy_active_to_candidate("EURUSD")


def test_apply_sets_exact_lifecycle_targets_and_leaves_modern_candidate_untouched(
    tmp_path, monkeypatch
):
    database, _, _ = _legacy_state(tmp_path, monkeypatch)
    spec = get_symbol_spec("NZDUSD")
    modern = database.register_candidate(
        spec.symbol_code, spec.display_name, spec.asset_class, spec.pip_value
    )

    result = _apply(database, tmp_path)

    assert result["result"] == "SUCCESS"
    assert database.get_symbol("EURUSD")["status"] == "candidate"
    assert database.get_symbol("USDJPY")["status"] == "candidate"
    assert database.get_symbol("GBPUSD")["status"] == "disabled"
    assert database.get_symbol("AUDUSD")["status"] == "disabled"
    assert database.get_active_symbols() == []
    assert database.get_symbol("NZDUSD") == modern
    assert all(
        database.get_symbol(symbol)["qualification_evidence_path"] is None
        for symbol in ("EURUSD", "USDJPY")
    )


def test_apply_quarantines_only_expected_aliases_with_identical_hashes(
    tmp_path, monkeypatch
):
    database, _, alias_bytes = _legacy_state(tmp_path, monkeypatch)
    immutable = forex_model_root(tmp_path) / "ensemble_EURUSD_legacy.pkl"
    immutable.write_bytes(b"immutable-evidence")

    result = _apply(database, tmp_path)

    assert result["aliases_quarantined"] == ["EURUSD", "USDJPY", "AUDUSD"]
    for symbol, content in alias_bytes.items():
        original = forex_model_root(tmp_path) / f"latest_{symbol}.pkl"
        assert not original.exists()
        record = next(
            item for item in result["files"]
            if item["kind"] == "alias" and item["symbol"] == symbol
        )
        quarantine = Path(record["quarantine_path"])
        assert quarantine.read_bytes() == content
        assert record["sha256_before"] == record["sha256_after"] == _sha256(quarantine)
    assert not (forex_model_root(tmp_path) / "latest_GBPUSD.pkl").exists()
    assert immutable.read_bytes() == b"immutable-evidence"


def test_unexpected_gbpusd_alias_fails_closed_before_any_change(tmp_path, monkeypatch):
    database, _, _ = _legacy_state(tmp_path, monkeypatch)
    unexpected = forex_model_root(tmp_path) / "latest_GBPUSD.pkl"
    unexpected.write_bytes(b"unexpected")
    before = _database_snapshot(database)

    with pytest.raises(PersistenceConflictError, match="UNEXPECTED_GBPUSD_ALIAS"):
        _apply(database, tmp_path)

    assert _database_snapshot(database) == before
    assert unexpected.read_bytes() == b"unexpected"
    assert not (tmp_path / "reports").exists()


def test_yahoo_datasets_are_byte_preserved_and_registry_is_quarantined(
    tmp_path, monkeypatch
):
    database, dataset_bytes, _ = _legacy_state(tmp_path, monkeypatch)

    result = _apply(database, tmp_path)

    dataset_records = [item for item in result["files"] if item["kind"] == "dataset"]
    assert len(dataset_records) == 12
    for record in dataset_records:
        key = (record["symbol"], record["timeframe"])
        original = Path(record["original_path"])
        quarantined = Path(record["quarantine_path"])
        assert not original.exists()
        assert quarantined.read_bytes() == dataset_bytes[key]
        assert record["provider_historical"] == "Yahoo"
        assert record["sha256_before"] == record["sha256_after"]

        row = database.get_dataset_registry(*key)[0]
        assert row["status"] == "quarantined"
        assert row["blob_path"] == str(quarantined.resolve())
        assert row["last_error"] == migration.LEGACY_QUARANTINE_CLASSIFICATION
        assert row["provider_used"] == "Yahoo"
        assert row["provider_class"] == "FX_REFERENCE"
        assert row["source_sha256"] == record["sha256_before"]
        assert row["external_ticker"] == f"{key[0]}=X"


def test_apply_manifest_is_complete_durable_and_secret_free(tmp_path, monkeypatch):
    database, _, _ = _legacy_state(tmp_path, monkeypatch)
    monkeypatch.setenv("ASTRA_API_KEY", "DO_NOT_RECORD_THIS_SECRET")

    result = _apply(database, tmp_path)
    manifest_path = Path(result["manifest_path"])
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert persisted == {key: value for key, value in result.items() if key != "manifest_path"}
    assert persisted["schema_version"] == 1
    assert persisted["source_git_sha"] == "a" * 40
    assert persisted["mode"] == "APPLY"
    assert persisted["phase"] == "VERIFY"
    assert persisted["result"] == "SUCCESS"
    assert persisted["errors"] == []
    assert set(persisted["symbol_before"]) == set(SYMBOLS)
    assert set(persisted["symbol_after"]) == set(SYMBOLS)
    assert len(persisted["dataset_before"]) == 12
    assert len(persisted["dataset_after"]) == 12
    assert len(persisted["files"]) == 15
    assert "DO_NOT_RECORD_THIS_SECRET" not in manifest_path.read_text(encoding="utf-8")


def test_rollback_restores_exact_prestate_and_all_file_bytes(tmp_path, monkeypatch):
    database, dataset_bytes, alias_bytes = _legacy_state(tmp_path, monkeypatch)
    before = _database_snapshot(database)
    applied = _apply(database, tmp_path)

    rolled_back = migration.rollback_migration(
        database=database,
        manifest_path=Path(applied["manifest_path"]),
        project_root=tmp_path,
        now=FIXED_NOW,
        source_git_sha="a" * 40,
    )

    assert rolled_back["result"] == "ROLLED_BACK"
    assert _database_snapshot(database) == before
    for (symbol, timeframe), content in dataset_bytes.items():
        assert forex_dataset_path(symbol, timeframe, project_root=tmp_path).read_bytes() == content
    for symbol, content in alias_bytes.items():
        assert (forex_model_root(tmp_path) / f"latest_{symbol}.pkl").read_bytes() == content
    assert all(not Path(item["quarantine_path"]).exists() for item in applied["files"])


def test_rollback_rejects_new_file_conflict_without_overwrite(tmp_path, monkeypatch):
    database, _, _ = _legacy_state(tmp_path, monkeypatch)
    applied = _apply(database, tmp_path)
    original = forex_model_root(tmp_path) / "latest_EURUSD.pkl"
    original.write_bytes(b"new-production-evidence")

    with pytest.raises(PersistenceConflictError, match="ROLLBACK_FILE_CONFLICT"):
        migration.rollback_migration(
            database=database,
            manifest_path=Path(applied["manifest_path"]),
            project_root=tmp_path,
            now=FIXED_NOW,
            source_git_sha="a" * 40,
        )

    assert original.read_bytes() == b"new-production-evidence"
    record = next(
        item for item in applied["files"]
        if item["kind"] == "alias" and item["symbol"] == "EURUSD"
    )
    assert Path(record["quarantine_path"]).is_file()
    assert database.get_active_symbols() == []


def test_rollback_rejects_database_conflict_before_moving_files(tmp_path, monkeypatch):
    database, _, _ = _legacy_state(tmp_path, monkeypatch)
    applied = _apply(database, tmp_path)
    database.disable_symbol("EURUSD")

    with pytest.raises(PersistenceConflictError, match="ROLLBACK_DATABASE_CONFLICT"):
        migration.rollback_migration(
            database=database,
            manifest_path=Path(applied["manifest_path"]),
            project_root=tmp_path,
            now=FIXED_NOW,
            source_git_sha="a" * 40,
        )

    assert all(Path(item["quarantine_path"]).is_file() for item in applied["files"])


def test_apply_failure_rolls_back_files_and_database(tmp_path, monkeypatch):
    database, dataset_bytes, alias_bytes = _legacy_state(tmp_path, monkeypatch)
    before = _database_snapshot(database)
    real_disable = database.disable_symbol

    def fail_second_disable(symbol, **kwargs):
        if symbol == "AUDUSD":
            raise RuntimeError("injected DB failure")
        return real_disable(symbol, **kwargs)

    monkeypatch.setattr(database, "disable_symbol", fail_second_disable)
    with pytest.raises(RuntimeError, match="injected DB failure"):
        _apply(database, tmp_path)

    assert _database_snapshot(database) == before
    for (symbol, timeframe), content in dataset_bytes.items():
        assert forex_dataset_path(symbol, timeframe, project_root=tmp_path).read_bytes() == content
    for symbol, content in alias_bytes.items():
        assert (forex_model_root(tmp_path) / f"latest_{symbol}.pkl").read_bytes() == content


def test_migration_performs_no_network_or_productive_actions(tmp_path, monkeypatch):
    database, _, _ = _legacy_state(tmp_path, monkeypatch)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    result = _apply(database, tmp_path)

    assert result["result"] == "SUCCESS"
    with sqlite3.connect(database.db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM model_quality").fetchone()[0] == 0
    source = Path(migration.__file__).read_text(encoding="utf-8")
    assert "DataRouter" not in source
    assert "train_model" not in source
    assert "activate_qualified_symbol" not in source
    assert "save_prediction" not in source
    assert "save_outcome" not in source


def test_cli_defaults_to_dry_run_and_rollback_is_mutually_exclusive():
    args = migration.parse_args([])
    assert args.apply is False
    assert args.rollback is None
    with pytest.raises(SystemExit):
        migration.parse_args(["--apply", "--rollback", "manifest.json"])

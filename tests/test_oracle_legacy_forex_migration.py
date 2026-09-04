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
    (tmp_path / "memory_db").mkdir(parents=True, exist_ok=True)
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
    monkeypatch.setenv("ASTRA_HOME", str(tmp_path.resolve()))
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
    before_paths = {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
    }

    result = migration.run_migration(
        database=database,
        project_root=tmp_path,
        now=FIXED_NOW,
        source_git_sha="a" * 40,
    )

    assert result["mode"] == "DRY_RUN"
    assert result["result"] == "DRY_RUN"
    assert _database_snapshot(database) == before
    assert {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
    } == before_paths
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
    assert persisted["runtime_project_root"] == str(tmp_path.resolve())
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
    assert rolled_back["runtime_project_root"] == str(tmp_path.resolve())
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


def test_explicit_runtime_without_git_uses_only_runtime_root_and_skips_git(
    tmp_path, monkeypatch
):
    runtime_root = tmp_path / "opt" / "astra"
    database, _, _ = _legacy_state(runtime_root, monkeypatch)
    assert not (runtime_root / ".git").exists()

    def forbidden_git(*_args, **_kwargs):
        raise AssertionError("git must not run for an explicit source SHA")

    monkeypatch.setattr(migration.subprocess, "run", forbidden_git)
    result = migration.run_migration(
        database=database,
        project_root=runtime_root,
        source_git_sha="A" * 40,
        now=FIXED_NOW,
    )

    assert result["runtime_project_root"] == str(runtime_root.resolve())
    assert result["source_git_sha"] == "a" * 40
    assert all(
        Path(record["original_path"]).is_relative_to(runtime_root.resolve())
        for record in result["files"]
    )


@pytest.mark.parametrize(
    "source_sha",
    ["", "a" * 39, "a" * 41, "g" * 40, "abc-not-a-git-sha"],
)
def test_malformed_explicit_source_sha_is_rejected_without_git(
    tmp_path, monkeypatch, source_sha
):
    database, _, _ = _legacy_state(tmp_path, monkeypatch)
    monkeypatch.setattr(
        migration.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("git must not run")
        ),
    )

    with pytest.raises(PersistenceConflictError, match="SOURCE_GIT_SHA_INVALID"):
        migration.run_migration(
            database=database,
            project_root=tmp_path,
            source_git_sha=source_sha,
            now=FIXED_NOW,
        )


def test_nonexistent_runtime_project_root_is_rejected(tmp_path, monkeypatch):
    valid_root = tmp_path / "valid"
    database, _, _ = _legacy_state(valid_root, monkeypatch)
    missing = tmp_path / "does-not-exist"
    monkeypatch.setenv("ASTRA_HOME", str(missing))

    with pytest.raises(
        PersistenceConflictError, match="RUNTIME_PROJECT_ROOT_NOT_FOUND"
    ):
        migration.run_migration(
            database=database,
            project_root=missing,
            source_git_sha="a" * 40,
            now=FIXED_NOW,
        )
    assert not missing.exists()


@pytest.mark.parametrize("missing_relative", ["data/forex", "models/forex", "memory_db"])
def test_runtime_project_root_requires_existing_structures(
    tmp_path, monkeypatch, missing_relative
):
    root = tmp_path / "runtime"
    for relative in ("data/forex", "models/forex", "memory_db"):
        if relative != missing_relative:
            (root / relative).mkdir(parents=True, exist_ok=True)
    database = SQLiteDatabase(str(tmp_path / "outside.db"))
    monkeypatch.setenv("ASTRA_HOME", str(root.resolve()))

    with pytest.raises(
        PersistenceConflictError, match="RUNTIME_PROJECT_STRUCTURE_MISSING"
    ):
        migration.run_migration(
            database=database,
            project_root=root,
            source_git_sha="a" * 40,
            now=FIXED_NOW,
        )


def test_astra_home_runtime_root_mismatch_fails_closed(tmp_path, monkeypatch):
    runtime_root = tmp_path / "runtime"
    database, _, _ = _legacy_state(runtime_root, monkeypatch)
    other_home = tmp_path / "other-astra"
    for relative in ("data/forex", "models/forex", "memory_db"):
        (other_home / relative).mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ASTRA_HOME", str(other_home.resolve()))

    with pytest.raises(PersistenceConflictError, match="ASTRA_HOME_ROOT_MISMATCH"):
        migration.run_migration(
            database=database,
            project_root=runtime_root,
            source_git_sha="a" * 40,
            now=FIXED_NOW,
        )


def test_apply_binds_datasets_models_quarantine_and_manifest_to_runtime_root(
    tmp_path, monkeypatch
):
    runtime_root = tmp_path / "deployed-runtime"
    database, _, _ = _legacy_state(runtime_root, monkeypatch)

    result = _apply(database, runtime_root)

    root = runtime_root.resolve()
    assert result["runtime_project_root"] == str(root)
    assert Path(result["manifest_path"]).is_relative_to(
        root / "reports" / "deployment"
    )
    for record in result["files"]:
        original = Path(record["original_path"])
        quarantine = Path(record["quarantine_path"])
        assert original.is_relative_to(root)
        assert quarantine.is_relative_to(root)
        if record["kind"] == "alias":
            assert original.is_relative_to(root / "models" / "forex")
            assert quarantine.is_relative_to(
                root / "models" / "forex" / "legacy_quarantine"
            )
        else:
            assert original.is_relative_to(root / "data" / "forex")
            assert quarantine.is_relative_to(root / "data" / "forex_legacy_quarantine")


def test_rollback_rejects_different_runtime_root_before_file_changes(
    tmp_path, monkeypatch
):
    runtime_root = tmp_path / "runtime-a"
    database, _, _ = _legacy_state(runtime_root, monkeypatch)
    applied = _apply(database, runtime_root)
    other_root = tmp_path / "runtime-b"
    for relative in ("data/forex", "models/forex", "memory_db"):
        (other_root / relative).mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ASTRA_HOME", str(other_root.resolve()))
    quarantined_before = {
        record["quarantine_path"]: _sha256(Path(record["quarantine_path"]))
        for record in applied["files"]
    }

    with pytest.raises(
        PersistenceConflictError, match="ROLLBACK_RUNTIME_ROOT_MISMATCH"
    ):
        migration.rollback_migration(
            database=database,
            manifest_path=Path(applied["manifest_path"]),
            project_root=other_root,
            source_git_sha="a" * 40,
            now=FIXED_NOW,
        )

    assert {
        path: _sha256(Path(path)) for path in quarantined_before
    } == quarantined_before
    assert database.get_active_symbols() == []


def test_cli_requires_runtime_root_and_accepts_explicit_source_sha():
    with pytest.raises(SystemExit):
        migration.parse_args([])
    args = migration.parse_args([
        "--project-root", "/opt/astra",
        "--source-git-sha", "A" * 40,
    ])
    assert args.apply is False
    assert args.rollback is None
    assert args.project_root == Path("/opt/astra")
    assert args.source_git_sha == "A" * 40
    with pytest.raises(SystemExit):
        migration.parse_args([
            "--project-root", "/opt/astra",
            "--apply",
            "--rollback", "manifest.json",
        ])

#!/usr/bin/env python3
"""Reversibly retire the exact legacy Oracle Forex production state.

The command is a dry-run unless ``--apply`` is supplied. It never acquires
market data, trains models, activates symbols, predicts, or trades.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOURCE_CHECKOUT_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_CHECKOUT_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_CHECKOUT_ROOT))

from forex.data.symbol_lifecycle import (  # noqa: E402
    disable_symbol,
    migrate_legacy_active_to_candidate,
)
from infra.db.database import (  # noqa: E402
    DatabaseAdapter,
    LEGACY_DATASET_QUARANTINE_CLASSIFICATION,
    PersistenceConflictError,
    get_database,
)
from runtime_paths import forex_dataset_path, forex_model_root  # noqa: E402


SCHEMA_VERSION = 1
TARGET_STATES = {
    "EURUSD": "candidate",
    "USDJPY": "candidate",
    "GBPUSD": "disabled",
    "AUDUSD": "disabled",
}
SYMBOLS = tuple(TARGET_STATES)
TIMEFRAMES = ("H1", "H4", "D1")
EXPECTED_ALIAS_SHA256 = {
    "EURUSD": "3bd389608a83fc4e2aa0ec2c1d5328e4deb1c3bd17f0530f6ebb40e8de13faa0",
    "USDJPY": "eebab3bc322b6deab1ddbf6fe2e16784a8877379fb2a693d7fdc477a8b24c3a7",
    "AUDUSD": "7482167aeced687c2375ce3c2b998e421047d46146deef2ce5b71f3743c5aa53",
}
LEGACY_QUARANTINE_CLASSIFICATION = LEGACY_DATASET_QUARANTINE_CLASSIFICATION
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_MIGRATION_ID = re.compile(r"^oracle-legacy-forex-[0-9]{8}T[0-9]{12}Z$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _timestamp(now: datetime | None) -> datetime:
    value = datetime.now(timezone.utc) if now is None else now
    if value.tzinfo is None:
        raise PersistenceConflictError("MIGRATION_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return value.astimezone(timezone.utc)


def _migration_id(now: datetime) -> str:
    return "oracle-legacy-forex-" + now.strftime("%Y%m%dT%H%M%S%fZ")


def _source_git_sha(explicit: str | None) -> str:
    if explicit is not None:
        value = str(explicit).strip().lower()
    else:
        if not (SOURCE_CHECKOUT_ROOT / ".git").exists():
            raise PersistenceConflictError("SOURCE_GIT_CHECKOUT_UNAVAILABLE")
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=SOURCE_CHECKOUT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        value = completed.stdout.strip().lower()
    if _GIT_SHA.fullmatch(value) is None:
        raise PersistenceConflictError("SOURCE_GIT_SHA_INVALID")
    return value


def _resolve_runtime_project_root(project_root: Path | str) -> Path:
    raw_root = Path(project_root).expanduser()
    try:
        root = raw_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PersistenceConflictError("RUNTIME_PROJECT_ROOT_NOT_FOUND") from exc
    if not root.is_dir():
        raise PersistenceConflictError("RUNTIME_PROJECT_ROOT_NOT_FOUND")

    required = (
        root / "data" / "forex",
        root / "models" / "forex",
        root / "memory_db",
    )
    missing = [str(path) for path in required if not path.is_dir()]
    if missing:
        raise PersistenceConflictError("RUNTIME_PROJECT_STRUCTURE_MISSING")

    configured_home = os.environ.get("ASTRA_HOME")
    if configured_home:
        home_path = Path(configured_home).expanduser()
        if not home_path.is_absolute():
            raise PersistenceConflictError("ASTRA_HOME_INVALID")
        configured_root = home_path.resolve()
        if configured_root != root:
            raise PersistenceConflictError("ASTRA_HOME_ROOT_MISMATCH")
    return root


def _scheduler_is_disabled() -> bool:
    value = os.environ.get("ASTRA_SCHEDULER_ENABLED")
    return value is not None and value.strip().lower() in _FALSE_VALUES


def _require_scheduler_disabled() -> None:
    if not _scheduler_is_disabled():
        raise PersistenceConflictError("SCHEDULER_MUST_BE_DISABLED")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _public_result(manifest: dict[str, Any], manifest_path: Path | None) -> dict:
    result = json.loads(json.dumps(manifest))
    if manifest_path is not None:
        result["manifest_path"] = str(manifest_path.resolve())
    return result


def _is_qualification_absent(row: dict) -> bool:
    return all(
        row.get(field) is None
        for field in (
            "qualification_evidence_path",
            "qualification_sha256",
            "qualified_at",
            "qualification_catalog_version",
        )
    )


def _require_legacy_active(row: dict | None, symbol: str) -> dict:
    if row is None:
        raise PersistenceConflictError(f"LEGACY_SYMBOL_MISSING: {symbol}")
    if row.get("status") != "active":
        raise PersistenceConflictError(
            f"LEGACY_SYMBOL_STATUS_INVALID: {symbol} status={row.get('status')}"
        )
    if row.get("activation_origin") != "legacy":
        raise PersistenceConflictError(
            f"LEGACY_SYMBOL_ORIGIN_INVALID: {symbol} activation_origin="
            f"{row.get('activation_origin')}"
        )
    if not _is_qualification_absent(row):
        raise PersistenceConflictError(
            f"LEGACY_SYMBOL_QUALIFICATION_PRESENT: {symbol}"
        )
    return row


def _file_record(
    *,
    kind: str,
    symbol: str,
    original: Path,
    quarantine: Path,
    timeframe: str | None = None,
    provider_historical: str | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    if original.is_symlink() or not original.is_file():
        raise PersistenceConflictError(
            f"MIGRATION_SOURCE_FILE_INVALID: {kind} {symbol} {timeframe or ''}".strip()
        )
    if quarantine.exists() or quarantine.is_symlink():
        raise PersistenceConflictError(
            f"MIGRATION_QUARANTINE_CONFLICT: {quarantine}"
        )
    digest = _sha256_file(original)
    if expected_sha256 is not None and digest != expected_sha256:
        raise PersistenceConflictError(
            f"MIGRATION_SOURCE_SHA256_MISMATCH: {kind} {symbol} "
            f"{timeframe or ''}".strip()
        )
    record: dict[str, Any] = {
        "kind": kind,
        "symbol": symbol,
        "original_path": str(original.resolve()),
        "quarantine_path": str(quarantine.resolve()),
        "bytes": original.stat().st_size,
        "sha256_before": digest,
        "sha256_after": None,
        "moved": False,
    }
    if timeframe is not None:
        record["timeframe"] = timeframe
    if provider_historical is not None:
        record["provider_historical"] = provider_historical
    return record


def _build_manifest(
    database: DatabaseAdapter,
    project_root: Path,
    *,
    mode: str,
    now: datetime,
    source_git_sha: str,
) -> dict[str, Any]:
    migration_id = _migration_id(now)
    model_root = forex_model_root(project_root).resolve()
    model_quarantine = model_root / "legacy_quarantine" / migration_id
    data_quarantine = (
        project_root.resolve() / "data" / "forex_legacy_quarantine" / migration_id
    )

    active_codes = {
        str(row.get("symbol_code") or "").upper()
        for row in database.get_active_symbols()
    }
    if active_codes != set(SYMBOLS):
        raise PersistenceConflictError(
            "ACTIVE_SYMBOL_SCOPE_MISMATCH: expected exact Oracle legacy set"
        )

    symbol_before = {
        symbol: _require_legacy_active(database.get_symbol(symbol), symbol)
        for symbol in SYMBOLS
    }
    files = []
    for symbol, expected_sha256 in EXPECTED_ALIAS_SHA256.items():
        original = model_root / f"latest_{symbol}.pkl"
        files.append(_file_record(
            kind="alias",
            symbol=symbol,
            original=original,
            quarantine=model_quarantine / original.name,
            expected_sha256=expected_sha256,
        ))
    unexpected_gbpusd = model_root / "latest_GBPUSD.pkl"
    if unexpected_gbpusd.exists() or unexpected_gbpusd.is_symlink():
        raise PersistenceConflictError("UNEXPECTED_GBPUSD_ALIAS")

    dataset_before: dict[str, dict] = {}
    for symbol in SYMBOLS:
        rows = database.get_dataset_registry(symbol)
        by_timeframe = {str(row.get("timeframe") or "").upper(): row for row in rows}
        if len(rows) != len(TIMEFRAMES) or set(by_timeframe) != set(TIMEFRAMES):
            raise PersistenceConflictError(
                f"LEGACY_DATASET_SCOPE_INVALID: {symbol} requires exact H1/H4/D1"
            )
        for timeframe in TIMEFRAMES:
            row = by_timeframe[timeframe]
            key = f"{symbol}:{timeframe}"
            original = forex_dataset_path(
                symbol, timeframe, project_root=project_root
            ).resolve()
            if (
                row.get("status") != "ready"
                or row.get("provider_used") != "Yahoo"
                or row.get("provider_class") != "FX_REFERENCE"
                or not row.get("external_ticker")
                or not row.get("source_fetched_at")
                or _SHA256.fullmatch(str(row.get("source_sha256") or "")) is None
                or Path(str(row.get("blob_path") or "")).expanduser().resolve()
                != original
            ):
                raise PersistenceConflictError(
                    f"LEGACY_DATASET_REGISTRY_INVALID: {key}"
                )
            record = _file_record(
                kind="dataset",
                symbol=symbol,
                timeframe=timeframe,
                original=original,
                quarantine=data_quarantine / original.name,
                provider_historical="Yahoo",
                expected_sha256=str(row["source_sha256"]),
            )
            files.append(record)
            dataset_before[key] = row

    return {
        "schema_version": SCHEMA_VERSION,
        "migration_id": migration_id,
        "timestamp": now.isoformat(),
        "runtime_project_root": str(project_root.resolve()),
        "source_git_sha": source_git_sha,
        "mode": mode,
        "phase": "PRECHECK",
        "preconditions": {
            "scheduler_enabled": False,
            "required_disabled_timers": [
                "astra-scheduler-h1.timer",
                "astra-scheduler-h4.timer",
                "astra-scheduler-d1.timer",
            ],
            "timers_changed_by_migration": False,
            "active_symbols_exact": list(SYMBOLS),
            "expected_aliases": list(EXPECTED_ALIAS_SHA256),
            "unexpected_gbpusd_alias_absent": True,
            "legacy_yahoo_dataset_count": 12,
        },
        "symbol_before": symbol_before,
        "symbol_after": {},
        "dataset_before": dataset_before,
        "dataset_after": {},
        "files": files,
        "aliases_quarantined": [],
        "errors": [],
        "result": "PENDING",
    }


def _manifest_path(project_root: Path, migration_id: str) -> Path:
    suffix = migration_id.removeprefix("oracle-legacy-forex-")
    return (
        project_root.resolve()
        / "reports"
        / "deployment"
        / f"oracle_forex_legacy_migration_{suffix}.json"
    )


def _persist_manifest(path: Path, manifest: dict[str, Any]) -> None:
    _atomic_write_json(path, manifest)


def _move_to_quarantine(record: dict[str, Any]) -> None:
    original = Path(record["original_path"])
    quarantine = Path(record["quarantine_path"])
    if original.is_symlink() or not original.is_file() or quarantine.exists():
        raise PersistenceConflictError("FILES_QUARANTINE_PRECONDITION_CHANGED")
    if (
        original.stat().st_size != record["bytes"]
        or _sha256_file(original) != record["sha256_before"]
    ):
        raise PersistenceConflictError("FILES_QUARANTINE_SOURCE_CHANGED")
    quarantine.parent.mkdir(parents=True, exist_ok=True)
    os.replace(original, quarantine)
    record["moved"] = True
    record["sha256_after"] = _sha256_file(quarantine)
    if (
        not quarantine.is_file()
        or quarantine.stat().st_size != record["bytes"]
        or record["sha256_after"] != record["sha256_before"]
    ):
        raise PersistenceConflictError("FILES_QUARANTINE_VERIFY_FAILED")


def _restore_file(record: dict[str, Any]) -> None:
    original = Path(record["original_path"])
    quarantine = Path(record["quarantine_path"])
    if original.exists() or original.is_symlink():
        raise PersistenceConflictError(
            f"ROLLBACK_FILE_CONFLICT: {original}"
        )
    if quarantine.is_symlink() or not quarantine.is_file():
        raise PersistenceConflictError(
            f"ROLLBACK_QUARANTINE_MISSING: {quarantine}"
        )
    if (
        quarantine.stat().st_size != record["bytes"]
        or _sha256_file(quarantine) != record["sha256_before"]
        or record.get("sha256_after") != record["sha256_before"]
    ):
        raise PersistenceConflictError(
            f"ROLLBACK_QUARANTINE_SHA256_MISMATCH: {quarantine}"
        )
    original.parent.mkdir(parents=True, exist_ok=True)
    os.replace(quarantine, original)
    if (
        not original.is_file()
        or original.stat().st_size != record["bytes"]
        or _sha256_file(original) != record["sha256_before"]
    ):
        raise PersistenceConflictError(f"ROLLBACK_FILE_VERIFY_FAILED: {original}")


def _return_file_to_quarantine(record: dict[str, Any]) -> None:
    original = Path(record["original_path"])
    quarantine = Path(record["quarantine_path"])
    if quarantine.exists() or not original.is_file():
        raise PersistenceConflictError("ROLLBACK_COMPENSATION_FILE_CONFLICT")
    if _sha256_file(original) != record["sha256_before"]:
        raise PersistenceConflictError("ROLLBACK_COMPENSATION_SHA256_MISMATCH")
    quarantine.parent.mkdir(parents=True, exist_ok=True)
    os.replace(original, quarantine)


def _database_matches(
    database: DatabaseAdapter,
    symbol_state: dict[str, dict],
    dataset_state: dict[str, dict],
) -> bool:
    for symbol, expected in symbol_state.items():
        if database.get_symbol(symbol) != expected:
            return False
    for key, expected in dataset_state.items():
        symbol, timeframe = key.split(":", 1)
        rows = database.get_dataset_registry(symbol, timeframe)
        if len(rows) != 1 or rows[0] != expected:
            return False
    return True


def _verify_applied(database: DatabaseAdapter, manifest: dict[str, Any]) -> None:
    if not _database_matches(
        database, manifest["symbol_after"], manifest["dataset_after"]
    ):
        raise PersistenceConflictError("VERIFY_DATABASE_STATE_MISMATCH")
    if database.get_active_symbols():
        raise PersistenceConflictError("VERIFY_ACTIVE_SYMBOLS_REMAIN")
    for symbol, target in TARGET_STATES.items():
        row = manifest["symbol_after"].get(symbol) or {}
        if row.get("status") != target:
            raise PersistenceConflictError("VERIFY_LIFECYCLE_TARGET_MISMATCH")
        if symbol in {"EURUSD", "USDJPY"} and not _is_qualification_absent(row):
            raise PersistenceConflictError("VERIFY_QUALIFICATION_WAS_FABRICATED")
    for record in manifest["files"]:
        original = Path(record["original_path"])
        quarantine = Path(record["quarantine_path"])
        if (
            original.exists()
            or not quarantine.is_file()
            or _sha256_file(quarantine) != record["sha256_before"]
            or record.get("sha256_after") != record["sha256_before"]
        ):
            raise PersistenceConflictError("VERIFY_QUARANTINED_FILE_MISMATCH")


def _automatic_rollback(
    database: DatabaseAdapter,
    manifest: dict[str, Any],
) -> list[str]:
    rollback_errors = []
    try:
        database.restore_legacy_forex_migration_state(
            symbol_before=manifest["symbol_before"],
            symbol_after=manifest["symbol_after"],
            dataset_before=manifest["dataset_before"],
            dataset_after=manifest["dataset_after"],
            allow_unchanged=True,
        )
    except Exception as exc:
        rollback_errors.append(f"DATABASE_ROLLBACK_{type(exc).__name__}")

    for record in reversed(manifest["files"]):
        if not record.get("moved"):
            continue
        try:
            _restore_file(record)
            record["moved"] = False
        except Exception as exc:
            rollback_errors.append(f"FILE_ROLLBACK_{type(exc).__name__}")
    return rollback_errors


def run_migration(
    *,
    database: DatabaseAdapter,
    project_root: Path | str,
    apply: bool = False,
    now: datetime | None = None,
    source_git_sha: str | None = None,
) -> dict[str, Any]:
    """Precheck the exact legacy state and optionally apply its quarantine."""
    root = _resolve_runtime_project_root(project_root)
    timestamp = _timestamp(now)
    git_sha = _source_git_sha(source_git_sha)
    if apply:
        _require_scheduler_disabled()
    manifest = _build_manifest(
        database,
        root,
        mode="APPLY" if apply else "DRY_RUN",
        now=timestamp,
        source_git_sha=git_sha,
    )
    if not apply:
        manifest["result"] = "DRY_RUN"
        return _public_result(manifest, None)

    path = _manifest_path(root, manifest["migration_id"])
    if path.exists() or path.is_symlink():
        raise PersistenceConflictError("MIGRATION_MANIFEST_ALREADY_EXISTS")
    _persist_manifest(path, manifest)
    try:
        manifest["phase"] = "FILES_QUARANTINE"
        _persist_manifest(path, manifest)
        for record in manifest["files"]:
            _move_to_quarantine(record)
            if record["kind"] == "alias":
                manifest["aliases_quarantined"].append(record["symbol"])
            _persist_manifest(path, manifest)

        manifest["phase"] = "DB_MIGRATION"
        _persist_manifest(path, manifest)
        for symbol in ("EURUSD", "USDJPY"):
            manifest["symbol_after"][symbol] = (
                migrate_legacy_active_to_candidate(
                    database,
                    symbol,
                    expected_state=manifest["symbol_before"][symbol],
                )
            )
            _persist_manifest(path, manifest)
        for symbol in ("GBPUSD", "AUDUSD"):
            manifest["symbol_after"][symbol] = disable_symbol(
                database,
                symbol,
                expected_state=manifest["symbol_before"][symbol],
            )
            _persist_manifest(path, manifest)

        for record in manifest["files"]:
            if record["kind"] != "dataset":
                continue
            key = f"{record['symbol']}:{record['timeframe']}"
            manifest["dataset_after"][key] = (
                database.quarantine_legacy_dataset_registry(
                    record["symbol"],
                    record["timeframe"],
                    expected_state=manifest["dataset_before"][key],
                    quarantine_path=record["quarantine_path"],
                )
            )
            _persist_manifest(path, manifest)

        manifest["phase"] = "VERIFY"
        _persist_manifest(path, manifest)
        _verify_applied(database, manifest)
        manifest["result"] = "SUCCESS"
        _persist_manifest(path, manifest)
    except Exception as exc:
        manifest["errors"].append({
            "phase": manifest["phase"],
            "classification": "MIGRATION_PHASE_FAILED",
            "exception_type": type(exc).__name__,
        })
        rollback_errors = _automatic_rollback(database, manifest)
        manifest["errors"].extend(
            {"phase": "ROLLBACK", "classification": item}
            for item in rollback_errors
        )
        manifest["phase"] = "FAILED"
        manifest["result"] = (
            "FAILED_ROLLED_BACK" if not rollback_errors else "FAILED_PARTIAL"
        )
        _persist_manifest(path, manifest)
        if rollback_errors:
            raise PersistenceConflictError("AUTOMATIC_ROLLBACK_FAILED") from exc
        raise
    return _public_result(manifest, path)


def _load_apply_manifest(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise PersistenceConflictError("ROLLBACK_MANIFEST_MISSING")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PersistenceConflictError("ROLLBACK_MANIFEST_INVALID") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("mode") != "APPLY"
        or manifest.get("phase") != "VERIFY"
        or manifest.get("result") != "SUCCESS"
        or _MIGRATION_ID.fullmatch(str(manifest.get("migration_id") or "")) is None
        or set(manifest.get("symbol_before") or {}) != set(SYMBOLS)
        or set(manifest.get("symbol_after") or {}) != set(SYMBOLS)
        or len(manifest.get("dataset_before") or {}) != 12
        or set(manifest.get("dataset_before") or {})
        != set(manifest.get("dataset_after") or {})
        or len(manifest.get("files") or []) != 15
    ):
        raise PersistenceConflictError("ROLLBACK_MANIFEST_CONTRACT_INVALID")
    return manifest


def _validate_rollback_paths(manifest: dict[str, Any], root: Path) -> None:
    migration_id = manifest["migration_id"]
    expected: dict[tuple[str, str, str | None], tuple[Path, Path]] = {}
    model_root = forex_model_root(root).resolve()
    model_quarantine = model_root / "legacy_quarantine" / migration_id
    data_quarantine = root / "data" / "forex_legacy_quarantine" / migration_id
    for symbol in EXPECTED_ALIAS_SHA256:
        name = f"latest_{symbol}.pkl"
        expected[("alias", symbol, None)] = (
            model_root / name,
            model_quarantine / name,
        )
    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            original = forex_dataset_path(
                symbol, timeframe, project_root=root
            ).resolve()
            expected[("dataset", symbol, timeframe)] = (
                original,
                data_quarantine / original.name,
            )

    observed = set()
    for record in manifest["files"]:
        key = (record.get("kind"), record.get("symbol"), record.get("timeframe"))
        if key not in expected or key in observed:
            raise PersistenceConflictError("ROLLBACK_FILE_SCOPE_INVALID")
        observed.add(key)
        original, quarantine = expected[key]
        if (
            Path(str(record.get("original_path") or "")).resolve()
            != original.resolve()
            or Path(str(record.get("quarantine_path") or "")).resolve()
            != quarantine.resolve()
            or _SHA256.fullmatch(str(record.get("sha256_before") or "")) is None
            or record.get("sha256_after") != record.get("sha256_before")
            or not isinstance(record.get("bytes"), int)
            or record["bytes"] < 0
            or record.get("moved") is not True
        ):
            raise PersistenceConflictError("ROLLBACK_FILE_RECORD_INVALID")
    if observed != set(expected):
        raise PersistenceConflictError("ROLLBACK_FILE_SCOPE_INCOMPLETE")


def _validate_rollback_state_contract(manifest: dict[str, Any]) -> None:
    try:
        manifest_timestamp = datetime.fromisoformat(str(manifest.get("timestamp")))
    except (TypeError, ValueError) as exc:
        raise PersistenceConflictError("ROLLBACK_MANIFEST_TIMESTAMP_INVALID") from exc
    preconditions = manifest.get("preconditions") or {}
    if (
        manifest.get("errors") != []
        or manifest.get("aliases_quarantined")
        != list(EXPECTED_ALIAS_SHA256)
        or _GIT_SHA.fullmatch(str(manifest.get("source_git_sha") or "")) is None
        or manifest_timestamp.tzinfo is None
        or preconditions.get("scheduler_enabled") is not False
        or preconditions.get("timers_changed_by_migration") is not False
        or preconditions.get("active_symbols_exact") != list(SYMBOLS)
        or preconditions.get("legacy_yahoo_dataset_count") != 12
    ):
        raise PersistenceConflictError("ROLLBACK_MANIFEST_EVIDENCE_INVALID")

    symbol_before = manifest["symbol_before"]
    symbol_after = manifest["symbol_after"]
    for symbol, target_status in TARGET_STATES.items():
        before = symbol_before[symbol]
        after = symbol_after[symbol]
        _require_legacy_active(before, symbol)
        if (
            after.get("status") != target_status
            or after.get("activation_origin") != "legacy"
            or not _is_qualification_absent(after)
        ):
            raise PersistenceConflictError(
                f"ROLLBACK_SYMBOL_AFTER_INVALID: {symbol}"
            )
        before_stable = {
            key: value for key, value in before.items()
            if key not in {"status", "updated_at"}
        }
        after_stable = {
            key: value for key, value in after.items()
            if key not in {"status", "updated_at"}
        }
        if before_stable != after_stable:
            raise PersistenceConflictError(
                f"ROLLBACK_SYMBOL_HISTORY_CHANGED: {symbol}"
            )

    records = {
        (item.get("symbol"), item.get("timeframe")): item
        for item in manifest["files"]
        if item.get("kind") == "dataset"
    }
    for key, before in manifest["dataset_before"].items():
        symbol, timeframe = key.split(":", 1)
        after = manifest["dataset_after"][key]
        record = records.get((symbol, timeframe))
        if (
            record is None
            or before.get("symbol") != symbol
            or before.get("timeframe") != timeframe
            or before.get("status") != "ready"
            or before.get("provider_used") != "Yahoo"
            or before.get("provider_class") != "FX_REFERENCE"
            or before.get("source_sha256") != record.get("sha256_before")
            or after.get("status") != "quarantined"
            or after.get("last_error") != LEGACY_QUARANTINE_CLASSIFICATION
            or after.get("blob_path") != record.get("quarantine_path")
        ):
            raise PersistenceConflictError(
                f"ROLLBACK_DATASET_STATE_INVALID: {key}"
            )
        before_stable = {
            item_key: value for item_key, value in before.items()
            if item_key not in {"blob_path", "status", "last_error", "last_updated"}
        }
        after_stable = {
            item_key: value for item_key, value in after.items()
            if item_key not in {"blob_path", "status", "last_error", "last_updated"}
        }
        if before_stable != after_stable:
            raise PersistenceConflictError(
                f"ROLLBACK_DATASET_PROVENANCE_CHANGED: {key}"
            )

    alias_records = {
        item.get("symbol"): item
        for item in manifest["files"]
        if item.get("kind") == "alias"
    }
    if set(alias_records) != set(EXPECTED_ALIAS_SHA256):
        raise PersistenceConflictError("ROLLBACK_ALIAS_SCOPE_INVALID")
    for symbol, expected_sha256 in EXPECTED_ALIAS_SHA256.items():
        if alias_records[symbol].get("sha256_before") != expected_sha256:
            raise PersistenceConflictError(
                f"ROLLBACK_ALIAS_SHA256_INVALID: {symbol}"
            )


def _precheck_rollback_files(manifest: dict[str, Any]) -> None:
    for record in manifest["files"]:
        original = Path(record["original_path"])
        quarantine = Path(record["quarantine_path"])
        if original.exists() or original.is_symlink():
            raise PersistenceConflictError(f"ROLLBACK_FILE_CONFLICT: {original}")
        if quarantine.is_symlink() or not quarantine.is_file():
            raise PersistenceConflictError(
                f"ROLLBACK_QUARANTINE_MISSING: {quarantine}"
            )
        if (
            quarantine.stat().st_size != record["bytes"]
            or _sha256_file(quarantine) != record["sha256_before"]
        ):
            raise PersistenceConflictError(
                f"ROLLBACK_QUARANTINE_SHA256_MISMATCH: {quarantine}"
            )


def rollback_migration(
    *,
    database: DatabaseAdapter,
    manifest_path: Path | str,
    project_root: Path | str,
    now: datetime | None = None,
    source_git_sha: str | None = None,
) -> dict[str, Any]:
    """Restore a successful migration only if no later state conflicts."""
    _require_scheduler_disabled()
    root = _resolve_runtime_project_root(project_root)
    source = Path(manifest_path).expanduser().resolve()
    manifest = _load_apply_manifest(source)
    if manifest.get("runtime_project_root") != str(root):
        raise PersistenceConflictError("ROLLBACK_RUNTIME_ROOT_MISMATCH")
    _validate_rollback_paths(manifest, root)
    _validate_rollback_state_contract(manifest)
    if not _database_matches(
        database, manifest["symbol_after"], manifest["dataset_after"]
    ):
        raise PersistenceConflictError("ROLLBACK_DATABASE_CONFLICT")
    _precheck_rollback_files(manifest)

    timestamp = _timestamp(now)
    rollback_manifest = {
        "schema_version": SCHEMA_VERSION,
        "migration_id": manifest["migration_id"],
        "timestamp": timestamp.isoformat(),
        "runtime_project_root": str(root),
        "source_git_sha": _source_git_sha(source_git_sha),
        "mode": "ROLLBACK",
        "phase": "PRECHECK",
        "source_manifest": str(source),
        "preconditions": {
            "scheduler_enabled": not _scheduler_is_disabled(),
            "database_matches_migration": True,
            "files_match_migration": True,
        },
        "symbol_before": manifest["symbol_after"],
        "symbol_after": manifest["symbol_before"],
        "dataset_before": manifest["dataset_after"],
        "dataset_after": manifest["dataset_before"],
        "files": manifest["files"],
        "aliases_quarantined": manifest["aliases_quarantined"],
        "errors": [],
        "result": "PENDING",
    }
    suffix = timestamp.strftime("%Y%m%dT%H%M%S%fZ")
    rollback_path = (
        root / "reports" / "deployment"
        / f"oracle_forex_legacy_migration_rollback_{suffix}.json"
    )
    if rollback_path.exists() or rollback_path.is_symlink():
        raise PersistenceConflictError("ROLLBACK_MANIFEST_ALREADY_EXISTS")
    _persist_manifest(rollback_path, rollback_manifest)

    restored = []
    try:
        rollback_manifest["phase"] = "FILES_RESTORE"
        _persist_manifest(rollback_path, rollback_manifest)
        for record in reversed(manifest["files"]):
            _restore_file(record)
            restored.append(record)
            _persist_manifest(rollback_path, rollback_manifest)

        rollback_manifest["phase"] = "DB_RESTORE"
        _persist_manifest(rollback_path, rollback_manifest)
        database.restore_legacy_forex_migration_state(
            symbol_before=manifest["symbol_before"],
            symbol_after=manifest["symbol_after"],
            dataset_before=manifest["dataset_before"],
            dataset_after=manifest["dataset_after"],
        )
    except Exception as exc:
        compensation_errors = []
        for record in reversed(restored):
            try:
                _return_file_to_quarantine(record)
            except Exception as compensation_exc:
                compensation_errors.append(type(compensation_exc).__name__)
        rollback_manifest["errors"].append({
            "phase": rollback_manifest["phase"],
            "classification": "ROLLBACK_FAILED",
            "exception_type": type(exc).__name__,
            "compensation_errors": compensation_errors,
        })
        rollback_manifest["phase"] = "FAILED"
        rollback_manifest["result"] = "FAILED"
        _persist_manifest(rollback_path, rollback_manifest)
        raise

    if not _database_matches(
        database, manifest["symbol_before"], manifest["dataset_before"]
    ):
        raise PersistenceConflictError("ROLLBACK_VERIFY_DATABASE_MISMATCH")
    for record in manifest["files"]:
        original = Path(record["original_path"])
        quarantine = Path(record["quarantine_path"])
        if (
            quarantine.exists()
            or not original.is_file()
            or _sha256_file(original) != record["sha256_before"]
        ):
            raise PersistenceConflictError("ROLLBACK_VERIFY_FILE_MISMATCH")
    rollback_manifest["phase"] = "VERIFY"
    rollback_manifest["result"] = "ROLLED_BACK"
    _persist_manifest(rollback_path, rollback_manifest)
    return _public_result(rollback_manifest, rollback_path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run or apply the exact Oracle legacy Forex migration"
    )
    parser.add_argument(
        "--project-root",
        required=True,
        type=Path,
        help="explicit deployed ASTRA runtime root (for Oracle: /opt/astra)",
    )
    parser.add_argument(
        "--source-git-sha",
        help="exact 40-character Git SHA of the deployed migration code",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true", help="apply quarantine")
    action.add_argument(
        "--rollback", type=Path, help="restore one successful apply manifest"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        runtime_root = _resolve_runtime_project_root(args.project_root)
        database = get_database()
        if args.rollback is not None:
            result = rollback_migration(
                database=database,
                manifest_path=args.rollback,
                project_root=runtime_root,
                source_git_sha=args.source_git_sha,
            )
        else:
            result = run_migration(
                database=database,
                project_root=runtime_root,
                apply=args.apply,
                source_git_sha=args.source_git_sha,
            )
    except Exception as exc:
        print(json.dumps({
            "result": "FAILED",
            "classification": "LEGACY_FOREX_MIGRATION_FAILED",
            "exception_type": type(exc).__name__,
        }, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

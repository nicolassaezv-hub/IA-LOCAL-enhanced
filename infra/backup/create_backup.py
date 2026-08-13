"""Create fail-closed, atomic ASTRA backups.

SQLite databases are copied with SQLite's online Backup API. A completed
archive is published with one atomic rename only after its manifest and
checksums have been verified. Service environment files and secrets are
intentionally excluded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import stat
import tarfile
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable, Sequence


DEFAULT_BACKUP_ROOT = Path("/var/backups/astra")
DEFAULT_PROJECT_ROOT = Path("/opt/astra")
ARCHIVE_PREFIX = "astra_backup_"

_STATE_ROOTS = (
    "models",
    "CSVs",
    "reports",
    "data/forex",
    "data/forex_analytics",
    "workspace/uploads",
    "lab_reports",
    "prediction/reports",
)
_LEGACY_DATABASES = ("memoria.db", "astra_hparam_cache.db")
_RUNTIME_FILES = ("memory_db/circuit_breaker_state.json",)
_FORBIDDEN_POSIX_BACKUP_ROOTS = frozenset(
    {
        "/",
        "/etc",
        "/usr",
        "/var",
        "/home",
        "/root",
        "/opt",
        "/srv",
        "/mnt",
        "/media",
        "/run",
        "/boot",
        "/dev",
        "/proc",
        "/sys",
    }
)


class BackupError(RuntimeError):
    """Backup could not be completed safely."""


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def validate_backup_root(project_root: Path, backup_root: Path) -> tuple[Path, Path]:
    if not backup_root.is_absolute():
        raise BackupError("Backup root must be an absolute dedicated directory")
    if ".." in backup_root.parts:
        raise BackupError("Backup root must not contain parent traversal")
    project = project_root.resolve(strict=True)
    backup = backup_root.resolve(strict=False)
    if backup.as_posix() in _FORBIDDEN_POSIX_BACKUP_ROOTS:
        raise BackupError("Backup root must be a dedicated directory, not a system root")
    public_uploads = (project / "workspace" / "uploads").resolve(strict=False)
    if backup == project or _is_within(backup, project) or _is_within(backup, public_uploads):
        raise BackupError("Backup root must be outside the ASTRA project and public uploads")
    return project, backup


def sqlite_snapshot(source: Path, destination: Path) -> None:
    """Create a transactionally consistent snapshot of a live SQLite DB."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{source.resolve().as_posix()}?mode=ro"
    try:
        with closing(
            sqlite3.connect(source_uri, uri=True, timeout=30.0)
        ) as source_db:
            with closing(sqlite3.connect(destination)) as destination_db:
                source_db.backup(destination_db)
                destination_db.commit()
                result = destination_db.execute("PRAGMA quick_check").fetchone()
                if not result or str(result[0]).lower() != "ok":
                    raise BackupError(f"SQLite snapshot integrity failed for {source.name}")
    except sqlite3.Error as exc:
        raise BackupError(f"SQLite snapshot failed for {source.name}: {type(exc).__name__}") from exc


def _iter_regular_files(root: Path) -> Iterable[Path]:
    if not root.exists() or root.is_symlink():
        return
    for current_root, directory_names, file_names in os.walk(root, followlinks=False):
        current = Path(current_root)
        directory_names[:] = [
            name for name in directory_names if not (current / name).is_symlink()
        ]
        for name in file_names:
            candidate = current / name
            if candidate.is_symlink() or not candidate.is_file():
                continue
            yield candidate


def _copy_runtime_state(project_root: Path, payload_root: Path) -> list[str]:
    copied: list[str] = []
    for relative_root in _STATE_ROOTS:
        source_root = project_root / relative_root
        for source in _iter_regular_files(source_root):
            relative = source.relative_to(project_root)
            destination = payload_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=False)
            copied.append(relative.as_posix())

    legacy_index = project_root / "astra_csv_index.json"
    if legacy_index.is_file() and not legacy_index.is_symlink():
        shutil.copy2(legacy_index, payload_root / legacy_index.name, follow_symlinks=False)
        copied.append(legacy_index.name)
    for relative_name in _RUNTIME_FILES:
        source = project_root / relative_name
        if source.is_file() and not source.is_symlink():
            destination = payload_root / relative_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=False)
            copied.append(relative_name)
    return copied


def _snapshot_databases(project_root: Path, payload_root: Path) -> list[str]:
    candidates = list(_iter_regular_files(project_root / "memory_db"))
    candidates.extend(project_root / name for name in _LEGACY_DATABASES)
    snapshots: list[str] = []
    seen: set[Path] = set()
    for source in candidates:
        if source.suffix.lower() != ".db" or not source.is_file() or source.is_symlink():
            continue
        resolved = source.resolve()
        if resolved in seen or not _is_within(resolved, project_root):
            continue
        seen.add(resolved)
        relative = source.relative_to(project_root)
        destination = payload_root / relative
        sqlite_snapshot(source, destination)
        snapshots.append(relative.as_posix())
    return sorted(snapshots)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_checksums(payload_root: Path) -> dict[str, str]:
    return {
        path.relative_to(payload_root).as_posix(): sha256_file(path)
        for path in sorted(_iter_regular_files(payload_root))
    }


def _verify_archive(archive: Path, expected_checksums: dict[str, str]) -> None:
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        files: dict[str, tarfile.TarInfo] = {}
        for member in members:
            member_path = PurePosixPath(member.name)
            if (
                not member.name
                or "\\" in member.name
                or member_path.is_absolute()
                or ".." in member_path.parts
                or PureWindowsPath(member.name).drive
            ):
                raise BackupError("Unsafe path generated in backup archive")
            if member.isfile():
                if member.name in files:
                    raise BackupError("Duplicate file path generated in backup archive")
                files[member.name] = member
        if "manifest.json" not in files:
            raise BackupError("Backup manifest is missing")
        manifest_stream = bundle.extractfile(files["manifest.json"])
        if manifest_stream is None:
            raise BackupError("Backup manifest is unreadable")
        with manifest_stream:
            manifest = json.load(manifest_stream)
        if manifest.get("status") != "complete":
            raise BackupError("Backup manifest is not complete")
        if manifest.get("checksums") != expected_checksums:
            raise BackupError("Backup manifest checksum inventory changed")
        for relative, expected_checksum in expected_checksums.items():
            relative_path = PurePosixPath(relative)
            if (
                not relative
                or "\\" in relative
                or relative_path.is_absolute()
                or ".." in relative_path.parts
                or PureWindowsPath(relative).drive
            ):
                raise BackupError("Unsafe payload path declared in backup manifest")
            archived_name = f"state/{relative}"
            member = files.get(archived_name)
            if member is None:
                raise BackupError("Backup archive is missing declared payload files")
            payload_stream = bundle.extractfile(member)
            if payload_stream is None:
                raise BackupError("Backup payload file is unreadable")
            digest = hashlib.sha256()
            with payload_stream:
                for chunk in iter(lambda: payload_stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected_checksum:
                raise BackupError(f"Backup payload checksum mismatch: {relative}")


def _secure_backup_root(backup_root: Path) -> None:
    try:
        backup_root.chmod(0o750)
        if os.name == "posix":
            effective_mode = stat.S_IMODE(backup_root.stat().st_mode)
            if effective_mode != 0o750:
                raise BackupError("Backup root permissions could not be verified")
    except BackupError:
        raise
    except OSError as exc:
        raise BackupError("Backup root permissions could not be secured") from exc


def prune_backups(
    backup_root: Path,
    *,
    retention_days: int,
    now: datetime | None = None,
    preserve: Path | None = None,
) -> list[Path]:
    """Delete expired top-level ASTRA archives, never following symlinks."""
    if retention_days < 1:
        raise BackupError("Backup retention must be at least one day")
    root = backup_root.resolve(strict=True)
    current_timestamp = (now or datetime.now(timezone.utc)).timestamp()
    cutoff = current_timestamp - retention_days * 86400
    preserved = preserve.resolve() if preserve is not None else None
    deleted: list[Path] = []
    for candidate in root.glob(f"{ARCHIVE_PREFIX}*.tar.gz"):
        if candidate.is_symlink() or not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if resolved.parent != root or resolved == preserved:
            continue
        if candidate.stat().st_mtime < cutoff:
            candidate.unlink()
            deleted.append(candidate)
    return deleted


def create_backup(
    *,
    project_root: Path,
    backup_root: Path,
    retention_days: int = 7,
    now: datetime | None = None,
) -> Path:
    project, backup = validate_backup_root(project_root, backup_root)
    backup.mkdir(parents=True, exist_ok=True, mode=0o750)
    _secure_backup_root(backup)

    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
    unique = secrets.token_hex(4)
    final_archive = backup / f"{ARCHIVE_PREFIX}{stamp}_{unique}.tar.gz"
    temporary_archive = backup / f".{final_archive.name}.tmp"
    staging = Path(tempfile.mkdtemp(prefix=".astra-backup-", dir=backup))
    try:
        payload_root = staging / "state"
        payload_root.mkdir()
        database_snapshots = _snapshot_databases(project, payload_root)
        copied_files = _copy_runtime_state(project, payload_root)
        checksums = _payload_checksums(payload_root)
        model_artifacts = sorted(
            path for path in checksums if path.startswith("models/")
        )
        manifest = {
            "timestamp": timestamp.isoformat(),
            "status": "complete",
            "secrets_included": False,
            "database_snapshots": database_snapshots,
            "model_artifacts": model_artifacts,
            "runtime_files": sorted(set(copied_files)),
            "checksums": checksums,
        }
        manifest_path = staging / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )

        with tarfile.open(temporary_archive, "w:gz") as bundle:
            bundle.add(manifest_path, arcname="manifest.json", recursive=False)
            bundle.add(payload_root, arcname="state", recursive=True)
        _verify_archive(temporary_archive, checksums)
        temporary_archive.chmod(0o640)
        os.replace(temporary_archive, final_archive)
        prune_backups(
            backup,
            retention_days=retention_days,
            now=timestamp,
            preserve=final_archive,
        )
        return final_archive
    except Exception:
        if temporary_archive.exists():
            temporary_archive.unlink()
        raise
    finally:
        staging_resolved = staging.resolve(strict=False)
        if staging_resolved.parent == backup.resolve(strict=True) and staging.name.startswith(
            ".astra-backup-"
        ):
            shutil.rmtree(staging_resolved, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create an atomic ASTRA backup")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(os.environ.get("ASTRA_HOME", DEFAULT_PROJECT_ROOT)),
    )
    parser.add_argument(
        "--backup-root",
        type=Path,
        default=Path(os.environ.get("ASTRA_BACKUP_ROOT", DEFAULT_BACKUP_ROOT)),
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=int(os.environ.get("ASTRA_BACKUP_RETENTION_DAYS", "7")),
    )
    args = parser.parse_args(argv)
    archive = create_backup(
        project_root=args.project_root,
        backup_root=args.backup_root,
        retention_days=args.retention_days,
    )
    print(f"Backup created: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

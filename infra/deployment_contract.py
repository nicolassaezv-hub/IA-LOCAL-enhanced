"""Testable deployment checks and truthful aggregate status for ASTRA.

The Linux installer delegates decisions to this module so tests never need
sudo or a running systemd instance.  It deliberately does not install
packages, create state, or contact providers unless the caller explicitly
requests the canonical readiness provider probe.
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence


SUPPORTED_ARCHITECTURES = frozenset({"aarch64", "arm64", "x86_64", "amd64"})
REQUIRED_PYTHON = (3, 12)
VALID_PHASE_STATUSES = frozenset({"PASS", "FAIL", "SKIP", "PENDING"})
DEFAULT_BACKUP_ROOT = Path("/var/backups/astra")
SAFE_INSTALL_BASES = (PurePosixPath("/opt"), PurePosixPath("/srv"))
SAFE_ENVIRONMENT_ROOT = PurePosixPath("/etc/astra")
FORBIDDEN_BACKUP_ROOTS = frozenset(
    PurePosixPath(value)
    for value in (
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
    )
)
_SAFE_PATH_PATTERN = re.compile(r"/[A-Za-z0-9._/-]+\Z")


@dataclass(frozen=True)
class PhaseResult:
    name: str
    status: str
    critical: bool = True
    detail: str = ""

    def __post_init__(self) -> None:
        if self.status not in VALID_PHASE_STATUSES:
            raise ValueError(f"Invalid deployment phase status: {self.status}")


def normalize_architecture(machine: str) -> str:
    """Return a stable architecture spelling without assuming x86."""
    normalized = machine.strip().lower()
    aliases = {"arm64": "aarch64", "amd64": "x86_64"}
    return aliases.get(normalized, normalized)


def validate_platform(
    *,
    system_name: str,
    machine: str,
    python_version: Sequence[int],
) -> list[str]:
    """Return explicit production precheck errors for platform facts."""
    errors: list[str] = []
    if system_name.strip().lower() != "linux":
        errors.append(f"Unsupported operating system: {system_name or 'unknown'}; Linux is required")

    architecture = machine.strip().lower()
    if architecture not in SUPPORTED_ARCHITECTURES:
        errors.append(
            f"Unsupported architecture: {machine or 'unknown'}; "
            "supported architectures are aarch64/arm64 and x86_64/amd64"
        )

    actual_python = tuple(python_version[:2])
    if actual_python != REQUIRED_PYTHON:
        rendered = ".".join(str(part) for part in actual_python) or "unknown"
        errors.append(f"Unsupported Python {rendered}; Python 3.12 is required")
    return errors


def load_environment_file(path: Path) -> dict[str, str]:
    """Parse the simple systemd EnvironmentFile subset used by ASTRA."""
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _validate_posix_path(value: str, label: str) -> tuple[PurePosixPath | None, list[str]]:
    errors: list[str] = []
    if not value or not _SAFE_PATH_PATTERN.fullmatch(value):
        errors.append(f"{label} must be an absolute POSIX path with supported characters")
        return None, errors
    candidate = PurePosixPath(value)
    if not candidate.is_absolute() or candidate.root != "/":
        errors.append(f"{label} must be an absolute POSIX path")
    if ".." in candidate.parts:
        errors.append(f"{label} must not contain parent traversal")
    return candidate, errors


def _resolved_path_escapes(path: PurePosixPath, root: PurePosixPath) -> bool:
    """Check existing POSIX symlinks without making Windows tests host-dependent."""
    if os.name != "posix":
        return False
    concrete_root = Path(root.as_posix())
    concrete_path = Path(path.as_posix())
    resolved_root = concrete_root.resolve(strict=False)
    resolved_path = concrete_path.resolve(strict=False)
    return resolved_root != concrete_root or not _path_is_within(resolved_path, concrete_root)


def validate_install_root(value: str) -> list[str]:
    """Require a dedicated ASTRA install directory below /opt or /srv."""
    candidate, errors = _validate_posix_path(value, "ASTRA_HOME")
    if candidate is None or errors:
        return errors
    base = next(
        (root for root in SAFE_INSTALL_BASES if candidate != root and _path_is_within(candidate, root)),
        None,
    )
    if base is None:
        errors.append("ASTRA_HOME must be a dedicated directory below /opt or /srv")
    elif _resolved_path_escapes(candidate, base):
        errors.append("ASTRA_HOME must not escape its safe install root through symlinks")
    return errors


def validate_environment_file_path(value: str) -> list[str]:
    """Require the production EnvironmentFile to remain below /etc/astra."""
    candidate, errors = _validate_posix_path(value, "ASTRA_ENV_FILE")
    if candidate is None or errors:
        return errors
    if candidate == SAFE_ENVIRONMENT_ROOT or not _path_is_within(
        candidate, SAFE_ENVIRONMENT_ROOT
    ):
        errors.append("ASTRA_ENV_FILE must be a file below /etc/astra")
    elif _resolved_path_escapes(candidate, SAFE_ENVIRONMENT_ROOT):
        errors.append("ASTRA_ENV_FILE must not escape /etc/astra through symlinks")
    return errors


def validate_backup_root_path(value: str, *, project_root: Path | None = None) -> list[str]:
    """Reject system roots, traversal, and paths inside the ASTRA project."""
    candidate, errors = _validate_posix_path(value, "ASTRA_BACKUP_ROOT")
    if candidate is None or errors:
        return errors
    if candidate in FORBIDDEN_BACKUP_ROOTS:
        errors.append("ASTRA_BACKUP_ROOT must be a dedicated directory, not a system root")
    if os.name == "posix":
        resolved = Path(candidate.as_posix()).resolve(strict=False)
        resolved_posix = PurePosixPath(resolved.as_posix())
        if resolved_posix in FORBIDDEN_BACKUP_ROOTS:
            errors.append("ASTRA_BACKUP_ROOT must not resolve to a system root")
    if project_root is not None:
        project = PurePosixPath(project_root.as_posix())
        if candidate == project or _path_is_within(candidate, project):
            errors.append("ASTRA_BACKUP_ROOT must be outside the ASTRA project")
        elif os.name == "posix":
            resolved_backup = Path(candidate.as_posix()).resolve(strict=False)
            resolved_project = project_root.resolve(strict=False)
            if resolved_backup == resolved_project or _path_is_within(
                resolved_backup, resolved_project
            ):
                errors.append("ASTRA_BACKUP_ROOT must resolve outside the ASTRA project")
    return errors


def validate_service_environment(
    values: Mapping[str, str],
    *,
    allow_public_http: bool = False,
    project_root: Path | None = None,
) -> list[str]:
    """Validate required production config without returning secret values."""
    errors: list[str] = []
    if not values.get("ASTRA_API_KEY", "").strip():
        errors.append("ASTRA_API_KEY is empty in the service EnvironmentFile")

    host = values.get("ASTRA_HOST", "127.0.0.1").strip() or "127.0.0.1"
    if host not in {"127.0.0.1", "::1", "localhost"} and not allow_public_http:
        errors.append(
            "Public HTTP bind requires an explicit deployment opt-in; "
            "keep ASTRA_HOST=127.0.0.1 behind a reverse proxy by default"
        )
    backup_value = values.get("ASTRA_BACKUP_ROOT", DEFAULT_BACKUP_ROOT.as_posix())
    errors.extend(validate_backup_root_path(backup_value, project_root=project_root))
    try:
        if int(values.get("ASTRA_BACKUP_RETENTION_DAYS", "7")) < 1:
            raise ValueError
    except ValueError:
        errors.append("ASTRA_BACKUP_RETENTION_DAYS must be a positive integer")
    return errors


def deployment_outcome(
    phases: Iterable[PhaseResult], *, readiness_status: str
) -> str:
    """Aggregate phases without turning process liveness into readiness."""
    phase_list = list(phases)
    if any(phase.critical and phase.status != "PASS" for phase in phase_list):
        return "FAILED"
    if readiness_status.upper() not in {"READY", "READY_WITH_WARNINGS"}:
        return "DEPLOYED_NOT_READY"
    return "SUCCESS"


def _precheck(
    project_root: Path,
    service_user: str,
    install_root: str,
    environment_file: str,
) -> list[str]:
    errors = validate_platform(
        system_name=platform.system(),
        machine=platform.machine(),
        python_version=sys.version_info,
    )
    if service_user.strip().lower() == "root":
        errors.append("ASTRA service user must not be root")
    errors.extend(validate_install_root(install_root))
    errors.extend(validate_environment_file_path(environment_file))
    if not (project_root / "workspace" / "server.py").is_file():
        errors.append(f"Invalid ASTRA project directory: {project_root}")
    if not Path("/run/systemd/system").is_dir():
        errors.append("systemd is not running; service installation cannot continue")
    try:
        free_bytes = shutil.disk_usage(project_root).free
        if free_bytes < 1_073_741_824:
            errors.append("Less than 1 GiB free space is available for deployment")
    except OSError as exc:
        errors.append(f"Unable to inspect deployment filesystem: {type(exc).__name__}")
    return errors


def _readiness(project_root: Path, probe_providers: bool) -> int:
    from deployment.production_readiness import run_production_readiness

    report = run_production_readiness(
        base_dir=project_root,
        probe_providers=probe_providers,
    )
    if report.ready:
        print("READY_WITH_WARNINGS" if report.status == "degraded" else "READY")
        return 0
    print("NOT_READY")
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ASTRA deployment contract checks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    precheck = subparsers.add_parser("precheck")
    precheck.add_argument("--project-root", type=Path, required=True)
    precheck.add_argument("--service-user", default="astra")
    precheck.add_argument("--install-root", required=True)
    precheck.add_argument("--environment-file", required=True)

    config = subparsers.add_parser("validate-config")
    config.add_argument("--environment-file", type=Path, required=True)
    config.add_argument("--allow-public-http", action="store_true")
    config.add_argument("--project-root", type=Path)

    readiness = subparsers.add_parser("readiness")
    readiness.add_argument("--project-root", type=Path, required=True)
    readiness.add_argument("--environment-file", type=Path)
    readiness.add_argument("--probe-providers", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "precheck":
        errors = _precheck(
            args.project_root.resolve(),
            args.service_user,
            args.install_root,
            args.environment_file,
        )
    elif args.command == "validate-config":
        if not args.environment_file.is_file():
            errors = [f"Service EnvironmentFile does not exist: {args.environment_file}"]
        else:
            errors = validate_service_environment(
                load_environment_file(args.environment_file),
                allow_public_http=args.allow_public_http,
                project_root=args.project_root,
            )
    else:
        if args.environment_file is not None:
            os.environ.update(load_environment_file(args.environment_file))
        return _readiness(args.project_root.resolve(), args.probe_providers)

    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

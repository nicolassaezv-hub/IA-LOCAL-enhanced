from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import shutil
import sqlite3
import tarfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from infra.backup import create_backup as backup_module
from infra.backup.create_backup import BackupError, create_backup, prune_backups
from infra.deployment_contract import (
    PhaseResult,
    deployment_outcome,
    normalize_architecture,
    validate_backup_root_path,
    validate_environment_file_path,
    validate_install_root,
    validate_platform,
    validate_service_environment,
)
import runtime_paths


ROOT = Path(__file__).resolve().parents[1]
SYSTEMD_ROOT = ROOT / "infra" / "systemd"
SERVICE_FILES = sorted(SYSTEMD_ROOT.glob("*.service"))


def _service_texts() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in SERVICE_FILES}


def _make_project(root: Path) -> Path:
    project = root / "project"
    for relative in ("memory_db", "models/forex", "CSVs/H1", "workspace/uploads"):
        (project / relative).mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(project / "memory_db" / "astra_autonomous.db")) as connection:
        connection.execute("CREATE TABLE evidence (value TEXT NOT NULL)")
        connection.execute("INSERT INTO evidence VALUES ('canonical')")
        connection.commit()
    (project / "models" / "forex" / "latest_EURUSD.pkl").write_bytes(b"model")
    (project / "models" / "forex" / "latest_EURUSD.meta.json").write_text(
        '{"provenance": "closed-loop"}', encoding="utf-8"
    )
    (project / "CSVs" / "H1" / "EURUSD.csv").write_text(
        "timestamp,close\n2026-01-01,1.0\n", encoding="utf-8"
    )
    return project


def test_units_use_explicit_non_root_identity_and_absolute_venv_python():
    texts = _service_texts()
    assert texts
    for name, source in texts.items():
        assert "User=astra" in source, name
        assert "Group=astra" in source, name
        assert "User=root" not in source, name
        assert "WorkingDirectory=/opt/astra" in source, name
        exec_start = next(line for line in source.splitlines() if line.startswith("ExecStart="))
        assert exec_start.startswith("ExecStart=/opt/astra/venv/bin/python /opt/astra/"), name


def test_units_keep_loopback_default_and_external_environment_file():
    texts = _service_texts()
    for name, source in texts.items():
        assert "EnvironmentFile=/etc/astra/astra.env" in source, name
        assert "EnvironmentFile=-" not in source, name
        assert "ASTRA_API_KEY=" not in source, name
        assert "0.0.0.0" not in source, name
    example = (ROOT / "infra/config/astra.env.example").read_text(encoding="utf-8")
    assert "ASTRA_HOST=127.0.0.1" in example
    assert "ASTRA_API_HOST=127.0.0.1" in example
    assert next(line for line in example.splitlines() if line.startswith("ASTRA_API_KEY=")) == "ASTRA_API_KEY="


def test_service_environment_requires_api_key_and_public_bind_opt_in():
    assert validate_service_environment({"ASTRA_HOST": "127.0.0.1"})
    assert not validate_service_environment(
        {"ASTRA_HOST": "127.0.0.1", "ASTRA_API_KEY": "configured-at-runtime"}
    )
    public = {"ASTRA_HOST": "0.0.0.0", "ASTRA_API_KEY": "configured-at-runtime"}
    assert validate_service_environment(public)
    assert not validate_service_environment(public, allow_public_http=True)
    assert validate_service_environment(
        {
            "ASTRA_HOST": "127.0.0.1",
            "ASTRA_API_KEY": "configured-at-runtime",
            "ASTRA_BACKUP_ROOT": "/opt/astra/workspace/uploads/backups",
        },
        project_root=Path("/opt/astra"),
    )
    assert validate_service_environment(
        {
            "ASTRA_HOST": "127.0.0.1",
            "ASTRA_API_KEY": "configured-at-runtime",
            "ASTRA_BACKUP_ROOT": "/var/backups/../opt/astra",
        },
        project_root=Path("/opt/astra"),
    )


def test_units_have_bounded_writable_roots_and_hardening():
    allowed = {
        "/opt/astra/memory_db",
        "/opt/astra/models",
        "/opt/astra/CSVs",
        "/opt/astra/workspace/uploads",
        "/opt/astra/reports",
        "/opt/astra/logs",
        "/opt/astra/data",
        "/opt/astra/lab_reports",
        "/opt/astra/prediction/reports",
        "/var/log/astra",
        "/var/backups/astra",
    }
    for name, source in _service_texts().items():
        assert "NoNewPrivileges=true" in source, name
        assert "PrivateTmp=true" in source, name
        assert "ProtectSystem=strict" in source, name
        assert "ProtectHome=true" in source, name
        assert "UMask=0027" in source, name
        for line in source.splitlines():
            if line.startswith("ReadWritePaths="):
                paths = set(line.removeprefix("ReadWritePaths=").split())
                assert paths <= allowed, (name, paths - allowed)
                assert "/opt/astra" not in paths
                assert "/opt/astra/forex/data" not in paths


@pytest.mark.parametrize(
    ("install_root", "valid"),
    [
        ("/", False),
        ("/etc", False),
        ("/home/ubuntu/astra", False),
        ("/opt/astra", True),
        ("/srv/astra", True),
    ],
)
def test_astra_home_requires_a_safe_dedicated_deployment_root(
    install_root: str, valid: bool
):
    assert (not validate_install_root(install_root)) is valid


@pytest.mark.parametrize(
    ("environment_file", "valid"),
    [
        ("/etc/astra/astra.env", True),
        ("/etc/astra/production.env", True),
        ("/etc/astra", False),
        ("/tmp/astra.env", False),
        ("/opt/astra/astra.env", False),
        ("/home/user/astra.env", False),
        ("/etc/passwd", False),
        ("/etc/astra/../passwd", False),
    ],
)
def test_environment_file_is_confined_below_etc_astra(
    environment_file: str, valid: bool
):
    assert (not validate_environment_file_path(environment_file)) is valid


@pytest.mark.parametrize(
    ("backup_root", "valid"),
    [
        ("/", False),
        ("/etc", False),
        ("/usr", False),
        ("/var", False),
        ("/home", False),
        ("/root", False),
        ("/opt", False),
        ("/srv", False),
        ("/mnt", False),
        ("/media", False),
        ("/run", False),
        ("/boot", False),
        ("/dev", False),
        ("/proc", False),
        ("/sys", False),
        ("/var/backups/astra", True),
        ("/mnt/astra-backups", True),
        ("/srv/astra-backups", True),
        ("/var/backups/../opt/astra", False),
        ("relative/backups", False),
    ],
)
def test_backup_root_requires_a_safe_dedicated_directory(
    backup_root: str, valid: bool
):
    errors = validate_backup_root_path(backup_root, project_root=Path("/opt/astra"))
    assert (not errors) is valid


def test_deploy_validates_paths_before_any_install_or_recursive_permission_change():
    deploy = (ROOT / "infra/deploy.sh").read_text(encoding="utf-8")
    precheck_call = deploy.index('run_phase PRECHECK precheck')
    filesystem_call = deploy.index('run_phase FILESYSTEM install_filesystem')
    assert precheck_call < filesystem_call
    assert '--install-root "$ASTRA_HOME"' in deploy
    assert '--environment-file "$ASTRA_ENV_FILE"' in deploy
    assert 'install -d -m 0750 -o root -g "$ASTRA_GROUP" "$(dirname "$ASTRA_ENV_FILE")"' in deploy
    assert 'install -m 0640 -o root -g "$ASTRA_GROUP"' in deploy
    assert 'chown root:"$ASTRA_GROUP" "$ASTRA_ENV_FILE"' in deploy
    assert 'chmod 0640 "$ASTRA_ENV_FILE"' in deploy


def test_deploy_checks_environment_file_existence_with_privilege():
    deploy = (ROOT / "infra/deploy.sh").read_text(encoding="utf-8")
    configure = deploy.split("configure_service_environment() {", 1)[1].split(
        "\n}", 1
    )[0]

    assert 'if ! run_privileged test -e "$ASTRA_ENV_FILE"; then' in configure
    assert '[[ ! -e "$ASTRA_ENV_FILE" ]]' not in configure


def test_deploy_only_installs_environment_template_when_file_is_missing():
    deploy = (ROOT / "infra/deploy.sh").read_text(encoding="utf-8")
    configure = deploy.split("configure_service_environment() {", 1)[1].split(
        "\n}", 1
    )[0]
    missing_branch, existing_branch = configure.split("\n    else\n", 1)

    assert "infra/config/astra.env.example" in missing_branch
    assert (
        'install -m 0640 -o root -g "$ASTRA_GROUP" "$generated" '
        '"$ASTRA_ENV_FILE"'
    ) in missing_branch
    assert "infra/config/astra.env.example" not in existing_branch
    assert '"$generated" "$ASTRA_ENV_FILE"' not in existing_branch


def test_existing_environment_file_keeps_restrictive_service_ownership():
    deploy = (ROOT / "infra/deploy.sh").read_text(encoding="utf-8")
    configure = deploy.split("configure_service_environment() {", 1)[1].split(
        "\n}", 1
    )[0]
    _, existing_branch = configure.split("\n    else\n", 1)

    assert 'run_privileged chown root:"$ASTRA_GROUP" "$ASTRA_ENV_FILE"' in existing_branch
    assert 'run_privileged chmod 0640 "$ASTRA_ENV_FILE"' in existing_branch


def test_deploy_precheck_does_not_use_interactive_sudo_validation():
    deploy = (ROOT / "infra/deploy.sh").read_text(encoding="utf-8")
    precheck = deploy.split("precheck() {", 1)[1].split("\n}", 1)[0]

    assert "sudo -v" not in precheck


def test_deploy_precheck_requires_non_interactive_passwordless_sudo():
    deploy = (ROOT / "infra/deploy.sh").read_text(encoding="utf-8")
    precheck = deploy.split("precheck() {", 1)[1].split("\n}", 1)[0]

    assert "if ! sudo -n true; then" in precheck
    assert "requires non-interactive passwordless sudo" in precheck


def test_run_privileged_uses_non_interactive_sudo_and_preserves_root_execution():
    deploy = (ROOT / "infra/deploy.sh").read_text(encoding="utf-8")
    run_privileged = deploy.split("run_privileged() {", 1)[1].split("\n}", 1)[0]

    assert 'if [[ "$EUID" -eq 0 ]]; then\n        "$@"' in run_privileged
    assert 'sudo -n "$@"' in run_privileged
    assert '\n        sudo "$@"' not in run_privileged


def test_rsync_excludes_every_real_dot_env_basename_at_any_depth():
    deploy = (ROOT / "infra/deploy.sh").read_text(encoding="utf-8")
    assert "--exclude='*.env'" in deploy
    assert "--exclude='/*.env'" not in deploy
    assert "--exclude='*.env.example'" not in deploy


def test_deploy_contains_no_world_writable_or_destructive_runtime_cleanup():
    deploy = (ROOT / "infra/deploy.sh").read_text(encoding="utf-8")
    assert "chmod -R 777" not in deploy
    assert "chmod 777" not in deploy
    assert "rm -rf" not in deploy
    assert "ASTRA_USER:-astra" in deploy
    assert "python3.12 -m venv" in deploy


def test_deploy_installs_linux_openmp_runtime_required_by_lightgbm():
    deploy = (ROOT / "infra/deploy.sh").read_text(encoding="utf-8")
    dependencies = deploy.split("system_dependencies() {", 1)[1].split("\n}", 1)[0]
    package_line = next(
        line.strip()
        for line in dependencies.splitlines()
        if line.strip().startswith("local packages=(")
    )
    packages = package_line.split("(", 1)[1].split(")", 1)[0].split()

    assert "libgomp1" in packages, (
        "LightGBM on Linux requires the libgomp1 OpenMP runtime (libgomp.so.1)"
    )


def test_critical_phase_failure_can_never_be_success():
    phases = [
        PhaseResult("PRECHECK", "PASS"),
        PhaseResult("DEPENDENCIES", "FAIL"),
        PhaseResult("READINESS", "PASS"),
    ]
    assert deployment_outcome(phases, readiness_status="READY") == "FAILED"


def test_process_alive_without_readiness_is_deployed_not_ready():
    phases = [PhaseResult("START", "PASS"), PhaseResult("SYSTEMD", "PASS")]
    assert deployment_outcome(phases, readiness_status="PENDING") == "DEPLOYED_NOT_READY"
    assert deployment_outcome(phases, readiness_status="ERROR") == "DEPLOYED_NOT_READY"
    assert deployment_outcome(phases, readiness_status="READY") == "SUCCESS"


def test_deploy_is_idempotent_by_contract_and_does_not_reset_env():
    deploy = (ROOT / "infra/deploy.sh").read_text(encoding="utf-8")
    assert 'if ! getent group "$ASTRA_GROUP"' in deploy
    assert 'if ! id "$ASTRA_USER"' in deploy
    assert 'if ! run_privileged test -e "$ASTRA_ENV_FILE"; then' in deploy
    assert "systemctl enable" in deploy
    assert "crontab" not in deploy
    assert "--delete" not in deploy
    assert "if run_readiness" in deploy
    assert "set +e\nrun_readiness" not in deploy
    assert "astra-new.$$" in deploy


def test_ubuntu_arm64_and_python_312_are_supported():
    assert normalize_architecture("arm64") == "aarch64"
    assert not validate_platform(
        system_name="Linux", machine="aarch64", python_version=(3, 12, 6)
    )


def test_unsupported_architecture_and_python_fail_explicitly():
    arch_errors = validate_platform(
        system_name="Linux", machine="riscv64", python_version=(3, 12, 6)
    )
    python_errors = validate_platform(
        system_name="Linux", machine="aarch64", python_version=(3, 11, 9)
    )
    assert any("Unsupported architecture: riscv64" in error for error in arch_errors)
    assert any("Python 3.11" in error and "3.12 is required" in error for error in python_errors)


def test_requirements_are_classified_constrained_and_not_x86_hardcoded():
    production = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    core = (ROOT / "requirements-core.txt").read_text(encoding="utf-8")
    ml = (ROOT / "requirements-ml.txt").read_text(encoding="utf-8")
    optional = (ROOT / "requirements-optional.txt").read_text(encoding="utf-8")
    constraints = (ROOT / "constraints-py312.txt").read_text(encoding="utf-8")
    assert "requirements-core.txt" in production and "requirements-ml.txt" in production
    assert "requirements-optional.txt" not in production
    assert "yfinance" in ml and "xgboost" in ml and "lightgbm" in ml
    assert "faiss-cpu" in optional and "openai" in optional
    combined = "\n".join((production, core, ml, optional, constraints)).lower()
    assert "x86_64" not in combined and "amd64" not in combined
    for source in (core, ml):
        for line in source.splitlines():
            line = line.strip()
            if line and not line.startswith(("#", "-r")):
                assert any(operator in line for operator in ("==", ">=", "<=", "~=", "<")), line


def test_optional_dependency_file_is_not_required_for_core_startup():
    production = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    readiness = (ROOT / "deployment/production_readiness.py").read_text(encoding="utf-8")
    assert "requirements-optional" not in production
    assert '("faiss", "faiss-cpu")' in readiness
    assert '("openai", "openai")' in readiness


def test_core_runtime_has_no_mandatory_static_optional_dependency_imports():
    optional_requirements = (ROOT / "requirements-optional.txt").read_text(
        encoding="utf-8"
    )
    for distribution in ("groq", "openai", "python-dotenv", "faiss-cpu"):
        assert distribution in optional_requirements

    optional_imports = {"groq", "openai", "dotenv", "faiss"}
    ignored_parts = {".git", ".venv", "venv", "legacy", "tests", "__pycache__"}
    mandatory: list[str] = []

    def catches_import_failure(handler: ast.ExceptHandler) -> bool:
        if handler.type is None:
            return True
        exception_nodes = (
            handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
        )
        caught_names = {
            exception.id
            for exception in exception_nodes
            if isinstance(exception, ast.Name)
        }
        return bool(
            caught_names
            & {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}
        )

    def is_deferred_or_guarded(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
        child = node
        parent = parents.get(child)
        while parent is not None:
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                return True
            if (
                isinstance(parent, ast.Try)
                and child in parent.body
                and any(catches_import_failure(handler) for handler in parent.handlers)
            ):
                return True
            child = parent
            parent = parents.get(child)
        return False

    for path in ROOT.rglob("*.py"):
        if any(part in ignored_parts for part in path.relative_to(ROOT).parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            roots: set[str] = set()
            if isinstance(node, ast.Import):
                roots = {alias.name.partition(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots = {node.module.partition(".")[0]}
            matched = roots & optional_imports
            if matched and not is_deferred_or_guarded(node, parents):
                mandatory.append(
                    f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:{sorted(matched)}"
                )

    assert not mandatory


def test_backup_uses_sqlite_online_snapshot_not_direct_live_db_copy():
    source = (ROOT / "infra/backup/create_backup.py").read_text(encoding="utf-8")
    shell = (ROOT / "infra/backup/backup.sh").read_text(encoding="utf-8")
    assert "source_db.backup(destination_db)" in source
    assert '"memory_db"' not in source.split("_STATE_ROOTS =", 1)[1].split(")", 1)[0]
    assert " cp " not in f" {shell} "
    assert "tar -" not in shell


def test_backup_manifest_checksums_and_sqlite_snapshot(tmp_path: Path):
    project = _make_project(tmp_path)
    (project / "memory_db/circuit_breaker_state.json").write_text(
        '{"is_open": false}', encoding="utf-8"
    )
    backup_root = tmp_path / "backups"
    archive = create_backup(project_root=project, backup_root=backup_root)
    assert archive.parent == backup_root
    with tarfile.open(archive, "r:gz") as bundle:
        manifest_file = bundle.extractfile("manifest.json")
        assert manifest_file is not None
        manifest = json.load(manifest_file)
        assert manifest["status"] == "complete"
        assert manifest["secrets_included"] is False
        assert manifest["database_snapshots"] == ["memory_db/astra_autonomous.db"]
        assert "models/forex/latest_EURUSD.pkl" in manifest["model_artifacts"]
        assert "memory_db/circuit_breaker_state.json" in manifest["runtime_files"]
        for relative, expected in manifest["checksums"].items():
            payload = bundle.extractfile(f"state/{relative}")
            assert payload is not None
            assert hashlib.sha256(payload.read()).hexdigest() == expected


def test_archive_verification_rejects_payload_checksum_mismatch(tmp_path: Path):
    archive = tmp_path / "corrupt.tar.gz"
    relative = "forex/data/EURUSD_H1.csv"
    expected_checksums = {relative: hashlib.sha256(b"expected payload").hexdigest()}
    manifest = json.dumps(
        {"status": "complete", "checksums": expected_checksums}
    ).encode("utf-8")
    corrupted_payload = b"different archived payload"

    with tarfile.open(archive, "w:gz") as bundle:
        manifest_info = tarfile.TarInfo("manifest.json")
        manifest_info.size = len(manifest)
        bundle.addfile(manifest_info, io.BytesIO(manifest))
        payload_info = tarfile.TarInfo(f"state/{relative}")
        payload_info.size = len(corrupted_payload)
        bundle.addfile(payload_info, io.BytesIO(corrupted_payload))

    with pytest.raises(BackupError, match="checksum mismatch"):
        backup_module._verify_archive(archive, expected_checksums)


def test_forex_data_source_is_not_backed_up_but_runtime_data_is(tmp_path: Path):
    project = _make_project(tmp_path)
    forex_data = project / "forex" / "data"
    (forex_data / "__pycache__").mkdir(parents=True)
    (forex_data / "caches").mkdir()
    (forex_data / "provider.py").write_text("SOURCE = True\n", encoding="utf-8")
    (forex_data / "__pycache__" / "provider.pyc").write_bytes(b"bytecode")
    (forex_data / "caches" / "provider.json").write_text("{}", encoding="utf-8")
    (forex_data / "EURUSD_H1.csv").write_text("timestamp,close\n", encoding="utf-8")
    (forex_data / "dataset_metadata.json").write_text(
        '{"pair": "EURUSD", "timeframe": "H1"}', encoding="utf-8"
    )
    runtime_data = project / "data" / "forex"
    runtime_data.mkdir(parents=True)
    (runtime_data / "EURUSD_H1.csv").write_text(
        "timestamp,close\n", encoding="utf-8"
    )

    archive = create_backup(project_root=project, backup_root=tmp_path / "backups")
    with tarfile.open(archive, "r:gz") as bundle:
        names = set(bundle.getnames())

    assert "state/forex/data/provider.py" not in names
    assert "state/forex/data/__pycache__/provider.pyc" not in names
    assert "state/forex/data/caches/provider.json" not in names
    assert "state/forex/data/EURUSD_H1.csv" not in names
    assert "state/forex/data/dataset_metadata.json" not in names
    assert "state/data/forex/EURUSD_H1.csv" in names


def test_incomplete_backup_is_never_published(monkeypatch, tmp_path: Path):
    project = _make_project(tmp_path)
    backup_root = tmp_path / "backups"

    def fail_verification(*_args, **_kwargs):
        raise BackupError("forced verification failure")

    monkeypatch.setattr(backup_module, "_verify_archive", fail_verification)
    with pytest.raises(BackupError, match="forced"):
        create_backup(project_root=project, backup_root=backup_root)
    assert not list(backup_root.glob("astra_backup_*.tar.gz"))
    assert not list(backup_root.glob("*.tmp"))
    assert not list(backup_root.glob(".astra-backup-*"))


def test_backup_excludes_environment_secrets(tmp_path: Path):
    project = _make_project(tmp_path)
    secret = "b3-secret-that-must-not-be-archived"
    config = project / "infra" / "config"
    config.mkdir(parents=True)
    (config / "astra.env").write_text(f"ASTRA_API_KEY={secret}\n", encoding="utf-8")
    archive = create_backup(project_root=project, backup_root=tmp_path / "backups")
    assert secret.encode() not in archive.read_bytes()
    with tarfile.open(archive, "r:gz") as bundle:
        assert not any(member.name.endswith("astra.env") for member in bundle.getmembers())


def test_retention_is_confined_and_preserves_new_backup(tmp_path: Path):
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    old = backup_root / "astra_backup_20000101T000000Z_deadbeef.tar.gz"
    fresh = backup_root / "astra_backup_20990101T000000Z_deadbeef.tar.gz"
    unrelated = tmp_path / "outside.tar.gz"
    old.write_bytes(b"old")
    fresh.write_bytes(b"fresh")
    unrelated.write_bytes(b"outside")
    old_time = (datetime.now(timezone.utc) - timedelta(days=30)).timestamp()
    os.utime(old, (old_time, old_time))
    deleted = prune_backups(backup_root, retention_days=7, preserve=fresh)
    assert deleted == [old]
    assert fresh.exists() and unrelated.exists()


def test_backup_root_cannot_be_project_or_public_uploads(tmp_path: Path):
    project = _make_project(tmp_path)
    with pytest.raises(BackupError):
        create_backup(project_root=project, backup_root=project / "backups")
    with pytest.raises(BackupError):
        create_backup(project_root=project, backup_root=project / "workspace/uploads/backups")


def test_backup_root_chmod_failure_is_fail_closed(monkeypatch, tmp_path: Path):
    project = _make_project(tmp_path)
    backup_root = tmp_path / "backups"
    original_chmod = Path.chmod

    def fail_backup_chmod(path: Path, mode: int, *args, **kwargs):
        if path == backup_root:
            raise OSError("chmod unavailable")
        return original_chmod(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "chmod", fail_backup_chmod)
    with pytest.raises(BackupError, match="permissions could not be secured"):
        create_backup(project_root=project, backup_root=backup_root)
    assert not list(backup_root.glob(f"{backup_module.ARCHIVE_PREFIX}*.tar.gz"))


def test_configured_project_path_uses_default_for_missing_or_empty_env(monkeypatch):
    environment_name = "ASTRA_TEST_RUNTIME_PATH"
    expected = runtime_paths.PROJECT_ROOT / "memory.db"

    monkeypatch.delenv(environment_name, raising=False)
    assert runtime_paths.configured_project_path(environment_name, "memory.db") == expected
    monkeypatch.setenv(environment_name, "")
    assert runtime_paths.configured_project_path(environment_name, "memory.db") == expected


def test_backup_does_not_follow_external_symlink(tmp_path: Path):
    project = _make_project(tmp_path)
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("outside", encoding="utf-8")
    link = project / "models" / "forex" / "external.pkl"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    archive = create_backup(project_root=project, backup_root=tmp_path / "backups")
    with tarfile.open(archive, "r:gz") as bundle:
        assert "state/models/forex/external.pkl" not in bundle.getnames()


def test_logrotate_uses_restrictive_service_ownership():
    source = (ROOT / "infra/logging/logrotate.conf").read_text(encoding="utf-8")
    assert "create 0640 astra astra" in source
    assert "su astra astra" in source
    assert "create 0644" not in source


def test_monitor_is_diagnostic_and_does_not_compete_with_systemd():
    source = (ROOT / "infra/monitor/supervisor.py").read_text(encoding="utf-8")
    assert "systemctl" not in source
    assert "restart_service" not in source
    assert "logging.FileHandler" not in source


def test_temporary_directories_are_immediately_removable(tmp_path: Path):
    work = tmp_path / "disposable"
    project = _make_project(work)
    create_backup(project_root=project, backup_root=work / "backups")
    shutil.rmtree(work)
    assert not work.exists()

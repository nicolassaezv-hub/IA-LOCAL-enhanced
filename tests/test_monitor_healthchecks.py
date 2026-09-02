"""Regression contracts for the diagnostic-only ASTRA monitor."""
from __future__ import annotations

from contextlib import nullcontext
import logging
from pathlib import Path
import sqlite3
import urllib.error

import pytest

from infra.monitor import supervisor


class _Response:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE health_probe (id INTEGER PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()


def test_database_health_uses_read_only_uri_query_only_and_quick_check(
    tmp_path, monkeypatch
):
    path = tmp_path / "monitor.db"
    _database(path)
    real_connect = sqlite3.connect
    calls = []
    statements = []

    class Cursor:
        def __init__(self, cursor):
            self.cursor = cursor

        def execute(self, statement, *args):
            statements.append(statement.strip())
            self.cursor.execute(statement, *args)
            return self

        def fetchone(self):
            return self.cursor.fetchone()

        def fetchall(self):
            return self.cursor.fetchall()

    class Connection:
        def __init__(self, connection):
            self.connection = connection

        def cursor(self):
            return Cursor(self.connection.cursor())

        def close(self):
            self.connection.close()

    def connect(database, *args, **kwargs):
        calls.append((database, kwargs.copy()))
        return Connection(real_connect(database, *args, **kwargs))

    monkeypatch.setattr(supervisor, "DB_PATH", str(path))
    monkeypatch.setattr(supervisor.sqlite3, "connect", connect)

    assert supervisor.check_database_health() is True
    assert calls == [(path.resolve().as_uri() + "?mode=ro", {"timeout": 5.0, "uri": True})]
    assert "PRAGMA query_only = ON;" in statements
    assert "PRAGMA query_only;" in statements
    assert "PRAGMA quick_check;" in statements
    assert all(not statement.upper().startswith(("CREATE", "INSERT", "UPDATE", "DELETE")) for statement in statements)


def test_database_health_does_not_require_write_access(tmp_path, monkeypatch):
    path = tmp_path / "readonly.db"
    _database(path)
    real_connect = sqlite3.connect

    def connect(database, *args, **kwargs):
        assert database.endswith("?mode=ro")
        assert kwargs["uri"] is True
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(supervisor, "DB_PATH", str(path))
    monkeypatch.setattr(supervisor.sqlite3, "connect", connect)
    assert supervisor.check_database_health() is True


def test_missing_database_retains_acceptable_first_write_behavior(
    tmp_path, monkeypatch, caplog
):
    path = tmp_path / "not-created-yet.db"
    monkeypatch.setattr(supervisor, "DB_PATH", str(path))
    with caplog.at_level(logging.WARNING, logger=supervisor.logger.name):
        assert supervisor.check_database_health() is True
    assert "DB_FILE_MISSING" in caplog.text
    assert str(path.resolve()) in caplog.text
    assert not path.exists()


def test_inaccessible_database_parent_fails_with_precise_classification(
    tmp_path, monkeypatch, caplog
):
    path = tmp_path / "monitor.db"
    _database(path)
    monkeypatch.setattr(supervisor, "DB_PATH", str(path))
    monkeypatch.setattr(supervisor.os, "access", lambda *_args: False)
    with caplog.at_level(logging.CRITICAL, logger=supervisor.logger.name):
        assert supervisor.check_database_health() is False
    assert "DB_PARENT_INACCESSIBLE" in caplog.text
    assert str(path.resolve()) in caplog.text


def test_failed_quick_check_fails_closed(tmp_path, monkeypatch, caplog):
    path = tmp_path / "monitor.db"
    _database(path)

    class Cursor:
        def execute(self, _statement):
            return self

        @staticmethod
        def fetchone():
            return (1,)

        @staticmethod
        def fetchall():
            return [("page 2 is corrupt",)]

    class Connection:
        @staticmethod
        def cursor():
            return Cursor()

        @staticmethod
        def close():
            return None

    monkeypatch.setattr(supervisor, "DB_PATH", str(path))
    monkeypatch.setattr(supervisor.sqlite3, "connect", lambda *_a, **_k: Connection())
    with caplog.at_level(logging.CRITICAL, logger=supervisor.logger.name):
        assert supervisor.check_database_health() is False
    assert "SQLITE_QUICK_CHECK_FAILED" in caplog.text
    assert str(path.resolve()) in caplog.text


def test_corrupt_database_fails_closed(tmp_path, monkeypatch, caplog):
    path = tmp_path / "corrupt.db"
    path.write_bytes(b"not a sqlite database")
    monkeypatch.setattr(supervisor, "DB_PATH", str(path))
    with caplog.at_level(logging.CRITICAL, logger=supervisor.logger.name):
        assert supervisor.check_database_health() is False
    assert "SQLITE_DATABASE_CORRUPTION" in caplog.text
    assert str(path.resolve()) in caplog.text


def test_read_only_connect_exception_is_precisely_classified(
    tmp_path, monkeypatch, caplog
):
    path = tmp_path / "monitor.db"
    _database(path)
    monkeypatch.setattr(supervisor, "DB_PATH", str(path))
    monkeypatch.setattr(
        supervisor.sqlite3,
        "connect",
        lambda *_a, **_k: (_ for _ in ()).throw(
            sqlite3.OperationalError("unable to open database file")
        ),
    )
    with caplog.at_level(logging.CRITICAL, logger=supervisor.logger.name):
        assert supervisor.check_database_health() is False
    assert "SQLITE_READ_ONLY_CONNECT_FAILED" in caplog.text
    assert "SQLITE_OPERATIONAL_LOCK_OR_ACCESS_ERROR" in caplog.text
    assert str(path.resolve()) in caplog.text


def test_health_endpoint_200_passes_immediately_without_warning(monkeypatch, caplog):
    calls = []

    def urlopen(request, timeout):
        calls.append((request.full_url, timeout))
        return _Response(200)

    monkeypatch.setattr(supervisor.urllib.request, "urlopen", urlopen)
    with caplog.at_level(logging.DEBUG, logger=supervisor.logger.name):
        assert supervisor.check_api_health() is True
    assert calls == [(f"http://{supervisor.API_HOST}:{supervisor.API_PORT}/health", 5)]
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_status_endpoint_can_pass_after_health_failure(monkeypatch, caplog):
    def urlopen(request, timeout):
        if request.full_url.endswith("/health"):
            raise urllib.error.HTTPError(request.full_url, 503, "unavailable", {}, None)
        return _Response(200)

    monkeypatch.setattr(supervisor.urllib.request, "urlopen", urlopen)
    with caplog.at_level(logging.DEBUG, logger=supervisor.logger.name):
        assert supervisor.check_api_health() is True
    assert "HTTP_STATUS_503" in caplog.text
    assert "HTTP_HEALTH_FAILED_SOCKET_REACHABLE" not in caplog.text


def test_http_failures_with_reachable_socket_pass_and_warn(monkeypatch, caplog):
    monkeypatch.setattr(
        supervisor.urllib.request,
        "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(
            urllib.error.URLError(ConnectionRefusedError())
        ),
    )
    monkeypatch.setattr(
        supervisor.socket,
        "create_connection",
        lambda *_a, **_k: nullcontext(),
        raising=False,
    )
    with caplog.at_level(logging.WARNING, logger=supervisor.logger.name):
        assert supervisor.check_api_health() is True
    assert "HTTP_HEALTH_FAILED_SOCKET_REACHABLE" in caplog.text
    assert f"host={supervisor.API_HOST}" in caplog.text
    assert f"port={supervisor.API_PORT}" in caplog.text
    assert "CONNECTION_REFUSED" in caplog.text


def test_http_and_socket_failures_fail_closed_without_secret_leak(
    monkeypatch, caplog
):
    secret = "Bearer SECRET_API_KEY_VALUE"
    monkeypatch.setattr(
        supervisor.urllib.request,
        "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(RuntimeError(secret)),
    )
    monkeypatch.setattr(
        supervisor.socket,
        "create_connection",
        lambda *_a, **_k: (_ for _ in ()).throw(ConnectionRefusedError(secret)),
        raising=False,
    )
    with caplog.at_level(logging.WARNING, logger=supervisor.logger.name):
        assert supervisor.check_api_health() is False
    assert "API_HEALTH_FAILED" in caplog.text
    assert "OTHER_RuntimeError" in caplog.text
    assert secret not in caplog.text


@pytest.mark.parametrize(
    ("api_ok", "db_ok", "expected"),
    ((True, True, 0), (False, True, 1), (True, False, 1)),
)
def test_check_once_exit_depends_only_on_api_and_database(
    monkeypatch, api_ok, db_ok, expected
):
    calls = []
    monkeypatch.setattr(supervisor, "check_api_health", lambda: api_ok)
    monkeypatch.setattr(supervisor, "check_database_health", lambda: db_ok)
    monkeypatch.setattr(
        supervisor, "check_scheduler_freshness", lambda: calls.append("scheduler")
    )
    assert supervisor.main(["--check-once"]) == expected
    assert calls == ["scheduler"]


def test_scheduler_no_run_warning_does_not_fail_check_once(monkeypatch):
    monkeypatch.setattr(supervisor, "check_api_health", lambda: True)
    monkeypatch.setattr(supervisor, "check_database_health", lambda: True)
    monkeypatch.setattr(supervisor, "check_scheduler_freshness", lambda: None)
    assert supervisor.main(["--check-once"]) == 0


def test_default_cli_still_invokes_infinite_supervisor(monkeypatch):
    calls = []
    monkeypatch.setattr(supervisor, "run_supervisor", lambda: calls.append("loop"))
    assert supervisor.main([]) == 0
    assert calls == ["loop"]


def test_monitor_systemd_sandbox_remains_strict_and_database_read_only():
    service = (
        Path(__file__).resolve().parents[1] / "infra/systemd/astra-monitor.service"
    ).read_text(encoding="utf-8")
    assert "ProtectSystem=strict" in service.splitlines()
    assert "ReadWritePaths=/var/log/astra" in service.splitlines()
    assert "ReadWritePaths=/opt/astra/memory_db" not in service
    assert "/opt/astra/memory_db" not in next(
        line for line in service.splitlines() if line.startswith("ReadWritePaths=")
    )

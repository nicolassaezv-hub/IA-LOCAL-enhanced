"""Fail-closed contracts for delegated monitor database health."""
from __future__ import annotations

from contextlib import nullcontext
import inspect
import json
import logging
from pathlib import Path
import sqlite3
import urllib.error

import pytest

from infra.db import database as database_module
from infra.monitor import supervisor


class _Response:
    def __init__(self, payload: dict, status: int = 200):
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def read(self, size: int = -1):
        return self._body if size < 0 else self._body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _sqlite_file(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE existing_state (id INTEGER PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()


def test_canonical_database_health_probe_is_non_mutating(tmp_path, monkeypatch):
    path = tmp_path / "health.db"
    _sqlite_file(path)
    real_connect = sqlite3.connect
    statements = []

    class Cursor:
        def __init__(self, cursor):
            self._cursor = cursor

        def execute(self, statement, *args):
            statements.append(statement.strip())
            self._cursor.execute(statement, *args)
            return self

        def fetchone(self):
            return self._cursor.fetchone()

        def fetchall(self):
            return self._cursor.fetchall()

    class Connection:
        def __init__(self, connection):
            self._connection = connection

        def cursor(self):
            return Cursor(self._connection.cursor())

        def close(self):
            self._connection.close()

    def connect(database_uri, *args, **kwargs):
        assert database_uri == path.resolve().as_uri() + "?mode=rw"
        assert kwargs["uri"] is True
        return Connection(real_connect(database_uri, *args, **kwargs))

    monkeypatch.setattr(database_module.sqlite3, "connect", connect)
    result = database_module.probe_database_health(path)

    assert result == {
        "state": "DB_HEALTH_PASS",
        "classification": "SQLITE_QUICK_CHECK_OK",
    }
    assert statements == [
        "PRAGMA query_only = ON;",
        "PRAGMA query_only;",
        "PRAGMA quick_check;",
    ]
    assert all(
        not statement.upper().startswith(("CREATE", "INSERT", "UPDATE", "DELETE"))
        for statement in statements
    )
    with real_connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert tables == {"existing_state"}
    assert "immutable=1" not in inspect.getsource(
        database_module.probe_database_health
    )


@pytest.mark.parametrize(
    ("payload", "expected_state"),
    (
        (
            {
                "state": "DB_HEALTH_PASS",
                "classification": "SQLITE_QUICK_CHECK_OK",
            },
            "DB_HEALTH_PASS",
        ),
        (
            {
                "state": "DB_HEALTH_FAILED",
                "classification": "SQLITE_DATABASE_CORRUPTION",
            },
            "DB_HEALTH_FAILED",
        ),
        (
            {
                "state": "DB_HEALTH_UNAVAILABLE",
                "classification": "SQLITE_CONNECT_FAILED",
            },
            "DB_HEALTH_UNAVAILABLE",
        ),
    ),
)
def test_monitor_consumes_delegated_database_states(
    monkeypatch, payload, expected_state
):
    monkeypatch.setattr(
        supervisor.urllib.request,
        "urlopen",
        lambda request, timeout: _Response(payload),
    )
    result = supervisor.check_delegated_database_health()
    assert result["state"] == expected_state
    assert result["classification"] == payload["classification"]


def test_delegated_database_transport_failure_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        supervisor.urllib.request,
        "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(
            urllib.error.URLError(ConnectionRefusedError())
        ),
    )
    assert supervisor.check_delegated_database_health() == {
        "state": "DB_HEALTH_UNAVAILABLE",
        "classification": "API_UNREACHABLE",
    }


def test_strict_daemon_never_runs_direct_database_probe(monkeypatch):
    monkeypatch.setattr(supervisor, "check_api_health", lambda **_kwargs: True)
    monkeypatch.setattr(
        supervisor,
        "check_delegated_database_health",
        lambda: {
            "state": "DB_HEALTH_PASS",
            "classification": "SQLITE_QUICK_CHECK_OK",
        },
    )
    monkeypatch.setattr(
        supervisor,
        "check_database_health",
        lambda: (_ for _ in ()).throw(AssertionError("direct DB probe used")),
    )
    monkeypatch.setattr(supervisor, "check_scheduler_freshness", lambda: None)

    result = supervisor.run_monitor_cycle(startup_grace=False)

    assert result["api"] == "API_HEALTH_PASS"
    assert result["database"] == "DB_HEALTH_PASS"


def test_explicit_delegated_database_failure_alerts(monkeypatch, caplog):
    monkeypatch.setattr(supervisor, "check_api_health", lambda **_kwargs: True)
    monkeypatch.setattr(
        supervisor,
        "check_delegated_database_health",
        lambda: {
            "state": "DB_HEALTH_FAILED",
            "classification": "SQLITE_QUICK_CHECK_FAILED",
        },
    )
    monkeypatch.setattr(supervisor, "check_scheduler_freshness", lambda: None)
    with caplog.at_level(logging.CRITICAL, logger=supervisor.logger.name):
        result = supervisor.run_monitor_cycle(startup_grace=False)
    assert result["database"] == "DB_HEALTH_FAILED"
    assert "DB_HEALTH_FAILED" in caplog.text
    assert "SQLITE_QUICK_CHECK_FAILED" in caplog.text


def test_delegated_database_unavailable_is_not_declared_healthy(
    monkeypatch, caplog
):
    monkeypatch.setattr(supervisor, "check_api_health", lambda **_kwargs: True)
    monkeypatch.setattr(
        supervisor,
        "check_delegated_database_health",
        lambda: {
            "state": "DB_HEALTH_UNAVAILABLE",
            "classification": "INVALID_HEALTH_RESPONSE",
        },
    )
    monkeypatch.setattr(supervisor, "check_scheduler_freshness", lambda: None)
    with caplog.at_level(logging.WARNING, logger=supervisor.logger.name):
        result = supervisor.run_monitor_cycle(startup_grace=False)
    assert result["database"] == "DB_HEALTH_UNAVAILABLE"
    assert "DB_HEALTH_UNAVAILABLE" in caplog.text
    assert "DB_HEALTH_PASS" not in caplog.text


def test_api_unreachable_is_distinct_and_skips_delegated_probe(
    monkeypatch, caplog
):
    delegated_calls = []
    monkeypatch.setattr(supervisor, "check_api_health", lambda **_kwargs: False)
    monkeypatch.setattr(
        supervisor,
        "check_delegated_database_health",
        lambda: delegated_calls.append(True),
    )
    monkeypatch.setattr(supervisor, "check_scheduler_freshness", lambda: None)
    with caplog.at_level(logging.ERROR, logger=supervisor.logger.name):
        result = supervisor.run_monitor_cycle(startup_grace=False)
    assert result == {
        "api": "API_UNREACHABLE",
        "database": "DB_HEALTH_UNAVAILABLE",
    }
    assert delegated_calls == []
    assert "API_UNREACHABLE" in caplog.text


def test_startup_connection_refused_grace_has_no_error(monkeypatch, caplog):
    monkeypatch.setattr(supervisor, "check_api_health", lambda **_kwargs: False)
    monkeypatch.setattr(supervisor, "check_scheduler_freshness", lambda: None)
    with caplog.at_level(logging.INFO, logger=supervisor.logger.name):
        result = supervisor.run_monitor_cycle(startup_grace=True)
    assert result["api"] == "API_UNREACHABLE"
    assert "API_STARTUP_GRACE" in caplog.text
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert 30 <= supervisor.STARTUP_GRACE_SECONDS <= 60


def test_real_connection_refused_classification_is_info_during_grace(
    monkeypatch, caplog
):
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
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionRefusedError()),
    )
    with caplog.at_level(logging.INFO, logger=supervisor.logger.name):
        assert supervisor.check_api_health(startup_grace=True) is False
    assert "API_STARTUP_GRACE" in caplog.text
    assert "CONNECTION_REFUSED" in caplog.text
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_api_failure_after_startup_grace_alerts_normally(monkeypatch, caplog):
    monkeypatch.setattr(supervisor, "check_api_health", lambda **_kwargs: False)
    monkeypatch.setattr(supervisor, "check_scheduler_freshness", lambda: None)
    with caplog.at_level(logging.ERROR, logger=supervisor.logger.name):
        supervisor.run_monitor_cycle(startup_grace=False)
    assert "API_UNREACHABLE" in caplog.text
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_check_once_remains_immediate_and_uses_direct_probe(monkeypatch):
    calls = []

    def api_health(*, startup_grace=False):
        calls.append(("api", startup_grace))
        return False

    monkeypatch.setattr(supervisor, "check_api_health", api_health)
    monkeypatch.setattr(
        supervisor,
        "check_database_health",
        lambda: calls.append(("direct_db", None)) or True,
    )
    monkeypatch.setattr(supervisor, "check_scheduler_freshness", lambda: None)
    assert supervisor.main(["--check-once"]) == 1
    assert calls == [("api", False), ("direct_db", None)]


def test_scheduler_disabled_logs_once_without_stale_warnings(monkeypatch, caplog):
    monkeypatch.setenv("ASTRA_SCHEDULER_ENABLED", "false")
    monkeypatch.setattr(supervisor, "_scheduler_disabled_logged", False)
    monkeypatch.setattr(
        supervisor,
        "get_last_scheduler_run_time",
        lambda _timeframe: (_ for _ in ()).throw(
            AssertionError("freshness queried while disabled")
        ),
    )
    with caplog.at_level(logging.INFO, logger=supervisor.logger.name):
        supervisor.check_scheduler_freshness()
        supervisor.check_scheduler_freshness()
    assert caplog.text.count("SCHEDULER_MONITORING_DISABLED") == 1
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_scheduler_enabled_retains_freshness_warning(monkeypatch, caplog):
    monkeypatch.setenv("ASTRA_SCHEDULER_ENABLED", "true")
    monkeypatch.setattr(supervisor, "SCHEDULER_THRESHOLDS", {"H1": 3600})
    monkeypatch.setattr(
        supervisor,
        "get_last_scheduler_run_time",
        lambda _timeframe: supervisor.datetime.now() - supervisor.timedelta(hours=2),
    )
    with caplog.at_level(logging.WARNING, logger=supervisor.logger.name):
        supervisor.check_scheduler_freshness()
    assert "H1 scheduler delay detected" in caplog.text


def test_database_health_endpoint_is_minimal_public_and_secret_safe(
    monkeypatch,
):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from workspace import server

    secret = "DO_NOT_EXPOSE_DATABASE_SECRET"
    monkeypatch.setenv("ASTRA_API_KEY", "required-api-secret")
    monkeypatch.setattr(
        server,
        "probe_database_health",
        lambda: {
            "state": "DB_HEALTH_PASS",
            "classification": "SQLITE_QUICK_CHECK_OK",
            "contents": secret,
            "path": secret,
        },
    )
    with TestClient(server.app) as client:
        response = client.get("/api/health/database")
        ordinary_health = client.get("/health")
        monkeypatch.setattr(
            server,
            "probe_database_health",
            lambda: {
                "state": "DB_HEALTH_FAILED",
                "classification": "SQLITE_QUICK_CHECK_FAILED",
                "contents": secret,
            },
        )
        failed = client.get("/api/health/database")
    assert response.status_code == 200
    assert response.json() == {
        "state": "DB_HEALTH_PASS",
        "classification": "SQLITE_QUICK_CHECK_OK",
    }
    assert secret not in response.text
    assert "required-api-secret" not in response.text
    assert ordinary_health.json() == {"status": "ok"}
    assert failed.status_code == 503
    assert failed.json() == {
        "state": "DB_HEALTH_FAILED",
        "classification": "SQLITE_QUICK_CHECK_FAILED",
    }
    assert secret not in failed.text


def test_monitor_systemd_stays_strict_without_database_write_access():
    root = Path(__file__).resolve().parents[1]
    service = (root / "infra/systemd/astra-monitor.service").read_text(
        encoding="utf-8"
    )
    supervisor_source = (root / "infra/monitor/supervisor.py").read_text(
        encoding="utf-8"
    )
    assert "ProtectSystem=strict" in service.splitlines()
    writable = next(
        line for line in service.splitlines() if line.startswith("ReadWritePaths=")
    )
    assert writable == "ReadWritePaths=/var/log/astra"
    assert "/opt/astra/memory_db" not in writable
    assert "immutable=1" not in supervisor_source

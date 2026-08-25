from __future__ import annotations

import importlib
import sqlite3
import sys
import types

import pytest

from infra.db import database
from infra.db.database import SQLiteDatabase


class _TrackedConnection:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection
        self.closed = False
        self.rollback_calls = 0

    @property
    def row_factory(self):
        return self._connection.row_factory

    @row_factory.setter
    def row_factory(self, value):
        self._connection.row_factory = value

    def execute(self, *args, **kwargs):
        return self._connection.execute(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        return self._connection.executescript(*args, **kwargs)

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        self.rollback_calls += 1
        return self._connection.rollback()

    def close(self):
        self.closed = True
        return self._connection.close()


def _track_connections(monkeypatch):
    real_connect = sqlite3.connect
    opened = []

    def tracked_connect(*args, **kwargs):
        connection = _TrackedConnection(real_connect(*args, **kwargs))
        opened.append(connection)
        return connection

    monkeypatch.setattr(database.sqlite3, "connect", tracked_connect)
    return opened


def test_sqlite_database_releases_file_for_immediate_deletion(tmp_path):
    db_path = tmp_path / "release.db"
    db = SQLiteDatabase(str(db_path))

    db.add_symbol("EURUSD", "EUR/USD", 0.0001)
    assert db.get_symbol("EURUSD")["status"] == "candidate"
    assert db.get_supported_symbols() == []

    db_path.unlink()
    assert not db_path.exists()


def test_sqlite_database_closes_and_rolls_back_after_operation_error(
    tmp_path, monkeypatch
):
    opened = _track_connections(monkeypatch)
    db_path = tmp_path / "rollback.db"
    db = SQLiteDatabase(str(db_path))
    run = db.create_scheduler_run({"timeframe": "H1"})

    with pytest.raises(sqlite3.OperationalError):
        db.update_scheduler_run(run["id"], {"missing_column": "value"})

    failed_connection = opened[-1]
    assert failed_connection.rollback_calls == 1
    assert db.get_scheduler_runs()[0]["status"] == "running"
    assert all(connection.closed for connection in opened)
    db_path.unlink()


def test_sqlite_database_consecutive_operations_do_not_accumulate_handles(
    tmp_path, monkeypatch
):
    opened = _track_connections(monkeypatch)
    db = SQLiteDatabase(str(tmp_path / "consecutive.db"))

    from forex.data.symbol_catalog import SYMBOL_CATALOG

    for spec in list(SYMBOL_CATALOG.values())[:25]:
        db.register_candidate(
            spec.symbol_code, spec.display_name, spec.asset_class, spec.pip_value
        )
        db.get_symbols_by_status("candidate")
        assert all(connection.closed for connection in opened)

    assert len(opened) > 25
    assert all(connection.closed for connection in opened)


def test_creando_import_uses_existing_canonical_market_symbols(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    module = importlib.import_module("creando")

    assert "EURUSD" in module.MT5_SYMBOLS
    assert module.to_yfinance_ticker("EURUSD") == "EURUSD=X"


def test_yahoo_provider_public_aliases_reference_canonical_objects():
    from forex.data import yahoo_provider

    assert yahoo_provider.FOREX_TICKER_MAP is yahoo_provider._FOREX_TICKER_MAP
    assert yahoo_provider.to_yahoo_ticker is yahoo_provider._to_yahoo_ticker


def test_forex_prediction_exports_canonical_model_selector(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    prediction = importlib.import_module("forex.prediction")

    assert prediction.ModelSelector is prediction.ModelSelectionEngine
    assert prediction._HAS_ROADMAP_V is True


def test_main_loads_required_roadmap_modules(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    main = importlib.import_module("main")

    assert main._HAS_ROADMAP_V is True
    assert main._HAS_ROADMAP_VI is True


def test_optional_news_state_uses_canonical_module_and_degrades_explicitly(
    monkeypatch,
):
    from forex.prediction import prediction_context

    canonical_module = types.ModuleType("news_intelligence")
    monkeypatch.setitem(sys.modules, "news_intelligence", canonical_module)

    with pytest.raises(RuntimeError, match="does not expose"):
        prediction_context._news_state("EURUSD")

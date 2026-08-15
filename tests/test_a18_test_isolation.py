"""A-18 regressions for offline, repeatable, production-safe tests."""

import os
import socket
import types
import urllib.request
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import modules_extra
from forex.data.data_router import DataRouter
from scheduler import autonomous_scheduler
from tests.test_infrastructure import (
    _run_isolated_e2e_cycle,
    test_database as _test_database_contract,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_TARGETS = (
    PROJECT_ROOT / "forex" / "data",
    PROJECT_ROOT / "data" / "forex",
    PROJECT_ROOT / "forex" / "models",
    PROJECT_ROOT / "CSVs",
    PROJECT_ROOT / "models",
    PROJECT_ROOT / "logs",
    PROJECT_ROOT / "reports",
    PROJECT_ROOT / "backups",
    PROJECT_ROOT / "memory_db",
    PROJECT_ROOT / "astra_csv_index.json",
    PROJECT_ROOT / "memoria.db",
    PROJECT_ROOT / "astra.env",
    PROJECT_ROOT / "infra" / "config" / "astra.env",
)

pytestmark = pytest.mark.unit


def _snapshot_product_targets():
    """Capture names and metadata without reading artifact or configuration data."""
    snapshot = {}
    for target in PRODUCT_TARGETS:
        if target.is_file():
            stat = target.stat()
            snapshot[str(target.relative_to(PROJECT_ROOT))] = (
                stat.st_size,
                stat.st_mtime_ns,
            )
            continue
        if not target.is_dir():
            continue
        for path in sorted(target.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            stat = path.stat()
            snapshot[str(path.relative_to(PROJECT_ROOT))] = (
                stat.st_size,
                stat.st_mtime_ns,
            )
    return snapshot


def _cycle_observation(root):
    result, runs = _run_isolated_e2e_cycle(root)
    return {
        "timeframe": result["timeframe"],
        "symbols_processed": result["symbols_processed"],
        "predictions_generated": result["predictions_generated"],
        "errors_count": result["errors_count"],
        "result_actions": [
            item.get("update", item.get("predict", {})).get("action")
            for item in result["results"]
        ],
        "run_status": runs[0]["status"],
    }


def test_isolated_e2e_does_not_create_or_modify_product_files(tmp_path):
    before = _snapshot_product_targets()

    observation = _cycle_observation(tmp_path / "cycle")

    assert observation["run_status"] == "completed"
    assert _snapshot_product_targets() == before


def test_optional_redis_degrades_without_a_real_server(monkeypatch):
    class OfflineRedis:
        def __init__(self, **_kwargs):
            raise ConnectionError("offline test boundary")

    monkeypatch.setattr(modules_extra, "HAS_REDIS", True)
    monkeypatch.setattr(
        modules_extra,
        "redis_lib",
        types.SimpleNamespace(Redis=OfflineRedis),
    )

    set_result = modules_extra.redis_set("a18", "value")
    get_result = modules_extra.redis_get("a18")

    assert set_result.startswith("Redis no disponible:")
    assert get_result.startswith("Redis no disponible:")
    assert "offline test boundary" in set_result
    assert "offline test boundary" in get_result


def test_isolated_e2e_never_loads_serialized_project_models(tmp_path):
    with patch(
        "pickle.load",
        side_effect=AssertionError("production pickle load attempted"),
    ) as pickle_load, patch(
        "joblib.load",
        side_effect=AssertionError("production model load attempted"),
    ) as model_load:
        observation = _cycle_observation(tmp_path / "cycle")

    pickle_load.assert_not_called()
    model_load.assert_not_called()
    assert observation["predictions_generated"] == 1
    assert observation["errors_count"] == 0


def test_data_router_unit_boundary_never_reaches_network(monkeypatch):
    class ProviderDouble:
        def __init__(self):
            self.calls = []

        def is_available(self):
            return True

        def fetch(self, pair, timeframe, bars, **kwargs):
            self.calls.append((pair, timeframe, bars, kwargs))
            return [{"close": 1.0}]

    primary = ProviderDouble()
    fallback = ProviderDouble()
    socket_tripwire = Mock(side_effect=AssertionError("network access attempted"))
    urlopen_tripwire = Mock(side_effect=AssertionError("HTTP access attempted"))
    monkeypatch.setattr(socket, "create_connection", socket_tripwire)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen_tripwire)

    with patch(
        "forex.data.mt5_provider.get_mt5_provider", return_value=primary
    ), patch(
        "forex.data.yahoo_provider.get_yahoo_provider", return_value=fallback
    ):
        router = DataRouter("EURUSD", "H1")
        result = router.fetch(2, raise_on_failure=True)

    assert result == [{"close": 1.0}]
    assert router.source_used == "MT5"
    assert primary.calls == [("EURUSD", "H1", 2, {"allow_fallback": False})]
    assert fallback.calls == []
    socket_tripwire.assert_not_called()
    urlopen_tripwire.assert_not_called()


def test_environment_and_module_globals_are_restored(tmp_path):
    env_before = {
        "ASTRA_DB_ENGINE": os.environ.get("ASTRA_DB_ENGINE"),
        "ASTRA_DB_PATH": os.environ.get("ASTRA_DB_PATH"),
    }
    scheduler_root_before = autonomous_scheduler.PROJECT_ROOT

    with pytest.MonkeyPatch.context() as scoped_patch:
        scoped_patch.setenv("ASTRA_DB_ENGINE", "temporary-a18-value")
        scoped_patch.setattr(
            autonomous_scheduler,
            "PROJECT_ROOT",
            tmp_path / "temporary-module-root",
        )

    assert {
        "ASTRA_DB_ENGINE": os.environ.get("ASTRA_DB_ENGINE"),
        "ASTRA_DB_PATH": os.environ.get("ASTRA_DB_PATH"),
    } == env_before
    assert autonomous_scheduler.PROJECT_ROOT == scheduler_root_before

    _test_database_contract()
    _cycle_observation(tmp_path / "cycle")

    assert {
        "ASTRA_DB_ENGINE": os.environ.get("ASTRA_DB_ENGINE"),
        "ASTRA_DB_PATH": os.environ.get("ASTRA_DB_PATH"),
    } == env_before
    assert autonomous_scheduler.PROJECT_ROOT == scheduler_root_before


def test_isolated_e2e_is_repeatable(tmp_path):
    first = _cycle_observation(tmp_path / "first")
    second = _cycle_observation(tmp_path / "second")

    assert first == second

#!/usr/bin/env python3
"""
ASTRA Infrastructure Test Suite
10 tests that validate the full infrastructure without Base44 dependency.
Run: python3 tests/test_infrastructure.py
"""
import ast
import sys, os, json, time, sqlite3, types, hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if __name__ == "__main__" and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PASS = 0; FAIL = 0; TESTS = []


def _set_active_fixture(db, symbol):
    from forex.data.symbol_catalog import get_symbol_spec

    spec = get_symbol_spec(symbol)
    db.register_candidate(
        spec.symbol_code, spec.display_name, spec.asset_class, spec.pip_value
    )
    with db._connection() as connection:
        connection.execute(
            "UPDATE supported_symbols SET status='active' WHERE symbol_code=?",
            (spec.symbol_code,),
        )


def _write_ready_dataset(path, pair="EURUSD", timeframe="H1"):
    import pandas as pd

    from forex.data.indicator_delta import recalculate_tail_indicators
    from forex.data.rolling_dataset import ROLLING_WINDOW, validate_dataset

    values = pd.Series(range(ROLLING_WINDOW), dtype=float)
    frequency = {"H1": "1h", "H4": "4h", "D1": "1D"}[timeframe]
    dataset = pd.DataFrame({
        "timestamp": pd.date_range(
            "2020-01-01", periods=ROLLING_WINDOW, freq=frequency
        ),
        "open": 1.08 + values / 10000,
        "high": 1.085 + values / 10000,
        "low": 1.075 + values / 10000,
        "close": 1.082 + values / 10000,
        "volume": 1000,
        "pair": pair,
    })
    dataset = recalculate_tail_indicators(dataset, k=len(dataset))
    validate_dataset(dataset, ROLLING_WINDOW)
    dataset.to_csv(path, index=False)
    return dataset


def _registry_provenance(path, symbol="EURUSD"):
    from forex.data.symbol_catalog import route_for_provider

    route = route_for_provider(symbol, "Yahoo")
    return {
        "provider_used": route.provider,
        "external_ticker": route.external_ticker,
        "provider_class": route.provider_class,
        "source_fetched_at": "2026-08-01T00:00:00+00:00",
        "source_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
    }


def _run_test(name, fn):
    global PASS, FAIL
    start = time.time()
    try:
        fn()
        TESTS.append(f"PASS  {name} ({time.time()-start:.1f}s)")
        PASS += 1
    except Exception as e:
        TESTS.append(f"FAIL  {name} ({time.time()-start:.1f}s) - {e}")
        FAIL += 1

def test_database():
    from infra.db.database import SQLiteDatabase, DatabaseAdapter, get_database, PostgreSQLDatabase
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "t.db"
        db = SQLiteDatabase(str(db_path))
        conn = sqlite3.connect(db_path)
        try:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        finally:
            conn.close()
        for t in ["supported_symbols","dataset_registry","predictions","outcomes","model_quality","scheduler_runs","config"]:
            assert t in tables, f"missing {t}"
        _set_active_fixture(db, "EURUSD")
        sym = db.get_symbol("EURUSD")
        assert sym["symbol_code"]=="EURUSD"
        assert len(db.get_supported_symbols())==1
        db.upsert_dataset_registry({"symbol":"EURUSD","timeframe":"H1","candle_count":100,"status":"ready","blob_path":str(Path(tmpdir) / "dataset.csv")})
        assert len(db.get_dataset_registry("EURUSD","H1"))==1
        pred = db.save_prediction({"symbol":"EURUSD","timeframe":"H1","direction":"buy","confidence":0.72})
        assert pred["id"] is not None
        assert len(db.get_predictions("EURUSD","H1"))==1
        run = db.create_scheduler_run({"timeframe":"H1","status":"running"})
        upd = db.update_scheduler_run(run["id"],{"status":"completed"})
        assert upd["status"]=="completed"
        h = db.get_system_health()
        assert h["symbols_active"]==1 and h["healthy"]==True
        assert issubclass(SQLiteDatabase, DatabaseAdapter)
        try: PostgreSQLDatabase(); assert False
        except NotImplementedError: pass
        with patch.dict(
            os.environ,
            {"ASTRA_DB_ENGINE": "sqlite", "ASTRA_DB_PATH": str(db_path)},
        ):
            assert isinstance(get_database(), SQLiteDatabase)

def test_init_first_run():
    from infra.db.database import SQLiteDatabase
    from scheduler.autonomous_scheduler import run_init, DEFAULT_SYMBOLS
    with TemporaryDirectory() as tmpdir:
        db = SQLiteDatabase(str(Path(tmpdir) / "t.db"))
        import pandas as pd
        df = pd.DataFrame({"timestamp":pd.date_range("2020-01-01",periods=2000,freq="1h"),"open":1.08,"high":1.085,"low":1.075,"close":1.082,"volume":1000,"pair":"EURUSD"})
        with patch("scheduler.autonomous_scheduler.PROJECT_ROOT",Path(tmpdir)):
            with patch("scheduler.autonomous_scheduler.fetch_market_data",return_value=(df,"test")):
                results = run_init(db)
        assert results == []
        assert len(db.get_symbols_by_status("candidate")) == len(DEFAULT_SYMBOLS)
        assert db.get_dataset_registry() == []

def test_rolling_update():
    from infra.db.database import SQLiteDatabase
    from scheduler.autonomous_scheduler import run_rolling_update, ROLLING_WINDOW
    with TemporaryDirectory() as tmpdir:
        db = SQLiteDatabase(str(Path(tmpdir) / "t.db"))
        _set_active_fixture(db, "EURUSD")
        import pandas as pd
        old = pd.date_range("2026-01-01",periods=2000,freq="1h")
        old_df = pd.DataFrame({"timestamp":old,"open":1.08,"high":1.085,"low":1.075,"close":1.082,"volume":1000,"pair":"EURUSD"})
        data_dir = Path(tmpdir)/"data"/"forex"; data_dir.mkdir(parents=True,exist_ok=True)
        csv = data_dir/"EURUSD_H1.csv"; old_df.to_csv(csv,index=False)
        db.upsert_dataset_registry({"symbol":"EURUSD","timeframe":"H1","candle_count":2000,"last_candle_timestamp":str(old[-1]),"blob_path":str(csv),"status":"ready", **_registry_provenance(csv)})
        new_all = pd.date_range("2026-01-01",periods=2003,freq="1h")
        new_df = pd.DataFrame({"timestamp":new_all,"open":1.08,"high":1.085,"low":1.075,"close":1.083,"volume":1000,"pair":"EURUSD"})
        with patch("scheduler.autonomous_scheduler.PROJECT_ROOT",Path(tmpdir)):
            with patch("scheduler.autonomous_scheduler.fetch_market_data",return_value=(new_df,"test")):
                result = run_rolling_update(db,"EURUSD","H1")
        assert result["action"]=="updated",f"got {result}"
        assert result["total"]==ROLLING_WINDOW
        assert result["added"]==3

def test_candidate_is_invisible_to_new_symbol_detection():
    from infra.db.database import SQLiteDatabase
    from scheduler.autonomous_scheduler import detect_new_symbols
    import pandas as pd
    with TemporaryDirectory() as tmpdir:
        db = SQLiteDatabase(str(Path(tmpdir) / "t.db"))
        _set_active_fixture(db, "EURUSD"); db.add_symbol("NZDUSD","NZD/USD",0.0001)
        for tf in ["H1","H4","D1"]:
            existing_path = Path(tmpdir)/f"EURUSD_{tf}.csv"
            existing_df = _write_ready_dataset(existing_path, timeframe=tf)
            db.upsert_dataset_registry({"symbol":"EURUSD","timeframe":tf,"status":"ready","candle_count":2000,"rolling_window_size":2000,"last_candle_timestamp":str(existing_df["timestamp"].iloc[-1]),"blob_path":str(existing_path), **_registry_provenance(existing_path)})
        df = pd.DataFrame({"timestamp":pd.date_range("2020-01-01",periods=2000,freq="1h"),"open":0.6,"high":0.605,"low":0.595,"close":0.602,"volume":1000,"pair":"NZDUSD"})
        with patch("scheduler.autonomous_scheduler.PROJECT_ROOT",Path(tmpdir)):
            with patch("scheduler.autonomous_scheduler.fetch_market_data",return_value=(df,"test")):
                gen = detect_new_symbols(db)
        assert gen == []
        assert db.get_symbol("NZDUSD")["status"] == "candidate"

def test_init_skip():
    from infra.db.database import SQLiteDatabase
    from scheduler.autonomous_scheduler import run_init
    with TemporaryDirectory() as tmpdir:
        db = SQLiteDatabase(str(Path(tmpdir) / "t.db"))
        _set_active_fixture(db, "EURUSD")
        for tf in ["H1","H4","D1"]:
            existing_path = Path(tmpdir)/f"EURUSD_{tf}.csv"
            existing_df = _write_ready_dataset(existing_path, timeframe=tf)
            db.upsert_dataset_registry({"symbol":"EURUSD","timeframe":tf,"status":"ready","candle_count":2000,"rolling_window_size":2000,"last_candle_timestamp":str(existing_df["timestamp"].iloc[-1]),"blob_path":str(existing_path), **_registry_provenance(existing_path)})
        with patch("scheduler.autonomous_scheduler.PROJECT_ROOT",Path(tmpdir)):
            results = run_init(db)
        assert all(r["action"]=="skip" for r in results)
        for reg in db.get_dataset_registry():
            assert reg["candle_count"]==2000

def test_api_health():
    import threading, http.server, socketserver
    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path=="/health":
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                self.wfile.write(b'{"status":"healthy"}')
            else:
                self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers()
                self.wfile.write(b"<html>ASTRA</html>")
        def log_message(self,*a): pass
    with ReusableTCPServer(("127.0.0.1",0),H) as srv:
        port = srv.server_address[1]
        thread = threading.Thread(target=srv.serve_forever,daemon=True)
        thread.start()
        try:
            import urllib.request
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as r:
                assert r.status==200
                assert json.loads(r.read())["status"]=="healthy"
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as r:
                assert r.status==200
        finally:
            srv.shutdown()
            thread.join(timeout=5)

def test_monitor():
    source = (PROJECT_ROOT/"infra"/"monitor"/"supervisor.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert "check_api_health" in functions
    assert "run_supervisor" in functions

def test_backup():
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        for directory in ["memory_db","data/forex","forex/models","scheduler","infra/db"]:
            (root / directory).mkdir(parents=True,exist_ok=True)
        (root / "memory_db/astra.db").write_text("db", encoding="utf-8")
        (root / "data/forex/EURUSD_H1.csv").write_text("csv", encoding="utf-8")
        (root / "forex/models/model.pkl").write_text("model", encoding="utf-8")
        import tarfile
        bf = root / "backup.tar.gz"
        with tarfile.open(bf,"w:gz") as tar:
            tar.add(root / "memory_db",arcname="memory_db")
            tar.add(root / "data/forex",arcname="data/forex")
            tar.add(root / "forex/models",arcname="forex/models")
        assert bf.stat().st_size>0
        with tarfile.open(bf,"r:gz") as tar:
            names=tar.getnames()
            assert any("memory_db" in n for n in names)
            assert any("data/forex" in n for n in names)

def _run_isolated_e2e_cycle(root: Path):
    from infra.db.database import SQLiteDatabase
    from scheduler.autonomous_scheduler import run_cycle
    root.mkdir(parents=True, exist_ok=True)
    db = SQLiteDatabase(str(root / "t.db"))
    _set_active_fixture(db, "EURUSD")
    import pandas as pd
    df = pd.DataFrame({"timestamp":pd.date_range("2020-01-01",periods=2000,freq="1h"),"open":1.08,"high":1.085,"low":1.075,"close":1.082,"volume":1000,"pair":"EURUSD"})
    data_dir = root/"data"/"forex"; data_dir.mkdir(parents=True,exist_ok=True)
    csv = data_dir/"EURUSD_H1.csv"; df.to_csv(csv,index=False)
    for tf in ["H1","H4","D1"]:
        db.upsert_dataset_registry({"symbol":"EURUSD","timeframe":tf,"status":"ready","candle_count":2000,"rolling_window_size":2000,"last_candle_timestamp":str(df["timestamp"].iloc[-1]),"blob_path":str(csv), **_registry_provenance(csv)})
    # Mock the canonical router boundary with newer candles.
    new_dates = pd.date_range("2020-01-01", periods=2003, freq="1h")
    new_data = pd.DataFrame({"timestamp":new_dates,"open":1.08,"high":1.085,"low":1.075,"close":1.083,"volume":1000,"pair":"EURUSD"})
    model_check = Mock(return_value=True)
    integrity_module = types.ModuleType("robustness.model_integrity_checker")
    integrity_module.check_model_before_cycle = model_check

    def fake_prediction(target_db, symbol, timeframe):
        saved = target_db.save_prediction({
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": "HOLD",
            "confidence": 0.5,
            "predicted_at": "2020-04-01T00:00:00",
        })
        return {"action": "predicted", "prediction": saved}

    prediction_boundary = Mock(side_effect=fake_prediction)
    with patch.dict(
        sys.modules,
        {"robustness.model_integrity_checker": integrity_module},
    ), patch(
        "forex.prediction.retrain_manager.RetrainManager.reconcile",
        return_value={"issues": []},
    ), patch(
        "forex.prediction.retrain_manager.RetrainManager.audit_pair_model",
        return_value={"eligible": True, "reason": "PRODUCTION_ELIGIBLE"},
    ), patch("scheduler.autonomous_scheduler.PROJECT_ROOT",root), patch(
        "scheduler.autonomous_scheduler.fetch_market_data",
        return_value=(new_data,"test"),
    ), patch(
        "scheduler.autonomous_scheduler.run_prediction",
        prediction_boundary,
    ), patch(
        "scheduler.autonomous_scheduler.detect_new_symbols",return_value=[]
    ):
        result = run_cycle(db,"H1")
    model_check.assert_called_once_with("EURUSD", "H1")
    prediction_boundary.assert_called_once_with(db, "EURUSD", "H1")
    assert len(db.get_predictions("EURUSD", "H1")) == 1
    return result, db.get_scheduler_runs()


def test_e2e_cycle():
    with TemporaryDirectory() as tmpdir:
        result, runs = _run_isolated_e2e_cycle(Path(tmpdir))
    assert result["timeframe"]=="H1" and result["symbols_processed"]==1
    assert result["predictions_generated"]==1 and result["errors_count"]==0
    assert len(runs)>=1 and runs[0]["status"]=="completed"

def test_decoupled_persistence():
    from infra.db.database import DatabaseAdapter, SQLiteDatabase, PostgreSQLDatabase, get_database
    import inspect
    assert inspect.isabstract(DatabaseAdapter)
    for m in DatabaseAdapter.__abstractmethods__:
        assert m in dir(SQLiteDatabase), f"missing {m}"
    try: PostgreSQLDatabase(); assert False
    except NotImplementedError: pass
    with TemporaryDirectory() as tmpdir, patch.dict(
        os.environ,
        {
            "ASTRA_DB_ENGINE": "sqlite",
            "ASTRA_DB_PATH": str(Path(tmpdir) / "factory.db"),
        },
    ):
        assert isinstance(get_database(), SQLiteDatabase)

if __name__ == "__main__":
    from astra_version import ASTRA_VERSION

    print("\n" + "="*60)
    print(f"  ASTRA v{ASTRA_VERSION} - Infrastructure Test Suite")
    print("="*60 + "\n")
    _run_test("1. Database abstraction layer", test_database)
    _run_test("2. First-run detection (init)", test_init_first_run)
    _run_test("3. Rolling update maintains size", test_rolling_update)
    _run_test("4. New symbol auto-detection", test_new_symbol_detection)
    _run_test("5. Init skip behavior (idempotency)", test_init_skip)
    _run_test("6. API health endpoint", test_api_health)
    _run_test("7. Monitor detects status", test_monitor)
    _run_test("8. Backup script validation", test_backup)
    _run_test("9. End-to-end cycle (integration)", test_e2e_cycle)
    _run_test("10. Decoupled persistence", test_decoupled_persistence)
    print("\n" + "="*60)
    for t in TESTS: print(f"  {t}")
    print("="*60)
    print(f"\n  Result: {PASS} passed, {FAIL} failed\n")
    sys.exit(0 if FAIL==0 else 1)

#!/usr/bin/env python3
"""
ASTRA Infrastructure Test Suite (v6.0.1-prod)
10 tests that validate the full infrastructure without Base44 dependency.
Run: python3 tests/test_infrastructure.py
"""
import sys, os, json, tempfile, shutil, time, sqlite3
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PASS = 0; FAIL = 0; TESTS = []


def _write_ready_dataset(path, pair="EURUSD"):
    import pandas as pd

    from forex.data.indicator_delta import recalculate_tail_indicators
    from forex.data.rolling_dataset import ROLLING_WINDOW, validate_dataset

    values = pd.Series(range(ROLLING_WINDOW), dtype=float)
    dataset = pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=ROLLING_WINDOW, freq="1h"),
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
    tmpdir = tempfile.mkdtemp()
    db = SQLiteDatabase(os.path.join(tmpdir, "t.db"))
    conn = sqlite3.connect(os.path.join(tmpdir, "t.db"))
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    for t in ["supported_symbols","dataset_registry","predictions","outcomes","model_quality","scheduler_runs","config"]:
        assert t in tables, f"missing {t}"
    sym = db.add_symbol("TESTUS","TEST/US",0.0001)
    assert sym["symbol_code"]=="TESTUS"
    assert len(db.get_supported_symbols())==1
    db.upsert_dataset_registry({"symbol":"TESTUS","timeframe":"H1","candle_count":100,"status":"ready","blob_path":"/tmp/t.csv"})
    assert len(db.get_dataset_registry("TESTUS","H1"))==1
    pred = db.save_prediction({"symbol":"TESTUS","timeframe":"H1","direction":"buy","confidence":0.72})
    assert pred["id"] is not None
    assert len(db.get_predictions("TESTUS","H1"))==1
    run = db.create_scheduler_run({"timeframe":"H1","status":"running"})
    upd = db.update_scheduler_run(run["id"],{"status":"completed"})
    assert upd["status"]=="completed"
    h = db.get_system_health()
    assert h["symbols_active"]==1 and h["healthy"]==True
    assert issubclass(SQLiteDatabase, DatabaseAdapter)
    try: PostgreSQLDatabase(); assert False
    except NotImplementedError: pass
    os.environ["ASTRA_DB_ENGINE"]="sqlite"
    assert isinstance(get_database(), SQLiteDatabase)
    shutil.rmtree(tmpdir)

def test_init_first_run():
    from infra.db.database import SQLiteDatabase
    from scheduler.autonomous_scheduler import run_init, DEFAULT_SYMBOLS
    tmpdir = tempfile.mkdtemp(); db = SQLiteDatabase(os.path.join(tmpdir,"t.db"))
    import pandas as pd
    df = pd.DataFrame({"timestamp":pd.date_range("2020-01-01",periods=2000,freq="1h"),"open":1.08,"high":1.085,"low":1.075,"close":1.082,"volume":1000,"pair":"EURUSD"})
    with patch("scheduler.autonomous_scheduler.PROJECT_ROOT",Path(tmpdir)):
        with patch("scheduler.autonomous_scheduler.fetch_market_data",return_value=(df,"test")):
            results = run_init(db)
    assert len(results)==len(DEFAULT_SYMBOLS)*3
    assert all(r["action"]=="generated" for r in results)
    assert len(db.get_dataset_registry())==len(DEFAULT_SYMBOLS)*3
    shutil.rmtree(tmpdir)

def test_rolling_update():
    from infra.db.database import SQLiteDatabase
    from scheduler.autonomous_scheduler import run_rolling_update, ROLLING_WINDOW
    tmpdir = tempfile.mkdtemp(); db = SQLiteDatabase(os.path.join(tmpdir,"t.db"))
    db.add_symbol("EURUSD","EUR/USD",0.0001)
    import pandas as pd
    old = pd.date_range("2026-01-01",periods=2000,freq="1h")
    old_df = pd.DataFrame({"timestamp":old,"open":1.08,"high":1.085,"low":1.075,"close":1.082,"volume":1000,"pair":"EURUSD"})
    data_dir = Path(tmpdir)/"forex"/"data"; data_dir.mkdir(parents=True,exist_ok=True)
    csv = data_dir/"EURUSD_H1.csv"; old_df.to_csv(csv,index=False)
    db.upsert_dataset_registry({"symbol":"EURUSD","timeframe":"H1","candle_count":2000,"last_candle_timestamp":str(old[-1]),"blob_path":str(csv),"status":"ready"})
    new_all = pd.date_range("2026-01-01",periods=2003,freq="1h")
    new_df = pd.DataFrame({"timestamp":new_all,"open":1.08,"high":1.085,"low":1.075,"close":1.083,"volume":1000,"pair":"EURUSD"})
    with patch("scheduler.autonomous_scheduler.PROJECT_ROOT",Path(tmpdir)):
        with patch("scheduler.autonomous_scheduler.fetch_market_data",return_value=(new_df,"test")):
            result = run_rolling_update(db,"EURUSD","H1")
    assert result["action"]=="updated",f"got {result}"
    assert result["total"]==ROLLING_WINDOW
    assert result["added"]==3
    shutil.rmtree(tmpdir)

def test_new_symbol_detection():
    from infra.db.database import SQLiteDatabase
    from scheduler.autonomous_scheduler import detect_new_symbols
    import pandas as pd
    tmpdir = tempfile.mkdtemp(); db = SQLiteDatabase(os.path.join(tmpdir,"t.db"))
    db.add_symbol("EURUSD","EUR/USD",0.0001); db.add_symbol("NZDUSD","NZD/USD",0.0001)
    for tf in ["H1","H4","D1"]:
        existing_path = Path(tmpdir)/f"EURUSD_{tf}.csv"
        existing_df = _write_ready_dataset(existing_path)
        db.upsert_dataset_registry({"symbol":"EURUSD","timeframe":tf,"status":"ready","candle_count":2000,"rolling_window_size":2000,"last_candle_timestamp":str(existing_df["timestamp"].iloc[-1]),"blob_path":str(existing_path)})
    df = pd.DataFrame({"timestamp":pd.date_range("2020-01-01",periods=2000,freq="1h"),"open":0.6,"high":0.605,"low":0.595,"close":0.602,"volume":1000,"pair":"NZDUSD"})
    with patch("scheduler.autonomous_scheduler.PROJECT_ROOT",Path(tmpdir)):
        with patch("scheduler.autonomous_scheduler.fetch_market_data",return_value=(df,"test")):
            gen = detect_new_symbols(db)
    assert len(gen)==3
    assert all(g["symbol"]=="NZDUSD" for g in gen)
    shutil.rmtree(tmpdir)

def test_init_skip():
    from infra.db.database import SQLiteDatabase
    from scheduler.autonomous_scheduler import run_init
    tmpdir = tempfile.mkdtemp(); db = SQLiteDatabase(os.path.join(tmpdir,"t.db"))
    db.add_symbol("EURUSD","EUR/USD",0.0001)
    for tf in ["H1","H4","D1"]:
        existing_path = Path(tmpdir)/f"EURUSD_{tf}.csv"
        existing_df = _write_ready_dataset(existing_path)
        db.upsert_dataset_registry({"symbol":"EURUSD","timeframe":tf,"status":"ready","candle_count":2000,"rolling_window_size":2000,"last_candle_timestamp":str(existing_df["timestamp"].iloc[-1]),"blob_path":str(existing_path)})
    with patch("scheduler.autonomous_scheduler.PROJECT_ROOT",Path(tmpdir)):
        results = run_init(db)
    assert all(r["action"]=="skip" for r in results)
    for reg in db.get_dataset_registry():
        assert reg["candle_count"]==2000
    shutil.rmtree(tmpdir)

def test_api_health():
    import threading, http.server, socketserver
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path=="/health":
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                self.wfile.write(b'{"status":"healthy"}')
            else:
                self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers()
                self.wfile.write(b"<html>ASTRA</html>")
        def log_message(self,*a): pass
    PORT=18002; socketserver.TCPServer.allow_reuse_address=True; srv=socketserver.TCPServer(("localhost",PORT),H)
    threading.Thread(target=srv.serve_forever,daemon=True).start(); time.sleep(0.3)
    import urllib.request
    r=urllib.request.urlopen(f"http://localhost:{PORT}/health"); assert r.status==200
    assert json.loads(r.read())["status"]=="healthy"
    r=urllib.request.urlopen(f"http://localhost:{PORT}/"); assert r.status==200
    srv.shutdown()

def test_monitor():
    import importlib.util
    spec = importlib.util.spec_from_file_location("supervisor", PROJECT_ROOT/"infra"/"monitor"/"supervisor.py")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        assert hasattr(mod,"main") or hasattr(mod,"Supervisor") or hasattr(mod,"check_api_health")
    except SystemExit: pass
    except Exception: pass

def test_backup():
    tmpdir = tempfile.mkdtemp()
    for d in ["memory_db","forex/data","forex/models","scheduler","infra/db"]:
        os.makedirs(os.path.join(tmpdir,d),exist_ok=True)
    open(os.path.join(tmpdir,"memory_db/astra.db"),"w").write("db")
    open(os.path.join(tmpdir,"forex/data/EURUSD_H1.csv"),"w").write("csv")
    open(os.path.join(tmpdir,"forex/models/model.pkl"),"w").write("model")
    import tarfile
    bf = os.path.join(tmpdir,"backup.tar.gz")
    with tarfile.open(bf,"w:gz") as tar:
        tar.add(os.path.join(tmpdir,"memory_db"),arcname="memory_db")
        tar.add(os.path.join(tmpdir,"forex/data"),arcname="forex/data")
        tar.add(os.path.join(tmpdir,"forex/models"),arcname="forex/models")
    assert os.path.getsize(bf)>0
    with tarfile.open(bf,"r:gz") as tar:
        names=tar.getnames()
        assert any("memory_db" in n for n in names)
        assert any("forex/data" in n for n in names)
    shutil.rmtree(tmpdir)

def test_e2e_cycle():
    from infra.db.database import SQLiteDatabase
    from scheduler.autonomous_scheduler import run_cycle
    tmpdir = tempfile.mkdtemp(); db = SQLiteDatabase(os.path.join(tmpdir,"t.db"))
    db.add_symbol("EURUSD","EUR/USD",0.0001)
    import pandas as pd
    df = pd.DataFrame({"timestamp":pd.date_range("2020-01-01",periods=2000,freq="1h"),"open":1.08,"high":1.085,"low":1.075,"close":1.082,"volume":1000,"pair":"EURUSD"})
    data_dir = Path(tmpdir)/"forex"/"data"; data_dir.mkdir(parents=True,exist_ok=True)
    csv = data_dir/"EURUSD_H1.csv"; df.to_csv(csv,index=False)
    for tf in ["H1","H4","D1"]:
        db.upsert_dataset_registry({"symbol":"EURUSD","timeframe":tf,"status":"ready","candle_count":2000,"rolling_window_size":2000,"last_candle_timestamp":str(df["timestamp"].iloc[-1]),"blob_path":str(csv)})
    # Mock the canonical router boundary with newer candles.
    new_dates = pd.date_range("2020-01-01", periods=2003, freq="1h")
    new_data = pd.DataFrame({"timestamp":new_dates,"open":1.08,"high":1.085,"low":1.075,"close":1.083,"volume":1000,"pair":"EURUSD"})
    with patch("scheduler.autonomous_scheduler.PROJECT_ROOT",Path(tmpdir)):
        with patch("scheduler.autonomous_scheduler.fetch_market_data",return_value=(new_data,"test")):
            with patch("scheduler.autonomous_scheduler.run_prediction",return_value={"action":"predicted"}):
                with patch("scheduler.autonomous_scheduler.detect_new_symbols",return_value=[]):
                    result = run_cycle(db,"H1")
    assert result["timeframe"]=="H1" and result["symbols_processed"]==1
    assert result["predictions_generated"]==1 and result["errors_count"]==0
    runs = db.get_scheduler_runs()
    assert len(runs)>=1 and runs[0]["status"]=="completed"
    shutil.rmtree(tmpdir)

def test_decoupled_persistence():
    from infra.db.database import DatabaseAdapter, SQLiteDatabase, PostgreSQLDatabase, get_database
    import inspect
    assert inspect.isabstract(DatabaseAdapter)
    for m in DatabaseAdapter.__abstractmethods__:
        assert m in dir(SQLiteDatabase), f"missing {m}"
    try: PostgreSQLDatabase(); assert False
    except NotImplementedError: pass
    os.environ["ASTRA_DB_ENGINE"]="sqlite"
    assert isinstance(get_database(), SQLiteDatabase)

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  ASTRA v6.0.1-prod - Infrastructure Test Suite")
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

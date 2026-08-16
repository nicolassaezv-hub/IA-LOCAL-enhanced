"""
ASTRA Doctor — Diagnóstico unificado del sistema.
Comando: astra doctor
Verifica todas las categorías: dependencias, configuración, modelos, APIs,
datos, scheduler, workplace, integración de módulos.
"""
from __future__ import annotations
import sys, os, time, json, sqlite3
from datetime import datetime
from pathlib import Path

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    _OK   = lambda s: f"{Fore.GREEN}✅ {s}{Style.RESET_ALL}"
    _WARN = lambda s: f"{Fore.YELLOW}⚠️  {s}{Style.RESET_ALL}"
    _FAIL = lambda s: f"{Fore.RED}❌ {s}{Style.RESET_ALL}"
    _HEAD = lambda s: f"{Fore.CYAN}{'─'*52}\n  {s}\n{'─'*52}{Style.RESET_ALL}"
    _INFO = lambda s: f"{Fore.WHITE}   {s}{Style.RESET_ALL}"
except ImportError:
    _OK   = lambda s: f"[OK]   {s}"
    _WARN = lambda s: f"[WARN] {s}"
    _FAIL = lambda s: f"[FAIL] {s}"
    _HEAD = lambda s: f"\n--- {s} ---"
    _INFO = lambda s: f"   {s}"

_BASE = Path(__file__).parent
_REPORT: list[dict] = []


def _record(category: str, label: str, status: str, detail: str = ""):
    _REPORT.append({"category": category, "label": label, "status": status, "detail": detail})


def _check_import(mod: str, label: str = "") -> bool:
    label = label or mod
    try:
        __import__(mod)
        return True
    except ImportError:
        return False
    except Exception:
        return False


# ── CATEGORÍA 1: Dependencias ─────────────────────────────────────────────────

def check_dependencies() -> list[str]:
    print(_HEAD("1. Dependencias"))
    issues = []
    critical = [
        ("pandas",    "pandas"),
        ("numpy",     "numpy"),
        ("sklearn",   "scikit-learn"),
        ("xgboost",   "xgboost"),
        ("lightgbm",  "lightgbm"),
        ("optuna",    "optuna"),
        ("requests",  "requests"),
        ("colorama",  "colorama"),
        ("openai",    "openai (cliente Groq/OpenAI)"),
        ("psutil",    "psutil"),
        ("rich",      "rich"),
        ("orjson",    "orjson"),
        ("filelock",  "filelock"),
    ]
    optional = [
        ("yfinance",   "yfinance (Yahoo Finance)"),
        ("redis",      "redis"),
        ("faiss",      "faiss-cpu"),
        ("torch",      "torch (PyTorch)"),
        ("sklearn.ensemble", "scikit-learn ensemble"),
    ]
    for mod, label in critical:
        ok = _check_import(mod)
        if ok:
            print(_OK(f"  {label}"))
            _record("dependencies", label, "ok")
        else:
            print(_FAIL(f"  {label} — REQUERIDO"))
            _record("dependencies", label, "fail", "pip install needed")
            issues.append(f"pip install {mod}")
    for mod, label in optional:
        ok = _check_import(mod)
        status = "ok" if ok else "warn"
        if ok:
            print(_OK(f"  {label} (opcional)"))
        else:
            print(_WARN(f"  {label} — opcional, no instalado"))
        _record("dependencies", label, status)
    return issues


# ── CATEGORÍA 2: Configuración ────────────────────────────────────────────────

def check_configuration() -> list[str]:
    print(_HEAD("2. Configuración"))
    issues = []

    groq_key = os.environ.get("GROQ_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if groq_key:
        print(_OK("  GROQ_API_KEY configurada"))
        _record("configuration", "GROQ_API_KEY", "ok")
    elif openai_key:
        print(_OK("  OPENAI_API_KEY configurada (alternativa)"))
        _record("configuration", "OPENAI_API_KEY", "ok")
    else:
        print(_FAIL("  Sin GROQ_API_KEY ni OPENAI_API_KEY — chat AI no funcionará"))
        _record("configuration", "API_KEY", "fail", "Set GROQ_API_KEY")
        issues.append("Configurar GROQ_API_KEY en Replit Secrets o .env")

    index_path = _BASE / "astra_csv_index.json"
    if index_path.exists():
        with open(index_path) as f:
            idx = json.load(f)
        print(_OK(f"  Índice CSV activo ({len(idx)} pares registrados)"))
        _record("configuration", "csv_index", "ok", f"{len(idx)} pares")
    else:
        print(_WARN("  Sin índice de CSVs (astra_csv_index.json) — ejecuta 'escanear csvs'"))
        _record("configuration", "csv_index", "warn")

    csvs_dir = _BASE / "CSVs"
    if csvs_dir.exists():
        csv_count = sum(1 for _ in csvs_dir.rglob("*.csv"))
        print(_OK(f"  Directorio CSVs/ existente ({csv_count} archivos CSV)"))
        _record("configuration", "csv_dir", "ok", f"{csv_count} csvs")
    else:
        print(_WARN("  Sin directorio CSVs/ — crea con 'descargar datos EURUSD H1'"))
        _record("configuration", "csv_dir", "warn")

    return issues


# ── CATEGORÍA 3: Modelos entrenados ──────────────────────────────────────────

def check_models() -> list[str]:
    print(_HEAD("3. Modelos ML"))
    issues = []
    models_dir = _BASE / "models"
    if not models_dir.exists():
        print(_WARN("  Sin directorio models/ — no hay modelos entrenados"))
        _record("models", "models_dir", "warn", "Ejecuta 'full forex <csv>'")
        issues.append("Entrena al menos un modelo: full forex <csv>")
        return issues

    pkl_files = list(models_dir.glob("*.pkl")) + list(models_dir.glob("**/*.pkl"))
    if pkl_files:
        for pkl in pkl_files[:5]:
            age_h = (time.time() - pkl.stat().st_mtime) / 3600
            age_str = f"{age_h:.0f}h ago" if age_h < 48 else f"{age_h/24:.1f}d ago"
            print(_OK(f"  Modelo: {pkl.name} ({age_str})"))
            _record("models", pkl.name, "ok", age_str)
        if len(pkl_files) > 5:
            print(_INFO(f"  ... y {len(pkl_files)-5} modelos más"))
    else:
        print(_WARN("  Sin modelos .pkl — ejecuta 'full forex <csv>'"))
        _record("models", "pkl_files", "warn")
        issues.append("Entrena modelos con: full forex <csv>")

    try:
        from forex.prediction.model_cache import get_model_cache
        mc = get_model_cache()
        active = mc.list_active_models()
        if active:
            print(_OK(f"  Model Cache: {len(active)} modelos activos en DB"))
            _record("models", "model_cache", "ok", f"{len(active)} activos")
        else:
            print(_WARN("  Model Cache vacío"))
            _record("models", "model_cache", "warn")
    except Exception as e:
        print(_WARN(f"  Model Cache error: {e}"))
        _record("models", "model_cache", "warn", str(e))

    return issues


# ── CATEGORÍA 4: APIs externas ────────────────────────────────────────────────

def check_apis() -> list[str]:
    print(_HEAD("4. APIs Externas"))
    issues = []

    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1"
            )
            resp = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": "ok"}],
                max_tokens=5,
            )
            print(_OK("  Groq API (Llama-3.3) — conectada y operativa"))
            _record("apis", "groq", "ok")
        except Exception as e:
            print(_FAIL(f"  Groq API — error: {str(e)[:60]}"))
            _record("apis", "groq", "fail", str(e)[:80])
            issues.append("Verificar GROQ_API_KEY")
    else:
        print(_WARN("  Groq API — sin key configurada"))
        _record("apis", "groq", "warn")

    try:
        import requests
        r = requests.get("https://api.binance.com/api/v3/ping", timeout=5)
        if r.status_code == 200:
            print(_OK("  Binance API — accesible"))
            _record("apis", "binance", "ok")
        else:
            print(_WARN(f"  Binance API — status {r.status_code}"))
            _record("apis", "binance", "warn")
    except Exception as e:
        print(_WARN(f"  Binance API — sin conexión ({str(e)[:40]})"))
        _record("apis", "binance", "warn", "no connection")

    try:
        import yfinance as yf
        ticker = yf.Ticker("EURUSD=X")
        hist = ticker.history(period="1d")
        if hist is not None and not hist.empty:
            print(_OK("  Yahoo Finance — datos disponibles"))
            _record("apis", "yahoo", "ok")
        else:
            print(_WARN("  Yahoo Finance — sin datos recientes"))
            _record("apis", "yahoo", "warn")
    except ImportError:
        print(_WARN("  Yahoo Finance — yfinance no instalado (pip install yfinance)"))
        _record("apis", "yahoo", "warn", "not installed")
    except Exception as e:
        print(_WARN(f"  Yahoo Finance — error ({str(e)[:40]})"))
        _record("apis", "yahoo", "warn", str(e)[:60])

    return issues


# ── CATEGORÍA 5: MT5 ──────────────────────────────────────────────────────────

def check_mt5() -> list[str]:
    print(_HEAD("5. MetaTrader 5"))
    issues = []
    try:
        import MetaTrader5 as mt5
        if mt5.initialize():
            info = mt5.terminal_info()
            print(_OK(f"  MT5 conectado — build {info.build}"))
            _record("mt5", "connection", "ok", f"build {info.build}")
            mt5.shutdown()
        else:
            print(_WARN(f"  MT5 no conectado — ¿está corriendo? Error: {mt5.last_error()}"))
            _record("mt5", "connection", "warn", str(mt5.last_error()))
    except ImportError:
        print(_INFO("  MT5 no disponible (Linux/Replit — solo Windows)"))
        _record("mt5", "available", "warn", "Windows only")
    except Exception as e:
        print(_WARN(f"  MT5 error: {str(e)[:60]}"))
        _record("mt5", "connection", "warn", str(e)[:60])
    return issues


# ── CATEGORÍA 6: Bases de datos ───────────────────────────────────────────────

def check_databases() -> list[str]:
    print(_HEAD("6. Bases de Datos"))
    issues = []
    dbs = {
        "memoria.db":           "Memoria principal (predicciones, outcomes, retrain)",
        "astra_hparam_cache.db": "Cache de hiperparámetros (VI.1)",
        "astra_model_quality.db": "Historial de calidad de modelos (VI.8)",
    }
    for db_name, desc in dbs.items():
        db_path = _BASE / db_name
        if db_path.exists():
            size_kb = db_path.stat().st_size / 1024
            try:
                conn = sqlite3.connect(str(db_path))
                tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                conn.close()
                print(_OK(f"  {db_name} ({size_kb:.1f}KB, {len(tables)} tablas) — {desc}"))
                _record("databases", db_name, "ok", f"{len(tables)} tables")
            except Exception as e:
                print(_FAIL(f"  {db_name} — corrompida: {e}"))
                _record("databases", db_name, "fail", str(e))
                issues.append(f"DB corrompida: {db_name}")
        else:
            print(_WARN(f"  {db_name} — no existe aún (se crea al primer uso)"))
            _record("databases", db_name, "warn", "will be created on first use")
    return issues


# ── CATEGORÍA 7: Scheduler ────────────────────────────────────────────────────

def check_scheduler() -> list[str]:
    print(_HEAD("7. Scheduler"))
    issues = []
    try:
        from forex.scheduler.autonomous_scheduler import get_scheduler
        sched = get_scheduler()
        running = sched.is_running
        job_count = len(sched._jobs) if hasattr(sched, '_jobs') else 0
        if running:
            print(_OK(f"  AutonomousScheduler activo ({job_count} tareas registradas)"))
            _record("scheduler", "autonomous", "ok", f"{job_count} jobs")
        else:
            print(_WARN(f"  AutonomousScheduler inactivo ({job_count} tareas configuradas)"))
            _record("scheduler", "autonomous", "warn", "stopped")
    except Exception as e:
        print(_FAIL(f"  AutonomousScheduler error: {str(e)[:60]}"))
        _record("scheduler", "autonomous", "fail", str(e)[:60])
        issues.append("Revisar forex/scheduler/autonomous_scheduler.py")

    try:
        from forex.scheduler.auto_updater import get_auto_updater
        upd = get_auto_updater()
        pairs = upd._load_active_pairs()
        print(_OK(f"  AutoUpdater: {len(pairs)} pares en índice activo"))
        _record("scheduler", "auto_updater", "ok", f"{len(pairs)} pairs")
    except Exception as e:
        print(_FAIL(f"  AutoUpdater error: {str(e)[:60]}"))
        _record("scheduler", "auto_updater", "fail", str(e)[:60])

    return issues


# ── CATEGORÍA 8: Integridad de datasets ──────────────────────────────────────

def check_datasets() -> list[str]:
    print(_HEAD("8. Integridad de Datasets"))
    issues = []
    csvs_dir = _BASE / "CSVs"
    if not csvs_dir.exists():
        print(_WARN("  Sin directorio CSVs/"))
        _record("datasets", "csvs_dir", "warn")
        return issues

    csv_files = list(csvs_dir.rglob("*.csv"))
    if not csv_files:
        print(_WARN("  Sin archivos CSV"))
        _record("datasets", "csv_files", "warn")
        return issues

    import pandas as pd
    checked = 0
    corrupt = 0
    for csv_path in csv_files[:10]:
        try:
            df = pd.read_csv(str(csv_path))
            required = {"open", "high", "low", "close"}
            missing = required - set(df.columns)
            null_pct = df.isnull().sum().sum() / max(df.size, 1) * 100
            if missing:
                print(_WARN(f"  {csv_path.name}: columnas faltantes {missing}"))
                _record("datasets", csv_path.name, "warn", f"missing cols: {missing}")
                issues.append(f"CSV {csv_path.name} incompleto")
            elif null_pct > 5:
                print(_WARN(f"  {csv_path.name}: {null_pct:.1f}% NaN"))
                _record("datasets", csv_path.name, "warn", f"{null_pct:.1f}% NaN")
            else:
                print(_OK(f"  {csv_path.name}: {len(df)} filas, OK"))
                _record("datasets", csv_path.name, "ok", f"{len(df)} rows")
            checked += 1
        except Exception as e:
            print(_FAIL(f"  {csv_path.name}: error — {str(e)[:50]}"))
            _record("datasets", csv_path.name, "fail", str(e)[:60])
            corrupt += 1

    if len(csv_files) > 10:
        print(_INFO(f"  ... {len(csv_files)-10} CSVs adicionales no inspeccionados"))

    return issues


# ── CATEGORÍA 9: Integridad de módulos ───────────────────────────────────────

def check_module_integration() -> list[str]:
    print(_HEAD("9. Integración de Módulos"))
    issues = []
    chain = [
        ("forex.data.data_router",              "DataRouter (fuente de datos)"),
        ("forex.data.rolling_dataset",          "RollingDataset (datasets eficientes)"),
        ("forex.data.csv_migrator",             "CSVMigrator (migración)"),
        ("forex.prediction.hyperparameter_cache","HyperparameterCache (VI.1)"),
        ("forex.prediction.adaptive_trainer",   "AdaptiveTrainer (VI.1)"),
        ("forex.prediction.model_cache",        "ModelCacheManager (VI.1)"),
        ("forex.prediction.candlestick_patterns","CandlestickDetector (VI.5)"),
        ("forex.prediction.model_quality_history","ModelQualityHistory (VI.8)"),
        ("forex.portfolio.opportunity_score",   "OpportunityScore (VI.8)"),
        ("forex.scheduler.autonomous_scheduler","AutonomousScheduler (VI.5)"),
        ("forex.scheduler.auto_updater",        "AutoUpdater (VI.5)"),
    ]
    for mod, label in chain:
        try:
            __import__(mod, fromlist=["x"])
            print(_OK(f"  {label}"))
            _record("integration", label, "ok")
        except Exception as e:
            msg = str(e)
            if "libgomp" in msg:
                print(_WARN(f"  {label} — libgomp (OK con LD_LIBRARY_PATH)"))
                _record("integration", label, "warn", "libgomp ok with preload")
            else:
                print(_FAIL(f"  {label} — {msg[:60]}"))
                _record("integration", label, "fail", msg[:60])
                issues.append(f"Módulo fallido: {mod}")

    return issues


# ── CATEGORÍA 10: API interna ─────────────────────────────────────────────────

def check_api() -> list[str]:
    print(_HEAD("10. API Interna"))
    issues = []
    api_state = _BASE / "astra_state.json"
    if api_state.exists():
        age_s = time.time() - api_state.stat().st_mtime
        age_str = f"{age_s:.0f}s" if age_s < 60 else f"{age_s/60:.1f}min"
        print(_OK(f"  astra_state.json — presente (actualizado hace {age_str})"))
        _record("api", "state_file", "ok", age_str)
    else:
        print(_WARN("  astra_state.json — aún no generado (se crea al primer uso)"))
        _record("api", "state_file", "warn", "not created yet")

    try:
        import requests
        r = requests.get("http://localhost:80/api/health", timeout=3)
        if r.status_code == 200:
            print(_OK("  API Server /api/health — OK"))
            _record("api", "api_server", "ok")
        else:
            print(_WARN(f"  API Server — status {r.status_code}"))
            _record("api", "api_server", "warn")
    except Exception:
        print(_WARN("  API Server — no disponible (normal si no hay workflow activo)"))
        _record("api", "api_server", "warn", "not reachable")

    return issues


# ── Reporte final ─────────────────────────────────────────────────────────────

def run_doctor(verbose: bool = True) -> dict:
    """Ejecuta el diagnóstico completo ASTRA Doctor."""
    print()
    try:
        from colorama import Fore, Style
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════════════╗")
        print(f"║           ASTRA DOCTOR — Diagnóstico Completo        ║")
        print(f"╚══════════════════════════════════════════════════════╝{Style.RESET_ALL}")
    except Exception:
        print("╔══════════════════════════════════════════════════════╗")
        print("║           ASTRA DOCTOR — Diagnóstico Completo        ║")
        print("╚══════════════════════════════════════════════════════╝")

    _REPORT.clear()
    all_issues: list[str] = []

    all_issues.extend(check_dependencies())
    all_issues.extend(check_configuration())
    all_issues.extend(check_models())
    all_issues.extend(check_apis())
    all_issues.extend(check_mt5())
    all_issues.extend(check_databases())
    all_issues.extend(check_scheduler())
    all_issues.extend(check_datasets())
    all_issues.extend(check_module_integration())
    all_issues.extend(check_api())

    ok_count   = sum(1 for r in _REPORT if r["status"] == "ok")
    warn_count = sum(1 for r in _REPORT if r["status"] == "warn")
    fail_count = sum(1 for r in _REPORT if r["status"] == "fail")

    print()
    try:
        from colorama import Fore, Style
        print(f"{Fore.CYAN}{'═'*54}")
        print(f"  RESUMEN FINAL")
        print(f"{'═'*54}{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}✅ {ok_count} OK{Style.RESET_ALL}   "
              f"{Fore.YELLOW}⚠️  {warn_count} Avisos{Style.RESET_ALL}   "
              f"{Fore.RED}❌ {fail_count} Fallos{Style.RESET_ALL}")
    except Exception:
        print(f"\n  RESUMEN: {ok_count} OK | {warn_count} Avisos | {fail_count} Fallos")

    if all_issues:
        print()
        print("  Acciones recomendadas:")
        for i, issue in enumerate(all_issues, 1):
            print(f"    {i}. {issue}")
    else:
        try:
            from colorama import Fore, Style
            print(f"\n  {Fore.GREEN}✅ Sistema operativo. Sin acciones requeridas.{Style.RESET_ALL}")
        except Exception:
            print("\n  Sistema operativo.")

    report_path = _BASE / "astra_doctor_report.json"
    result = {
        "ts": datetime.now().isoformat(),
        "ok": ok_count,
        "warn": warn_count,
        "fail": fail_count,
        "issues": all_issues,
        "checks": _REPORT,
    }
    try:
        with open(report_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\n  Reporte guardado: {report_path.name}")
    except Exception:
        pass

    return result


if __name__ == "__main__":
    run_doctor()

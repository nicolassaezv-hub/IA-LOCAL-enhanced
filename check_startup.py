"""
ASTRA — Startup Diagnostic & Auto-Repair Script
================================================
Run this from your astra/ folder before launching main.py:

    python check_startup.py

What it does:
  1. Auto-fixes the lazy_loader.py naming conflict (attach/attach_stub issue)
  2. Auto-adds redis_delete to modules_extra.py if missing
  3. Tests every module import and reports pass/fail with exact errors
  4. Checks all heavy third-party packages
  5. Verifies the Forex + Business Intelligence pipeline
  6. Prints a final action checklist
"""

import sys
import os
import importlib
import traceback
import time
import ctypes
import subprocess

# Pre-load libgomp.so.1 so xgboost / lightgbm / faiss can find it on NixOS.
# Must happen before any of those packages are imported.
try:
    _gomp_path = subprocess.check_output(
        ["gcc", "-print-file-name=libgomp.so.1"],
        text=True, stderr=subprocess.DEVNULL
    ).strip()
    if _gomp_path and _gomp_path != "libgomp.so.1":
        ctypes.CDLL(_gomp_path)
except Exception:
    pass

# ── Color helpers (no deps needed) ───────────────────────────────────────────
try:
    from colorama import Fore, Style, init as _cinit
    _cinit(autoreset=True)
    def _ok(msg):  print(f"  {Fore.GREEN}[OK]{Style.RESET_ALL}  {msg}")
    def _err(msg): print(f"  {Fore.RED}[FAIL]{Style.RESET_ALL} {msg}")
    def _warn(msg):print(f"  {Fore.YELLOW}[WARN]{Style.RESET_ALL} {msg}")
    def _fix(msg): print(f"  {Fore.CYAN}[FIX]{Style.RESET_ALL}  {msg}")
    def _head(msg):print(f"\n{Fore.GREEN}{'═'*60}\n{msg}\n{'═'*60}{Style.RESET_ALL}")
except ImportError:
    def _ok(msg):  print(f"  [OK]   {msg}")
    def _err(msg): print(f"  [FAIL] {msg}")
    def _warn(msg):print(f"  [WARN] {msg}")
    def _fix(msg): print(f"  [FIX]  {msg}")
    def _head(msg):print(f"\n{'='*60}\n{msg}\n{'='*60}")


# Keep track of issues for the final report
ISSUES   = []
WARNINGS = []
FIXED    = []


# ═══════════════════════════════════════════════════════════
#  PHASE 1 — AUTO-REPAIRS
# ═══════════════════════════════════════════════════════════

def phase1_autorepair():
    _head("PHASE 1 — Auto-Repair")

    here = os.path.dirname(os.path.abspath(__file__))

    # ── Fix 1: lazy_loader.py naming conflict ────────────────
    # scikit-image and librosa internally call lazy_loader.attach()
    # and lazy_loader.attach_stub(). If a local lazy_loader.py exists
    # in the same folder as main.py, Python picks it up first and those
    # calls fail with AttributeError.
    for bad_name, fixed_name in [
        ("lazy_loader.py",        "astra_lazy_loader.py"),
        ("lazy_loader_custom.py", "astra_lazy_loader_custom.py"),
    ]:
        bad_path   = os.path.join(here, bad_name)
        fixed_path = os.path.join(here, fixed_name)
        if os.path.exists(bad_path):
            try:
                os.rename(bad_path, fixed_path)
                _ok(f"Renamed {bad_name} → {fixed_name}  (lazy_loader conflict fixed)")
                FIXED.append(f"Renamed {bad_name} → {fixed_name}")
                # Remove cached bytecode so Python re-resolves lazy_loader
                pycache = os.path.join(here, "__pycache__")
                for f in os.listdir(pycache) if os.path.isdir(pycache) else []:
                    if "lazy_loader" in f:
                        try:
                            os.remove(os.path.join(pycache, f))
                        except Exception:
                            pass
            except Exception as e:
                _err(f"Could not rename {bad_name}: {e}")
                ISSUES.append(f"Manual fix needed: rename {bad_name} → {fixed_name}")
        elif os.path.exists(fixed_path):
            _ok(f"{fixed_name} already in place (no conflict)")
        else:
            _ok(f"No local {bad_name} found (no conflict)")

    # ── Fix 2: redis_delete missing from modules_extra.py ────
    # memory_router.py line 91 does: from modules_extra import redis_delete
    # but modules_extra.py only defines redis_set and redis_get.
    extras_path = os.path.join(here, "modules_extra.py")
    if os.path.exists(extras_path):
        with open(extras_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "redis_delete" not in content:
            patch = '''
def redis_delete(clave):
    r = redis.Redis(host='localhost', port=6379, db=0)
    result = r.delete(clave)
    return f"Eliminado de Redis: {clave}" if result else f"Clave no encontrada: {clave}"
'''
            # Insert before the comandos_extra dict
            if "# --- Diccionario de comandos ---" in content:
                content = content.replace(
                    "# --- Diccionario de comandos ---",
                    patch + "\n# --- Diccionario de comandos ---"
                )
            else:
                content = content + "\n" + patch
            with open(extras_path, "w", encoding="utf-8") as f:
                f.write(content)
            _ok("Added redis_delete() to modules_extra.py")
            FIXED.append("Added redis_delete() to modules_extra.py")
        else:
            _ok("redis_delete already defined in modules_extra.py")
    else:
        _warn("modules_extra.py not found in this directory")


# ═══════════════════════════════════════════════════════════
#  PHASE 2 — THIRD-PARTY PACKAGE CHECKS
# ═══════════════════════════════════════════════════════════

PACKAGES = [
    # (pip_name,          import_name,       critical?)
    ("colorama",          "colorama",         True),
    ("pandas",            "pandas",           True),
    ("numpy",             "numpy",            True),
    ("scikit-learn",      "sklearn",          True),
    ("xgboost",           "xgboost",          True),
    ("lightgbm",          "lightgbm",         True),
    ("optuna",            "optuna",           True),
    ("matplotlib",        "matplotlib",       True),
    ("seaborn",           "seaborn",          False),
    ("openpyxl",          "openpyxl",         True),
    ("PyPDF2",            "PyPDF2",           True),
    ("python-docx",       "docx",             True),
    ("pdfplumber",        "pdfplumber",       False),
    ("requests",          "requests",         True),
    ("beautifulsoup4",    "bs4",              True),
    ("deep-translator",   "deep_translator",  False),
    ("psutil",            "psutil",           True),
    ("tqdm",              "tqdm",             True),
    ("arrow",             "arrow",            False),
    ("orjson",            "orjson",           False),
    ("filelock",          "filelock",         False),
    ("watchdog",          "watchdog",         False),
    ("schedule",          "schedule",         False),
    ("rich",              "rich",             False),
    ("tabulate",          "tabulate",         False),
    ("reportlab",         "reportlab",        False),
    ("sympy",             "sympy",            False),
    ("faiss-cpu",         "faiss",            False),
    ("redis",             "redis",            False),
    ("SQLAlchemy",        "sqlalchemy",       False),
    ("PyJWT",             "jwt",              False),
    ("bcrypt",            "bcrypt",           False),
    ("cryptography",      "cryptography",     False),
    ("passlib",           "passlib",          False),
    ("paramiko",          "paramiko",         False),
    ("httpx",             "httpx",            False),
    ("aiohttp",           "aiohttp",          False),
    ("python-socketio",   "socketio",         False),
    ("fastapi",           "fastapi",          False),
    ("Flask",             "flask",            False),
    ("grpcio",            "grpc",             False),
    ("SpeechRecognition", "speech_recognition", False),
    ("pyttsx3",           "pyttsx3",          False),
    ("pydub",             "pydub",            False),
    ("sounddevice",       "sounddevice",      False),
    ("openai",            "openai",           False),
    # lazy-loader must come last (we just renamed the conflict above)
    ("lazy-loader",       "lazy_loader",      True),
    # These are large / slow — tested last
    ("torch",             "torch",            False),
    ("scikit-image",      "skimage",          False),
    ("librosa",           "librosa",          False),
    ("tensorflow",        "tensorflow",       False),
]


def phase2_packages():
    _head("PHASE 2 — Third-Party Package Imports")

    failed_critical = []
    failed_optional = []
    ok_count = 0

    for pip_name, import_name, critical in PACKAGES:
        try:
            mod = importlib.import_module(import_name)
            ver = getattr(mod, "__version__", "?")
            _ok(f"{pip_name:<28} {ver}")
            ok_count += 1
        except Exception as e:
            short_err = str(e).split("\n")[0][:80]
            if critical:
                _err(f"{pip_name:<28} CRITICAL — {short_err}")
                failed_critical.append((pip_name, import_name, short_err))
                ISSUES.append(f"pip install {pip_name}  [{short_err}]")
            else:
                _warn(f"{pip_name:<28} optional — {short_err}")
                failed_optional.append((pip_name, import_name, short_err))
                WARNINGS.append(f"{pip_name}: {short_err}")

    print(f"\n  Packages: {ok_count} OK, "
          f"{len(failed_critical)} critical failures, "
          f"{len(failed_optional)} optional failures")

    if failed_critical:
        print()
        _fix("Run this to fix critical packages:")
        pkgs = " ".join(p for p, _, _ in failed_critical)
        print(f"    pip install {pkgs}")


# ═══════════════════════════════════════════════════════════
#  PHASE 3 — APP MODULE IMPORTS
# ═══════════════════════════════════════════════════════════

APP_MODULES = [
    # (module_name,          description)
    ("memory",               "SQLite memory store"),
    ("argument_parser",      "Intent argument parser"),
    ("progress_utils",       "Progress bar utilities"),
    ("utils",                "System utilities"),
    ("security",             "Cryptography tools"),
    ("io_files",             "PDF / Word / Excel reader-writer"),
    ("web_tools",            "Web scraping & HTTP tools"),
    ("modules_extra",        "Faiss / LlamaIndex / Redis / SQLAlchemy"),
    ("memory_router",        "Unified memory router"),
    ("tool_registry",        "Central tool registry (all imports)"),
    ("intent_router",        "Intent classification"),
    ("tool_executor",        "Tool executor"),
    ("astra_agent",          "Main ASTRA agent"),
    ("ai_models",            "AI / ML models (torch, tf, sklearn)"),
    ("visualization",        "Charts & image processing (skimage)"),
    ("audio_video",          "Audio / speech / video (librosa)"),
    ("analytics_memory",     "Analytics memory store"),
    ("forex_analytics",      "Forex technical analytics"),
]

FOREX_MODULES = [
    ("forex.market_universe",                   "Market definitions + find_market"),
    ("forex.indicators",                        "Unified indicator layer (CCI/MFI/ROC/ATR-rel)"),
    ("forex.forex_memory",                      "Forex history store"),
    ("forex.prediction.csv_adapter",            "CSV normalizer + NaN imputation"),
    ("forex.prediction.feature_engineering",    "Feature builder (85 features + CCI/MFI/ROC/ATR)"),
    ("forex.prediction.dataset_builder",        "Dataset + R/R-aware target"),
    ("forex.prediction.xgb_trainer",            "Ensemble trainer (XGB+LGBM+RF)"),
    ("forex.prediction.predictor",              "Signal predictor + confidence gate"),
    ("forex.prediction.integrated_pipeline",    "Full Forex pipeline"),
    ("forex.business.business_csv_adapter",     "Business CSV normalizer"),
    ("forex.business.kpi_engine",               "KPI computation engine"),
    ("forex.business.business_predictor",       "GROWING/DECLINING/STABLE signal"),
    ("forex.business.business_pipeline",        "Full Business pipeline"),
]


def _try_import(name, desc):
    t0 = time.time()
    try:
        importlib.import_module(name)
        elapsed = time.time() - t0
        _ok(f"{name:<48} ({elapsed:.1f}s)  {desc}")
        return True
    except Exception:
        tb = traceback.format_exc()
        last_line = [l.strip() for l in tb.strip().splitlines() if l.strip()][-1]
        _err(f"{name:<48} FAILED")
        print(f"         → {last_line}")
        ISSUES.append(f"Module {name} failed: {last_line}")
        return False


def phase3_app_modules():
    _head("PHASE 3 — App Module Imports")
    ok = sum(_try_import(name, desc) for name, desc in APP_MODULES)
    print(f"\n  App modules: {ok}/{len(APP_MODULES)} loaded")


def phase4_forex_modules():
    _head("PHASE 4 — Forex & Business Intelligence Modules")
    ok = sum(_try_import(name, desc) for name, desc in FOREX_MODULES)
    print(f"\n  Forex/BI modules: {ok}/{len(FOREX_MODULES)} loaded")


# ═══════════════════════════════════════════════════════════
#  PHASE 5 — FUNCTIONAL SMOKE TESTS
# ═══════════════════════════════════════════════════════════

def phase5_smoke():
    _head("PHASE 5 — Functional Smoke Tests")

    # Test 1: market_universe find_market
    try:
        from forex.market_universe import find_market, normalize_symbol, get_all_forex_pairs
        assert find_market("eurusd") == "EUR/USD", "find_market eurusd mismatch"
        assert find_market("bitcoin") is None, "find_market should return None for unsupported"
        assert len(get_all_forex_pairs()) > 30, "Too few pairs"
        _ok("forex.market_universe: find_market, normalize_symbol, get_all_forex_pairs work")
    except Exception as e:
        _err(f"forex.market_universe smoke test: {e}")
        ISSUES.append(f"market_universe smoke: {e}")

    # Test 2: KPI engine (no file needed)
    try:
        import pandas as pd, numpy as np
        from forex.business.kpi_engine import KPIEngine
        df = pd.DataFrame({
            "date":         pd.date_range("2024-01", periods=12, freq="MS"),
            "revenue":      np.random.uniform(20000, 50000, 12),
            "cost_of_sales":np.random.uniform(8000, 18000, 12),
            "expenses":     np.random.uniform(5000, 12000, 12),
        })
        engine = KPIEngine(df)
        kpis = engine.compute_all()
        assert "health_score" in kpis, "Missing health_score"
        _ok(f"KPIEngine smoke: health_score={kpis['health_score']}, trend={kpis.get('trend_direction')}")
    except Exception as e:
        _err(f"KPIEngine smoke test: {e}")
        ISSUES.append(f"KPIEngine: {e}")

    # Test 3: CSV adapter with synthetic forex data
    try:
        import pandas as pd, numpy as np, tempfile, os
        from forex.prediction.csv_adapter import adapt_csv
        df = pd.DataFrame({
            "timestamp": pd.date_range("2023-01-01", periods=200, freq="h"),
            "open":   np.random.uniform(130, 145, 200),
            "high":   np.random.uniform(131, 146, 200),
            "low":    np.random.uniform(129, 144, 200),
            "close":  np.random.uniform(130, 145, 200),
            "volume": np.random.uniform(100, 500, 200),
        })
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as tmp:
            df.to_csv(tmp, index=False)
            tmp_path = tmp.name
        result = adapt_csv(tmp_path, pair="USDJPY")
        os.unlink(tmp_path)
        assert len(result) > 0, "Empty result from csv_adapter"
        _ok(f"csv_adapter smoke: {len(result)} rows loaded, cols={list(result.columns[:5])}")
    except Exception as e:
        _err(f"csv_adapter smoke test: {e}")
        ISSUES.append(f"ForexCSVAdapter: {e}")

    # Test 4: redis_delete presence in modules_extra
    try:
        from modules_extra import redis_delete
        _ok("redis_delete imported from modules_extra successfully")
    except ImportError:
        _err("redis_delete missing from modules_extra.py (memory_router will crash)")
        ISSUES.append("Add redis_delete() to modules_extra.py — see Phase 1 auto-repair or add manually")
    except Exception as e:
        _err(f"redis_delete import error: {e}")


# ═══════════════════════════════════════════════════════════
#  FINAL REPORT
# ═══════════════════════════════════════════════════════════

def final_report():
    _head("FINAL REPORT")

    if FIXED:
        try:
            from colorama import Fore, Style
            print(f"{Fore.CYAN}Auto-fixed:{Style.RESET_ALL}")
        except ImportError:
            print("Auto-fixed:")
        for f in FIXED:
            print(f"  ✓ {f}")

    if WARNINGS:
        try:
            from colorama import Fore, Style
            print(f"\n{Fore.YELLOW}Warnings (optional packages — won't block startup):{Style.RESET_ALL}")
        except ImportError:
            print("\nWarnings (optional):")
        for w in WARNINGS:
            print(f"  ~ {w}")

    if not ISSUES:
        try:
            from colorama import Fore, Style
            print(f"\n{Fore.GREEN}✅ No critical issues found — ASTRA should start normally.{Style.RESET_ALL}")
            print(f"   Run:  python main.py\n")
        except ImportError:
            print("\n[OK] No critical issues — run: python main.py\n")
    else:
        try:
            from colorama import Fore, Style
            print(f"\n{Fore.RED}❌ {len(ISSUES)} issue(s) need manual attention:{Style.RESET_ALL}")
        except ImportError:
            print(f"\n[FAIL] {len(ISSUES)} issue(s) need manual attention:")
        for i, issue in enumerate(ISSUES, 1):
            print(f"  {i}. {issue}")
        print()
        print("  Most common fix:")
        print("    pip install xgboost lightgbm optuna scikit-learn")
        print("    pip install lazy-loader==0.5")
        print()
        print("  Then re-run:  python check_startup.py")
        print()


# ═══════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        from colorama import Fore, Style, init as _ci
        _ci(autoreset=True)
        print(f"\n{Fore.GREEN}╔══════════════════════════════════════════════════════════╗")
        print(f"║          ASTRA — Startup Diagnostic & Auto-Repair         ║")
        print(f"╚══════════════════════════════════════════════════════════╝{Style.RESET_ALL}\n")
    except ImportError:
        print("\n" + "="*60)
        print("     ASTRA — Startup Diagnostic & Auto-Repair")
        print("="*60 + "\n")

    phase1_autorepair()
    phase2_packages()
    phase3_app_modules()
    phase4_forex_modules()
    phase5_smoke()
    final_report()

#!/usr/bin/env python3
"""
ASTRA Production Startup Validator
Runs before the main server to confirm environment is ready.
Exit 0 = OK, Exit 1 = FATAL error(s) found.
"""
import sys, os

errors = []
warnings_list = []

# 1. Check Python version
if sys.version_info < (3, 11):
    errors.append(f"Python 3.11+ required, found {sys.version}")
else:
    print(f"  ✅ Python {sys.version.split()[0]}")

# 2. Check critical env variables
critical_env = ["GROQ_API_KEY"]
optional_env = ["OPENAI_API_KEY", "MT5_ACCOUNT", "NEWS_API_KEY"]

for var in critical_env:
    if not os.environ.get(var):
        warnings_list.append(f"Missing env var: {var} (ASTRA will use local model fallback)")
    else:
        print(f"  ✅ {var} set")

# 3. Check critical imports
critical_modules = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("sklearn", "scikit-learn"),
    ("xgboost", "xgboost"),
    ("lightgbm", "lightgbm"),
]

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for mod, pkg in critical_modules:
    try:
        __import__(mod)
        print(f"  ✅ {pkg}")
    except ImportError:
        errors.append(f"Missing package: {pkg} — run: pip install {pkg}")

# 4. Check forex pipeline
try:
    from forex.prediction.csv_adapter import adapt_csv
    from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
    print("  ✅ Forex pipeline importable")
except Exception as e:
    errors.append(f"Forex pipeline broken: {e}")

# 5. Check workspace server
try:
    from workspace.server import app
    print("  ✅ Workspace server importable")
except Exception as e:
    errors.append(f"Workspace server broken: {e}")

# 6. Check memory DB
try:
    import memory
    print("  ✅ Memory DB accessible")
except Exception as e:
    errors.append(f"Memory DB error: {e}")

# Summary
print()
if warnings_list:
    print(f"⚠  WARNINGS ({len(warnings_list)}):")
    for w in warnings_list:
        print(f"   • {w}")

if errors:
    print(f"❌ FATAL ERRORS ({len(errors)}) — cannot start:")
    for e in errors:
        print(f"   • {e}")
    sys.exit(1)
else:
    print("✅ ASTRA startup validation PASSED — safe to start server")
    sys.exit(0)

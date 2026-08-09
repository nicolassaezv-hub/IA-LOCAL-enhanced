"""
VI.2.B — Self-Test / Diagnóstico del Proyecto
Comando: 'self-test' o 'diagnóstico'
Verifica todos los imports, modelos, DBs, CSVs, scheduler y memoria.
Retorna semáforo: ✅ OK / ⚠️ Warning / ❌ Error por módulo.
"""
import sys
import os
import time
from pathlib import Path

_ROOT = Path(__file__).parent


def _check(label: str, fn) -> tuple[str, str]:
    """Ejecuta un check y retorna (estado, mensaje)."""
    try:
        result = fn()
        if result is True or result is None:
            return "ok", label
        elif result is False:
            return "error", label
        else:
            return "ok", f"{label}: {result}"
    except ImportError as e:
        return "warn", f"{label}: módulo no instalado ({e})"
    except Exception as e:
        return "error", f"{label}: {str(e)[:80]}"


def run_self_test(verbose: bool = True) -> dict:
    """
    Ejecuta el diagnóstico completo del sistema.
    Retorna dict con resultados por categoría.
    """
    from rich.console import Console
    from rich.table import Table
    console = Console()

    checks = {
        "ok": [],
        "warn": [],
        "error": [],
    }

    def add(label, fn):
        status, msg = _check(label, fn)
        checks[status].append(msg)

    console.print("\n[bold cyan]╔══════════════════════════════════════╗[/]")
    console.print("[bold cyan]║    ASTRA — SELF-TEST (VI.2.B)        ║[/]")
    console.print("[bold cyan]╚══════════════════════════════════════╝[/]\n")

    t0 = time.time()

    # ── Core imports ─────────────────────────────────────────────
    console.print("[bold]▸ Core imports[/]")

    add("astra_agent",      lambda: __import__("astra_agent"))
    add("intent_router",    lambda: __import__("intent_router"))
    add("tool_registry",    lambda: __import__("tool_registry"))
    add("tool_executor",    lambda: __import__("tool_executor"))
    add("argument_parser",  lambda: __import__("argument_parser"))
    add("memory",           lambda: __import__("memory"))
    add("io_files",         lambda: __import__("io_files"))
    add("security",         lambda: __import__("security"))
    add("web_tools",        lambda: __import__("web_tools"))

    # ── Roadmap V prediction modules ─────────────────────────────
    console.print("[bold]▸ Forex / Roadmap V modules[/]")

    def _imp(mod): return lambda: __import__(mod)

    for mod in [
        "forex.prediction.decision_engine",
        "forex.prediction.risk_engine",
        "forex.prediction.mtf_coherence",
        "forex.prediction.regime_detector",
        "forex.prediction.reliability_score",
        "forex.prediction.model_selector",
        "forex.prediction.feature_importance",
        "forex.prediction.backtest_protocol",
        "forex.prediction.quality_analyzer",
        "forex.prediction.outcome_tracker",
        "forex.prediction.retrain_manager",
        "forex.prediction.decision_explainer",
        "forex.prediction.multi_pair_scanner",
    ]:
        add(mod.split(".")[-1], _imp(mod))

    # ── Roadmap VI modules ────────────────────────────────────────
    console.print("[bold]▸ Roadmap VI modules[/]")

    for mod in [
        "forex.prediction.hyperparameter_cache",
        "forex.prediction.adaptive_trainer",
        "forex.prediction.model_cache",
        "forex.prediction.model_quality_history",
        "forex.prediction.candlestick_patterns",
        "forex.data.rolling_dataset",
        "forex.data.indicator_delta",
        "forex.data.csv_migrator",
        "forex.data.data_router",
        "forex.data.yahoo_provider",
        "forex.data.binance_provider",
        "forex.data.mt5_provider",
        "forex.portfolio.opportunity_score",
        "forex.scheduler.autonomous_scheduler",
        "forex.scheduler.auto_updater",
    ]:
        add(mod.split(".")[-1], _imp(mod))

    # ── Modelos entrenados ────────────────────────────────────────
    console.print("[bold]▸ Modelos entrenados[/]")

    models_dir = _ROOT / "models" / "forex"
    if models_dir.exists():
        pkl_files = list(models_dir.glob("*.pkl"))
        if pkl_files:
            checks["ok"].append(f"Modelos pkl: {len(pkl_files)} encontrados")
        else:
            checks["warn"].append("Modelos pkl: ninguno entrenado — ejecuta 'full forex <csv>'")
    else:
        checks["warn"].append("models/forex/ no existe — sin modelos entrenados")

    # ── Base de datos ─────────────────────────────────────────────
    console.print("[bold]▸ Bases de datos[/]")

    def _check_db(path):
        import sqlite3
        p = Path(path)
        if not p.exists():
            return f"{p.name}: creará al primer uso"
        conn = sqlite3.connect(str(p))
        conn.execute("SELECT 1")
        conn.close()
        return f"{p.name}: OK ({p.stat().st_size // 1024} KB)"

    add("astra_memory.db",        lambda: _check_db(_ROOT / "astra_memory.db"))
    add("astra_hparam_cache.db",  lambda: _check_db(_ROOT / "astra_hparam_cache.db"))
    add("astra_model_quality.db", lambda: _check_db(_ROOT / "astra_model_quality.db"))

    # ── CSVs disponibles ─────────────────────────────────────────
    console.print("[bold]▸ CSVs disponibles[/]")

    csv_root = _ROOT / "CSVs"
    if csv_root.exists():
        total_csv = list(csv_root.rglob("*.csv"))
        if total_csv:
            checks["ok"].append(f"CSVs encontrados: {len(total_csv)}")
            for csv_path in total_csv[:5]:
                tf = csv_path.parent.name
                pair = csv_path.stem
                checks["ok"].append(f"  {pair}/{tf}: {csv_path.name}")
        else:
            checks["warn"].append("Sin CSVs en CSVs/ — crea con 'descargar datos <par> <tf>'")
    else:
        checks["warn"].append("CSVs/ no existe — crea con 'descargar datos <par> <tf>'")

    # ── Scheduler ────────────────────────────────────────────────
    console.print("[bold]▸ Scheduler[/]")

    try:
        from forex.scheduler.autonomous_scheduler import get_scheduler
        sched = get_scheduler()
        checks["ok"].append(f"Scheduler: {'Activo' if sched.is_running else 'Detenido (normal si no se inició)'}")
    except Exception as e:
        checks["warn"].append(f"Scheduler: {e}")

    # ── Memoria ──────────────────────────────────────────────────
    console.print("[bold]▸ Memoria[/]")

    def _check_memory():
        import sqlite3
        db_path = _ROOT / "astra_memory.db"
        if not db_path.exists():
            return "Sin DB de memoria — creará al primer uso"
        conn = sqlite3.connect(str(db_path))
        try:
            count = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
            return f"{count} entradas en memoria"
        except Exception:
            return "DB de memoria vacía (nueva)"
        finally:
            conn.close()

    add("memoria", _check_memory)

    # ── APIs opcionales ──────────────────────────────────────────
    console.print("[bold]▸ APIs opcionales[/]")

    groq_key = os.environ.get("GROQ_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if groq_key:
        checks["ok"].append("GROQ_API_KEY: configurada ✅")
    elif openai_key:
        checks["ok"].append("OPENAI_API_KEY: configurada ✅")
    else:
        checks["warn"].append("Sin API key (GROQ/OpenAI) — chat AI en modo fallback")

    # ── Paquetes opcionales ───────────────────────────────────────
    optional = [
        ("yfinance", "Yahoo Finance provider (VI.7.B)"),
        ("requests", "HTTP client para Binance"),
        ("torch",    "PyTorch (deep learning)"),
        ("redis",    "Redis cache"),
        ("flask",    "Flask REST API"),
        ("fastapi",  "FastAPI REST API"),
        ("MetaTrader5", "MT5 provider (solo Windows)"),
    ]
    for pkg, desc in optional:
        try:
            __import__(pkg)
            checks["ok"].append(f"{pkg}: disponible")
        except ImportError:
            checks["warn"].append(f"{pkg}: no instalado ({desc})")

    # ── Resultado final ──────────────────────────────────────────
    elapsed = time.time() - t0

    table = Table(title=f"\nSelf-Test completado en {elapsed:.1f}s", show_lines=False)
    table.add_column("Estado", width=6)
    table.add_column("Descripción")

    for msg in checks["ok"]:
        table.add_row("[green]  ✅[/]", msg)
    for msg in checks["warn"]:
        table.add_row("[yellow]  ⚠️[/]", msg)
    for msg in checks["error"]:
        table.add_row("[red]  ❌[/]", msg)

    if verbose:
        console.print(table)

    n_ok    = len(checks["ok"])
    n_warn  = len(checks["warn"])
    n_error = len(checks["error"])

    summary = (
        f"\n  ✅ {n_ok} OK   ⚠️ {n_warn} Warnings   ❌ {n_error} Errores\n"
    )
    if n_error == 0:
        console.print(f"[bold green]{summary}  Sistema listo para operar.[/]")
    else:
        console.print(f"[bold yellow]{summary}  Hay errores que requieren atención.[/]")

    return {
        "ok": n_ok, "warn": n_warn, "error": n_error,
        "ok_list": checks["ok"],
        "warn_list": checks["warn"],
        "error_list": checks["error"],
        "elapsed_s": elapsed,
        "healthy": n_error == 0,
    }


if __name__ == "__main__":
    run_self_test()

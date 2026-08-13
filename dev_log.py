"""
ASTRA Development Log — Sistema de registro del desarrollo.
Almacena implementaciones, optimizaciones, correcciones y versiones.
Reemplaza la necesidad de crear nuevos Roadmaps.
Comando: dev log, dev log add, dev log show, dev log release
"""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime
from enum import Enum

from runtime_paths import configured_project_path


_DB = configured_project_path("ASTRA_DEV_LOG_DB_PATH", "dev_log.db")

try:
    from colorama import Fore, Style
    _H = lambda s: f"{Fore.CYAN}{s}{Style.RESET_ALL}"
    _G = lambda s: f"{Fore.GREEN}{s}{Style.RESET_ALL}"
    _Y = lambda s: f"{Fore.YELLOW}{s}{Style.RESET_ALL}"
    _R = lambda s: f"{Fore.RED}{s}{Style.RESET_ALL}"
    _W = lambda s: f"{Fore.WHITE}{s}{Style.RESET_ALL}"
except ImportError:
    _H = _G = _Y = _R = _W = lambda s: s


class EntryType(str, Enum):
    FEATURE      = "feature"
    OPTIMIZATION = "optimization"
    BUGFIX       = "bugfix"
    RELEASE      = "release"
    REFACTOR     = "refactor"
    DOCS         = "docs"


def _init_db():
    conn = sqlite3.connect(str(_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dev_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        TEXT NOT NULL,
            version   TEXT NOT NULL DEFAULT '',
            type      TEXT NOT NULL,
            title     TEXT NOT NULL,
            detail    TEXT NOT NULL DEFAULT '',
            author    TEXT NOT NULL DEFAULT 'ASTRA',
            tags      TEXT NOT NULL DEFAULT '[]'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dev_log_ts ON dev_log(ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dev_log_type ON dev_log(type)")
    conn.commit()
    conn.close()


def add_entry(
    title: str,
    entry_type: str = "feature",
    detail: str = "",
    version: str = "",
    author: str = "ASTRA",
    tags: list[str] | None = None,
) -> int:
    _init_db()
    conn = sqlite3.connect(str(_DB))
    cur = conn.execute(
        "INSERT INTO dev_log (ts,version,type,title,detail,author,tags) VALUES (?,?,?,?,?,?,?)",
        (
            datetime.now().isoformat(),
            version,
            entry_type.lower(),
            title,
            detail,
            author,
            json.dumps(tags or []),
        ),
    )
    entry_id = cur.lastrowid
    conn.commit()
    conn.close()
    return entry_id


def get_entries(
    limit: int = 20,
    entry_type: str = "",
    version: str = "",
) -> list[dict]:
    _init_db()
    conn = sqlite3.connect(str(_DB))
    conn.row_factory = sqlite3.Row
    q = "SELECT * FROM dev_log WHERE 1=1"
    params: list = []
    if entry_type:
        q += " AND type=?"
        params.append(entry_type.lower())
    if version:
        q += " AND version=?"
        params.append(version)
    q += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_versions() -> list[str]:
    _init_db()
    conn = sqlite3.connect(str(_DB))
    rows = conn.execute(
        "SELECT DISTINCT version FROM dev_log WHERE version!='' ORDER BY ts DESC"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_release_notes(version: str) -> str:
    entries = get_entries(limit=200, version=version)
    if not entries:
        return f"Sin entradas para versión {version}."
    lines = [_H(f"Release Notes — v{version}"), ""]
    type_order = ["feature", "optimization", "bugfix", "refactor", "docs"]
    type_labels = {
        "feature":      "✨ Nuevas Funcionalidades",
        "optimization": "⚡ Optimizaciones",
        "bugfix":       "🐛 Correcciones",
        "refactor":     "♻️  Refactorizaciones",
        "release":      "🚀 Release",
        "docs":         "📚 Documentación",
    }
    grouped: dict[str, list[dict]] = {}
    for e in entries:
        t = e["type"]
        grouped.setdefault(t, []).append(e)

    for t in type_order:
        if t in grouped:
            lines.append(_G(f"  {type_labels.get(t, t)}"))
            for e in grouped[t]:
                ts = e["ts"][:10]
                lines.append(f"    [{ts}] {e['title']}")
                if e.get("detail"):
                    lines.append(f"           {e['detail']}")
            lines.append("")
    return "\n".join(lines)


def format_log(entries: list[dict]) -> str:
    if not entries:
        return "Sin entradas en el dev log."
    type_icons = {
        "feature":      "✨",
        "optimization": "⚡",
        "bugfix":       "🐛",
        "refactor":     "♻️",
        "release":      "🚀",
        "docs":         "📚",
    }
    lines = [_H(f"  ASTRA Development Log ({len(entries)} entradas)"), ""]
    for e in entries:
        icon = type_icons.get(e["type"], "•")
        ts = e["ts"][:16].replace("T", " ")
        ver = f" [v{e['version']}]" if e.get("version") else ""
        lines.append(f"  {icon} {_W(e['title'])}{_Y(ver)}")
        lines.append(f"     {ts} · {e['type']}{' · ' + e['detail'] if e.get('detail') else ''}")
    return "\n".join(lines)


def cmd_dev_log(args: str = "") -> str:
    """Comando 'dev log [add|show|release|versions] ...'"""
    parts = args.strip().split(None, 1)
    sub = parts[0].lower() if parts else "show"
    rest = parts[1] if len(parts) > 1 else ""

    if sub in ("show", "list", ""):
        entries = get_entries(limit=20)
        return format_log(entries)

    elif sub == "add":
        # dev log add [tipo] título | detalle
        # Ejemplo: dev log add feature Nuevo comando doctor | diagnóstico completo
        r2 = rest.strip()
        # Detectar tipo opcional
        type_keywords = list(EntryType)
        detected_type = "feature"
        for kw in type_keywords:
            if r2.lower().startswith(kw.value + " "):
                detected_type = kw.value
                r2 = r2[len(kw.value):].strip()
                break
        title, _, detail = r2.partition("|")
        title = title.strip()
        detail = detail.strip()
        if not title:
            return "Uso: dev log add [tipo] título | detalle\nTipos: feature, optimization, bugfix, refactor, docs, release"
        entry_id = add_entry(title=title, entry_type=detected_type, detail=detail)
        return _G(f"  ✅ Entrada #{entry_id} añadida: [{detected_type}] {title}")

    elif sub == "release":
        ver = rest.strip()
        if not ver:
            versions = list_versions()
            if versions:
                return "Versiones disponibles: " + ", ".join(versions)
            return "Sin releases registrados. Usa: dev log release <versión>"
        return get_release_notes(ver)

    elif sub == "versions":
        versions = list_versions()
        return "Versiones: " + (", ".join(versions) if versions else "ninguna")

    elif sub in ("bugfix", "fix"):
        title, _, detail = rest.partition("|")
        entry_id = add_entry(title=title.strip(), entry_type="bugfix", detail=detail.strip())
        return _G(f"  ✅ Bugfix #{entry_id} registrado: {title.strip()}")

    elif sub in ("feature", "feat"):
        title, _, detail = rest.partition("|")
        entry_id = add_entry(title=title.strip(), entry_type="feature", detail=detail.strip())
        return _G(f"  ✅ Feature #{entry_id} registrada: {title.strip()}")

    else:
        return (
            "Comandos disponibles:\n"
            "  dev log show            — Ver últimas 20 entradas\n"
            "  dev log add [tipo] title | detalle  — Añadir entrada\n"
            "  dev log bugfix title    — Registrar corrección\n"
            "  dev log feature title   — Registrar nueva función\n"
            "  dev log release <ver>   — Release notes de una versión\n"
            "  dev log versions        — Listar versiones disponibles"
        )


# ── Pre-carga entradas históricas si la DB está vacía ─────────────────────────

def _seed_initial_entries():
    _init_db()
    conn = sqlite3.connect(str(_DB))
    count = conn.execute("SELECT COUNT(*) FROM dev_log").fetchone()[0]
    conn.close()
    if count > 0:
        return

    initial = [
        ("5.0.0", "release",      "Roadmap V completo — Prediction Framework Forex",
         "Pipeline ML completo: XGBoost+LightGBM+RF, Quality Gate, Backtest, Walk-Forward, Feature Importance, Risk Engine, Decision Engine, Outcome Tracker, Portfolio Ranker"),
        ("6.0.0", "feature",      "Roadmap VI — Autonomización & Data Intelligence",
         "HyperparamCache, AdaptiveTrainer, ModelCache, CandlestickPatterns, RollingDataset, IndicatorDelta, CSVMigrator, DataRouter, YahooProvider, BinanceProvider, MT5Provider, OpportunityScore, ModelQualityHistory, AutonomousScheduler, AutoUpdater"),
        ("6.0.0", "feature",      "astra doctor — Diagnóstico unificado 10 categorías",
         "Verifica dependencias, configuración, modelos, APIs, MT5, DB, scheduler, datasets, módulos, API interna"),
        ("6.0.0", "feature",      "API REST interna (astra_api.py + routes Node.js)",
         "Servidor HTTP en puerto 8766 con endpoints de predicciones, ranking, estado, outcomes, datasets, doctor"),
        ("6.0.0", "feature",      "Oracle Cloud readiness — docs/ORACLE_CLOUD.md",
         "Arquitectura systemd, servicios independientes, nginx proxy, sincronización con Workplace"),
        ("6.0.0", "feature",      "Development Log — sistema de registro del desarrollo",
         "Reemplaza nuevos Roadmaps, almacena features/bugfixes/releases en SQLite"),
        ("6.0.0", "bugfix",       "CandlestickPatterns NaN guard con min_periods=3",
         "avg_body era NaN con <11 filas por rolling(10) sin min_periods mínimo"),
        ("6.0.0", "bugfix",       "OpportunityRanker CLI: claves top_buy/top_sell",
         "Handler CLI usaba keys 'buy'/'sell' pero rank() retorna 'top_buy'/'top_sell'"),
        ("6.0.0", "bugfix",       "ModelCacheManager.should_retrain() retorna tuple[bool,str]",
         "Handler no desempaquetaba correctamente el resultado"),
        ("6.0.0", "optimization", "Eliminados archivos obsoletos: check_functionality, check_skeleton, test_main",
         "Archivos de testing primitivo reemplazados por check_system.py y astra_doctor.py"),
        ("6.0.0", "release",      "Roadmap VI completado — ASTRA 6.0.0",
         "35/35 tests pasando, integración completa pipeline, API interna, Oracle Cloud ready"),
    ]
    for ver, etype, title, detail in initial:
        add_entry(title=title, entry_type=etype, detail=detail, version=ver)


_seed_initial_entries()

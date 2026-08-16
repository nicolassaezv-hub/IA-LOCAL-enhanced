# self_analysis.py
"""
ASTRA Self-Analysis — genera un reporte de estado completo del sistema y
lo guarda como REPORT DD-MM.md en el mismo directorio.

Activa con: 'self analysis', 'analiza astra', 'reporte sistema', etc.
"""

import os
import sys
import datetime
import platform
import importlib

import psutil

# ==========================================
# HELPERS
# ==========================================

def _check_module(name: str) -> str:
    try:
        importlib.import_module(name)
        return "✅ disponible"
    except (ImportError, OSError, Exception):
        return "⚠️  no instalado"


def _memory_count() -> int:
    """Cuenta entradas en SQLite memory."""
    try:
        from memory import cargar_memoria
        entries = cargar_memoria(limit=9999)
        if not entries:
            return 0
        return len(str(entries).split("\n"))
    except Exception:
        return 0


def _forex_market_count() -> int:
    """Cuenta mercados guardados en forex_memory."""
    try:
        from forex.forex_memory import list_saved_markets
        markets = list_saved_markets()
        if not markets:
            return 0
        return len(markets) if isinstance(markets, list) else 0
    except Exception:
        return 0


def _tool_count() -> int:
    """Cuenta herramientas registradas."""
    try:
        from tool_registry import TOOLS
        return len(TOOLS)
    except Exception:
        return 0


def _ai_backend() -> str:
    groq_key = os.environ.get("GROQ_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    if groq_key:
        return "Groq — openai/gpt-oss-120b"
    if openai_key:
        return "OpenAI — gpt-3.5-turbo"
    return "Sin configurar (GROQ_API_KEY o OPENAI_API_KEY requerido)"


def _branch_status() -> list:
    return [
        ("1", "Core (Tool Registry, Memory, File I/O, Security)", "✅ Completo"),
        ("2", "Prediction Framework (Forex ML pipeline)",         "✅ Completo"),
        ("3", "Business Intelligence Engine (KPIs, BI pipeline)", "✅ Completo"),
        ("4", "SME/PYME Consultant (Diagnostic, Forecast, Sim)",  "🔄 En progreso"),
        ("5", "Industry Packs (Retail, Restaurante, E-Commerce)",  "⏳ Pendiente"),
        ("6", "Multi-Agent Astra",                                "🔜 Futuro"),
        ("7", "Executive Copilot",                                "🔜 Futuro"),
    ]


# ==========================================
# GENERADOR PRINCIPAL
# ==========================================

def generate_self_analysis() -> str:
    """
    Genera el reporte completo como string Markdown
    y lo guarda en REPORT DD-MM.md junto a main.py.
    Devuelve un resumen para mostrar en consola.
    """
    now = datetime.datetime.now()
    date_label = now.strftime("%d-%m")          # e.g. 20-06
    date_full  = now.strftime("%d/%m/%Y %H:%M") # e.g. 20/06/2025 14:32

    # ── System info ──
    cpu_pct  = psutil.cpu_percent(interval=1)
    ram      = psutil.virtual_memory()
    ram_pct  = ram.percent
    ram_used = round(ram.used  / (1024**3), 2)
    ram_tot  = round(ram.total / (1024**3), 2)

    # ── Module availability ──
    modules = {
        "openai":       _check_module("openai"),
        "torch":        _check_module("torch"),
        "tensorflow":   _check_module("tensorflow"),
        "keras":        _check_module("keras"),
        "xgboost":      _check_module("xgboost"),
        "lightgbm":     _check_module("lightgbm"),
        "sklearn":      _check_module("sklearn"),
        "optuna":       _check_module("optuna"),
        "redis":        _check_module("redis"),
        "faiss":        _check_module("faiss"),
        "llama_index":  _check_module("llama_index"),
        "pdfplumber":   _check_module("pdfplumber"),
        "PyPDF2":       _check_module("PyPDF2"),
        "python-docx":  _check_module("docx"),
        "openpyxl":     _check_module("openpyxl"),
        "reportlab":    _check_module("reportlab"),
        "matplotlib":   _check_module("matplotlib"),
        "seaborn":      _check_module("seaborn"),
        "rich":         _check_module("rich"),
        "cryptography": _check_module("cryptography"),
        "bcrypt":       _check_module("bcrypt"),
        "PyJWT":        _check_module("jwt"),
        "pyttsx3":      _check_module("pyttsx3"),
        "sounddevice":  _check_module("sounddevice"),
    }

    available  = sum(1 for v in modules.values() if "✅" in v)
    missing    = sum(1 for v in modules.values() if "⚠️"  in v)
    tool_count = _tool_count()
    mem_count  = _memory_count()
    forex_count = _forex_market_count()

    # ── Build markdown ──
    lines = [
        f"# ASTRA — Reporte de Auto-Análisis",
        f"",
        f"> Generado: {date_full}  ",
        f"> Plataforma: {platform.system()} {platform.release()} — Python {sys.version.split()[0]}",
        f"",
        f"---",
        f"",
        f"## 🖥️  Estado del Sistema",
        f"",
        f"| Recurso | Valor |",
        f"|---------|-------|",
        f"| CPU     | {cpu_pct}% |",
        f"| RAM usada | {ram_used} GB / {ram_tot} GB ({ram_pct}%) |",
        f"| OS      | {platform.system()} {platform.release()} |",
        f"| Python  | {sys.version.split()[0]} |",
        f"",
        f"---",
        f"",
        f"## 🤖  Motor de IA",
        f"",
        f"| Parámetro | Valor |",
        f"|-----------|-------|",
        f"| Backend | {_ai_backend()} |",
        f"| GROQ_API_KEY | {'✅ configurada' if os.environ.get('GROQ_API_KEY') else '❌ no encontrada'} |",
        f"| OPENAI_API_KEY | {'✅ configurada' if os.environ.get('OPENAI_API_KEY') else '— no configurada'} |",
        f"",
        f"---",
        f"",
        f"## 🧰  Registro de Herramientas",
        f"",
        f"| Ítem | Valor |",
        f"|------|-------|",
        f"| Total de herramientas | **{tool_count}** |",
        f"| Entradas en memoria SQLite | {mem_count} líneas |",
        f"| Mercados Forex analizados | {forex_count} |",
        f"",
        f"---",
        f"",
        f"## 📦  Módulos Opcionales",
        f"",
        f"| Módulo | Estado |",
        f"|--------|--------|",
    ]

    for mod, status in modules.items():
        lines.append(f"| {mod} | {status} |")

    lines += [
        f"",
        f"> **{available}/{len(modules)}** módulos disponibles — {missing} opcionales sin instalar.",
        f"",
        f"---",
        f"",
        f"## 🗺️  Roadmap de Branches",
        f"",
        f"| Branch | Nombre | Estado |",
        f"|--------|--------|--------|",
    ]

    for b, name, status in _branch_status():
        lines.append(f"| {b} | {name} | {status} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 📝  Diagnóstico Rápido",
        f"",
    ]

    # Quick diagnostics
    if not os.environ.get("GROQ_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        lines.append("- ❌ **CRÍTICO** — No hay API key configurada. El chat AI no funcionará.")
    else:
        lines.append("- ✅ API key AI configurada correctamente.")

    if missing > 8:
        lines.append(f"- ⚠️  {missing} módulos opcionales no instalados. Considera `pip install openai torch tensorflow`.")
    elif missing > 0:
        lines.append(f"- ℹ️  {missing} módulos opcionales no instalados (no críticos).")
    else:
        lines.append("- ✅ Todos los módulos disponibles.")

    if tool_count >= 70:
        lines.append(f"- ✅ Registro de herramientas completo ({tool_count} tools).")
    else:
        lines.append(f"- ⚠️  Registro de herramientas incompleto ({tool_count} tools — esperado ≥70).")

    lines += [
        f"",
        f"---",
        f"",
        f"*Reporte generado automáticamente por ASTRA Self-Analysis.*",
    ]

    report_md = "\n".join(lines)

    # ── Save file ──
    here = os.path.dirname(os.path.abspath(__file__))
    filename = f"REPORT {date_label}.md"
    filepath = os.path.join(here, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_md)

    # ── Console summary ──
    summary_lines = [
        f"\n{'='*52}",
        f"  ASTRA — Auto-Análisis completado",
        f"{'='*52}",
        f"  Reporte guardado → {filename}",
        f"  Herramientas registradas : {tool_count}",
        f"  Motor AI                 : {_ai_backend()}",
        f"  Módulos disponibles      : {available}/{len(modules)}",
        f"  RAM                      : {ram_used}GB / {ram_tot}GB ({ram_pct}%)",
        f"  CPU                      : {cpu_pct}%",
        f"{'='*52}",
    ]
    return "\n".join(summary_lines)

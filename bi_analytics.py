"""
bi_analytics.py — ASTRA Business Intelligence adapter for tool_registry.

Wraps BusinessPipeline with clean top-level functions that match the
tool_registry / tool_executor pattern (same style as forex_analytics.py).

Available tools:
    bi_analyze(filepath)   — KPI report + health score + alerts (no ML)
    bi_consult(filepath)   — Full PYME consultant: KPIs + ML signal + recommendations
    bi_kpis(filepath)      — Raw KPI dict (for programmatic use)
    bi_train(filepath)     — Train a prediction model on business data
"""

from colorama import Fore, Style

_BI_PIPELINE = None


def _get_pipeline():
    global _BI_PIPELINE
    if _BI_PIPELINE is None:
        from forex.business.business_pipeline import BusinessPipeline
        _BI_PIPELINE = BusinessPipeline()
    return _BI_PIPELINE


def _fmt_kv(label: str, value, suffix: str = "") -> str:
    if isinstance(value, float):
        return f"  {label:<26}: {value:>12,.2f}{suffix}"
    return f"  {label:<26}: {value}{suffix}"


def _format_analysis(result: dict) -> str:
    lines = [
        f"\n{Fore.CYAN}╔══ ASTRA BI — ANÁLISIS KPI ══╗{Style.RESET_ALL}",
        f"  Archivo      : {result.get('file', '?')}",
        f"  Tipo negocio : {result.get('business_type', 'generic')}",
        f"  Periodo      : {result.get('date_range', '?')}  ({result.get('periods', 0)} meses)",
    ]

    health = result.get("health_score", 50)
    label  = result.get("health_label", "?")
    trend  = result.get("trend_direction", "stable")
    color  = Fore.GREEN if health >= 70 else (Fore.YELLOW if health >= 40 else Fore.RED)
    bar    = "█" * (health // 10) + "░" * (10 - health // 10)

    lines += [
        f"  Salud        : {color}[{bar}] {health}/100 — {label}{Style.RESET_ALL}",
        f"  Tendencia    : {trend}",
        "",
    ]

    kpi_map = {
        "total_revenue":      ("Ingresos totales",    ""),
        "avg_revenue":        ("Ingreso promedio",     ""),
        "gross_margin_pct":   ("Margen bruto",         " %"),
        "net_margin_pct":     ("Margen neto",          " %"),
        "expense_ratio_pct":  ("Ratio gastos",         " %"),
        "mom_growth_pct":     ("Crecimiento MoM",      " %"),
        "yoy_growth_pct":     ("Crecimiento YoY",      " %"),
        "ending_balance":     ("Saldo final",          ""),
    }
    for key, (lbl, sfx) in kpi_map.items():
        if key in result:
            lines.append(_fmt_kv(lbl, result[key], sfx))

    alerts = result.get("alerts", [])
    if alerts:
        lines += [f"\n{Fore.YELLOW}  ── ALERTAS ──────────────────────────{Style.RESET_ALL}"]
        for a in alerts:
            lines.append(f"  ⚠  {a}")

    anomalies = result.get("anomalies", [])
    if anomalies:
        lines += [f"\n{Fore.YELLOW}  ── ANOMALÍAS ────────────────────────{Style.RESET_ALL}"]
        for an in anomalies[:5]:
            lines.append(f"  •  {an}")

    lines.append("")
    return "\n".join(lines)


def _format_consult(result: dict) -> str:
    base = _format_analysis(result)

    action  = result.get("action", "STABLE")
    conf    = result.get("confidence", 0)
    risk    = result.get("risk_level", "MEDIUM")
    outlook = result.get("outlook", "")

    _COLOR = {"GROWING": Fore.GREEN, "DECLINING": Fore.RED, "STABLE": Fore.YELLOW}
    _ICON  = {"GROWING": "▲ CRECIENDO", "DECLINING": "▼ DECLINANDO", "STABLE": "─ ESTABLE"}
    color  = _COLOR.get(action, Fore.WHITE)
    icon   = _ICON.get(action, action)

    signal_lines = [
        f"{color}╔══ SEÑAL ML ══╗{Style.RESET_ALL}",
        f"  Señal        : {color}{icon}{Style.RESET_ALL}",
        f"  Confianza    : {conf:.2f}",
        f"  Nivel riesgo : {risk}",
    ]
    if outlook:
        signal_lines.append(f"  Perspectiva  : {outlook}")

    recs = result.get("recommendations", [])
    if recs:
        signal_lines += [f"\n{Fore.CYAN}  ── RECOMENDACIONES ─────────────────{Style.RESET_ALL}"]
        for i, r in enumerate(recs, 1):
            signal_lines.append(f"  {i}. {r}")

    signal_lines.append("")
    return base + "\n".join(signal_lines)


# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC TOOL FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────

def bi_analyze(filepath: str) -> str:
    """
    KPI analysis only — fast, no ML model needed.
    Returns health score, KPIs, trend direction, and alerts.

    Usage:
        bi_analyze("ventas_2025.csv")
        bi_analyze("data/negocio.xlsx")
    """
    try:
        result = _get_pipeline().analyze(filepath)
        if "error" in result:
            return f"[ASTRA-BI] Error: {result['error']}"
        return _format_analysis(result)
    except Exception as e:
        return f"[ASTRA-BI] Error al analizar '{filepath}': {e}"


def bi_consult(filepath: str) -> str:
    """
    Full PYME consultant mode: KPIs + ML signal + recommendations.
    Use this for a complete business diagnosis.

    Usage:
        bi_consult("ventas_2025.csv")
        bi_consult("data/negocio.xlsx")
    """
    try:
        result = _get_pipeline().consult(filepath)
        if "error" in result:
            return f"[ASTRA-BI] Error: {result['error']}"
        return _format_consult(result)
    except Exception as e:
        return f"[ASTRA-BI] Error al consultar '{filepath}': {e}"


def bi_kpis(filepath: str) -> dict:
    """
    Return the raw KPI dict for programmatic use.
    Includes health_score, margins, growth rates, alerts, anomalies.

    Usage:
        kpis = bi_kpis("ventas_2025.csv")
        print(kpis["health_score"], kpis["gross_margin_pct"])
    """
    try:
        from forex.business.business_csv_adapter import adapt_business_csv
        from forex.business.kpi_engine import KPIEngine
        df = adapt_business_csv(filepath)
        return KPIEngine(df).compute_all()
    except Exception as e:
        return {"error": str(e), "file": filepath}


def bi_train(filepath: str) -> str:
    """
    Train an ML ensemble model on a business dataset.
    Saves the model to models/business/ for future predictions.

    Usage:
        bi_train("ventas_historico.csv")
    """
    try:
        result = _get_pipeline().train(filepath)
        if "error" in result:
            return f"[ASTRA-BI] Error al entrenar: {result['error']}"
        rows = result.get("rows_trained", 0)
        acc  = result.get("accuracy", 0)
        path = result.get("model_path", "?")
        return (
            f"\n[ASTRA-BI] Modelo entrenado ✓\n"
            f"  Archivo  : {result.get('file', '?')}\n"
            f"  Filas    : {rows}\n"
            f"  Accuracy : {acc:.2%}\n"
            f"  Guardado : {path}\n"
        )
    except Exception as e:
        return f"[ASTRA-BI] Error al entrenar: {e}"

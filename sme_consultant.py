# sme_consultant.py
"""
Branch 4 — SME/PYME Consultant
Four modules built on top of the Branch 3 BI engine:

  sme_diagnostic(filepath)            — multi-dimensional health scorecard
  sme_forecast(filepath, months=6)    — revenue/cost projections 3/6/12m
  sme_recommend(filepath)             — Llama-generated strategic action plan
  sme_simulate(filepath, scenario)    — what-if scenario with before/after analysis

All functions return formatted strings ready for console display.
Narration (Llama) is injected by astra_agent via ask_llama_with_context
for diagnostic, forecast, and simulate; recommend calls it directly.
"""

import os
import re
import numpy as np
from colorama import Fore, Style

# ==========================================
# INTERNAL HELPERS
# ==========================================

def _load_kpis(filepath: str) -> tuple:
    """
    Load and compute KPIs from a business file.
    Returns (kpis_dict, df, error_str_or_None).
    """
    try:
        from forex.business.business_csv_adapter import adapt_business_csv
        from forex.business.kpi_engine import KPIEngine
        df   = adapt_business_csv(filepath)
        kpis = KPIEngine(df).compute_all()
        return kpis, df, None
    except Exception as e:
        return {}, None, str(e)


def _bar(score: int, width: int = 10) -> str:
    filled = round(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _score_color(score: int) -> str:
    if score >= 70:
        return Fore.GREEN
    if score >= 45:
        return Fore.YELLOW
    return Fore.RED


def _dimension_scores(kpis: dict) -> dict:
    """
    Compute three diagnostic dimensions from KPI data.

    Financial  (0-100): margin quality + expense efficiency + cash health
    Growth     (0-100): MoM + YoY + trend direction + CAGR
    Risk       (0-100): lower raw_risk = more risk; we invert to 0-100 score
    """
    # ── Financial ──
    fin = 50
    gm  = kpis.get("gross_margin_pct_latest", kpis.get("gross_margin_pct"))
    nm  = kpis.get("net_margin_pct_latest",   kpis.get("net_margin_pct"))
    er  = kpis.get("expense_ratio_pct")
    bal = kpis.get("min_balance")

    if gm is not None:
        if gm > 50:   fin += 20
        elif gm > 30: fin += 12
        elif gm > 15: fin +=  5
        elif gm < 0:  fin -= 20
        else:         fin -= 10

    if nm is not None:
        if nm > 15:   fin += 15
        elif nm > 5:  fin +=  8
        elif nm > 0:  fin +=  3
        elif nm < -5: fin -= 20
        else:         fin -= 10

    if er is not None:
        if er < 50:   fin += 10
        elif er < 70: fin +=  5
        elif er > 90: fin -= 15
        elif er > 80: fin -=  8

    if bal is not None:
        if bal < 0:   fin -= 15
        elif bal > 0: fin +=  5

    # ── Growth ──
    grw = 50
    mom  = kpis.get("mom_growth_pct")
    yoy  = kpis.get("yoy_growth_pct")
    cagr = kpis.get("cagr_pct")
    trend= kpis.get("trend_direction", "stable")
    strength = kpis.get("trend_strength", 0)

    if trend == "growing":   grw += 15
    elif trend == "declining": grw -= 15

    if mom is not None:
        if mom > 10:   grw += 15
        elif mom > 5:  grw += 10
        elif mom > 0:  grw +=  5
        elif mom < -10: grw -= 15
        elif mom < 0:  grw -=  8

    if yoy is not None:
        if yoy > 20:   grw += 10
        elif yoy > 5:  grw +=  5
        elif yoy < -15: grw -= 10
        elif yoy < 0:  grw -=  5

    if cagr is not None:
        if cagr > 10:  grw += 10
        elif cagr > 0: grw +=  5
        elif cagr < 0: grw -= 10

    grw += round(strength * 10)

    # ── Risk (inverted: 100 = low risk, 0 = high risk) ──
    raw_risk = 50
    anomalies = kpis.get("anomalies", [])
    drops     = sum(1 for a in anomalies if a.get("direction") == "drop")
    spikes    = sum(1 for a in anomalies if a.get("direction") == "spike")
    alerts    = kpis.get("alerts", [])

    raw_risk += drops  * 8
    raw_risk += spikes * 3
    raw_risk += len(alerts) * 4

    if trend == "declining": raw_risk += 15
    if bal is not None and bal < 0: raw_risk += 20
    if nm is not None and nm < -5:  raw_risk += 15

    risk_score = max(0, 100 - raw_risk)

    return {
        "financial": max(0, min(100, fin)),
        "growth":    max(0, min(100, grw)),
        "risk":      max(0, min(100, risk_score)),
    }


# ==========================================
# MODULE 1 — DIAGNOSTIC
# ==========================================

def sme_diagnostic(filepath: str) -> str:
    """
    Multi-dimensional health scorecard for a PYME.

    Scores three dimensions independently:
      Financial  — margin quality, expense efficiency, cash health
      Growth     — revenue trend, MoM/YoY rates, CAGR
      Risk       — anomaly exposure, cash risk, trend stability

    Weighted overall: Financial 40% + Growth 35% + Risk 25%
    """
    kpis, df, err = _load_kpis(filepath)
    if err:
        return f"[Branch4-Diagnostic] Error al cargar '{filepath}': {err}"

    dims    = _dimension_scores(kpis)
    fin_s   = dims["financial"]
    grw_s   = dims["growth"]
    risk_s  = dims["risk"]
    overall = round(fin_s * 0.40 + grw_s * 0.35 + risk_s * 0.25)

    health  = kpis.get("health_score", 50)
    label   = kpis.get("health_label", "?")
    trend   = kpis.get("trend_direction", "stable")
    fname   = os.path.basename(filepath)

    ov_color = _score_color(overall)

    lines = [
        f"\n{Fore.CYAN}╔══ ASTRA — DIAGNÓSTICO PYME ══╗{Style.RESET_ALL}",
        f"  Archivo    : {fname}",
        f"  Tipo       : {kpis.get('business_type', 'generic')}",
        f"  Periodo    : {kpis.get('date_range', '?')}  ({kpis.get('periods', 0)} meses)",
        f"  Tendencia  : {trend}",
        "",
        f"  {Fore.WHITE}── SCORECARD MULTIDIMENSIONAL ──────────────────────{Style.RESET_ALL}",
    ]

    for label_str, score in [
        ("Salud Financiera",   fin_s),
        ("Salud de Crecim.",   grw_s),
        ("Nivel de Riesgo",    risk_s),
    ]:
        color = _score_color(score)
        bar   = _bar(score)
        lines.append(
            f"  {label_str:<22}: {color}[{bar}] {score:>3}/100{Style.RESET_ALL}"
        )

    lines += [
        "",
        f"  {'PUNTUACIÓN GLOBAL':<22}: "
        f"{ov_color}[{_bar(overall)}] {overall:>3}/100 — {label}{Style.RESET_ALL}",
        "",
    ]

    # Key KPI snapshot
    kpi_rows = [
        ("Ingresos totales",    kpis.get("total_revenue"),     ""),
        ("Ingreso promedio",    kpis.get("avg_revenue"),        ""),
        ("Margen bruto",        kpis.get("gross_margin_pct"),   " %"),
        ("Margen neto",         kpis.get("net_margin_pct"),     " %"),
        ("Ratio gastos",        kpis.get("expense_ratio_pct"),  " %"),
        ("Crecimiento MoM",     kpis.get("mom_growth_pct"),     " %"),
        ("Crecimiento YoY",     kpis.get("yoy_growth_pct"),     " %"),
        ("CAGR",                kpis.get("cagr_pct"),           " %"),
        ("Saldo mínimo",        kpis.get("min_balance"),        ""),
    ]
    lines.append(f"  {Fore.WHITE}── KPIs CLAVE ──────────────────────────────────────{Style.RESET_ALL}")
    for lbl, val, sfx in kpi_rows:
        if val is not None:
            if isinstance(val, float):
                lines.append(f"  {lbl:<22}: {val:>12,.2f}{sfx}")
            else:
                lines.append(f"  {lbl:<22}: {val}{sfx}")

    alerts = kpis.get("alerts", [])
    if alerts:
        lines.append(f"\n  {Fore.YELLOW}── ALERTAS ──────────────────────────────────────{Style.RESET_ALL}")
        for a in alerts:
            lines.append(f"  ⚠  {a}")

    anomalies = kpis.get("anomalies", [])
    if anomalies:
        lines.append(f"\n  {Fore.YELLOW}── ANOMALÍAS DETECTADAS ────────────────────────{Style.RESET_ALL}")
        for an in anomalies[:5]:
            direction = "▲ pico" if an.get("direction") == "spike" else "▼ caída"
            lines.append(
                f"  •  Periodo {an.get('period','?')} | {an.get('metric','?')} "
                f"| {direction} | z={an.get('z_score',0):.1f}"
            )

    lines.append("")
    return "\n".join(lines)


# ==========================================
# MODULE 2 — FORECAST
# ==========================================

def sme_forecast(filepath: str, months: int = 6) -> str:
    """
    Projects the primary revenue metric forward `months` periods.
    Uses linear trend extrapolation with confidence intervals
    derived from trend_strength (R²).

    sme_forecast("ventas.csv")       → 6-month projection (default)
    sme_forecast("ventas.csv", 12)   → 12-month projection
    """
    try:
        months = int(months)
    except (TypeError, ValueError):
        months = 6

    kpis, df, err = _load_kpis(filepath)
    if err:
        return f"[Branch4-Forecast] Error al cargar '{filepath}': {err}"

    slope    = kpis.get("trend_slope", 0)
    strength = kpis.get("trend_strength", 0)
    latest   = kpis.get("latest_revenue",
               kpis.get("avg_revenue", 0))
    avg_rev  = kpis.get("avg_revenue", latest or 1)
    trend    = kpis.get("trend_direction", "stable")
    fname    = os.path.basename(filepath)

    # Uncertainty band: wider when trend_strength is low
    uncertainty = (1 - strength) * abs(avg_rev) * 0.20
    uncertainty = max(uncertainty, abs(avg_rev) * 0.03)

    trend_icon = {"growing": "▲", "declining": "▼", "stable": "─"}.get(trend, "─")
    trend_color = {
        "growing":   Fore.GREEN,
        "declining": Fore.RED,
        "stable":    Fore.YELLOW,
    }.get(trend, Fore.WHITE)

    lines = [
        f"\n{Fore.CYAN}╔══ ASTRA — PROYECCIÓN {months} MESES ══╗{Style.RESET_ALL}",
        f"  Archivo    : {fname}",
        f"  Base       : {latest:,.2f} (último período)",
        f"  Tendencia  : {trend_color}{trend_icon} {trend}{Style.RESET_ALL}  "
        f"(pendiente: {slope:+,.2f}/mes | R²: {strength:.2f})",
        "",
        f"  {'Mes':<6} {'Optimista':>14} {'Esperado':>14} {'Conservador':>14}",
        f"  {'─'*6} {'─'*14} {'─'*14} {'─'*14}",
    ]

    projections = []
    for i in range(1, months + 1):
        expected     = latest + slope * i
        optimistic   = expected + uncertainty * (1 + i * 0.05)
        conservative = expected - uncertainty * (1 + i * 0.05)
        projections.append((i, optimistic, expected, conservative))
        lines.append(
            f"  {i:<6} {optimistic:>14,.2f} {expected:>14,.2f} {conservative:>14,.2f}"
        )

    # Summary
    final_expected = projections[-1][2]
    total_change   = final_expected - latest
    pct_change     = (total_change / abs(latest) * 100) if latest != 0 else 0
    change_color   = Fore.GREEN if pct_change >= 0 else Fore.RED
    change_icon    = "▲" if pct_change >= 0 else "▼"

    lines += [
        "",
        f"  Proyección final ({months}m): "
        f"{change_color}{change_icon} {final_expected:,.2f} "
        f"({pct_change:+.1f}% vs actual){Style.RESET_ALL}",
        f"  Confianza del modelo: {strength * 100:.0f}%",
        f"  Banda de incertidumbre: ±{uncertainty:,.2f} (creciente con el tiempo)",
        "",
        f"  {Fore.YELLOW}Nota: proyección basada en tendencia lineal histórica."
        f" Factores externos no modelados.{Style.RESET_ALL}",
        "",
    ]
    return "\n".join(lines)


# ==========================================
# MODULE 3 — RECOMMENDATIONS  (Llama-native)
# ==========================================

def sme_recommend(filepath: str) -> str:
    """
    Generates a strategic action plan with ASTRA's active Groq model.

    Combines KPIs + dimensional scores into a rich context and asks ASTRA's
    Llama engine to produce 5 concrete, prioritized recommendations.
    """
    kpis, df, err = _load_kpis(filepath)
    if err:
        return f"[Branch4-Recommend] Error al cargar '{filepath}': {err}"

    dims    = _dimension_scores(kpis)
    overall = round(dims["financial"] * 0.40 + dims["growth"] * 0.35 + dims["risk"] * 0.25)
    fname   = os.path.basename(filepath)

    # Build rich context for Llama
    context_lines = [
        f"EMPRESA: {fname} | Tipo: {kpis.get('business_type','generic')}",
        f"PUNTUACIÓN GLOBAL: {overall}/100",
        f"  Salud Financiera : {dims['financial']}/100",
        f"  Salud Crecimiento: {dims['growth']}/100",
        f"  Nivel Riesgo     : {dims['risk']}/100",
        "",
        "KPIs FINANCIEROS:",
    ]
    for key, lbl, sfx in [
        ("total_revenue",    "Ingresos totales",   ""),
        ("avg_revenue",      "Ingreso promedio",    ""),
        ("gross_margin_pct", "Margen bruto",        "%"),
        ("net_margin_pct",   "Margen neto",         "%"),
        ("expense_ratio_pct","Ratio gastos",        "%"),
        ("mom_growth_pct",   "Crecimiento MoM",     "%"),
        ("yoy_growth_pct",   "Crecimiento YoY",     "%"),
        ("cagr_pct",         "CAGR",                "%"),
        ("ending_balance",   "Saldo final",         ""),
        ("min_balance",      "Saldo mínimo",        ""),
    ]:
        val = kpis.get(key)
        if val is not None:
            context_lines.append(
                f"  {lbl:<22}: {val:,.2f}{sfx}"
                if isinstance(val, float)
                else f"  {lbl:<22}: {val}{sfx}"
            )

    alerts = kpis.get("alerts", [])
    if alerts:
        context_lines.append("\nALERTAS ACTIVAS:")
        for a in alerts:
            context_lines.append(f"  {a}")

    context_lines += [
        "",
        f"Tendencia general: {kpis.get('trend_direction','stable')} "
        f"(fuerza: {kpis.get('trend_strength',0):.2f})",
        f"Anomalías detectadas: {len(kpis.get('anomalies',[]))}",
    ]

    user_prompt = (
        f"Basándote en los datos de diagnóstico de {fname}, "
        f"genera un plan de acción estratégico con exactamente 5 recomendaciones. "
        f"Para cada una incluye: acción concreta, impacto esperado en números "
        f"(% o unidades), y plazo de implementación (corto/medio/largo plazo). "
        f"Prioriza por urgencia e impacto."
    )

    try:
        from ai_models import ask_llama_with_context
        recommendation = ask_llama_with_context(
            user_prompt,
            "\n".join(context_lines)
        )
    except Exception as e:
        recommendation = f"[Llama no disponible: {e}]"

    header = (
        f"\n{Fore.CYAN}╔══ ASTRA — PLAN DE ACCIÓN ESTRATÉGICO ══╗{Style.RESET_ALL}\n"
        f"  Empresa  : {fname}\n"
        f"  Score    : {overall}/100\n"
        f"{'─'*52}\n"
    )
    return header + recommendation + "\n"


# ==========================================
# MODULE 4 — SIMULATION
# ==========================================

_METRIC_KEYWORDS = {
    "revenue":  ["ventas", "ingresos", "revenue", "venta"],
    "expenses": ["costos", "gastos", "expenses", "costes", "costo", "gasto"],
    "margin":   ["margen", "margin"],
    "units":    ["unidades", "units", "productos"],
}

_DIRECTION_POSITIVE = ["aumentar", "aumento", "subir", "increas", "grow", "crecer",
                       "incrementar", "mejorar", "más", "mas"]
_DIRECTION_NEGATIVE = ["reducir", "reduccion", "reducción", "bajar", "disminuir",
                       "decrease", "cut", "recortar", "menos", "ahorrar", "eliminar"]


def _parse_scenario(scenario: str) -> tuple:
    """
    Parse a free-text scenario into (metric, pct_delta).
    Returns ("revenue", +0.20) for "aumento ventas 20%".
    Returns ("expenses", -0.15) for "reducir costos 15%".
    """
    lower = scenario.lower()

    # Extract percentage
    pct_match = re.search(r"(\d+\.?\d*)\s*%?", lower)
    pct = float(pct_match.group(1)) / 100.0 if pct_match else 0.10

    # Direction
    is_positive = any(w in lower for w in _DIRECTION_POSITIVE)
    is_negative = any(w in lower for w in _DIRECTION_NEGATIVE)
    if is_negative and not is_positive:
        sign = -1
    else:
        sign = 1

    # Metric
    metric = "revenue"
    for m, keywords in _METRIC_KEYWORDS.items():
        if any(k in lower for k in keywords):
            metric = m
            break

    return metric, sign * pct


def sme_simulate(filepath: str, scenario: str = "aumentar ventas 10%") -> str:
    """
    What-if scenario analysis with before/after KPI comparison.

    Examples:
        sme_simulate("ventas.csv", "reducir costos 15%")
        sme_simulate("ventas.csv", "aumentar ingresos 20%")
        sme_simulate("ventas.csv", "si ahorro 10% en gastos")
    """
    kpis, df, err = _load_kpis(filepath)
    if err:
        return f"[Branch4-Simulate] Error al cargar '{filepath}': {err}"

    metric, delta = _parse_scenario(scenario)
    fname = os.path.basename(filepath)

    # ── Baseline scores ──
    dims_before  = _dimension_scores(kpis)
    overall_before = round(
        dims_before["financial"] * 0.40 +
        dims_before["growth"]    * 0.35 +
        dims_before["risk"]      * 0.25
    )

    # ── Apply scenario delta to KPI snapshot ──
    kpis_after = dict(kpis)

    if metric == "revenue":
        for key in ["total_revenue", "avg_revenue", "latest_revenue",
                    "max_revenue", "min_revenue"]:
            if key in kpis_after:
                kpis_after[key] = kpis_after[key] * (1 + delta)
        if "mom_growth_pct" in kpis_after:
            kpis_after["mom_growth_pct"] = kpis_after["mom_growth_pct"] + delta * 100

    elif metric == "expenses":
        if "expense_ratio_pct" in kpis_after:
            kpis_after["expense_ratio_pct"] = kpis_after["expense_ratio_pct"] * (1 + delta)
        if "total_expenses" in kpis_after:
            kpis_after["total_expenses"] = kpis_after["total_expenses"] * (1 + delta)
        # Improved margins when expenses drop
        if "gross_margin_pct" in kpis_after and delta < 0:
            kpis_after["gross_margin_pct"] = min(100, kpis_after["gross_margin_pct"] - delta * 40)
        if "net_margin_pct" in kpis_after and delta < 0:
            kpis_after["net_margin_pct"] = kpis_after["net_margin_pct"] - delta * 30

    elif metric == "margin":
        if "gross_margin_pct" in kpis_after:
            kpis_after["gross_margin_pct"] = min(100, kpis_after["gross_margin_pct"] + delta * 100)
        if "net_margin_pct" in kpis_after:
            kpis_after["net_margin_pct"] = min(100, kpis_after["net_margin_pct"] + delta * 100)

    elif metric == "units":
        if "total_units_sold" in kpis_after:
            kpis_after["total_units_sold"] = kpis_after["total_units_sold"] * (1 + delta)
        if "avg_units_sold" in kpis_after:
            kpis_after["avg_units_sold"] = kpis_after["avg_units_sold"] * (1 + delta)

    dims_after   = _dimension_scores(kpis_after)
    overall_after = round(
        dims_after["financial"] * 0.40 +
        dims_after["growth"]    * 0.35 +
        dims_after["risk"]      * 0.25
    )

    direction_icon = "▲" if delta >= 0 else "▼"
    metric_label   = {"revenue": "Ingresos", "expenses": "Costos",
                      "margin": "Margen", "units": "Unidades"}[metric]

    lines = [
        f"\n{Fore.CYAN}╔══ ASTRA — SIMULACIÓN DE ESCENARIO ══╗{Style.RESET_ALL}",
        f"  Archivo    : {fname}",
        f"  Escenario  : «{scenario}»",
        f"  Variable   : {metric_label}  {direction_icon} {abs(delta)*100:.1f}%",
        "",
        f"  {'Dimensión':<22} {'Antes':>8} {'Después':>8} {'Δ':>8}",
        f"  {'─'*22} {'─'*8} {'─'*8} {'─'*8}",
    ]

    for dim_key, dim_lbl in [
        ("financial", "Salud Financiera"),
        ("growth",    "Salud Crecim."),
        ("risk",      "Nivel Riesgo"),
    ]:
        before_v = dims_before[dim_key]
        after_v  = dims_after[dim_key]
        diff     = after_v - before_v
        diff_str = f"{diff:+.0f}"
        diff_col = Fore.GREEN if diff > 0 else (Fore.RED if diff < 0 else Fore.WHITE)
        lines.append(
            f"  {dim_lbl:<22} {before_v:>8} {after_v:>8} "
            f"{diff_col}{diff_str:>8}{Style.RESET_ALL}"
        )

    diff_overall = overall_after - overall_before
    ov_col = Fore.GREEN if diff_overall > 0 else (Fore.RED if diff_overall < 0 else Fore.WHITE)
    lines += [
        f"  {'─'*22} {'─'*8} {'─'*8} {'─'*8}",
        f"  {'PUNTUACIÓN GLOBAL':<22} {overall_before:>8} "
        f"{ov_col}{overall_after:>8} {diff_overall:>+8}{Style.RESET_ALL}",
        "",
    ]

    # Key KPI before/after
    lines.append(f"  {Fore.WHITE}── IMPACTO EN KPIs CLAVE ──────────────────────{Style.RESET_ALL}")
    for key, lbl, sfx in [
        ("total_revenue",    "Ingresos totales",   ""),
        ("expense_ratio_pct","Ratio gastos",        "%"),
        ("gross_margin_pct", "Margen bruto",        "%"),
        ("net_margin_pct",   "Margen neto",         "%"),
    ]:
        bv = kpis.get(key)
        av = kpis_after.get(key)
        if bv is not None and av is not None:
            diff_kpi = av - bv
            diff_kpi_col = Fore.GREEN if diff_kpi > 0 else (Fore.RED if diff_kpi < 0 else Fore.WHITE)
            lines.append(
                f"  {lbl:<22}: {bv:>12,.2f}{sfx} → "
                f"{diff_kpi_col}{av:>12,.2f}{sfx} ({diff_kpi:+,.2f}){Style.RESET_ALL}"
            )

    lines.append("")
    return "\n".join(lines)

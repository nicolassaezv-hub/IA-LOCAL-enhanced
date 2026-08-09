"""
Decision Explainer — V.1 Roadmap V
====================================
Genera explicaciones en lenguaje natural para las decisiones del Decision Engine.
"""

from __future__ import annotations

from typing import Any

from forex.prediction.reliability_score import ReliabilityReport
from forex.prediction.regime_detector import RegimeAssessment
from forex.prediction.mtf_coherence import MTFCoherenceResult


def explain_decision(
    decision: str,
    reliability: ReliabilityReport,
    regime: RegimeAssessment,
    mtf: MTFCoherenceResult,
    factors_for: list[str] | None = None,
    factors_against: list[str] | None = None,
    risk_info: dict | None = None,
    pair: str = "",
    timeframe: str = "",
) -> str:
    """
    Genera una explicacion completa en español de la decision del Decision Engine.
    """
    factors_for = factors_for or []
    factors_against = factors_against or []
    risk_info = risk_info or {}

    lines: list[str] = []

    # Header
    pair_tf = f"{pair} {timeframe}" if pair else ""
    lines.append(f"Decision para {pair_tf}: {decision}")
    lines.append("")

    # Reliability
    lines.append(f"Confiabilidad: {reliability.reliability_score:.1f}/100 ({reliability.quality_tier})")
    lines.append("")

    # Regime
    lines.append(f"Regimen de mercado: {regime.description}")
    lines.append(f"  ADX: {regime.adx:.1f}, Volatilidad: {regime.volatility_level}, Bias: {regime.directional_bias}")
    lines.append("")

    # MTF
    if mtf.timeframe if hasattr(mtf, 'timeframe') else True:
        lines.append(f"Coherencia Multi-Timeframe: {mtf.coherence_score:.1f}/100")
        lines.append(f"  Alineacion: {mtf.alignment}, Direccion: {mtf.direction}")
        if mtf.forced_hold:
            lines.append("  HOLD forzado por incoherencia MTF.")
        lines.append("")

    # Factors
    if factors_for:
        lines.append("Factores a favor:")
        for f in factors_for:
            lines.append(f"  + {f}")
        lines.append("")

    if factors_against:
        lines.append("Factores en contra:")
        for f in factors_against:
            lines.append(f"  - {f}")
        lines.append("")

    # Risk
    if risk_info:
        lines.append("Analisis de riesgo:")
        if "sl" in risk_info:
            lines.append(f"  Stop Loss: {risk_info['sl']}")
        if "tp" in risk_info:
            lines.append(f"  Take Profit: {risk_info['tp']}")
        if "position_size" in risk_info:
            lines.append(f"  Tamano de posicion: {risk_info['position_size']}")
        if "risk_pct" in risk_info:
            lines.append(f"  Riesgo del capital: {risk_info['risk_pct']}")
        lines.append("")

    # Conclusion
    if decision == "NO OPERAR":
        lines.append("Conclusion: No se recomienda operar en este momento debido a las condiciones del mercado.")
    elif decision == "HOLD":
        lines.append("Conclusion: Mantener posicion actual. Las señales no son suficientemente fuertes para una nueva operacion.")
    elif decision == "BUY":
        lines.append(f"Conclusion: Señal de compra con {reliability.reliability_score:.1f}/100 de confiabilidad. Operar con cautela siguiendo la gestion de riesgo recomendada.")
    elif decision == "SELL":
        lines.append(f"Conclusion: Señal de venta con {reliability.reliability_score:.1f}/100 de confiabilidad. Operar con cautela siguiendo la gestion de riesgo recomendada.")

    return "\n".join(lines)


def build_factors(
    decision: str,
    reliability: ReliabilityReport,
    regime: RegimeAssessment,
    mtf: MTFCoherenceResult,
    circuit_breaker_active: bool = False,
    news_active: bool = False,
    volatility_extreme: bool = False,
) -> tuple[list[str], list[str]]:
    """Construye listas de factores a favor y en contra."""
    factors_for: list[str] = []
    factors_against: list[str] = []

    # Circuit breaker
    if circuit_breaker_active:
        factors_against.append("Circuit Breaker activo — operaciones bloqueadas")
    else:
        factors_for.append("Circuit Breaker desactivado — operaciones permitidas")

    # MTF
    if mtf.coherent:
        factors_for.append(f"Coherencia MTF: {mtf.coherence_score:.1f}/100 — timeframes alineados")
    else:
        factors_against.append(f"Coherencia MTF baja: {mtf.coherence_score:.1f}/100 — timeframes desalineados")

    # Regime
    if regime.is_trending() and decision in ("BUY", "SELL"):
        factors_for.append(f"Regimen tendencial ({regime.primary}) favorece señales direccionales")
    elif regime.is_ranging() and decision in ("BUY", "SELL"):
        factors_against.append(f"Regimen lateral ({regime.primary}) no favorece señales direccionales")

    # News
    if news_active:
        factors_against.append("Noticias de alto impacto activas — mayor incertidumbre")
    else:
        factors_for.append("Sin noticias de alto impacto — condiciones estables")

    # Volatility
    if volatility_extreme:
        factors_against.append("Volatilidad extrema — riesgo fuera de modelo")
    elif regime.volatility_level == "normal":
        factors_for.append("Volatilidad dentro de rango normal")

    # Reliability
    if reliability.should_notify:
        factors_for.append(f"Reliability Score alto: {reliability.reliability_score:.1f}/100")
    elif reliability.forced_hold:
        factors_against.append(f"Reliability Score bajo: {reliability.reliability_score:.1f}/100")

    # Ensemble agreement
    for comp in reliability.components:
        if comp.name == "ensemble_agreement" and comp.score >= 80:
            factors_for.append(f"Alto acuerdo del ensemble: {comp.score:.0f}%")
        elif comp.name == "ensemble_agreement" and comp.score < 50:
            factors_against.append(f"Bajo acuerdo del ensemble: {comp.score:.0f}%")

    return factors_for, factors_against

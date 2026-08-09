"""
Forex Decision Engine — V.1 Roadmap V (⭐⭐⭐⭐⭐)
=================================================
Motor de decision final — consolida todas las señales en
BUY / SELL / HOLD / NO OPERAR + explicacion completa.

Reemplaza la logica fragmentada actual donde cada modulo actua
de forma aislada. Integra:
  - Predicciones del ensemble (XGB/LGB/RF)
  - Confidence Score del predictor
  - Estado del Circuit Breaker
  - Señal de News Intelligence
  - Coherencia Multi-Timeframe (V.3)
  - Volatilidad actual (ATR, BB)
  - Historial de desempeño del modelo
  - Régimen de mercado (V.4)
  - Reliability Score (V.8)

Casos de decision:
  - Circuit Breaker abierto → NO OPERAR forzado
  - MTF incoherente → HOLD forzado
  - Volatilidad extrema → NO OPERAR
  - Noticias de alto impacto activas → NO OPERAR o reducir tamano
  - Reliability Score < umbral → HOLD
  - Todo OK + señal fuerte → BUY / SELL con justificacion
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np

from forex.prediction.reliability_score import ReliabilityReport, ReliabilityScorer
from forex.prediction.regime_detector import RegimeAssessment, RegimeDetector
from forex.prediction.mtf_coherence import MTFCoherenceResult, MTFIntelligence
from forex.prediction.decision_explainer import explain_decision, build_factors


@dataclass
class DecisionResult:
    decision: str = "HOLD"  # BUY, SELL, HOLD, NO_OPERAR
    signal: str = "HOLD"
    reliability_score: float = 0.0
    quality_tier: str = "hold"
    explanation: str = ""
    factors_for: list[str] = field(default_factory=list)
    factors_against: list[str] = field(default_factory=list)
    risk_level: str = "medium"  # low, medium, high
    regime: str = ""
    mtf_coherent: bool = False
    circuit_breaker_active: bool = False
    news_active: bool = False
    volatility_extreme: bool = False
    risk_info: dict = field(default_factory=dict)
    pair: str = ""
    timeframe: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "signal": self.signal,
            "reliability_score": round(self.reliability_score, 2),
            "quality_tier": self.quality_tier,
            "explanation": self.explanation,
            "factors_for": self.factors_for,
            "factors_against": self.factors_against,
            "risk_level": self.risk_level,
            "regime": self.regime,
            "mtf_coherent": self.mtf_coherent,
            "circuit_breaker_active": self.circuit_breaker_active,
            "news_active": self.news_active,
            "volatility_extreme": self.volatility_extreme,
            "risk_info": self.risk_info,
            "pair": self.pair,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)


class DecisionEngine:
    """
    Motor de decision final que consolida todas las señales.
    """

    DEFAULTS = {
        "reliability_threshold": 50.0,
        "notify_threshold": 85.0,
        "volatility_extreme_atr_percentile": 95.0,
        "circuit_breaker_max_consecutive_losses": 5,
    }

    def __init__(self, config: dict | None = None):
        self.config = {**self.DEFAULTS, **(config or {})}

    def decide(
        self,
        ensemble_signal: str = "HOLD",  # BUY, SELL, HOLD
        model_confidence: float = 0.0,
        ensemble_predictions: list[str] | None = None,
        regime: RegimeAssessment | None = None,
        mtf: MTFCoherenceResult | None = None,
        circuit_breaker_active: bool = False,
        news_active: bool = False,
        news_sentiment: str = "",
        volatility_level: str = "normal",
        atr_percentile: float = 50.0,
        model_win_rate: float | None = None,
        model_recent_predictions: int = 0,
        risk_info: dict | None = None,
        pair: str = "",
        timeframe: str = "",
    ) -> DecisionResult:
        """
        Consolida todas las señales y produce una decision final.

        Args:
            ensemble_signal: señal del ensemble (BUY/SELL/HOLD)
            model_confidence: confianza del modelo (0-1 o 0-100)
            ensemble_predictions: lista de predicciones individuales
            regime: assessment del regimen de mercado (V.4)
            mtf: resultado de coherencia MTF (V.3)
            circuit_breaker_active: si el circuit breaker esta abierto
            news_active: si hay noticias de alto impacto
            news_sentiment: sentimiento de noticias
            volatility_level: high/normal/low
            atr_percentile: percentil de ATR (0-100)
            model_win_rate: win rate historico del modelo
            model_recent_predictions: numero de predicciones recientes
            risk_info: info de riesgo del Risk Engine (V.2)
            pair/timeframe: metadatos
        """
        result = DecisionResult(
            signal=ensemble_signal,
            pair=pair,
            timeframe=timeframe,
            risk_info=risk_info or {},
        )

        # Calcular Reliability Score (V.8)
        scorer = ReliabilityScorer()
        mtf_score = mtf.coherence_score if mtf else None
        regime_primary = regime.primary if regime else ""
        regime_confidence = regime.confidence if regime else 0.0

        reliability = scorer.compute(
            model_confidence=model_confidence,
            ensemble_predictions=ensemble_predictions,
            mtf_coherence_score=mtf_score,
            regime_primary=regime_primary,
            regime_confidence=regime_confidence,
            news_active=news_active,
            news_sentiment=news_sentiment,
            volatility_level=volatility_level,
            model_win_rate=model_win_rate,
            model_recent_predictions=model_recent_predictions,
            signal=ensemble_signal,
        )

        result.reliability_score = reliability.reliability_score
        result.quality_tier = reliability.quality_tier

        # Detectar volatilidad extrema
        volatility_extreme = atr_percentile >= self.config["volatility_extreme_atr_percentile"]
        result.volatility_extreme = volatility_extreme

        # Casos de decision — orden de prioridad

        # 1. Circuit Breaker abierto → NO OPERAR forzado
        if circuit_breaker_active:
            result.decision = "NO_OPERAR"
            result.circuit_breaker_active = True
            result.risk_level = "high"

        # 2. Volatilidad extrema → NO OPERAR
        elif volatility_extreme:
            result.decision = "NO_OPERAR"
            result.risk_level = "high"

        # 3. Noticias de alto impacto → NO OPERAR
        elif news_active and news_sentiment in ("high_impact", "negative"):
            result.decision = "NO_OPERAR"
            result.news_active = True
            result.risk_level = "high"

        # 4. MTF incoherente → HOLD forzado
        elif mtf and mtf.forced_hold:
            result.decision = "HOLD"
            result.mtf_coherent = False
            result.risk_level = "medium"

        # 5. Reliability Score < umbral → HOLD
        elif reliability.forced_hold:
            result.decision = "HOLD"
            result.risk_level = "medium"

        # 6. Todo OK + señal fuerte → BUY / SELL
        elif ensemble_signal in ("BUY", "SELL") and reliability.should_display:
            result.decision = ensemble_signal
            result.mtf_coherent = mtf.coherent if mtf else True
            if reliability.should_notify:
                result.risk_level = "low"
            else:
                result.risk_level = "medium"

        # 7. Default → HOLD
        else:
            result.decision = "HOLD"
            result.risk_level = "medium"

        # Construir factores
        result.factors_for, result.factors_against = build_factors(
            result.decision, reliability,
            regime or RegimeAssessment(),
            mtf or MTFCoherenceResult(),
            circuit_breaker_active, news_active, volatility_extreme,
        )

        # Generar explicacion
        result.explanation = explain_decision(
            result.decision, reliability,
            regime or RegimeAssessment(),
            mtf or MTFCoherenceResult(),
            result.factors_for, result.factors_against,
            result.risk_info, pair, timeframe,
        )

        # Metadatos
        if regime:
            result.regime = regime.primary
        if mtf:
            result.mtf_coherent = mtf.coherent
        result.news_active = news_active

        from datetime import datetime
        result.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return result


# ──────────────────────────────────────────────────────
# CLI formatting
# ──────────────────────────────────────────────────────

def cmd_decision_report(result: DecisionResult) -> str:
    """Formatea un DecisionResult para consola."""
    try:
        from colorama import Fore, Style, init
        init(autoreset=True)
        G = Fore.GREEN
        R = Fore.RED
        Y = Fore.YELLOW
        C = Fore.CYAN
        B = Fore.BLUE
        S = Style.RESET_ALL
    except Exception:
        G = R = Y = C = B = S = ""

    lines: list[str] = []

    lines.append(f"\n{C}{'='*65}{S}")
    lines.append(f"{C}  FOREX DECISION ENGINE — V.1 ⭐{S}")
    if result.pair:
        lines.append(f"{C}  {result.pair} · {result.timeframe} · {result.timestamp}{S}")
    lines.append(f"{C}{'='*65}{S}\n")

    decision_colors = {"BUY": G, "SELL": R, "HOLD": Y, "NO_OPERAR": R}
    dec_color = decision_colors.get(result.decision, Y)
    dec_label = result.decision.replace("_", " ")

    lines.append(f"{B}── Decision Final ──{S}")
    lines.append(f"  {dec_color}{dec_label}{S}")
    lines.append(f"  Reliability Score: {result.reliability_score:.1f}/100 ({result.quality_tier})")
    lines.append(f"  Nivel de riesgo:   {result.risk_level}")
    lines.append(f"  Regimen:           {result.regime}")
    lines.append(f"  MTF Coherente:     {'Si' if result.mtf_coherent else 'No'}")
    lines.append(f"  Circuit Breaker:   {'Activo' if result.circuit_breaker_active else 'Inactivo'}")
    lines.append(f"  Noticias activas:  {'Si' if result.news_active else 'No'}")
    lines.append(f"  Volatilidad extrema: {'Si' if result.volatility_extreme else 'No'}\n")

    if result.factors_for:
        lines.append(f"{G}── Factores a Favor ──{S}")
        for f in result.factors_for:
            lines.append(f"  + {f}")
        lines.append("")

    if result.factors_against:
        lines.append(f"{R}── Factores en Contra ──{S}")
        for f in result.factors_against:
            lines.append(f"  - {f}")
        lines.append("")

    if result.risk_info:
        lines.append(f"{B}── Informacion de Riesgo ──{S}")
        for k, v in result.risk_info.items():
            lines.append(f"  {k}: {v}")
        lines.append("")

    lines.append(f"{B}── Explicacion ──{S}")
    for line in result.explanation.split("\n"):
        lines.append(f"  {line}")

    lines.append(f"\n{C}{'='*65}{S}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────

if __name__ == "__main__":
    from forex.prediction.regime_detector import RegimeAssessment
    from forex.prediction.mtf_coherence import MTFCoherenceResult

    engine = DecisionEngine()

    # Test 1: Strong BUY signal
    regime = RegimeAssessment(
        primary="trending_bullish", confidence=85.0, adx=42.0,
        volatility_level="normal", directional_bias="bullish",
        description="Mercado alcista con tendencia fuerte",
    )
    mtf = MTFCoherenceResult(
        coherence_score=88.0, coherent=True, forced_hold=False,
        alignment="fully_aligned", direction="bullish",
    )
    result = engine.decide(
        ensemble_signal="BUY",
        model_confidence=0.85,
        ensemble_predictions=["BUY", "BUY", "BUY"],
        regime=regime,
        mtf=mtf,
        model_win_rate=0.62,
        model_recent_predictions=50,
        pair="EURUSD",
        timeframe="H1",
    )
    print(cmd_decision_report(result))
    assert result.decision == "BUY", f"Expected BUY, got {result.decision}"

    # Test 2: Circuit breaker → NO OPERAR
    result2 = engine.decide(
        ensemble_signal="BUY",
        model_confidence=0.90,
        regime=regime,
        mtf=mtf,
        circuit_breaker_active=True,
        pair="EURUSD",
        timeframe="H1",
    )
    assert result2.decision == "NO_OPERAR", f"Expected NO_OPERAR, got {result2.decision}"

    # Test 3: MTF incoherent → HOLD
    mtf_bad = MTFCoherenceResult(
        coherence_score=40.0, coherent=False, forced_hold=True,
        alignment="misaligned", direction="neutral",
    )
    result3 = engine.decide(
        ensemble_signal="BUY",
        model_confidence=0.75,
        regime=regime,
        mtf=mtf_bad,
        pair="EURUSD",
        timeframe="H1",
    )
    assert result3.decision == "HOLD", f"Expected HOLD, got {result3.decision}"

    # Test 4: News impact → NO OPERAR
    result4 = engine.decide(
        ensemble_signal="BUY",
        model_confidence=0.80,
        regime=regime,
        mtf=mtf,
        news_active=True,
        news_sentiment="high_impact",
        pair="EURUSD",
        timeframe="H1",
    )
    assert result4.decision == "NO_OPERAR", f"Expected NO_OPERAR, got {result4.decision}"

    # Test 5: Weak signal → HOLD
    result5 = engine.decide(
        ensemble_signal="BUY",
        model_confidence=0.45,
        ensemble_predictions=["BUY", "SELL", "HOLD"],
        regime=RegimeAssessment(primary="ranging", confidence=50.0, volatility_level="high"),
        mtf=MTFCoherenceResult(coherence_score=35.0, forced_hold=True),
        pair="EURUSD",
        timeframe="H1",
    )
    assert result5.decision == "HOLD", f"Expected HOLD, got {result5.decision}"

    print("\n=== V.1 PASSED ===")

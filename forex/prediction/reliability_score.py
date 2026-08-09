"""
Prediction Reliability Score — V.8 Roadmap V
==============================================
Reemplaza el Confidence Score binario actual (threshold 0.62-0.65)
por un indice de confiabilidad compuesto 0-100 que considera multiples
factores independientes. Cada factor tiene un peso calibrado; el indice
final determina si la señal supera el umbral de notificacion.

Componentes del indice:
  - Confidence del modelo (~30%)
  - Acuerdo entre modelos del ensemble (~20%)
  - Coherencia Multi-Timeframe (V.3) (~15%)
  - Regimen favorable para el modelo (V.4) (~15%)
  - Ausencia de noticias de alto impacto (~10%)
  - Volatilidad dentro de rango normal (~5%)
  - Historial reciente del modelo (~5%)

Escala de confiabilidad:
  85-100:  Señal de alta calidad → notificar
  70-84:   Señal valida → mostrar en dashboard
  50-69:   Señal debil → registrar, no notificar
  < 50:    HOLD automatico
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np


@dataclass
class ReliabilityComponent:
    name: str
    score: float = 0.0
    weight: float = 0.0
    weighted_score: float = 0.0
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReliabilityReport:
    reliability_score: float = 0.0
    quality_tier: str = "weak"  # high_quality, valid, weak, hold
    should_notify: bool = False
    should_display: bool = False
    forced_hold: bool = False
    components: list[ReliabilityComponent] = field(default_factory=list)
    signal: str = "HOLD"  # BUY, SELL, HOLD, NO_OPERAR
    recommendation: str = ""
    breakdown: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "reliability_score": round(self.reliability_score, 2),
            "quality_tier": self.quality_tier,
            "should_notify": self.should_notify,
            "should_display": self.should_display,
            "forced_hold": self.forced_hold,
            "signal": self.signal,
            "recommendation": self.recommendation,
            "components": [c.to_dict() for c in self.components],
            "breakdown": self.breakdown,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)


class ReliabilityScorer:
    """
    Calculador del indice de confiabilidad compuesto.
    """

    DEFAULT_WEIGHTS = {
        "model_confidence": 0.30,
        "ensemble_agreement": 0.20,
        "mtf_coherence": 0.15,
        "regime_favorable": 0.15,
        "news_absent": 0.10,
        "volatility_normal": 0.05,
        "model_history": 0.05,
    }

    DEFAULT_THRESHOLDS = {
        "notify": 85.0,
        "display": 70.0,
        "weak": 50.0,
    }

    def __init__(
        self,
        weights: dict | None = None,
        thresholds: dict | None = None,
    ):
        self.weights = {**self.DEFAULT_WEIGHTS, **(weights or {})}
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}

    def compute(
        self,
        model_confidence: float,
        ensemble_predictions: list[str] | None = None,
        mtf_coherence_score: float | None = None,
        regime_primary: str = "",
        regime_confidence: float = 0.0,
        news_active: bool = False,
        news_sentiment: str = "",
        volatility_level: str = "normal",
        model_win_rate: float | None = None,
        model_recent_predictions: int = 0,
        signal: str = "HOLD",
    ) -> ReliabilityReport:
        """
        Calcula el Reliability Score compuesto.

        Args:
            model_confidence: confianza del modelo (0-1 o 0-100)
            ensemble_predictions: lista de predicciones del ensemble (e.g. ["BUY","BUY","HOLD"])
            mtf_coherence_score: score de coherencia MTF (0-100, de V.3)
            regime_primary: regimen primario (de V.4)
            regime_confidence: confianza del regimen (0-100, de V.4)
            news_active: si hay noticias de alto impacto activas
            news_sentiment: sentimiento de noticias
            volatility_level: "high", "normal", "low"
            model_win_rate: win rate historico del modelo (0-1 o 0-100)
            model_recent_predictions: numero de predicciones recientes
            signal: señal preliminar (BUY/SELL/HOLD)
        """
        report = ReliabilityReport(signal=signal)
        components: list[ReliabilityComponent] = []

        # 1. Model confidence (0-100)
        mc_score = self._normalize(model_confidence) * 100
        components.append(ReliabilityComponent(
            name="model_confidence",
            score=round(mc_score, 2),
            weight=self.weights["model_confidence"],
            weighted_score=round(mc_score * self.weights["model_confidence"], 2),
            description=f"Confianza del modelo: {mc_score:.1f}/100",
        ))

        # 2. Ensemble agreement (0-100)
        ea_score = self._ensemble_agreement(ensemble_predictions)
        components.append(ReliabilityComponent(
            name="ensemble_agreement",
            score=round(ea_score, 2),
            weight=self.weights["ensemble_agreement"],
            weighted_score=round(ea_score * self.weights["ensemble_agreement"], 2),
            description=f"Acuerdo del ensemble: {ea_score:.1f}/100",
        ))

        # 3. MTF coherence (0-100)
        if mtf_coherence_score is not None:
            mtf_score = float(mtf_coherence_score)
        else:
            mtf_score = 50.0
        components.append(ReliabilityComponent(
            name="mtf_coherence",
            score=round(mtf_score, 2),
            weight=self.weights["mtf_coherence"],
            weighted_score=round(mtf_score * self.weights["mtf_coherence"], 2),
            description=f"Coherencia MTF: {mtf_score:.1f}/100",
        ))

        # 4. Regime favorable (0-100)
        regime_score = self._regime_favorability(regime_primary, regime_confidence, signal)
        components.append(ReliabilityComponent(
            name="regime_favorable",
            score=round(regime_score, 2),
            weight=self.weights["regime_favorable"],
            weighted_score=round(regime_score * self.weights["regime_favorable"], 2),
            description=f"Regimen favorable: {regime_score:.1f}/100 ({regime_primary})",
        ))

        # 5. News absent (0-100)
        news_score = 100.0 if not news_active else 20.0
        if news_active and news_sentiment in ("positive", "negative", "high_impact"):
            news_score = 10.0
        components.append(ReliabilityComponent(
            name="news_absent",
            score=round(news_score, 2),
            weight=self.weights["news_absent"],
            weighted_score=round(news_score * self.weights["news_absent"], 2),
            description=f"Ausencia de noticias: {news_score:.1f}/100",
        ))

        # 6. Volatility normal (0-100)
        vol_scores = {"normal": 100.0, "low": 70.0, "high": 30.0}
        vol_score = vol_scores.get(volatility_level, 50.0)
        components.append(ReliabilityComponent(
            name="volatility_normal",
            score=round(vol_score, 2),
            weight=self.weights["volatility_normal"],
            weighted_score=round(vol_score * self.weights["volatility_normal"], 2),
            description=f"Volatilidad normal: {vol_score:.1f}/100 ({volatility_level})",
        ))

        # 7. Model history (0-100)
        hist_score = self._model_history_score(model_win_rate, model_recent_predictions)
        components.append(ReliabilityComponent(
            name="model_history",
            score=round(hist_score, 2),
            weight=self.weights["model_history"],
            weighted_score=round(hist_score * self.weights["model_history"], 2),
            description=f"Historial del modelo: {hist_score:.1f}/100",
        ))

        report.components = components
        report.reliability_score = sum(c.weighted_score for c in components)
        report.breakdown = {c.name: {"score": c.score, "weight": c.weight, "weighted": c.weighted_score} for c in components}

        report.quality_tier = self._classify_tier(report.reliability_score)
        report.should_notify = report.reliability_score >= self.thresholds["notify"]
        report.should_display = report.reliability_score >= self.thresholds["display"]
        report.forced_hold = report.reliability_score < self.thresholds["weak"]

        if report.forced_hold:
            report.signal = "HOLD"
            report.recommendation = f"HOLD automatico — Reliability Score {report.reliability_score:.1f} < {self.thresholds['weak']}"
        elif report.should_notify:
            report.recommendation = f"Señal de alta calidad — Reliability Score {report.reliability_score:.1f}/100 → NOTIFICAR"
        elif report.should_display:
            report.recommendation = f"Señal valida — Reliability Score {report.reliability_score:.1f}/100 → mostrar en dashboard"
        else:
            report.recommendation = f"Señal debil — Reliability Score {report.reliability_score:.1f}/100 → registrar sin notificar"

        return report

    def _normalize(self, value: float) -> float:
        """Normaliza un valor a 0-1 (acepta 0-1 o 0-100)."""
        if value > 1.0:
            return min(1.0, value / 100.0)
        return max(0.0, min(1.0, value))

    def _ensemble_agreement(self, predictions: list[str] | None) -> float:
        """Calcula el nivel de acuerdo entre modelos del ensemble (0-100)."""
        if not predictions or len(predictions) == 0:
            return 50.0
        from collections import Counter
        counts = Counter(predictions)
        most_common_count = counts.most_common(1)[0][1]
        agreement = most_common_count / len(predictions)
        return agreement * 100.0

    def _regime_favorability(self, regime: str, regime_confidence: float, signal: str) -> float:
        """
        Evalua si el regimen es favorable para la señal.
        Mercados tendenciales favorecen señales direccionales.
        Mercados laterales favorecen HOLD o estrategias de rango.
        """
        if not regime:
            return 50.0

        base = 50.0
        trending = regime in ("trending_bullish", "trending_bearish")
        ranging = regime == "ranging"
        breakout = regime == "breakout"
        high_vol = regime == "high_volatility"
        news = regime == "news_impact"

        if signal == "BUY":
            if regime == "trending_bullish":
                base = 90.0
            elif regime == "breakout":
                base = 75.0
            elif ranging:
                base = 30.0
            elif high_vol:
                base = 20.0
            elif news:
                base = 15.0
            else:
                base = 50.0
        elif signal == "SELL":
            if regime == "trending_bearish":
                base = 90.0
            elif regime == "breakout":
                base = 75.0
            elif ranging:
                base = 30.0
            elif high_vol:
                base = 20.0
            elif news:
                base = 15.0
            else:
                base = 50.0
        elif signal == "HOLD":
            if ranging:
                base = 80.0
            elif high_vol:
                base = 70.0
            elif news:
                base = 85.0
            else:
                base = 40.0

        confidence_factor = regime_confidence / 100.0
        return base * (0.5 + 0.5 * confidence_factor)

    def _model_history_score(self, win_rate: float | None, recent_predictions: int) -> float:
        """Evalua el historial reciente del modelo (0-100)."""
        if win_rate is None or recent_predictions == 0:
            return 50.0

        wr = self._normalize(win_rate)
        wr_score = wr * 100.0

        if recent_predictions < 10:
            confidence_penalty = 0.7
        elif recent_predictions < 30:
            confidence_penalty = 0.85
        else:
            confidence_penalty = 1.0

        return wr_score * confidence_penalty

    def _classify_tier(self, score: float) -> str:
        if score >= self.thresholds["notify"]:
            return "high_quality"
        elif score >= self.thresholds["display"]:
            return "valid"
        elif score >= self.thresholds["weak"]:
            return "weak"
        return "hold"


# ──────────────────────────────────────────────────────
# CLI formatting
# ──────────────────────────────────────────────────────

def cmd_reliability_report(report: ReliabilityReport) -> str:
    """Formatea un ReliabilityReport para consola."""
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
    lines.append(f"{C}  PREDICTION RELIABILITY SCORE — V.8{S}")
    lines.append(f"{C}{'='*65}{S}\n")

    tier_colors = {
        "high_quality": G,
        "valid": C,
        "weak": Y,
        "hold": R,
    }
    tier_labels = {
        "high_quality": "ALTA CALIDAD",
        "valid": "VALIDA",
        "weak": "DEBIL",
        "hold": "HOLD",
    }
    score_color = tier_colors.get(report.quality_tier, Y)

    lines.append(f"{B}── Resultado ──{S}")
    lines.append(f"  Reliability Score:  {score_color}{report.reliability_score:.1f}/100{S}")
    lines.append(f"  Tier:               {score_color}{tier_labels.get(report.quality_tier, report.quality_tier)}{S}")
    lines.append(f"  Señal:              {G if report.signal == 'BUY' else R if report.signal == 'SELL' else Y}{report.signal}{S}")
    lines.append(f"  Notificar:          {G if report.should_notify else 'No'}{'Si' if report.should_notify else ''}{S}")
    lines.append(f"  Mostrar:            {'Si' if report.should_display else 'No'}")
    lines.append(f"  HOLD forzado:       {'Si' if report.forced_hold else 'No'}")
    lines.append(f"  Recomendacion:      {report.recommendation}\n")

    lines.append(f"{B}── Desglose por Componente ──{S}")
    lines.append(f"  {'Componente':<25} {'Score':>8} {'Peso':>6} {'Weighted':>10}")
    lines.append(f"  {'-'*25} {'-'*8} {'-'*6} {'-'*10}")

    for comp in sorted(report.components, key=lambda c: c.weighted_score, reverse=True):
        lines.append(
            f"  {comp.name:<25} {comp.score:>8.1f} {comp.weight:>6.0%} {comp.weighted_score:>10.2f}"
        )
        if comp.description:
            lines.append(f"  {'':>25} {comp.description}")

    lines.append(f"\n  {'TOTAL':<25} {'':>8} {'100%':>6} {report.reliability_score:>10.2f}")

    lines.append(f"\n{C}{'='*65}{S}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────

if __name__ == "__main__":
    scorer = ReliabilityScorer()

    # High quality signal
    report = scorer.compute(
        model_confidence=0.85,
        ensemble_predictions=["BUY", "BUY", "BUY"],
        mtf_coherence_score=88.0,
        regime_primary="trending_bullish",
        regime_confidence=85.0,
        news_active=False,
        volatility_level="normal",
        model_win_rate=0.62,
        model_recent_predictions=50,
        signal="BUY",
    )
    print(cmd_reliability_report(report))
    assert report.should_notify, "Should notify with high quality signal"
    assert report.reliability_score >= 85, f"Score should be >= 85, got {report.reliability_score}"

    # Weak signal
    report2 = scorer.compute(
        model_confidence=0.55,
        ensemble_predictions=["BUY", "SELL", "HOLD"],
        mtf_coherence_score=45.0,
        regime_primary="ranging",
        regime_confidence=60.0,
        news_active=True,
        news_sentiment="high_impact",
        volatility_level="high",
        model_win_rate=0.45,
        model_recent_predictions=5,
        signal="BUY",
    )
    print(cmd_reliability_report(report2))
    assert report2.forced_hold, "Should force hold with weak signal"
    assert report2.reliability_score < 50, f"Score should be < 50, got {report2.reliability_score}"

    # Valid signal
    report3 = scorer.compute(
        model_confidence=0.70,
        ensemble_predictions=["SELL", "SELL", "HOLD"],
        mtf_coherence_score=72.0,
        regime_primary="trending_bearish",
        regime_confidence=75.0,
        news_active=False,
        volatility_level="normal",
        model_win_rate=0.58,
        model_recent_predictions=30,
        signal="SELL",
    )
    print(cmd_reliability_report(report3))
    assert report3.should_display, "Should display valid signal"
    assert 70 <= report3.reliability_score < 85, f"Score should be 70-84, got {report3.reliability_score}"

    print("\n=== V.8 PASSED ===")

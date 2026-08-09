"""
Risk Engine — V.2 Roadmap V
=============================
Extiende el PositionSizer ya existente (Kelly fraccionado x0.25,
clamp 0.5%-2.0%) para generar un analisis de riesgo completo por señal.
ASTRA no ejecuta operaciones — toda la salida es recomendacion analitica.

Inputs:
  - Precio actual y volatilidad (ATR)
  - Confidence y Reliability Score
  - Capital disponible (configurable)
  - Régimen de mercado (V.4)
  - rr_ratio (default 1.0 por regla del usuario)

Recomendaciones:
  - Stop Loss (precio y pips)
  - Take Profit (precio y pips)
  - Riesgo/Recompensa calculado
  - Tamano recomendado de posicion
  - Riesgo porcentual del capital
  - Drawdown esperado de la operacion
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np


@dataclass
class RiskAssessment:
    decision: str = "HOLD"
    pair: str = ""
    timeframe: str = ""
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    sl_pips: float = 0.0
    tp_pips: float = 0.0
    rr_ratio: float = 1.0
    position_size: float = 0.0
    risk_pct: float = 0.0
    risk_amount: float = 0.0
    reward_amount: float = 0.0
    expected_drawdown: float = 0.0
    kelly_fraction: float = 0.0
    regime: str = ""
    atr_value: float = 0.0
    atr_multiplier_sl: float = 1.5
    atr_multiplier_tp: float = 1.5
    capital: float = 10000.0
    risk_level: str = "medium"
    recommendation: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)


class RiskEngine:
    """
    Motor de analisis de riesgo.
    Extiende position_sizing.py con calculos completos de SL/TP y riesgo.
    """

    DEFAULTS = {
        "capital": 10000.0,
        "risk_per_trade_pct": 1.0,
        "max_risk_pct": 2.0,
        "min_risk_pct": 0.5,
        "kelly_fraction": 0.25,
        "rr_ratio_default": 1.0,
        "atr_mult_sl_trending": 1.5,
        "atr_mult_sl_ranging": 2.0,
        "atr_mult_sl_high_vol": 2.5,
        "atr_mult_tp_trending": 1.5,
        "atr_mult_tp_ranging": 1.0,
        "pip_values": {
            "EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01,
            "USDCHF": 0.0001, "AUDUSD": 0.0001, "USDCAD": 0.0001,
            "NZDUSD": 0.0001, "default": 0.0001,
        },
    }

    def __init__(self, config: dict | None = None):
        self.config = {**self.DEFAULTS, **(config or {})}

    def assess(
        self,
        decision: str = "BUY",
        entry_price: float = 0.0,
        atr: float = 0.0,
        reliability_score: float = 0.0,
        model_win_rate: float = 0.5,
        regime: str = "",
        pair: str = "",
        timeframe: str = "",
        capital: float | None = None,
        rr_ratio: float | None = None,
    ) -> RiskAssessment:
        """
        Calcula el analisis de riesgo completo para una señal.
        """
        cap = capital if capital is not None else self.config["capital"]
        rr = rr_ratio if rr_ratio is not None else self.config["rr_ratio_default"]

        result = RiskAssessment(
            decision=decision,
            pair=pair,
            timeframe=timeframe,
            entry_price=entry_price,
            atr_value=atr,
            rr_ratio=rr,
            regime=regime,
            capital=cap,
        )

        if decision not in ("BUY", "SELL"):
            result.recommendation = "No hay señal direccional — no se requiere analisis de riesgo."
            result.risk_level = "none"
            return result

        # ATR multipliers segun regimen
        sl_mult, tp_mult = self._get_atr_multipliers(regime)
        result.atr_multiplier_sl = sl_mult
        result.atr_multiplier_tp = tp_mult

        # Stop Loss y Take Profit
        sl_distance = atr * sl_mult
        tp_distance = atr * tp_mult * rr

        if decision == "BUY":
            result.stop_loss = entry_price - sl_distance
            result.take_profit = entry_price + tp_distance
        else:  # SELL
            result.stop_loss = entry_price + sl_distance
            result.take_profit = entry_price - tp_distance

        # Pips
        pip_value = self._get_pip_value(pair)
        result.sl_pips = abs(sl_distance / pip_value)
        result.tp_pips = abs(tp_distance / pip_value)

        # Kelly fraction
        kelly = self._kelly_criterion(model_win_rate, rr)
        result.kelly_fraction = kelly * self.config["kelly_fraction"]

        # Position sizing
        risk_pct = self._compute_risk_pct(reliability_score, result.kelly_fraction)
        result.risk_pct = risk_pct
        result.risk_amount = cap * (risk_pct / 100.0)
        result.reward_amount = result.risk_amount * rr

        # Position size (units)
        if sl_distance > 0:
            result.position_size = result.risk_amount / sl_distance
        else:
            result.position_size = 0.0

        # Expected drawdown
        result.expected_drawdown = sl_distance

        # Risk level
        result.risk_level = self._classify_risk(reliability_score, risk_pct, regime)

        # Recommendation
        result.recommendation = self._build_recommendation(result)

        return result

    def _get_atr_multipliers(self, regime: str) -> tuple[float, float]:
        """Retorna multiplicadores de ATR para SL y TP segun regimen."""
        if regime in ("trending_bullish", "trending_bearish"):
            return self.config["atr_mult_sl_trending"], self.config["atr_mult_tp_trending"]
        elif regime == "ranging":
            return self.config["atr_mult_sl_ranging"], self.config["atr_mult_tp_ranging"]
        elif regime in ("high_volatility", "news_impact"):
            return self.config["atr_mult_sl_high_vol"], self.config["atr_mult_tp_trending"]
        return self.config["atr_mult_sl_trending"], self.config["atr_mult_tp_trending"]

    def _kelly_criterion(self, win_rate: float, rr: float) -> float:
        """Kelly Criterion: f = (p*b - q) / b donde p=win_rate, q=1-p, b=rr."""
        p = max(0.01, min(0.99, win_rate))
        q = 1.0 - p
        b = max(0.1, rr)
        kelly = (p * b - q) / b
        return max(0.0, kelly)

    def _compute_risk_pct(self, reliability: float, kelly: float) -> float:
        """
        Calcula el porcentaje de riesgo basado en Kelly y Reliability Score.
        Clamp entre min_risk_pct y max_risk_pct.
        """
        base_risk = kelly * 100.0
        reliability_factor = max(0.3, min(1.0, reliability / 100.0))
        adjusted_risk = base_risk * reliability_factor

        return max(self.config["min_risk_pct"], min(self.config["max_risk_pct"], adjusted_risk))

    def _classify_risk(self, reliability: float, risk_pct: float, regime: str) -> str:
        """Clasifica el nivel de riesgo."""
        if regime in ("high_volatility", "news_impact"):
            return "high"
        if reliability >= 85 and risk_pct <= 1.0:
            return "low"
        if reliability >= 70 and risk_pct <= 1.5:
            return "medium"
        return "high"

    def _get_pip_value(self, pair: str) -> float:
        """Retorna el valor de un pip para el par dado."""
        return self.config["pip_values"].get(pair, self.config["pip_values"]["default"])

    def _build_recommendation(self, r: RiskAssessment) -> str:
        """Construye la recomendacion en español."""
        lines = [
            f"Analisis de riesgo para {r.pair} {r.decision}:",
            f"  Entrada: {r.entry_price:.5f}",
            f"  Stop Loss: {r.stop_loss:.5f} ({r.sl_pips:.1f} pips)",
            f"  Take Profit: {r.take_profit:.5f} ({r.tp_pips:.1f} pips)",
            f"  R/R Ratio: {r.rr_ratio:.2f}",
            f"  Tamano de posicion: {r.position_size:.2f} unidades",
            f"  Riesgo: {r.risk_pct:.2f}% del capital ({r.risk_amount:.2f})",
            f"  Recompensa esperada: {r.reward_amount:.2f}",
            f"  Kelly fraction: {r.kelly_fraction:.4f}",
            f"  Nivel de riesgo: {r.risk_level}",
        ]
        return "\n".join(lines)


# ──────────────────────────────────────────────────────
# CLI formatting
# ──────────────────────────────────────────────────────

def cmd_risk_report(risk: RiskAssessment) -> str:
    """Formatea un RiskAssessment para consola."""
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

    lines.append(f"\n{C}{'='*60}{S}")
    lines.append(f"{C}  RISK ENGINE — V.2{S}")
    if risk.pair:
        lines.append(f"{C}  {risk.pair} · {risk.timeframe} · {risk.decision}{S}")
    lines.append(f"{C}{'='*60}{S}\n")

    if risk.decision not in ("BUY", "SELL"):
        lines.append(f"  {Y}No hay señal direccional.{S}")
        lines.append(f"  {risk.recommendation}")
        lines.append(f"\n{C}{'='*60}{S}")
        return "\n".join(lines)

    risk_colors = {"low": G, "medium": Y, "high": R, "none": C}
    rc = risk_colors.get(risk.risk_level, Y)

    lines.append(f"{B}── Precios ──{S}")
    lines.append(f"  Entrada:       {risk.entry_price:.5f}")
    lines.append(f"  Stop Loss:     {R}{risk.stop_loss:.5f}{S} ({risk.sl_pips:.1f} pips)")
    lines.append(f"  Take Profit:   {G}{risk.take_profit:.5f}{S} ({risk.tp_pips:.1f} pips)")
    lines.append(f"  R/R Ratio:     {risk.rr_ratio:.2f}\n")

    lines.append(f"{B}── Posicion ──{S}")
    lines.append(f"  Tamano:        {risk.position_size:.2f} unidades")
    lines.append(f"  Riesgo:        {rc}{risk.risk_pct:.2f}%{S} ({risk.risk_amount:.2f})")
    lines.append(f"  Recompensa:    {G}{risk.reward_amount:.2f}{S}")
    lines.append(f"  Kelly:         {risk.kelly_fraction:.4f}")
    lines.append(f"  Drawdown esp:  {risk.expected_drawdown:.5f}\n")

    lines.append(f"{B}── Evaluacion ──{S}")
    lines.append(f"  Nivel de riesgo: {rc}{risk.risk_level}{S}")
    lines.append(f"  Regimen:         {risk.regime}")
    lines.append(f"  ATR:             {risk.atr_value:.5f}")
    lines.append(f"  SL mult:         {risk.atr_multiplier_sl}")
    lines.append(f"  TP mult:         {risk.atr_multiplier_tp}\n")

    lines.append(f"{C}{'='*60}{S}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = RiskEngine()

    # BUY signal with trending regime
    risk = engine.assess(
        decision="BUY",
        entry_price=1.0850,
        atr=0.0045,
        reliability_score=85.0,
        model_win_rate=0.60,
        regime="trending_bullish",
        pair="EURUSD",
        timeframe="H1",
    )
    print(cmd_risk_report(risk))
    assert risk.stop_loss < risk.entry_price, "SL should be below entry for BUY"
    assert risk.take_profit > risk.entry_price, "TP should be above entry for BUY"
    assert risk.risk_pct >= 0.5, "Risk should be at least min"
    assert risk.risk_pct <= 2.0, "Risk should be at most max"

    # SELL signal with high volatility
    risk2 = engine.assess(
        decision="SELL",
        entry_price=1.0850,
        atr=0.0060,
        reliability_score=72.0,
        model_win_rate=0.55,
        regime="high_volatility",
        pair="EURUSD",
        timeframe="H1",
    )
    print(cmd_risk_report(risk2))
    assert risk2.stop_loss > risk2.entry_price, "SL should be above entry for SELL"
    assert risk2.take_profit < risk2.entry_price, "TP should be below entry for SELL"
    assert risk2.risk_level == "high", "High vol regime should be high risk"

    # HOLD signal
    risk3 = engine.assess(
        decision="HOLD",
        entry_price=1.0850,
        pair="EURUSD",
        timeframe="H1",
    )
    print(cmd_risk_report(risk3))
    assert risk3.risk_level == "none"

    print("\n=== V.2 PASSED ===")

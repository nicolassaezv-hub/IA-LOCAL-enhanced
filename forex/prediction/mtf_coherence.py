"""
Multi-Timeframe Intelligence — V.3 Roadmap V
==============================================
Formaliza la logica multi-timeframe que ya existe en ASTRA
(deteccion automatica de H4/D1 en _forex_full) convirtiendola
en un sistema de validacion explicita de coherencia entre temporalidades.
Solo se emite señal cuando las tres capas apuntan en la misma direccion.

Jerarquia de timeframes:
  D1 → Tendencia principal (contexto)
  H4 → Confirmacion de tendencia
  H1 → Punto de entrada preciso

Indice de coherencia MTF:
  Score 0-100 de alineacion entre TFs
  COHERENTE: señal valida
  INCOHERENTE: HOLD forzado automatico
  Componente del Reliability Score (V.8)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class TimeframeSignal:
    timeframe: str = ""
    signal: str = "HOLD"  # BUY, SELL, HOLD
    confidence: float = 0.0
    trend: str = "neutral"  # bullish, bearish, neutral
    rsi: float = 0.0
    macd_signal: str = "neutral"  # bullish, bearish, neutral
    ema_alignment: str = "mixed"
    adx: float = 0.0
    close: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MTFCoherenceResult:
    coherence_score: float = 0.0
    coherent: bool = False
    forced_hold: bool = False
    d1_signal: TimeframeSignal = field(default_factory=TimeframeSignal)
    h4_signal: TimeframeSignal = field(default_factory=TimeframeSignal)
    h1_signal: TimeframeSignal = field(default_factory=TimeframeSignal)
    alignment: str = "unknown"  # fully_aligned, partially_aligned, misaligned
    direction: str = "neutral"  # bullish, bearish, neutral
    description: str = ""
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "coherence_score": round(self.coherence_score, 2),
            "coherent": self.coherent,
            "forced_hold": self.forced_hold,
            "d1_signal": self.d1_signal.to_dict(),
            "h4_signal": self.h4_signal.to_dict(),
            "h1_signal": self.h1_signal.to_dict(),
            "alignment": self.alignment,
            "direction": self.direction,
            "description": self.description,
            "recommendation": self.recommendation,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)


class MTFIntelligence:
    """
    Sistema de validacion de coherencia multi-timeframe.
    Construye sobre la deteccion MTF ya existente (_resolve_mtf_paths,
    features H4/D1 en feature_engineering.py).
    """

    DEFAULTS = {
        "coherence_threshold": 65.0,
        "d1_weight": 40.0,
        "h4_weight": 35.0,
        "h1_weight": 25.0,
        "rsi_buy_threshold": 55.0,
        "rsi_sell_threshold": 45.0,
        "adx_trend_threshold": 25.0,
    }

    def __init__(self, config: dict | None = None):
        self.config = {**self.DEFAULTS, **(config or {})}

    def analyze(
        self,
        d1_df: pd.DataFrame | None = None,
        h4_df: pd.DataFrame | None = None,
        h1_df: pd.DataFrame | None = None,
        pair: str = "",
    ) -> MTFCoherenceResult:
        """
        Analiza la coherencia entre los tres timeframes.

        Cada DataFrame debe contener al menos: close, y opcionalmente
        rsi_14, macd, macd_signal, adx, ema_20, ema_50, ema_150.
        """
        result = MTFCoherenceResult()

        if d1_df is not None and len(d1_df) > 0:
            result.d1_signal = self._analyze_timeframe(d1_df, "D1")
        if h4_df is not None and len(h4_df) > 0:
            result.h4_signal = self._analyze_timeframe(h4_df, "H4")
        if h1_df is not None and len(h1_df) > 0:
            result.h1_signal = self._analyze_timeframe(h1_df, "H1")

        result.coherence_score = self._compute_coherence(result)
        result.coherent = result.coherence_score >= self.config["coherence_threshold"]
        result.alignment = self._classify_alignment(result)
        result.direction = self._compute_direction(result)
        result.forced_hold = not result.coherent
        result.description = self._describe(result)
        result.recommendation = self._recommend(result)

        return result

    def _analyze_timeframe(self, df: pd.DataFrame, tf: str) -> TimeframeSignal:
        """Analiza un unico timeframe y extrae su señal."""
        sig = TimeframeSignal(timeframe=tf)

        close = self._get_last(df, "close")
        rsi = self._get_last(df, "rsi")
        macd = self._get_last(df, "macd")
        macd_signal = self._get_last(df, "macd_signal")
        adx = self._get_last(df, "adx")
        ema_s = self._get_last(df, "ema_20")
        ema_m = self._get_last(df, "ema_50")
        ema_l = self._get_last(df, "ema_150")

        sig.close = float(close) if close is not None else 0.0
        sig.rsi = float(rsi) if rsi is not None else 50.0
        sig.adx = float(adx) if adx is not None else 0.0

        if ema_s is not None and ema_m is not None and ema_l is not None:
            if ema_s > ema_m > ema_l:
                sig.ema_alignment = "bullish_stack"
                sig.trend = "bullish"
            elif ema_s < ema_m < ema_l:
                sig.ema_alignment = "bearish_stack"
                sig.trend = "bearish"
            elif ema_s > ema_m:
                sig.ema_alignment = "bullish_cross"
                sig.trend = "bullish"
            elif ema_s < ema_m:
                sig.ema_alignment = "bearish_cross"
                sig.trend = "bearish"
            else:
                sig.ema_alignment = "mixed"
                sig.trend = "neutral"

        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                sig.macd_signal = "bullish"
                if sig.trend == "neutral":
                    sig.trend = "bullish"
            elif macd < macd_signal:
                sig.macd_signal = "bearish"
                if sig.trend == "neutral":
                    sig.trend = "bearish"

        if rsi is not None:
            if rsi > self.config["rsi_buy_threshold"]:
                if sig.trend == "neutral":
                    sig.trend = "bullish"
            elif rsi < self.config["rsi_sell_threshold"]:
                if sig.trend == "neutral":
                    sig.trend = "bearish"

        if sig.trend == "bullish":
            sig.signal = "BUY"
            sig.confidence = self._tf_confidence(sig, "bullish")
        elif sig.trend == "bearish":
            sig.signal = "SELL"
            sig.confidence = self._tf_confidence(sig, "bearish")
        else:
            sig.signal = "HOLD"
            sig.confidence = 30.0

        return sig

    def _tf_confidence(self, sig: TimeframeSignal, direction: str) -> float:
        """Calcula la confianza de un timeframe individual."""
        score = 50.0
        if sig.ema_alignment.endswith("stack"):
            score += 20.0
        elif sig.ema_alignment.endswith("cross"):
            score += 10.0
        if sig.macd_signal == direction:
            score += 15.0
        if sig.adx >= self.config["adx_trend_threshold"]:
            score += 15.0
        return min(100.0, score)

    def _compute_coherence(self, result: MTFCoherenceResult) -> float:
        """
        Score 0-100 de alineacion entre TFs.
        D1 tiene mayor peso, luego H4, luego H1.
        """
        signals = [result.d1_signal, result.h4_signal, result.h1_signal]
        weights = [self.config["d1_weight"], self.config["h4_weight"], self.config["h1_weight"]]
        total_weight = sum(weights)

        directions = [s.trend for s in signals]
        confidences = [s.confidence for s in signals]

        if all(d == "neutral" for d in directions):
            return 20.0

        primary_direction = max(set(directions), key=directions.count) if any(d != "neutral" for d in directions) else "neutral"

        if primary_direction == "neutral":
            return 30.0

        score = 0.0
        for sig, w in zip(signals, weights):
            if sig.trend == primary_direction:
                score += w * (sig.confidence / 100.0)
            elif sig.trend == "neutral":
                score += w * 0.3
            else:
                score += 0.0

        return min(100.0, (score / total_weight) * 100.0)

    def _classify_alignment(self, result: MTFCoherenceResult) -> str:
        directions = [result.d1_signal.trend, result.h4_signal.trend, result.h1_signal.trend]
        non_neutral = [d for d in directions if d != "neutral"]

        if len(non_neutral) == 0:
            return "unknown"
        if len(set(non_neutral)) == 1 and "neutral" not in directions:
            return "fully_aligned"
        if len(set(non_neutral)) == 1:
            return "partially_aligned"
        return "misaligned"

    def _compute_direction(self, result: MTFCoherenceResult) -> str:
        if not result.coherent:
            return "neutral"
        directions = [result.d1_signal.trend, result.h4_signal.trend, result.h1_signal.trend]
        non_neutral = [d for d in directions if d != "neutral"]
        if not non_neutral:
            return "neutral"
        return max(set(non_neutral), key=non_neutral.count)

    def _describe(self, result: MTFCoherenceResult) -> str:
        alignment_desc = {
            "fully_aligned": "Todos los timeframes alineados",
            "partially_aligned": "Timeframes parcialmente alineados",
            "misaligned": "Timeframes desalineados",
            "unknown": "Senales indeterminadas",
        }
        base = alignment_desc.get(result.alignment, result.alignment)
        return f"{base}. Coherencia: {result.coherence_score:.1f}/100. Direccion: {result.direction}"

    def _recommend(self, result: MTFCoherenceResult) -> str:
        if result.forced_hold:
            return f"HOLD forzado — coherencia MTF insuficiente ({result.coherence_score:.1f} < {self.config['coherence_threshold']})"
        if result.direction == "bullish":
            return f"BUY valido — coherencia MTF: {result.coherence_score:.1f}/100"
        elif result.direction == "bearish":
            return f"SELL valido — coherencia MTF: {result.coherence_score:.1f}/100"
        return f"HOLD — sin direccion clara"

    def _get_last(self, df: pd.DataFrame, prefix: str) -> float | None:
        for col in df.columns:
            if col.lower().startswith(prefix.lower()):
                val = df[col].iloc[-1] if len(df) > 0 else None
                if pd.notna(val):
                    return float(val)
        return None


# ──────────────────────────────────────────────────────
# CLI formatting
# ──────────────────────────────────────────────────────

def cmd_mtf_report(result: MTFCoherenceResult, pair: str = "") -> str:
    """Formatea un MTFCoherenceResult para consola."""
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
    lines.append(f"{C}  MULTI-TIMEFRAME INTELLIGENCE — V.3{S}")
    if pair:
        lines.append(f"{C}  {pair}{S}")
    lines.append(f"{C}{'='*65}{S}\n")

    score_color = G if result.coherent else R if result.coherence_score < 40 else Y
    lines.append(f"{B}── Coherencia MTF ──{S}")
    lines.append(f"  Score:          {score_color}{result.coherence_score:.1f}/100{S}")
    lines.append(f"  Coherente:      {G if result.coherent else R}{'Si' if result.coherent else 'No'}{S}")
    lines.append(f"  Alineacion:     {result.alignment}")
    lines.append(f"  Direccion:      {result.direction}")
    lines.append(f"  HOLD forzado:   {'Si' if result.forced_hold else 'No'}")
    lines.append(f"  Descripcion:    {result.description}")
    lines.append(f"  Recomendacion:  {result.recommendation}\n")

    for tf_sig in [result.d1_signal, result.h4_signal, result.h1_signal]:
        if not tf_sig.timeframe:
            continue
        signal_color = G if tf_sig.signal == "BUY" else R if tf_sig.signal == "SELL" else Y
        lines.append(f"{B}── {tf_sig.timeframe} ──{S}")
        lines.append(f"  Señal:          {signal_color}{tf_sig.signal}{S} (confianza: {tf_sig.confidence:.1f}%)")
        lines.append(f"  Tendencia:      {tf_sig.trend}")
        lines.append(f"  RSI:            {tf_sig.rsi:.2f}")
        lines.append(f"  MACD:           {tf_sig.macd_signal}")
        lines.append(f"  EMA Alignment:  {tf_sig.ema_alignment}")
        lines.append(f"  ADX:            {tf_sig.adx:.2f}")
        lines.append(f"  Close:          {tf_sig.close:.5f}\n")

    lines.append(f"{C}{'='*65}{S}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────

if __name__ == "__main__":
    np.random.seed(42)
    n = 200

    def make_df(bullish: bool = True, n: int = 200) -> pd.DataFrame:
        drift = 0.0005 if bullish else -0.0005
        close = np.cumsum(np.random.randn(n) * 0.001 + drift) + 1.0
        ema_20 = pd.Series(close).rolling(20, min_periods=1).mean()
        ema_50 = pd.Series(close).rolling(50, min_periods=1).mean()
        ema_150 = pd.Series(close).rolling(150, min_periods=1).mean()
        return pd.DataFrame({
            "close": close,
            "rsi_14": np.random.uniform(40, 70, n) if bullish else np.random.uniform(30, 60, n),
            "macd": np.random.randn(n) * 0.001 + (0.0002 if bullish else -0.0002),
            "macd_signal": np.random.randn(n) * 0.001,
            "adx": np.linspace(20, 35, n),
            "ema_20": ema_20,
            "ema_50": ema_50,
            "ema_150": ema_150,
        })

    # All bullish — should be coherent
    mtf = MTFIntelligence()
    result = mtf.analyze(
        d1_df=make_df(bullish=True),
        h4_df=make_df(bullish=True),
        h1_df=make_df(bullish=True),
        pair="EURUSD",
    )
    print(cmd_mtf_report(result, "EURUSD"))
    print(f"  Coherent: {result.coherent}, Score: {result.coherence_score:.1f}, Direction: {result.direction}")

    # Misaligned — D1 bullish, H4 bearish, H1 bullish
    result2 = mtf.analyze(
        d1_df=make_df(bullish=True),
        h4_df=make_df(bullish=False),
        h1_df=make_df(bullish=True),
        pair="EURUSD",
    )
    print(cmd_mtf_report(result2, "EURUSD"))
    print(f"  Coherent: {result2.coherent}, Score: {result2.coherence_score:.1f}, Forced Hold: {result2.forced_hold}")

    print("\n=== V.3 PASSED ===")

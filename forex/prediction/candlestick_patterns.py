"""
VI.5.D — Candlestick Pattern Detector
Detección de patrones japoneses clásicos sin dependencia de TA-Lib.
Implementación pura en Python/pandas para portabilidad.
Integrado como feature adicional — suma evidencia a la señal del modelo.
"""
import pandas as pd
import numpy as np
from typing import Optional


def _body(o, c): return abs(c - o)
def _upper_shadow(o, c, h): return h - max(o, c)
def _lower_shadow(o, c, l): return min(o, c) - l
def _is_bullish(o, c): return c > o
def _is_bearish(o, c): return c < o


class CandlestickPatternDetector:
    """
    Detecta patrones de velas japonesas clásicos.
    No requiere TA-Lib — implementación pura en pandas.
    """

    def detect(self, df: pd.DataFrame) -> dict:
        """
        Detecta patrones en las últimas filas del DataFrame.
        Retorna un dict con los patrones detectados y si confirman señal BUY/SELL.
        """
        if df is None or len(df) < 3:
            return {"patterns": [], "bias": "neutral", "confirm_buy": False, "confirm_sell": False}

        detected = []

        # Última y penúltima vela
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3] if len(df) >= 3 else prev

        o1, h1, l1, c1 = float(last["open"]), float(last["high"]), float(last["low"]), float(last["close"])
        o2, h2, l2, c2 = float(prev["open"]), float(prev["high"]), float(prev["low"]), float(prev["close"])
        o3, h3, l3, c3 = float(prev2["open"]), float(prev2["high"]), float(prev2["low"]), float(prev2["close"])

        body1 = _body(o1, c1)
        body2 = _body(o2, c2)
        avg_body = df["close"].diff().abs().rolling(10, min_periods=3).mean().iloc[-1]
        if avg_body is None or (hasattr(avg_body, '__float__') and __import__('math').isnan(float(avg_body))) or avg_body == 0:
            avg_body = 0.001

        # ── Patrones Alcistas ──────────────────────────────────────────

        # Doji (indecisión — no sesgo direccional fuerte)
        if body1 < avg_body * 0.1 and _upper_shadow(o1, c1, h1) + _lower_shadow(o1, c1, l1) > body1 * 3:
            detected.append({"name": "Doji", "bias": "neutral"})

        # Hammer (alcista — sombra inferior larga, cuerpo pequeño arriba)
        lower_sh = _lower_shadow(o1, c1, l1)
        if (lower_sh >= body1 * 2 and
                _upper_shadow(o1, c1, h1) < body1 * 0.5 and
                body1 < avg_body * 1.5):
            detected.append({"name": "Hammer", "bias": "bullish"})

        # Shooting Star (bajista — sombra superior larga, cuerpo pequeño abajo)
        upper_sh = _upper_shadow(o1, c1, h1)
        if (upper_sh >= body1 * 2 and
                _lower_shadow(o1, c1, l1) < body1 * 0.5 and
                body1 < avg_body * 1.5 and _is_bearish(o1, c1)):
            detected.append({"name": "Shooting Star", "bias": "bearish"})

        # Bullish Engulfing
        if (_is_bearish(o2, c2) and _is_bullish(o1, c1) and
                c1 > o2 and o1 < c2 and body1 > body2):
            detected.append({"name": "Bullish Engulfing", "bias": "bullish"})

        # Bearish Engulfing
        if (_is_bullish(o2, c2) and _is_bearish(o1, c1) and
                c1 < o2 and o1 > c2 and body1 > body2):
            detected.append({"name": "Bearish Engulfing", "bias": "bearish"})

        # Bullish Harami
        if (_is_bearish(o2, c2) and _is_bullish(o1, c1) and
                o1 > c2 and c1 < o2 and body1 < body2 * 0.6):
            detected.append({"name": "Bullish Harami", "bias": "bullish"})

        # Bearish Harami
        if (_is_bullish(o2, c2) and _is_bearish(o1, c1) and
                o1 < c2 and c1 > o2 and body1 < body2 * 0.6):
            detected.append({"name": "Bearish Harami", "bias": "bearish"})

        # Morning Star (alcista — 3 velas)
        if (_is_bearish(o3, c3) and body2 < avg_body * 0.5 and _is_bullish(o1, c1) and
                c1 > (o3 + c3) / 2 and body3 > avg_body * 0.8):
            detected.append({"name": "Morning Star", "bias": "bullish"})

        # Evening Star (bajista — 3 velas)
        body3 = _body(o3, c3)
        if (_is_bullish(o3, c3) and body2 < avg_body * 0.5 and _is_bearish(o1, c1) and
                c1 < (o3 + c3) / 2 and body3 > avg_body * 0.8):
            detected.append({"name": "Evening Star", "bias": "bearish"})

        # ── Determinar sesgo neto ──────────────────────────────────────
        bullish = sum(1 for p in detected if p["bias"] == "bullish")
        bearish = sum(1 for p in detected if p["bias"] == "bearish")

        if bullish > bearish:
            bias = "bullish"
        elif bearish > bullish:
            bias = "bearish"
        else:
            bias = "neutral"

        return {
            "patterns": detected,
            "bias": bias,
            "confirm_buy":  bias == "bullish",
            "confirm_sell": bias == "bearish",
            "pattern_names": [p["name"] for p in detected],
        }

    def format_result(self, result: dict) -> str:
        """Formatea el resultado para mostrar en consola."""
        patterns = result.get("pattern_names", [])
        bias = result.get("bias", "neutral")
        if not patterns:
            return "  Sin patrones de vela detectados."
        bias_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}.get(bias, "⚪")
        pnames = ", ".join(patterns)
        return f"  {bias_emoji} Patrones detectados: {pnames}  (sesgo: {bias})"


_detector = CandlestickPatternDetector()


def get_detector() -> CandlestickPatternDetector:
    return _detector


def detect_patterns(df: pd.DataFrame) -> dict:
    """Atajo rápido para detectar patrones."""
    return _detector.detect(df)

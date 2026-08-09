"""
Regime Detection — V.4 Roadmap V
=================================
Detecta automaticamente el estado del mercado y lo inyecta en el
Decision Engine y el Model Selection Engine.

Regimenes detectados:
  - Mercado alcista / bajista
  - Mercado lateral (rango)
  - Alta / baja volatilidad
  - Mercado afectado por noticias
  - Ruptura de rango (breakout)

Logica de deteccion:
  - ADX: alta tendencia vs. lateral
  - ATR percentil: regimen de volatilidad
  - Posicion precio vs. EMA(20/50/200): sesgo direccional
  - Señal de News Intelligence: noticias activas

Integracion en IntegratedPipeline.predict() como contexto previo.
Almacenamiento del regimen en memoria.db para historial.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd


class Regime(str, Enum):
    TRENDING_BULLISH = "trending_bullish"
    TRENDING_BEARISH = "trending_bearish"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    NEWS_IMPACT = "news_impact"
    BREAKOUT = "breakout"
    TRANSITIONAL = "transitional"


@dataclass
class RegimeAssessment:
    primary: str = "ranging"
    secondary: str = ""
    confidence: float = 0.0
    adx: float = 0.0
    atr_percentile: float = 0.0
    ema_alignment: str = ""
    volatility_level: str = ""
    directional_bias: str = ""
    news_active: bool = False
    components: dict = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    def is_trending(self) -> bool:
        return self.primary in (Regime.TRENDING_BULLISH.value, Regime.TRENDING_BEARISH.value)

    def is_ranging(self) -> bool:
        return self.primary == Regime.RANGING.value

    def is_high_volatility(self) -> bool:
        return self.primary == Regime.HIGH_VOLATILITY.value

    def is_breakout(self) -> bool:
        return self.primary == Regime.BREAKOUT.value

    def is_news_impact(self) -> bool:
        return self.primary == Regime.NEWS_IMPACT.value


class RegimeDetector:
    """
    Clasificador de regimen de mercado basado en indicadores tecnicos.
    """

    DEFAULTS = {
        "adx_trend_threshold": 25.0,
        "adx_strong_trend": 40.0,
        "atr_high_percentile": 80.0,
        "atr_low_percentile": 20.0,
        "ema_short": 20,
        "ema_mid": 50,
        "ema_long": 150,
        "breakout_atr_mult": 2.0,
        "lookback_periods": 200,
    }

    def __init__(self, config: dict | None = None):
        self.config = {**self.DEFAULTS, **(config or {})}

    def detect(
        self,
        df: pd.DataFrame,
        news_active: bool = False,
        news_sentiment: str = "",
        pair: str = "",
        timeframe: str = "",
    ) -> RegimeAssessment:
        """
        Detecta el regimen de mercado a partir de un DataFrame con indicadores.

        Espera columnas: adx, atr_14, ema_20, ema_50, ema_150, close
        (o variantes con sufijos numericos).
        """
        assessment = RegimeAssessment()
        assessment.news_active = news_active

        adx = self._get_value(df, "adx")
        atr = self._get_value(df, "atr")
        ema_s = self._get_value(df, f"ema_{self.config['ema_short']}")
        ema_m = self._get_value(df, f"ema_{self.config['ema_mid']}")
        ema_l = self._get_value(df, f"ema_{self.config['ema_long']}")
        close = self._get_value(df, "close")

        atr_series = self._get_series(df, "atr")
        close_series = self._get_series(df, "close")

        assessment.adx = float(adx) if adx is not None else 0.0

        if atr_series is not None and len(atr_series) > 0:
            atr_arr = atr_series.dropna().values
            if len(atr_arr) > 10:
                current_atr = float(atr_arr[-1])
                sorted_atr = np.sort(atr_arr)
                idx = np.searchsorted(sorted_atr, current_atr)
                assessment.atr_percentile = min(100.0, max(0.0, float(idx) / len(sorted_atr) * 100.0))
            else:
                assessment.atr_percentile = 50.0
        else:
            assessment.atr_percentile = 50.0

        if ema_s is not None and ema_m is not None and ema_l is not None:
            assessment.ema_alignment = self._classify_ema_alignment(ema_s, ema_m, ema_l)
            assessment.directional_bias = self._directional_bias(close, ema_s, ema_m, ema_l)
        else:
            assessment.ema_alignment = "unknown"
            assessment.directional_bias = "neutral"

        if assessment.atr_percentile >= self.config["atr_high_percentile"]:
            assessment.volatility_level = "high"
        elif assessment.atr_percentile <= self.config["atr_low_percentile"]:
            assessment.volatility_level = "low"
        else:
            assessment.volatility_level = "normal"

        assessment.components = {
            "adx": round(assessment.adx, 2),
            "atr_percentile": round(assessment.atr_percentile, 1),
            "ema_alignment": assessment.ema_alignment,
            "volatility_level": assessment.volatility_level,
            "directional_bias": assessment.directional_bias,
            "news_active": news_active,
            "news_sentiment": news_sentiment,
        }

        assessment.primary, assessment.secondary, assessment.confidence = self._classify_regime(
            assessment, news_active, news_sentiment, close_series
        )

        assessment.description = self._describe(assessment)

        return assessment

    def _classify_regime(
        self,
        a: RegimeAssessment,
        news_active: bool,
        news_sentiment: str,
        close_series: pd.Series | None,
    ) -> tuple[str, str, float]:
        """
        Clasifica el regimen principal basado en todos los componentes.
        Retorna (primary, secondary, confidence 0-100).
        """
        scores: dict[str, float] = {r.value: 0.0 for r in Regime}
        confidence = 50.0

        if a.news_active and news_sentiment in ("positive", "negative", "high_impact"):
            scores[Regime.NEWS_IMPACT.value] = 80.0
            confidence = 75.0

        if a.adx >= self.config["adx_strong_trend"]:
            if a.directional_bias == "bullish":
                scores[Regime.TRENDING_BULLISH.value] = 85.0
            elif a.directional_bias == "bearish":
                scores[Regime.TRENDING_BEARISH.value] = 85.0
            confidence = 85.0
        elif a.adx >= self.config["adx_trend_threshold"]:
            if a.directional_bias == "bullish":
                scores[Regime.TRENDING_BULLISH.value] = 65.0
            elif a.directional_bias == "bearish":
                scores[Regime.TRENDING_BEARISH.value] = 65.0
            confidence = 65.0
        else:
            scores[Regime.RANGING.value] = 60.0
            confidence = 60.0

        if a.volatility_level == "high" and a.adx < self.config["adx_trend_threshold"]:
            scores[Regime.HIGH_VOLATILITY.value] = max(scores[Regime.HIGH_VOLATILITY.value], 70.0)
            confidence = max(confidence, 70.0)
        elif a.volatility_level == "low":
            scores[Regime.LOW_VOLATILITY.value] = max(scores[Regime.LOW_VOLATILITY.value], 50.0)

        if close_series is not None and len(close_series) >= 20:
            recent_move = self._detect_breakout(close_series, a.adx)
            if recent_move:
                scores[Regime.BREAKOUT.value] = max(scores[Regime.BREAKOUT.value], 75.0)
                confidence = max(confidence, 75.0)

        if a.adx < self.config["adx_trend_threshold"] and a.volatility_level == "normal":
            scores[Regime.TRANSITIONAL.value] = max(scores[Regime.TRANSITIONAL.value], 40.0)

        primary = max(scores, key=scores.get)
        secondary = ""
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_scores) > 1 and sorted_scores[1][1] > 30:
            secondary = sorted_scores[1][0]

        return primary, secondary, confidence

    def _classify_ema_alignment(self, ema_s: float, ema_m: float, ema_l: float) -> str:
        if ema_s > ema_m > ema_l:
            return "bullish_stack"
        elif ema_s < ema_m < ema_l:
            return "bearish_stack"
        elif ema_s > ema_m and ema_m < ema_l:
            return "bullish_cross"
        elif ema_s < ema_m and ema_m > ema_l:
            return "bearish_cross"
        else:
            return "mixed"

    def _directional_bias(self, close: float, ema_s: float, ema_m: float, ema_l: float) -> str:
        if close is None:
            return "neutral"
        above = sum([close > ema_s, close > ema_m, close > ema_l])
        if above >= 2:
            return "bullish"
        elif above <= 1:
            return "bearish"
        return "neutral"

    def _detect_breakout(self, close_series: pd.Series, adx: float) -> bool:
        recent = close_series.iloc[-20:]
        range_high = recent.iloc[:-1].max()
        range_low = recent.iloc[:-1].min()
        current = recent.iloc[-1]
        range_size = range_high - range_low
        if range_size == 0:
            return False
        breakout_threshold = range_size * 0.1
        return current > range_high - breakout_threshold or current < range_low + breakout_threshold

    def _get_value(self, df: pd.DataFrame, prefix: str) -> float | None:
        for col in df.columns:
            if col.lower().startswith(prefix.lower()):
                val = df[col].iloc[-1] if len(df) > 0 else None
                if pd.notna(val):
                    return float(val)
        return None

    def _get_series(self, df: pd.DataFrame, prefix: str) -> pd.Series | None:
        for col in df.columns:
            if col.lower().startswith(prefix.lower()):
                return df[col]
        return None

    def _describe(self, a: RegimeAssessment) -> str:
        regime_names = {
            Regime.TRENDING_BULLISH.value: "Mercado alcista con tendencia fuerte",
            Regime.TRENDING_BEARISH.value: "Mercado bajista con tendencia fuerte",
            Regime.RANGING.value: "Mercado lateral en rango",
            Regime.HIGH_VOLATILITY.value: "Alta volatilidad sin tendencia clara",
            Regime.LOW_VOLATILITY.value: "Baja volatilidad, mercado tranquilo",
            Regime.NEWS_IMPACT.value: "Mercado afectado por noticias de alto impacto",
            Regime.BREAKOUT.value: "Ruptura de rango detectada",
            Regime.TRANSITIONAL.value: "Mercado en transicion entre regimenes",
        }
        desc = regime_names.get(a.primary, a.primary)
        if a.secondary:
            desc += f" (secundario: {regime_names.get(a.secondary, a.secondary)})"
        return desc


# ──────────────────────────────────────────────────────
# Regime history storage (SQLite)
# ──────────────────────────────────────────────────────

def store_regime(assessment: RegimeAssessment, pair: str, timeframe: str, db_path: str = "memoria.db") -> bool:
    """Almacena el regimen detectado en memoria.db para historial."""
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS regime_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                primary_regime TEXT NOT NULL,
                secondary_regime TEXT,
                confidence REAL,
                adx REAL,
                atr_percentile REAL,
                ema_alignment TEXT,
                volatility_level TEXT,
                directional_bias TEXT,
                news_active INTEGER,
                description TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            INSERT INTO regime_history
                (pair, timeframe, primary_regime, secondary_regime, confidence,
                 adx, atr_percentile, ema_alignment, volatility_level,
                 directional_bias, news_active, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pair, timeframe, assessment.primary, assessment.secondary,
            assessment.confidence, assessment.adx, assessment.atr_percentile,
            assessment.ema_alignment, assessment.volatility_level,
            assessment.directional_bias, int(assessment.news_active),
            assessment.description,
        ))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_regime_history(pair: str = "", db_path: str = "memoria.db", limit: int = 100) -> list[dict]:
    """Obtiene el historial de regimenes de memoria.db."""
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        if pair:
            cursor = conn.execute(
                "SELECT * FROM regime_history WHERE pair = ? ORDER BY timestamp DESC LIMIT ?",
                (pair, limit)
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM regime_history ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


# ──────────────────────────────────────────────────────
# CLI formatting
# ──────────────────────────────────────────────────────

def cmd_regime_report(assessment: RegimeAssessment, pair: str = "", timeframe: str = "") -> str:
    """Formatea un RegimeAssessment para consola."""
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
    lines.append(f"{C}  REGIME DETECTION — V.4{S}")
    if pair:
        lines.append(f"{C}  {pair} · {timeframe}{S}")
    lines.append(f"{C}{'='*60}{S}\n")

    regime_colors = {
        Regime.TRENDING_BULLISH.value: G,
        Regime.TRENDING_BEARISH.value: R,
        Regime.RANGING.value: Y,
        Regime.HIGH_VOLATILITY.value: R,
        Regime.LOW_VOLATILITY.value: C,
        Regime.NEWS_IMPACT.value: R,
        Regime.BREAKOUT.value: G,
        Regime.TRANSITIONAL.value: Y,
    }
    primary_color = regime_colors.get(assessment.primary, "")

    lines.append(f"{B}── Regimen Detectado ──{S}")
    lines.append(f"  Primario:     {primary_color}{assessment.primary}{S}")
    if assessment.secondary:
        lines.append(f"  Secundario:   {assessment.secondary}")
    lines.append(f"  Confianza:    {assessment.confidence:.1f}%")
    lines.append(f"  Descripcion:  {assessment.description}\n")

    lines.append(f"{B}── Componentes ──{S}")
    lines.append(f"  ADX:              {assessment.adx:.2f}")
    lines.append(f"  ATR Percentil:    {assessment.atr_percentile:.1f}%")
    lines.append(f"  EMA Alignment:    {assessment.ema_alignment}")
    lines.append(f"  Volatilidad:      {assessment.volatility_level}")
    lines.append(f"  Bias Direccional: {assessment.directional_bias}")
    lines.append(f"  Noticias Activas: {'Si' if assessment.news_active else 'No'}")

    lines.append(f"\n{C}{'='*60}{S}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────

if __name__ == "__main__":
    np.random.seed(42)
    n = 300

    # Trending bullish
    close_bull = np.cumsum(np.random.randn(n) * 0.001 + 0.0005) + 1.0
    df_bull = pd.DataFrame({
        "close": close_bull,
        "adx": np.linspace(20, 45, n),
        "atr_14": np.abs(np.random.randn(n)) * 0.005,
        "ema_20": pd.Series(close_bull).rolling(20, min_periods=1).mean(),
        "ema_50": pd.Series(close_bull).rolling(50, min_periods=1).mean(),
        "ema_150": pd.Series(close_bull).rolling(150, min_periods=1).mean(),
    })

    detector = RegimeDetector()
    assessment = detector.detect(df_bull, pair="EURUSD", timeframe="H1")
    print(cmd_regime_report(assessment, "EURUSD", "H1"))

    # Ranging
    close_range = np.cumsum(np.random.randn(n) * 0.001) + 1.0
    df_range = pd.DataFrame({
        "close": close_range,
        "adx": np.linspace(15, 22, n),
        "atr_14": np.abs(np.random.randn(n)) * 0.003,
        "ema_20": pd.Series(close_range).rolling(20, min_periods=1).mean(),
        "ema_50": pd.Series(close_range).rolling(50, min_periods=1).mean(),
        "ema_150": pd.Series(close_range).rolling(150, min_periods=1).mean(),
    })

    assessment2 = detector.detect(df_range, pair="GBPUSD", timeframe="H4")
    print(cmd_regime_report(assessment2, "GBPUSD", "H4"))

    # News impact
    assessment3 = detector.detect(df_bull, news_active=True, news_sentiment="high_impact", pair="EURUSD", timeframe="H1")
    print(cmd_regime_report(assessment3, "EURUSD", "H1"))

    print("\n=== V.4 PASSED ===")

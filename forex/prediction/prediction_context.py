"""
prediction_context.py — Construcción del contexto completo para el Decision Engine.

Roadmap V se implementó como una colección de módulos independientes (V.1 a V.9)
pero el pipeline de producción sólo invocaba el Quality Gate (V.5) y un Decision
Engine (V.1) degradado: recibía únicamente `ensemble_signal` y `model_confidence`,
dejando los otros 14 parámetros en sus valores neutros por defecto. Resultado: las
prioridades 1..5 de la jerarquía de decisión nunca se disparaban.

Este módulo centraliza la recolección de ese contexto (V.3 MTF, V.4 Regime,
V.8 Reliability, V.2 Risk) para que `integrated_pipeline.predict()` pueda pasarlo
completo al Decision Engine.

Todo fallo se registra con `logger.warning` — nunca se silencia.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("forex.prediction.context")


# ──────────────────────────────────────────────────────────────
# Contenedor
# ──────────────────────────────────────────────────────────────
@dataclass
class PredictionContext:
    """Contexto agregado que alimenta el Decision Engine (V.1)."""

    pair: str = ""
    timeframe: str = "H1"

    regime: Any = None                    # RegimeAssessment | None
    mtf: Any = None                       # MTFCoherenceResult | None
    reliability: Any = None               # ReliabilityReport | None
    risk: Any = None                      # RiskAssessment | None

    circuit_breaker_active: bool = False
    news_active: bool = False
    news_sentiment: str = ""
    volatility_level: str = "normal"
    atr_percentile: float = 50.0
    atr_value: float = 0.0

    model_win_rate: Optional[float] = None
    model_recent_predictions: int = 0

    degraded: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        out: dict[str, Any] = {
            "pair": self.pair,
            "timeframe": self.timeframe,
            "circuit_breaker_active": self.circuit_breaker_active,
            "news_active": self.news_active,
            "news_sentiment": self.news_sentiment,
            "volatility_level": self.volatility_level,
            "atr_percentile": round(self.atr_percentile, 2),
            "atr_value": self.atr_value,
            "model_win_rate": self.model_win_rate,
            "model_recent_predictions": self.model_recent_predictions,
            "degraded_components": self.degraded,
        }
        for key, obj in (
            ("regime", self.regime),
            ("mtf", self.mtf),
            ("reliability", self.reliability),
            ("risk", self.risk),
        ):
            if obj is not None and hasattr(obj, "to_dict"):
                try:
                    out[key] = obj.to_dict()
                except Exception as exc:  # pragma: no cover - defensivo
                    logger.warning("No se pudo serializar %s: %s", key, exc)
        return out


# ──────────────────────────────────────────────────────────────
# Helpers de bajo nivel
# ──────────────────────────────────────────────────────────────
def _atr_stats(df: pd.DataFrame) -> tuple[float, float, str]:
    """Devuelve (atr_actual, atr_percentil, nivel_volatilidad)."""
    col = next((c for c in ("ATR_14", "atr_14", "ATR", "atr") if c in df.columns), None)
    if col is None:
        high, low, close = df.get("high"), df.get("low"), df.get("close")
        if high is None or low is None or close is None:
            return 0.0, 50.0, "normal"
        prev = close.shift(1)
        tr = pd.concat(
            [(high - low).abs(), (high - prev).abs(), (low - prev).abs()], axis=1
        ).max(axis=1)
        series = tr.rolling(14).mean()
    else:
        series = df[col]

    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return 0.0, 50.0, "normal"

    current = float(series.iloc[-1])
    window = series.tail(250)
    pct = float((window <= current).mean() * 100.0) if len(window) > 1 else 50.0

    if pct >= 90:
        level = "extreme"
    elif pct >= 70:
        level = "high"
    elif pct <= 20:
        level = "low"
    else:
        level = "normal"
    return current, pct, level


def _circuit_breaker_state() -> tuple[bool, dict]:
    try:
        from forex.prediction.circuit_breaker import CircuitBreaker

        state = CircuitBreaker().check() or {}
        return bool(state.get("open")), state
    except Exception as exc:
        logger.warning("Circuit Breaker no disponible (%s) — se asume cerrado.", exc)
        return False, {}


def _model_performance(pair: str, timeframe: str) -> tuple[Optional[float], int]:
    """Win rate histórico real del modelo. (None, 0) si no hay historial."""
    try:
        from forex.prediction.outcome_tracker import OutcomeTracker

        stats = OutcomeTracker().get_stats(pair=pair)
        total = int(getattr(stats, "evaluated", 0) or 0)
        if total > 0:
            wr = getattr(stats, "win_rate", None)
            if wr is not None:
                wr = float(wr)
                if wr > 1.0:
                    wr /= 100.0
                return wr, total
    except Exception as exc:
        logger.warning("OutcomeTracker no disponible (%s).", exc)

    try:
        from forex.prediction.model_quality_history import get_quality_history

        wr = get_quality_history().get_win_rate(pair=pair, horizon=timeframe)
        if wr:
            wr = float(wr)
            if wr > 1.0:
                wr /= 100.0
            return wr, 0
    except Exception as exc:
        logger.warning("ModelQualityHistory no disponible (%s).", exc)

    return None, 0


def _news_state(pair: str) -> tuple[bool, str]:
    """Estado de noticias de alto impacto. Degrada a (False, '') con aviso."""
    try:
        from forex.news_filter import is_news_active  # type: ignore

        active, sentiment = is_news_active(pair)
        return bool(active), str(sentiment or "")
    except Exception:
        return False, ""


def _load_tf(path: Optional[str], pair: str) -> Optional[pd.DataFrame]:
    if not path:
        return None
    try:
        from forex.prediction.csv_adapter import adapt_csv

        return adapt_csv(path, pair=pair)
    except Exception as exc:
        logger.warning("No se pudo cargar el timeframe %s: %s", path, exc)
        return None


# ──────────────────────────────────────────────────────────────
# API principal
# ──────────────────────────────────────────────────────────────
def build_context(
    df: pd.DataFrame,
    *,
    pair: str = "",
    timeframe: str = "H1",
    signal: str = "HOLD",
    model_confidence: float = 0.0,
    ensemble_predictions: Optional[list[str]] = None,
    h4_df: Optional[pd.DataFrame] = None,
    d1_df: Optional[pd.DataFrame] = None,
    path_h4: Optional[str] = None,
    path_d1: Optional[str] = None,
    entry_price: Optional[float] = None,
    rr_ratio: Optional[float] = None,
) -> PredictionContext:
    """
    Ejecuta V.4 (regime), V.3 (MTF), V.8 (reliability) y V.2 (risk) sobre el
    dataframe ya enriquecido con features y devuelve el contexto completo.

    Ningún fallo interrumpe la predicción: cada componente que no pueda
    ejecutarse queda registrado en `ctx.degraded` y se avisa por logger.
    """
    ctx = PredictionContext(pair=pair, timeframe=timeframe)

    ctx.atr_value, ctx.atr_percentile, ctx.volatility_level = _atr_stats(df)
    ctx.circuit_breaker_active, _cb = _circuit_breaker_state()
    ctx.news_active, ctx.news_sentiment = _news_state(pair)
    ctx.model_win_rate, ctx.model_recent_predictions = _model_performance(pair, timeframe)

    # ── V.4 Regime Detection ──────────────────────────────────
    try:
        from forex.prediction.roadmap_v_integration import run_regime_detection

        ctx.regime = run_regime_detection(
            df,
            news_active=ctx.news_active,
            news_sentiment=ctx.news_sentiment,
            pair=pair,
            timeframe=timeframe,
            verbose=False,
        )
        if getattr(ctx.regime, "volatility_level", ""):
            ctx.volatility_level = ctx.regime.volatility_level
        if getattr(ctx.regime, "atr_percentile", 0.0):
            ctx.atr_percentile = float(ctx.regime.atr_percentile)
    except Exception as exc:
        ctx.degraded.append("regime")
        logger.warning("V.4 Regime Detection no ejecutado: %s", exc)

    # ── V.3 MTF Coherence ─────────────────────────────────────
    try:
        from forex.prediction.roadmap_v_integration import run_mtf_coherence

        h4 = h4_df if h4_df is not None else _load_tf(path_h4, pair)
        d1 = d1_df if d1_df is not None else _load_tf(path_d1, pair)
        if h4 is not None or d1 is not None:
            ctx.mtf = run_mtf_coherence(
                d1_df=d1, h4_df=h4, h1_df=df, pair=pair, verbose=False
            )
        else:
            ctx.degraded.append("mtf(sin H4/D1)")
            logger.warning(
                "V.3 MTF omitido para %s: no hay CSV de H4 ni D1 disponible.", pair or "?"
            )
    except Exception as exc:
        ctx.degraded.append("mtf")
        logger.warning("V.3 MTF Coherence no ejecutado: %s", exc)

    # ── V.8 Reliability Score ─────────────────────────────────
    try:
        from forex.prediction.roadmap_v_integration import run_reliability_score

        ctx.reliability = run_reliability_score(
            model_confidence=model_confidence,
            ensemble_predictions=ensemble_predictions,
            mtf_coherence_score=(
                float(getattr(ctx.mtf, "coherence_score", 0.0)) if ctx.mtf else None
            ),
            regime_primary=str(getattr(ctx.regime, "primary", "") or ""),
            regime_confidence=float(getattr(ctx.regime, "confidence", 0.0) or 0.0),
            news_active=ctx.news_active,
            news_sentiment=ctx.news_sentiment,
            volatility_level=ctx.volatility_level,
            model_win_rate=ctx.model_win_rate,
            model_recent_predictions=ctx.model_recent_predictions,
            signal=signal,
            verbose=False,
        )
    except Exception as exc:
        ctx.degraded.append("reliability")
        logger.warning("V.8 Reliability Score no ejecutado: %s", exc)

    # ── V.2 Risk Engine (sólo para señales operables) ─────────
    if signal in ("BUY", "SELL"):
        try:
            from forex.prediction.roadmap_v_integration import run_risk_engine

            price = entry_price
            if price is None and "close" in df.columns:
                price = float(pd.to_numeric(df["close"], errors="coerce").dropna().iloc[-1])

            ctx.risk = run_risk_engine(
                decision=signal,
                entry_price=float(price or 0.0),
                atr=ctx.atr_value,
                reliability_score=float(
                    getattr(ctx.reliability, "reliability_score", model_confidence * 100.0)
                ),
                model_win_rate=float(ctx.model_win_rate or 0.5),
                regime=str(getattr(ctx.regime, "primary", "") or ""),
                pair=pair,
                timeframe=timeframe,
                rr_ratio=rr_ratio,
                verbose=False,
            )
        except Exception as exc:
            ctx.degraded.append("risk")
            logger.warning("V.2 Risk Engine no ejecutado: %s", exc)

    if ctx.degraded:
        logger.warning(
            "Predicción %s con contexto degradado: %s",
            pair or "?",
            ", ".join(ctx.degraded),
        )
    return ctx


__all__ = ["PredictionContext", "build_context"]

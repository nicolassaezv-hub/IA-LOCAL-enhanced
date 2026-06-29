"""
predictor.py — Generador de señales con confidence gate + regime filter (ADX)

Retorna BUY / SELL / HOLD con metadata completa.

Filtros antes de disparar señal:
  1. Confianza mínima (default 0.62) — debajo de esto → HOLD
  2. ADX mínimo (default 22) — mercado ranging → señales poco confiables → HOLD
"""

import numpy as np
import pandas as pd
from .model_storage import ModelStorage


MIN_CONFIDENCE = 0.62
MIN_ADX        = 22.0


class ForexPredictor:

    def __init__(self, min_confidence: float = MIN_CONFIDENCE,
                 min_adx: float = MIN_ADX):
        self.storage        = ModelStorage()
        self.model          = None
        self.min_confidence = min_confidence
        self.min_adx        = min_adx

    # ─────────────────────────────────────────────────────────
    # Carga el modelo (lazy, solo una vez)
    # ─────────────────────────────────────────────────────────
    def load_model(self):
        if self.model is None:
            self.model = self.storage.load_latest()
        return self.model

    # ─────────────────────────────────────────────────────────
    # Predicción cruda (sin filtros)
    # ─────────────────────────────────────────────────────────
    def predict(self, X: pd.DataFrame) -> dict:
        model = self.load_model()
        prob  = model.predict_proba(X)[0]
        pred  = int(np.argmax(prob))
        conf  = float(np.max(prob))
        return {
            "prediction": pred,
            "direction":  "bullish" if pred == 1 else "bearish",
            "confidence": conf,
        }

    def predict_latest(self, df: pd.DataFrame) -> dict:
        return self.predict(df.tail(1))

    def predict_batch(self, X: pd.DataFrame) -> list:
        model = self.load_model()
        probs = model.predict_proba(X)
        preds = np.argmax(probs, axis=1)
        return [
            {
                "prediction": int(preds[i]),
                "direction":  "bullish" if preds[i] == 1 else "bearish",
                "confidence": float(np.max(probs[i])),
            }
            for i in range(len(X))
        ]

    # ─────────────────────────────────────────────────────────
    # SEÑAL CON FILTROS — salida principal para ASTRA
    # ─────────────────────────────────────────────────────────
    def signal(self, df: pd.DataFrame, pair: str = None) -> dict:
        raw        = self.predict_latest(df)
        confidence = raw["confidence"]
        direction  = raw["direction"]
        latest     = df.iloc[-1]

        # Calcular ADX si no está en el DataFrame
        if "ADX_14" not in df.columns:
            from forex.indicators import compute_adx
            df = df.copy()
            df["ADX_14"] = compute_adx(df)

        adx         = float(df["ADX_14"].iloc[-1]) if "ADX_14" in df.columns else 25.0
        if np.isnan(adx):
            adx = 25.0
        is_trending = adx >= self.min_adx

        # Aplicar filtros
        reasons = []
        if confidence < self.min_confidence:
            reasons.append(
                f"confianza {confidence:.2f} < umbral {self.min_confidence:.2f}"
            )
        if not is_trending:
            reasons.append(
                f"ADX {adx:.1f} < {self.min_adx} (mercado ranging/choppy)"
            )

        if reasons:
            action = "HOLD"
        else:
            action = "BUY" if direction == "bullish" else "SELL"

        # Signal strength: combina confianza (65%) + ADX (35%)
        adx_score      = min(adx / 50.0, 1.0)
        signal_strength = round((confidence * 0.65 + adx_score * 0.35) * 100, 1)

        # Régimen de mercado
        if adx >= 40:
            regime = "strong trend"
        elif adx >= 25:
            regime = "moderate trend"
        elif adx >= self.min_adx:
            regime = "weak trend"
        else:
            regime = "ranging"

        return {
            "pair":           pair,
            "action":         action,
            "direction":      direction,
            "confidence":     round(confidence, 4),
            "signal_strength": signal_strength,
            "regime":         regime,
            "adx":            round(adx, 2),
            "hold_reason":    "; ".join(reasons) if reasons else None,
            "interpretation": _interpret(action, confidence, signal_strength),
        }

    # Alias para compatibilidad
    def predict_summary(self, X: pd.DataFrame, pair: str = None) -> dict:
        return self.signal(X, pair=pair)


def _interpret(action: str, confidence: float, strength: float) -> str:
    if action == "HOLD":
        return "Condiciones no cumplidas — espera un setup más claro."
    if strength >= 75:
        return f"Señal {action} de alta calidad — setup favorable detectado."
    if strength >= 55:
        return f"Señal {action} moderada — operar con tamaño estándar."
    return f"Señal {action} marginal — reducir tamaño o esperar confirmación."

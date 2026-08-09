"""
predictor.py — Generador de señales con confidence gate + regime filter (ADX)

FIX #1: predict usa predict_features() (NO el X con horizonte dropeado)
FIX #2: load_model(pair=...) carga el modelo correcto por par
FIX #5: MIN_CONFIDENCE elevado a 0.65
FIX #10: signal_strength calibrado — usa directamente la confidence como proxy principal

Retorna BUY / SELL / HOLD con metadata completa.

Filtros antes de disparar señal:
  1. Confianza mínima (0.65) — debajo de esto → HOLD
  2. ADX mínimo (22) — mercado ranging → señales poco confiables → HOLD
  3. Modelo válido — si el modelo no pasó el umbral de calibración → HOLD con aviso
"""

import numpy as np
import pandas as pd
from .model_storage import ModelStorage

MIN_CONFIDENCE = 0.65   # FIX #5: antes 0.62
MIN_ADX        = 22.0


class ForexPredictor:

    def __init__(self, min_confidence: float = MIN_CONFIDENCE,
                 min_adx: float = MIN_ADX):
        self.storage        = ModelStorage()
        self._models        = {}          # caché por par
        self.min_confidence = min_confidence
        self.min_adx        = min_adx

    # ─────────────────────────────────────────────────────────
    # Carga el modelo correcto por par (con caché)
    # ─────────────────────────────────────────────────────────
    def load_model(self, pair: str = None):
        key = (pair or "").upper().replace("/", "").replace("_", "")
        if key not in self._models:
            self._models[key] = self.storage.load_model(pair=pair)
        return self._models[key]

    def invalidate_cache(self, pair: str = None):
        """Forzar recarga del modelo (después de un nuevo entrenamiento)."""
        key = (pair or "").upper().replace("/", "").replace("_", "")
        self._models.pop(key, None)

    # ─────────────────────────────────────────────────────────
    # Predicción cruda (sin filtros)
    # ─────────────────────────────────────────────────────────
    def predict(self, X: pd.DataFrame, pair: str = None) -> dict:
        model = self.load_model(pair=pair)
        prob  = model.predict_proba(X)[0]
        pred  = int(np.argmax(prob))
        conf  = float(np.max(prob))
        return {
            "prediction": pred,
            "direction":  "bullish" if pred == 1 else "bearish",
            "confidence": conf,
        }

    def predict_batch(self, X: pd.DataFrame, pair: str = None) -> list:
        model = self.load_model(pair=pair)
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
    # SEÑAL PRINCIPAL — BUY / SELL / HOLD
    # FIX #1: recibe X ya preparado con predict_features()
    # FIX #2: carga modelo por par
    # FIX #10: signal_strength simplificado y calibrado
    # ─────────────────────────────────────────────────────────
    def signal(self, X: pd.DataFrame, pair: str = None) -> dict:
        raw        = self.predict(X.tail(1), pair=pair)
        confidence = raw["confidence"]
        direction  = raw["direction"]

        # ADX de la última fila
        if "ADX_14" in X.columns:
            adx = float(X["ADX_14"].iloc[-1])
            if np.isnan(adx):
                adx = 25.0
        else:
            adx = 25.0

        is_trending = adx >= self.min_adx

        # Verificar si el modelo pasó la calibración (sufficient flag)
        model = self.load_model(pair=pair)
        model_sufficient = getattr(model, "sufficient", True)

        # Aplicar filtros
        reasons = []
        if confidence < self.min_confidence:
            reasons.append(f"confidence {confidence:.2f} < umbral {self.min_confidence:.2f}")
        if not is_trending:
            reasons.append(f"ADX {adx:.1f} < {self.min_adx} (mercado ranging)")
        if not model_sufficient:
            reasons.append("modelo con precision < 65% — requiere re-tune con más datos")

        action = "HOLD" if reasons else ("BUY" if direction == "bullish" else "SELL")

        # FIX #10: signal_strength = confidence calibrada * ADX factor
        # La confidence ya está calibrada isotónicamente — refleja tasa de acierto real
        adx_factor    = min(adx / 40.0, 1.0)   # normalizado a [0,1] con max 40
        signal_strength = round(
            (confidence * 0.75 + adx_factor * 0.25) * 100, 1
        )

        # Probabilidad estimada de que la señal sea correcta
        # Con calibración isotónica: confidence ≈ P(TP | señal)
        est_prob_correct = round(confidence * 100, 1)

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
            "pair":             pair,
            "action":           action,
            "direction":        direction,
            "confidence":       round(confidence, 4),
            "est_prob_correct": est_prob_correct,   # % prob real de acierto (calibrado)
            "signal_strength":  signal_strength,
            "regime":           regime,
            "adx":              round(adx, 2),
            "model_valid":      model_sufficient,
            "hold_reason":      "; ".join(reasons) if reasons else None,
            "interpretation":   _interpret(action, confidence, signal_strength, est_prob_correct),
        }

    # Alias para compatibilidad
    def predict_summary(self, X: pd.DataFrame, pair: str = None) -> dict:
        return self.signal(X, pair=pair)

    # Legacy — para código que pasa df completo (no X procesado)
    def predict_latest(self, df: pd.DataFrame) -> dict:
        return self.predict(df.tail(1))


def _interpret(action: str, confidence: float, strength: float, prob: float) -> str:
    if action == "HOLD":
        return "Condiciones no cumplidas — espera un setup más claro."
    if prob >= 75:
        return f"Señal {action} de ALTA CALIDAD — probabilidad estimada de acierto: {prob:.1f}%."
    if prob >= 65:
        return f"Señal {action} válida — probabilidad estimada de acierto: {prob:.1f}%."
    return f"Señal {action} marginal ({prob:.1f}%) — reducir tamaño o esperar confirmación adicional."

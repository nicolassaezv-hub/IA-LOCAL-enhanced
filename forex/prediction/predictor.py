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
from .dataset_builder import DatasetBuilder
from .h1_directional import (
    H1_CONFIDENCE_SEMANTICS,
    H1_DECISION_POLICY,
    H1_FEATURE_PROFILE,
    H1_MODEL_CONTRACT,
    H1_SCORE_TYPE,
    h1_direction_decision,
    h1_runtime_contract_error,
)
from .model_storage import ModelStorage

_NON_NUMERIC = {'timestamp', 'session', 'pair', 'regime', 'action', 'date', 'time'}

def _prepare_X(X: pd.DataFrame, model) -> pd.DataFrame:
    """
    Prepara X para predict_proba:
    1. Elimina columnas no-numéricas (timestamp, session, pair, datetime, object)
    2. Extrae feature_names del modelo (XGBoost / LGBM / RF) como str Python puro
    3. Alinea columnas: rellena con 0 las features MTF faltantes (H4/D1)
    4. Asegura que todos los nombres de columna son str Python (no numpy.str_)
    5. Convierte a float64 para compatibilidad XGBoost/sklearn
    """
    X = X.copy()
    
    # 1. Quitar columnas no-numéricas
    drop_cols = [c for c in X.columns 
                 if c.lower() in _NON_NUMERIC 
                 or X[c].dtype == object 
                 or str(X[c].dtype).startswith('datetime')]
    if drop_cols:
        X = X.drop(columns=drop_cols)
    
    # Normalizar nombres de columna a str Python puro (evita numpy.str_ issues)
    X.columns = [str(c) for c in X.columns]
    
    # 2. Extraer feature_names del modelo como str Python puro
    feat_names = getattr(model, 'feature_names', None)
    if feat_names is None:
        base = getattr(model, 'base', None) or model
        models_list = getattr(base, 'models', [])
        for _, m in models_list:
            if hasattr(m, 'feature_names_in_'):
                feat_names = [str(f) for f in m.feature_names_in_]
                break
    
    if feat_names:
        # Normalizar a str Python puro (desde numpy.str_ u otros)
        feat_names = [str(f) for f in feat_names]
        # Columnas faltantes → rellenar con 0.0 (ej. features MTF sin H4/D1)
        for col in feat_names:
            if col not in X.columns:
                X[col] = 0.0
        # Seleccionar y reordenar exactamente las features del modelo
        X = X[feat_names]
    
    # 3. Asegurar nombres de columna como str y valores float64
    X.columns = [str(c) for c in X.columns]
    X = X.astype(float)
    return X

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

    def prepare_features(
        self, df: pd.DataFrame, *, pair: str = None, n_rows: int = 1
    ) -> pd.DataFrame:
        """Build the model-selected inference profile without H1 zero filling."""
        model = self.load_model(pair=pair)
        if getattr(model, "model_contract", None) == H1_MODEL_CONTRACT:
            features = DatasetBuilder(df).predict_features(
                n_rows=n_rows,
                feature_profile=H1_FEATURE_PROFILE,
            )
            reason = h1_runtime_contract_error(model, features.columns)
            if reason:
                raise ValueError(reason)
            return features
        _, train_columns = self.storage.load_model_with_features(pair=pair)
        return DatasetBuilder(df).predict_features(
            n_rows=n_rows,
            train_columns=train_columns,
        )

    # ─────────────────────────────────────────────────────────
    # Predicción cruda (sin filtros)
    # ─────────────────────────────────────────────────────────
    def predict(self, X: pd.DataFrame, pair: str = None) -> dict:
        model = self.load_model(pair=pair)
        X     = _prepare_X(X, model)
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
        X     = _prepare_X(X, model)
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
        model = self.load_model(pair=pair)
        if getattr(model, "model_contract", None) == H1_MODEL_CONTRACT:
            return self._signal_h1(X.tail(1), pair=pair, model=model)

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

    @staticmethod
    def _signal_h1(X: pd.DataFrame, *, pair: str, model) -> dict:
        """Return a score-percentile decision with no probability claim or legacy veto."""
        reason = h1_runtime_contract_error(model, X.columns)
        base = {
            "pair": pair,
            "model_contract": H1_MODEL_CONTRACT,
            "target_profile": getattr(model, "target_profile", None),
            "target_definition_version": getattr(
                model, "target_definition_version", None
            ),
            "horizon": getattr(model, "horizon", None),
            "feature_profile": getattr(model, "feature_profile", None),
            "score_type": H1_SCORE_TYPE,
            "decision_policy": H1_DECISION_POLICY,
            "confidence_semantics": H1_CONFIDENCE_SEMANTICS,
        }
        if reason:
            return {
                **base,
                "action": "HOLD",
                "direction": "unknown",
                "direction_score": None,
                "decision_percentile": None,
                "decision_extremeness": 0.0,
                "confidence": 0.0,
                "model_valid": False,
                "hold_reason": reason,
                "interpretation": "H1 model/feature contract mismatch; prediction blocked.",
            }
        prepared = X.loc[:, list(model.feature_names)].astype(float)
        direction_score = float(model.predict_proba(prepared)[0, 1])
        decision = h1_direction_decision(direction_score, model)
        action = decision["action"]
        if action == "BUY":
            interpretation = (
                "Directional model score is in the bullish upper quartile "
                "of its temporal OOF reference."
            )
            hold_reason = None
        elif action == "SELL":
            interpretation = (
                "Directional model score is in the bearish lower quartile "
                "of its temporal OOF reference."
            )
            hold_reason = None
        else:
            interpretation = "Score lies inside the temporal OOF abstention band."
            hold_reason = "OOF_QUARTILE_ABSTENTION"
        return {
            **base,
            "action": action,
            "direction": "bullish" if direction_score >= 0.5 else "bearish",
            "direction_score": direction_score,
            "decision_percentile": decision["decision_percentile"],
            "decision_extremeness": decision["decision_extremeness"],
            "confidence": decision["decision_extremeness"],
            "model_valid": True,
            "hold_reason": hold_reason,
            "interpretation": interpretation,
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

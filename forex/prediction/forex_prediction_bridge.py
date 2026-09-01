"""
forex_prediction_bridge.py — Bridge para ASTRA

FIX #1: usa predict_features() para señal sobre última vela real
FIX #2: pasa pair al predictor para modelo correcto
"""

import pandas as pd

from .feature_engineering import build_features
from .dataset_builder     import DatasetBuilder
from .h1_directional      import H1_MODEL_CONTRACT
from .predictor           import ForexPredictor
from .csv_adapter         import adapt_csv


class ForexPredictionBridge:

    def __init__(self, min_confidence: float = 0.65, min_adx: float = 22.0):
        self.predictor = ForexPredictor(
            min_confidence=min_confidence,
            min_adx=min_adx,
        )

    def load_data(self, filepath: str, pair: str = None) -> pd.DataFrame:
        return adapt_csv(filepath, pair=pair)

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepara features para predicción (sin drop de horizonte)."""
        df      = build_features(df)
        builder = DatasetBuilder(df)
        return builder.predict_features(n_rows=1)

    def prepare_data(self, df: pd.DataFrame, use_feature_engineering: bool = True):
        """Compatibilidad legacy — retorna (X_pred, None)."""
        if use_feature_engineering:
            df = build_features(df)
        X = DatasetBuilder(df).predict_features(n_rows=1)
        return X, None

    # ─────────────────────────────────────────────────────────
    # PREDICT — señal sobre la última vela real (FIX #1 + #2)
    # ─────────────────────────────────────────────────────────
    def predict_from_csv(self, filepath: str, pair: str = None) -> dict:
        df   = self.load_data(filepath, pair=pair)
        pair = pair or (str(df["pair"].iloc[-1]) if "pair" in df.columns else None)
        model = self.predictor.load_model(pair=pair)
        if getattr(model, "model_contract", None) == H1_MODEL_CONTRACT:
            X = self.predictor.prepare_features(build_features(df), pair=pair)
        else:
            X = self.prepare_features(df)
        return self.predictor.signal(X, pair=pair)

    def analyze(self, filepath: str, pair: str = None) -> dict:
        df   = self.load_data(filepath, pair=pair)
        pair = pair or (str(df["pair"].iloc[-1]) if "pair" in df.columns else None)
        model = self.predictor.load_model(pair=pair)
        if getattr(model, "model_contract", None) == H1_MODEL_CONTRACT:
            X = self.predictor.prepare_features(build_features(df), pair=pair)
        else:
            X = self.prepare_features(df)
        signal = self.predictor.signal(X, pair=pair)
        return {**signal, "data_points": len(df)}

    def analyze_for_astra(self, filepath: str, pair: str = None) -> dict:
        result = self.analyze(filepath, pair=pair)
        action = result.get("action", "HOLD")
        conf   = result.get("confidence", 0)
        pair_r = result.get("pair", "?")
        if result.get("model_contract") == H1_MODEL_CONTRACT:
            score = result.get("direction_score")
            percentile = result.get("decision_percentile")
            summary = (
                f"{pair_r} → {action} "
                f"(direction_score={score:.4f}, percentile={percentile:.4f}, "
                f"extremeness={conf:.2f})"
            )
        else:
            strng = result.get("signal_strength", 0)
            prob = result.get("est_prob_correct", 0)
            summary = (
                f"{pair_r} → {action} "
                f"(confidence={conf:.2f}, prob_acierto={prob:.1f}%, strength={strng})"
            )
        return {
            "type":    "forex_prediction",
            "payload": result,
            "summary": summary,
        }

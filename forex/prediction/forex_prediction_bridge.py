import pandas as pd

from .feature_engineering import build_features
from .dataset_builder import DatasetBuilder
from .predictor import ForexPredictor


class ForexPredictionBridge:

    def __init__(self, min_confidence: float = 0.62, min_adx: float = 22.0):
        self.predictor = ForexPredictor(
            min_confidence=min_confidence,
            min_adx=min_adx,
        )

    # -----------------------------
    # LOAD DATA
    # -----------------------------
    def load_data(self, filepath: str) -> pd.DataFrame:
        df = pd.read_csv(filepath)
        df.columns = df.columns.str.strip()
        return df

    # -----------------------------
    # BUILD FEATURE PIPELINE
    # -----------------------------
    def prepare_data(self, df: pd.DataFrame, use_feature_engineering: bool = True):
        if use_feature_engineering:
            df = build_features(df)

        builder = DatasetBuilder(df)
        X, y    = builder.build()
        return X, y

    # -----------------------------
    # PREDICT ONLY (NO TRAINING)
    # Returns BUY / SELL / HOLD with full signal details.
    # -----------------------------
    def predict_from_csv(self, filepath: str, pair: str = None) -> dict:
        df   = self.load_data(filepath)
        X, _ = self.prepare_data(df)
        return self.predictor.signal(X, pair=pair)

    # -----------------------------
    # FULL ANALYSIS PIPELINE (ASTRA-READY)
    # -----------------------------
    def analyze(self, filepath: str, pair: str = None) -> dict:
        df   = self.load_data(filepath)
        X, _ = self.prepare_data(df)

        inferred_pair = pair
        if inferred_pair is None and "pair" in df.columns:
            inferred_pair = str(df["pair"].iloc[-1])

        signal = self.predictor.signal(X, pair=inferred_pair)

        return {
            **signal,
            "data_points": len(df),
        }

    # -----------------------------
    # ASTRA INTEGRATION OUTPUT
    # One-liner summary + full payload for ASTRA to render.
    # -----------------------------
    def analyze_for_astra(self, filepath: str) -> dict:
        result = self.analyze(filepath)

        action = result.get("action", "HOLD")
        conf   = result.get("confidence", 0)
        pair   = result.get("pair", "?")
        strng  = result.get("signal_strength", 0)

        summary = (
            f"{pair} → {action} "
            f"(confidence={conf:.2f}, strength={strng})"
        )

        return {
            "type":    "forex_prediction",
            "payload": result,
            "summary": summary,
        }

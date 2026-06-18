import pandas as pd

from .feature_engineering import build_features
from .dataset_builder import DatasetBuilder
from .predictor import ForexPredictor


class ForexPredictionBridge:

    def __init__(self):

        self.predictor = ForexPredictor()

    # -----------------------------
    # LOAD DATA
    # -----------------------------
    def load_data(self, filepath: str):

        df = pd.read_csv(filepath)

        return df

    # -----------------------------
    # BUILD FEATURE PIPELINE
    # -----------------------------
    def prepare_data(self, df: pd.DataFrame, use_feature_engineering=True):

        # Optional enrichment layer
        if use_feature_engineering:

            df = build_features(df)

        # Dataset builder (ML format)
        builder = DatasetBuilder(df)

        X, y = builder.build()

        return X, y

    # -----------------------------
    # PREDICT ONLY (NO TRAINING)
    # -----------------------------
    def predict_from_csv(self, filepath: str):

        df = self.load_data(filepath)

        X, _ = self.prepare_data(df)

        result = self.predictor.predict_latest(X)

        return result

    # -----------------------------
    # FULL ANALYSIS PIPELINE
    # (READY FOR ASTRA)
    # -----------------------------
    def analyze(self, filepath: str, pair: str = None):

        df = self.load_data(filepath)

        X, y = self.prepare_data(df)

        prediction = self.predictor.predict_latest(X)

        return {
            "pair": pair or df["pair"].iloc[-1],
            "signal": prediction["direction"],
            "confidence": prediction["confidence"],
            "raw_prediction": prediction["prediction"],
            "data_points": len(df)
        }

    # -----------------------------
    # ASTRA INTEGRATION OUTPUT
    # -----------------------------
    def analyze_for_astra(self, filepath: str):

        result = self.analyze(filepath)

        return {
            "type": "forex_prediction",
            "payload": result,
            "summary": (
                f"{result['pair']} → "
                f"{result['signal']} "
                f"({result['confidence']:.2f})"
            )
        }

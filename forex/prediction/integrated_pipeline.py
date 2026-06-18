import pandas as pd

from .feature_engineering import build_features
from .dataset_builder import DatasetBuilder
from .predictor import ForexPredictor
from .backtester import ForexBacktester


class ForexIntegratedPipeline:

    def __init__(self):

        self.predictor = ForexPredictor()
        self.backtester = ForexBacktester()

    # -----------------------------
    # FULL PIPELINE (PRODUCTION MODE)
    # -----------------------------
    def run(self, filepath: str, mode="predict"):

        # 1. Load data
        df = pd.read_csv(filepath)

        # 2. Feature engineering (optional but recommended)
        df = build_features(df)

        # 3. Build dataset
        builder = DatasetBuilder(df)

        X, y = builder.build()

        # -------------------------
        # MODE 1: PREDICTION ONLY
        # -------------------------
        if mode == "predict":

            result = self.predictor.predict_latest(X)

            return {
                "type": "prediction",
                "signal": result["direction"],
                "confidence": result["confidence"]
            }

        # -------------------------
        # MODE 2: BACKTEST
        # -------------------------
        elif mode == "backtest":

            result = self.backtester.run(X)

            return {
                "type": "backtest",
                "results": result
            }

        # -------------------------
        # MODE 3: FULL ANALYSIS
        # -------------------------
        elif mode == "full":

            prediction = self.predictor.predict_latest(X)
            backtest = self.backtester.run(X)

            return {
                "type": "full_analysis",
                "prediction": prediction,
                "backtest": backtest
            }

        else:

            raise ValueError(
                f"Unknown mode: {mode}"
            )

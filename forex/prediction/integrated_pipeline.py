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

        # 2. Feature engineering
        df = build_features(df)

        # 3. Build dataset
        builder = DatasetBuilder(df)

        X, y = builder.build()

        # -------------------------
        # MODE 1: PREDICTION ONLY
        # -------------------------
        if mode == "predict":

            prediction = self.predictor.predict_latest(X)

            return {
                "type": "prediction",
                "prediction": prediction,
                "interpretation": (
                    "Strong trend signal"
                    if prediction["confidence"] > 0.70
                    else "Weak/uncertain signal"
                )
            }

        # -------------------------
        # MODE 2: BACKTEST
        # -------------------------
        elif mode == "backtest":

            backtest = self.backtester.run(X)

            return {
                "type": "backtest",
                "results": backtest
            }

        # -------------------------
        # MODE 3: FULL ANALYSIS
        # -------------------------
        elif mode == "full":

            prediction = self.predictor.predict_latest(X)

            backtest = self.backtester.run(X)

            return {
                "type": "full_analysis",
                "rows_processed": len(df),
                "prediction": prediction,

                "backtest": backtest,

                "insight": {

                    "market_quality": (
                        "high"
                        if backtest["win_rate"] > 0.55
                        else "low"
                    ),

                    "risk_level": (
                        "high"
                        if backtest["max_drawdown"] > 0.20
                        else "controlled"
                    ),

                    "model_reliability": (
                        "good"
                        if prediction["confidence"] > 0.65
                        else "weak"
                    )
                }
            }

        else:

            raise ValueError(
                f"Unknown mode: {mode}"
            )

import os
import joblib
import numpy as np
import pandas as pd


class ForexPredictor:

    def __init__(
        self,
        model_path="models/xgb_forex.pkl"
    ):

        self.model_path = model_path
        self.model = None

    # -----------------------------
    # LOAD MODEL
    # -----------------------------
    def load(self):

        if not os.path.exists(self.model_path):

            raise FileNotFoundError(
                f"Model not found at {self.model_path}. Train first."
            )

        self.model = joblib.load(self.model_path)

        return self

    # -----------------------------
    # SINGLE PREDICTION
    # -----------------------------
    def predict_single(self, X: pd.DataFrame):

        if self.model is None:

            self.load()

        pred = self.model.predict(X)[0]

        prob = self.model.predict_proba(X)[0]

        confidence = float(np.max(prob))

        direction = (
            "bullish"
            if pred == 1
            else "bearish"
        )

        return {
            "prediction": int(pred),
            "direction": direction,
            "confidence": confidence
        }

    # -----------------------------
    # LATEST ROW PREDICTION
    # (for real-time use in Astra)
    # -----------------------------
    def predict_latest(self, df: pd.DataFrame):

        if self.model is None:

            self.load()

        latest = df.tail(1)

        return self.predict_single(latest)

    # -----------------------------
    # BATCH PREDICTION
    # -----------------------------
    def predict_batch(self, X: pd.DataFrame):

        if self.model is None:

            self.load()

        preds = self.model.predict(X)
        probs = self.model.predict_proba(X)

        results = []

        for i in range(len(X)):

            results.append({
                "prediction": int(preds[i]),
                "direction": (
                    "bullish"
                    if preds[i] == 1
                    else "bearish"
                ),
                "confidence": float(np.max(probs[i]))
            })

        return results

import numpy as np
import pandas as pd

from .model_storage import ModelStorage


class ForexPredictor:

    def __init__(self):

        self.storage = ModelStorage()
        self.model = None

    # -----------------------------
    # LOAD MODEL (SAFE)
    # -----------------------------
    def load_model(self):

        if self.model is None:

            self.model = self.storage.load_latest()

        return self.model

    # -----------------------------
    # CORE SINGLE PREDICTION
    # -----------------------------
    def predict(self, X: pd.DataFrame):

        model = self.load_model()

        pred = model.predict(X)[0]
        prob = model.predict_proba(X)[0]

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
    # LATEST ROW (REAL TIME USAGE)
    # -----------------------------
    def predict_latest(self, df: pd.DataFrame):

        latest = df.tail(1)

        return self.predict(latest)

    # -----------------------------
    # BATCH PREDICTION
    # -----------------------------
    def predict_batch(self, X: pd.DataFrame):

        model = self.load_model()

        preds = model.predict(X)
        probs = model.predict_proba(X)

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

    # -----------------------------
    # ASTRA-READY SUMMARY OUTPUT
    # -----------------------------
    def predict_summary(self, X: pd.DataFrame, pair=None):

        result = self.predict_latest(X)

        return {
            "pair": pair,
            "signal": result["direction"],
            "confidence": round(result["confidence"], 4),
            "raw_prediction": result["prediction"]
        }

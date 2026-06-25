"""
predictor.py — Signal generator with confidence gate and regime filter

Improvements vs original:
- Confidence gate: only fires BUY/SELL above a threshold (default 0.62)
- Market regime filter: suppresses signals in choppy/ranging markets
  (low ADX = no clear trend = low-quality signals)
- Returns actionable signal: BUY / SELL / HOLD
- Richer output: signal_strength score, regime label, reason for HOLD
"""

import numpy as np
import pandas as pd

from .model_storage import ModelStorage


# Minimum confidence to fire BUY or SELL.
# Below this → HOLD (no trade).
# Raise this to get fewer but higher-quality signals.
MIN_CONFIDENCE = 0.62

# Minimum ADX to consider the market "trending enough".
# Below this = choppy/ranging market → signals are unreliable → HOLD.
MIN_ADX = 22.0


class ForexPredictor:

    def __init__(
        self,
        min_confidence: float = MIN_CONFIDENCE,
        min_adx: float = MIN_ADX,
    ):
        self.storage        = ModelStorage()
        self.model          = None
        self.min_confidence = min_confidence
        self.min_adx        = min_adx

    # -----------------------------
    # LOAD MODEL (SAFE)
    # -----------------------------
    def load_model(self):
        if self.model is None:
            self.model = self.storage.load_latest()
        return self.model

    # -----------------------------
    # CORE SINGLE PREDICTION
    # Returns raw direction + calibrated confidence.
    # -----------------------------
    def predict(self, X: pd.DataFrame) -> dict:
        model = self.load_model()

        pred  = model.predict(X)[0]
        prob  = model.predict_proba(X)[0]

        confidence = float(np.max(prob))
        direction  = "bullish" if pred == 1 else "bearish"

        return {
            "prediction": int(pred),
            "direction":  direction,
            "confidence": confidence,
        }

    # -----------------------------
    # LATEST ROW (REAL-TIME USAGE)
    # -----------------------------
    def predict_latest(self, df: pd.DataFrame) -> dict:
        return self.predict(df.tail(1))

    # -----------------------------
    # BATCH PREDICTION
    # -----------------------------
    def predict_batch(self, X: pd.DataFrame) -> list:
        model = self.load_model()
        preds = model.predict(X)
        probs = model.predict_proba(X)

        return [
            {
                "prediction": int(preds[i]),
                "direction":  "bullish" if preds[i] == 1 else "bearish",
                "confidence": float(np.max(probs[i])),
            }
            for i in range(len(X))
        ]

    # -----------------------------
    # SIGNAL WITH CONFIDENCE GATE + REGIME FILTER
    #
    # This is the main output for ASTRA recommendations.
    #
    # Logic:
    #   1. Get raw model prediction + calibrated confidence
    #   2. Check if market is trending (ADX >= min_adx)
    #   3. If confidence < min_confidence  → HOLD (weak signal)
    #   4. If ADX too low (ranging market) → HOLD (bad conditions)
    #   5. Otherwise → BUY or SELL
    # -----------------------------
    def signal(self, df: pd.DataFrame, pair: str = None) -> dict:
        raw = self.predict_latest(df)

        confidence  = raw["confidence"]
        direction   = raw["direction"]
        latest      = df.iloc[-1]

        # Market regime check via ADX
        adx         = float(latest.get("ADX_14", 999))
        is_trending = adx >= self.min_adx

        # Determine actionable signal
        reasons = []

        if confidence < self.min_confidence:
            reasons.append(f"confidence {confidence:.2f} < threshold {self.min_confidence:.2f}")

        if not is_trending:
            reasons.append(f"ADX {adx:.1f} < {self.min_adx} (ranging/choppy market)")

        if reasons:
            action = "HOLD"
        else:
            action = "BUY" if direction == "bullish" else "SELL"

        # Signal strength (0–100) — composite of confidence + trend clarity
        adx_score       = min(adx / 50.0, 1.0)          # 0–1 as ADX goes 0→50+
        signal_strength = round((confidence * 0.65 + adx_score * 0.35) * 100, 1)

        # Trend label
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
            "action":         action,                   # BUY / SELL / HOLD
            "direction":      direction,                # bullish / bearish
            "confidence":     round(confidence, 4),
            "signal_strength": signal_strength,         # 0–100
            "regime":         regime,
            "adx":            round(adx, 2),
            "hold_reason":    "; ".join(reasons) if reasons else None,
            "interpretation": _interpret(action, confidence, signal_strength),
        }

    # -----------------------------
    # ASTRA-READY SUMMARY (backward compat + upgraded)
    # -----------------------------
    def predict_summary(self, X: pd.DataFrame, pair: str = None) -> dict:
        return self.signal(X, pair=pair)


def _interpret(action: str, confidence: float, strength: float) -> str:
    if action == "HOLD":
        return "Conditions not met — wait for a cleaner setup."
    if strength >= 75:
        return f"High-quality {action} signal — favorable risk/reward setup detected."
    if strength >= 55:
        return f"Moderate {action} signal — trade with standard position size."
    return f"Marginal {action} signal — reduce position size or wait for confirmation."

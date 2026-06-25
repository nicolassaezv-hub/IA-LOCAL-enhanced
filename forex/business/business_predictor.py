"""
forex/business/business_predictor.py

Lightweight business growth signal predictor.

Uses a simple logistic-regression / threshold approach on the
KPI time series to classify the next period as GROWING, DECLINING,
or STABLE.  No heavy ML framework required — scikit-learn is
optional; if unavailable, falls back to a trend-slope heuristic.

Author: Nicolas Saez / Astra Project
"""

from typing import Dict, Optional

import numpy as np
import pandas as pd

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score
    _HAS_SKLEARN = True
except Exception:
    _HAS_SKLEARN = False


class BusinessPredictor:
    """
    Predict whether the next business period will GROW, DECLINE,
    or remain STABLE based on historical revenue/margin data.
    """

    def __init__(self):
        self.model = None
        self.accuracy = 0.0
        self.precision = 0.0
        self._trained = False

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------

    @staticmethod
    def _build_features(df: pd.DataFrame) -> pd.DataFrame:
        """Create lagged features from the normalized business DataFrame."""
        feats = pd.DataFrame(index=df.index)

        if "revenue" in df.columns:
            rev = df["revenue"]
            feats["revenue_lag1"] = rev.shift(1)
            feats["revenue_lag2"] = rev.shift(2)
            feats["revenue_pct_change"] = rev.pct_change()
            feats["revenue_ma3"] = rev.rolling(3).mean()
            feats["revenue_ma6"] = rev.rolling(6).mean()

        if "gross_profit" in df.columns:
            feats["gp_lag1"] = df["gross_profit"].shift(1)
            feats["gp_pct_change"] = df["gross_profit"].pct_change()

        if "net_income" in df.columns:
            feats["ni_lag1"] = df["net_income"].shift(1)
            feats["ni_pct_change"] = df["net_income"].pct_change()

        if "expenses" in df.columns:
            feats["exp_lag1"] = df["expenses"].shift(1)
            feats["exp_pct_change"] = df["expenses"].pct_change()

        return feats.replace([np.inf, -np.inf], np.nan)

    @staticmethod
    def _build_target(df: pd.DataFrame) -> pd.Series:
        """
        Target: 1 if next-period revenue grows >5%, -1 if declines >5%,
        0 otherwise (stable).
        """
        if "revenue" not in df.columns:
            return pd.Series(0, index=df.index)
        rev = df["revenue"]
        future = rev.shift(-1)
        pct = (future - rev) / rev.replace(0, np.nan) * 100
        target = pd.Series(0, index=df.index)
        target[pct > 5] = 1
        target[pct < -5] = -1
        return target

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, df: pd.DataFrame) -> Dict:
        """Train the predictor on a normalized business DataFrame."""
        X = self._build_features(df)
        y = self._build_target(df)

        valid = X.dropna().index.intersection(y.dropna().index)
        X, y = X.loc[valid], y.loc[valid]

        if len(X) < 10 or y.nunique() < 2:
            # Not enough data — use heuristic mode
            self._trained = False
            return {
                "trained": False,
                "reason": "Insufficient data or single-class target",
                "rows": len(X),
            }

        if _HAS_SKLEARN:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.25, random_state=42, stratify=y
            )
            self.model = LogisticRegression(
                max_iter=500, class_weight="balanced"
            )
            self.model.fit(X_train, y_train)
            preds = self.model.predict(X_test)
            self.accuracy = float(accuracy_score(y_test, preds))
            self.precision = float(
                precision_score(y_test, preds, average="weighted", zero_division=0)
            )
            self._trained = True
            return {
                "trained": True,
                "rows": len(X),
                "accuracy": self.accuracy,
                "precision": self.precision,
            }

        self._trained = False
        return {"trained": False, "reason": "scikit-learn not available", "rows": len(X)}

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, df: pd.DataFrame) -> Dict:
        """
        Predict next-period signal.

        Returns dict with:
            action      : 'GROWING' | 'DECLINING' | 'STABLE'
            confidence  : float 0-1
            health_score: int 0-100 (from KPIEngine if available)
            risk_level   : str
        """
        from forex.business.kpi_engine import KPIEngine

        kpis = KPIEngine(df).compute_all()
        health = kpis["health_score"]
        risk = kpis["risk_level"]
        trend = kpis.get("trend_direction", "unknown")

        if self._trained and self.model is not None:
            X = self._build_features(df)
            last = X.dropna().tail(1)
            if len(last) == 0:
                return self._heuristic_predict(kpis, trend, health, risk)
            pred = int(self.model.predict(last)[0])
            proba = self.model.predict_proba(last)[0]
            classes = self.model.classes_
            idx = list(classes).index(pred)
            confidence = float(proba[idx])
            action = {1: "GROWING", -1: "DECLINING", 0: "STABLE"}.get(pred, "STABLE")
            return {
                "action": action,
                "confidence": confidence,
                "health_score": health,
                "risk_level": risk,
            }

        return self._heuristic_predict(kpis, trend, health, risk)

    @staticmethod
    def _heuristic_predict(kpis, trend, health, risk) -> Dict:
        """Fallback when no trained model is available."""
        growth = kpis.get("growth_rate_pct")
        if trend == "growing" or (growth is not None and growth > 5):
            action = "GROWING"
            confidence = 0.6 if health >= 50 else 0.4
        elif trend == "declining" or (growth is not None and growth < -5):
            action = "DECLINING"
            confidence = 0.6 if health < 50 else 0.4
        else:
            action = "STABLE"
            confidence = 0.5
        return {
            "action": action,
            "confidence": confidence,
            "health_score": health,
            "risk_level": risk,
        }

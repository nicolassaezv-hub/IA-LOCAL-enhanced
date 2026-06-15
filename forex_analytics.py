"""
forex_analytics.py

ASTRA Forex Analytics Engine

Features:
- CSV loading
- Dataset profiling
- Session analysis
- RSI analysis
- MACD analysis
- EMA trend analysis
- Volatility analysis
- Correlation analysis
- Market regime detection
- Complete report generation
"""

import pandas as pd
import numpy as np

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


class ForexAnalytics:

    def __init__(self):

        self.df = None
        self.filepath = None

    # ====================================================
    # LOADING
    # ====================================================

    def load_csv(self, filepath):

        self.filepath = filepath

        self.df = pd.read_csv(filepath)

        return {
            "status": "loaded",
            "rows": len(self.df),
            "columns": len(self.df.columns),
            "column_names": list(self.df.columns)
        }

    # ====================================================
    # BASIC DATASET INFO
    # ====================================================

    def dataset_summary(self):

        self._check_loaded()

        return {

            "rows": len(self.df),

            "columns": len(self.df.columns),

            "missing_values":
                self.df.isnull().sum().to_dict(),

            "memory_usage_mb":
                round(
                    self.df.memory_usage(
                        deep=True
                    ).sum() / 1024**2,
                    2
                )
        }

    # ====================================================
    # SESSION ANALYSIS
    # ====================================================

    def session_analysis(self):

        self._check_loaded()

        if "Session" not in self.df.columns:

            return {
                "error":
                    "Session column not found"
            }

        report = {}

        grouped = self.df.groupby("Session")

        for session, data in grouped:

            report[session] = {

                "candles":
                    int(len(data)),

                "avg_volume":
                    float(data["Volume"].mean())
                    if "Volume" in data.columns
                    else None,

                "avg_spread":
                    float(data["Spread"].mean())
                    if "Spread" in data.columns
                    else None,

                "avg_volatility":
                    float(
                        data["Volatility_24h"].mean()
                    )
                    if "Volatility_24h"
                    in data.columns
                    else None
            }

        return report

    # ====================================================
    # RSI ANALYSIS
    # ====================================================

    def rsi_analysis(self):

        self._check_loaded()

        if "RSI_14" not in self.df.columns:

            return {
                "error":
                    "RSI_14 column not found"
            }

        rsi = self.df["RSI_14"]

        return {

            "mean":
                float(rsi.mean()),

            "max":
                float(rsi.max()),

            "min":
                float(rsi.min()),

            "overbought":
                int((rsi > 70).sum()),

            "oversold":
                int((rsi < 30).sum())
        }

    # ====================================================
    # MACD ANALYSIS
    # ====================================================

    def macd_analysis(self):

        self._check_loaded()

        required = [
            "MACD",
            "MACD_signal",
            "MACD_hist"
        ]

        missing = [
            col
            for col in required
            if col not in self.df.columns
        ]

        if missing:

            return {
                "error":
                    f"Missing columns: {missing}"
            }

        bullish_cross = (
            (
                self.df["MACD"]
                >
                self.df["MACD_signal"]
            )
        ).sum()

        bearish_cross = (
            (
                self.df["MACD"]
                <
                self.df["MACD_signal"]
            )
        ).sum()

        return {

            "bullish_periods":
                int(bullish_cross),

            "bearish_periods":
                int(bearish_cross),

            "avg_histogram":
                float(
                    self.df["MACD_hist"].mean()
                )
        }

    # ====================================================
    # VOLATILITY
    # ====================================================

    def volatility_analysis(self):

        self._check_loaded()

        if "Volatility_24h" not in self.df.columns:

            return {
                "error":
                    "Volatility_24h missing"
            }

        vol = self.df["Volatility_24h"]

        return {

            "mean":
                float(vol.mean()),

            "std":
                float(vol.std()),

            "max":
                float(vol.max()),

            "min":
                float(vol.min())
        }

    # ====================================================
    # TREND ANALYSIS
    # ====================================================

    def trend_analysis(self):

        self._check_loaded()

        required = [
            "EMA20",
            "EMA50",
            "EMA200"
        ]

        missing = [
            col
            for col in required
            if col not in self.df.columns
        ]

        if missing:

            return {
                "error":
                    f"Missing columns: {missing}"
            }

        bullish = (
            (self.df["EMA20"] > self.df["EMA50"])
            &
            (self.df["EMA50"] > self.df["EMA200"])
        ).sum()

        bearish = (
            (self.df["EMA20"] < self.df["EMA50"])
            &
            (self.df["EMA50"] < self.df["EMA200"])
        ).sum()

        return {

            "bullish_candles":
                int(bullish),

            "bearish_candles":
                int(bearish),

            "bullish_ratio":
                round(
                    bullish / len(self.df),
                    4
                ),

            "bearish_ratio":
                round(
                    bearish / len(self.df),
                    4
                )
        }

    # ====================================================
    # CORRELATIONS
    # ====================================================

    def correlation_matrix(self):

        self._check_loaded()

        numeric_df = self.df.select_dtypes(
            include=np.number
        )

        return numeric_df.corr().round(3)

    # ====================================================
    # MARKET REGIME DETECTION
    # ====================================================

    def market_regime_detection(
        self,
        n_clusters=3
    ):

        self._check_loaded()

        features = [

            "Returns",

            "Volatility_24h",

            "ATR_14"
        ]

        available = [

            col
            for col in features
            if col in self.df.columns
        ]

        if len(available) < 2:

            return {
                "error":
                    "Not enough regime features"
            }

        X = self.df[
            available
        ].dropna()

        scaler = StandardScaler()

        X_scaled = scaler.fit_transform(X)

        model = KMeans(
            n_clusters=n_clusters,
            random_state=42,
            n_init=10
        )

        labels = model.fit_predict(
            X_scaled
        )

        counts = (
            pd.Series(labels)
            .value_counts()
            .to_dict()
        )

        return {

            "clusters":
                counts,

            "features":
                available
        }

    # ====================================================
    # COMPLETE REPORT
    # ====================================================

    def generate_report(self):

        self._check_loaded()

        return {

            "dataset":
                self.dataset_summary(),

            "sessions":
                self.session_analysis(),

            "rsi":
                self.rsi_analysis(),

            "macd":
                self.macd_analysis(),

            "volatility":
                self.volatility_analysis(),

            "trend":
                self.trend_analysis(),

            "regimes":
                self.market_regime_detection()
        }

    # ====================================================
    # INTERNAL
    # ====================================================

    

import pandas as pd
import numpy as np


class FeatureEngineering:

    def __init__(self, df: pd.DataFrame):

        self.df = df.copy()

    # -----------------------------
    # LAG FEATURES (VERY IMPORTANT)
    # -----------------------------
    def add_lag_features(self):

        for lag in [1, 2, 3, 5, 10]:

            self.df[f"close_lag_{lag}"] = (
                self.df["close"].shift(lag)
            )

            self.df[f"returns_lag_{lag}"] = (
                self.df["returns"].shift(lag)
            )

        return self

    # -----------------------------
    # ROLLING STATISTICS
    # -----------------------------
    def add_rolling_stats(self):

        windows = [5, 10, 20]

        for w in windows:

            self.df[f"rolling_mean_{w}"] = (
                self.df["close"]
                .rolling(w)
                .mean()
            )

            self.df[f"rolling_std_{w}"] = (
                self.df["close"]
                .rolling(w)
                .std()
            )

        return self

    # -----------------------------
    # PRICE STRUCTURE FEATURES
    # -----------------------------
    def add_price_structure(self):

        self.df["hl_range"] = (
            self.df["high"] - self.df["low"]
        )

        self.df["oc_range"] = (
            self.df["close"] - self.df["open"]
        )

        self.df["body_strength"] = (
            abs(self.df["close"] - self.df["open"])
            / (self.df["hl_range"] + 1e-9)
        )

        return self

    # -----------------------------
    # REGIME FEATURES (TREND VS RANGE)
    # -----------------------------
    def add_market_regime(self):

        self.df["trend_strength"] = (
            self.df["EMA20"] - self.df["EMA200"]
        )

        self.df["volatility_regime"] = (
            self.df["ATR_14"] / (self.df["close"] + 1e-9)
        )

        return self

    # -----------------------------
    # MOMENTUM FEATURES
    # -----------------------------
    def add_momentum(self):

        self.df["momentum_5"] = (
            self.df["close"]
            - self.df["close"].shift(5)
        )

        self.df["momentum_10"] = (
            self.df["close"]
            - self.df["close"].shift(10)
        )

        return self

    # -----------------------------
    # CLEANING
    # -----------------------------
    def clean(self):

        self.df = (
            self.df
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )

        return self

    # -----------------------------
    # PIPELINE
    # -----------------------------
    def build(self):

        return (
            self.add_lag_features()
            .add_rolling_stats()
            .add_price_structure()
            .add_market_regime()
            .add_momentum()
            .clean()
            .df
        )


def build_features(df: pd.DataFrame):

    return FeatureEngineering(df).build()

import pandas as pd
import numpy as np


class DatasetBuilder:

    def __init__(self, df: pd.DataFrame):

        self.df = df.copy()

    # -----------------------------
    # TIME FEATURES
    # -----------------------------
    def process_time(self):

        self.df["timestamp"] = pd.to_datetime(
            self.df["timestamp"]
        )

        self.df["hour"] = self.df["timestamp"].dt.hour

        self.df["day_of_week"] = (
            self.df["timestamp"].dt.dayofweek
        )

        return self

    # -----------------------------
    # SESSION ENCODING
    # -----------------------------
    def encode_session(self):

        mapping = {
            "Tokyo": 0,
            "London": 1,
            "NewYork": 2
        }

        self.df["session"] = (
            self.df["session"]
            .map(mapping)
            .fillna(-1)
        )

        return self

    # -----------------------------
    # PAIR ENCODING
    # -----------------------------
    def encode_pair(self):

        unique_pairs = self.df["pair"].unique()

        pair_map = {
            p: i for i, p in enumerate(unique_pairs)
        }

        self.df["pair"] = (
            self.df["pair"]
            .map(pair_map)
        )

        return self

    # -----------------------------
    # TARGET CREATION
    # -----------------------------
    def create_target(self, horizon=1):

        self.df["target"] = (
            self.df["close"]
            .shift(-horizon)
            > self.df["close"]
        ).astype(int)

        return self

    # -----------------------------
    # FEATURE SELECTION
    # -----------------------------
    def build_X(self):

        features = [

            # OHLCV
            "open", "high", "low", "close",
            "volume", "spread",

            # indicators (already computed)
            "RSI_14",
            "MACD", "MACD_signal", "MACD_hist",
            "ATR_14",

            # trend
            "EMA20", "EMA50", "EMA200",

            # volatility
            "volatility_24h",

            # Bollinger Bands
            "BB_upper", "BB_lower",

            # returns
            "returns",

            # encoded categorical
            "session",
            "pair",

            # time features
            "hour",
            "day_of_week"
        ]

        return self.df[features]

    # -----------------------------
    # BUILD y
    # -----------------------------
    def build_y(self):

        return self.df["target"]

    # -----------------------------
    # FULL PIPELINE
    # -----------------------------
    def build(self, horizon=1):

        self.process_time()
        self.encode_session()
        self.encode_pair()
        self.create_target(horizon)

        X = self.build_X()
        y = self.build_y()

        # Clean NaNs caused by shifting / indicators
        X = X.replace([np.inf, -np.inf], np.nan).dropna()
        y = y.loc[X.index]

        return X, y

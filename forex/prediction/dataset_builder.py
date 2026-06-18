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
        self.df["day_of_week"] = self.df["timestamp"].dt.dayofweek

        return self

    # -----------------------------
    # ENCODE SESSION
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
    # ENCODE PAIR (IMPORTANT)
    # -----------------------------
    def encode_pair(self):

        pairs = self.df["pair"].unique()

        pair_map = {
            p: i for i, p in enumerate(pairs)
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

            # indicators
            "RSI_14",
            "MACD", "MACD_signal", "MACD_hist",
            "ATR_14",
            "EMA20", "EMA50", "EMA200",
            "BB_upper", "BB_lower",

            # derived
            "returns",
            "volatility_24h",

            # encoded context
            "session",
            "pair",

            # time
            "hour",
            "day_of_week"
        ]

        return self.df[features]

    # -----------------------------
    # BUILD Y
    # -----------------------------
    def build_y(self, horizon=1):

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
        y = self.build_y(horizon)

        return X.dropna(), y.dropna()

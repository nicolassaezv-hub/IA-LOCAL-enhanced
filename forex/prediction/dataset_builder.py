import pandas as pd
import numpy as np


class DatasetBuilder:

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    # -----------------------------
    # TIME FEATURES
    # -----------------------------
    def process_time(self):
        if "timestamp" in self.df.columns:
            self.df["timestamp"]   = pd.to_datetime(self.df["timestamp"])
            self.df["hour"]        = self.df["timestamp"].dt.hour
            self.df["day_of_week"] = self.df["timestamp"].dt.dayofweek
        else:
            self.df["hour"]        = 0
            self.df["day_of_week"] = 0
        return self

    # -----------------------------
    # SESSION ENCODING
    # -----------------------------
    def encode_session(self):
        mapping = {"Tokyo": 0, "London": 1, "NewYork": 2}
        if "session" in self.df.columns:
            self.df["session"] = self.df["session"].map(mapping).fillna(-1)
        else:
            self.df["session"] = -1
        return self

    # -----------------------------
    # PAIR ENCODING
    # -----------------------------
    def encode_pair(self):
        if "pair" in self.df.columns:
            unique_pairs = self.df["pair"].unique()
            pair_map     = {p: i for i, p in enumerate(unique_pairs)}
            self.df["pair"] = self.df["pair"].map(pair_map)
        else:
            self.df["pair"] = 0
        return self

    # -----------------------------
    # TARGET — RISK/REWARD AWARE (UPGRADED)
    #
    # Old target: "next candle closes higher" — basically coin flip noise.
    #
    # New target: within the next `horizon` candles, does price reach
    # the take-profit level (+rr_ratio * ATR) BEFORE hitting the
    # stop-loss level (-1 * ATR)?
    #
    # Label = 1 (bullish / BUY)   if TP hit first
    # Label = 0 (bearish / SELL)  if SL hit first or neither
    #
    # Why ATR-based levels? Because ATR already reflects the pair's
    # natural volatility — the same pip distance means different things
    # on EURUSD vs GOLD.
    #
    # rr_ratio=1.5 means we only label rows where 1.5R profit is
    # achievable before 1R loss — so even a 50% accuracy is profitable.
    # -----------------------------
    def create_target(self, horizon: int = 10, rr_ratio: float = 1.5):

        close = self.df["close"].values
        atr_col = self.df.get("ATR_14")
        if atr_col is None or atr_col.isna().all():
            # Fallback: use a percentage of close as a synthetic ATR
            atr = (pd.Series(close) * 0.01).values
        else:
            atr = atr_col.fillna(pd.Series(close) * 0.01).values
        n     = len(close)
        target = np.zeros(n, dtype=int)

        for i in range(n - 1):
            entry = close[i]
            sl    = atr[i]          # 1 * ATR below (stop loss distance)
            tp    = atr[i] * rr_ratio  # rr_ratio * ATR above (take profit distance)

            # Skip rows where ATR is zero or NaN — can't define a meaningful target
            if sl <= 0 or np.isnan(sl) or np.isnan(tp) or tp <= 0:
                continue

            tp_price = entry + tp
            sl_price = entry - sl

            hit_tp = False
            hit_sl = False

            for j in range(i + 1, min(i + 1 + horizon, n)):
                high = self.df["high"].iloc[j]
                low  = self.df["low"].iloc[j]

                if high >= tp_price:
                    hit_tp = True
                    break
                if low <= sl_price:
                    hit_sl = True
                    break

            target[i] = 1 if hit_tp and not hit_sl else 0

        self.df["target"] = target
        return self

    # -----------------------------
    # FEATURE SELECTION
    # All newly engineered columns are included automatically via
    # _discover_features(), which is future-proof as features are added.
    # -----------------------------
    def build_X(self):

        # Core columns always included
        always_include = [
            "open", "high", "low", "close",
            "returns",
            "hour", "day_of_week",
            "session", "pair",
        ]

        # Optional pre-computed indicator columns from the CSV
        optional_csv = [
            "volume", "spread",
            "RSI_14",
            "MACD", "MACD_signal", "MACD_hist",
            "ATR_14",
            "EMA20", "EMA50", "EMA200",
            "volatility_24h",
            "BB_upper", "BB_lower",
        ]

        # Auto-detect engineered feature columns (all new computed cols)
        engineered_prefixes = (
            "close_lag_", "returns_lag_",
            "rolling_mean_", "rolling_std_",
            "hl_range", "oc_range", "body_strength",
            "upper_shadow", "lower_shadow",
            "trend_strength", "volatility_regime",
            "momentum_",
            "ADX_14", "plus_DI", "minus_DI",
            "stoch_k", "stoch_d", "stoch_cross",
            "williams_r",
            "obv", "obv_ema", "obv_diverge",
            "bb_width", "bb_squeeze", "bb_pct_b",
            "pattern_",
            "ema20_above_50", "ema50_above_200", "ema_cross_signal",
            "rsi_overbought", "rsi_oversold", "rsi_slope",
        )

        engineered_cols = [
            c for c in self.df.columns
            if any(c.startswith(p) for p in engineered_prefixes)
        ]

        use_optional = [c for c in optional_csv if c in self.df.columns]
        all_features  = list(dict.fromkeys(always_include + use_optional + engineered_cols))
        present       = [c for c in all_features if c in self.df.columns]

        return self.df[present]

    # -----------------------------
    # BUILD y
    # -----------------------------
    def build_y(self):
        return self.df["target"]

    # -----------------------------
    # FULL PIPELINE
    # horizon   : how many future candles to look ahead for TP/SL
    # rr_ratio  : take-profit multiple (e.g. 1.5 = risk 1, reward 1.5)
    # -----------------------------
    def build(self, horizon: int = 10, rr_ratio: float = 1.5):

        self.process_time()
        self.encode_session()
        self.encode_pair()
        self.create_target(horizon=horizon, rr_ratio=rr_ratio)

        X = self.build_X()
        y = self.build_y()

        # Align indices after NaN drops from feature engineering
        X = X.replace([np.inf, -np.inf], np.nan).dropna()
        y = y.loc[X.index]

        # Drop the last `horizon` rows — their target is incomplete
        # (we can't confirm TP/SL for the tail rows)
        if len(X) > horizon:
            X = X.iloc[:-horizon]
            y = y.iloc[:-horizon]

        return X, y

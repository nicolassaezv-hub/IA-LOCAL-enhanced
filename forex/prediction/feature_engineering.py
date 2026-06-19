import pandas as pd
import numpy as np


class FeatureEngineering:

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    # -----------------------------
    # LAG FEATURES
    # -----------------------------
    def add_lag_features(self):
        for lag in [1, 2, 3, 5, 10]:
            self.df[f"close_lag_{lag}"]   = self.df["close"].shift(lag)
            self.df[f"returns_lag_{lag}"] = self.df["returns"].shift(lag)
        return self

    # -----------------------------
    # ROLLING STATISTICS
    # -----------------------------
    def add_rolling_stats(self):
        for w in [5, 10, 20]:
            self.df[f"rolling_mean_{w}"] = self.df["close"].rolling(w).mean()
            self.df[f"rolling_std_{w}"]  = self.df["close"].rolling(w).std()
        return self

    # -----------------------------
    # PRICE STRUCTURE FEATURES
    # -----------------------------
    def add_price_structure(self):
        self.df["hl_range"] = self.df["high"] - self.df["low"]
        self.df["oc_range"] = self.df["close"] - self.df["open"]
        self.df["body_strength"] = (
            abs(self.df["close"] - self.df["open"])
            / (self.df["hl_range"] + 1e-9)
        )
        body_top    = self.df[["open", "close"]].max(axis=1)
        body_bottom = self.df[["open", "close"]].min(axis=1)
        self.df["upper_shadow"] = (self.df["high"] - body_top)    / (self.df["hl_range"] + 1e-9)
        self.df["lower_shadow"] = (body_bottom - self.df["low"])  / (self.df["hl_range"] + 1e-9)
        return self

    # -----------------------------
    # REGIME FEATURES (TREND VS RANGE)
    # -----------------------------
    def add_market_regime(self):
        self.df["trend_strength"]    = self.df["EMA20"] - self.df["EMA200"]
        self.df["volatility_regime"] = self.df["ATR_14"] / (self.df["close"] + 1e-9)
        return self

    # -----------------------------
    # MOMENTUM FEATURES
    # -----------------------------
    def add_momentum(self):
        self.df["momentum_5"]  = self.df["close"] - self.df["close"].shift(5)
        self.df["momentum_10"] = self.df["close"] - self.df["close"].shift(10)
        return self

    # -----------------------------
    # ADX — TREND STRENGTH (NEW)
    # High ADX = strong trend → model signals are more reliable in trending markets.
    # -----------------------------
    def add_adx(self, period: int = 14):
        high  = self.df["high"]
        low   = self.df["low"]
        close = self.df["close"]

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low  - close.shift(1)).abs()
        tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        up_move   = high - high.shift(1)
        down_move = low.shift(1) - low

        plus_dm  = np.where((up_move > down_move)   & (up_move > 0),   up_move,   0.0)
        minus_dm = np.where((down_move > up_move)   & (down_move > 0), down_move, 0.0)

        atr_s    = pd.Series(tr.values,       index=self.df.index).ewm(alpha=1/period, adjust=False).mean()
        plus_di  = 100 * pd.Series(plus_dm,  index=self.df.index).ewm(alpha=1/period, adjust=False).mean() / (atr_s + 1e-9)
        minus_di = 100 * pd.Series(minus_dm, index=self.df.index).ewm(alpha=1/period, adjust=False).mean() / (atr_s + 1e-9)

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
        self.df["ADX_14"]   = dx.ewm(alpha=1/period, adjust=False).mean().values
        self.df["plus_DI"]  = plus_di.values
        self.df["minus_DI"] = minus_di.values
        return self

    # -----------------------------
    # STOCHASTIC OSCILLATOR (NEW)
    # Overbought/oversold momentum + crossover signal.
    # -----------------------------
    def add_stochastic(self, k_period: int = 14, d_period: int = 3):
        low_min  = self.df["low"].rolling(k_period).min()
        high_max = self.df["high"].rolling(k_period).max()
        self.df["stoch_k"]     = 100 * (self.df["close"] - low_min) / (high_max - low_min + 1e-9)
        self.df["stoch_d"]     = self.df["stoch_k"].rolling(d_period).mean()
        k_above = (self.df["stoch_k"] > self.df["stoch_d"]).astype(int)
        self.df["stoch_cross"] = k_above - k_above.shift(1)
        return self

    # -----------------------------
    # WILLIAMS %R (NEW)
    # Momentum reversal indicator — complements RSI.
    # -----------------------------
    def add_williams_r(self, period: int = 14):
        high_max = self.df["high"].rolling(period).max()
        low_min  = self.df["low"].rolling(period).min()
        self.df["williams_r"] = -100 * (high_max - self.df["close"]) / (high_max - low_min + 1e-9)
        return self

    # -----------------------------
    # ON-BALANCE VOLUME (NEW)
    # Volume flow confirms or diverges from price moves.
    # -----------------------------
    def add_obv(self):
        direction = np.sign(self.df["close"].diff())
        direction.iloc[0] = 0
        col = "volume" if "volume" in self.df.columns else None
        vol = self.df[col] if col else pd.Series(np.zeros(len(self.df)), index=self.df.index)
        obv = (direction * vol).cumsum()
        self.df["obv"]         = obv
        self.df["obv_ema"]     = obv.ewm(span=20, adjust=False).mean()
        self.df["obv_diverge"] = obv - obv.ewm(span=20, adjust=False).mean()
        return self

    # -----------------------------
    # BOLLINGER BAND FEATURES (NEW)
    # BB squeeze = low volatility before explosive move.
    # %B tells where price is inside the band.
    # -----------------------------
    def add_bb_features(self):
        if "BB_upper" not in self.df.columns or "BB_lower" not in self.df.columns:
            mid = self.df["close"].rolling(20).mean()
            std = self.df["close"].rolling(20).std()
            self.df["BB_upper"] = mid + 2 * std
            self.df["BB_lower"] = mid - 2 * std
        bb_width = self.df["BB_upper"] - self.df["BB_lower"]
        self.df["bb_width"]   = bb_width
        self.df["bb_squeeze"] = bb_width / (bb_width.rolling(20).mean() + 1e-9)
        self.df["bb_pct_b"]   = (
            (self.df["close"] - self.df["BB_lower"])
            / (self.df["BB_upper"] - self.df["BB_lower"] + 1e-9)
        )
        return self

    # -----------------------------
    # CANDLESTICK PATTERN FLAGS (NEW)
    # Binary features — let the model discover which patterns matter.
    # -----------------------------
    def add_candle_patterns(self):
        op = self.df["open"]
        hi = self.df["high"]
        lo = self.df["low"]
        cl = self.df["close"]
        body   = (cl - op).abs()
        hl_rng = hi - lo + 1e-9

        self.df["pattern_doji"] = (body / hl_rng < 0.1).astype(int)

        body_top    = pd.concat([op, cl], axis=1).max(axis=1)
        body_bottom = pd.concat([op, cl], axis=1).min(axis=1)
        lower_wick  = body_bottom - lo
        upper_wick  = hi - body_top

        self.df["pattern_hammer"] = (
            (lower_wick > 2 * body) & (upper_wick < body * 0.5)
        ).astype(int)

        self.df["pattern_shooting_star"] = (
            (upper_wick > 2 * body) & (lower_wick < body * 0.5)
        ).astype(int)

        prev_body = cl.shift(1) - op.shift(1)
        curr_body = cl - op
        self.df["pattern_bull_engulf"] = (
            (prev_body < 0) & (curr_body > 0)
            & (cl > op.shift(1)) & (op < cl.shift(1))
        ).astype(int)

        self.df["pattern_bear_engulf"] = (
            (prev_body > 0) & (curr_body < 0)
            & (cl < op.shift(1)) & (op > cl.shift(1))
        ).astype(int)

        return self

    # -----------------------------
    # EMA CROSSOVER SIGNALS (NEW)
    # Directional bias from EMA alignments.
    # -----------------------------
    def add_ema_signals(self):
        if "EMA20" in self.df.columns and "EMA50" in self.df.columns:
            self.df["ema20_above_50"]  = (self.df["EMA20"] > self.df["EMA50"]).astype(int)
            self.df["ema50_above_200"] = (self.df["EMA50"] > self.df["EMA200"]).astype(int)
            cross = (self.df["EMA20"] > self.df["EMA50"]).astype(int)
            self.df["ema_cross_signal"] = cross - cross.shift(1)
        return self

    # -----------------------------
    # RSI FEATURES EXTENDED (NEW)
    # Overbought/oversold zones + slope direction.
    # -----------------------------
    def add_rsi_features(self):
        if "RSI_14" in self.df.columns:
            self.df["rsi_overbought"] = (self.df["RSI_14"] > 70).astype(int)
            self.df["rsi_oversold"]   = (self.df["RSI_14"] < 30).astype(int)
            self.df["rsi_slope"]      = self.df["RSI_14"].diff(3)
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
    # FULL PIPELINE
    # -----------------------------
    def build(self):
        return (
            self
            .add_lag_features()
            .add_rolling_stats()
            .add_price_structure()
            .add_market_regime()
            .add_momentum()
            .add_adx()
            .add_stochastic()
            .add_williams_r()
            .add_obv()
            .add_bb_features()
            .add_candle_patterns()
            .add_ema_signals()
            .add_rsi_features()
            .clean()
            .df
        )


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    return FeatureEngineering(df).build()

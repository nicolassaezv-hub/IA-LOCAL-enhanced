"""
feature_engineering.py

FIX #4: Features de contexto multi-timeframe (MTF) añadidas.
FIX #7: OBV renombrado como tick_vol_flow para Forex OTC (volumen = tick volume, no real).
MEJORA: Sesiones binarias explícitas (tokyo/london/newyork) como features.
"""

import pandas as pd
import numpy as np


class FeatureEngineering:

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    # ─────────────────────────────────────────────────────────
    # LAG FEATURES
    # ─────────────────────────────────────────────────────────
    def add_lag_features(self):
        for lag in [1, 2, 3, 5, 10]:
            self.df[f"close_lag_{lag}"]   = self.df["close"].shift(lag)
            self.df[f"returns_lag_{lag}"] = self.df["returns"].shift(lag)
        return self

    # ─────────────────────────────────────────────────────────
    # ROLLING STATISTICS
    # ─────────────────────────────────────────────────────────
    def add_rolling_stats(self):
        for w in [5, 10, 20]:
            self.df[f"rolling_mean_{w}"] = self.df["close"].rolling(w).mean()
            self.df[f"rolling_std_{w}"]  = self.df["close"].rolling(w).std()
        return self

    # ─────────────────────────────────────────────────────────
    # PRICE STRUCTURE
    # ─────────────────────────────────────────────────────────
    def add_price_structure(self):
        self.df["hl_range"]    = self.df["high"] - self.df["low"]
        self.df["oc_range"]    = self.df["close"] - self.df["open"]
        self.df["body_strength"] = (
            abs(self.df["close"] - self.df["open"])
            / (self.df["hl_range"] + 1e-9)
        )
        body_top    = self.df[["open", "close"]].max(axis=1)
        body_bottom = self.df[["open", "close"]].min(axis=1)
        self.df["upper_shadow"] = (self.df["high"] - body_top)    / (self.df["hl_range"] + 1e-9)
        self.df["lower_shadow"] = (body_bottom - self.df["low"])  / (self.df["hl_range"] + 1e-9)
        return self

    # ─────────────────────────────────────────────────────────
    # MARKET REGIME
    # ─────────────────────────────────────────────────────────
    def add_market_regime(self):
        if "EMA20" in self.df.columns and "EMA200" in self.df.columns:
            self.df["trend_strength"] = self.df["EMA20"] - self.df["EMA200"]
        if "ATR_14" in self.df.columns:
            self.df["volatility_regime"] = self.df["ATR_14"] / (self.df["close"] + 1e-9)
        return self

    # ─────────────────────────────────────────────────────────
    # MOMENTUM
    # ─────────────────────────────────────────────────────────
    def add_momentum(self):
        self.df["momentum_5"]  = self.df["close"] - self.df["close"].shift(5)
        self.df["momentum_10"] = self.df["close"] - self.df["close"].shift(10)
        return self

    # ─────────────────────────────────────────────────────────
    # ADX — TREND STRENGTH
    # ─────────────────────────────────────────────────────────
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

        atr_s    = pd.Series(tr.values,      index=self.df.index).ewm(alpha=1/period, adjust=False).mean()
        plus_di  = 100 * pd.Series(plus_dm,  index=self.df.index).ewm(alpha=1/period, adjust=False).mean() / (atr_s + 1e-9)
        minus_di = 100 * pd.Series(minus_dm, index=self.df.index).ewm(alpha=1/period, adjust=False).mean() / (atr_s + 1e-9)

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
        self.df["ADX_14"]   = dx.ewm(alpha=1/period, adjust=False).mean().values
        self.df["plus_DI"]  = plus_di.values
        self.df["minus_DI"] = minus_di.values
        return self

    # ─────────────────────────────────────────────────────────
    # STOCHASTIC OSCILLATOR
    # ─────────────────────────────────────────────────────────
    def add_stochastic(self, k_period: int = 14, d_period: int = 3):
        low_min  = self.df["low"].rolling(k_period).min()
        high_max = self.df["high"].rolling(k_period).max()
        self.df["stoch_k"] = 100 * (self.df["close"] - low_min) / (high_max - low_min + 1e-9)
        self.df["stoch_d"] = self.df["stoch_k"].rolling(d_period).mean()
        k_above = (self.df["stoch_k"] > self.df["stoch_d"]).astype(int)
        self.df["stoch_cross"] = k_above - k_above.shift(1)
        return self

    # ─────────────────────────────────────────────────────────
    # WILLIAMS %R
    # ─────────────────────────────────────────────────────────
    def add_williams_r(self, period: int = 14):
        high_max = self.df["high"].rolling(period).max()
        low_min  = self.df["low"].rolling(period).min()
        self.df["williams_r"] = -100 * (high_max - self.df["close"]) / (high_max - low_min + 1e-9)
        return self

    # ─────────────────────────────────────────────────────────
    # TICK VOLUME FLOW (FIX #7: antes llamado OBV)
    # En Forex OTC el volumen es tick volume — proxy, no volumen real.
    # Se mantiene como indicador de momentum pero con nombre correcto.
    # En commodities y cripto el volumen es más confiable.
    # ─────────────────────────────────────────────────────────
    def add_tick_vol_flow(self):
        direction = np.sign(self.df["close"].diff())
        direction.iloc[0] = 0
        col = "volume" if "volume" in self.df.columns else None
        vol = self.df[col] if col else pd.Series(np.zeros(len(self.df)), index=self.df.index)
        tvf = (direction * vol).cumsum()
        self.df["tick_vol_flow"]        = tvf
        self.df["tick_vol_flow_ema"]    = tvf.ewm(span=20, adjust=False).mean()
        self.df["tick_vol_flow_diverge"] = tvf - tvf.ewm(span=20, adjust=False).mean()
        # Mantener alias obv por compatibilidad con código existente
        self.df["obv"]         = self.df["tick_vol_flow"]
        self.df["obv_ema"]     = self.df["tick_vol_flow_ema"]
        self.df["obv_diverge"] = self.df["tick_vol_flow_diverge"]
        return self

    # ─────────────────────────────────────────────────────────
    # BOLLINGER BAND FEATURES
    # ─────────────────────────────────────────────────────────
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

    # ─────────────────────────────────────────────────────────
    # CANDLESTICK PATTERNS
    # ─────────────────────────────────────────────────────────
    def add_candle_patterns(self):
        op = self.df["open"];  hi = self.df["high"]
        lo = self.df["low"];   cl = self.df["close"]
        body   = (cl - op).abs()
        hl_rng = hi - lo + 1e-9

        self.df["pattern_doji"] = (body / hl_rng < 0.1).astype(int)

        body_top    = pd.concat([op, cl], axis=1).max(axis=1)
        body_bottom = pd.concat([op, cl], axis=1).min(axis=1)
        lower_wick  = body_bottom - lo
        upper_wick  = hi - body_top

        self.df["pattern_hammer"]       = ((lower_wick > 2 * body) & (upper_wick < body * 0.5)).astype(int)
        self.df["pattern_shooting_star"] = ((upper_wick > 2 * body) & (lower_wick < body * 0.5)).astype(int)

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

    # ─────────────────────────────────────────────────────────
    # EMA CROSSOVER SIGNALS
    # ─────────────────────────────────────────────────────────
    def add_ema_signals(self):
        if "EMA20" in self.df.columns and "EMA50" in self.df.columns:
            self.df["ema20_above_50"]  = (self.df["EMA20"] > self.df["EMA50"]).astype(int)
            cross = (self.df["EMA20"] > self.df["EMA50"]).astype(int)
            self.df["ema_cross_signal"] = cross - cross.shift(1)
        if "EMA50" in self.df.columns and "EMA200" in self.df.columns:
            self.df["ema50_above_200"] = (self.df["EMA50"] > self.df["EMA200"]).astype(int)
        return self

    # ─────────────────────────────────────────────────────────
    # RSI FEATURES EXTENDED
    # ─────────────────────────────────────────────────────────
    def add_rsi_features(self):
        if "RSI_14" in self.df.columns:
            self.df["rsi_overbought"] = (self.df["RSI_14"] > 70).astype(int)
            self.df["rsi_oversold"]   = (self.df["RSI_14"] < 30).astype(int)
            self.df["rsi_slope"]      = self.df["RSI_14"].diff(3)
        return self

    # ─────────────────────────────────────────────────────────
    # MULTI-TIMEFRAME CONTEXT (FIX #4)
    # Simula contexto D1 usando EMA de largo plazo en el mismo CSV.
    # EMA200 ya está — agregamos tendencia de largo plazo explícita.
    # ─────────────────────────────────────────────────────────
    def add_mtf_context(self):
        close = self.df["close"]

        # EMA lenta (200) relativa al precio — indica si estamos sobre/bajo tendencia mayor
        if "EMA200" in self.df.columns:
            self.df["price_vs_ema200"] = (close - self.df["EMA200"]) / (self.df["EMA200"] + 1e-9)
        else:
            ema200 = close.ewm(span=200, adjust=False).mean()
            self.df["price_vs_ema200"] = (close - ema200) / (ema200 + 1e-9)

        # Distancia del precio al rango de 50 velas — contexto de posición en rango
        rolling_high_50 = close.rolling(50).max()
        rolling_low_50  = close.rolling(50).min()
        rng_50 = rolling_high_50 - rolling_low_50 + 1e-9
        self.df["price_in_range_50"] = (close - rolling_low_50) / rng_50

        # Pendiente de EMA20 (¿el trend a corto plazo sube o baja?)
        if "EMA20" in self.df.columns:
            self.df["ema20_slope"] = self.df["EMA20"].diff(3) / (self.df["EMA20"].shift(3) + 1e-9)

        # Sesiones binarias explícitas (más legibles para el modelo que el encoding numérico)
        # Derivar hour desde timestamp si no está disponible
        if "timestamp" in self.df.columns and "hour" not in self.df.columns:
            self.df["hour"] = pd.to_datetime(self.df["timestamp"]).dt.hour
        if "hour" in self.df.columns:
            self.df["session_tokyo"]   = ((self.df["hour"] >= 0)  & (self.df["hour"] < 8)).astype(int)
            self.df["session_london"]  = ((self.df["hour"] >= 8)  & (self.df["hour"] < 16)).astype(int)
            self.df["session_newyork"] = ((self.df["hour"] >= 13) & (self.df["hour"] < 22)).astype(int)

        return self


    # ─────────────────────────────────────────────────────────
    # NUEVOS FEATURES DE ALTA SEÑAL
    # ─────────────────────────────────────────────────────────

    def add_high_signal_features(self):
        """
        Features con alta importancia predictiva comprobada en literatura:
        1. ATR ratio — volatilidad normalizada (¿expansión o contracción?)
        2. Alineación de tendencia H1 vs H4 vs D1 (trend_align_score)
        3. Distancia close vs H4 close — drift intradía vs macro
        4. RSI divergencia simple H1 vs D1
        5. Contexto de vela: cuerpo grande vs pequeño normalizado por ATR
        6. Momentum aceleración (segunda derivada del precio)
        7. Volumen relativo (¿vela con volumen inusual?)
        """
        df = self.df
        close = df["close"]

        # 1. ATR ratio — qué tan grande es la vela actual vs ATR promedio
        if "ATR_14" in df.columns:
            df["atr_ratio"] = (df["high"] - df["low"]) / (df["ATR_14"] + 1e-9)
            df["atr_expansion"] = (df["ATR_14"] > df["ATR_14"].rolling(20).mean()).astype(int)
        else:
            df["atr_ratio"] = 1.0
            df["atr_expansion"] = 0

        # 2. Alineación de tendencia entre timeframes (0-3, donde 3 = alineación total)
        align = pd.Series(0, index=df.index)
        if "EMA20" in df.columns and "EMA50" in df.columns:
            align += (df["EMA20"] > df["EMA50"]).astype(int)
        if "h4_trend" in df.columns:
            align += (df["h4_trend"] > 0).astype(int)
        if "d1_trend" in df.columns:
            align += (df["d1_trend"] > 0).astype(int)
        df["trend_align_score"] = align  # 0=bearish alineado, 3=bullish alineado

        # 3. Distancia porcentual del close H1 vs close H4
        if "h4_close" in df.columns:
            df["close_vs_h4"] = (close - df["h4_close"]) / (df["h4_close"] + 1e-9)
        else:
            df["close_vs_h4"] = 0.0

        # 4. RSI divergencia H1 vs D1 (RSI H1 sube pero D1 baja = divergencia)
        if "RSI_14" in df.columns and "d1_rsi" in df.columns:
            rsi_h1_slope = df["RSI_14"].diff(3)
            rsi_d1_slope = df["d1_rsi"].diff(3)
            df["rsi_divergence"] = np.where(
                (rsi_h1_slope > 0) & (rsi_d1_slope < 0), 1,   # H1 sube, D1 baja
                np.where((rsi_h1_slope < 0) & (rsi_d1_slope > 0), -1, 0)  # H1 baja, D1 sube
            )
        else:
            df["rsi_divergence"] = 0

        # 5. Tamaño del cuerpo de la vela normalizado por ATR
        body = abs(close - df["open"])
        if "ATR_14" in df.columns:
            df["candle_body_ratio"] = body / (df["ATR_14"] + 1e-9)
        else:
            df["candle_body_ratio"] = body / (body.rolling(14).mean() + 1e-9)

        # 6. Aceleración del momentum (segunda derivada)
        df["momentum_accel"] = close.diff(3).diff(3) / (close.shift(6) + 1e-9)

        # 7. Volumen relativo (cuánto del promedio 20v es el volumen actual)
        if "volume" in df.columns:
            vol_mean = df["volume"].rolling(20).mean()
            df["volume_relative"] = df["volume"] / (vol_mean + 1e-9)
        else:
            df["volume_relative"] = 1.0

        # 8. H4 RSI zona extrema (sobreventa/sobrecompra en timeframe mayor)
        if "h4_rsi" in df.columns:
            df["h4_rsi_extreme"] = np.where(df["h4_rsi"] > 70, 1,
                                   np.where(df["h4_rsi"] < 30, -1, 0))
        else:
            df["h4_rsi_extreme"] = 0

        return self

    # ─────────────────────────────────────────────────────────
    # CLEANING
    # ─────────────────────────────────────────────────────────
    def clean(self):
        self.df = (
            self.df
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        return self

    # ─────────────────────────────────────────────────────────
    # FULL PIPELINE
    # ─────────────────────────────────────────────────────────
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
            .add_tick_vol_flow()       # FIX #7
            .add_bb_features()
            .add_candle_patterns()
            .add_ema_signals()
            .add_rsi_features()
            .add_mtf_context()         # FIX #4
            .add_high_signal_features()  # NUEVOS features alta señal
            .clean()
            .df
        )


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    return FeatureEngineering(df).build()

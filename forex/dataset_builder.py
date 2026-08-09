"""
dataset_builder.py

FIX #1: predict_features() retorna la última vela real (sin drop de horizonte).
FIX #3: Timeouts (ni TP ni SL) se excluyen del training.
FIX #9: PAIR_CONFIG con horizon/rr_ratio óptimos por instrumento.

NUEVO: rr_ratio=1.0 como default universal más balanceado.
NUEVO: Las features MTF reales (h4_*, d1_*) se incluyen automáticamente si están presentes.
NUEVO: filter_cols_by_variance() elimina features con varianza casi cero (ruido).
"""

import pandas as pd
import numpy as np

# ─────────────────────────────────────────────────────────────
# CONFIG POR PAR
# ─────────────────────────────────────────────────────────────
PAIR_CONFIG = {
    "EURUSD": {"horizon": 12, "rr_ratio": 1.0},
    "GBPUSD": {"horizon": 12, "rr_ratio": 1.0},
    "USDJPY": {"horizon": 12, "rr_ratio": 1.0},
    "USDCHF": {"horizon": 12, "rr_ratio": 1.0},
    "AUDUSD": {"horizon": 10, "rr_ratio": 1.0},
    "USDCAD": {"horizon": 10, "rr_ratio": 1.0},
    "NZDUSD": {"horizon": 10, "rr_ratio": 1.0},
    "AUDCAD": {"horizon": 10, "rr_ratio": 1.0},
    "EURGBP": {"horizon": 10, "rr_ratio": 1.0},
    "EURJPY": {"horizon": 10, "rr_ratio": 1.2},
    "GBPJPY": {"horizon":  8, "rr_ratio": 1.2},
    "XAUUSD": {"horizon":  8, "rr_ratio": 1.5},
    "XAGUSD": {"horizon":  8, "rr_ratio": 1.5},
    "USOIL":  {"horizon":  8, "rr_ratio": 1.5},
    "UKOIL":  {"horizon":  8, "rr_ratio": 1.5},
    "BTCUSD": {"horizon":  6, "rr_ratio": 2.0},
    "ETHUSD": {"horizon":  6, "rr_ratio": 2.0},
}

DEFAULT_PAIR_CONFIG = {"horizon": 10, "rr_ratio": 1.0}


def get_pair_config(pair: str) -> dict:
    if not pair:
        return DEFAULT_PAIR_CONFIG
    clean = pair.upper().replace("/", "").replace("_", "").replace("-", "")
    return PAIR_CONFIG.get(clean, DEFAULT_PAIR_CONFIG)


class DatasetBuilder:

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def process_time(self):
        if "timestamp" in self.df.columns:
            ts = pd.to_datetime(self.df["timestamp"])
            self.df["hour"]        = ts.dt.hour
            self.df["day_of_week"] = ts.dt.dayofweek
        else:
            self.df["hour"]        = 0
            self.df["day_of_week"] = 0
        return self

    def encode_session(self):
        mapping = {"Tokyo": 0, "London": 1, "NewYork": 2}
        if "session" in self.df.columns:
            self.df["session"] = self.df["session"].map(mapping).fillna(-1)
        else:
            self.df["session"] = -1
        return self

    def encode_pair(self):
        if "pair" in self.df.columns:
            unique_pairs = self.df["pair"].unique()
            pair_map     = {p: i for i, p in enumerate(unique_pairs)}
            self.df["pair"] = self.df["pair"].map(pair_map)
        else:
            self.df["pair"] = 0
        return self

    # ─────────────────────────────────────────────────────────
    # TARGET — RISK/REWARD AWARE (sin timeouts en train)
    # ─────────────────────────────────────────────────────────
    def create_target(self, horizon: int = 10, rr_ratio: float = 1.0):
        close   = self.df["close"].values
        atr_col = self.df.get("ATR_14")
        if atr_col is None or atr_col.isna().all():
            atr = (pd.Series(close) * 0.01).values
        else:
            atr = atr_col.fillna(pd.Series(close) * 0.01).values

        n      = len(close)
        target = np.full(n, -1, dtype=int)

        for i in range(n - 1):
            entry = close[i]
            sl    = atr[i]
            tp    = atr[i] * rr_ratio

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

            if hit_tp and not hit_sl:
                target[i] = 1
            elif hit_sl and not hit_tp:
                target[i] = 0

        self.df["target"] = target
        return self

    # ─────────────────────────────────────────────────────────
    # FEATURE COLUMNS
    # Incluye features MTF reales (h4_*, d1_*) si están presentes
    # ─────────────────────────────────────────────────────────
    def build_X(self):
        always_include = [
            "open", "high", "low", "close",
            "returns", "hour", "day_of_week", "session", "pair",
        ]
        optional_csv = [
            "volume", "spread",
            "RSI_14", "MACD", "MACD_signal", "MACD_hist",
            "ATR_14", "EMA20", "EMA50", "EMA200",
            "volatility_24h", "BB_upper", "BB_lower",
        ]
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
            "tick_vol_flow", "obv",
            "bb_width", "bb_squeeze", "bb_pct_b",
            "pattern_",
            "ema20_above_50", "ema50_above_200", "ema_cross_signal",
            "rsi_overbought", "rsi_oversold", "rsi_slope",
            "price_vs_ema200", "price_in_range_50", "ema20_slope",
            "session_tokyo", "session_london", "session_newyork",
            # MTF reales
            "h4_", "d1_",
            # Nuevos features alta señal
            "atr_ratio", "atr_expansion", "trend_align_score",
            "close_vs_h4", "rsi_divergence", "candle_body_ratio",
            "momentum_accel", "volume_relative", "h4_rsi_extreme",
        )
        engineered_cols = [
            c for c in self.df.columns
            if any(c.startswith(p) for p in engineered_prefixes)
        ]
        use_optional = [c for c in optional_csv if c in self.df.columns]
        all_features  = list(dict.fromkeys(always_include + use_optional + engineered_cols))
        present       = [c for c in all_features if c in self.df.columns]
        # Excluir siempre: timestamp, target y pair (pair tiene varianza 0
        # en CSVs de un solo instrumento y causa feature mismatch train/predict)
        exclude = {"timestamp", "target", "pair"}
        present = [c for c in present if c not in exclude]
        return self.df[present]

    def build_y(self):
        return self.df["target"]

    # ─────────────────────────────────────────────────────────
    # FILTER LOW VARIANCE FEATURES
    # Elimina features con std ≈ 0 (constantes) que no aportan señal
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def filter_low_variance(X: pd.DataFrame, threshold: float = 1e-6) -> pd.DataFrame:
        # Siempre preservar MTF reales y columnas clave aunque tengan varianza baja
        protected = {c for c in X.columns if c.startswith("h4_") or c.startswith("d1_")}
        var  = X.var()
        keep = list(var[var > threshold].index) + [c for c in protected if c not in var[var > threshold].index]
        keep = [c for c in X.columns if c in keep]  # mantener orden original
        removed = len(X.columns) - len(keep)
        if removed > 0:
            print(f"[DATASET] Features baja varianza eliminadas: {removed}")
        return X[keep]

    # ─────────────────────────────────────────────────────────
    # BUILD — para TRAINING
    # ─────────────────────────────────────────────────────────
    def build(self, horizon: int = 10, rr_ratio: float = 1.0):
        self.process_time()
        self.encode_session()
        self.encode_pair()
        self.create_target(horizon=horizon, rr_ratio=rr_ratio)

        X = self.build_X()
        y = self.build_y()

        X = X.replace([np.inf, -np.inf], np.nan).dropna()
        y = y.loc[X.index]

        if len(X) > horizon:
            X = X.iloc[:-horizon]
            y = y.iloc[:-horizon]

        # Eliminar timeouts
        valid_mask = y != -1
        X = X[valid_mask]
        y = y[valid_mask]

        # Eliminar features de baja varianza
        X = self.filter_low_variance(X)

        timeout_pct = (1 - valid_mask.sum() / len(valid_mask)) * 100
        buy_pct     = (y == 1).sum() / len(y) * 100
        sell_pct    = (y == 0).sum() / len(y) * 100
        print(f"[DATASET] Filas train: {len(X)} | BUY: {buy_pct:.1f}% | SELL: {sell_pct:.1f}% | Timeout: {timeout_pct:.1f}%")

        return X, y

    # ─────────────────────────────────────────────────────────
    # PREDICT FEATURES — última vela real (FIX #1)
    # ─────────────────────────────────────────────────────────
    def predict_features(self, n_rows: int = 1,
                          train_columns: list = None) -> pd.DataFrame:
        """
        Extrae features de la(s) última(s) vela(s) para predicción.
        Si se pasan train_columns, alinea exactamente con las columnas
        del modelo entrenado (evita feature mismatch).
        """
        self.process_time()
        self.encode_session()
        self.encode_pair()

        X = self.build_X()
        X = X.replace([np.inf, -np.inf], np.nan).dropna()

        if len(X) == 0:
            raise ValueError("Sin filas válidas tras feature engineering.")

        X_tail = X.tail(n_rows)

        # Alinear con columnas del modelo si se proporcionan
        if train_columns is not None:
            for col in train_columns:
                if col not in X_tail.columns:
                    X_tail = X_tail.copy()
                    X_tail[col] = 0.0
            X_tail = X_tail[train_columns]

        return X_tail

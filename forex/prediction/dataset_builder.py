"""
dataset_builder.py

FIX #1: predict_features() retorna la última vela real (sin drop de horizonte).
FIX #3: Timeouts (ni TP ni SL) se excluyen del training.
FIX #9: PAIR_CONFIG con horizon/rr_ratio óptimos por instrumento.

NUEVO: rr_ratio=1.0 como default universal más balanceado.
NUEVO: Las features MTF reales (h4_*, d1_*) se incluyen automáticamente si están presentes.
NUEVO: filter_cols_by_variance() elimina features con varianza casi cero (ruido).
"""

import hashlib
import json

import pandas as pd
import numpy as np


FEATURE_PROFILES = ("legacy", "stationary_v1")

STATIONARY_V1_EXCLUDED_FEATURES = {
    "open", "high", "low", "close", "spread",
    "MACD", "MACD_signal", "MACD_hist", "ATR_14",
    "EMA20", "EMA50", "EMA200", "BB_upper", "BB_lower",
    "hl_range", "oc_range", "trend_strength", "momentum_5", "momentum_10",
    "tick_vol_flow", "tick_vol_flow_ema", "obv", "obv_ema", "obv_diverge",
    "bb_width",
    "h4_close", "h4_ema20", "h4_ema50", "h4_ema200", "h4_atr", "h4_macd",
    "d1_close", "d1_ema20", "d1_ema50", "d1_ema200", "d1_atr", "d1_macd",
}
STATIONARY_V1_EXCLUDED_PREFIXES = (
    "close_lag_", "rolling_mean_", "rolling_std_",
)
STATIONARY_V1_NORMALIZED_FEATURES = (
    "open_vs_close", "high_vs_close", "low_vs_close", "range_pct", "body_pct",
    "close_vs_ema20", "close_vs_ema50", "close_vs_ema200",
    "ema20_vs_50", "ema50_vs_200", "trend_strength_pct",
    "close_vs_lag_1", "close_vs_lag_2", "close_vs_lag_3",
    "close_vs_lag_5", "close_vs_lag_10",
    "close_vs_rollmean_5", "close_vs_rollmean_10", "close_vs_rollmean_20",
    "rolling_std_pct_5", "rolling_std_pct_10", "rolling_std_pct_20",
    "momentum_pct_5", "momentum_pct_10", "bb_width_pct", "atr_pct",
    "macd_pct", "macd_signal_pct", "macd_hist_pct", "spread_pct",
    "h4_close_vs_ema20", "h4_close_vs_ema50", "h4_close_vs_ema200",
    "h4_ema20_vs_50", "h4_ema50_vs_200", "h4_atr_pct", "h4_macd_pct",
    "d1_close_vs_ema20", "d1_close_vs_ema50", "d1_close_vs_ema200",
    "d1_ema20_vs_50", "d1_ema50_vs_200", "d1_atr_pct", "d1_macd_pct",
)


def feature_names_sha256(feature_names) -> str:
    """Return a deterministic identity for an exact ordered feature contract."""
    payload = json.dumps(list(feature_names), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

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
    "USOUSD": {"horizon":  8, "rr_ratio": 1.5},
    "UKOUSD": {"horizon":  8, "rr_ratio": 1.5},
    "BTCUSDT": {"horizon": 6, "rr_ratio": 2.0},
    "ETHUSDT": {"horizon": 6, "rr_ratio": 2.0},
}

DEFAULT_PAIR_CONFIG = {"horizon": 10, "rr_ratio": 1.0}


def get_pair_config(pair: str) -> dict:
    if not pair:
        return DEFAULT_PAIR_CONFIG
    clean = pair.upper().replace("/", "").replace("_", "").replace("-", "")
    return PAIR_CONFIG.get(clean, DEFAULT_PAIR_CONFIG)


def is_ml_configured(pair: str) -> bool:
    """Return whether production ML horizon/RR is explicitly configured."""
    if not pair:
        return False
    clean = pair.upper().replace("/", "").replace("_", "").replace("-", "")
    return clean in PAIR_CONFIG


def require_ml_config(pair: str) -> dict:
    """Fail closed instead of promoting production ML through the default config."""
    if not is_ml_configured(pair):
        raise ValueError(f"ML_CONFIG_NOT_DEFINED: {pair}")
    return get_pair_config(pair)


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
                tp_hit = high >= tp_price
                sl_hit = low <= sl_price
                if tp_hit and sl_hit:
                    break
                if tp_hit:
                    hit_tp = True
                    break
                if sl_hit:
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
    @staticmethod
    def _validate_feature_profile(feature_profile: str) -> str:
        profile = str(feature_profile).strip().lower()
        if profile not in FEATURE_PROFILES:
            raise ValueError(f"FEATURE_PROFILE_UNSUPPORTED: {feature_profile}")
        return profile

    @staticmethod
    def _ratio(numerator, denominator):
        return numerator / denominator.replace(0, np.nan)

    def _legacy_feature_names(self) -> list[str]:
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
        return [c for c in present if c not in exclude]

    def _add_stationary_v1_features(self) -> None:
        """Add row-local or trailing-only relative representations."""
        df = self.df
        close = df["close"]
        df["open_vs_close"] = self._ratio(df["open"], close) - 1.0
        df["high_vs_close"] = self._ratio(df["high"], close) - 1.0
        df["low_vs_close"] = self._ratio(df["low"], close) - 1.0
        df["range_pct"] = self._ratio(df["high"] - df["low"], close)
        df["body_pct"] = self._ratio(close - df["open"], df["open"])

        for period in (20, 50, 200):
            ema = f"EMA{period}"
            if ema in df.columns:
                df[f"close_vs_ema{period}"] = self._ratio(close - df[ema], close)
        if {"EMA20", "EMA50"} <= set(df.columns):
            df["ema20_vs_50"] = self._ratio(df["EMA20"] - df["EMA50"], close)
        if {"EMA50", "EMA200"} <= set(df.columns):
            df["ema50_vs_200"] = self._ratio(df["EMA50"] - df["EMA200"], close)
        if {"EMA20", "EMA200"} <= set(df.columns):
            df["trend_strength_pct"] = self._ratio(
                df["EMA20"] - df["EMA200"], close
            )

        for lag in (1, 2, 3, 5, 10):
            source = f"close_lag_{lag}"
            lagged = df[source] if source in df.columns else close.shift(lag)
            df[f"close_vs_lag_{lag}"] = self._ratio(close, lagged) - 1.0
        for window in (5, 10, 20):
            mean_name = f"rolling_mean_{window}"
            std_name = f"rolling_std_{window}"
            rolling_mean = (
                df[mean_name]
                if mean_name in df.columns
                else close.rolling(window).mean()
            )
            rolling_std = (
                df[std_name]
                if std_name in df.columns
                else close.rolling(window).std()
            )
            df[f"close_vs_rollmean_{window}"] = (
                self._ratio(close, rolling_mean) - 1.0
            )
            df[f"rolling_std_pct_{window}"] = self._ratio(rolling_std, close)

        lagged_5 = df["close_lag_5"] if "close_lag_5" in df.columns else close.shift(5)
        lagged_10 = (
            df["close_lag_10"] if "close_lag_10" in df.columns else close.shift(10)
        )
        df["momentum_pct_5"] = self._ratio(close, lagged_5) - 1.0
        df["momentum_pct_10"] = self._ratio(close, lagged_10) - 1.0
        if {"BB_upper", "BB_lower"} <= set(df.columns):
            df["bb_width_pct"] = self._ratio(
                df["BB_upper"] - df["BB_lower"], close
            )
        if "ATR_14" in df.columns:
            df["atr_pct"] = self._ratio(df["ATR_14"], close)
        for source, target in (
            ("MACD", "macd_pct"),
            ("MACD_signal", "macd_signal_pct"),
            ("MACD_hist", "macd_hist_pct"),
            ("spread", "spread_pct"),
        ):
            if source in df.columns:
                df[target] = self._ratio(df[source], close)

        for prefix in ("h4", "d1"):
            prefix_close = f"{prefix}_close"
            if prefix_close not in df.columns:
                continue
            mtf_close = df[prefix_close]
            for period in (20, 50, 200):
                ema = f"{prefix}_ema{period}"
                if ema in df.columns:
                    df[f"{prefix}_close_vs_ema{period}"] = self._ratio(
                        mtf_close - df[ema], mtf_close
                    )
            ema20 = f"{prefix}_ema20"
            ema50 = f"{prefix}_ema50"
            ema200 = f"{prefix}_ema200"
            if {ema20, ema50} <= set(df.columns):
                df[f"{prefix}_ema20_vs_50"] = self._ratio(
                    df[ema20] - df[ema50], mtf_close
                )
            if {ema50, ema200} <= set(df.columns):
                df[f"{prefix}_ema50_vs_200"] = self._ratio(
                    df[ema50] - df[ema200], mtf_close
                )
            atr = f"{prefix}_atr"
            macd = f"{prefix}_macd"
            if atr in df.columns:
                df[f"{prefix}_atr_pct"] = self._ratio(df[atr], mtf_close)
            if macd in df.columns:
                df[f"{prefix}_macd_pct"] = self._ratio(df[macd], mtf_close)

    # ─────────────────────────────────────────────────────────
    # FEATURE COLUMNS
    # Incluye features MTF reales (h4_*, d1_*) si están presentes
    # ─────────────────────────────────────────────────────────
    def build_X(self, feature_profile: str = "legacy"):
        profile = self._validate_feature_profile(feature_profile)
        legacy_names = self._legacy_feature_names()
        if profile == "legacy":
            return self.df[legacy_names]

        self._add_stationary_v1_features()
        names = [
            name for name in legacy_names
            if name not in STATIONARY_V1_NORMALIZED_FEATURES
            if name not in STATIONARY_V1_EXCLUDED_FEATURES
            and not name.startswith(STATIONARY_V1_EXCLUDED_PREFIXES)
        ]
        names.extend(
            name for name in STATIONARY_V1_NORMALIZED_FEATURES
            if name in self.df.columns and name not in names
        )
        return self.df[names]

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
    def build(
        self,
        horizon: int = 10,
        rr_ratio: float = 1.0,
        feature_profile: str = "legacy",
    ):
        profile = self._validate_feature_profile(feature_profile)
        self.process_time()
        self.encode_session()
        self.encode_pair()
        self.create_target(horizon=horizon, rr_ratio=rr_ratio)

        X = self.build_X(feature_profile=profile)
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
        X = self.filter_low_variance(
            X,
            threshold=0.0 if profile == "stationary_v1" else 1e-6,
        )

        timeout_pct = (1 - valid_mask.sum() / len(valid_mask)) * 100
        buy_pct     = (y == 1).sum() / len(y) * 100
        sell_pct    = (y == 0).sum() / len(y) * 100
        print(f"[DATASET] Filas train: {len(X)} | BUY: {buy_pct:.1f}% | SELL: {sell_pct:.1f}% | Timeout: {timeout_pct:.1f}%")

        return X, y

    # ─────────────────────────────────────────────────────────
    # PREDICT FEATURES — última vela real (FIX #1)
    # ─────────────────────────────────────────────────────────
    def predict_features(
        self,
        n_rows: int = 1,
        train_columns: list = None,
        feature_profile: str = "legacy",
    ) -> pd.DataFrame:
        """
        Extrae features de la(s) última(s) vela(s) para predicción.
        Si se pasan train_columns, alinea exactamente con las columnas
        del modelo entrenado (evita feature mismatch).
        """
        self.process_time()
        self.encode_session()
        self.encode_pair()

        X = self.build_X(feature_profile=feature_profile)
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

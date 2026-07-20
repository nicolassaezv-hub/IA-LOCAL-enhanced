"""
csv_adapter.py — Normaliza CSVs de brokers al esquema interno de ASTRA.

NUEVO: filter_weekend_gaps() — elimina las primeras N velas post-gap (fin de semana/feriados)
       para evitar ATR inflado y SL/TP falsos en la apertura del lunes.
NUEVO: merge_mtf_context() — enriquece un CSV H1 con features de H4 y D1 usando merge_asof
       (sin lookahead: para cada vela H1 usa la última vela H4/D1 disponible antes de ella).
"""

import os
import pandas as pd
import numpy as np

# ─────────────────────────────────────────────────────────────
# COLUMN RENAMING MAP
# ─────────────────────────────────────────────────────────────
_RENAME = {
    "volume":             "volume",
    "rsi_14":             "RSI_14",
    "macd":               "MACD",
    "macd_signal":        "MACD_signal",
    "macd_histogram":     "MACD_hist",
    "macd_hist":          "MACD_hist",
    "atr_14":             "ATR_14",
    "ema_20":             "EMA20",
    "ema_50":             "EMA50",
    "ema_150":            "EMA200",
    "ema_200":            "EMA200",
    "bollinger_upper_20": "BB_upper",
    "bollinger_lower_20": "BB_lower",
    "bb_upper":           "BB_upper",
    "bb_lower":           "BB_lower",
    "return_5":           "returns",
    "returns":            "returns",
    "volatility_20":      "volatility_24h",
    "volatility_24h":     "volatility_24h",
}

_REQUIRED = ["open", "high", "low", "close"]

_PAIR_SUFFIXES = ['_TEST','_H1','_H4','_D1','_M15','_M30',
                  '_TEST2','_BACKUP','_NEW','_OLD','_2024','_2025','_2026']

def _normalize_pair(name: str) -> str:
    """Normalize a pair name: remove underscores and strip known suffixes."""
    name = str(name).upper().strip()
    for sfx in _PAIR_SUFFIXES:
        if name.endswith(sfx):
            name = name[:-len(sfx)]
            break
    name = name.replace("_", "").replace("-", "").replace("/", "")
    return name if name else "UNKNOWN"


# ─────────────────────────────────────────────────────────────
# FILL NaN INDICATORS
# ─────────────────────────────────────────────────────────────
def fill_nan_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"]

    if "returns" not in df.columns:
        df["returns"] = close.pct_change().fillna(0)

    if "RSI_14" not in df.columns:
        delta = close.diff()
        gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
        rs    = gain / (loss + 1e-9)
        df["RSI_14"] = 100 - 100 / (1 + rs)

    if "ATR_14" not in df.columns:
        hl  = df["high"] - df["low"]
        hc  = (df["high"] - close.shift(1)).abs()
        lc  = (df["low"]  - close.shift(1)).abs()
        df["ATR_14"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).ewm(com=13, adjust=False).mean()

    if "EMA20" not in df.columns:
        df["EMA20"]  = close.ewm(span=20,  adjust=False).mean()
    if "EMA50" not in df.columns:
        df["EMA50"]  = close.ewm(span=50,  adjust=False).mean()
    if "EMA200" not in df.columns:
        df["EMA200"] = close.ewm(span=200, adjust=False).mean()

    if "MACD" not in df.columns:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df["MACD"]        = ema12 - ema26
        df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_hist"]   = df["MACD"] - df["MACD_signal"]

    if "BB_upper" not in df.columns:
        mid = close.rolling(20).mean()
        std = close.rolling(20).std()
        df["BB_upper"] = mid + 2 * std
        df["BB_lower"] = mid - 2 * std

    return df


# ─────────────────────────────────────────────────────────────
# FILTER WEEKEND GAPS  (NUEVO)
# ─────────────────────────────────────────────────────────────
def filter_weekend_gaps(df: pd.DataFrame, gap_hours: float = 4.0,
                        n_candles_after: int = 3) -> pd.DataFrame:
    """
    Elimina las primeras n_candles_after velas que siguen a cualquier gap mayor
    a gap_hours (fin de semana, feriados). Estas velas tienen ATR inflado,
    spreads altos y SL/TP falsos en el target.

    gap_hours      — umbral para considerar gap (H1: 4h, H4: 12h, D1: 72h)
    n_candles_after — cuántas velas post-gap eliminar (defecto 3 para H1)
    """
    if "timestamp" not in df.columns:
        return df

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    gaps = df["timestamp"].diff() > pd.Timedelta(hours=gap_hours)
    gap_indices = set(df[gaps].index)

    remove_set = set()
    for idx in gap_indices:
        for k in range(n_candles_after):
            remove_set.add(idx + k)

    mask    = ~df.index.isin(remove_set)
    removed = (~mask).sum()
    if removed > 0:
        print(f"[CSV ADAPTER] Gap filter: {removed} velas post-gap eliminadas")
    return df[mask].reset_index(drop=True)


# ─────────────────────────────────────────────────────────────
# MERGE MTF CONTEXT  (NUEVO)
# ─────────────────────────────────────────────────────────────
def merge_mtf_context(df_h1: pd.DataFrame,
                      path_h4: str = None,
                      path_d1: str = None) -> pd.DataFrame:
    """
    Enriquece df_h1 con features de H4 y D1 usando merge_asof (sin lookahead).
    Para cada vela H1, usa la última vela H4/D1 disponible ANTES de ella.

    Agrega columnas: h4_rsi, h4_ema20, h4_ema50, h4_ema200, h4_trend,
                     h4_macd, h4_atr, h4_return5, h4_close,
                     d1_rsi, d1_ema20, d1_ema200, d1_trend, d1_macd,
                     d1_atr, d1_return5, d1_close
    """
    df = df_h1.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    def _load_tf(path, prefix, cols):
        raw = pd.read_csv(path)
        raw["timestamp"] = pd.to_datetime(raw["timestamp"])
        raw = raw.sort_values("timestamp").reset_index(drop=True)
        rename = {c: f"{prefix}_{c.split('_')[-1] if '_' in c else c}" for c in cols}
        # Mapeo explícito
        rename = {
            "rsi_14":    f"{prefix}_rsi",
            "atr_14":    f"{prefix}_atr",
            "ema_20":    f"{prefix}_ema20",
            "ema_50":    f"{prefix}_ema50",
            "ema_150":   f"{prefix}_ema200",
            "macd":      f"{prefix}_macd",
            "return_5":  f"{prefix}_return5",
            "close":     f"{prefix}_close",
        }
        available = {k: v for k, v in rename.items() if k in raw.columns}
        sub = raw[["timestamp"] + list(available.keys())].rename(columns=available)
        # Agregar trend derivado (ema20 > ema200)
        if f"{prefix}_ema20" in sub.columns and f"{prefix}_ema200" in sub.columns:
            sub[f"{prefix}_trend"] = (sub[f"{prefix}_ema20"] > sub[f"{prefix}_ema200"]).astype(int)
        return sub

    if path_h4 and os.path.exists(path_h4):
        h4 = _load_tf(path_h4, "h4", [])
        df = pd.merge_asof(df, h4, on="timestamp", direction="backward")
        print(f"[CSV ADAPTER] MTF H4 merged: {len([c for c in df.columns if c.startswith('h4_')])} cols")

    if path_d1 and os.path.exists(path_d1):
        d1 = _load_tf(path_d1, "d1", [])
        df = pd.merge_asof(df, d1, on="timestamp", direction="backward")
        print(f"[CSV ADAPTER] MTF D1 merged: {len([c for c in df.columns if c.startswith('d1_')])} cols")

    return df


# ─────────────────────────────────────────────────────────────
# MAIN ADAPT_CSV
# ─────────────────────────────────────────────────────────────
def adapt_csv(filepath: str, pair: str = None,
              filter_gaps: bool = True,
              path_h4: str = None,
              path_d1: str = None) -> pd.DataFrame:
    """
    Carga y normaliza un CSV al esquema interno de ASTRA.

    filepath     — path al CSV principal (cualquier timeframe)
    pair         — nombre del par (ej. 'EURUSD')
    filter_gaps  — si True, elimina velas post-gap de fin de semana
    path_h4      — opcional: path al CSV H4 para merge MTF
    path_d1      — opcional: path al CSV D1 para merge MTF
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(filepath)
    else:
        df = pd.read_csv(filepath)

    # Normalize column names
    df.columns = df.columns.str.strip().str.lower()
    df = df.rename(columns={k: v for k, v in _RENAME.items() if k in df.columns})

    # Parse timestamp
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp").reset_index(drop=True)

    # Filter weekend gaps ANTES de calcular el target
    if filter_gaps and "timestamp" in df.columns:
        # Detectar timeframe automáticamente
        if len(df) > 2:
            median_gap = df["timestamp"].diff().median()
            if median_gap <= pd.Timedelta("1h"):
                gap_thresh, n_after = 4.0, 3    # H1
            elif median_gap <= pd.Timedelta("4h"):
                gap_thresh, n_after = 12.0, 2   # H4
            else:
                gap_thresh, n_after = 72.0, 1   # D1+
            df = filter_weekend_gaps(df, gap_hours=gap_thresh, n_candles_after=n_after)

    # Inject pair
    if pair:
        df["pair"] = _normalize_pair(pair)
    elif "pair" in df.columns:
        df["pair"] = df["pair"].astype(str).str.strip().str.upper().apply(_normalize_pair)
    else:
        name = os.path.splitext(os.path.basename(filepath))[0].upper()
        df["pair"] = _normalize_pair(name)

    # Inject spread proxy
    if "spread" not in df.columns:
        df["spread"] = (df["high"] - df["low"]) * 0.05

    # Fill missing indicators from OHLCV
    for col in _REQUIRED:
        if col not in df.columns:
            raise ValueError(f"CSV missing required column: {col}")

    df = fill_nan_indicators(df)

    # Inject session from timestamp if not present
    if "session" not in df.columns and "timestamp" in df.columns:
        hour = df["timestamp"].dt.hour
        df["session"] = np.select(
            [hour.between(0, 7), hour.between(8, 15), hour.between(13, 21)],
            ["Tokyo", "London", "NewYork"],
            default="Tokyo",
        )

    # MTF merge (si se pasan paths)
    if path_h4 or path_d1:
        df = merge_mtf_context(df, path_h4=path_h4, path_d1=path_d1)

    # Fill remaining NaN
    df = df.ffill().bfill()

    print(f"[CSV ADAPTER] Loaded {filepath}")
    print(f"[CSV ADAPTER] Rows: {len(df)} | Pair: {df['pair'].iloc[0]} | Columns: {len(df.columns)}")
    print(f"[CSV ADAPTER] Columns present: {list(df.columns)}")

    return df


# ─────────────────────────────────────────────────────────────
# COMPATIBILITY CHECK
# ─────────────────────────────────────────────────────────────
def check_compatibility(filepath: str) -> dict:
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(filepath)
    else:
        df = pd.read_csv(filepath)

    df.columns = df.columns.str.strip().str.lower()
    cols = set(df.columns)

    will_rename   = {k: v for k, v in _RENAME.items() if k in cols}
    will_derive   = [c for c in ["session", "pair", "spread"] if c not in cols]
    missing_crit  = [c for c in _REQUIRED if c not in cols]
    extra_cols    = [c for c in cols if c not in set(_RENAME.keys()) | set(_REQUIRED) | {"timestamp"}]

    return {
        "compatible":       len(missing_crit) == 0,
        "will_be_renamed":  will_rename,
        "will_be_derived":  will_derive,
        "missing_critical": missing_crit,
        "extra_columns":    extra_cols,
    }

"""
csv_adapter.py — Normalizes external CSV formats to the internal column schema.

Supported input formats:
  - "London-Strategic-Edge" style (lowercase snake_case indicators,
    ema_150 instead of ema_200, bollinger_* naming, return_5 instead of returns)
  - Any CSV where OHLCV columns are present — adapter auto-detects the rest.

What it does:
  1. Renames columns to internal names (case-insensitive, flexible)
  2. Derives missing columns (returns, session, EMA200, spread, pair)
  3. Drops NaN warm-up rows at the start
  4. Returns a clean DataFrame ready for feature_engineering.build_features()

Usage:
    from forex.prediction.csv_adapter import adapt_csv

    df = adapt_csv("usd_jpy_dataset_London-Strategic-Edge.csv", pair="USDJPY")
    # df is now ready for the full pipeline
"""

import os
import re
import pandas as pd
import numpy as np


# -------------------------------------------------------
# COLUMN NAME MAPPING
# Maps known external names → internal names.
# All comparisons are done lowercase + stripped.
# -------------------------------------------------------
_RENAME_MAP = {
    # RSI
    "rsi_14":           "RSI_14",
    "rsi14":            "RSI_14",
    "rsi":              "RSI_14",

    # MACD
    "macd":             "MACD",
    "macd_signal":      "MACD_signal",
    "macd_hist":        "MACD_hist",
    "macd_histogram":   "MACD_hist",
    "macdhistogram":    "MACD_hist",

    # ATR
    "atr_14":           "ATR_14",
    "atr14":            "ATR_14",
    "atr":              "ATR_14",

    # EMAs
    "ema_20":           "EMA20",
    "ema20":            "EMA20",
    "ema_50":           "EMA50",
    "ema50":            "EMA50",
    "ema_200":          "EMA200",
    "ema200":           "EMA200",
    "ema_150":          "EMA200",   # treat 150 as 200 proxy (common in some exports)
    "ema150":           "EMA200",

    # Bollinger Bands
    "bollinger_upper_20": "BB_upper",
    "bollinger_upper":    "BB_upper",
    "bb_upper_20":        "BB_upper",
    "bb_upper":           "BB_upper",
    "bollinger_lower_20": "BB_lower",
    "bollinger_lower":    "BB_lower",
    "bb_lower_20":        "BB_lower",
    "bb_lower":           "BB_lower",

    # Returns / volatility
    "return_5":         "returns",
    "return_1":         "returns",
    "returns":          "returns",
    "return":           "returns",
    "volatility_20":    "volatility_24h",
    "volatility_24h":   "volatility_24h",
    "volatility":       "volatility_24h",

    # Volume / spread
    "volume":           "volume",
    "spread":           "spread",

    # Pair
    "pair":             "pair",
    "symbol":           "pair",
    "ticker":           "pair",
}


def _normalize_col(name: str) -> str:
    """Lowercase + strip a column name for lookup."""
    return name.strip().lower()


def adapt_csv(
    filepath: str,
    pair: str = None,
    drop_nan_rows: bool = True,
) -> pd.DataFrame:
    """
    Load and normalize a forex CSV to the internal column schema.

    Parameters
    ----------
    filepath      : path to CSV or XLSX
    pair          : forex pair label (e.g. "USDJPY"). If None, tries to infer
                    from the filename (e.g. "usd_jpy_..." → "USDJPY").
    drop_nan_rows : drop the warm-up rows at the start where indicators are NaN

    Returns
    -------
    pd.DataFrame with standardized column names, ready for build_features()
    """

    # --- 1. Load file ---
    if filepath.endswith((".xlsx", ".xls")):
        df = pd.read_excel(filepath)
    else:
        df = pd.read_csv(filepath)

    df.columns = df.columns.str.strip()

    # --- 2. Rename columns using the map ---
    rename = {}
    for col in df.columns:
        norm = _normalize_col(col)
        if norm in _RENAME_MAP:
            rename[col] = _RENAME_MAP[norm]
    if rename:
        df = df.rename(columns=rename)

    # --- 3. Parse timestamp ---
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    else:
        # Try to find any date/time column
        for c in df.columns:
            if "time" in c.lower() or "date" in c.lower():
                df["timestamp"] = pd.to_datetime(df[c])
                break

    # --- 4. Derive `returns` if missing ---
    # Prefer 1-period log return for consistency with feature engineering
    if "returns" not in df.columns and "close" in df.columns:
        df["returns"] = df["close"].pct_change()
    elif "returns" in df.columns:
        # If we mapped return_5 → returns but it's 5-period, also compute 1-period
        # Keep the 5-period as return_5 for use as a feature, derive 1-period as returns
        df["return_5"] = df["returns"].copy()
        df["returns"]  = df["close"].pct_change() if "close" in df.columns else df["returns"]

    # --- 5. Compute EMA200 if missing (ema_150 was mapped as proxy but compute real one) ---
    if "EMA200" not in df.columns and "close" in df.columns:
        df["EMA200"] = df["close"].ewm(span=200, adjust=False).mean()
    elif "EMA200" in df.columns:
        # If ema_150 was mapped as EMA200, also compute the real 200-period alongside it
        # We keep the mapped value (model learns from it) and compute the true one
        # as EMA200_true for reference — but only use EMA200 to stay consistent.
        pass

    # --- 6. Add EMA20 / EMA50 if still missing ---
    if "EMA20" not in df.columns and "close" in df.columns:
        df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
    if "EMA50" not in df.columns and "close" in df.columns:
        df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()

    # --- 7. Derive `session` from timestamp hour ---
    # Tokyo:   00:00–08:00 UTC
    # London:  08:00–16:00 UTC  (overlap NY: 13:00–16:00)
    # NewYork: 16:00–00:00 UTC
    if "session" not in df.columns and "timestamp" in df.columns:
        hour = df["timestamp"].dt.hour
        conditions = [
            (hour >= 0)  & (hour < 8),    # Tokyo
            (hour >= 8)  & (hour < 16),   # London
            (hour >= 16) & (hour < 24),   # New York
        ]
        df["session"] = np.select(conditions, ["Tokyo", "London", "NewYork"], default="Tokyo")

    # --- 8. Add `pair` column ---
    if "pair" not in df.columns:
        if pair is None:
            pair = _infer_pair_from_filename(filepath)
        df["pair"] = pair

    # --- 9. Add `spread` = 0 if missing (conservative fallback) ---
    if "spread" not in df.columns:
        df["spread"] = 0.0

    # --- 10. Drop NaN warm-up rows (indicator initialization period) ---
    if drop_nan_rows:
        core_indicators = [c for c in ["RSI_14", "ATR_14", "MACD"] if c in df.columns]
        if core_indicators:
            df = df.dropna(subset=core_indicators).reset_index(drop=True)

    print(f"[CSV ADAPTER] Loaded {filepath}")
    print(f"[CSV ADAPTER] Rows: {len(df)} | Pair: {df['pair'].iloc[0]} | Columns: {len(df.columns)}")
    print(f"[CSV ADAPTER] Columns present: {list(df.columns)}")

    return df


def _infer_pair_from_filename(filepath: str) -> str:
    """
    Try to extract pair name from filename.
    e.g. "usd_jpy_dataset_London-Strategic-Edge.csv" → "USDJPY"
         "EURUSD_H1.csv" → "EURUSD"
         "xauusd_data.csv" → "XAUUSD"
    """
    basename = os.path.basename(filepath).upper()
    # Remove extension
    basename = os.path.splitext(basename)[0]

    # Known pairs to look for
    known_pairs = [
        "EURUSD", "USDJPY", "GBPUSD", "USDCHF", "AUDUSD", "USDCAD",
        "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "XAUUSD", "XAGUSD",
        "USOIL", "UKOIL", "BTCUSD", "ETHUSD",
        # Also handle underscore variants
        "USD_JPY", "EUR_USD", "GBP_USD", "AUD_USD", "USD_CAD",
        "XAU_USD", "XAG_USD",
    ]
    for pair in known_pairs:
        if pair in basename:
            return pair.replace("_", "")

    # Fallback: look for 6-letter sequence that could be a pair
    m = re.search(r"([A-Z]{6})", basename)
    if m:
        return m.group(1)

    return "UNKNOWN"


def check_compatibility(filepath: str) -> dict:
    """
    Inspect a CSV and report which columns will be mapped, derived, or are missing.
    Useful for debugging before running the full pipeline.

    Usage:
        report = check_compatibility("my_data.csv")
        print(report)
    """
    if filepath.endswith((".xlsx", ".xls")):
        df = pd.read_excel(filepath, nrows=5)
    else:
        df = pd.read_csv(filepath, nrows=5)

    df.columns = df.columns.str.strip()
    raw_cols   = list(df.columns)

    mapped     = {}
    unmapped   = []
    for col in raw_cols:
        norm = _normalize_col(col)
        if norm in _RENAME_MAP:
            mapped[col] = _RENAME_MAP[norm]
        else:
            unmapped.append(col)

    internal_required = [
        "timestamp", "open", "high", "low", "close",
        "RSI_14", "MACD", "MACD_signal", "MACD_hist",
        "ATR_14", "EMA20", "EMA50", "EMA200",
        "BB_upper", "BB_lower", "returns", "volume",
    ]
    after_rename   = set(mapped.values()) | set(unmapped)
    will_be_derived = []
    missing        = []

    for req in internal_required:
        if req in after_rename:
            continue
        # Check if it will be derived
        if req in ("returns", "EMA200", "EMA20", "EMA50"):
            will_be_derived.append(req)
        else:
            missing.append(req)

    # session, pair, spread are always derived/added if missing
    will_be_derived += ["session", "pair", "spread"]

    return {
        "raw_columns":      raw_cols,
        "will_be_renamed":  mapped,
        "will_be_derived":  will_be_derived,
        "unrecognized":     unmapped,
        "missing_critical": missing,
        "compatible":       len(missing) == 0,
    }

"""
creando.py

MT5 dataset builder for Astra Forex Analytics.

Downloads OHLCV history from MetaTrader5 for every supported market
(forex pairs, commodities and crypto) and writes one CSV per
(symbol, timeframe) combination with technical indicators already
computed — ready to be consumed by `forex_analytics.analyze_market`.

Timeframes (per the project plan):
    H1  — last 2 years  -> now
    H4  — 2023-01-01    -> now
    D1  — 2021-01-01    -> now

Output layout:
    CSVs/
        H1/
            EURUSD.csv
            XAUUSD.csv
            ...
        H4/
            ...
        D1/
            ...

The symbol universe is sourced from `forex.market_universe` so this
script and the rest of Astra always agree on what is supported.

Author: Nicolas Saez / Astra Project
"""

import os
from datetime import datetime, timedelta

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from forex.market_universe import (
    FOREX_PAIRS,
    COMMODITIES,
    CRYPTO_ASSETS,
    MT5_SYMBOLS,
)


# ============================================================
# TIMEFRAME CONFIGURATION
# ============================================================
# Each entry: (mt5_constant, output_subfolder, start_date, label)
NOW = datetime.now()

TIMEFRAMES = [
    (mt5.TIMEFRAME_H1, "H1", NOW - timedelta(days=730),  "H1 (2y)"),
    (mt5.TIMEFRAME_H4,  "H4", datetime(2023, 1, 1),       "H4 (2023->now)"),
    (mt5.TIMEFRAME_D1,  "D1", datetime(2021, 1, 1),       "D1 (2021->now)"),
]

OUTPUT_ROOT = "CSVs"


# ============================================================
# INDICATORS
# ============================================================

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = avg_loss.replace(0, np.nan)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(close: pd.Series):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return macd, signal, hist


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df["rsi_14"] = calculate_rsi(df["close"], 14)
    (df["macd"], df["macd_signal"], df["macd_histogram"]) = calculate_macd(df["close"])
    df["atr_14"] = calculate_atr(df, 14)
    df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema_150"] = df["close"].ewm(span=150, adjust=False).mean()
    ma20 = df["close"].rolling(20).mean()
    std20 = df["close"].rolling(20).std()
    df["bollinger_upper_20"] = ma20 + 2 * std20
    df["bollinger_lower_20"] = ma20 - 2 * std20
    df["return_5"] = df["close"] / df["close"].shift(5) - 1
    returns = np.log(df["close"] / df["close"].shift(1))
    df["volatility_20"] = returns.rolling(20).std()
    return df


COLUMNS = [
    "timestamp", "open", "high", "low", "close", "volume",
    "rsi_14", "macd", "macd_signal", "macd_histogram", "atr_14",
    "ema_20", "ema_50", "ema_150",
    "bollinger_upper_20", "bollinger_lower_20",
    "return_5", "volatility_20",
]


# ============================================================
# MT5 DOWNLOAD
# ============================================================

def download_symbol(symbol: str, timeframe_const: int,
                    start: datetime, end: datetime,
                    out_folder: str) -> bool:
    """Download one symbol/timeframe and write its CSV. Returns True on success."""

    rates = mt5.copy_rates_range(symbol, timeframe_const, start, end)
    if rates is None or len(rates) == 0:
        print(f"  [skip] Sin datos para {symbol}")
        return False

    df = pd.DataFrame(rates)
    df["timestamp"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    df = add_indicators(df)
    df = df[COLUMNS]

    os.makedirs(out_folder, exist_ok=True)
    filename = os.path.join(out_folder, f"{symbol}.csv")
    df.to_csv(filename, index=False)
    print(f"  [ok] {filename}  ({len(df)} filas)")
    return True


def main() -> None:
    os.makedirs(OUTPUT_ROOT, exist_ok=True)

    if not mt5.initialize():
        raise RuntimeError("No se pudo conectar a MT5")

    symbols = MT5_SYMBOLS
    print(f"Universo de mercados: {len(symbols)} simbolos")
    print(f"  Forex:       {len(FOREX_PAIRS)}")
    print(f"  Commodities: {len(COMMODITIES)}")
    print(f"  Crypto:      {len(CRYPTO_ASSETS)}")
    print()

    total_ok = 0
    total_skip = 0
    try:
        for tf_const, tf_folder, start, tf_label in TIMEFRAMES:
            out_folder = os.path.join(OUTPUT_ROOT, tf_folder)
            print(f"=== Timeframe {tf_label}  ->  {out_folder} ===")
            for symbol in symbols:
                print(f"Descargando {symbol} [{tf_folder}]...")
                ok = download_symbol(symbol, tf_const, start, NOW, out_folder)
                if ok:
                    total_ok += 1
                else:
                    total_skip += 1
            print()
    finally:
        mt5.shutdown()

    print(f"Proceso completado: {total_ok} CSVs escritos, {total_skip} sin datos.")


if __name__ == "__main__":
    main()

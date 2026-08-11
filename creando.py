"""
creando.py — Dataset builder para ASTRA Forex

MODO MT5 (Windows con MetaTrader5 instalado):
  Descarga datos OHLCV directo desde el terminal MT5.
  python creando.py

MODO YFINANCE (cualquier OS, sin MT5):
  Descarga datos via Yahoo Finance (yfinance).
  python creando.py --modo yfinance
  python creando.py --modo yfinance --pares EURUSD GBPUSD XAUUSD
  python creando.py --modo yfinance --timeframe H1   (H1, H4, D1)

Los CSVs se generan en:
  CSVs/H1/<SYMBOL>.csv
  CSVs/H4/<SYMBOL>.csv
  CSVs/D1/<SYMBOL>.csv

Con todos los indicadores técnicos necesarios para el pipeline de predicción
(rsi_14, macd, macd_signal, macd_histogram, atr_14, ema_20, ema_50, ema_150,
bollinger_upper_20, bollinger_lower_20, return_5, volatility_20).

Author: Nicolas Saez / Astra Project
"""

import os
import sys
import argparse
import warnings
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── MT5 (opcional, solo Windows) ─────────────────────────────────────────────
try:
    import MetaTrader5 as mt5
    HAS_MT5 = True
except ImportError:
    HAS_MT5 = False
    mt5 = None

# ── yfinance (fallback multiplataforma) ──────────────────────────────────────
try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False
    yf = None

from forex.market_universe import FOREX_PAIRS
from forex.data.yahoo_provider import (
    FOREX_TICKER_MAP as YFINANCE_TICKER_MAP,
    to_yahoo_ticker as to_yfinance_ticker,
)

MT5_SYMBOLS = sorted(pair.replace("/", "") for pair in FOREX_PAIRS)

OUTPUT_ROOT = "CSVs"
NOW = datetime.now()


# ============================================================
# TIMEFRAME CONFIG
# ============================================================

YF_TIMEFRAME_CONFIG = {
    # (yf_interval, yf_period_or_start, output_subfolder, label)
    "H1": ("1h",  "730d",  "H1", "H1 (2 años)"),
    "H4": ("1h",  "730d",  "H4", "H4 simulado desde H1 (2 años)"),
    "D1": ("1d",  "3650d", "D1", "D1 (10 años)"),
}

MT5_TIMEFRAME_CONFIG = None  # se define solo si HAS_MT5


def _get_mt5_timeframes():
    return [
        (mt5.TIMEFRAME_H1, "H1", NOW - timedelta(days=730),  "H1 (2y)"),
        (mt5.TIMEFRAME_H4, "H4", datetime(2023, 1, 1),       "H4 (2023->now)"),
        (mt5.TIMEFRAME_D1, "D1", datetime(2021, 1, 1),       "D1 (2021->now)"),
    ]


# ============================================================
# INDICATORS
# ============================================================

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = avg_loss.replace(0, np.nan)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(close: pd.Series):
    ema12   = close.ewm(span=12, adjust=False).mean()
    ema26   = close.ewm(span=26, adjust=False).mean()
    macd    = ema12 - ema26
    signal  = macd.ewm(span=9, adjust=False).mean()
    hist    = macd - signal
    return macd, signal, hist


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl  = df["high"] - df["low"]
    hc  = (df["high"] - df["close"].shift()).abs()
    lc  = (df["low"]  - df["close"].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["rsi_14"]             = calculate_rsi(df["close"], 14)
    macd, sig, hist          = calculate_macd(df["close"])
    df["macd"]               = macd
    df["macd_signal"]        = sig
    df["macd_histogram"]     = hist
    df["atr_14"]             = calculate_atr(df, 14)
    df["ema_20"]             = df["close"].ewm(span=20,  adjust=False).mean()
    df["ema_50"]             = df["close"].ewm(span=50,  adjust=False).mean()
    df["ema_150"]            = df["close"].ewm(span=150, adjust=False).mean()
    ma20                     = df["close"].rolling(20).mean()
    std20                    = df["close"].rolling(20).std()
    df["bollinger_upper_20"] = ma20 + 2 * std20
    df["bollinger_lower_20"] = ma20 - 2 * std20
    df["return_5"]           = df["close"] / df["close"].shift(5) - 1
    log_ret                  = np.log(df["close"] / df["close"].shift(1))
    df["volatility_20"]      = log_ret.rolling(20).std()
    return df


OUTPUT_COLUMNS = [
    "timestamp", "open", "high", "low", "close", "volume",
    "rsi_14", "macd", "macd_signal", "macd_histogram", "atr_14",
    "ema_20", "ema_50", "ema_150",
    "bollinger_upper_20", "bollinger_lower_20",
    "return_5", "volatility_20",
]


# ============================================================
# VALIDATION
# ============================================================

def validate_ohlcv(df: pd.DataFrame, symbol: str = "") -> tuple:
    errors = []
    if len(df) < 50:
        errors.append(f"  ❌ Muy pocas filas: {len(df)} (mínimo 50)")
    invalid_hl = (df["high"] < df["low"]).sum()
    if invalid_hl > 0:
        errors.append(f"  ❌ {invalid_hl} filas con High < Low")
    nan_core = df[["open", "high", "low", "close"]].isna().sum().sum()
    if nan_core > 0:
        errors.append(f"  ❌ {nan_core} NaN en OHLC")
    is_valid = not any(e.startswith("  ❌") for e in errors)
    return is_valid, errors


# ============================================================
# SESSION LABELS
# ============================================================

def add_session(df: pd.DataFrame) -> pd.DataFrame:
    if "timestamp" not in df.columns:
        df["session"] = "Unknown"
        return df
    hour = pd.to_datetime(df["timestamp"]).dt.hour
    conditions = [
        (hour >= 0)  & (hour < 8),
        (hour >= 8)  & (hour < 16),
        (hour >= 16) & (hour < 24),
    ]
    df["session"] = np.select(conditions, ["Tokyo", "London", "NewYork"], default="Tokyo")
    return df


# ============================================================
# RESAMPLE H1 → H4
# ============================================================

def resample_h1_to_h4(df: pd.DataFrame) -> pd.DataFrame:
    """Agrupa velas H1 en H4."""
    df2 = df.copy()
    df2["timestamp"] = pd.to_datetime(df2["timestamp"])
    df2 = df2.set_index("timestamp")
    ohlcv = df2[["open", "high", "low", "close", "volume"]].resample("4h").agg({
        "open":   "first",
        "high":   "max",
        "low":    "min",
        "close":  "last",
        "volume": "sum",
    }).dropna()
    ohlcv = ohlcv.reset_index()
    ohlcv = ohlcv.rename(columns={"timestamp": "timestamp"})
    return ohlcv


# ============================================================
# YFINANCE DOWNLOAD
# ============================================================

def _yf_download_ohlcv(ticker_str: str, interval: str, period: str) -> pd.DataFrame:
    """Descarga OHLCV desde Yahoo Finance y normaliza columnas."""
    t  = yf.Ticker(ticker_str)
    df = t.history(period=period, interval=interval, auto_adjust=True)
    if df.empty:
        return pd.DataFrame()
    df = df.reset_index()
    # Normalizar nombre de columna de tiempo
    time_col = "Datetime" if "Datetime" in df.columns else "Date"
    df = df.rename(columns={
        time_col:  "timestamp",
        "Open":    "open",
        "High":    "high",
        "Low":     "low",
        "Close":   "close",
        "Volume":  "volume",
    })
    # Quitar timezone
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
    keep = ["timestamp", "open", "high", "low", "close", "volume"]
    df = df[[c for c in keep if c in df.columns]].copy()
    if "volume" not in df.columns:
        df["volume"] = 0
    df = df.dropna(subset=["open", "high", "low", "close"])
    return df


def download_yfinance(display_name: str, timeframe: str, out_folder: str) -> bool:
    """
    Descarga un par/instrumento via yfinance y guarda el CSV con indicadores.
    Retorna True si fue exitoso.
    """
    ticker_str = to_yfinance_ticker(display_name)
    if ticker_str is None:
        print(f"  [skip] {display_name} — sin ticker yfinance disponible")
        return False

    cfg = YF_TIMEFRAME_CONFIG.get(timeframe)
    if cfg is None:
        print(f"  [skip] Timeframe desconocido: {timeframe}")
        return False

    yf_interval, yf_period, out_sub, label = cfg

    try:
        if timeframe == "H4":
            # Descargamos H1 y resampleamos a H4
            raw = _yf_download_ohlcv(ticker_str, "1h", yf_period)
            if raw.empty:
                print(f"  [skip] {display_name} ({ticker_str}) — sin datos H1 para H4")
                return False
            raw = resample_h1_to_h4(raw)
        else:
            raw = _yf_download_ohlcv(ticker_str, yf_interval, yf_period)

        if raw.empty or len(raw) < 50:
            print(f"  [skip] {display_name} ({ticker_str}) — datos insuficientes ({len(raw)} filas)")
            return False

        is_valid, errors = validate_ohlcv(raw, display_name)
        for e in errors:
            print(e)
        if not is_valid:
            return False

        df = add_indicators(raw)
        df = add_session(df)

        # Guardar solo columnas definidas (+ session)
        save_cols = [c for c in OUTPUT_COLUMNS + ["session"] if c in df.columns]
        df = df[save_cols].dropna(subset=["rsi_14", "atr_14"])  # drop warm-up rows

        if len(df) < 50:
            print(f"  [skip] {display_name} — muy pocas filas tras indicadores ({len(df)})")
            return False

        os.makedirs(out_folder, exist_ok=True)
        # Nombre de archivo = símbolo MT5 limpio (ej. EURUSD.csv)
        file_symbol = display_name.replace("/", "").replace(" ", "_").upper()
        filepath = os.path.join(out_folder, f"{file_symbol}.csv")
        df.to_csv(filepath, index=False)
        print(f"  [ok] {filepath}  ({len(df)} filas)")
        return True

    except Exception as e:
        print(f"  [error] {display_name} ({ticker_str}): {e}")
        return False


# ============================================================
# MT5 DOWNLOAD
# ============================================================

def download_mt5_symbol(symbol: str, timeframe_const: int,
                        start: datetime, end: datetime,
                        out_folder: str) -> bool:
    rates = mt5.copy_rates_range(symbol, timeframe_const, start, end)
    if rates is None or len(rates) == 0:
        print(f"  [skip] Sin datos para {symbol}")
        return False

    df = pd.DataFrame(rates)
    df["timestamp"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})

    is_valid, errors = validate_ohlcv(df, symbol)
    for e in errors:
        print(e)
    if not is_valid:
        return False

    df = add_indicators(df)
    df = add_session(df)
    save_cols = [c for c in OUTPUT_COLUMNS + ["session"] if c in df.columns]
    df = df[save_cols].dropna(subset=["rsi_14", "atr_14"])

    os.makedirs(out_folder, exist_ok=True)
    filepath = os.path.join(out_folder, f"{symbol}.csv")
    df.to_csv(filepath, index=False)
    print(f"  [ok] {filepath}  ({len(df)} filas)")
    return True


# ============================================================
# MAIN — MODO MT5
# ============================================================

def run_mt5(timeframes_arg: str = "H1,H4,D1"):
    if not HAS_MT5:
        print("❌ MetaTrader5 no instalado. Usa --modo yfinance")
        sys.exit(1)
    if not mt5.initialize():
        print("❌ No se pudo conectar a MT5. ¿Está ejecutándose?")
        sys.exit(1)

    tf_list = _get_mt5_timeframes()
    requested = [t.strip() for t in timeframes_arg.split(",")]
    tf_list = [(c, f, s, l) for c, f, s, l in tf_list if f in requested]

    symbols = MT5_SYMBOLS
    print(f"\n[MT5] Universo: {len(symbols)} símbolos")
    total_ok = total_skip = 0
    try:
        for tf_const, tf_folder, start, tf_label in tf_list:
            out_folder = os.path.join(OUTPUT_ROOT, tf_folder)
            print(f"\n=== {tf_label} → {out_folder} ===")
            for sym in symbols:
                ok = download_mt5_symbol(sym, tf_const, start, NOW, out_folder)
                total_ok += ok; total_skip += not ok
    finally:
        mt5.shutdown()
    print(f"\n✅ MT5 completo: {total_ok} CSVs generados, {total_skip} omitidos.")


# ============================================================
# MAIN — MODO YFINANCE
# ============================================================

def run_yfinance(timeframes_arg: str = "H1", pairs_arg: list = None):
    if not HAS_YF:
        print("❌ yfinance no instalado. Ejecuta: pip install yfinance")
        sys.exit(1)

    requested_tf = [t.strip() for t in timeframes_arg.split(",")]

    # Si el usuario pasó pares específicos, usarlos; si no, todos los soportados
    if pairs_arg:
        candidates = []
        from forex.market_universe import normalize_symbol, is_supported_market
        for p in pairs_arg:
            norm = normalize_symbol(p)
            if not is_supported_market(norm):
                print(f"  [warn] '{p}' no está en el universo de ASTRA, intentando igual...")
            candidates.append(norm if is_supported_market(norm) else p.upper())
    else:
        # Todos los pares con ticker yfinance disponible
        candidates = list(YFINANCE_TICKER_MAP.keys())

    total_ok = total_skip = 0

    for tf in requested_tf:
        cfg = YF_TIMEFRAME_CONFIG.get(tf)
        if cfg is None:
            print(f"[warn] Timeframe '{tf}' desconocido. Opciones: H1, H4, D1")
            continue
        _, _, out_sub, label = cfg
        out_folder = os.path.join(OUTPUT_ROOT, out_sub)
        print(f"\n=== yfinance {label} → {out_folder} ===")
        print(f"    {len(candidates)} instrumentos a descargar\n")

        for display_name in candidates:
            ok = download_yfinance(display_name, tf, out_folder)
            total_ok   += ok
            total_skip += not ok

    print(f"\n✅ yfinance completo: {total_ok} CSVs generados, {total_skip} omitidos.")
    print(f"   Carpeta: {os.path.abspath(OUTPUT_ROOT)}/")


# ============================================================
# CLI
# ============================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="ASTRA — Generador de datasets Forex/Commodities/Crypto",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument(
        "--modo", choices=["mt5", "yfinance"], default=None,
        help=(
            "mt5      : descarga via MetaTrader5 (solo Windows)\n"
            "yfinance : descarga via Yahoo Finance (cualquier OS, sin MT5)\n"
            "Si se omite, auto-detecta (MT5 si disponible, yfinance si no)"
        ),
    )
    p.add_argument(
        "--timeframe", default="H1",
        help="Timeframes separados por coma: H1, H4, D1  (default: H1)",
    )
    p.add_argument(
        "--pares", nargs="*", default=None,
        help=(
            "Pares/instrumentos a descargar (solo modo yfinance).\n"
            "Ejemplos: EURUSD GBPUSD XAUUSD BTCUSD\n"
            "Si se omite, descarga todos los soportados."
        ),
    )
    return p.parse_args()


def main():
    args = parse_args()

    # Auto-detect modo si no se especificó
    modo = args.modo
    if modo is None:
        modo = "mt5" if HAS_MT5 else "yfinance"
        print(f"[auto] Modo detectado: {modo}")

    print(f"\n{'='*60}")
    print(f"  ASTRA — Dataset Builder")
    print(f"  Modo      : {modo.upper()}")
    print(f"  Timeframe : {args.timeframe}")
    if args.pares:
        print(f"  Pares     : {', '.join(args.pares)}")
    print(f"  Salida    : {os.path.abspath(OUTPUT_ROOT)}/")
    print(f"{'='*60}\n")

    if modo == "mt5":
        run_mt5(args.timeframe)
    else:
        run_yfinance(args.timeframe, args.pares)


if __name__ == "__main__":
    main()

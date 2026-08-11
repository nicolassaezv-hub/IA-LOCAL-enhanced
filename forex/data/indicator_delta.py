"""
VI.6.B — Indicator Delta Calculator
Recalcula solo los indicadores de las últimas K filas afectadas por una vela nueva.
Evita reconstruir los N indicadores completos por cada tick.
"""
import pandas as pd
import numpy as np


def _safe_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _safe_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


def _safe_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def _safe_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _safe_ema(close, fast)
    ema_slow = _safe_ema(close, slow)
    macd = ema_fast - ema_slow
    macd_signal = _safe_ema(macd, signal)
    macd_hist = macd - macd_signal
    return macd, macd_signal, macd_hist


def _safe_bb(close: pd.Series, period: int = 20, std_dev: float = 2.0):
    sma = close.rolling(window=period, min_periods=1).mean()
    std = close.rolling(window=period, min_periods=1).std().fillna(0)
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, lower


INDICATOR_MIN_HISTORY = {
    "RSI_14": 14,
    "MACD": 26,
    "MACD_signal": 26 + 9,
    "MACD_hist": 26 + 9,
    "ATR_14": 14,
    "EMA20": 20,
    "EMA50": 50,
    "EMA200": 200,
    "BB_upper": 20,
    "BB_lower": 20,
    "returns": 2,
    "volatility_24h": 24,
}

# Delta recalculation uses five extra observations as numerical context.  Keep
# this distinct from the minimum history used to validate indicator warm-up.
_INDICATOR_CONTEXT_BUFFER = 5
_INDICATOR_WINDOWS = dict(INDICATOR_MIN_HISTORY)


def recalculate_tail_indicators(df: pd.DataFrame, k: int = 60) -> pd.DataFrame:
    """
    Recalcula los indicadores de las últimas k filas del DataFrame.
    Usa un contexto adicional para que los indicadores con ventana larga sean precisos.

    df: DataFrame completo con columnas OHLCV
    k: número de filas al final a recalcular
    Retorna el DataFrame con los indicadores de la cola actualizados.
    """
    # Providers return OHLCV-only frames. Materialize the complete production
    # indicator contract before the existing formulas recalculate the tail.
    for column in INDICATOR_MIN_HISTORY:
        if column not in df.columns:
            df[column] = np.nan

    if len(df) < 2:
        return df

    # Contexto mínimo para que la recalculación sea precisa
    max_window = max(_INDICATOR_WINDOWS.values()) + _INDICATOR_CONTEXT_BUFFER
    context_rows = min(len(df), k + max_window)
    tail_start_idx = len(df) - context_rows

    ctx = df.iloc[tail_start_idx:].copy()
    close = ctx["close"]
    high = ctx["high"]
    low = ctx["low"]

    # Recalcular todos los indicadores sobre el contexto
    if "RSI_14" in df.columns:
        ctx["RSI_14"] = _safe_rsi(close, 14)
    if "EMA20" in df.columns:
        ctx["EMA20"] = _safe_ema(close, 20)
    if "EMA50" in df.columns:
        ctx["EMA50"] = _safe_ema(close, 50)
    if "EMA200" in df.columns:
        ctx["EMA200"] = _safe_ema(close, 200)
    if "ATR_14" in df.columns:
        ctx["ATR_14"] = _safe_atr(high, low, close, 14)
    if "MACD" in df.columns:
        m, ms, mh = _safe_macd(close)
        ctx["MACD"] = m
        if "MACD_signal" in df.columns:
            ctx["MACD_signal"] = ms
        if "MACD_hist" in df.columns:
            ctx["MACD_hist"] = mh
    if "BB_upper" in df.columns:
        bu, bl = _safe_bb(close)
        ctx["BB_upper"] = bu
        if "BB_lower" in df.columns:
            ctx["BB_lower"] = bl
    if "returns" in df.columns:
        ctx["returns"] = close.pct_change().fillna(0)
    if "volatility_24h" in df.columns:
        ctx["volatility_24h"] = close.pct_change().rolling(24, min_periods=1).std().fillna(0)

    # Sólo actualizar las últimas k filas del df original
    actual_tail = min(k, context_rows)
    tail_slice = ctx.iloc[-actual_tail:]
    df.iloc[-actual_tail:] = tail_slice.values

    return df

"""
forex/indicators.py — Technical Indicators
Provides CCI, MFI, ROC and other technical indicators for forex analysis.
"""

import numpy as np
import pandas as pd


def compute_cci(high, low, close, period=20):
    """
    Compute the Commodity Channel Index (CCI).
    
    Args:
        high: Series of high prices
        low: Series of low prices
        close: Series of close prices
        period: Period for calculation (default: 20)
    
    Returns:
        Series with CCI values
    """
    if isinstance(high, pd.Series):
        high = high.values
    if isinstance(low, pd.Series):
        low = low.values
    if isinstance(close, pd.Series):
        close = close.values
    
    typical_price = (high + low + close) / 3
    
    cci = []
    for i in range(len(typical_price)):
        if i < period - 1:
            cci.append(np.nan)
        else:
            ma = np.mean(typical_price[i - period + 1:i + 1])
            mad = np.mean(np.abs(typical_price[i - period + 1:i + 1] - ma))
            if mad != 0:
                cci.append((typical_price[i] - ma) / (0.015 * mad))
            else:
                cci.append(0)
    
    return pd.Series(cci, index=pd.RangeIndex(len(cci)))


def compute_mfi(high, low, close, volume, period=14):
    """
    Compute the Money Flow Index (MFI).
    
    Args:
        high: Series of high prices
        low: Series of low prices
        close: Series of close prices
        volume: Series of volumes
        period: Period for calculation (default: 14)
    
    Returns:
        Series with MFI values
    """
    if isinstance(high, pd.Series):
        high = high.values
    if isinstance(low, pd.Series):
        low = low.values
    if isinstance(close, pd.Series):
        close = close.values
    if isinstance(volume, pd.Series):
        volume = volume.values
    
    typical_price = (high + low + close) / 3
    money_flow = typical_price * volume
    
    positive_flow = []
    negative_flow = []
    
    for i in range(len(typical_price)):
        if i == 0:
            positive_flow.append(0)
            negative_flow.append(0)
        elif typical_price[i] > typical_price[i - 1]:
            positive_flow.append(money_flow[i])
            negative_flow.append(0)
        else:
            positive_flow.append(0)
            negative_flow.append(money_flow[i])
    
    positive_flow = np.array(positive_flow)
    negative_flow = np.array(negative_flow)
    
    mfi = []
    for i in range(len(typical_price)):
        if i < period - 1:
            mfi.append(np.nan)
        else:
            pos_sum = np.sum(positive_flow[i - period + 1:i + 1])
            neg_sum = np.sum(negative_flow[i - period + 1:i + 1])
            if pos_sum + neg_sum != 0:
                mfi.append(100 * pos_sum / (pos_sum + neg_sum))
            else:
                mfi.append(50)
    
    return pd.Series(mfi, index=pd.RangeIndex(len(mfi)))


def compute_roc(close, period=10):
    """
    Compute the Rate of Change (ROC).
    
    Args:
        close: Series of close prices
        period: Period for calculation (default: 10)
    
    Returns:
        Series with ROC values
    """
    if isinstance(close, pd.Series):
        close = close.values
    
    roc = []
    for i in range(len(close)):
        if i < period:
            roc.append(np.nan)
        else:
            roc.append(((close[i] - close[i - period]) / close[i - period]) * 100)
    
    return pd.Series(roc, index=pd.RangeIndex(len(roc)))


def compute_rsi(close, period=14):
    """
    Compute the Relative Strength Index (RSI).
    
    Args:
        close: Series of close prices
        period: Period for calculation (default: 14)
    
    Returns:
        Series with RSI values
    """
    if isinstance(close, pd.Series):
        close = close.values
    
    deltas = np.diff(close)
    seed = deltas[:period + 1]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = np.zeros_like(close)
    rsi[:period] = 100. - 100. / (1. + rs)
    
    for i in range(period, len(close)):
        delta = deltas[i - 1]
        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta
        
        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period
        rs = up / down if down != 0 else 0
        rsi[i] = 100. - 100. / (1. + rs)
    
    return pd.Series(rsi)


def compute_macd(close, fast=12, slow=26, signal=9):
    """
    Compute MACD (Moving Average Convergence Divergence).
    
    Args:
        close: Series of close prices
        fast: Fast EMA period (default: 12)
        slow: Slow EMA period (default: 26)
        signal: Signal line period (default: 9)
    
    Returns:
        Tuple of (macd, signal, histogram)
    """
    if isinstance(close, pd.Series):
        close = close.values
    
    ema_fast = pd.Series(close).ewm(span=fast).mean().values
    ema_slow = pd.Series(close).ewm(span=slow).mean().values
    macd_line = ema_fast - ema_slow
    signal_line = pd.Series(macd_line).ewm(span=signal).mean().values
    histogram = macd_line - signal_line
    
    return (
        pd.Series(macd_line),
        pd.Series(signal_line),
        pd.Series(histogram)
    )


def compute_bollinger_bands(close, period=20, std_dev=2):
    """
    Compute Bollinger Bands.
    
    Args:
        close: Series of close prices
        period: Moving average period (default: 20)
        std_dev: Number of standard deviations (default: 2)
    
    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    if isinstance(close, pd.Series):
        close_series = close.copy()
    else:
        close_series = pd.Series(close)
    
    middle_band = close_series.rolling(window=period).mean()
    std = close_series.rolling(window=period).std()
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    
    return upper_band, middle_band, lower_band


def compute_atr(high, low, close, period=14):
    """
    Compute Average True Range (ATR).

    Args:
        high, low, close: Series or array-like price data
        period: smoothing period (default: 14)

    Returns:
        pd.Series with ATR values
    """
    import pandas as pd
    high  = pd.Series(high).reset_index(drop=True)
    low   = pd.Series(low).reset_index(drop=True)
    close = pd.Series(close).reset_index(drop=True)

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean()


def compute_atr_relative(high, low, atr):
    """
    Compute ATR relative to the candle range (high - low).

    Returns ATR / candle_range. Values > 1.5 indicate a large-ATR candle;
    values < 0.5 indicate a small-ATR candle relative to its range.

    Args:
        high, low: Series or array-like price data
        atr: Series with ATR values (e.g. ATR_14)

    Returns:
        pd.Series with relative ATR values
    """
    import pandas as pd
    high = pd.Series(high).reset_index(drop=True)
    low  = pd.Series(low).reset_index(drop=True)
    atr  = pd.Series(atr).reset_index(drop=True)

    candle_range = (high - low).abs().replace(0, float("nan"))
    return (atr / candle_range).fillna(1.0)


def compute_adx(df, period=14):
    """
    Compute Average Directional Index (ADX).
    
    ADX measures trend strength (0-100):
    - 0-25: Weak/No trend (ranging market)
    - 25-50: Moderate to Strong trend
    - 50+: Very strong trend
    
    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ADX period (default: 14)
    
    Returns:
        Series with ADX values
    """
    if isinstance(df, pd.DataFrame):
        high = df['high'].values if 'high' in df.columns else df['High'].values
        low = df['low'].values if 'low' in df.columns else df['Low'].values
        close = df['close'].values if 'close' in df.columns else df['Close'].values
    else:
        raise ValueError("Input must be a DataFrame with OHLC data")
    
    # Calculate Directional Movements
    plus_dm = np.zeros(len(high))
    minus_dm = np.zeros(len(high))
    
    for i in range(1, len(high)):
        up_move = high[i] - high[i-1]
        down_move = low[i-1] - low[i]
        
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        else:
            plus_dm[i] = 0
            
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move
        else:
            minus_dm[i] = 0
    
    # Calculate True Range
    tr = np.zeros(len(high))
    for i in range(len(high)):
        if i == 0:
            tr[i] = high[i] - low[i]
        else:
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )
    
    # Calculate smoothed values
    plus_dm_smooth = np.zeros(len(high))
    minus_dm_smooth = np.zeros(len(high))
    tr_smooth = np.zeros(len(high))
    
    # Initial smoothing values
    plus_dm_smooth[period-1] = np.sum(plus_dm[:period])
    minus_dm_smooth[period-1] = np.sum(minus_dm[:period])
    tr_smooth[period-1] = np.sum(tr[:period])
    
    # Continue smoothing
    for i in range(period, len(high)):
        plus_dm_smooth[i] = plus_dm_smooth[i-1] - plus_dm_smooth[i-1]/period + plus_dm[i]
        minus_dm_smooth[i] = minus_dm_smooth[i-1] - minus_dm_smooth[i-1]/period + minus_dm[i]
        tr_smooth[i] = tr_smooth[i-1] - tr_smooth[i-1]/period + tr[i]
    
    # Calculate Directional Indicators
    plus_di = np.zeros(len(high))
    minus_di = np.zeros(len(high))
    
    for i in range(period-1, len(high)):
        if tr_smooth[i] != 0:
            plus_di[i] = 100 * (plus_dm_smooth[i] / tr_smooth[i])
            minus_di[i] = 100 * (minus_dm_smooth[i] / tr_smooth[i])
    
    # Calculate ADX
    di_diff = np.abs(plus_di - minus_di)
    di_sum = plus_di + minus_di
    
    di_ratio = np.zeros(len(high))
    for i in range(len(high)):
        if di_sum[i] != 0:
            di_ratio[i] = di_diff[i] / di_sum[i]
        else:
            di_ratio[i] = 0
    
    # Smooth ADX
    adx = np.zeros(len(high))
    adx[period*2-1] = np.mean(di_ratio[period-1:period*2-1]) * 100
    
    for i in range(period*2, len(high)):
        adx[i] = (adx[i-1] * (period-1) + di_ratio[i] * 100) / period
    
    return pd.Series(adx, index=pd.RangeIndex(len(adx)))

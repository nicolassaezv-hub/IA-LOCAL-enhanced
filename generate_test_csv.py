"""
generate_test_csv.py

Utility to generate test Forex CSV files with indicators pre-calculated.
These CSVs can be used immediately for training and prediction testing.

Usage:
    python generate_test_csv.py --symbol EURUSD --timeframe H1 --output test_eurusd.csv
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI with proper implementation."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()  # ✅ FIXED
    avg_loss = avg_loss.replace(0, np.nan)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(close: pd.Series):
    """Calculate MACD."""
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return macd, signal, hist


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate ATR."""
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all technical indicators to dataframe."""
    df = df.copy()
    
    # Basic indicators
    df["rsi_14"] = calculate_rsi(df["close"], 14)
    df["macd"], df["macd_signal"], df["macd_histogram"] = calculate_macd(df["close"])
    df["atr_14"] = calculate_atr(df, 14)
    
    # EMAs
    df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema_150"] = df["close"].ewm(span=150, adjust=False).mean()
    
    # Bollinger Bands
    ma20 = df["close"].rolling(20).mean()
    std20 = df["close"].rolling(20).std()
    df["bollinger_upper_20"] = ma20 + 2 * std20
    df["bollinger_lower_20"] = ma20 - 2 * std20
    
    # Returns
    df["return_5"] = df["close"] / df["close"].shift(5) - 1
    
    # Volatility
    returns = np.log(df["close"] / df["close"].shift(1))
    df["volatility_20"] = returns.rolling(20).std()
    
    return df


def validate_ohlcv(df: pd.DataFrame) -> tuple[bool, list]:
    """Validate OHLCV data."""
    errors = []
    
    if len(df) == 0:
        return False, ["Empty dataframe"]
    
    if (df["high"] < df["low"]).sum() > 0:
        errors.append("High < Low found")
    
    if ((df["high"] < df["open"]) | (df["high"] < df["close"])).sum() > 0:
        errors.append("High < Open or Close found")
    
    if ((df["low"] > df["open"]) | (df["low"] > df["close"])).sum() > 0:
        errors.append("Low > Open or Close found")
    
    if df[["open", "high", "low", "close", "volume"]].isna().sum().sum() > 0:
        errors.append("NaN values in OHLCV")
    
    if (df["volume"] <= 0).sum() > 0:
        errors.append("Zero or negative volume found")
    
    return len(errors) == 0, errors


def generate_synthetic_data(
    symbol: str = "EURUSD",
    n_candles: int = 500,
    start_price: float = 1.1000,
    volatility: float = 0.002,
    timeframe: str = "H1"
) -> pd.DataFrame:
    """
    Generate synthetic but realistic Forex OHLCV data.
    
    Args:
        symbol: Currency pair (e.g., "EURUSD")
        n_candles: Number of candles
        start_price: Starting price
        volatility: Daily volatility
        timeframe: H1, H4, D1
    
    Returns:
        DataFrame with OHLCV and indicators
    """
    print(f"📊 Generating {n_candles} {timeframe} candles for {symbol}...")
    
    # Generate timestamps
    freq_map = {"H1": "1h", "H4": "4h", "D1": "1D"}
    freq = freq_map.get(timeframe, "1h")
    
    dates = pd.date_range(
        start=datetime(2023, 1, 1),
        periods=n_candles,
        freq=freq
    )
    
    np.random.seed(42)
    
    # Generate prices with random walk
    returns = np.random.randn(n_candles) * volatility
    close_prices = start_price * np.exp(np.cumsum(returns))
    
    # Create base data
    data = {
        'timestamp': dates,
        'open': close_prices + np.random.randn(n_candles) * volatility * start_price / 2,
        'close': close_prices,
        'volume': np.random.randint(5000, 50000, n_candles),
    }
    
    df = pd.DataFrame(data)
    
    # Generate High and Low
    intra_high = np.random.rand(n_candles) * volatility * start_price
    df['high'] = np.maximum(df['open'], df['close']) + intra_high
    
    intra_low = np.random.rand(n_candles) * volatility * start_price
    df['low'] = np.minimum(df['open'], df['close']) - intra_low
    
    # Ensure OHLC logic
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    # Validate
    is_valid, errors = validate_ohlcv(df)
    if not is_valid:
        print(f"❌ Validation errors: {errors}")
        return None
    
    print(f"✅ Data validation passed")
    
    # Add indicators
    print(f"📈 Calculating indicators...")
    df = add_indicators(df)
    
    # Reorder columns
    columns = [
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'rsi_14', 'macd', 'macd_signal', 'macd_histogram', 'atr_14',
        'ema_20', 'ema_50', 'ema_150',
        'bollinger_upper_20', 'bollinger_lower_20',
        'return_5', 'volatility_20'
    ]
    
    df = df[columns]
    
    # Check for NaN
    nan_count = df.isna().sum().sum()
    print(f"✅ Indicators calculated ({nan_count} NaN values, mostly from warm-up)")
    
    return df


def save_csv(df: pd.DataFrame, output_path: str, symbol: str) -> bool:
    """Save dataframe to CSV."""
    try:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"💾 Saved to: {output_path}")
        print(f"   Rows: {len(df)}, Columns: {len(df.columns)}")
        return True
    except Exception as e:
        print(f"❌ Error saving CSV: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate test Forex CSV with indicators"
    )
    parser.add_argument(
        "--symbol",
        default="EURUSD",
        help="Currency pair (default: EURUSD)"
    )
    parser.add_argument(
        "--timeframe",
        default="H1",
        choices=["H1", "H4", "D1"],
        help="Timeframe (default: H1)"
    )
    parser.add_argument(
        "--candles",
        type=int,
        default=500,
        help="Number of candles (default: 500)"
    )
    parser.add_argument(
        "--price",
        type=float,
        default=1.1000,
        help="Starting price (default: 1.1000)"
    )
    parser.add_argument(
        "--volatility",
        type=float,
        default=0.002,
        help="Daily volatility (default: 0.002)"
    )
    parser.add_argument(
        "--output",
        help="Output CSV path (default: test_<SYMBOL>_<TIMEFRAME>.csv)"
    )
    
    args = parser.parse_args()
    
    # Default output path
    if not args.output:
        args.output = f"test_{args.symbol}_{args.timeframe}.csv"
    
    print("=" * 70)
    print("FOREX TEST CSV GENERATOR")
    print("=" * 70)
    print(f"Symbol: {args.symbol}")
    print(f"Timeframe: {args.timeframe}")
    print(f"Candles: {args.candles}")
    print(f"Price: {args.price}")
    print(f"Volatility: {args.volatility}")
    print()
    
    # Generate data
    df = generate_synthetic_data(
        symbol=args.symbol,
        n_candles=args.candles,
        start_price=args.price,
        volatility=args.volatility,
        timeframe=args.timeframe
    )
    
    if df is None:
        print("❌ Failed to generate data")
        return False
    
    # Save
    success = save_csv(df, args.output, args.symbol)
    
    if success:
        print("\n" + "=" * 70)
        print("✅ TEST CSV READY FOR TRAINING & PREDICTION")
        print("=" * 70)
        print(f"\nUsage examples:")
        print(f"  python main.py")
        print(f"  > train forex {args.output}")
        print(f"  > predict forex {args.output}")
        print(f"  > tune forex {args.output}")
        print()
    
    return success


if __name__ == "__main__":
    main()

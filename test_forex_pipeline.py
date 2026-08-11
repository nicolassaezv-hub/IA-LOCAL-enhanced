"""
test_forex_pipeline.py

Unit tests for the Forex prediction pipeline.
Tests: data generation, indicators, target creation, feature engineering.

Usage:
    cd IA-LOCAL-enhanced-main
    python test_forex_pipeline.py
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

# ============================================================
# SYNTHETIC DATA GENERATOR
# ============================================================

def create_synthetic_forex_csv(
    symbol: str = "EURUSD",
    n_candles: int = 500,
    start_price: float = 1.1000,
    volatility: float = 0.002,
    seed: int = 42
) -> pd.DataFrame:
    """
    Creates a valid synthetic Forex dataset with realistic OHLCV data.
    
    Args:
        symbol: Currency pair (e.g., "EURUSD")
        n_candles: Number of candles to generate
        start_price: Starting close price
        volatility: Daily volatility (0.002 = 0.2%)
        seed: Random seed for reproducibility
    
    Returns:
        DataFrame ready for feature engineering
    """
    rng = np.random.default_rng(seed)
    
    # Generate timestamps (hourly)
    dates = pd.date_range(
        start=datetime(2023, 1, 1),
        periods=n_candles,
        freq='1h'
    )
    
    # Generate price movements using random walk
    returns = rng.standard_normal(n_candles) * volatility
    close_prices = start_price * np.exp(np.cumsum(returns))
    
    # Generate OHLCV
    data = {
        'timestamp': dates,
        'open': close_prices + rng.standard_normal(n_candles) * volatility * start_price / 2,
        'close': close_prices,
        'volume': rng.integers(5000, 50000, n_candles),
    }
    
    df = pd.DataFrame(data)
    
    # High = max(open, close) + some randomness
    intra_high = rng.random(n_candles) * volatility * start_price
    df['high'] = np.maximum(df['open'], df['close']) + intra_high
    
    # Low = min(open, close) - some randomness
    intra_low = rng.random(n_candles) * volatility * start_price
    df['low'] = np.minimum(df['open'], df['close']) - intra_low
    
    # Ensure High >= Low >= min(Open, Close) and High >= max(Open, Close)
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    # Add pair column
    df['pair'] = symbol
    
    return df[['timestamp', 'pair', 'open', 'high', 'low', 'close', 'volume']]


# ============================================================
# VALIDATION FUNCTIONS (SAME AS IN creando.py)
# ============================================================

def validate_ohlcv(df: pd.DataFrame, symbol: str = "") -> tuple[bool, list]:
    """Validates OHLC logic and data quality."""
    errors = []
    
    if len(df) == 0:
        return False, ["Empty dataframe"]
    
    invalid_high_low = (df["high"] < df["low"]).sum()
    if invalid_high_low > 0:
        errors.append(f"  ❌ {invalid_high_low} rows: High < Low")
    
    invalid_high_oc = ((df["high"] < df["open"]) | (df["high"] < df["close"])).sum()
    if invalid_high_oc > 0:
        errors.append(f"  ❌ {invalid_high_oc} rows: High < Open or Close")
    
    invalid_low_oc = ((df["low"] > df["open"]) | (df["low"] > df["close"])).sum()
    if invalid_low_oc > 0:
        errors.append(f"  ❌ {invalid_low_oc} rows: Low > Open or Close")
    
    nan_ohlcv = df[["open", "high", "low", "close", "volume"]].isna().sum().sum()
    if nan_ohlcv > 0:
        errors.append(f"  ❌ {nan_ohlcv} NaN values in OHLCV")
    
    if (df["volume"] <= 0).sum() > 0:
        errors.append(f"  ⚠️  {(df['volume'] <= 0).sum()} rows with zero/negative volume")
    
    spread = df["high"] - df["low"]
    large_spread = (spread > df["close"] * 0.05).sum()
    if large_spread > len(df) * 0.01:
        errors.append(f"  ⚠️  {large_spread} rows with spread > 5%")
    
    is_valid = len([e for e in errors if e.startswith("  ❌")]) == 0
    return is_valid, errors


# ============================================================
# INDICATOR TESTS
# ============================================================

def test_rsi_calculation():
    """Test RSI calculation (the one with the bug fix)."""
    print("\n[TEST] RSI Calculation")
    
    df = create_synthetic_forex_csv(n_candles=100)
    
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()  # ✅ FIX HERE
        avg_loss = avg_loss.replace(0, np.nan)
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    rsi = calculate_rsi(df['close'], 14)
    
    # Check: RSI should not be all NaN
    assert not rsi.isna().all(), "❌ RSI is completely NaN"
    valid_rsi = rsi.dropna()
    assert not valid_rsi.empty, "❌ RSI has no valid values"
    assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all(), \
        f"❌ RSI out of [0, 100] range: min={valid_rsi.min():.2f}, max={valid_rsi.max():.2f}"
    assert rsi.dropna().shape[0] > 0, "❌ No valid RSI values"
    
    print(f"  ✅ RSI calculated successfully ({rsi.dropna().shape[0]} valid values)")
    print(f"     Mean: {rsi.mean():.2f}, Std: {rsi.std():.2f}")


def test_ohlcv_validation():
    """Test OHLCV validation logic."""
    print("\n[TEST] OHLCV Validation")
    
    # Valid data
    df_valid = create_synthetic_forex_csv(n_candles=100)
    is_valid, errors = validate_ohlcv(df_valid)
    
    assert is_valid, f"❌ Valid data marked as invalid: {errors}"
    print(f"  ✅ Valid data passed validation")
    
    # Invalid data - swap high/low
    df_invalid = create_synthetic_forex_csv(n_candles=100)
    df_invalid.loc[0, 'high'] = df_invalid.loc[0, 'low'] - 0.001
    
    is_valid, errors = validate_ohlcv(df_invalid)
    assert not is_valid, "❌ Invalid data should be caught"
    print(f"  ✅ Invalid data correctly detected: {errors[0]}")


def test_dataset_quality():
    """Test that synthetic data has realistic properties."""
    print("\n[TEST] Dataset Quality")
    
    df = create_synthetic_forex_csv(n_candles=500)
    
    # Check size
    assert len(df) == 500, f"❌ Expected 500 rows, got {len(df)}"
    print(f"  ✅ Correct number of candles: {len(df)}")
    
    # Check no NaN
    nan_count = df[['open', 'high', 'low', 'close', 'volume']].isna().sum().sum()
    assert nan_count == 0, f"❌ Found {nan_count} NaN values"
    print(f"  ✅ No NaN values in OHLCV")
    
    # Check volume range
    assert (df['volume'] > 0).all(), "❌ Volume should be positive"
    print(f"  ✅ All volumes positive")
    
    # Check price stability (not all same price)
    price_std = df['close'].std()
    assert price_std > 0, "❌ Close price has no variance"
    print(f"  ✅ Price variance exists (std: {price_std:.6f})")


def test_feature_engineering_compatibility():
    """Test that generated CSV is compatible with feature_engineering.py"""
    print("\n[TEST] Feature Engineering Compatibility")
    
    try:
        from forex.prediction.feature_engineering import FeatureEngineering, build_features
        from forex.prediction.csv_adapter import adapt_csv
        
        df = create_synthetic_forex_csv(n_candles=200)
        
        # adapt_csv normalises the raw OHLCV before feature engineering
        with TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "feature-engineering.csv"
            df.to_csv(csv_path, index=False)
            df = adapt_csv(csv_path, pair='EURUSD')
        
        # Try to run feature engineering
        df_engineered = build_features(df)
        
        assert len(df_engineered) > 0, "❌ Feature engineering returned empty"
        assert df_engineered.shape[1] > df.shape[1], "❌ No new features added"
        
        print(f"  ✅ Feature engineering successful")
        print(f"     Input columns: {df.shape[1]}, Output columns: {df_engineered.shape[1]}")
        
    except Exception as e:
        raise AssertionError("Feature engineering compatibility failed") from e


def test_target_creation():
    """Test that target labels are created correctly."""
    print("\n[TEST] Target Label Creation")
    
    try:
        from forex.prediction.dataset_builder import DatasetBuilder
        from forex.prediction.feature_engineering import build_features
        
        from forex.prediction.csv_adapter import adapt_csv
        df_raw = create_synthetic_forex_csv(n_candles=300)
        with TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "target-creation.csv"
            df_raw.to_csv(csv_path, index=False)
            df = adapt_csv(csv_path, pair='EURUSD')
        df = build_features(df)
        
        builder = DatasetBuilder(df)
        X, y = builder.build(horizon=10, rr_ratio=1.5)
        
        assert len(X) > 0, "❌ No features generated"
        assert len(y) > 0, "❌ No targets generated"
        assert len(X) == len(y), "❌ X and y length mismatch"
        
        buy_ratio = y.sum() / len(y)
        assert 0 < buy_ratio < 1, f"❌ All signals same direction (buy: {buy_ratio:.1%})"
        
        print(f"  ✅ Target creation successful")
        print(f"     Total samples: {len(X)}")
        print(f"     Buy signals: {y.sum()} ({y.sum()/len(y):.1%})")
        print(f"     Sell signals: {(y==0).sum()} ({(y==0).sum()/len(y):.1%})")
        print(f"     Features: {X.shape[1]}")
        
    except Exception as e:
        raise AssertionError("Target creation failed") from e


# ============================================================
# RUN ALL TESTS
# ============================================================

def run_all_tests():
    """Run all tests."""
    print("=" * 70)
    print("FOREX PIPELINE TEST SUITE")
    print("=" * 70)
    
    test_ohlcv_validation()
    test_dataset_quality()
    test_rsi_calculation()
    test_feature_engineering_compatibility()
    test_target_creation()
    
    print("\n" + "=" * 70)
    print("✅ TEST SUITE COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()

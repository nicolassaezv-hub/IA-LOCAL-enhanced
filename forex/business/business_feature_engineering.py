"""
business_feature_engineering.py — Build ML features from normalized business data.

Features built:
  Time         : month, quarter, day_of_week, is_month_end, is_quarter_end
  Growth       : mom_growth, 3m/6m rolling avg, 3m/6m rolling std
  Trend        : linear slope over last 3/6/12 periods
  Ratio        : gross_margin_pct, net_margin_pct, expense_ratio
  Seasonality  : same_month_last_year_delta, seasonal_index
  Anomaly      : z_score, is_outlier flag
  Lag features : lag_1, lag_2, lag_3, lag_6, lag_12
"""

import numpy as np
import pandas as pd
from typing import Optional


def build_business_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add ML-ready features to a normalized business DataFrame.

    Parameters
    ----------
    df : output of business_csv_adapter.adapt_business_csv()

    Returns
    -------
    pd.DataFrame with new feature columns appended.
    """
    df = df.copy()

    metric = _primary_metric(df)
    if metric is None:
        return df

    series = df[metric]

    # ── Time features ────────────────────────────────────────────────────
    if "date" in df.columns and df["date"].notna().any():
        df["month"]            = df["date"].dt.month
        df["quarter"]          = df["date"].dt.quarter
        df["day_of_week"]      = df["date"].dt.dayofweek
        df["is_month_end"]     = df["date"].dt.is_month_end.astype(int)
        df["is_quarter_end"]   = df["date"].dt.is_quarter_end.astype(int)
        df["month_sin"]        = np.sin(2 * np.pi * df["month"] / 12)
        df["month_cos"]        = np.cos(2 * np.pi * df["month"] / 12)
    else:
        df["month"]  = 0
        df["quarter"]= 0

    # ── Lag features ─────────────────────────────────────────────────────
    for lag in [1, 2, 3, 6, 12]:
        df[f"lag_{lag}"] = series.shift(lag)

    # ── Growth features ───────────────────────────────────────────────────
    prev = series.shift(1)
    df["mom_growth"]   = ((series - prev) / prev.replace(0, np.nan) * 100)
    df["mom_growth_abs"]= series - prev

    prev3  = series.shift(3)
    df["3m_growth"]    = ((series - prev3) / prev3.replace(0, np.nan) * 100)

    prev12 = series.shift(12)
    df["yoy_growth"]   = ((series - prev12) / prev12.replace(0, np.nan) * 100)

    # ── Rolling stats ─────────────────────────────────────────────────────
    for window in [3, 6, 12]:
        df[f"rolling_{window}m_avg"] = series.rolling(window, min_periods=1).mean()
        df[f"rolling_{window}m_std"] = series.rolling(window, min_periods=2).std()

    # ── Trend slope (linear regression over last N periods) ───────────────
    for window in [3, 6, 12]:
        df[f"slope_{window}p"] = series.rolling(window, min_periods=window).apply(
            lambda x: _compute_slope(x), raw=True
        )

    # ── Ratio features ────────────────────────────────────────────────────
    if "gross_profit" in df.columns and "revenue" in df.columns:
        rev = df["revenue"].replace(0, np.nan)
        df["gross_margin_pct"] = df["gross_profit"] / rev * 100

    if "net_income" in df.columns and "revenue" in df.columns:
        rev = df["revenue"].replace(0, np.nan)
        df["net_margin_pct"] = df["net_income"] / rev * 100

    if "expenses" in df.columns and "revenue" in df.columns:
        rev = df["revenue"].replace(0, np.nan)
        df["expense_ratio_pct"] = df["expenses"] / rev * 100

    if "cost_of_sales" in df.columns and "revenue" in df.columns:
        rev = df["revenue"].replace(0, np.nan)
        df["cogs_ratio_pct"] = df["cost_of_sales"] / rev * 100

    # ── Seasonality features ──────────────────────────────────────────────
    if "month" in df.columns and df["month"].any():
        monthly_avg = series.groupby(df["month"]).transform("mean")
        global_avg  = series.mean()
        if global_avg != 0:
            df["seasonal_index"] = monthly_avg / global_avg
        else:
            df["seasonal_index"] = 1.0
        df["seasonal_deviation"] = series - monthly_avg

    # ── Z-score anomaly flag ──────────────────────────────────────────────
    rolling_mean = series.rolling(12, min_periods=3).mean()
    rolling_std  = series.rolling(12, min_periods=3).std()
    df["z_score"]   = (series - rolling_mean) / rolling_std.replace(0, np.nan)
    df["is_outlier"]= (df["z_score"].abs() > 2.5).astype(int)

    # ── Acceleration (rate of change of growth) ───────────────────────────
    if "mom_growth" in df.columns:
        df["growth_acceleration"] = df["mom_growth"].diff()

    # ── Drop rows with all NaN features ──────────────────────────────────
    feature_cols = [c for c in df.columns if c not in
                    ["date", "period", "product", "category"]]
    df.dropna(subset=["lag_1"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


def _primary_metric(df: pd.DataFrame) -> Optional[str]:
    for col in ["revenue", "net_income", "gross_profit", "balance", "inflow", "units_sold"]:
        if col in df.columns:
            return col
    return None


def _compute_slope(x: np.ndarray) -> float:
    if len(x) < 2:
        return 0.0
    n    = np.arange(len(x))
    return float(np.polyfit(n, x, 1)[0])

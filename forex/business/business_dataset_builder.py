"""
business_dataset_builder.py — Build ML-ready X/y from engineered business features.

Target definitions (configurable):
  'growth'   — will next period's primary metric be higher than current? (binary)
  'decline'  — will the metric drop more than decline_threshold% next period?
  'margin'   — will gross margin compress next period?
  'cashflow' — will ending balance be negative in the next N periods?

Default: 'growth' (most general, works for any business type)
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional


_EXCLUDE_COLS = {
    "date", "period", "product", "category", "description",
    "lag_1", "lag_2", "lag_3", "lag_6", "lag_12",
}

_TARGET_COLS = {
    "growth":   "revenue",
    "decline":  "revenue",
    "margin":   "gross_margin_pct",
    "cashflow": "balance",
}


class BusinessDatasetBuilder:
    """
    Builds the ML feature matrix X and target vector y from a
    business DataFrame that has already been through feature engineering.

    Parameters
    ----------
    df               : feature-engineered DataFrame
    target           : 'growth' | 'decline' | 'margin' | 'cashflow'
    horizon          : periods ahead to predict (default 1)
    decline_threshold: % drop threshold for 'decline' target (default 10)
    """

    def __init__(
        self,
        df:                pd.DataFrame,
        target:            str   = "growth",
        horizon:           int   = 1,
        decline_threshold: float = 10.0,
    ):
        self.df                = df.copy()
        self.target            = target
        self.horizon           = horizon
        self.decline_threshold = decline_threshold

    def build(self) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Returns
        -------
        X : feature matrix
        y : target vector (0 / 1)
        """
        df = self.df.copy()

        metric_col = _TARGET_COLS.get(self.target, "revenue")
        if metric_col not in df.columns:
            for fallback in ["net_income", "gross_profit", "balance", "inflow"]:
                if fallback in df.columns:
                    metric_col = fallback
                    break
            else:
                raise ValueError(
                    f"Cannot build target '{self.target}': "
                    f"no usable metric column found."
                )

        # ── Build target ─────────────────────────────────────────────────
        future = df[metric_col].shift(-self.horizon)
        current = df[metric_col]

        if self.target == "growth":
            y = (future > current).astype(int)

        elif self.target == "decline":
            pct_change = (future - current) / current.replace(0, np.nan) * 100
            y = (pct_change < -self.decline_threshold).astype(int)

        elif self.target == "margin":
            if "gross_margin_pct" not in df.columns:
                raise ValueError("'margin' target requires gross_margin_pct column.")
            future_margin = df["gross_margin_pct"].shift(-self.horizon)
            y = (future_margin < df["gross_margin_pct"]).astype(int)

        elif self.target == "cashflow":
            future_bal = df[metric_col].shift(-self.horizon)
            y = (future_bal < 0).astype(int)

        else:
            raise ValueError(f"Unknown target: {self.target}")

        # ── Build feature matrix ─────────────────────────────────────────
        drop_cols = set(_EXCLUDE_COLS) | {metric_col}
        feature_cols = [
            c for c in df.columns
            if c not in drop_cols
            and df[c].dtype in [np.float64, np.float32, np.int64, np.int32, float, int]
        ]

        X = df[feature_cols].copy()

        # Align with valid y (drop rows where future is unknown)
        valid_mask = y.notna() & X.notna().all(axis=1)
        X = X[valid_mask]
        y = y[valid_mask]

        # Fill remaining NaN with column medians
        X = X.fillna(X.median())

        return X, y.astype(int)

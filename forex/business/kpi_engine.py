"""
forex/business/kpi_engine.py

Computes business KPIs from a normalized business DataFrame
(produced by `business_csv_adapter.adapt_business_csv`).

KPIs include: revenue trend, gross/net margins, growth rate,
expense ratio, health score (0-100), and trend direction.

Author: Nicolas Saez / Astra Project
"""

from typing import Dict, Optional

import numpy as np
import pandas as pd


class KPIEngine:
    """Compute a full KPI dictionary from a normalized business DataFrame."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self._has_revenue = "revenue" in df.columns
        self._has_cost = "cost_of_sales" in df.columns
        self._has_expenses = "expenses" in df.columns
        self._has_gross = "gross_profit" in df.columns
        self._has_net = "net_income" in df.columns

    # ------------------------------------------------------------------
    # Individual KPI computations
    # ------------------------------------------------------------------

    def _revenue(self) -> Optional[float]:
        if not self._has_revenue:
            return None
        return float(self.df["revenue"].sum())

    def _avg_revenue(self) -> Optional[float]:
        if not self._has_revenue:
            return None
        return float(self.df["revenue"].mean())

    def _growth_rate(self) -> Optional[float]:
        """Period-over-period revenue growth (percentage)."""
        if not self._has_revenue or len(self.df) < 2:
            return None
        rev = self.df["revenue"].dropna()
        if len(rev) < 2:
            return None
        first, last = float(rev.iloc[0]), float(rev.iloc[-1])
        if first == 0:
            return None
        return ((last - first) / first) * 100.0

    def _gross_margin(self) -> Optional[float]:
        if self._has_gross and self._has_revenue:
            rev = self.df["revenue"].sum()
            if rev == 0:
                return None
            return float(self.df["gross_profit"].sum() / rev * 100)
        if self._has_revenue and self._has_cost:
            rev = self.df["revenue"].sum()
            if rev == 0:
                return None
            gp = rev - self.df["cost_of_sales"].sum()
            return float(gp / rev * 100)
        return None

    def _net_margin(self) -> Optional[float]:
        if self._has_net and self._has_revenue:
            rev = self.df["revenue"].sum()
            if rev == 0:
                return None
            return float(self.df["net_income"].sum() / rev * 100)
        if self._has_revenue and self._has_cost and self._has_expenses:
            rev = self.df["revenue"].sum()
            if rev == 0:
                return None
            ni = rev - self.df["cost_of_sales"].sum() - self.df["expenses"].sum()
            return float(ni / rev * 100)
        return None

    def _expense_ratio(self) -> Optional[float]:
        if not (self._has_expenses and self._has_revenue):
            return None
        rev = self.df["revenue"].sum()
        if rev == 0:
            return None
        return float(self.df["expenses"].sum() / rev * 100)

    def _trend_slope_and_strength(self):
        """
        Linear-regression slope (revenue change per period, in currency
        units) and R^2 (goodness of fit / trend_strength) on the revenue
        series. Shared by _trend_direction() and exposed in compute_all()
        for downstream consumers (sme_consultant.sme_forecast, dashboards).
        Returns (slope, r_squared) — both 0.0 if not enough data.
        """
        if not self._has_revenue:
            return 0.0, 0.0
        rev = self.df["revenue"].dropna()
        if len(rev) < 3:
            return 0.0, 0.0
        x = np.arange(len(rev))
        y = rev.values.astype(float)
        slope, intercept = np.polyfit(x, y, 1)
        y_pred = slope * x + intercept
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))
        return float(slope), float(r_squared)

    def _trend_direction(self) -> str:
        """Simple linear-regression slope on revenue to determine trend."""
        if not self._has_revenue or len(self.df) < 3:
            return "unknown"
        slope, _ = self._trend_slope_and_strength()
        if slope > 0:
            return "growing"
        if slope < 0:
            return "declining"
        return "stable"

    def _latest_revenue(self) -> Optional[float]:
        if not self._has_revenue:
            return None
        rev = self.df["revenue"].dropna()
        if len(rev) == 0:
            return None
        return float(rev.iloc[-1])

    def _health_score(self) -> int:
        """
        Composite health score 0-100 based on available KPIs.
        Weights: growth 30, gross margin 25, net margin 25, expense ratio 20.
        """
        score = 50  # neutral baseline

        growth = self._growth_rate()
        if growth is not None:
            if growth > 20:
                score += 15
            elif growth > 5:
                score += 8
            elif growth < -20:
                score -= 15
            elif growth < -5:
                score -= 8

        gm = self._gross_margin()
        if gm is not None:
            if gm > 40:
                score += 12
            elif gm > 20:
                score += 6
            elif gm < 0:
                score -= 12

        nm = self._net_margin()
        if nm is not None:
            if nm > 15:
                score += 12
            elif nm > 5:
                score += 6
            elif nm < 0:
                score -= 12

        er = self._expense_ratio()
        if er is not None:
            if er < 20:
                score += 8
            elif er > 50:
                score -= 8

        return max(0, min(100, int(score)))

    def _risk_level(self) -> str:
        health = self._health_score()
        if health >= 70:
            return "LOW"
        if health >= 40:
            return "MEDIUM"
        return "HIGH"

    def _anomalies(self) -> list:
        """Detect revenue drops > 20% period-over-period."""
        anomalies = []
        if not self._has_revenue or len(self.df) < 2:
            return anomalies
        rev = self.df["revenue"].dropna()
        for i in range(1, len(rev)):
            prev, curr = float(rev.iloc[i - 1]), float(rev.iloc[i])
            if prev > 0 and curr > 0:
                change = (curr - prev) / prev * 100
                if change < -20:
                    anomalies.append({
                        "period": str(self.df["period"].iloc[i])
                        if "period" in self.df.columns else f"row {i}",
                        "change_pct": round(change, 1),
                    })
        return anomalies

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_all(self) -> Dict:
        """Return a dictionary with all computed KPIs."""
        slope, strength = self._trend_slope_and_strength()
        return {
            "business_type": self.df.attrs.get("business_type", "generic"),
            "rows": len(self.df),
            "total_revenue": self._revenue(),
            "avg_revenue": self._avg_revenue(),
            "latest_revenue": self._latest_revenue(),
            "growth_rate_pct": self._growth_rate(),
            "gross_margin_pct": self._gross_margin(),
            "net_margin_pct": self._net_margin(),
            "expense_ratio_pct": self._expense_ratio(),
            "trend_direction": self._trend_direction(),
            "trend_slope": slope,
            "trend_strength": strength,
            "health_score": self._health_score(),
            "risk_level": self._risk_level(),
            "anomalies": self._anomalies(),
        }

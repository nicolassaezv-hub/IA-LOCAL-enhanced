"""
forex_analytics.py — ASTRA Forex Analytics Engine

Generates a human-readable technical analysis report from a forex CSV.
Uses adapt_csv (which calls fill_nan_indicators) so the engine never
fails on missing or NaN indicator columns — everything is computed from
OHLCV when absent.

New in this version:
  - Unified with the indicator layer (forex.indicators)
  - CCI, MFI, ROC analysis sections added
  - Fixed: market_regime_detection used "Returns" (capital R) — corrected to "returns"
  - analyze_market_file now uses adapt_csv for proper column renaming + imputation
"""

import pandas as pd
import numpy as np

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from forex.market_universe import (
    normalize_symbol,
    get_market_type,
    is_supported_market,
)
from forex.indicators import (
    compute_cci,
    compute_mfi,
    compute_roc,
)
from forex.forex_report import ForexReport
from forex.forex_models import validate_confidence
from forex.forex_memory import (
    save_analysis,
    get_history,
    compare_last_reports,
)


class ForexAnalytics:

    def __init__(self):
        self.df = None
        self.filepath = None

    def _check_loaded(self):
        if self.df is None:
            raise ValueError("No dataset loaded. Call load_csv() first.")

    # =========================================================================
    # LOADING — uses adapt_csv for renaming + NaN imputation
    # =========================================================================

    def load_csv(self, filepath: str, pair: str = None):
        """
        Load a forex CSV using the full adapt_csv pipeline:
          - Column renaming (rsi_14 → RSI_14, ema_150 → EMA200, etc.)
          - NaN indicator imputation from OHLCV
          - Session labels, pair, spread injection
        """
        from forex.prediction.csv_adapter import adapt_csv
        self.filepath = filepath
        self.df = adapt_csv(filepath, pair=pair)
        return {
            "status":       "loaded",
            "rows":         len(self.df),
            "columns":      len(self.df.columns),
            "column_names": list(self.df.columns),
        }

    # =========================================================================
    # DATASET SUMMARY
    # =========================================================================

    def dataset_summary(self):
        self._check_loaded()
        return {
            "rows":            len(self.df),
            "columns":         len(self.df.columns),
            "missing_values":  self.df.isnull().sum().to_dict(),
            "memory_usage_mb": round(
                self.df.memory_usage(deep=True).sum() / 1024 ** 2, 2
            ),
        }

    # =========================================================================
    # SESSION ANALYSIS
    # =========================================================================

    def session_analysis(self):
        self._check_loaded()
        if "session" not in self.df.columns:
            return {"error": "session column not found"}

        report = {}
        for session, data in self.df.groupby("session"):
            report[session] = {
                "candles":        int(len(data)),
                "avg_volume":     float(data["volume"].mean()) if "volume" in data.columns else None,
                "avg_spread":     float(data["spread"].mean()) if "spread" in data.columns else None,
                "avg_volatility": float(data["volatility_24h"].mean()) if "volatility_24h" in data.columns else None,
            }
        return report

    # =========================================================================
    # RSI ANALYSIS
    # =========================================================================

    def rsi_analysis(self):
        self._check_loaded()
        if "RSI_14" not in self.df.columns:
            return {"error": "RSI_14 not available"}

        rsi = self.df["RSI_14"].dropna()
        return {
            "mean":        round(float(rsi.mean()), 2),
            "max":         round(float(rsi.max()), 2),
            "min":         round(float(rsi.min()), 2),
            "overbought":  int((rsi > 70).sum()),
            "oversold":    int((rsi < 30).sum()),
            "current":     round(float(rsi.iloc[-1]), 2) if len(rsi) else None,
        }

    # =========================================================================
    # MACD ANALYSIS
    # =========================================================================

    def macd_analysis(self):
        self._check_loaded()
        required = ["MACD", "MACD_signal", "MACD_hist"]
        missing  = [c for c in required if c not in self.df.columns]
        if missing:
            return {"error": f"Missing columns: {missing}"}

        macd    = self.df["MACD"].dropna()
        sig     = self.df["MACD_signal"].dropna()
        hist    = self.df["MACD_hist"].dropna()

        bullish_cross = int((self.df["MACD"] > self.df["MACD_signal"]).sum())
        bearish_cross = int((self.df["MACD"] < self.df["MACD_signal"]).sum())

        current_hist = float(hist.iloc[-1]) if len(hist) else None
        momentum = (
            "bullish" if current_hist and current_hist > 0
            else "bearish" if current_hist and current_hist < 0
            else "neutral"
        )

        return {
            "bullish_periods":  bullish_cross,
            "bearish_periods":  bearish_cross,
            "avg_histogram":    round(float(hist.mean()), 6),
            "current_macd":     round(float(macd.iloc[-1]), 6) if len(macd) else None,
            "current_histogram": round(current_hist, 6) if current_hist is not None else None,
            "current_momentum": momentum,
        }

    # =========================================================================
    # VOLATILITY ANALYSIS
    # =========================================================================

    def volatility_analysis(self):
        self._check_loaded()
        col = next((c for c in ["volatility_24h", "ATR_14"] if c in self.df.columns), None)
        if col is None:
            return {"error": "No volatility column available"}

        vol = self.df[col].dropna()
        pct_above_mean = float((vol > vol.mean()).sum()) / len(vol) * 100 if len(vol) else 0

        return {
            "column": col,
            "mean":   round(float(vol.mean()), 6),
            "std":    round(float(vol.std()),  6),
            "max":    round(float(vol.max()),  6),
            "min":    round(float(vol.min()),  6),
            "current": round(float(vol.iloc[-1]), 6) if len(vol) else None,
            "pct_above_avg": round(pct_above_mean, 1),
        }

    # =========================================================================
    # TREND ANALYSIS (EMA triple alignment)
    # =========================================================================

    def trend_analysis(self):
        self._check_loaded()
        required = ["EMA20", "EMA50", "EMA200"]
        missing  = [c for c in required if c not in self.df.columns]
        if missing:
            return {"error": f"Missing columns: {missing}"}

        bullish = int((
            (self.df["EMA20"] > self.df["EMA50"]) &
            (self.df["EMA50"] > self.df["EMA200"])
        ).sum())

        bearish = int((
            (self.df["EMA20"] < self.df["EMA50"]) &
            (self.df["EMA50"] < self.df["EMA200"])
        ).sum())

        total   = len(self.df)
        last_20 = float(self.df["EMA20"].iloc[-1])
        last_50 = float(self.df["EMA50"].iloc[-1])
        last_200= float(self.df["EMA200"].iloc[-1])
        current_bias = (
            "bullish" if last_20 > last_50 > last_200
            else "bearish" if last_20 < last_50 < last_200
            else "mixed"
        )

        return {
            "bullish_candles":  bullish,
            "bearish_candles":  bearish,
            "bullish_ratio":    round(bullish / total, 4),
            "bearish_ratio":    round(bearish / total, 4),
            "current_ema20":    round(last_20, 6),
            "current_ema50":    round(last_50, 6),
            "current_ema200":   round(last_200, 6),
            "current_bias":     current_bias,
        }

    # =========================================================================
    # CCI ANALYSIS (new)
    # =========================================================================

    def cci_analysis(self):
        self._check_loaded()
        # Compute CCI if not already present
        if "CCI_20" not in self.df.columns:
            self.df["CCI_20"] = compute_cci(
                self.df["high"], self.df["low"], self.df["close"], 20
            )

        cci = self.df["CCI_20"].dropna()
        current = float(cci.iloc[-1]) if len(cci) else None
        zone = (
            "overbought" if current and current > 100
            else "oversold" if current and current < -100
            else "neutral"
        )

        return {
            "mean":        round(float(cci.mean()), 2),
            "max":         round(float(cci.max()),  2),
            "min":         round(float(cci.min()),  2),
            "overbought_periods": int((cci >  100).sum()),
            "oversold_periods":   int((cci < -100).sum()),
            "current":     round(current, 2) if current is not None else None,
            "current_zone": zone,
        }

    # =========================================================================
    # MFI ANALYSIS (new)
    # =========================================================================

    def mfi_analysis(self):
        self._check_loaded()
        if "MFI_14" not in self.df.columns:
            volume = (
                self.df["volume"]
                if "volume" in self.df.columns
                else pd.Series(np.zeros(len(self.df)), index=self.df.index)
            )
            self.df["MFI_14"] = compute_mfi(
                self.df["high"], self.df["low"], self.df["close"], volume, 14
            )

        mfi = self.df["MFI_14"].dropna()
        current = float(mfi.iloc[-1]) if len(mfi) else None
        zone = (
            "overbought" if current and current > 80
            else "oversold" if current and current < 20
            else "neutral"
        )

        return {
            "mean":        round(float(mfi.mean()), 2),
            "max":         round(float(mfi.max()),  2),
            "min":         round(float(mfi.min()),  2),
            "overbought_periods": int((mfi > 80).sum()),
            "oversold_periods":   int((mfi < 20).sum()),
            "current":     round(current, 2) if current is not None else None,
            "current_zone": zone,
        }

    # =========================================================================
    # ROC ANALYSIS (new)
    # =========================================================================

    def roc_analysis(self):
        self._check_loaded()
        if "ROC_10" not in self.df.columns:
            self.df["ROC_10"] = compute_roc(self.df["close"], 10)

        roc = self.df["ROC_10"].dropna()
        current = float(roc.iloc[-1]) if len(roc) else None
        momentum = (
            "strong_bull" if current and current > 1
            else "bull"    if current and current > 0
            else "strong_bear" if current and current < -1
            else "bear"    if current and current < 0
            else "neutral"
        )

        return {
            "mean":      round(float(roc.mean()), 4),
            "max":       round(float(roc.max()),  4),
            "min":       round(float(roc.min()),  4),
            "current":   round(current, 4) if current is not None else None,
            "momentum":  momentum,
            "positive_periods": int((roc > 0).sum()),
            "negative_periods": int((roc < 0).sum()),
        }

    # =========================================================================
    # CORRELATIONS
    # =========================================================================

    def correlation_matrix(self):
        self._check_loaded()
        numeric_df = self.df.select_dtypes(include=np.number)
        return numeric_df.corr().round(3)

    # =========================================================================
    # MARKET REGIME DETECTION (KMeans clustering)
    # =========================================================================

    def market_regime_detection(self, n_clusters: int = 3):
        self._check_loaded()
        # Fixed: was "Returns" (capital R) — column is now always "returns" (lowercase)
        feature_candidates = ["returns", "volatility_24h", "ATR_14"]
        available = [c for c in feature_candidates if c in self.df.columns]

        if len(available) < 2:
            return {"error": "Not enough regime features available"}

        X = self.df[available].dropna()
        if len(X) < n_clusters:
            return {"error": f"Too few rows ({len(X)}) for {n_clusters} clusters"}

        scaler  = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        model   = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels  = model.fit_predict(X_scaled)
        counts  = pd.Series(labels).value_counts().to_dict()

        return {
            "clusters":  counts,
            "features":  available,
            "n_samples": len(X),
        }

    # =========================================================================
    # COMPLETE REPORT
    # =========================================================================

    def generate_report(self):
        self._check_loaded()
        return {
            "dataset":    self.dataset_summary(),
            "sessions":   self.session_analysis(),
            "rsi":        self.rsi_analysis(),
            "macd":       self.macd_analysis(),
            "volatility": self.volatility_analysis(),
            "trend":      self.trend_analysis(),
            "cci":        self.cci_analysis(),
            "mfi":        self.mfi_analysis(),
            "roc":        self.roc_analysis(),
            "regimes":    self.market_regime_detection(),
        }


# =============================================================================
# PUBLIC API
# =============================================================================

def analyze_market_file(
    filepath: str = None,
    symbol:   str = None,
) -> str:
    """
    Analyze a forex/commodity dataset and save the report.

    Supports:
        analyze_market_file("EURUSD")
        analyze_market_file("data.csv", "EURUSD")
    """
    if symbol is None:
        symbol   = filepath
        filepath = None

    symbol = normalize_symbol(symbol)

    if not is_supported_market(symbol):
        raise ValueError(f"Unsupported market: {symbol}")

    if filepath is None:
        return f"{symbol} recognized. No dataset provided — supply a CSV path to run analysis."

    # Use adapt_csv so renaming + NaN imputation happen before analytics
    engine = ForexAnalytics()
    engine.load_csv(filepath, pair=symbol)

    analytics  = engine.generate_report()
    trend_data = analytics.get("trend", {})
    bullish    = trend_data.get("bullish_ratio", 0)
    bearish    = trend_data.get("bearish_ratio", 0)

    if bullish > bearish:
        trend = "bullish"
    elif bearish > bullish:
        trend = "bearish"
    else:
        trend = "neutral"

    # Build enriched technical summary for the report
    rsi_data = analytics.get("rsi", {})
    macd_data= analytics.get("macd", {})
    vol_data = analytics.get("volatility", {})
    cci_data = analytics.get("cci", {})
    mfi_data = analytics.get("mfi", {})
    roc_data = analytics.get("roc", {})

    technical_analysis = (
        f"RSI (14):        current={rsi_data.get('current')}  "
        f"overbought={rsi_data.get('overbought')} periods  "
        f"oversold={rsi_data.get('oversold')} periods\n\n"

        f"MACD (12/26/9):  momentum={macd_data.get('current_momentum')}  "
        f"histogram={macd_data.get('current_histogram')}  "
        f"bullish={macd_data.get('bullish_periods')} / bearish={macd_data.get('bearish_periods')} periods\n\n"

        f"Volatility:      current={vol_data.get('current')}  "
        f"mean={vol_data.get('mean')}  "
        f"pct_above_avg={vol_data.get('pct_above_avg')}%\n\n"

        f"Trend (EMA):     bias={trend_data.get('current_bias')}  "
        f"EMA20={trend_data.get('current_ema20')} / "
        f"EMA50={trend_data.get('current_ema50')} / "
        f"EMA200={trend_data.get('current_ema200')}\n\n"

        f"CCI (20):        current={cci_data.get('current')}  "
        f"zone={cci_data.get('current_zone')}  "
        f"overbought={cci_data.get('overbought_periods')} / "
        f"oversold={cci_data.get('oversold_periods')} periods\n\n"

        f"MFI (14):        current={mfi_data.get('current')}  "
        f"zone={mfi_data.get('current_zone')}  "
        f"overbought={mfi_data.get('overbought_periods')} / "
        f"oversold={mfi_data.get('oversold_periods')} periods\n\n"

        f"ROC (10):        current={roc_data.get('current')}%  "
        f"momentum={roc_data.get('momentum')}"
    )

    report = ForexReport(
        symbol           = symbol,
        market_type      = get_market_type(symbol),
        trend            = trend,
        confidence       = validate_confidence(max(bullish, bearish)),
        technical_analysis = technical_analysis,
        ai_summary       = f"{symbol} analyzed successfully.",
    )

    save_analysis(report)
    return report.to_text()


def market_history(symbol: str) -> str:
    symbol  = normalize_symbol(symbol)
    reports = get_history(symbol)
    if not reports:
        return f"No history found for {symbol}"
    return "\n\n".join(r.to_text() for r in reports)


def compare_market_history(symbol: str, num_reports: int = 5) -> str:
    symbol = normalize_symbol(symbol)
    return compare_last_reports(symbol, num_reports)

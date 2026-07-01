"""
forex_models.py

Core enums, constants and validation models used by
Astra Forex Analytics.

Author: Nicolas Saez / Astra Project
"""

from __future__ import annotations

from enum import Enum
from typing import List


# ==========================================================
# MARKET TYPES
# ==========================================================

class MarketType(str, Enum):
    FOREX = "forex"
    COMMODITY = "commodity"
    UNKNOWN = "unknown"


# ==========================================================
# TREND TYPES
# ==========================================================

class Trend(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


# ==========================================================
# SIGNAL TYPES
# ==========================================================

class Signal(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"
    UNKNOWN = "unknown"


# ==========================================================
# ANALYSIS TYPES
# ==========================================================

class AnalysisType(str, Enum):
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    HYBRID = "hybrid"
    AI_ASSISTED = "ai_assisted"


# ==========================================================
# CONFIDENCE
# ==========================================================

MIN_CONFIDENCE = 0.0
MAX_CONFIDENCE = 1.0


def validate_confidence(value: float) -> float:
    """
    Clamp confidence value to valid range.

    Examples
    --------
    1.5 -> 1.0
    -0.2 -> 0.0
    0.83 -> 0.83
    """

    if value < MIN_CONFIDENCE:
        return MIN_CONFIDENCE

    if value > MAX_CONFIDENCE:
        return MAX_CONFIDENCE

    return round(value, 4)


# ==========================================================
# CONFIDENCE LABELS
# ==========================================================

def confidence_label(value: float) -> str:
    """
    Convert confidence score into
    human-friendly text.
    """

    value = validate_confidence(value)

    if value >= 0.90:
        return "very_high"

    if value >= 0.75:
        return "high"

    if value >= 0.60:
        return "moderate"

    if value >= 0.40:
        return "low"

    return "very_low"


# ==========================================================
# TREND HELPERS
# ==========================================================

def trend_from_score(score: float) -> Trend:
    """
    Convert directional score into trend.

    Range:
        -1.0 ... +1.0
    """

    if score >= 0.40:
        return Trend.BULLISH

    if score <= -0.40:
        return Trend.BEARISH

    if -0.15 <= score <= 0.15:
        return Trend.SIDEWAYS

    return Trend.NEUTRAL


# ==========================================================
# SIGNAL HELPERS
# ==========================================================

def signal_from_score(score: float) -> Signal:
    """
    Convert directional score into signal.

    Range:
        -1.0 ... +1.0
    """

    if score >= 0.80:
        return Signal.STRONG_BUY

    if score >= 0.40:
        return Signal.BUY

    if score <= -0.80:
        return Signal.STRONG_SELL

    if score <= -0.40:
        return Signal.SELL

    return Signal.HOLD


# ==========================================================
# REPORT VALIDATION
# ==========================================================

def validate_support_resistance(
    values: List[float]
) -> List[float]:
    """
    Remove invalid levels and sort them.
    """

    clean = []

    for value in values:

        try:
            numeric = float(value)

            if numeric > 0:
                clean.append(numeric)

        except Exception:
            continue

    return sorted(set(clean))


# ==========================================================
# SCORE NORMALIZATION
# ==========================================================

def normalize_score(score: float) -> float:
    """
    Force score into range [-1, 1].
    """

    if score > 1:
        return 1.0

    if score < -1:
        return -1.0

    return round(score, 4)


# ==========================================================
# DISPLAY HELPERS
# ==========================================================

def trend_emoji(trend: Trend) -> str:
    """
    Visual representation of trend.
    """

    mapping = {
        Trend.BULLISH: "📈",
        Trend.BEARISH: "📉",
        Trend.NEUTRAL: "⚖️",
        Trend.SIDEWAYS: "➡️",
        Trend.UNKNOWN: "❓",
    }

    return mapping.get(trend, "❓")


def signal_emoji(signal: Signal) -> str:
    """
    Visual representation of signal.
    """

    mapping = {
        Signal.STRONG_BUY: "🚀",
        Signal.BUY: "📈",
        Signal.HOLD: "⚖️",
        Signal.SELL: "📉",
        Signal.STRONG_SELL: "🔻",
        Signal.UNKNOWN: "❓",
    }

    return mapping.get(signal, "❓")


# ==========================================================
# DEFAULT CONFIG
# ==========================================================

DEFAULT_ANALYSIS_TYPE = AnalysisType.HYBRID

DEFAULT_TREND = Trend.UNKNOWN

DEFAULT_SIGNAL = Signal.UNKNOWN

DEFAULT_CONFIDENCE = 0.50


# ==========================================================
# TESTING
# ==========================================================

if __name__ == "__main__":

    test_scores = [
        -1.0,
        -0.7,
        -0.2,
        0.0,
        0.3,
        0.6,
        1.0,
    ]

    print("\nASTRA FOREX MODELS TEST\n")

    for score in test_scores:

        trend = trend_from_score(score)
        signal = signal_from_score(score)

        print(
            f"Score={score:>4} | "
            f"Trend={trend.value:<9} "
            f"{trend_emoji(trend)} | "
            f"Signal={signal.value:<12} "
            f"{signal_emoji(signal)}"
        )

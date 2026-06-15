"""
forex_report.py

Structured Forex Analysis Report for Astra.

Every Forex or commodity analysis should produce a ForexReport.

Author: Nicolas Saez / Astra Project
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any
import json


@dataclass
class ForexReport:
    """
    Standard analysis report used across Astra Forex Analytics.
    """

    symbol: str
    market_type: str

    trend: str = "unknown"
    confidence: float = 0.0

    technical_analysis: str = ""
    fundamental_analysis: str = ""

    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)

    news_items: List[str] = field(default_factory=list)

    ai_summary: str = ""

    source: str = "astra"

    created_at: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )

    metadata: Dict[str, Any] = field(default_factory=dict)

    # ======================================================
    # SERIALIZATION
    # ======================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert report into a dictionary.
        """

        return asdict(self)

    def to_json(self, indent: int = 4) -> str:
        """
        Convert report into JSON.
        """

        return json.dumps(
            self.to_dict(),
            indent=indent,
            ensure_ascii=False
        )

    # ======================================================
    # HUMAN FRIENDLY OUTPUT
    # ======================================================

    def to_text(self) -> str:
        """
        Convert report into a readable text report.
        """

        lines = [
            "=" * 60,
            "ASTRA FOREX ANALYSIS REPORT",
            "=" * 60,
            f"Market: {self.symbol}",
            f"Type: {self.market_type}",
            f"Trend: {self.trend}",
            f"Confidence: {self.confidence:.2f}",
            f"Created: {self.created_at}",
            "",
            "TECHNICAL ANALYSIS",
            "-" * 60,
            self.technical_analysis or "N/A",
            "",
            "FUNDAMENTAL ANALYSIS",
            "-" * 60,
            self.fundamental_analysis or "N/A",
            "",
            "SUPPORT LEVELS",
            "-" * 60,
            str(self.support_levels) if self.support_levels else "N/A",
            "",
            "RESISTANCE LEVELS",
            "-" * 60,
            str(self.resistance_levels) if self.resistance_levels else "N/A",
            "",
            "NEWS",
            "-" * 60,
        ]

        if self.news_items:
            for item in self.news_items:
                lines.append(f"• {item}")
        else:
            lines.append("N/A")

        lines.extend([
            "",
            "AI SUMMARY",
            "-" * 60,
            self.ai_summary or "N/A",
            "",
            "=" * 60
        ])

        return "\n".join(lines)

    # ======================================================
    # VALIDATION
    # ======================================================

    def is_valid(self) -> bool:
        """
        Basic validation.
        """

        return (
            bool(self.symbol)
            and bool(self.market_type)
            and 0.0 <= self.confidence <= 1.0
        )

    # ======================================================
    # SAVE HELPERS
    # ======================================================

    def save_json(self, filepath: str) -> None:
        """
        Save report as JSON.
        """

        with open(filepath, "w", encoding="utf-8") as file:
            file.write(self.to_json())

    def save_text(self, filepath: str) -> None:
        """
        Save report as text.
        """

        with open(filepath, "w", encoding="utf-8") as file:
            file.write(self.to_text())


# ==========================================================
# FACTORY HELPERS
# ==========================================================

def create_empty_report(
    symbol: str,
    market_type: str
) -> ForexReport:
    """
    Create an empty report skeleton.
    """

    return ForexReport(
        symbol=symbol,
        market_type=market_type,
    )


# ==========================================================
# TESTING
# ==========================================================

if __name__ == "__main__":

    report = ForexReport(
        symbol="EUR/USD",
        market_type="forex",
        trend="bullish",
        confidence=0.82,
        technical_analysis=(
            "Price remains above key moving averages."
        ),
        fundamental_analysis=(
            "ECB outlook supports euro strength."
        ),
        support_levels=[1.1450, 1.1400],
        resistance_levels=[1.1550, 1.1600],
        news_items=[
            "ECB official comments support rate stability.",
            "US inflation data released this week."
        ],
        ai_summary=(
            "Bullish bias while above support."
        ),
    )

    print(report.to_text())

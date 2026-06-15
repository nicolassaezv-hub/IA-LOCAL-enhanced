"""
forex_memory.py

Persistence layer for Astra Forex Analytics.

Stores, retrieves, lists and compares Forex analysis reports.

Author: Nicolas Saez / Astra Project
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from forex.forex_report import ForexReport


# ==========================================================
# STORAGE CONFIGURATION
# ==========================================================

BASE_DIR = Path("data") / "forex_analytics"

BASE_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# INTERNAL HELPERS
# ==========================================================

def _safe_filename(symbol: str) -> str:
    """
    EUR/USD -> EUR_USD
    Brent Crude Oil -> BRENT_CRUDE_OIL
    """

    return (
        symbol.upper()
        .replace("/", "_")
        .replace(" ", "_")
    )


def _market_directory(symbol: str) -> Path:
    """
    Returns the directory for a specific market.
    """

    market_dir = BASE_DIR / _safe_filename(symbol)

    market_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    return market_dir


# ==========================================================
# SAVE
# ==========================================================

def save_analysis(report: ForexReport) -> str:
    """
    Save a ForexReport as JSON.

    Returns:
        Path of saved file.
    """

    market_dir = _market_directory(
        report.symbol
    )

    timestamp = (
        report.created_at
        .replace(":", "-")
        .replace(".", "-")
    )

    filename = (
        f"{timestamp}.json"
    )

    filepath = market_dir / filename

    with open(
        filepath,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report.to_dict(),
            file,
            indent=4,
            ensure_ascii=False
        )

    return str(filepath)


# ==========================================================
# LOAD
# ==========================================================

def load_analysis(
    filepath: str
) -> ForexReport:
    """
    Load a saved report.
    """

    with open(
        filepath,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    return ForexReport(**data)


# ==========================================================
# HISTORY
# ==========================================================

def get_history(
    symbol: str
) -> List[ForexReport]:
    """
    Return all reports for a market.
    """

    market_dir = _market_directory(
        symbol
    )

    reports = []

    for file in sorted(
        market_dir.glob("*.json")
    ):

        try:

            reports.append(
                load_analysis(str(file))
            )

        except Exception:
            pass

    return reports


# ==========================================================
# LATEST REPORT
# ==========================================================

def get_latest_analysis(
    symbol: str
) -> Optional[ForexReport]:
    """
    Return latest report for a market.
    """

    reports = get_history(symbol)

    if not reports:
        return None

    return reports[-1]


# ==========================================================
# LIST MARKETS
# ==========================================================

def list_saved_markets() -> List[str]:
    """
    Returns all markets
    with stored analyses.
    """

    markets = []

    for folder in BASE_DIR.iterdir():

        if folder.is_dir():

            markets.append(
                folder.name
                .replace("_", "/")
            )

    return sorted(markets)


# ==========================================================
# COUNT REPORTS
# ==========================================================

def count_reports(
    symbol: str
) -> int:
    """
    Count reports for a market.
    """

    market_dir = _market_directory(
        symbol
    )

    return len(
        list(
            market_dir.glob("*.json")
        )
    )


# ==========================================================
# COMPARISON
# ==========================================================

def compare_last_reports(
    symbol: str,
    num_reports: int = 5
) -> str:
    """
    Compare recent reports.

    Returns human-readable text.
    """

    reports = get_history(symbol)

    if not reports:

        return (
            f"No analysis history "
            f"found for {symbol}."
        )

    reports = reports[-num_reports:]

    lines = [
        "=" * 60,
        f"ANALYSIS HISTORY: {symbol}",
        "=" * 60,
        ""
    ]

    for report in reports:

        lines.extend([
            f"Date: {report.created_at}",
            f"Trend: {report.trend}",
            f"Confidence: {report.confidence:.2f}",
            f"Summary: {report.ai_summary}",
            "-" * 60,
        ])

    return "\n".join(lines)


# ==========================================================
# DELETE
# ==========================================================

def delete_market_history(
    symbol: str
) -> int:
    """
    Delete all reports for a market.

    Returns:
        Number of deleted reports.
    """

    market_dir = _market_directory(
        symbol
    )

    files = list(
        market_dir.glob("*.json")
    )

    for file in files:

        try:
            file.unlink()

        except Exception:
            pass

    return len(files)


# ==========================================================
# STATS
# ==========================================================

def get_storage_stats() -> dict:
    """
    Returns overall storage statistics.
    """

    total_markets = 0
    total_reports = 0

    for folder in BASE_DIR.iterdir():

        if folder.is_dir():

            total_markets += 1

            total_reports += len(
                list(
                    folder.glob("*.json")
                )
            )

    return {
        "total_markets": total_markets,
        "total_reports": total_reports,
        "storage_directory": str(BASE_DIR)
    }


# ==========================================================
# TESTING
# ==========================================================

if __name__ == "__main__":

    print(
        "\nASTRA FOREX MEMORY"
    )

    print(
        get_storage_stats()
    )

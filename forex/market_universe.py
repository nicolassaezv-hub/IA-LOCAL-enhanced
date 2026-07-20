"""
market_universe.py

Central market definitions for Astra Forex Analytics.

This module is the single source of truth for all supported
Forex pairs and commodities available in Astra.

Author: Nicolas Saez / Astra Project
"""

from typing import Optional


# ============================================================
# SUPPORTED FOREX PAIRS
# ============================================================

FOREX_PAIRS = {
    "AUD/CAD",
    "AUD/CHF",
    "AUD/JPY",
    "AUD/NZD",
    "AUD/USD",
    "CAD/CHF",
    "CAD/JPY",
    "EUR/AUD",
    "EUR/CAD",
    "EUR/CHF",
    "EUR/GBP",
    "EUR/JPY",
    "EUR/MXN",
    "EUR/NOK",
    "EUR/NZD",
    "EUR/RUB",
    "EUR/SEK",
    "EUR/USD",
    "GBP/AUD",
    "GBP/CAD",
    "GBP/CHF",
    "GBP/JPY",
    "GBP/NZD",
    "GBP/USD",
    "NZD/CAD",
    "NZD/CHF",
    "NZD/JPY",
    "NZD/USD",
    "USD/CAD",
    "USD/CHF",
    "USD/CNH",
    "USD/HKD",
    "USD/INR",
    "USD/JPY",
    "USD/MXN",
    "USD/NOK",
    "USD/RUB",
    "USD/SEK",
    "USD/SGD",
    "USD/TRY",
    "USD/ZAR",
}


# ============================================================
# SUPPORTED COMMODITIES
# ============================================================

COMMODITIES = {
    "BRENT CRUDE OIL",
    "COCOA",
    "COFFEE",
    "COPPER",
    "CORN",
    "COTTON",
    "FCATTLE",
    "HEATING OIL",
    "LCATTLE",
    "LHOG",
    "NATURAL GAS",
    "OATS",
    "ORANGE JUICE",
    "RICE",
    "ROBUSTA COFFEE",
    "SOYBEAN",
    "SOYBEAN MEAL",
    "SUGAR",
    "WHEAT",
    "WTI CRUDE OIL",
}


# ============================================================
# COMMON USER ALIASES
# ============================================================

ALIASES = {
    # Forex
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "AUDUSD": "AUD/USD",
    "NZDUSD": "NZD/USD",
    "USDCAD": "USD/CAD",
    "USDCHF": "USD/CHF",
    "USDMXN": "USD/MXN",
    "USDTRY": "USD/TRY",
    "USDZAR": "USD/ZAR",
    "EURJPY": "EUR/JPY",
    "GBPJPY": "GBP/JPY",
    "NZDJPY": "NZD/JPY",
    "EURGBP": "EUR/GBP",
    "EURAUD": "EUR/AUD",
    "GBPAUD": "GBP/AUD",

    # Commodities
    "BRENT": "BRENT CRUDE OIL",
    "BRENT OIL": "BRENT CRUDE OIL",
    "WTI": "WTI CRUDE OIL",
    "WTI OIL": "WTI CRUDE OIL",
    "NATGAS": "NATURAL GAS",
    "GAS": "NATURAL GAS",
    "ROBUSTA": "ROBUSTA COFFEE",
    "FEEDER CATTLE": "FCATTLE",
    "LIVE CATTLE": "LCATTLE",
    "LEAN HOGS": "LHOG",
}


# ============================================================
# COMBINED MARKET SET
# ============================================================

ALL_MARKETS = FOREX_PAIRS.union(COMMODITIES)


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_symbol(symbol: str) -> str:
    """
    Normalize user market input.

    Examples
    --------
    eurusd
        -> EUR/USD

    Eur/Usd
        -> EUR/USD

    usdjpy
        -> USD/JPY

    brent
        -> BRENT CRUDE OIL

    natural gas
        -> NATURAL GAS
    """

    if not symbol:
        return ""

    symbol = symbol.strip().upper()

    # Alias lookup first
    if symbol in ALIASES:
        return ALIASES[symbol]

    # Remove spaces for forex pair detection
    compact = symbol.replace(" ", "")

    # EURUSD -> EUR/USD
    if len(compact) == 6 and "/" not in compact:
        possible_pair = f"{compact[:3]}/{compact[3:]}"
        if possible_pair in FOREX_PAIRS:
            return possible_pair

    return symbol


# ============================================================
# VALIDATION
# ============================================================

def is_supported_market(symbol: str) -> bool:
    """
    Check whether a market is supported by Astra.
    """

    normalized = normalize_symbol(symbol)
    return normalized in ALL_MARKETS


def is_forex_pair(symbol: str) -> bool:
    """
    Returns True if symbol is a supported Forex pair.
    """

    normalized = normalize_symbol(symbol)
    return normalized in FOREX_PAIRS


def is_commodity(symbol: str) -> bool:
    """
    Returns True if symbol is a supported commodity.
    """

    normalized = normalize_symbol(symbol)
    return normalized in COMMODITIES


# ============================================================
# MARKET TYPE
# ============================================================

def get_market_type(symbol: str) -> str:
    """
    Returns:
        'forex'
        'commodity'
        'unknown'
    """

    normalized = normalize_symbol(symbol)

    if normalized in FOREX_PAIRS:
        return "forex"

    if normalized in COMMODITIES:
        return "commodity"

    return "unknown"


# ============================================================
# LIST HELPERS
# ============================================================

def get_all_forex_pairs() -> list[str]:
    """
    Return all supported Forex pairs sorted alphabetically.
    """

    return sorted(FOREX_PAIRS)


def get_all_commodities() -> list[str]:
    """
    Return all supported commodities sorted alphabetically.
    """

    return sorted(COMMODITIES)


def get_all_markets() -> list[str]:
    """
    Return all supported markets sorted alphabetically.
    """

    return sorted(ALL_MARKETS)


# ============================================================
# SEARCH HELPERS
# ============================================================

def find_market(query: str) -> Optional[str]:
    """
    Attempts to find a supported market.

    Examples
    --------
    find_market("eurusd")
        -> EUR/USD

    find_market("brent")
        -> BRENT CRUDE OIL

    find_market("bitcoin")
        -> None
    """

    normalized = normalize_symbol(query)

    if normalized in ALL_MARKETS:
        return normalized

    return None


# ============================================================
# DEBUG / LOCAL TEST
# ============================================================

if __name__ == "__main__":
    tests = [
        "eurusd",
        "EUR/USD",
        "usdjpy",
        "brent",
        "natural gas",
        "btcusd",
    ]

    for item in tests:
        market = find_market(item)

        print(f"\nInput: {item}")

        if market:
            print(f"Market: {market}")
            print(f"Type: {get_market_type(market)}")
        else:
            print("Unsupported market")

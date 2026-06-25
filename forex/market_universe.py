"""
market_universe.py

Central market definitions for Astra Forex Analytics.

This module is the single source of truth for all supported
Forex pairs, commodities and crypto assets available in Astra,
plus the MT5 symbol-name mapping used by `creando.py` to build
the CSV datasets.

Author: Nicolas Saez / Astra Project
"""

from typing import Optional


# ============================================================
# SUPPORTED FOREX PAIRS
# ============================================================
# Display format uses "BASE/QUOTE". The MT5 broker symbol name
# (concatenated, no slash) is derived in MT5_SYMBOL_MAP below.

FOREX_PAIRS = {
    "AUD/CAD", "AUD/CHF", "AUD/JPY", "AUD/NZD", "AUD/USD",
    "CAD/CHF", "CAD/JPY",
    "CHF/JPY",
    "EUR/AUD", "EUR/CAD", "EUR/CHF", "EUR/CZK", "EUR/GBP",
    "EUR/HKD", "EUR/JPY", "EUR/MXN", "EUR/NZD", "EUR/PLN",
    "EUR/NOK", "EUR/RUB", "EUR/SEK", "EUR/TRY", "EUR/USD", "EUR/ZAR",
    "GBP/AUD", "GBP/CAD", "GBP/CHF", "GBP/JPY", "GBP/NZD",
    "GBP/SEK", "GBP/USD",
    "NZD/CAD", "NZD/CHF", "NZD/JPY", "NZD/USD",
    "USD/CAD", "USD/CHF", "USD/CNH", "USD/CZK", "USD/DKK",
    "USD/HKD", "USD/INR", "USD/JPY", "USD/MXN", "USD/NOK",
    "USD/PLN", "USD/RUB", "USD/SEK", "USD/SGD", "USD/TRY",
    "USD/ZAR",
}


# ============================================================
# SUPPORTED COMMODITIES
# ============================================================
# Display names (human readable). MT5 broker symbols mapped below.

COMMODITIES = {
    "BRENT CRUDE OIL",
    "COCOA",
    "CORN",
    "COTTON",
    "HEATING OIL",
    "LCATTLE",        # Live Cattle
    "LHOG",           # Lean Hogs
    "FCATTLE",        # Feeder Cattle
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
    "XAG/EUR",        # Silver vs EUR
    "XAG/USD",        # Silver vs USD
    "XAU/EUR",        # Gold vs EUR
    "XAU/USD",        # Gold vs USD
    "XAU/XAG",        # Gold vs Silver
    "XPD/USD",        # Palladium
    "XPT/USD",        # Platinum
    "XAU/OIL",
    "XAU/SNP",
}


# ============================================================
# SUPPORTED CRYPTO ASSETS
# ============================================================
# Quoted vs USD where applicable.

CRYPTO_ASSETS = {
    "ADA/USD",
    "BCH/USD",
    "BTC/USD",
    "DASH/USD",
    "DOGE/USD",
    "EOS/USD",
    "ETC/USD",
    "ETH/USD",
    "LTC/USD",
    "SOL/USD",
    "XLM/USD",
    "XMR/USD",
    "XRP/USD",
    "ZEC/USD",
}


# ============================================================
# MT5 SYMBOL NAME MAPPING
# ============================================================
# MT5 brokers use concatenated symbol names (no slash, no spaces).
# This map converts Astra display names -> MT5 symbol strings used
# by `creando.py` when calling mt5.copy_rates_range().
#
# If your broker uses a suffix/prefix (e.g. "EURUSD.r", "EURUSD.m"),
# adjust the values here only — the display names stay the same.

MT5_SYMBOL_MAP = {
    # Forex
    "AUD/CAD": "AUDCAD", "AUD/CHF": "AUDCHF", "AUD/JPY": "AUDJPY",
    "AUD/NZD": "AUDNZD", "AUD/USD": "AUDUSD",
    "CAD/CHF": "CADCHF", "CAD/JPY": "CADJPY",
    "CHF/JPY": "CHFJPY",
    "EUR/AUD": "EURAUD", "EUR/CAD": "EURCAD", "EUR/CHF": "EURCHF",
    "EUR/CZK": "EURCZK", "EUR/GBP": "EURGBP", "EUR/HKD": "EURHKD",
    "EUR/JPY": "EURJPY", "EUR/MXN": "EURMXN", "EUR/NZD": "EURNZD",
    "EUR/NOK": "EURNOK", "EUR/PLN": "EURPLN", "EUR/RUB": "EURRUB", "EUR/SEK": "EURSEK",
    "EUR/TRY": "EURTRY", "EUR/USD": "EURUSD", "EUR/ZAR": "EURZAR",
    "GBP/AUD": "GBPAUD", "GBP/CAD": "GBPCAD", "GBP/CHF": "GBPCHF",
    "GBP/JPY": "GBPJPY", "GBP/NZD": "GBPNZD", "GBP/SEK": "GBPSEK",
    "GBP/USD": "GBPUSD",
    "NZD/CAD": "NZDCAD", "NZD/CHF": "NZDCHF", "NZD/JPY": "NZDJPY",
    "NZD/USD": "NZDUSD",
    "USD/CAD": "USDCAD", "USD/CHF": "USDCHF", "USD/CNH": "USDCNH",
    "USD/CZK": "USDCZK", "USD/DKK": "USDDKK", "USD/HKD": "USDHKD",
    "USD/INR": "USDINR", "USD/JPY": "USDJPY", "USD/MXN": "USDMXN",
    "USD/NOK": "USDNOK", "USD/PLN": "USDPLN", "USD/RUB": "USDRUB",
    "USD/SEK": "USDSEK", "USD/SGD": "USDSGD", "USD/TRY": "USDTRY",
    "USD/ZAR": "USDZAR",

    # Commodities
    "BRENT CRUDE OIL": "BRENTUSD",
    "WTI CRUDE OIL":   "OILUSD",
    "NATURAL GAS":     "NATGASUSD",
    "HEATING OIL":     "HEATINGOIL",
    "COCOA":           "COCOA",
    "CORN":            "CORN",
    "COTTON":          "COTTON",
    "OATS":            "OATS",
    "ORANGE JUICE":    "ORANGEJUICE",
    "RICE":            "RICE",
    "ROBUSTA COFFEE":  "ROBUSTA",
    "SOYBEAN":         "SOYBEAN",
    "SOYBEAN MEAL":    "SOYBEANMEAL",
    "SUGAR":           "SUGAR",
    "WHEAT":           "WHEAT",
    "LCATTLE":         "LCATTLE",
    "LHOG":            "LHOG",
    "FCATTLE":         "FCATTLE",
    "XAG/EUR":         "XAGEUR",
    "XAG/USD":         "XAGUSD",
    "XAU/EUR":         "XAUEUR",
    "XAU/USD":         "XAUUSD",
    "XAU/XAG":         "XAUXAG",
    "XPD/USD":         "XPDUSD",
    "XPT/USD":         "XPTUSD",
    "XAU/OIL":         "XAUOIL",
    "XAU/SNP":         "XAUSNP",

    # Crypto
    "ADA/USD":  "ADAUSD",
    "BCH/USD":  "BCHUSD",
    "BTC/USD":  "BTCUSD",
    "DASH/USD": "DASHUSD",
    "DOGE/USD": "DOGEUSD",
    "EOS/USD":  "EOSUSD",
    "ETC/USD":  "ETCUSD",
    "ETH/USD":  "ETHUSD",
    "LTC/USD":  "LTCUSD",
    "SOL/USD":  "SOLUSD",
    "XLM/USD":  "XLMUSD",
    "XMR/USD":  "XMRUSD",
    "XRP/USD":  "XRPUSD",
    "ZEC/USD":  "ZECUSD",
}

# Flat ordered list of MT5 symbol strings — consumed by creando.py.
MT5_SYMBOLS = list(MT5_SYMBOL_MAP.values())


# ============================================================
# COMMON USER ALIASES
# ============================================================

ALIASES = {
    # Forex (concatenated -> display)
    "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "USDJPY": "USD/JPY",
    "AUDUSD": "AUD/USD", "NZDUSD": "NZD/USD", "USDCAD": "USD/CAD",
    "USDCHF": "USD/CHF", "USDMXN": "USD/MXN", "USDTRY": "USD/TRY",
    "USDZAR": "USD/ZAR", "EURJPY": "EUR/JPY", "GBPJPY": "GBP/JPY",
    "NZDJPY": "NZD/JPY", "EURGBP": "EUR/GBP", "EURAUD": "EUR/AUD",
    "GBPAUD": "GBP/AUD", "EURSEK": "EUR/SEK", "EURRUB": "EUR/RUB",
    "EURNOK": "EUR/NOK", "USDCNH": "USD/CNH", "USDHKD": "USD/HKD",
    "USDINR": "USD/INR", "USDNOK": "USD/NOK", "USDRUB": "USD/RUB",
    "USDSEK": "USD/SEK", "USDSGD": "USD/SGD", "EURMXN": "EUR/MXN",

    # Commodities
    "BRENT": "BRENT CRUDE OIL", "BRENT OIL": "BRENT CRUDE OIL",
    "WTI": "WTI CRUDE OIL", "WTI OIL": "WTI CRUDE OIL",
    "NATGAS": "NATURAL GAS", "GAS": "NATURAL GAS",
    "ROBUSTA": "ROBUSTA COFFEE",
    "FEEDER CATTLE": "FCATTLE", "LIVE CATTLE": "LCATTLE",
    "LEAN HOGS": "LHOG",
    "XAU": "XAU/USD", "GOLD": "XAU/USD",
    "XAG": "XAG/USD", "SILVER": "XAG/USD",
    "XPD": "XPD/USD", "PALLADIUM": "XPD/USD",
    "XPT": "XPT/USD", "PLATINUM": "XPT/USD",

    # Crypto
    "BTC": "BTC/USD", "BITCOIN": "BTC/USD",
    "ETH": "ETH/USD", "ETHEREUM": "ETH/USD",
    "XRP": "XRP/USD", "RIPPLE": "XRP/USD",
    "ADA": "ADA/USD", "CARDANO": "ADA/USD",
    "SOL": "SOL/USD", "SOLANA": "SOL/USD",
    "DOGE": "DOGE/USD", "DOGECOIN": "DOGE/USD",
    "LTC": "LTC/USD", "LITECOIN": "LTC/USD",
}


# ============================================================
# COMBINED MARKET SET
# ============================================================

ALL_MARKETS = FOREX_PAIRS.union(COMMODITIES).union(CRYPTO_ASSETS)


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_symbol(symbol: str) -> str:
    """
    Normalize user market input to a canonical display name.

    Examples
    --------
    eurusd        -> EUR/USD
    Eur/Usd       -> EUR/USD
    usdjpy        -> USD/JPY
    brent         -> BRENT CRUDE OIL
    natural gas   -> NATURAL GAS
    btcusd        -> BTC/USD
    """
    if not symbol:
        return ""

    symbol = symbol.strip().upper()

    # Alias lookup first
    if symbol in ALIASES:
        return ALIASES[symbol]

    # Remove spaces for forex pair detection
    compact = symbol.replace(" ", "")

    # 6-char concatenated symbols: EURUSD, BTCUSD, XAUUSD, XAGUSD, etc.
    if len(compact) == 6 and "/" not in compact:
        candidate = f"{compact[:3]}/{compact[3:]}"
        if candidate in FOREX_PAIRS:
            return candidate
        if candidate in COMMODITIES:
            return candidate
        if candidate in CRYPTO_ASSETS:
            return candidate

    return symbol


# ============================================================
# MT5 SYMBOL RESOLUTION
# ============================================================

def to_mt5_symbol(symbol: str) -> str:
    """
    Convert an Astra display name (or raw user input) into the
    MT5 broker symbol string used by creando.py.
    """
    normalized = normalize_symbol(symbol)
    return MT5_SYMBOL_MAP.get(normalized, normalized.replace("/", ""))


# ============================================================
# VALIDATION
# ============================================================

def is_supported_market(symbol: str) -> bool:
    normalized = normalize_symbol(symbol)
    return normalized in ALL_MARKETS


def is_forex_pair(symbol: str) -> bool:
    normalized = normalize_symbol(symbol)
    return normalized in FOREX_PAIRS


def is_commodity(symbol: str) -> bool:
    normalized = normalize_symbol(symbol)
    return normalized in COMMODITIES


def is_crypto(symbol: str) -> bool:
    normalized = normalize_symbol(symbol)
    return normalized in CRYPTO_ASSETS


# ============================================================
# MARKET TYPE
# ============================================================

def get_market_type(symbol: str) -> str:
    """
    Returns 'forex', 'commodity', 'crypto' or 'unknown'.
    """
    normalized = normalize_symbol(symbol)
    if normalized in FOREX_PAIRS:
        return "forex"
    if normalized in COMMODITIES:
        return "commodity"
    if normalized in CRYPTO_ASSETS:
        return "crypto"
    return "unknown"


# ============================================================
# LIST HELPERS
# ============================================================

def get_all_forex_pairs() -> list[str]:
    return sorted(FOREX_PAIRS)


def get_all_commodities() -> list[str]:
    return sorted(COMMODITIES)


def get_all_crypto() -> list[str]:
    return sorted(CRYPTO_ASSETS)


def get_all_markets() -> list[str]:
    return sorted(ALL_MARKETS)


# ============================================================
# SEARCH HELPERS
# ============================================================

def find_market(query: str) -> Optional[str]:
    normalized = normalize_symbol(query)
    if normalized in ALL_MARKETS:
        return normalized
    return None


# ============================================================
# DEBUG / LOCAL TEST
# ============================================================

if __name__ == "__main__":
    tests = [
        "eurusd", "EUR/USD", "usdjpy", "brent", "natural gas",
        "btcusd", "btc", "xauusd", "gold",
    ]
    for item in tests:
        market = find_market(item)
        print(f"\nInput: {item}")
        if market:
            print(f"Market: {market}")
            print(f"Type:   {get_market_type(market)}")
            print(f"MT5:    {to_mt5_symbol(market)}")
        else:
            print("Unsupported market")

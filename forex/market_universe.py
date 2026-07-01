"""
market_universe.py

Central market definitions for Astra Forex Analytics.

Author: Nicolas Saez / Astra Project
"""

from typing import Optional


# ============================================================
# SUPPORTED FOREX PAIRS
# ============================================================

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

COMMODITIES = {
    "BRENT CRUDE OIL",
    "COCOA",
    "CORN",
    "COTTON",
    "HEATING OIL",
    "LCATTLE",
    "LHOG",
    "FCATTLE",
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
    "XAG/EUR",
    "XAG/USD",
    "XAU/EUR",
    "XAU/USD",
    "XAU/XAG",
    "XPD/USD",
    "XPT/USD",
    "XAU/OIL",
    "XAU/SNP",
}

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
# MT5 SYMBOL NAME MAPPING (para cuando MT5 está disponible)
# ============================================================

MT5_SYMBOL_MAP = {
    "AUD/CAD": "AUDCAD", "AUD/CHF": "AUDCHF", "AUD/JPY": "AUDJPY",
    "AUD/NZD": "AUDNZD", "AUD/USD": "AUDUSD",
    "CAD/CHF": "CADCHF", "CAD/JPY": "CADJPY",
    "CHF/JPY": "CHFJPY",
    "EUR/AUD": "EURAUD", "EUR/CAD": "EURCAD", "EUR/CHF": "EURCHF",
    "EUR/CZK": "EURCZK", "EUR/GBP": "EURGBP", "EUR/HKD": "EURHKD",
    "EUR/JPY": "EURJPY", "EUR/MXN": "EURMXN", "EUR/NZD": "EURNZD",
    "EUR/NOK": "EURNOK", "EUR/PLN": "EURPLN", "EUR/RUB": "EURRUB",
    "EUR/SEK": "EURSEK", "EUR/TRY": "EURTRY", "EUR/USD": "EURUSD",
    "EUR/ZAR": "EURZAR",
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
    "ADA/USD":  "ADAUSD",  "BCH/USD":  "BCHUSD",  "BTC/USD":  "BTCUSD",
    "DASH/USD": "DASHUSD", "DOGE/USD": "DOGEUSD", "EOS/USD":  "EOSUSD",
    "ETC/USD":  "ETCUSD",  "ETH/USD":  "ETHUSD",  "LTC/USD":  "LTCUSD",
    "SOL/USD":  "SOLUSD",  "XLM/USD":  "XLMUSD",  "XMR/USD":  "XMRUSD",
    "XRP/USD":  "XRPUSD",  "ZEC/USD":  "ZECUSD",
}

MT5_SYMBOLS = list(MT5_SYMBOL_MAP.values())

# ============================================================
# YFINANCE TICKER MAP (fallback sin MT5)
# ============================================================
# Mapea el nombre display de Astra -> ticker de Yahoo Finance
# Solo se incluyen los pares que Yahoo Finance soporta con datos H1/D1 útiles

YFINANCE_TICKER_MAP = {
    # Forex majors & crosses (Yahoo usa sufijo =X)
    "EUR/USD": "EURUSD=X",  "GBP/USD": "GBPUSD=X",  "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",  "NZD/USD": "NZDUSD=X",  "USD/CAD": "USDCAD=X",
    "USD/CHF": "USDCHF=X",  "EUR/JPY": "EURJPY=X",  "GBP/JPY": "GBPJPY=X",
    "EUR/GBP": "EURGBP=X",  "EUR/AUD": "EURAUD=X",  "EUR/CAD": "EURCAD=X",
    "EUR/CHF": "EURCHF=X",  "EUR/NZD": "EURNZD=X",  "GBP/AUD": "GBPAUD=X",
    "GBP/CAD": "GBPCAD=X",  "GBP/CHF": "GBPCHF=X",  "GBP/NZD": "GBPNZD=X",
    "AUD/JPY": "AUDJPY=X",  "AUD/CAD": "AUDCAD=X",  "AUD/CHF": "AUDCHF=X",
    "AUD/NZD": "AUDNZD=X",  "NZD/JPY": "NZDJPY=X",  "NZD/CAD": "NZDCAD=X",
    "NZD/CHF": "NZDCHF=X",  "CAD/JPY": "CADJPY=X",  "CAD/CHF": "CADCHF=X",
    "CHF/JPY": "CHFJPY=X",  "USD/MXN": "USDMXN=X",  "USD/TRY": "USDTRY=X",
    "USD/ZAR": "USDZAR=X",  "USD/SEK": "USDSEK=X",  "USD/NOK": "USDNOK=X",
    "USD/HKD": "USDHKD=X",  "USD/SGD": "USDSGD=X",  "USD/CNH": "USDCNH=X",
    "EUR/SEK": "EURSEK=X",  "EUR/NOK": "EURNOK=X",  "EUR/TRY": "EURTRY=X",
    "EUR/ZAR": "EURZAR=X",  "EUR/MXN": "EURMXN=X",
    # Commodities (Yahoo usa contratos de futuros)
    "XAU/USD":       "GC=F",   # Gold futures
    "XAG/USD":       "SI=F",   # Silver futures
    "WTI CRUDE OIL": "CL=F",   # WTI Crude futures
    "BRENT CRUDE OIL":"BZ=F",  # Brent Crude futures
    "NATURAL GAS":   "NG=F",   # Natural Gas futures
    "CORN":          "ZC=F",   # Corn futures
    "WHEAT":         "ZW=F",   # Wheat futures
    "SOYBEAN":       "ZS=F",   # Soybean futures
    "SUGAR":         "SB=F",   # Sugar futures
    "COTTON":        "CT=F",   # Cotton futures
    "XPT/USD":       "PL=F",   # Platinum futures
    "XPD/USD":       "PA=F",   # Palladium futures
    # Crypto
    "BTC/USD":  "BTC-USD",
    "ETH/USD":  "ETH-USD",
    "XRP/USD":  "XRP-USD",
    "ADA/USD":  "ADA-USD",
    "SOL/USD":  "SOL-USD",
    "DOGE/USD": "DOGE-USD",
    "LTC/USD":  "LTC-USD",
    "BCH/USD":  "BCH-USD",
}

# ============================================================
# ALIASES
# ============================================================

ALIASES = {
    "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "USDJPY": "USD/JPY",
    "AUDUSD": "AUD/USD", "NZDUSD": "NZD/USD", "USDCAD": "USD/CAD",
    "USDCHF": "USD/CHF", "USDMXN": "USD/MXN", "USDTRY": "USD/TRY",
    "USDZAR": "USD/ZAR", "EURJPY": "EUR/JPY", "GBPJPY": "GBP/JPY",
    "NZDJPY": "NZD/JPY", "EURGBP": "EUR/GBP", "EURAUD": "EUR/AUD",
    "GBPAUD": "GBP/AUD", "EURSEK": "EUR/SEK", "EURRUB": "EUR/RUB",
    "EURNOK": "EUR/NOK", "USDCNH": "USD/CNH", "USDHKD": "USD/HKD",
    "USDINR": "USD/INR", "USDNOK": "USD/NOK", "USDRUB": "USD/RUB",
    "USDSEK": "USD/SEK", "USDSGD": "USD/SGD", "EURMXN": "EUR/MXN",
    "EURCAD": "EUR/CAD", "EURCHF": "EUR/CHF", "EURNZD": "EUR/NZD",
    "GBPCAD": "GBP/CAD", "GBPCHF": "GBP/CHF", "GBPNZD": "GBP/NZD",
    "AUDJPY": "AUD/JPY", "AUDCAD": "AUD/CAD", "AUDCHF": "AUD/CHF",
    "AUDNZD": "AUD/NZD", "NZDCAD": "NZD/CAD", "NZDCHF": "NZD/CHF",
    "CADJPY": "CAD/JPY", "CADCHF": "CAD/CHF", "CHFJPY": "CHF/JPY",
    "BRENT": "BRENT CRUDE OIL", "BRENT OIL": "BRENT CRUDE OIL",
    "WTI": "WTI CRUDE OIL", "WTI OIL": "WTI CRUDE OIL",
    "NATGAS": "NATURAL GAS", "GAS": "NATURAL GAS",
    "ROBUSTA": "ROBUSTA COFFEE",
    "FEEDER CATTLE": "FCATTLE", "LIVE CATTLE": "LCATTLE", "LEAN HOGS": "LHOG",
    "XAU": "XAU/USD", "GOLD": "XAU/USD",
    "XAG": "XAG/USD", "SILVER": "XAG/USD",
    "XPD": "XPD/USD", "PALLADIUM": "XPD/USD",
    "XPT": "XPT/USD", "PLATINUM": "XPT/USD",
    "BTC": "BTC/USD", "BITCOIN": "BTC/USD",
    "ETH": "ETH/USD", "ETHEREUM": "ETH/USD",
    "XRP": "XRP/USD", "RIPPLE": "XRP/USD",
    "ADA": "ADA/USD", "CARDANO": "ADA/USD",
    "SOL": "SOL/USD", "SOLANA": "SOL/USD",
    "DOGE": "DOGE/USD", "DOGECOIN": "DOGE/USD",
    "LTC": "LTC/USD", "LITECOIN": "LTC/USD",
}

ALL_MARKETS = FOREX_PAIRS.union(COMMODITIES).union(CRYPTO_ASSETS)


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_symbol(symbol: str) -> str:
    if not symbol:
        return ""
    symbol = symbol.strip().upper()
    if symbol in ALIASES:
        return ALIASES[symbol]
    compact = symbol.replace(" ", "")
    if len(compact) == 6 and "/" not in compact:
        candidate = f"{compact[:3]}/{compact[3:]}"
        if candidate in ALL_MARKETS:
            return candidate
    return symbol


def to_mt5_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    return MT5_SYMBOL_MAP.get(normalized, normalized.replace("/", ""))


def to_yfinance_ticker(symbol: str) -> Optional[str]:
    """Convierte nombre Astra -> ticker Yahoo Finance. None si no soportado."""
    normalized = normalize_symbol(symbol)
    return YFINANCE_TICKER_MAP.get(normalized)


def is_supported_market(symbol: str) -> bool:
    return normalize_symbol(symbol) in ALL_MARKETS


def is_supported_yfinance(symbol: str) -> bool:
    return to_yfinance_ticker(symbol) is not None


def is_forex_pair(symbol: str) -> bool:
    return normalize_symbol(symbol) in FOREX_PAIRS


def is_commodity(symbol: str) -> bool:
    return normalize_symbol(symbol) in COMMODITIES


def is_crypto(symbol: str) -> bool:
    return normalize_symbol(symbol) in CRYPTO_ASSETS


def get_market_type(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    if normalized in FOREX_PAIRS:
        return "forex"
    if normalized in COMMODITIES:
        return "commodity"
    if normalized in CRYPTO_ASSETS:
        return "crypto"
    return "unknown"


def get_all_forex_pairs() -> list:
    return sorted(FOREX_PAIRS)


def get_all_commodities() -> list:
    return sorted(COMMODITIES)


def get_all_crypto() -> list:
    return sorted(CRYPTO_ASSETS)


def find_market(text: str) -> Optional[str]:
    """Busca cualquier mercado conocido dentro de un texto libre."""
    text = text.strip().upper()
    if text in ALL_MARKETS:
        return text
    if text in ALIASES:
        return ALIASES[text]
    compact = text.replace(" ", "")
    if len(compact) == 6 and "/" not in compact:
        candidate = f"{compact[:3]}/{compact[3:]}"
        if candidate in ALL_MARKETS:
            return candidate
    return None

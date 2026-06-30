"""
market_universe.py — Universal market symbol registry for ASTRA.

Centralizes all supported forex pairs, commodities, and crypto assets
with mappings to MT5 symbols and Yahoo Finance tickers.

Functions:
  - get_all_forex_pairs()     -> list of forex pairs
  - get_all_commodities()     -> list of commodities
  - normalize_symbol(symbol)  -> standardized format (e.g., "EURUSD")
  - is_supported_market(sym)  -> True if in our universe
  - get_market_type(symbol)   -> "forex", "commodity", "crypto", or None
  - to_yfinance_ticker(symbol) -> Yahoo Finance ticker (e.g., "EURUSD=X")
  - to_mt5_symbol(symbol)     -> MT5 symbol (e.g., "EURUSD")

Author: Nicolas Saez / Astra Project
"""

from typing import Optional, List

# ==========================================================
# FOREX PAIRS (majors + crosses)
# ==========================================================

FOREX_PAIRS = [
    # Majors
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    # Euro crosses
    "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
    # GBP crosses
    "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
    # Other crosses
    "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
    "CADJPY", "CADCHF",
    "NZDJPY", "NZDCHF",
    # Scandinavian
    "USDSEK", "USDNOK", "USDTRY", "USDZAR",
    "EURSEK", "EURNOK", "EURTRY",
]

FOREX_PAIRS_ALIASES = {
    "EUR/USD": "EURUSD", "GBP/USD": "GBPUSD", "USD/JPY": "USDJPY",
    "USD/CHF": "USDCHF", "AUD/USD": "AUDUSD", "USD/CAD": "USDCAD",
    "NZD/USD": "NZDUSD", "EUR/GBP": "EURGBP", "EUR/JPY": "EURJPY",
    "GBP/JPY": "GBPJPY", "XAU/USD": "XAUUSD", "XAG/USD": "XAGUSD",
    "USD_JPY": "USDJPY", "EUR_USD": "EURUSD", "GBP_USD": "GBPUSD",
    "AUD_USD": "AUDUSD", "USD_CAD": "USDCAD", "XAU_USD": "XAUUSD", "XAG_USD": "XAGUSD",
}

# ==========================================================
# COMMODITIES (metals, energy, agriculture)
# ==========================================================

COMMODITIES = [
    "XAUUSD",  # Gold
    "XAGUSD",  # Silver
    "XPTUSD",  # Platinum
    "XPDUSD",  # Palladium
    "USOIL",   # WTI Crude Oil
    "UKOIL",   # Brent Crude Oil
    "NGAS",    # Natural Gas
]

COMMODITY_ALIASES = {
    "GOLD": "XAUUSD", "SILVER": "XAGUSD", "XAU": "XAUUSD", "XAG": "XAGUSD",
    "WTI": "USOIL", "CRUDE": "USOIL", "BRENT": "UKOIL", "OIL": "USOIL",
    "NATGAS": "NGAS", "NATURAL_GAS": "NGAS",
}

# ==========================================================
# CRYPTO (major pairs vs USD)
# ==========================================================

CRYPTO_ASSETS = [
    "BTCUSD", "ETHUSD", "XRPUSD", "LTCUSD",
    "ADAUSD", "SOLUSD", "DOGEUSD", "DOTUSD",
]

CRYPTO_ALIASES = {
    "BTC": "BTCUSD", "BITCOIN": "BTCUSD",
    "ETH": "ETHUSD", "ETHEREUM": "ETHUSD",
    "XRP": "XRPUSD", "RIPPLE": "XRPUSD",
    "LTC": "LTCUSD", "LITECOIN": "LTCUSD",
    "ADA": "ADAUSD", "CARDANO": "ADAUSD",
    "SOL": "SOLUSD", "SOLANA": "SOLUSD",
    "DOGE": "DOGEUSD", "DOGECOIN": "DOGEUSD",
    "DOT": "DOTUSD", "POLKADOT": "DOTUSD",
}

# ==========================================================
# YAHOO FINANCE TICKER MAP
# ==========================================================

YFINANCE_TICKER_MAP = {
    # Forex majors
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X", "AUDUSD": "AUDUSD=X", "USDCAD": "USDCAD=X",
    "NZDUSD": "NZDUSD=X",
    # Euro crosses
    "EURGBP": "EURGBP=X", "EURJPY": "EURJPY=X", "EURCHF": "EURCHF=X",
    "EURAUD": "EURAUD=X", "EURCAD": "EURCAD=X", "EURNZD": "EURNZD=X",
    # GBP crosses
    "GBPJPY": "GBPJPY=X", "GBPCHF": "GBPCHF=X", "GBPAUD": "GBPAUD=X",
    "GBPCAD": "GBPCAD=X", "GBPNZD": "GBPNZD=X",
    # Other crosses
    "AUDJPY": "AUDJPY=X", "AUDCHF": "AUDCHF=X", "AUDCAD": "AUDCAD=X",
    "NZDJPY": "NZDJPY=X", "NZDCHF": "NZDCHF=X",
    "CADJPY": "CADJPY=X", "CADCHF": "CADCHF=X",
    # Scandinavian
    "USDSEK": "USDSEK=X", "USDNOK": "USDNOK=X", "USDTRY": "USDTRY=X",
    "EURSEK": "EURSEK=X", "EURNOK": "EURNOK=X",
    # Commodities
    "XAUUSD": "GC=F", "XAGUSD": "SI=F", "USOIL": "CL=F", "UKOIL": "BZ=F", "NGAS": "NG=F",
    # Crypto
    "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD", "XRPUSD": "XRP-USD",
    "LTCUSD": "LTC-USD", "ADAUSD": "ADA-USD", "SOLUSD": "SOL-USD",
    "DOGEUSD": "DOGE-USD",
}

# ==========================================================
# MT5 SYMBOL MAP
# ==========================================================

MT5_SYMBOL_MAP = {
    "EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "USDJPY": "USDJPY",
    "USDCHF": "USDCHF", "AUDUSD": "AUDUSD", "USDCAD": "USDCAD",
    "NZDUSD": "NZDUSD", "EURGBP": "EURGBP", "EURJPY": "EURJPY",
    "GBPJPY": "GBPJPY", "XAUUSD": "XAUUSD", "XAGUSD": "XAGUSD",
    "USOIL": "USOIL", "UKOIL": "UKOIL", "BTCUSD": "BTCUSD", "ETHUSD": "ETHUSD",
}

MT5_SYMBOLS = list(MT5_SYMBOL_MAP.values())

# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def normalize_symbol(symbol: str) -> str:
    if not symbol:
        return "UNKNOWN"
    s = symbol.upper().replace("/", "").replace("_", "").replace("-", "")
    if s in FOREX_PAIRS_ALIASES: return FOREX_PAIRS_ALIASES[s]
    if s in COMMODITY_ALIASES: return COMMODITY_ALIASES[s]
    if s in CRYPTO_ALIASES: return CRYPTO_ALIASES[s]
    if s in FOREX_PAIRS or s in COMMODITIES or s in CRYPTO_ASSETS:
        return s
    return s

def is_supported_market(symbol: str) -> bool:
    s = normalize_symbol(symbol)
    return s in FOREX_PAIRS or s in COMMODITIES or s in CRYPTO_ASSETS

def get_market_type(symbol: str) -> Optional[str]:
    s = normalize_symbol(symbol)
    if s in FOREX_PAIRS: return "forex"
    if s in COMMODITIES: return "commodity"
    if s in CRYPTO_ASSETS: return "crypto"
    return None

def get_all_forex_pairs() -> List[str]:
    return FOREX_PAIRS.copy()

def get_all_commodities() -> List[str]:
    return COMMODITIES.copy()

def get_all_crypto() -> List[str]:
    return CRYPTO_ASSETS.copy()

def to_yfinance_ticker(symbol: str) -> Optional[str]:
    s = normalize_symbol(symbol)
    return YFINANCE_TICKER_MAP.get(s)

def to_mt5_symbol(symbol: str) -> Optional[str]:
    s = normalize_symbol(symbol)
    return MT5_SYMBOL_MAP.get(s)

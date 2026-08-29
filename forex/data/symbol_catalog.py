"""Canonical operational symbol catalog for ASTRA data acquisition."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Iterable


SUPPORTED_TIMEFRAMES = ("H1", "H4", "D1")
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{5,12}$")


class UnsupportedSymbolError(ValueError):
    """Raised when a symbol is not an exact canonical catalog entry."""


@dataclass(frozen=True)
class ProviderRoute:
    provider: str
    external_ticker: str
    provider_class: str


@dataclass(frozen=True)
class SymbolSpec:
    symbol_code: str
    display_name: str
    asset_class: str
    pip_value: float
    primary: ProviderRoute
    fallback: ProviderRoute | None = None
    secondary: ProviderRoute | None = None
    supported_timeframes: tuple[str, ...] = SUPPORTED_TIMEFRAMES
    legacy_default_active: bool = False
    blocked_routes: tuple[str, ...] = ()


def _mt5_yahoo_forex(
    code: str,
    display_name: str,
    pip_value: float,
    yahoo_ticker: str,
    *,
    legacy_default_active: bool = False,
) -> SymbolSpec:
    return SymbolSpec(
        symbol_code=code,
        display_name=display_name,
        asset_class="FOREX",
        pip_value=pip_value,
        primary=ProviderRoute("MT5", code, "BROKER"),
        secondary=ProviderRoute(
            "OANDA", f"{code[:3]}_{code[3:]}", "BROKER_REST"
        ),
        fallback=ProviderRoute("Yahoo", yahoo_ticker, "FX_REFERENCE"),
        legacy_default_active=legacy_default_active,
    )


def _mt5_only(
    code: str,
    display_name: str,
    asset_class: str,
    pip_value: float,
    *blocked_routes: str,
) -> SymbolSpec:
    return SymbolSpec(
        symbol_code=code,
        display_name=display_name,
        asset_class=asset_class,
        pip_value=pip_value,
        primary=ProviderRoute("MT5", code, "BROKER"),
        blocked_routes=tuple(blocked_routes),
    )


def _binance(code: str, pip_value: float) -> SymbolSpec:
    return SymbolSpec(
        symbol_code=code,
        display_name=f"{code[:-4]}/USDT",
        asset_class="CRYPTO",
        pip_value=pip_value,
        primary=ProviderRoute("Binance", code, "EXCHANGE"),
    )


def _index(code: str, display_name: str, yahoo_ticker: str) -> SymbolSpec:
    return SymbolSpec(
        symbol_code=code,
        display_name=display_name,
        asset_class="INDEX",
        pip_value=1.0,
        primary=ProviderRoute("MT5", code, "BROKER"),
        fallback=ProviderRoute("Yahoo", yahoo_ticker, "INDEX_REFERENCE"),
    )


_SPECS = (
    _mt5_yahoo_forex("EURUSD", "EUR/USD", 0.0001, "EURUSD=X", legacy_default_active=True),
    _mt5_yahoo_forex("GBPUSD", "GBP/USD", 0.0001, "GBPUSD=X", legacy_default_active=True),
    _mt5_yahoo_forex("USDJPY", "USD/JPY", 0.01, "JPY=X", legacy_default_active=True),
    _mt5_yahoo_forex("USDCHF", "USD/CHF", 0.0001, "CHF=X"),
    _mt5_yahoo_forex("AUDUSD", "AUD/USD", 0.0001, "AUDUSD=X", legacy_default_active=True),
    _mt5_yahoo_forex("NZDUSD", "NZD/USD", 0.0001, "NZDUSD=X"),
    _mt5_yahoo_forex("USDCAD", "USD/CAD", 0.0001, "CAD=X"),
    _mt5_yahoo_forex("EURGBP", "EUR/GBP", 0.0001, "EURGBP=X"),
    _mt5_yahoo_forex("EURJPY", "EUR/JPY", 0.01, "EURJPY=X"),
    _mt5_yahoo_forex("GBPJPY", "GBP/JPY", 0.01, "GBPJPY=X"),
    _mt5_yahoo_forex("AUDJPY", "AUD/JPY", 0.01, "AUDJPY=X"),
    _mt5_yahoo_forex("EURAUD", "EUR/AUD", 0.0001, "EURAUD=X"),
    _mt5_yahoo_forex("GBPAUD", "GBP/AUD", 0.0001, "GBPAUD=X"),
    _mt5_yahoo_forex("EURCHF", "EUR/CHF", 0.0001, "EURCHF=X"),
    _mt5_yahoo_forex("GBPCHF", "GBP/CHF", 0.0001, "GBPCHF=X"),
    _mt5_yahoo_forex("AUDCAD", "AUD/CAD", 0.0001, "AUDCAD=X"),
    _mt5_yahoo_forex("AUDCHF", "AUD/CHF", 0.0001, "AUDCHF=X"),
    _mt5_yahoo_forex("AUDNZD", "AUD/NZD", 0.0001, "AUDNZD=X"),
    _mt5_yahoo_forex("CADCHF", "CAD/CHF", 0.0001, "CADCHF=X"),
    _mt5_yahoo_forex("CADJPY", "CAD/JPY", 0.01, "CADJPY=X"),
    _mt5_yahoo_forex("CHFJPY", "CHF/JPY", 0.01, "CHFJPY=X"),
    _mt5_yahoo_forex("NZDCAD", "NZD/CAD", 0.0001, "NZDCAD=X"),
    _mt5_yahoo_forex("NZDCHF", "NZD/CHF", 0.0001, "NZDCHF=X"),
    _mt5_yahoo_forex("NZDJPY", "NZD/JPY", 0.01, "NZDJPY=X"),
    _mt5_yahoo_forex("EURCAD", "EUR/CAD", 0.0001, "EURCAD=X"),
    _mt5_yahoo_forex("EURNZD", "EUR/NZD", 0.0001, "EURNZD=X"),
    _mt5_yahoo_forex("GBPCAD", "GBP/CAD", 0.0001, "GBPCAD=X"),
    _mt5_yahoo_forex("GBPNZD", "GBP/NZD", 0.0001, "GBPNZD=X"),
    _mt5_only(
        "XAUUSD", "Gold spot/USD", "METAL", 0.01,
        "Yahoo GC=F is a gold future, not spot XAUUSD",
    ),
    _mt5_only(
        "XAGUSD", "Silver spot/USD", "METAL", 0.001,
        "Yahoo SI=F is a silver future, not spot XAGUSD",
    ),
    _mt5_only("XPTUSD", "Platinum spot/USD", "METAL", 0.01),
    _mt5_only(
        "USOUSD", "WTI oil/USD", "COMMODITY", 0.01,
        "Yahoo CL=F is a crude-oil future, not the broker instrument USOUSD",
    ),
    _mt5_only(
        "UKOUSD", "Brent oil/USD", "COMMODITY", 0.01,
        "Yahoo BZ=F is a Brent future, not the broker instrument UKOUSD",
    ),
    _index("SPX500", "S&P 500", "^GSPC"),
    _index("NAS100", "NASDAQ 100", "^NDX"),
    _index("GER40", "DAX 40", "^GDAXI"),
    _index("UK100", "FTSE 100", "^FTSE"),
    _index("JPN225", "Nikkei 225", "^N225"),
    _index("AUS200", "S&P/ASX 200", "^AXJO"),
    _binance("BTCUSDT", 0.01),
    _binance("ETHUSDT", 0.01),
    _binance("BNBUSDT", 0.01),
    _binance("SOLUSDT", 0.001),
    _binance("XRPUSDT", 0.0001),
    _binance("ADAUSDT", 0.0001),
    _binance("DOGEUSDT", 0.00001),
    _binance("AVAXUSDT", 0.001),
    _binance("MATICUSDT", 0.0001),
    _binance("DOTUSDT", 0.001),
    _binance("LTCUSDT", 0.01),
    _binance("LINKUSDT", 0.001),
    _binance("UNIUSDT", 0.001),
    _binance("ATOMUSDT", 0.001),
    _binance("NEARUSDT", 0.001),
)

SYMBOL_CATALOG = {spec.symbol_code: spec for spec in _SPECS}
if len(SYMBOL_CATALOG) != len(_SPECS):
    raise RuntimeError("Duplicate symbol_code in canonical symbol catalog")


def normalize_symbol_code(value: str) -> str:
    code = str(value or "").strip().upper()
    if not _SYMBOL_PATTERN.fullmatch(code):
        raise UnsupportedSymbolError(
            "Symbol must be an exact 5-12 character uppercase alphanumeric catalog code"
        )
    return code


def get_symbol_spec(value: str) -> SymbolSpec:
    code = normalize_symbol_code(value)
    try:
        return SYMBOL_CATALOG[code]
    except KeyError as exc:
        raise UnsupportedSymbolError(f"Unsupported canonical symbol: {code}") from exc


def symbols_by_asset_class(asset_class: str) -> tuple[str, ...]:
    expected = str(asset_class).upper()
    return tuple(
        spec.symbol_code
        for spec in _SPECS
        if spec.asset_class == expected
    )


def legacy_default_specs() -> tuple[SymbolSpec, ...]:
    return tuple(spec for spec in _SPECS if spec.legacy_default_active)


def route_for_provider(symbol: str, provider: str) -> ProviderRoute | None:
    spec = get_symbol_spec(symbol)
    expected = str(provider).lower()
    for route in provider_routes(spec):
        if route.provider.lower() == expected:
            return route
    return None


def provider_routes(value: SymbolSpec | str) -> tuple[ProviderRoute, ...]:
    """Return the catalog-authoritative provider order for one symbol."""
    spec = value if isinstance(value, SymbolSpec) else get_symbol_spec(value)
    return tuple(
        route
        for route in (spec.primary, spec.secondary, spec.fallback)
        if route is not None
    )


def catalog_codes() -> tuple[str, ...]:
    return tuple(spec.symbol_code for spec in _SPECS)


def operational_capabilities(value: str) -> dict[str, bool]:
    """Separate data routing from explicitly configured production ML support."""
    spec = get_symbol_spec(value)
    from forex.prediction.dataset_builder import is_ml_configured

    return {
        "data_supported": True,
        "ml_configured": is_ml_configured(spec.symbol_code),
    }


def _catalog_payload(specs: Iterable[SymbolSpec]) -> list[dict]:
    return [asdict(spec) for spec in specs]


CATALOG_VERSION = hashlib.sha256(
    json.dumps(
        _catalog_payload(_SPECS), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
).hexdigest()


__all__ = [
    "CATALOG_VERSION",
    "ProviderRoute",
    "SUPPORTED_TIMEFRAMES",
    "SYMBOL_CATALOG",
    "SymbolSpec",
    "UnsupportedSymbolError",
    "catalog_codes",
    "get_symbol_spec",
    "legacy_default_specs",
    "normalize_symbol_code",
    "operational_capabilities",
    "provider_routes",
    "route_for_provider",
    "symbols_by_asset_class",
]

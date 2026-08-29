"""
VI.7.D — Universal Data Router
Capa de abstracción: detecta el tipo de activo y enruta a la fuente correcta.
Un solo punto de entrada para todos los datos del sistema.
"""
import pandas as pd
import copy
from pathlib import Path
from typing import Optional

from forex.data.symbol_catalog import (
    UnsupportedSymbolError,
    get_symbol_spec,
    symbols_by_asset_class,
)


class DataProviderError(RuntimeError):
    """No configured real provider could return market data."""


_FOREX_PAIRS = set(symbols_by_asset_class("FOREX"))
_COMMODITY_PAIRS = set(symbols_by_asset_class("COMMODITY")) | set(
    symbols_by_asset_class("METAL")
)
_INDEX_PAIRS = set(symbols_by_asset_class("INDEX"))


def _detect_asset_type(pair: str) -> str:
    """
    Detecta si el par es Forex, Crypto, Commodity o Índice.
    Returns: 'forex' | 'crypto' | 'commodity' | 'index'
    """
    asset_class = get_symbol_spec(pair).asset_class
    return "commodity" if asset_class == "METAL" else asset_class.lower()


class DataRouter:
    """
    Router universal de datos.
    Uso: DataRouter(pair, tf).fetch(bars=500)
    Auto-detecta la fuente correcta y aplica fallback si falla.
    """

    def __init__(self, pair: str, tf: str = "H1"):
        self.spec = get_symbol_spec(pair)
        self.pair = self.spec.symbol_code
        self.tf = tf.upper()
        if self.tf not in self.spec.supported_timeframes:
            raise ValueError(f"Unsupported timeframe for {self.pair}: {self.tf}")
        self.asset_type = _detect_asset_type(self.pair)
        self._source_used: Optional[str] = None
        self._attempt_errors: list[str] = []
        self._last_acquisition_metadata: Optional[dict] = None

    def _capture_acquisition_metadata(
        self,
        provider,
        source: str,
        bars: int,
        frame,
    ) -> None:
        metadata = getattr(provider, "last_acquisition_metadata", None)
        if metadata is None and frame is not None:
            metadata = {
                "schema_version": 1,
                "provider": source,
                "symbol": self.pair,
                "timeframe": self.tf,
                "requested_bars": int(bars),
                "raw_closed_rows": int(len(frame)),
                "invalid_rows_dropped": 0,
                "valid_rows_before_tail": int(len(frame)),
                "returned_rows": int(len(frame)),
                "dropped_rows": [],
            }
        if metadata is not None:
            self._last_acquisition_metadata = copy.deepcopy(metadata)
            if isinstance(frame, pd.DataFrame):
                frame.attrs["acquisition_metadata"] = copy.deepcopy(metadata)

    def fetch(self, bars: int = 500, save_csv: bool = False,
              csv_dir: str = None,
              raise_on_failure: bool = False) -> Optional[pd.DataFrame]:
        """
        Descarga datos del activo.
        Enruta automáticamente a MT5 (forex), Yahoo (fallback) o Binance (crypto).
        """
        df = None
        self._attempt_errors = []
        self._last_acquisition_metadata = None

        if self.asset_type == "crypto":
            df, source = self._fetch_crypto(bars)
        else:
            df, source = self._fetch_forex(bars)

        self._source_used = source

        if df is None and raise_on_failure:
            detail = "; ".join(self._attempt_errors) or "no provider available"
            raise DataProviderError(
                f"DataRouter({self.pair}/{self.tf}) failed: {detail}"
            )

        if df is not None and save_csv:
            self._save(df, csv_dir)

        return df

    def _fetch_forex(self, bars: int) -> tuple[Optional[pd.DataFrame], str]:
        """Intenta MT5 primero, luego Yahoo."""
        for route in (self.spec.primary, self.spec.fallback):
            if route is None:
                continue
            try:
                if route.provider == "MT5":
                    from forex.data.mt5_provider import get_mt5_provider

                    provider = get_mt5_provider()
                    kwargs = {"allow_fallback": False}
                elif route.provider == "Yahoo":
                    from forex.data.yahoo_provider import get_yahoo_provider

                    provider = get_yahoo_provider()
                    kwargs = {}
                else:
                    self._attempt_errors.append(
                        f"Unsupported configured provider: {route.provider}"
                    )
                    continue
                if not provider.is_available():
                    self._attempt_errors.append(f"{route.provider} unavailable")
                    continue
                df = None
                try:
                    df = provider.fetch(self.pair, self.tf, bars, **kwargs)
                finally:
                    self._capture_acquisition_metadata(
                        provider, route.provider, bars, locals().get("df")
                    )
                if df is not None and len(df) > 0:
                    return df, route.provider
                self._attempt_errors.append(f"{route.provider} returned no data")
            except Exception as exc:
                self._attempt_errors.append(f"{route.provider}: {exc}")

        return None, "none"

    def _fetch_crypto(self, bars: int) -> tuple[Optional[pd.DataFrame], str]:
        """Use only explicit catalog routes; USD and USDT are never aliased."""
        for route in (self.spec.primary, self.spec.fallback):
            if route is None:
                continue
            try:
                if route.provider != "Binance":
                    self._attempt_errors.append(
                        f"Unsupported crypto provider: {route.provider}"
                    )
                    continue
                from forex.data.binance_provider import get_binance_provider

                provider = get_binance_provider()
                if not provider.is_available():
                    self._attempt_errors.append("Binance unavailable")
                    continue
                df = None
                try:
                    df = provider.fetch(self.pair, self.tf, bars)
                finally:
                    self._capture_acquisition_metadata(
                        provider, route.provider, bars, locals().get("df")
                    )
                if df is not None and len(df) > 0:
                    return df, "Binance"
                self._attempt_errors.append("Binance returned no data")
            except Exception as exc:
                self._attempt_errors.append(f"Binance: {exc}")

        return None, "none"

    @property
    def route_used(self):
        if not self._source_used or self._source_used == "none":
            return None
        for route in (self.spec.primary, self.spec.fallback):
            if route is not None and route.provider == self._source_used:
                return route
        return None

    def _save(self, df: pd.DataFrame, csv_dir: str = None):
        base = Path(csv_dir) if csv_dir else Path(__file__).parent.parent.parent / "CSVs" / self.tf
        base.mkdir(parents=True, exist_ok=True)
        out = base / f"{self.pair}.csv"
        df.to_csv(out, index=False)

    @property
    def source_used(self) -> Optional[str]:
        return self._source_used

    @property
    def attempt_errors(self) -> tuple[str, ...]:
        return tuple(self._attempt_errors)

    @property
    def last_acquisition_metadata(self) -> Optional[dict]:
        return copy.deepcopy(self._last_acquisition_metadata)

    def info(self) -> str:
        return (
            f"DataRouter({self.pair}/{self.tf}) "
            f"tipo={self.asset_type} "
            f"fuente={self._source_used or 'no consultada'}"
        )


def fetch_data(pair: str, tf: str = "H1", bars: int = 500,
               save_csv: bool = False) -> Optional[pd.DataFrame]:
    """Atajo rápido para obtener datos de cualquier activo."""
    router = DataRouter(pair, tf)
    return router.fetch(bars=bars, save_csv=save_csv)


__all__ = [
    "DataProviderError",
    "DataRouter",
    "UnsupportedSymbolError",
    "fetch_data",
]

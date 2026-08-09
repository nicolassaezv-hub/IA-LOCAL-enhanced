"""
VI.7.D — Universal Data Router
Capa de abstracción: detecta el tipo de activo y enruta a la fuente correcta.
Un solo punto de entrada para todos los datos del sistema.
"""
import pandas as pd
from pathlib import Path
from typing import Optional


_FOREX_PAIRS = {
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD",
    "USDCAD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURAUD",
    "GBPAUD", "EURCHF", "GBPCHF", "AUDCAD", "AUDCHF", "AUDNZD",
    "CADCHF", "CADJPY", "CHFJPY", "NZDCAD", "NZDCHF", "NZDJPY",
    "EURCAD", "EURNZD", "GBPCAD", "GBPNZD",
}
_COMMODITY_PAIRS = {"XAUUSD", "XAGUSD", "USOUSD", "UKOUSD", "XPTUSD"}
_INDEX_PAIRS = {"SPX500", "NAS100", "GER40", "UK100", "JPN225", "AUS200"}


def _detect_asset_type(pair: str) -> str:
    """
    Detecta si el par es Forex, Crypto, Commodity o Índice.
    Returns: 'forex' | 'crypto' | 'commodity' | 'index'
    """
    p = pair.upper().replace("_", "").replace("/", "")
    if p in _FOREX_PAIRS:
        return "forex"
    if p in _COMMODITY_PAIRS:
        return "commodity"
    if p in _INDEX_PAIRS:
        return "index"
    # Intentar detectar crypto
    try:
        from forex.data.binance_provider import is_crypto_pair
        if is_crypto_pair(p):
            return "crypto"
    except ImportError:
        pass
    # Default: tratar como forex si termina con moneda conocida
    forex_currencies = {"USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"}
    for c in forex_currencies:
        if p.endswith(c) or p.startswith(c):
            return "forex"
    return "forex"


class DataRouter:
    """
    Router universal de datos.
    Uso: DataRouter(pair, tf).fetch(bars=500)
    Auto-detecta la fuente correcta y aplica fallback si falla.
    """

    def __init__(self, pair: str, tf: str = "H1"):
        self.pair = pair.upper().replace("_", "")
        self.tf = tf.upper()
        self.asset_type = _detect_asset_type(self.pair)
        self._source_used: Optional[str] = None

    def fetch(self, bars: int = 500, save_csv: bool = False,
              csv_dir: str = None) -> Optional[pd.DataFrame]:
        """
        Descarga datos del activo.
        Enruta automáticamente a MT5 (forex), Yahoo (fallback) o Binance (crypto).
        """
        df = None

        if self.asset_type == "crypto":
            df, source = self._fetch_crypto(bars)
        else:
            df, source = self._fetch_forex(bars)

        self._source_used = source

        if df is not None and save_csv:
            self._save(df, csv_dir)

        return df

    def _fetch_forex(self, bars: int) -> tuple[Optional[pd.DataFrame], str]:
        """Intenta MT5 primero, luego Yahoo."""
        try:
            from forex.data.mt5_provider import get_mt5_provider
            mt5 = get_mt5_provider()
            if mt5.is_available():
                df = mt5.fetch(self.pair, self.tf, bars)
                if df is not None and len(df) > 0:
                    return df, "MT5"
        except Exception:
            pass

        try:
            from forex.data.yahoo_provider import get_yahoo_provider
            yp = get_yahoo_provider()
            if yp.is_available():
                df = yp.fetch(self.pair, self.tf, bars)
                if df is not None and len(df) > 0:
                    return df, "Yahoo"
        except Exception:
            pass

        return None, "none"

    def _fetch_crypto(self, bars: int) -> tuple[Optional[pd.DataFrame], str]:
        """Binance para crypto, Yahoo como fallback."""
        try:
            from forex.data.binance_provider import get_binance_provider
            bp = get_binance_provider()
            if bp.is_available():
                df = bp.fetch(self.pair, self.tf, bars)
                if df is not None and len(df) > 0:
                    return df, "Binance"
        except Exception:
            pass

        try:
            from forex.data.yahoo_provider import get_yahoo_provider
            yp = get_yahoo_provider()
            df = yp.fetch(self.pair, self.tf, bars)
            if df is not None and len(df) > 0:
                return df, "Yahoo"
        except Exception:
            pass

        return None, "none"

    def _save(self, df: pd.DataFrame, csv_dir: str = None):
        base = Path(csv_dir) if csv_dir else Path(__file__).parent.parent.parent / "CSVs" / self.tf
        base.mkdir(parents=True, exist_ok=True)
        out = base / f"{self.pair}.csv"
        df.to_csv(out, index=False)

    @property
    def source_used(self) -> Optional[str]:
        return self._source_used

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

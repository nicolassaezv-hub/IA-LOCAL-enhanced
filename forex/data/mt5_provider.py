"""
VI.7.A — MT5 Data Provider
Fuente primaria de datos Forex via MetaTrader 5 Python API.
Solo disponible en Windows con MT5 instalado.
Fallback automático a Yahoo Finance si MT5 no está disponible.
"""
import pandas as pd
from typing import Optional


_MT5_TIMEFRAMES = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "D1": 16408,
    "W1": 32769, "MN1": 49153,
}


def _is_mt5_available() -> bool:
    try:
        import MetaTrader5  # noqa
        return True
    except ImportError:
        return False


def _normalize_mt5_df(rates, pair: str) -> pd.DataFrame:
    """Convierte el array de MT5 al schema estándar ASTRA."""
    import pandas as pd
    df = pd.DataFrame(rates)
    df["timestamp"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={
        "open": "open", "high": "high", "low": "low",
        "close": "close", "tick_volume": "volume", "real_volume": "volume_real"
    })
    df["pair"] = pair.upper()
    df["volume"] = df.get("volume", df.get("tick_volume", 0))
    keep = ["timestamp", "open", "high", "low", "close", "volume", "pair"]
    return df[[c for c in keep if c in df.columns]].reset_index(drop=True)


class MT5Provider:
    """
    Proveedor principal de datos Forex via MetaTrader 5.
    Solo funciona en Windows con MT5 instalado y cuenta configurada.
    """

    def __init__(self):
        self._available = None
        self._initialized = False

    def is_available(self) -> bool:
        if self._available is None:
            self._available = _is_mt5_available()
        return self._available

    def _ensure_init(self) -> bool:
        if self._initialized:
            return True
        if not self.is_available():
            return False
        try:
            import MetaTrader5 as mt5
            if not mt5.initialize():
                return False
            self._initialized = True
            return True
        except Exception:
            return False

    def fetch(self, pair: str, tf: str = "H1", bars: int = 500) -> Optional[pd.DataFrame]:
        """
        Descarga datos históricos de MT5.
        Con fallback automático a Yahoo si MT5 no está disponible.
        """
        if not self._ensure_init():
            return self._fallback(pair, tf, bars)

        try:
            import MetaTrader5 as mt5
            tf_code = _MT5_TIMEFRAMES.get(tf.upper(), 16385)  # default H1
            rates = mt5.copy_rates_from_pos(pair.upper(), tf_code, 0, bars)
            if rates is None or len(rates) == 0:
                return self._fallback(pair, tf, bars)
            return _normalize_mt5_df(rates, pair)
        except Exception as e:
            print(f"[MT5Provider] Error: {e} — usando fallback Yahoo")
            return self._fallback(pair, tf, bars)

    def _fallback(self, pair: str, tf: str, bars: int) -> Optional[pd.DataFrame]:
        """Fallback a Yahoo Finance cuando MT5 no está disponible."""
        try:
            from forex.data.yahoo_provider import get_yahoo_provider
            yp = get_yahoo_provider()
            df = yp.fetch(pair, tf, bars)
            if df is not None:
                print(f"[MT5Provider] Usando Yahoo Finance como fallback para {pair}/{tf}")
            return df
        except Exception:
            return None

    def shutdown(self):
        if self._initialized and self.is_available():
            try:
                import MetaTrader5 as mt5
                mt5.shutdown()
                self._initialized = False
            except Exception:
                pass


_provider = MT5Provider()


def get_mt5_provider() -> MT5Provider:
    return _provider

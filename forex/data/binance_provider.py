"""
VI.7.C — Binance Crypto Provider
Datos de criptomonedas via python-binance (API pública, sin auth para datos históricos).
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional


_CRYPTO_PAIRS = {
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "MATICUSDT", "DOTUSDT",
    "LTCUSDT", "LINKUSDT", "UNIUSDT", "ATOMUSDT", "NEARUSDT",
}

_TF_MAP = {
    "M1": "1m", "M3": "3m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "1h", "H2": "2h", "H4": "4h", "H6": "6h", "H8": "8h",
    "H12": "12h", "D1": "1d", "W1": "1w", "MN1": "1M",
}

_BINANCE_BASE = "https://api.binance.com/api/v3/klines"


def is_crypto_pair(pair: str) -> bool:
    """Determina si un par es criptográfico."""
    p = pair.upper().replace("_", "").replace("/", "")
    if p in _CRYPTO_PAIRS:
        return True
    crypto_currencies = {"BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE",
                         "AVAX", "MATIC", "DOT", "LTC", "LINK", "UNI", "ATOM"}
    for c in crypto_currencies:
        if p.startswith(c) or p.endswith(c):
            return True
    return False


def _normalize_binance_klines(klines: list, pair: str) -> pd.DataFrame:
    """Convierte klines de Binance al schema estándar ASTRA."""
    cols = ["open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"]
    df = pd.DataFrame(klines, columns=cols)
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["pair"] = pair.upper()
    return df[["timestamp", "open", "high", "low", "close", "volume", "pair"]].reset_index(drop=True)


class BinanceProvider:
    """
    Proveedor de datos de criptomonedas via Binance API pública.
    No requiere API key para datos históricos.
    """

    def __init__(self):
        self._available = None

    def is_available(self) -> bool:
        if self._available is None:
            try:
                import requests  # noqa
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def fetch(self, pair: str, tf: str = "H1", bars: int = 500) -> Optional[pd.DataFrame]:
        """
        Descarga datos de Binance.
        pair: par crypto (BTCUSDT, ETHUSDT, etc.)
        tf: timeframe ASTRA (H1, H4, D1, etc.)
        bars: número de velas (máx 1000 por request)
        """
        if not self.is_available():
            return None

        try:
            import requests
        except ImportError:
            return None

        p = pair.upper().replace("_", "").replace("/", "")
        interval = _TF_MAP.get(tf.upper(), "1h")
        limit = min(bars, 1000)

        try:
            resp = requests.get(
                _BINANCE_BASE,
                params={"symbol": p, "interval": interval, "limit": limit},
                timeout=10
            )
            resp.raise_for_status()
            klines = resp.json()
            if not klines or isinstance(klines, dict):
                return None
            return _normalize_binance_klines(klines, pair)
        except Exception as e:
            print(f"[BinanceProvider] Error descargando {pair}/{tf}: {e}")
            return None

    def fetch_and_save(self, pair: str, tf: str = "H1", bars: int = 500,
                       csv_dir: str = None) -> Optional[str]:
        """Descarga y guarda en la ruta estándar CSVs/{tf}/{pair}.csv"""
        df = self.fetch(pair, tf, bars)
        if df is None:
            return None
        from pathlib import Path
        base = Path(csv_dir) if csv_dir else Path(__file__).parent.parent.parent / "CSVs" / tf.upper()
        base.mkdir(parents=True, exist_ok=True)
        out = base / f"{pair.upper()}.csv"
        df.to_csv(out, index=False)
        return str(out)

    def available_pairs_sample(self) -> list[str]:
        """Retorna una muestra de pares disponibles."""
        return sorted(list(_CRYPTO_PAIRS))


_provider = BinanceProvider()


def get_binance_provider() -> BinanceProvider:
    return _provider

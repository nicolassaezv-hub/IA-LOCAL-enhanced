"""
VI.7.C — Binance Crypto Provider
Datos de criptomonedas via python-binance (API pública, sin auth para datos históricos).
"""
import pandas as pd
from typing import Optional

from forex.data.symbol_catalog import get_symbol_spec, symbols_by_asset_class


_CRYPTO_PAIRS = set(symbols_by_asset_class("CRYPTO"))

_TF_MAP = {
    "M1": "1m", "M3": "3m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "1h", "H2": "2h", "H4": "4h", "H6": "6h", "H8": "8h",
    "H12": "12h", "D1": "1d", "W1": "1w", "MN1": "1M",
}

_BINANCE_BASE = "https://api.binance.com/api/v3/klines"


def is_crypto_pair(pair: str) -> bool:
    """Return True only for exact crypto instruments in the central catalog."""
    try:
        return get_symbol_spec(pair).asset_class == "CRYPTO"
    except ValueError:
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
        try:
            requested = max(1, int(bars))
            remaining = requested + 1  # one slot may be the current open kline
            end_time = None
            batches = []
            while remaining > 0:
                params = {
                    "symbol": p,
                    "interval": interval,
                    "limit": min(remaining, 1000),
                }
                if end_time is not None:
                    params["endTime"] = end_time
                resp = requests.get(_BINANCE_BASE, params=params, timeout=10)
                resp.raise_for_status()
                batch = resp.json()
                if not batch or isinstance(batch, dict):
                    break
                batches.extend(batch)
                remaining -= len(batch)
                oldest_open = int(batch[0][0])
                next_end_time = oldest_open - 1
                if len(batch) < params["limit"] or next_end_time == end_time:
                    break
                end_time = next_end_time

            if not batches:
                return None
            now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
            closed = [row for row in batches if int(row[6]) <= now_ms]
            if not closed:
                return None
            df = _normalize_binance_klines(closed, pair)
            return (df.drop_duplicates(subset=["timestamp"], keep="last")
                      .sort_values("timestamp")
                      .tail(requested)
                      .reset_index(drop=True))
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

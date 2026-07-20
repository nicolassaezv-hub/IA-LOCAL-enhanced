"""
VI.7.B — Yahoo Finance Provider
Descarga datos Forex e índices via yfinance. Fallback cuando MT5 no disponible.
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional


_FOREX_TICKER_MAP = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "JPY=X",
    "USDCHF": "CHFUSD=X", "AUDUSD": "AUDUSD=X", "NZDUSD": "NZDUSD=X",
    "USDCAD": "CAD=X",    "EURGBP": "EURGBP=X", "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X", "AUDJPY": "AUDJPY=X", "EURAUD": "EURAUD=X",
    "GBPAUD": "GBPAUD=X", "EURCHF": "EURCHF=X", "GBPCHF": "GBPCHF=X",
    "AUDCAD": "AUDCAD=X", "AUDCHF": "AUDCHF=X", "AUDNZD": "AUDNZD=X",
    "CADCHF": "CADCHF=X", "CADJPY": "CADJPY=X", "CHFJPY": "CHFJPY=X",
    "NZDCAD": "NZDCAD=X", "NZDCHF": "NZDCHF=X", "NZDJPY": "NZDJPY=X",
    "XAUUSD": "GC=F",     "XAGUSD": "SI=F",
    "USOUSD": "CL=F",     "UKOUSD": "BZ=F",
    "SPX500": "^GSPC",    "NAS100": "^NDX",     "GER40": "^GDAXI",
}

_TF_MAP = {
    "M1": "1m",   "M5": "5m",   "M15": "15m",  "M30": "30m",
    "H1": "1h",   "H4": "4h",   "D1": "1d",    "W1": "1wk",
}


def _to_yahoo_ticker(pair: str) -> str:
    p = pair.upper().replace("_", "")
    return _FOREX_TICKER_MAP.get(p, p)


def _to_yf_interval(tf: str) -> str:
    return _TF_MAP.get(tf.upper(), "1h")


def _normalize_df(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    """Convierte el DataFrame de yfinance al schema estándar de ASTRA."""
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    col_map = {
        "open": "open", "high": "high", "low": "low",
        "close": "close", "volume": "volume",
        "adj close": "close",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    df.index.name = "timestamp"
    df = df.reset_index()
    if "timestamp" not in df.columns:
        df.rename(columns={df.columns[0]: "timestamp"}, inplace=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)
    df["pair"] = pair.upper()
    for c in ["open", "high", "low", "close", "volume"]:
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    keep = ["timestamp", "open", "high", "low", "close", "volume", "pair"]
    return df[[c for c in keep if c in df.columns]].reset_index(drop=True)


class YahooProvider:
    """
    Proveedor de datos via yfinance.
    Fallback primario cuando MT5 no está disponible.
    """

    def __init__(self):
        self._available = None

    def is_available(self) -> bool:
        if self._available is None:
            try:
                import yfinance  # noqa
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def fetch(self, pair: str, tf: str = "H1", bars: int = 500) -> Optional[pd.DataFrame]:
        """
        Descarga datos de Yahoo Finance.
        pair: par en formato ASTRA (EURUSD, XAUUSD, etc.)
        tf: timeframe (M1, M5, M15, M30, H1, H4, D1, W1)
        bars: número de velas a descargar
        """
        if not self.is_available():
            return None

        try:
            import yfinance as yf
        except ImportError:
            return None

        ticker = _to_yahoo_ticker(pair)
        interval = _to_yf_interval(tf)

        # Calcular period según bars y timeframe
        bars_per_day = {"1m": 1440, "5m": 288, "15m": 96, "30m": 48,
                        "1h": 24, "4h": 6, "1d": 1, "1wk": 0.14}
        bpd = bars_per_day.get(interval, 24)
        days_needed = max(2, int(bars / max(bpd, 0.1)) + 5)

        # yfinance limite: datos intraday solo van 60 días atrás
        if interval in ("1m", "5m", "15m", "30m"):
            days_needed = min(days_needed, 59)

        start = (datetime.now() - timedelta(days=days_needed)).strftime("%Y-%m-%d")

        try:
            df_raw = yf.download(ticker, start=start, interval=interval,
                                 progress=False, auto_adjust=True)
            if df_raw is None or df_raw.empty:
                return None
            df = _normalize_df(df_raw, pair)
            return df.tail(bars).reset_index(drop=True)
        except Exception as e:
            print(f"[YahooProvider] Error descargando {pair}/{tf}: {e}")
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


_provider = YahooProvider()


def get_yahoo_provider() -> YahooProvider:
    return _provider

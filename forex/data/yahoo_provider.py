"""
VI.7.B — Yahoo Finance Provider
Descarga datos Forex e índices via yfinance. Fallback cuando MT5 no disponible.
"""
import pandas as pd
from datetime import datetime, timedelta
import copy
from typing import Optional

from forex.data.ohlc_contract import sanitize_ohlc_frame
from forex.data.symbol_catalog import SYMBOL_CATALOG, route_for_provider


_FOREX_TICKER_MAP = {
    code: route.external_ticker
    for code in SYMBOL_CATALOG
    if (route := route_for_provider(code, "Yahoo")) is not None
}
FOREX_TICKER_MAP = _FOREX_TICKER_MAP

_TF_MAP = {
    "M1": "1m",   "M5": "5m",   "M15": "15m",  "M30": "30m",
    "H1": "1h",   "H4": "1h",   "D1": "1d",    "W1": "1wk",  # H4 se resamplea desde 1h
}

_CANDLE_DURATION = {
    "M1": pd.Timedelta(minutes=1),
    "M5": pd.Timedelta(minutes=5),
    "M15": pd.Timedelta(minutes=15),
    "M30": pd.Timedelta(minutes=30),
    "H1": pd.Timedelta(hours=1),
    "D1": pd.Timedelta(days=1),
    "W1": pd.Timedelta(weeks=1),
}


class YahooDataContractError(RuntimeError):
    """Raised when Yahoo cannot satisfy the requested valid-bar contract."""


def _to_yahoo_ticker(pair: str) -> str:
    route = route_for_provider(pair, "Yahoo")
    if route is None:
        raise ValueError(f"No semantically exact Yahoo route for {pair}")
    return route.external_ticker


to_yahoo_ticker = _to_yahoo_ticker


def _to_yf_interval(tf: str) -> str:
    return _TF_MAP.get(tf.upper(), "1h")


def _normalize_df(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    """Convierte el DataFrame de yfinance al schema estándar de ASTRA."""
    df = df.copy()
    # yfinance >= 0.2.28 devuelve columnas MultiIndex (campo, ticker) -> aplanar
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
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
    keep = ["timestamp", "open", "high", "low", "close", "volume", "pair"]
    return df[[c for c in keep if c in df.columns]].reset_index(drop=True)


def _closed_before(df: pd.DataFrame, duration: pd.Timedelta,
                   now: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    """Conserva velas cuyo timestamp de apertura más duración ya cerró."""
    if df.empty or "timestamp" not in df.columns:
        return df
    cutoff = pd.Timestamp.now(tz="UTC").tz_localize(None) if now is None else pd.Timestamp(now)
    if cutoff.tzinfo is not None:
        cutoff = cutoff.tz_convert("UTC").tz_localize(None)
    timestamps = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)
    return df.loc[timestamps + duration <= cutoff].reset_index(drop=True)


def _resample_h4(df: pd.DataFrame,
                 now: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    """Agrega H1 en H4 y conserva únicamente bloques completos y cerrados."""
    if df.empty or "timestamp" not in df.columns:
        return df
    pair = df["pair"].iloc[-1] if "pair" in df.columns else ""
    indexed = df.copy()
    indexed["timestamp"] = pd.to_datetime(indexed["timestamp"], utc=True).dt.tz_localize(None)
    indexed = indexed.sort_values("timestamp").set_index("timestamp")
    out = (indexed
             .resample("4h")
             .agg({"open": "first", "high": "max", "low": "min",
                   "close": "last", "volume": "sum"})
             .dropna()
             .reset_index())
    complete_starts = [
        start
        for start, values in indexed["close"].resample("4h")
        if values.notna().all()
        and values.index.equals(pd.date_range(start, periods=4, freq="h"))
    ]
    out = out[out["timestamp"].isin(complete_starts)].reset_index(drop=True)
    out = _closed_before(out, pd.Timedelta(hours=4), now=now)
    out["pair"] = pair
    return out


class YahooProvider:
    """
    Proveedor de datos via yfinance.
    Fallback primario cuando MT5 no está disponible.
    """

    def __init__(self):
        self._available = None
        self._last_acquisition_metadata: Optional[dict] = None

    @property
    def last_acquisition_metadata(self) -> Optional[dict]:
        """Return provenance for the last attempted acquisition."""
        return copy.deepcopy(self._last_acquisition_metadata)

    @staticmethod
    def _metadata(
        pair: str,
        timeframe: str,
        bars: int,
        raw_closed_rows: int,
        valid_rows_before_tail: int,
        returned_rows: int,
        dropped_rows: list[dict],
    ) -> dict:
        return {
            "schema_version": 1,
            "provider": "Yahoo",
            "symbol": pair.upper(),
            "timeframe": timeframe.upper(),
            "requested_bars": int(bars),
            "raw_closed_rows": int(raw_closed_rows),
            "invalid_rows_dropped": int(len(dropped_rows)),
            "valid_rows_before_tail": int(valid_rows_before_tail),
            "returned_rows": int(returned_rows),
            "dropped_rows": dropped_rows,
        }

    @staticmethod
    def _sanitize_h4(df: pd.DataFrame) -> tuple[pd.DataFrame, int, list[dict]]:
        """Reject an H4 block when any source H1 row is contract-invalid."""
        h1_closed = _closed_before(df, pd.Timedelta(hours=1))
        _valid_h1, dropped_h1 = sanitize_ohlc_frame(h1_closed)
        raw_h4 = _resample_h4(h1_closed)
        affected: dict[pd.Timestamp, str] = {}
        for item in dropped_h1:
            block = pd.Timestamp(item["timestamp"]).floor("4h")
            affected.setdefault(block, item["reason"])

        valid_h4, invalid_h4 = sanitize_ohlc_frame(raw_h4)
        for item in invalid_h4:
            affected.setdefault(pd.Timestamp(item["timestamp"]), item["reason"])
        if affected:
            timestamps = pd.to_datetime(valid_h4["timestamp"])
            valid_h4 = valid_h4.loc[~timestamps.isin(affected)].reset_index(drop=True)
        dropped = [
            {"timestamp": timestamp.isoformat(), "reason": reason}
            for timestamp, reason in sorted(affected.items())
            if timestamp in set(pd.to_datetime(raw_h4["timestamp"]))
        ]
        return valid_h4, len(raw_h4), dropped

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
        self._last_acquisition_metadata = None
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
        needed_bars = bars * 4 if tf.upper() == "H4" else bars
        # Calendar-day headroom covers Forex weekends and holidays. H4 asks
        # for four H1 observations per output candle before closed-bar filtering.
        days_needed = max(2, int(needed_bars / max(bpd, 0.1) * 1.5) + 10)

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
            if tf.upper() == "H4":
                valid, raw_closed_rows, dropped = self._sanitize_h4(df)
            else:
                duration = _CANDLE_DURATION.get(tf.upper())
                closed = _closed_before(df, duration) if duration is not None else df
                raw_closed_rows = len(closed)
                valid, dropped = sanitize_ohlc_frame(closed)

            returned_rows = min(len(valid), bars)
            self._last_acquisition_metadata = self._metadata(
                pair,
                tf,
                bars,
                raw_closed_rows,
                len(valid),
                returned_rows,
                dropped,
            )
            if len(valid) < bars:
                raise YahooDataContractError(
                    "INSUFFICIENT_VALID_BARS_AFTER_SANITIZATION: "
                    f"{pair.upper()}/{tf.upper()} requested={bars} valid={len(valid)} "
                    f"raw_closed={raw_closed_rows} dropped={len(dropped)}"
                )
            result = valid.tail(bars).reset_index(drop=True)
            result.attrs["acquisition_metadata"] = self.last_acquisition_metadata
            return result
        except YahooDataContractError:
            raise
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


__all__ = [
    "FOREX_TICKER_MAP",
    "YahooDataContractError",
    "YahooProvider",
    "get_yahoo_provider",
    "to_yahoo_ticker",
]

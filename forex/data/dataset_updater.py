"""
V.11 — Actualizacion Inteligente de Datasets
=============================================
Reemplaza el flujo manual de creando.py por un sistema de actualizacion
incremental que descarga solo las velas nuevas, recalcula indicadores
afectados y mantiene los CSVs sincronizados.

Integracion:
    from forex.data.dataset_updater import DatasetUpdater
    updater = DatasetUpdater(data_dir="data/forex")
    result = updater.update_pair("EURUSD", "H1")
"""
from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

try:
    from colorama import Fore, Style
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

if HAS_COLOR:
    _C = lambda s: f"{Fore.CYAN}{s}{Style.RESET_ALL}"
    _G = lambda s: f"{Fore.GREEN}{s}{Style.RESET_ALL}"
    _Y = lambda s: f"{Fore.YELLOW}{s}{Style.RESET_ALL}"
    _R = lambda s: f"{Fore.RED}{s}{Style.RESET_ALL}"
    _B = lambda s: f"{Fore.BLUE}{s}{Style.RESET_ALL}"
else:
    _C = _G = _Y = _R = _B = lambda s: s


# ── yfinance timeframe mapping ──
YF_INTERVALS = {
    "H1": "1h",
    "H4": "60m",
    "D1": "1d",
}

YF_PERIODS = {
    "H1": "730d",
    "H4": "730d",
    "D1": "5y",
}

# ── Forex symbol suffix ──
YF_SUFFIX = "=X"


@dataclass
class UpdateResult:
    pair: str = ""
    timeframe: str = ""
    rows_before: int = 0
    rows_after: int = 0
    new_rows: int = 0
    last_timestamp: str = ""
    updated: bool = False
    error: str = ""
    duration_sec: float = 0.0

    def to_dict(self) -> dict:
        return {
            "pair": self.pair,
            "timeframe": self.timeframe,
            "rows_before": self.rows_before,
            "rows_after": self.rows_after,
            "new_rows": self.new_rows,
            "last_timestamp": self.last_timestamp,
            "updated": self.updated,
            "error": self.error,
            "duration_sec": round(self.duration_sec, 2),
        }


class DatasetUpdater:
    """Motor de actualizacion incremental de datasets forex."""

    def __init__(
        self,
        data_dir: str = "data/forex",
        db_path: str = "memoria.db",
        config: dict | None = None,
    ):
        self.data_dir = data_dir
        self.db_path = db_path
        self.config = config or {}
        os.makedirs(data_dir, exist_ok=True)

    # ── CSV path ──
    def _csv_path(self, pair: str, timeframe: str) -> str:
        return os.path.join(self.data_dir, f"{pair}_{timeframe}.csv")

    # ── Load existing CSV ──
    def _load_existing(self, pair: str, timeframe: str) -> pd.DataFrame | None:
        path = self._csv_path(pair, timeframe)
        if not os.path.exists(path):
            return None
        try:
            df = pd.read_csv(path)
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            elif "Datetime" in df.columns:
                df = df.rename(columns={"Datetime": "timestamp"})
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            return df
        except Exception:
            return None

    # ── Fetch from yfinance ──
    def _fetch_yfinance(
        self,
        pair: str,
        timeframe: str,
        start: str | None = None,
        period: str | None = None,
    ) -> pd.DataFrame | None:
        if not HAS_YFINANCE:
            return None
        symbol = pair.upper() + YF_SUFFIX
        interval = YF_INTERVALS.get(timeframe, "1h")
        try:
            if start:
                end = datetime.utcnow().strftime("%Y-%m-%d")
                raw = yf.download(symbol, start=start, end=end, interval=interval, progress=False)
            else:
                p = period or YF_PERIODS.get(timeframe, "730d")
                raw = yf.download(symbol, period=p, interval=interval, progress=False)
            if raw is None or raw.empty:
                return None
            raw = raw.reset_index()
            col_map = {
                "Datetime": "timestamp",
                "Date": "timestamp",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
            raw = raw.rename(columns={k: v for k, v in col_map.items() if k in raw.columns})
            if "timestamp" in raw.columns:
                raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True)
            for c in ["open", "high", "low", "close", "volume"]:
                if c not in raw.columns:
                    raw[c] = 0.0
            return raw[["timestamp", "open", "high", "low", "close", "volume"]]
        except Exception:
            return None

    # ── Filter weekend gaps ──
    def _filter_weekends(self, df: pd.DataFrame) -> pd.DataFrame:
        if "timestamp" not in df.columns:
            return df
        ts = pd.to_datetime(df["timestamp"], utc=True)
        mask = ts.dt.dayofweek < 5
        return df[mask].reset_index(drop=True)

    # ── Recalculate indicators (stubs for integration with feature_engineering) ──
    def _recalc_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            import numpy as np
            close = df["close"].values
            high = df["high"].values
            low = df["low"].values

            # RSI 14
            delta = np.diff(close, prepend=close[0])
            gain = np.where(delta > 0, delta, 0.0)
            loss = np.where(delta < 0, -delta, 0.0)
            avg_gain = pd.Series(gain).rolling(14, min_periods=1).mean()
            avg_loss = pd.Series(loss).rolling(14, min_periods=1).mean()
            rs = avg_gain / (avg_loss + 1e-10)
            df["rsi_14"] = 100 - (100 / (1 + rs))

            # EMA 20, 50, 150
            for p in [20, 50, 150]:
                df[f"ema_{p}"] = pd.Series(close).ewm(span=p, adjust=False).mean().values

            # MACD
            ema12 = pd.Series(close).ewm(span=12, adjust=False).mean()
            ema26 = pd.Series(close).ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9, adjust=False).mean()
            df["macd"] = macd.values
            df["macd_signal"] = signal.values
            df["macd_histogram"] = (macd - signal).values

            # ATR 14
            tr = np.maximum(
                high - low,
                np.maximum(
                    np.abs(high - np.roll(close, 1)),
                    np.abs(low - np.roll(close, 1)),
                ),
            )
            tr[0] = high[0] - low[0]
            df["atr_14"] = pd.Series(tr).rolling(14, min_periods=1).mean().values

            # ADX (simplified)
            plus_dm = np.where(
                (high - np.roll(high, 1)) > (np.roll(low, 1) - low),
                np.maximum(high - np.roll(high, 1), 0),
                0,
            )
            minus_dm = np.where(
                (np.roll(low, 1) - low) > (high - np.roll(high, 1)),
                np.maximum(np.roll(low, 1) - low, 0),
                0,
            )
            plus_di = 100 * pd.Series(plus_dm).rolling(14, min_periods=1).mean() / (pd.Series(tr).rolling(14, min_periods=1).mean() + 1e-10)
            minus_di = 100 * pd.Series(minus_dm).rolling(14, min_periods=1).mean() / (pd.Series(tr).rolling(14, min_periods=1).mean() + 1e-10)
            dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
            df["adx"] = pd.Series(dx).rolling(14, min_periods=1).mean().values

        except Exception:
            pass
        return df

    # ── Main update method ──
    def update_pair(
        self,
        pair: str,
        timeframe: str,
        force_full: bool = False,
    ) -> UpdateResult:
        start_time = time.time()
        result = UpdateResult(pair=pair, timeframe=timeframe)

        existing = self._load_existing(pair, timeframe)
        result.rows_before = len(existing) if existing is not None else 0

        if existing is not None and not existing.empty and not force_full:
            last_ts = existing["timestamp"].iloc[-1]
            start_date = (last_ts + timedelta(hours=1)).strftime("%Y-%m-%d")
            new_data = self._fetch_yfinance(pair, timeframe, start=start_date)
        else:
            new_data = self._fetch_yfinance(pair, timeframe)

        if new_data is None or new_data.empty:
            result.error = "No se pudieron obtener datos de yfinance"
            result.duration_sec = time.time() - start_time
            return result

        new_data = self._filter_weekends(new_data)

        if existing is not None and not existing.empty:
            combined = pd.concat([existing, new_data], ignore_index=True)
            combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
            combined = combined.sort_values("timestamp").reset_index(drop=True)
        else:
            combined = new_data

        combined = self._recalc_indicators(combined)

        result.rows_after = len(combined)
        result.new_rows = result.rows_after - result.rows_before
        result.last_timestamp = str(combined["timestamp"].iloc[-1]) if len(combined) > 0 else ""
        result.updated = result.new_rows > 0 or force_full

        path = self._csv_path(pair, timeframe)
        combined.to_csv(path, index=False)

        self._log_update(pair, timeframe, result)

        result.duration_sec = time.time() - start_time
        return result

    # ── Log to SQLite ──
    def _log_update(self, pair: str, timeframe: str, result: UpdateResult):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dataset_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair TEXT,
                    timeframe TEXT,
                    rows_before INTEGER,
                    rows_after INTEGER,
                    new_rows INTEGER,
                    timestamp TEXT,
                    duration_sec REAL
                )
            """)
            conn.execute(
                "INSERT INTO dataset_updates (pair, timeframe, rows_before, rows_after, new_rows, timestamp, duration_sec) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (pair, timeframe, result.rows_before, result.rows_after, result.new_rows, datetime.utcnow().isoformat(), result.duration_sec),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── Get last update info ──
    def get_last_update(self, pair: str, timeframe: str) -> dict | None:
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                "SELECT * FROM dataset_updates WHERE pair=? AND timeframe=? ORDER BY id DESC LIMIT 1",
                (pair, timeframe),
            ).fetchone()
            conn.close()
            if row:
                return {
                    "pair": row[1],
                    "timeframe": row[2],
                    "rows_before": row[3],
                    "rows_after": row[4],
                    "new_rows": row[5],
                    "timestamp": row[6],
                    "duration_sec": row[7],
                }
        except Exception:
            pass
        return None

    # ── Update multiple pairs ──
    def update_all(
        self,
        pairs: list[str] | None = None,
        timeframes: list[str] | None = None,
    ) -> list[UpdateResult]:
        pairs = pairs or ["EURUSD", "GBPUSD", "USDJPY"]
        timeframes = timeframes or ["H1", "H4", "D1"]
        results = []
        for pair in pairs:
            for tf in timeframes:
                r = self.update_pair(pair, tf)
                results.append(r)
        return results


# ── CLI ──
def cmd_dataset_update(args: str = "") -> str:
    """Comando CLI: dataset_update <pair> <timeframe> [data_dir]"""
    parts = args.strip().split()
    if len(parts) < 2:
        return "Uso: dataset_update <pair> <timeframe> [data_dir]"
    pair = parts[0].upper()
    timeframe = parts[1].upper()
    data_dir = parts[2] if len(parts) > 2 else "data/forex"
    updater = DatasetUpdater(data_dir=data_dir)
    result = updater.update_pair(pair, timeframe)
    if result.error:
        return f"{_R('Error')}: {result.error}"
    return (
        f"{_G('Dataset actualizado')} {pair} {timeframe}\n"
        f"  Filas: {result.rows_before} → {result.rows_after} ({_G(f'+{result.new_rows}')} nuevas)\n"
        f"  Ultima vela: {result.last_timestamp}\n"
        f"  Tiempo: {result.duration_sec:.2f}s"
    )


if __name__ == "__main__":
    print(cmd_dataset_update("EURUSD H1"))

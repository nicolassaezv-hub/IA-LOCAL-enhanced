"""
VI.6.A — Rolling Dataset Manager
Dataset de tamaño fijo con actualización incremental — sin reconstrucción completa.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional

_DEFAULT_MAX_ROWS = 5000
_TAIL_RECALC_ROWS = 60  # filas a recalcular al añadir una vela


class RollingDataset:
    """
    Mantiene un CSV de tamaño constante (max_rows).
    update(new_candle) añade 1 vela y elimina la más antigua.
    Solo recalcula los últimos K indicadores afectados.
    """

    def __init__(self, pair: str, tf: str, csv_dir: str = None,
                 max_rows: int = _DEFAULT_MAX_ROWS):
        self.pair = pair.upper()
        self.tf = tf.upper()
        self.max_rows = max_rows
        base = Path(csv_dir) if csv_dir else Path(__file__).parent.parent.parent / "CSVs" / tf.upper()
        base.mkdir(parents=True, exist_ok=True)
        self.csv_path = base / f"{self.pair}.csv"
        self._df: Optional[pd.DataFrame] = None

    def load(self) -> bool:
        """Carga el CSV en memoria. Devuelve True si existe."""
        if self.csv_path.exists():
            try:
                self._df = pd.read_csv(self.csv_path, parse_dates=["timestamp"])
                return True
            except Exception:
                self._df = None
                return False
        return False

    def initialize(self, df: pd.DataFrame) -> bool:
        """
        Crea el CSV inicial desde un DataFrame.
        Mantiene solo las últimas max_rows filas.
        """
        try:
            df = df.copy().tail(self.max_rows).reset_index(drop=True)
            self._df = df
            df.to_csv(self.csv_path, index=False)
            return True
        except Exception as e:
            print(f"[RollingDataset] Error inicializando {self.pair}: {e}")
            return False

    def update(self, new_candle: dict) -> bool:
        """
        Añade 1 vela nueva y elimina la más antigua.
        Luego recalcula los indicadores de la cola.
        """
        if self._df is None and not self.load():
            return False
        try:
            new_row = pd.DataFrame([new_candle])
            self._df = pd.concat([self._df, new_row], ignore_index=True)
            if len(self._df) > self.max_rows:
                self._df = self._df.tail(self.max_rows).reset_index(drop=True)
            self._recalculate_tail()
            self._df.to_csv(self.csv_path, index=False)
            return True
        except Exception as e:
            print(f"[RollingDataset] Error actualizando {self.pair}: {e}")
            return False

    def _recalculate_tail(self, k: int = _TAIL_RECALC_ROWS):
        """Recalcula solo los indicadores de las últimas k filas."""
        if self._df is None or len(self._df) < 2:
            return
        from forex.data.indicator_delta import recalculate_tail_indicators
        try:
            self._df = recalculate_tail_indicators(self._df, k)
        except Exception:
            pass

    def validate(self) -> dict:
        """Verifica integridad del dataset."""
        if self._df is None and not self.load():
            return {"ok": False, "error": "CSV no existe"}
        issues = []
        if len(self._df) == 0:
            issues.append("DataFrame vacío")
        required_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        missing = required_cols - set(self._df.columns)
        if missing:
            issues.append(f"Columnas faltantes: {missing}")
        if self._df.isnull().any().any():
            null_cols = self._df.columns[self._df.isnull().any()].tolist()
            issues.append(f"Valores nulos en: {null_cols}")
        return {
            "ok": len(issues) == 0,
            "rows": len(self._df),
            "max_rows": self.max_rows,
            "pair": self.pair,
            "tf": self.tf,
            "issues": issues,
            "last_ts": str(self._df["timestamp"].iloc[-1]) if "timestamp" in self._df.columns and len(self._df) > 0 else "N/A"
        }

    def get_df(self) -> Optional[pd.DataFrame]:
        if self._df is None:
            self.load()
        return self._df

    def info(self) -> str:
        v = self.validate()
        if not v["ok"]:
            return f"[RollingDataset] {self.pair}/{self.tf} ❌ {v.get('error', v.get('issues'))}"
        return (
            f"[RollingDataset] {self.pair}/{self.tf} ✅ "
            f"{v['rows']}/{v['max_rows']} filas — último: {v['last_ts']}"
        )


def get_rolling_dataset(pair: str, tf: str, csv_dir: str = None,
                        max_rows: int = _DEFAULT_MAX_ROWS) -> RollingDataset:
    return RollingDataset(pair, tf, csv_dir, max_rows)

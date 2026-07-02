"""
prediction_lab/dataset_analyzer.py — ASTRA Phase 5.2

Examina un DataFrame o ruta CSV y produce un DatasetAnalysis.
"""

from __future__ import annotations
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    missing_pct: float
    unique_count: int
    is_numeric: bool
    is_datetime: bool
    is_categorical: bool
    sample_values: List[Any]
    outlier_pct: float = 0.0


@dataclass
class DatasetAnalysis:
    rows: int
    columns: int
    column_profiles: List[ColumnProfile]
    numeric_cols: List[str]
    categorical_cols: List[str]
    datetime_cols: List[str]
    missing_pct_overall: float
    is_timeseries: bool
    datetime_col: Optional[str]
    target_candidates: List[str]
    class_balance: Optional[Dict[str, float]]
    duplicate_rows: int
    memory_mb: float
    predictive_signal: float
    warnings: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Filas       : {self.rows:,}",
            f"Columnas    : {self.columns}",
            f"Datos falt. : {self.missing_pct_overall:.1f}%",
            f"Duplicados  : {self.duplicate_rows}",
            f"Serie temp. : {'Sí' if self.is_timeseries else 'No'}" + (f"  ({self.datetime_col})" if self.datetime_col else ""),
            f"Señal pred. : {self.predictive_signal:.0%}",
            f"Numéricas   : {len(self.numeric_cols)}  cols",
            f"Categóricas : {len(self.categorical_cols)}  cols",
            f"Memoria     : {self.memory_mb:.1f} MB",
        ]
        if self.target_candidates:
            lines.append(f"Target cand.: {', '.join(self.target_candidates[:4])}")
        if self.class_balance:
            bal = "  |  ".join(f"{k}: {v:.1%}" for k, v in self.class_balance.items())
            lines.append(f"Balance     : {bal}")
        if self.warnings:
            lines.append("Avisos      : " + "; ".join(self.warnings))
        return "\n".join(lines)


class DatasetAnalyzer:
    def analyze(self, source: Any, target_col: Optional[str] = None) -> DatasetAnalysis:
        df = self._load(source)
        return self._run(df, target_col)

    def _load(self, source: Any) -> pd.DataFrame:
        if isinstance(source, pd.DataFrame):
            return source.copy()
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {source}")
        ext = path.suffix.lower()
        if ext == ".csv":
            return pd.read_csv(path, low_memory=False)
        if ext in (".xlsx", ".xls"):
            return pd.read_excel(path)
        raise ValueError(f"Formato no soportado: {ext}")

    def _run(self, df: pd.DataFrame, target_col: Optional[str]) -> DatasetAnalysis:
        warns: List[str] = []
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        datetime_cols = df.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()
        datetime_cols += self._find_datetime_cols(df, categorical_cols)
        datetime_cols = list(set(datetime_cols))
        profiles = [self._profile_col(df, c) for c in df.columns]
        missing_overall = df.isnull().mean().mean() * 100
        duplicates = df.duplicated().sum()
        memory_mb = df.memory_usage(deep=True).sum() / (1024 ** 2)
        is_ts, ts_col = self._detect_timeseries(df, datetime_cols)
        target_candidates = self._find_target_candidates(df, target_col, numeric_cols, categorical_cols)
        class_balance = self._compute_balance(df, target_col or (target_candidates[0] if target_candidates else None))
        signal = self._estimate_signal(df, numeric_cols, target_col)
        if missing_overall > 30:
            warns.append(f"Alta tasa de datos faltantes ({missing_overall:.1f}%)")
        if duplicates > 0:
            warns.append(f"{duplicates} filas duplicadas detectadas")
        if len(df) < 200:
            warns.append("Dataset muy pequeño (< 200 filas)")
        if signal < 0.30:
            warns.append("Señal predictiva baja")
        return DatasetAnalysis(
            rows=len(df), columns=len(df.columns), column_profiles=profiles,
            numeric_cols=numeric_cols, categorical_cols=categorical_cols,
            datetime_cols=datetime_cols, missing_pct_overall=round(missing_overall, 2),
            is_timeseries=is_ts, datetime_col=ts_col, target_candidates=target_candidates,
            class_balance=class_balance, duplicate_rows=int(duplicates),
            memory_mb=round(memory_mb, 2), predictive_signal=round(signal, 3), warnings=warns,
        )

    def _profile_col(self, df, col):
        s = df[col]
        is_numeric = pd.api.types.is_numeric_dtype(s)
        is_dt = pd.api.types.is_datetime64_any_dtype(s)
        is_cat = not is_numeric and not is_dt
        outlier_pct = 0.0
        if is_numeric:
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                mask = (s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)
                outlier_pct = round(mask.sum() / len(s) * 100, 2)
        return ColumnProfile(name=col, dtype=str(s.dtype), missing_pct=round(s.isnull().mean() * 100, 2),
            unique_count=int(s.nunique()), is_numeric=is_numeric, is_datetime=is_dt,
            is_categorical=is_cat, sample_values=s.dropna().head(5).tolist(), outlier_pct=outlier_pct)

    def _find_datetime_cols(self, df, text_cols):
        found = []
        dt_hints = {"time", "date", "fecha", "timestamp", "ts", "datetime"}
        for col in text_cols:
            if any(h in col.lower() for h in dt_hints):
                try:
                    pd.to_datetime(df[col].dropna().head(10))
                    found.append(col)
                except Exception:
                    pass
        return found

    def _detect_timeseries(self, df, dt_cols):
        if dt_cols:
            return True, dt_cols[0]
        for col in df.columns:
            if any(h in col.lower() for h in {"time", "date", "fecha", "ts", "timestamp"}):
                return True, col
        return False, None

    def _find_target_candidates(self, df, explicit, numeric, categorical):
        if explicit and explicit in df.columns:
            return [explicit]
        candidates = []
        label_hints = {"target", "label", "clase", "class", "output", "signal", "resultado", "y"}
        for col in df.columns:
            if col.lower() in label_hints or any(h in col.lower() for h in label_hints):
                candidates.append(col)
        if not candidates and numeric:
            candidates.append(numeric[-1])
        if not candidates and categorical:
            candidates.append(categorical[-1])
        return candidates[:4]

    def _compute_balance(self, df, col):
        if col is None or col not in df.columns:
            return None
        s = df[col].dropna()
        if s.nunique() > 20:
            return None
        counts = s.value_counts(normalize=True)
        return {str(k): round(v, 4) for k, v in counts.items()}

    def _estimate_signal(self, df, numeric_cols, target):
        if len(numeric_cols) < 2:
            return 0.3
        try:
            sub = df[numeric_cols].dropna()
            if len(sub) == 0:
                return 0.3
            stds = sub.std()
            means = sub.mean().abs().replace(0, 1e-9)
            cv = (stds / means).clip(0, 10)
            score = float(cv.mean()) / 10
            score = min(0.95, max(0.05, score))
            if target and target in df.columns and df[target].nunique() == 2:
                score = min(0.95, score + 0.10)
            return round(score, 3)
        except Exception:
            return 0.30


_analyzer = DatasetAnalyzer()


def analyze_dataset(source: Any, target_col: Optional[str] = None) -> DatasetAnalysis:
    return _analyzer.analyze(source, target_col)


def cmd_lab_examina(filepath: str) -> str:
    if not filepath:
        return "Uso: lab examina <archivo.csv>"
    try:
        analysis = analyze_dataset(filepath)
        return (
            f"\n{'═' * 56}\n"
            f"  ASTRA Prediction Lab — Análisis de Dataset\n"
            f"{'═' * 56}\n"
            f"{analysis.summary()}\n"
            f"{'═' * 56}"
        )
    except Exception as e:
        return f"Error analizando dataset: {e}"

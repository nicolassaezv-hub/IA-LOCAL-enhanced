"""
prediction_lab/dataset_analyzer.py — Fase 5.2 (Prediction Lab)

Analiza un dataset en profundidad y produce un DatasetReport con:
  - dimensiones (filas, columnas, tipos)
  - % de NaN por columna
  - balance del target (si es clasificación) o distribución (si es regresión)
  - correlaciones Pearson feature→target
  - multicolinealidad (VIF — Variance Inflation Factor, calculado con numpy puro,
    sin depender de statsmodels)
  - outliers por columna (IQR + z-score)
  - skewness / kurtosis por columna
  - un score de calidad 0-100 por dimensión + un score agregado

Este reporte alimenta directamente al Feasibility Engine (5.3), que decide
si con este dataset se puede construir un predictor útil.

Patrón "graceful fail": si el CSV no existe, está vacío, o el target no se
puede determinar, el reporte lo indica en vez de lanzar una excepción — el
caller (CLI o el propio pipeline de Prediction Lab) decide cómo reaccionar.

API pública:
  analyze_dataset(csv_path, target_variable=None, problem_spec=None) -> DatasetReport
  cmd_lab_dataset(csv_path, target_variable=None)                    -> str
"""

import os
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

import numpy as np
import pandas as pd

try:
    from scipy import stats as _scipy_stats
    _HAS_SCIPY = True
except Exception:
    _HAS_SCIPY = False


# ══════════════════════════════════════════════════════════
#  DATASET REPORT
# ══════════════════════════════════════════════════════════

@dataclass
class DatasetReport:
    csv_path:            str
    ok:                  bool = True
    error:               Optional[str] = None

    n_rows:              int = 0
    n_cols:              int = 0
    numeric_cols:        List[str] = field(default_factory=list)
    non_numeric_cols:    List[str] = field(default_factory=list)

    missing_pct:         Dict[str, float] = field(default_factory=dict)
    target_variable:     Optional[str] = None
    target_is_numeric:   bool = False
    target_balance:      Dict[str, Any] = field(default_factory=dict)   # clasificación
    target_distribution: Dict[str, Any] = field(default_factory=dict)   # regresión

    correlations:        Dict[str, float] = field(default_factory=dict)   # feature -> pearson r vs target
    top_correlated:      List[str] = field(default_factory=list)

    vif:                 Dict[str, float] = field(default_factory=dict)   # feature -> VIF
    high_vif_features:   List[str] = field(default_factory=list)          # VIF > 10

    outliers_pct:        Dict[str, float] = field(default_factory=dict)   # % filas outlier (IQR) por columna
    skewness:            Dict[str, float] = field(default_factory=dict)
    kurtosis:            Dict[str, float] = field(default_factory=dict)

    quality_scores:      Dict[str, float] = field(default_factory=dict)   # completeness, balance, signal, multicollinearity, outliers, distribution
    overall_quality:     float = 0.0
    warnings:            List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        if not self.ok:
            return f"[DATASET ANALYZER] Error: {self.error}"

        lines = [
            "═" * 62,
            " DATASET ANALYZER — Reporte",
            "═" * 62,
            f" Archivo          : {self.csv_path}",
            f" Filas x Columnas : {self.n_rows} x {self.n_cols}",
            f" Columnas numéricas   : {len(self.numeric_cols)}",
            f" Columnas no numéricas: {len(self.non_numeric_cols)}",
        ]

        if self.target_variable:
            lines.append(f" Target detectado : {self.target_variable}"
                         f" ({'numérico' if self.target_is_numeric else 'categórico'})")
            if self.target_balance:
                bal = ", ".join(f"{k}={v}" for k, v in self.target_balance.items() if k != "n_classes")
                lines.append(f" Balance target   : {bal}")
            if self.target_distribution:
                td = self.target_distribution
                lines.append(
                    f" Distribución target: media={td.get('mean', 0):.4f} "
                    f"std={td.get('std', 0):.4f} min={td.get('min', 0):.4f} max={td.get('max', 0):.4f}"
                )
        else:
            lines.append(" Target detectado : (ninguno — pasa target_variable explícitamente)")

        if self.top_correlated:
            lines.append(" Top correlaciones con target:")
            for c in self.top_correlated[:8]:
                lines.append(f"   {c:<25} r = {self.correlations.get(c, 0):+.3f}")

        if self.high_vif_features:
            lines.append(f" ⚠ Multicolinealidad alta (VIF>10): {', '.join(self.high_vif_features[:10])}")

        missing_top = sorted(self.missing_pct.items(), key=lambda x: -x[1])[:5]
        missing_top = [(c, p) for c, p in missing_top if p > 0]
        if missing_top:
            lines.append(" Columnas con más NaN:")
            for c, p in missing_top:
                lines.append(f"   {c:<25} {p:.1f}% faltante")

        outlier_top = sorted(self.outliers_pct.items(), key=lambda x: -x[1])[:5]
        outlier_top = [(c, p) for c, p in outlier_top if p > 0]
        if outlier_top:
            lines.append(" Columnas con más outliers (IQR):")
            for c, p in outlier_top:
                lines.append(f"   {c:<25} {p:.1f}% filas outlier")

        lines.append("-" * 62)
        lines.append(" Scores de calidad (0-100):")
        for dim, score in self.quality_scores.items():
            lines.append(f"   {dim:<18}: {score:5.1f}")
        lines.append(f" CALIDAD GENERAL   : {self.overall_quality:5.1f} / 100")

        if self.warnings:
            lines.append("-" * 62)
            lines.append(" Advertencias:")
            for w in self.warnings:
                lines.append(f"   ⚠ {w}")

        lines.append("═" * 62)
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════

_TARGET_NAME_HINTS = [
    "target", "label", "y", "class", "outcome", "churn", "signal",
    "direction", "result", "action",
]


def _guess_target(df: pd.DataFrame) -> Optional[str]:
    """Heurística simple: busca nombres comunes de target, si no, no adivina nada."""
    cols_lower = {c.lower(): c for c in df.columns}
    for hint in _TARGET_NAME_HINTS:
        if hint in cols_lower:
            return cols_lower[hint]
    return None


def _is_classification_target(series: pd.Series) -> bool:
    """Considera categórico si tiene pocos valores únicos relativo al total, o es no numérico."""
    if not pd.api.types.is_numeric_dtype(series):
        return True
    n_unique = series.nunique(dropna=True)
    return n_unique <= max(10, int(len(series) * 0.05))


def _compute_vif(X: pd.DataFrame, max_features: int = 20) -> Dict[str, float]:
    """
    VIF_i = 1 / (1 - R_i^2), donde R_i^2 sale de regresionar la feature i
    contra todas las demás (OLS vía numpy.linalg.lstsq — sin statsmodels).

    Para datasets con muchas columnas se limita a max_features (las de
    mayor varianza) para no volverse O(n^3) enproyectos con cientos de features.
    """
    cols = list(X.columns)
    if len(cols) > max_features:
        variances = X.var().sort_values(ascending=False)
        cols = list(variances.index[:max_features])
    X = X[cols].astype(float)

    vif = {}
    n = len(X)
    for col in cols:
        y = X[col].values
        others = [c for c in cols if c != col]
        if not others or n <= len(others) + 1:
            vif[col] = 1.0
            continue
        Xo = X[others].values
        Xo = np.column_stack([np.ones(n), Xo])
        try:
            coef, *_ = np.linalg.lstsq(Xo, y, rcond=None)
            y_pred = Xo @ coef
            ss_res = float(np.sum((y - y_pred) ** 2))
            ss_tot = float(np.sum((y - y.mean()) ** 2))
            r2 = 1 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
            r2 = max(0.0, min(r2, 0.999999))
            vif[col] = round(1.0 / (1.0 - r2), 2)
        except Exception:
            vif[col] = 1.0
    return vif


def _iqr_outlier_pct(series: pd.Series) -> float:
    s = series.dropna()
    if len(s) < 5:
        return 0.0
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return 0.0
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = ((s < lower) | (s > upper)).sum()
    return round(outliers / len(s) * 100, 2)


def _score_completeness(missing_pct: Dict[str, float]) -> float:
    if not missing_pct:
        return 100.0
    avg_missing = sum(missing_pct.values()) / len(missing_pct)
    return round(max(0.0, 100.0 - avg_missing * 2), 1)   # penaliza 2x el % promedio de NaN


def _score_balance(target_balance: dict, target_is_classification: bool) -> float:
    if not target_is_classification or not target_balance:
        return 100.0  # regresión no se evalúa por balance de clases
    pcts = [v for k, v in target_balance.items() if k != "n_classes" and isinstance(v, (int, float))]
    if not pcts:
        return 100.0
    n_classes = target_balance.get("n_classes", len(pcts))
    ideal = 100.0 / n_classes if n_classes else 50.0
    # Penaliza la desviación de la clase mayoritaria respecto al ideal
    max_pct = max(pcts)
    deviation = max_pct - ideal
    return round(max(0.0, 100.0 - deviation * 1.5), 1)


def _score_signal(correlations: Dict[str, float]) -> float:
    if not correlations:
        return 40.0   # sin target no se puede evaluar señal — score neutro-bajo
    abs_corrs = sorted((abs(v) for v in correlations.values()), reverse=True)
    top5 = abs_corrs[:5] if len(abs_corrs) >= 5 else abs_corrs
    avg_top = sum(top5) / len(top5) if top5 else 0.0
    return round(min(avg_top * 150, 100.0), 1)   # r=0.67 promedio en top5 -> 100


def _score_multicollinearity(vif: Dict[str, float]) -> float:
    if not vif:
        return 100.0
    high = [v for v in vif.values() if v > 10]
    pct_high = len(high) / len(vif) * 100
    return round(max(0.0, 100.0 - pct_high * 1.2), 1)


def _score_outliers(outliers_pct: Dict[str, float]) -> float:
    if not outliers_pct:
        return 100.0
    avg_outlier = sum(outliers_pct.values()) / len(outliers_pct)
    return round(max(0.0, 100.0 - avg_outlier * 3), 1)


def _score_distribution(skewness: Dict[str, float]) -> float:
    if not skewness:
        return 100.0
    avg_abs_skew = sum(abs(v) for v in skewness.values()) / len(skewness)
    return round(max(0.0, 100.0 - avg_abs_skew * 15), 1)


# ══════════════════════════════════════════════════════════
#  API PÚBLICA
# ══════════════════════════════════════════════════════════

def analyze_dataset(csv_path: str, target_variable: Optional[str] = None,
                     problem_spec=None) -> DatasetReport:
    """
    Analiza un CSV en profundidad.

    Parameters
    ----------
    csv_path        : ruta al archivo CSV
    target_variable : nombre de la columna objetivo (opcional — si no se
                       da, se intenta tomar de problem_spec o adivinar por nombre)
    problem_spec     : ProblemSpec opcional (de prompt_analyzer) — si trae
                       target_variable, tiene prioridad sobre la heurística
                       de adivinanza (pero no sobre un target_variable explícito).
    """
    if not csv_path or not os.path.exists(csv_path):
        return DatasetReport(csv_path=csv_path, ok=False,
                              error=f"Archivo no encontrado: {csv_path}")

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return DatasetReport(csv_path=csv_path, ok=False, error=f"No se pudo leer el CSV: {e}")

    if df.empty:
        return DatasetReport(csv_path=csv_path, ok=False, error="El CSV está vacío.")

    n_rows, n_cols = df.shape
    numeric_cols     = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    non_numeric_cols = [c for c in df.columns if c not in numeric_cols]

    missing_pct = {c: round(df[c].isna().mean() * 100, 2) for c in df.columns}

    # Resolver target: explícito > problem_spec > heurística por nombre.
    # En cada paso se valida que el candidato sea realmente una columna del
    # dataset — un target_variable "sucio" (ej. extraído mal por el LLM/heurístico
    # del Prompt Analyzer) nunca debe aceptarse solo porque no está vacío.
    target = target_variable if target_variable in df.columns else None
    if not target and problem_spec is not None:
        candidate = getattr(problem_spec, "target_variable", None)
        if candidate and candidate in df.columns:
            target = candidate
    if not target:
        target = _guess_target(df)

    warnings = []
    if n_rows < 200:
        warnings.append(f"Solo {n_rows} filas — puede ser insuficiente para entrenar un modelo robusto (recomendado: 300+).")

    target_is_numeric   = False
    target_balance      = {}
    target_distribution = {}
    correlations         = {}
    top_correlated       = []

    if target and target in df.columns:
        target_series = df[target]
        is_clf = _is_classification_target(target_series)
        target_is_numeric = pd.api.types.is_numeric_dtype(target_series) and not is_clf

        if is_clf:
            counts = target_series.value_counts(dropna=True)
            total  = counts.sum()
            target_balance = {str(k): round(v / total * 100, 2) for k, v in counts.items()}
            target_balance["n_classes"] = int(counts.shape[0])
        else:
            desc = target_series.describe()
            target_distribution = {
                "mean": float(desc.get("mean", 0.0)),
                "std":  float(desc.get("std", 0.0)),
                "min":  float(desc.get("min", 0.0)),
                "max":  float(desc.get("max", 0.0)),
            }

        # Correlaciones Pearson feature -> target (solo si target es numérico o binarizable)
        try:
            if pd.api.types.is_numeric_dtype(target_series):
                target_numeric = target_series
            else:
                target_numeric = pd.factorize(target_series)[0]
            feature_cols = [c for c in numeric_cols if c != target]
            for c in feature_cols:
                col_vals = df[c]
                mask = col_vals.notna() & pd.Series(target_numeric, index=df.index).notna()
                if mask.sum() < 5:
                    continue
                r = np.corrcoef(col_vals[mask], pd.Series(target_numeric, index=df.index)[mask])[0, 1]
                if not np.isnan(r):
                    correlations[c] = round(float(r), 4)
            top_correlated = sorted(correlations, key=lambda c: -abs(correlations[c]))
        except Exception:
            pass
    else:
        warnings.append("No se pudo determinar la variable objetivo — algunas métricas (balance, correlación, señal) no estarán disponibles.")

    # VIF sobre features numéricas (excluyendo el target)
    feature_cols_for_vif = [c for c in numeric_cols if c != target]
    vif = {}
    high_vif_features = []
    if len(feature_cols_for_vif) >= 2:
        X_vif = df[feature_cols_for_vif].replace([np.inf, -np.inf], np.nan).dropna()
        if len(X_vif) >= 10:
            vif = _compute_vif(X_vif)
            high_vif_features = sorted(
                [c for c, v in vif.items() if v > 10], key=lambda c: -vif[c]
            )

    # Outliers, skew, kurtosis por columna numérica
    outliers_pct = {}
    skewness     = {}
    kurtosis     = {}
    for c in numeric_cols:
        s = df[c].replace([np.inf, -np.inf], np.nan).dropna()
        if len(s) < 5:
            continue
        outliers_pct[c] = _iqr_outlier_pct(s)
        if _HAS_SCIPY:
            skewness[c] = round(float(_scipy_stats.skew(s)), 3)
            kurtosis[c] = round(float(_scipy_stats.kurtosis(s)), 3)
        else:
            skewness[c] = round(float(s.skew()), 3)
            kurtosis[c] = round(float(s.kurt()), 3)

    if high_vif_features:
        warnings.append(f"{len(high_vif_features)} features con multicolinealidad alta (VIF>10) — considera eliminarlas o combinarlas.")

    target_is_classification = bool(target_balance)
    quality_scores = {
        "completeness":       _score_completeness(missing_pct),
        "balance":            _score_balance(target_balance, target_is_classification),
        "signal":             _score_signal(correlations),
        "multicollinearity":  _score_multicollinearity(vif),
        "outliers":           _score_outliers(outliers_pct),
        "distribution":       _score_distribution(skewness),
    }
    overall_quality = round(sum(quality_scores.values()) / len(quality_scores), 1)

    return DatasetReport(
        csv_path=csv_path,
        ok=True,
        n_rows=n_rows,
        n_cols=n_cols,
        numeric_cols=numeric_cols,
        non_numeric_cols=non_numeric_cols,
        missing_pct=missing_pct,
        target_variable=target,
        target_is_numeric=target_is_numeric,
        target_balance=target_balance,
        target_distribution=target_distribution,
        correlations=correlations,
        top_correlated=top_correlated,
        vif=vif,
        high_vif_features=high_vif_features,
        outliers_pct=outliers_pct,
        skewness=skewness,
        kurtosis=kurtosis,
        quality_scores=quality_scores,
        overall_quality=overall_quality,
        warnings=warnings,
    )


def cmd_lab_dataset(csv_path: str, target_variable: Optional[str] = None) -> str:
    """Comando CLI: 'lab dataset <archivo.csv>' — para wiring en main.py."""
    if not csv_path or not csv_path.strip():
        return "Uso: lab dataset <archivo.csv> [target_variable]"
    report = analyze_dataset(csv_path.strip(), target_variable=target_variable)
    return report.summary()

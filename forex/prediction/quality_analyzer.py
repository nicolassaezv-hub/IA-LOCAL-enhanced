"""
Dataset Quality Analyzer — V.5 Roadmap V
==========================================
Gate de calidad obligatorio antes de cualquier entrenamiento.
Si el dataset no cumple los estandares minimos, el entrenamiento
se detendra con un informe detallado de los problemas encontrados.

Evalua:
  - Valores faltantes y huecos temporales
  - Outliers estadisticos por columna
  - Filas duplicadas o inconsistentes
  - Balance de clases (BUY/SELL/HOLD)
  - Cobertura temporal minima
  - Calidad de indicadores tecnicos

Integracion: IntegratedPipeline.train() debe llamar a QualityAnalyzer.analyze()
antes de entrenar. Si report.approved == False, bloquear entrenamiento.
"""

from __future__ import annotations

import math
import os
from typing import Any

import numpy as np
import pandas as pd

from forex.prediction.quality_report import QualityReport, QualityIssue


class QualityAnalyzer:
    """Motor de analisis de calidad de datasets para entrenamiento ML."""

    # Thresholds configurables
    DEFAULTS = {
        "min_rows": 200,
        "max_missing_pct": 15.0,
        "max_outlier_pct": 10.0,
        "max_duplicate_pct": 5.0,
        "min_class_pct": 5.0,
        "min_temporal_coverage_pct": 80.0,
        "min_score": 60.0,
    }

    def __init__(self, config: dict | None = None):
        self.config = {**self.DEFAULTS, **(config or {})}

    def analyze(self, df: pd.DataFrame, pair: str = "", timeframe: str = "") -> QualityReport:
        """Analiza un DataFrame y retorna un QualityReport completo."""
        report = QualityReport()
        report.dataset_info = self._collect_dataset_info(df, pair, timeframe)

        if len(df) == 0:
            report.issues.append(QualityIssue(
                severity="critical", category="empty_dataset", column="*",
                description="El dataset esta vacio (0 filas).",
                suggestion="Proporcionar un CSV con datos validos.",
            ))
            self._finalize(report)
            return report

        self._check_missing_values(df, report)
        self._check_outliers(df, report)
        self._check_duplicates(df, report)
        self._check_temporal_coverage(df, report)
        self._check_class_balance(df, report)
        self._check_technical_indicators(df, report)
        self._check_row_count(df, report)

        self._finalize(report)
        return report

    def analyze_csv(self, filepath: str, pair: str = "", timeframe: str = "") -> QualityReport:
        """Carga un CSV y lo analiza."""
        try:
            df = pd.read_csv(filepath)
            return self.analyze(df, pair=pair, timeframe=timeframe)
        except Exception as e:
            report = QualityReport()
            report.issues.append(QualityIssue(
                severity="critical", category="file_error", column="*",
                description=f"No se pudo cargar el archivo: {e}",
                suggestion="Verificar que el archivo existe y tiene formato CSV valido.",
            ))
            self._finalize(report)
            return report

    def _collect_dataset_info(self, df: pd.DataFrame, pair: str, timeframe: str) -> dict:
        info = {
            "pair": pair,
            "timeframe": timeframe,
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": list(df.columns),
            "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
        }
        if "timestamp" in df.columns:
            try:
                ts = pd.to_datetime(df["timestamp"])
                info["date_start"] = str(ts.iloc[0])
                info["date_end"] = str(ts.iloc[-1])
                info["date_range_days"] = (ts.iloc[-1] - ts.iloc[0]).days
            except Exception:
                pass
        return info

    def _check_missing_values(self, df: pd.DataFrame, report: QualityReport) -> None:
        """Valores faltantes y huecos temporales."""
        for col in df.columns:
            missing = df[col].isna().sum()
            if missing == 0:
                continue
            pct = (missing / len(df)) * 100
            severity = "critical" if pct > self.config["max_missing_pct"] else "warning" if pct > 5.0 else "info"
            report.issues.append(QualityIssue(
                severity=severity,
                category="missing_values",
                column=col,
                description=f"{missing} valores faltantes ({pct:.1f}%).",
                suggestion="Imputar con forward-fill, interpolacion o eliminar filas.",
                value=round(pct, 2),
            ))

        if "timestamp" in df.columns:
            try:
                ts = pd.to_datetime(df["timestamp"]).sort_values()
                diffs = ts.diff().dropna()
                if len(diffs) > 0:
                    median_diff = diffs.median()
                    large_gaps = (diffs > median_diff * 3).sum()
                    if large_gaps > 0:
                        gap_pct = (large_gaps / len(diffs)) * 100
                        severity = "warning" if gap_pct < 10 else "critical"
                        report.issues.append(QualityIssue(
                            severity=severity,
                            category="temporal_gaps",
                            column="timestamp",
                            description=f"{large_gaps} huecos temporales ({gap_pct:.1f}%) mayores a 3x el intervalo mediano.",
                            suggestion="Rellenar huecos con interpolacion o excluir periodos con gaps grandes.",
                            value=round(gap_pct, 2),
                        ))
            except Exception:
                pass

    def _check_outliers(self, df: pd.DataFrame, report: QualityReport) -> None:
        """Outliers estadisticos por columna numerica."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) < 10:
                continue

            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue

            lower = q1 - 3.0 * iqr
            upper = q3 + 3.0 * iqr
            outliers = ((series < lower) | (series > upper)).sum()
            pct = (outliers / len(series)) * 100

            if pct > self.config["max_outlier_pct"]:
                report.issues.append(QualityIssue(
                    severity="warning",
                    category="outliers",
                    column=col,
                    description=f"{outliers} outliers ({pct:.1f}%) detectados via IQR*3.",
                    suggestion="Revisar valores. Considerar winsorizar o eliminar outliers extremos.",
                    value=round(pct, 2),
                ))
            elif pct > 5.0:
                report.issues.append(QualityIssue(
                    severity="info",
                    category="outliers",
                    column=col,
                    description=f"{outliers} outliers ({pct:.1f}%) — dentro de limite aceptable.",
                    value=round(pct, 2),
                ))

    def _check_duplicates(self, df: pd.DataFrame, report: QualityReport) -> None:
        """Filas duplicadas o inconsistentes."""
        dup_count = df.duplicated().sum()
        if dup_count > 0:
            pct = (dup_count / len(df)) * 100
            severity = "warning" if pct > self.config["max_duplicate_pct"] else "info"
            report.issues.append(QualityIssue(
                severity=severity,
                category="duplicates",
                column="*",
                description=f"{dup_count} filas duplicadas ({pct:.1f}%).",
                suggestion="Eliminar duplicados con df.drop_duplicates().",
                value=round(pct, 2),
            ))

        if "timestamp" in df.columns:
            ts_dups = df["timestamp"].duplicated().sum()
            if ts_dups > 0:
                report.issues.append(QualityIssue(
                    severity="warning",
                    category="duplicate_timestamps",
                    column="timestamp",
                    description=f"{ts_dups} timestamps duplicados.",
                    suggestion="Cada timestamp debe ser unico. Eliminar o agregar filas duplicadas.",
                    value=float(ts_dups),
                ))

    def _check_temporal_coverage(self, df: pd.DataFrame, report: QualityReport) -> None:
        """Cobertura temporal minima."""
        if "timestamp" not in df.columns:
            return

        try:
            ts = pd.to_datetime(df["timestamp"]).sort_values()
            total_range = (ts.iloc[-1] - ts.iloc[0]).total_seconds()
            if total_range == 0:
                return

            diffs = ts.diff().dropna()
            median_interval = diffs.median().total_seconds()
            expected_points = int(total_range / median_interval) if median_interval > 0 else 0
            actual_points = len(ts)

            if expected_points > 0:
                coverage = (actual_points / expected_points) * 100
                report.temporal_coverage = {
                    "start": str(ts.iloc[0]),
                    "end": str(ts.iloc[-1]),
                    "range_days": int(total_range / 86400),
                    "expected_points": expected_points,
                    "actual_points": actual_points,
                    "coverage_pct": round(coverage, 2),
                }

                if coverage < self.config["min_temporal_coverage_pct"]:
                    report.issues.append(QualityIssue(
                        severity="warning",
                        category="temporal_coverage",
                        column="timestamp",
                        description=f"Cobertura temporal: {coverage:.1f}% (minimo: {self.config['min_temporal_coverage_pct']}%).",
                        suggestion="Obtener mas datos para cubrir el periodo faltante.",
                        value=round(coverage, 2),
                    ))
        except Exception:
            pass

    def _check_class_balance(self, df: pd.DataFrame, report: QualityReport) -> None:
        """Balance de clases (BUY/SELL/HOLD o columna target)."""
        target_candidates = ["target", "label", "signal", "action", "direction", "y"]
        target_col = None
        for col in target_candidates:
            if col in df.columns:
                target_col = col
                break

        if target_col is None:
            return

        value_counts = df[target_col].value_counts()
        total = len(df)
        balance = {}
        for val, count in value_counts.items():
            pct = (count / total) * 100
            balance[str(val)] = round(pct, 2)

        report.class_balance = balance

        for val, count in value_counts.items():
            pct = (count / total) * 100
            if pct < self.config["min_class_pct"]:
                report.issues.append(QualityIssue(
                    severity="warning",
                    category="class_imbalance",
                    column=target_col,
                    description=f"Clase '{val}' tiene solo {pct:.1f}% de los datos ({count} filas).",
                    suggestion="Usar class_weight='balanced', oversampling o SMOTE.",
                    value=round(pct, 2),
                ))

        if len(value_counts) == 1:
            report.issues.append(QualityIssue(
                severity="critical",
                category="single_class",
                column=target_col,
                description=f"Solo una clase presente: '{value_counts.index[0]}'.",
                suggestion="El modelo no puede aprender con una sola clase. Revisar la generacion del target.",
            ))

    def _check_technical_indicators(self, df: pd.DataFrame, report: QualityReport) -> None:
        """Calidad de indicadores tecnicos."""
        indicator_cols = {
            "rsi_14": (0, 100),
            "macd": None,
            "macd_signal": None,
            "macd_histogram": None,
            "atr_14": (0, None),
            "ema_20": (0, None),
            "ema_50": (0, None),
            "ema_150": (0, None),
            "bollinger_upper_20": None,
            "bollinger_lower_20": None,
            "adx": (0, 100),
            "cci": (-200, 200),
            "mfi": (0, 100),
            "roc": None,
            "stochastic_k": (0, 100),
            "stochastic_d": (0, 100),
        }

        found = 0
        all_nan = 0
        for col, valid_range in indicator_cols.items():
            if col not in df.columns:
                continue
            found += 1

            series = df[col].dropna()
            if len(series) == 0:
                all_nan += 1
                report.issues.append(QualityIssue(
                    severity="critical",
                    category="indicator_all_nan",
                    column=col,
                    description=f"Indicador '{col}' tiene todos sus valores NaN.",
                    suggestion="Recalcular el indicador o excluirlo del dataset.",
                ))
                continue

            if valid_range:
                lo, hi = valid_range
                if lo is not None:
                    out_of_range = (series < lo).sum()
                    if out_of_range > 0:
                        report.issues.append(QualityIssue(
                            severity="warning",
                            category="indicator_out_of_range",
                            column=col,
                            description=f"{out_of_range} valores fuera de rango (< {lo}).",
                            suggestion="Recalcular el indicador. Valores fuera de rango indican error de calculo.",
                            value=float(out_of_range),
                        ))
                if hi is not None:
                    out_of_range = (series > hi).sum()
                    if out_of_range > 0:
                        report.issues.append(QualityIssue(
                            severity="warning",
                            category="indicator_out_of_range",
                            column=col,
                            description=f"{out_of_range} valores fuera de rango (> {hi}).",
                            suggestion="Recalcular el indicador. Valores fuera de rango indican error de calculo.",
                            value=float(out_of_range),
                        ))

            if series.std() == 0:
                report.issues.append(QualityIssue(
                    severity="warning",
                    category="indicator_zero_variance",
                    column=col,
                    description=f"Indicador '{col}' tiene varianza cero — valor constante.",
                    suggestion="Excluir del dataset o verificar el calculo.",
                ))

        if found == 0:
            report.issues.append(QualityIssue(
                severity="info",
                category="no_indicators",
                column="*",
                description="No se encontraron columnas de indicadores tecnicos conocidos.",
                suggestion="Calcular indicadores con feature_engineering.py antes de entrenar.",
            ))

    def _check_row_count(self, df: pd.DataFrame, report: QualityReport) -> None:
        """Verifica que el dataset tenga suficientes filas."""
        min_rows = self.config["min_rows"]
        if len(df) < min_rows:
            report.issues.append(QualityIssue(
                severity="critical",
                category="insufficient_rows",
                column="*",
                description=f"Dataset tiene {len(df)} filas (minimo: {min_rows}).",
                suggestion=f"Obtener al menos {min_rows} filas para entrenamiento robusto.",
                value=float(len(df)),
            ))

    def _finalize(self, report: QualityReport) -> None:
        """Calcula score global, cuenta issues y determina aprobacion."""
        for issue in report.issues:
            if issue.severity == "critical":
                report.critical_count += 1
            elif issue.severity == "warning":
                report.warning_count += 1
            else:
                report.info_count += 1
        report.total_issues = len(report.issues)

        score = 100.0
        for issue in report.issues:
            if issue.severity == "critical":
                score -= 25
            elif issue.severity == "warning":
                score -= 8
            else:
                score -= 1
        report.global_score = max(0.0, min(100.0, score))

        if report.critical_count > 0:
            report.approved = False
            report.recommendation = (
                f"RECHAZADO: {report.critical_count} problema(s) critico(s). "
                "Resolver antes de entrenar."
            )
        elif report.global_score < self.config["min_score"]:
            report.approved = False
            report.recommendation = (
                f"RECHAZADO: Score {report.global_score:.1f} < {self.config['min_score']} "
                f"({report.warning_count} warnings). Mejorar calidad del dataset."
            )
        else:
            report.approved = True
            report.recommendation = (
                f"APROBADO: Score {report.global_score:.1f}/100. "
                f"{report.warning_count} warnings no bloqueantes."
            )


# ──────────────────────────────────────────────────────
# CLI formatting (colorama)
# ──────────────────────────────────────────────────────

def cmd_quality_report(report: QualityReport) -> str:
    """Formatea un QualityReport para consola."""
    try:
        from colorama import Fore, Style, init
        init(autoreset=True)
        G = Fore.GREEN
        R = Fore.RED
        Y = Fore.YELLOW
        C = Fore.CYAN
        B = Fore.BLUE
        S = Style.RESET_ALL
    except Exception:
        G = R = Y = C = B = S = ""

    lines: list[str] = []
    status = f"{G}APROBADO{S}" if report.approved else f"{R}RECHAZADO{S}"
    score_color = G if report.global_score >= 80 else Y if report.global_score >= 60 else R

    lines.append(f"\n{C}{'='*60}{S}")
    lines.append(f"{C}  DATASET QUALITY REPORT{S}")
    lines.append(f"{C}{'='*60}{S}\n")

    info = report.dataset_info
    if info:
        lines.append(f"{B}── Dataset ──{S}")
        lines.append(f"  Pair:      {info.get('pair', 'N/A')}")
        lines.append(f"  Rows:      {info.get('rows', 0)}")
        lines.append(f"  Columns:   {info.get('columns', 0)}")
        lines.append(f"  Memory:    {info.get('memory_mb', 0)} MB")
        if "date_start" in info:
            lines.append(f"  Period:    {info.get('date_start', '?')} → {info.get('date_end', '?')}")
            lines.append(f"  Range:     {info.get('date_range_days', 0)} days")

    lines.append(f"\n{B}── Resultado ──{S}")
    lines.append(f"  Score:     {score_color}{report.global_score:.1f}/100{S}")
    lines.append(f"  Status:    {status}")
    lines.append(f"  Issues:    {R}{report.critical_count} critical{S}, {Y}{report.warning_count} warnings{S}, {report.info_count} info")
    lines.append(f"  Verdict:   {report.recommendation}")

    if report.temporal_coverage:
        tc = report.temporal_coverage
        lines.append(f"\n{B}── Temporal Coverage ──{S}")
        lines.append(f"  Coverage:  {tc.get('coverage_pct', 0):.1f}%")
        lines.append(f"  Points:    {tc.get('actual_points', 0)} / {tc.get('expected_points', 0)} expected")

    if report.class_balance:
        lines.append(f"\n{B}── Class Balance ──{S}")
        for cls, pct in report.class_balance.items():
            color = G if pct >= 20 else Y if pct >= 10 else R
            lines.append(f"  {cls:>10}: {color}{pct:.1f}%{S}")

    if report.issues:
        lines.append(f"\n{B}── Issues ({report.total_issues}) ──{S}")
        for issue in report.issues:
            if issue.severity == "critical":
                prefix = f"  {R}[CRIT]{S}"
            elif issue.severity == "warning":
                prefix = f"  {Y}[WARN]{S}"
            else:
                prefix = f"  [INFO]"
            lines.append(f"{prefix} {issue.category} / {issue.column}: {issue.description}")
            if issue.suggestion:
                lines.append(f"         → {issue.suggestion}")
    else:
        lines.append(f"\n{G}  No issues found. Dataset is clean.{S}")

    lines.append(f"\n{C}{'='*60}{S}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────
# Quality gate function — called by IntegratedPipeline
# ──────────────────────────────────────────────────────

def quality_gate(df: pd.DataFrame, config: dict | None = None, pair: str = "", timeframe: str = "") -> tuple[bool, QualityReport]:
    """
    Gate de calidad para IntegratedPipeline.train().
    Retorna (approved, report).
    Si approved == False, el entrenamiento debe bloquearse.
    """
    analyzer = QualityAnalyzer(config=config)
    report = analyzer.analyze(df, pair=pair, timeframe=timeframe)
    return report.approved, report


# ──────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────

if __name__ == "__main__":
    np.random.seed(42)
    n = 500
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    df = pd.DataFrame({
        "timestamp": dates,
        "open": np.random.randn(n) * 0.01 + 1.0,
        "high": np.random.randn(n) * 0.01 + 1.01,
        "low": np.random.randn(n) * 0.01 + 0.99,
        "close": np.random.randn(n) * 0.01 + 1.0,
        "volume": np.random.randint(100, 10000, n),
        "rsi_14": np.random.uniform(0, 100, n),
        "macd": np.random.randn(n) * 0.001,
        "macd_signal": np.random.randn(n) * 0.001,
        "macd_histogram": np.random.randn(n) * 0.001,
        "atr_14": np.abs(np.random.randn(n)) * 0.005,
        "ema_20": np.random.randn(n) * 0.01 + 1.0,
        "ema_50": np.random.randn(n) * 0.01 + 1.0,
        "ema_150": np.random.randn(n) * 0.01 + 1.0,
        "target": np.random.choice([0, 1, 2], n, p=[0.4, 0.35, 0.25]),
    })

    df.loc[10:15, "rsi_14"] = np.nan
    df.loc[20:22, "rsi_14"] = 150
    df.loc[5, "timestamp"] = df.loc[4, "timestamp"]

    analyzer = QualityAnalyzer()
    report = analyzer.analyze(df, pair="EURUSD", timeframe="H1")
    print(cmd_quality_report(report))
    print(f"\n  JSON: {report.to_json()[:200]}...")

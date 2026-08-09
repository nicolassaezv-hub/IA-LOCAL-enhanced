"""
Feature Importance Analyzer — V.6 Roadmap V
=============================================
Elimina redundancias y optimiza automaticamente el conjunto de features.
En cada ciclo de entrenamiento, evalua que indicadores realmente aportan
informacion y cuales son redundantes.

Evalua:
  - Importancia nativa del ensemble (XGB/LGB/RF)
  - Correlacion entre features (Spearman)
  - SHAP values para explicabilidad
  - Permutation importance en holdout

Resultado:
  - Lista de features optimos para este par/regimen
  - Features descartados con justificacion
  - Recomendacion de nuevos indicadores a calcular

Integracion con feature_engineering.py para filtrado dinamico.
Respeta la regla existente: columnas MTF excluidas del filtro de baja varianza.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:
    from sklearn.inspection import permutation_importance
    _HAS_SKLEARN = True
except Exception:
    _HAS_SKLEARN = False

try:
    import shap
    _HAS_SHAP = True
except Exception:
    _HAS_SHAP = False


# ──────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────

@dataclass
class FeatureInfo:
    name: str
    native_importance: float = 0.0
    permutation_importance: float = 0.0
    shap_importance: float = 0.0
    mean_abs_correlation: float = 0.0
    correlated_with: list = field(default_factory=list)
    composite_score: float = 0.0
    status: str = "keep"  # "keep", "discard", "review"
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FeatureImportanceReport:
    features: list[FeatureInfo] = field(default_factory=list)
    optimal_features: list[str] = field(default_factory=list)
    discarded_features: list[str] = field(default_factory=list)
    review_features: list[str] = field(default_factory=list)
    correlation_clusters: list[list[str]] = field(default_factory=list)
    recommended_new_indicators: list[str] = field(default_factory=list)
    pair: str = ""
    timeframe: str = ""
    model_name: str = ""
    total_features: int = 0
    optimal_count: int = 0

    def to_dict(self) -> dict:
        return {
            "features": [f.to_dict() for f in self.features],
            "optimal_features": self.optimal_features,
            "discarded_features": self.discarded_features,
            "review_features": self.review_features,
            "correlation_clusters": self.correlation_clusters,
            "recommended_new_indicators": self.recommended_new_indicators,
            "pair": self.pair,
            "timeframe": self.timeframe,
            "model_name": self.model_name,
            "total_features": self.total_features,
            "optimal_count": self.optimal_count,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)


# ──────────────────────────────────────────────────────
# Core analyzer
# ──────────────────────────────────────────────────────

class FeatureImportanceAnalyzer:
    """
    Analiza la importancia de features de un modelo entrenado y
    recomienda el conjunto optimo para futuros entrenamientos.
    """

    # Columnas MTF que NO se deben filtrar por baja varianza
    MTF_PREFIXES = ["d1_", "h4_", "h1_", "mtf_"]

    def __init__(
        self,
        correlation_threshold: float = 0.85,
        importance_percentile: float = 20.0,
        min_importance: float = 0.001,
        use_shap: bool = True,
        use_permutation: bool = True,
    ):
        self.correlation_threshold = correlation_threshold
        self.importance_percentile = importance_percentile
        self.min_importance = min_importance
        self.use_shap = use_shap and _HAS_SHAP
        self.use_permutation = use_permutation and _HAS_SKLEARN

    def analyze(
        self,
        model: Any,
        X: pd.DataFrame | np.ndarray,
        y: np.ndarray,
        X_test: pd.DataFrame | np.ndarray | None = None,
        y_test: np.ndarray | None = None,
        feature_names: list[str] | None = None,
        pair: str = "",
        timeframe: str = "",
        model_name: str = "",
        mtf_columns: list[str] | None = None,
    ) -> FeatureImportanceReport:
        """
        Analiza la importancia de features del modelo.

        Args:
            model: modelo sklearn-like entrenado (debe tener feature_importances_ o coef_)
            X: features de entrenamiento
            y: target de entrenamiento
            X_test/y_test: holdout para permutation importance
            feature_names: nombres de columnas (si X no es DataFrame)
            pair/timeframe/model_name: metadatos
            mtf_columns: columnas MTF que no se filtraran por baja importancia
        """
        if feature_names is None:
            if isinstance(X, pd.DataFrame):
                feature_names = list(X.columns)
            else:
                feature_names = [f"f{i}" for i in range(X.shape[1])]

        if mtf_columns is None:
            mtf_columns = [f for f in feature_names if any(f.startswith(p) for p in self.MTF_PREFIXES)]

        if isinstance(X, pd.DataFrame):
            X_arr = X.values
        else:
            X_arr = np.asarray(X)

        if X_test is not None:
            X_test_arr = X_test.values if isinstance(X_test, pd.DataFrame) else np.asarray(X_test)
        else:
            X_test_arr = None

        report = FeatureImportanceReport(
            pair=pair,
            timeframe=timeframe,
            model_name=model_name,
            total_features=len(feature_names),
        )

        native_imp = self._get_native_importance(model, feature_names)
        perm_imp = self._get_permutation_importance(model, X_test_arr, y_test, feature_names) if self.use_permutation and X_test_arr is not None else {}
        shap_imp = self._get_shap_importance(model, X_test_arr, feature_names) if self.use_shap and X_test_arr is not None else {}
        corr_matrix, corr_pairs = self._compute_correlation(X, feature_names)

        features: list[FeatureInfo] = []
        for name in feature_names:
            fi = FeatureInfo(name=name)
            fi.native_importance = native_imp.get(name, 0.0)
            fi.permutation_importance = perm_imp.get(name, 0.0)
            fi.shap_importance = shap_imp.get(name, 0.0)

            correlated = corr_pairs.get(name, [])
            fi.correlated_with = [c for c, v in correlated if c != name]
            if correlated:
                fi.mean_abs_correlation = float(np.mean([v for _, v in correlated]))

            fi.composite_score = self._composite_score(fi)
            features.append(fi)

        report.features = features
        self._classify_features(report, mtf_columns)
        report.correlation_clusters = self._find_correlation_clusters(corr_pairs)
        report.recommended_new_indicators = self._recommend_indicators(report)

        return report

    def _get_native_importance(self, model: Any, names: list[str]) -> dict[str, float]:
        """Importancia nativa del modelo (tree-based o coef)."""
        result = {}
        try:
            if hasattr(model, "feature_importances_"):
                imp = model.feature_importances_
                for i, name in enumerate(names):
                    result[name] = float(imp[i]) if i < len(imp) else 0.0
            elif hasattr(model, "coef_"):
                coef = model.coef_
                if coef.ndim > 1:
                    coef = np.abs(coef).mean(axis=0)
                for i, name in enumerate(names):
                    result[name] = float(abs(coef[i])) if i < len(coef) else 0.0
        except Exception:
            pass
        return result

    def _get_permutation_importance(self, model: Any, X_test: np.ndarray, y_test: np.ndarray, names: list[str]) -> dict[str, float]:
        """Permutation importance en holdout."""
        result = {}
        try:
            if y_test is None or len(y_test) == 0:
                return result
            r = permutation_importance(model, X_test, y_test, n_repeats=10, random_state=42, scoring="accuracy")
            for i, name in enumerate(names):
                result[name] = float(r.importances_mean[i])
        except Exception:
            pass
        return result

    def _get_shap_importance(self, model: Any, X_test: np.ndarray, names: list[str]) -> dict[str, float]:
        """SHAP values para explicabilidad."""
        result = {}
        try:
            if not _HAS_SHAP or X_test is None or len(X_test) == 0:
                return result

            X_sample = X_test[:min(200, len(X_test))]

            try:
                explainer = shap.TreeExplainer(model)
                shap_values = explainer.shap_values(X_sample)
            except Exception:
                explainer = shap.LinearExplainer(model, X_sample)
                shap_values = explainer.shap_values(X_sample)

            if isinstance(shap_values, list):
                shap_values = shap_values[0]
            if shap_values.ndim > 2:
                shap_values = shap_values.mean(axis=2)

            mean_abs = np.abs(shap_values).mean(axis=0)
            for i, name in enumerate(names):
                result[name] = float(mean_abs[i]) if i < len(mean_abs) else 0.0
        except Exception:
            pass
        return result

    def _compute_correlation(self, X: pd.DataFrame | np.ndarray, names: list[str]) -> tuple[pd.DataFrame, dict[str, list[tuple[str, float]]]]:
        """Matriz de correlacion Spearman y pares altamente correlacionados."""
        if isinstance(X, np.ndarray):
            df = pd.DataFrame(X, columns=names)
        else:
            df = X

        corr_pairs: dict[str, list[tuple[str, float]]] = {}
        try:
            corr_matrix = df.corr(method="spearman").abs()
            for i, name in enumerate(names):
                if name not in corr_matrix.columns:
                    continue
                row = corr_matrix[name]
                high = [(other, float(val)) for other, val in row.items() if other != name and val > self.correlation_threshold]
                corr_pairs[name] = sorted(high, key=lambda x: x[1], reverse=True)
        except Exception:
            corr_matrix = pd.DataFrame()
        return corr_matrix, corr_pairs

    def _composite_score(self, fi: FeatureInfo) -> float:
        """Score compuesto: 50% native, 25% permutation, 15% SHAP, 10% correlation penalty."""
        native = fi.native_importance
        perm = fi.permutation_importance
        shap_val = fi.shap_importance
        corr_penalty = fi.mean_abs_correlation * 0.5

        score = native * 0.50 + perm * 0.25 + shap_val * 0.15 - corr_penalty * 0.10
        return max(0.0, score)

    def _classify_features(self, report: FeatureImportanceReport, mtf_columns: list[str]) -> None:
        """Clasifica features en keep / discard / review."""
        if not report.features:
            return

        scores = [f.composite_score for f in report.features]
        threshold = float(np.percentile(scores, self.importance_percentile)) if len(scores) > 1 else 0.0

        for fi in report.features:
            is_mtf = fi.name in mtf_columns or any(fi.name.startswith(p) for p in self.MTF_PREFIXES)

            if fi.composite_score < self.min_importance and not is_mtf:
                fi.status = "discard"
                fi.reason = "Importancia compuesta muy baja"
                report.discarded_features.append(fi.name)
            elif fi.mean_abs_correlation > self.correlation_threshold and not is_mtf:
                fi.status = "discard"
                fi.reason = f"Altamente correlacionado con {fi.correlated_with}"
                report.discarded_features.append(fi.name)
            elif fi.composite_score < threshold and not is_mtf:
                fi.status = "review"
                fi.reason = f"Importancia baja (percentil {self.importance_percentile:.0f})"
                report.review_features.append(fi.name)
            else:
                fi.status = "keep"
                fi.reason = "Importancia suficiente" if not is_mtf else "MTF — excluido de filtro"
                report.optimal_features.append(fi.name)

        report.optimal_count = len(report.optimal_features)

    def _find_correlation_clusters(self, corr_pairs: dict[str, list[tuple[str, float]]]) -> list[list[str]]:
        """Encuentra clusters de features altamente correlacionados."""
        visited: set[str] = set()
        clusters: list[list[str]] = []

        for name, pairs in corr_pairs.items():
            if name in visited:
                continue
            cluster = {name}
            for other, _ in pairs:
                cluster.add(other)
            if len(cluster) > 1:
                clusters.append(sorted(cluster))
                visited.update(cluster)

        return clusters

    def _recommend_indicators(self, report: FeatureImportanceReport) -> list[str]:
        """Recomienda nuevos indicadores a calcular basado en gaps detectados."""
        recommendations: list[str] = []
        current_names = {f.name.lower() for f in report.features}

        indicator_suggestions = [
            ("vwap", "VWAP — Volume Weighted Average Price (util para confirmar tendencias)"),
            ("ichimoku", "Ichimoku Cloud (soporte/resistencia dinamico)"),
            ("pivot", "Pivot Points (niveles de soporte/resistencia clasicos)"),
            ("obv", "On-Balance Volume (flujo de volumen acumulado)"),
            ("vwap_band", "VWAP Bands (bandas alrededor al VWAP)"),
            ("supertrend", "Supertrend (indicador de tendencia con ATR)"),
            ("adx_di_plus", "ADX +DI/-DI (direccion de la tendencia)"),
            ("williams_r", "Williams %R (oscilador de momento)"),
            ("stoch_rsi", "Stochastic RSI (oscilador mas sensible)"),
            ("atr_pctrank", "ATR Percentile Rank (volatilidad relativa)"),
        ]

        for key, desc in indicator_suggestions:
            if not any(key in name for name in current_names):
                recommendations.append(desc)

        return recommendations


# ──────────────────────────────────────────────────────
# Dynamic filtering for feature_engineering integration
# ──────────────────────────────────────────────────────

def filter_features(
    X: pd.DataFrame,
    report: FeatureImportanceReport,
    keep_mtf: bool = True,
) -> pd.DataFrame:
    """
    Filtra un DataFrame de features segun el reporte de importancia.
    Elimina features descartados. Mantiene MTF si keep_mtf=True.
    """
    drop_cols = list(report.discarded_features)
    if not keep_mtf:
        drop_cols.extend(report.review_features)

    drop_cols = [c for c in drop_cols if c in X.columns]
    return X.drop(columns=drop_cols, errors="ignore")


def get_optimal_feature_names(report: FeatureImportanceReport) -> list[str]:
    """Retorna solo los nombres de features optimos."""
    return report.optimal_features.copy()


# ──────────────────────────────────────────────────────
# CLI formatting
# ──────────────────────────────────────────────────────

def cmd_feature_importance_report(report: FeatureImportanceReport) -> str:
    """Formatea un FeatureImportanceReport para consola."""
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

    lines.append(f"\n{C}{'='*70}{S}")
    lines.append(f"{C}  FEATURE IMPORTANCE REPORT — V.6{S}")
    lines.append(f"{C}  {report.pair} · {report.timeframe} · {report.model_name}{S}")
    lines.append(f"{C}{'='*70}{S}\n")

    lines.append(f"{B}── Summary ──{S}")
    lines.append(f"  Total features:     {report.total_features}")
    lines.append(f"  Optimal (keep):     {G}{report.optimal_count}{S}")
    lines.append(f"  Discarded:          {R}{len(report.discarded_features)}{S}")
    lines.append(f"  Review:             {Y}{len(report.review_features)}{S}\n")

    if report.features:
        lines.append(f"{B}── Feature Ranking (by composite score) ──{S}")
        lines.append(f"  {'Feature':<30} {'Native':>8} {'Permut':>8} {'SHAP':>8} {'Corr':>6} {'Score':>8} {'Status':>8}")
        lines.append(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*8} {'-'*6} {'-'*8} {'-'*8}")

        sorted_features = sorted(report.features, key=lambda f: f.composite_score, reverse=True)
        for fi in sorted_features:
            if fi.status == "keep":
                status_color = G
            elif fi.status == "discard":
                status_color = R
            else:
                status_color = Y
            lines.append(
                f"  {fi.name:<30} {fi.native_importance:>8.4f} {fi.permutation_importance:>8.4f} "
                f"{fi.shap_importance:>8.4f} {fi.mean_abs_correlation:>6.3f} "
                f"{fi.composite_score:>8.4f} {status_color}{fi.status:>8}{S}"
            )
            if fi.reason and fi.status != "keep":
                lines.append(f"  {'':>30} {fi.reason}")

    if report.correlation_clusters:
        lines.append(f"\n{B}── Correlation Clusters (>{0.85:.0%}) ──{S}")
        for i, cluster in enumerate(report.correlation_clusters):
            lines.append(f"  Cluster {i+1}: {', '.join(cluster)}")

    if report.recommended_new_indicators:
        lines.append(f"\n{B}── Recommended New Indicators ──{S}")
        for rec in report.recommended_new_indicators:
            lines.append(f"  {Y}→{S} {rec}")

    lines.append(f"\n{C}{'='*70}{S}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────

if __name__ == "__main__":
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split

    np.random.seed(42)
    n = 500
    X = pd.DataFrame({
        "rsi_14": np.random.uniform(0, 100, n),
        "macd": np.random.randn(n) * 0.01,
        "macd_signal": np.random.randn(n) * 0.01,
        "atr_14": np.abs(np.random.randn(n)) * 0.005,
        "ema_20": np.random.randn(n) * 0.01 + 1.0,
        "ema_50": np.random.randn(n) * 0.01 + 1.0,
        "ema_150": np.random.randn(n) * 0.01 + 1.0,
        "bollinger_upper_20": np.random.randn(n) * 0.02 + 1.02,
        "bollinger_lower_20": np.random.randn(n) * 0.02 + 0.98,
        "d1_trend": np.random.randn(n) * 0.005,
        "useless_feature": np.zeros(n),
        "constant_feature": np.ones(n) * 42,
    })

    y = np.random.choice([0, 1, 2], n, p=[0.4, 0.35, 0.25])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    model = RandomForestClassifier(n_estimators=50, random_state=42)
    model.fit(X_train, y_train)

    analyzer = FeatureImportanceAnalyzer(use_shap=False, use_permutation=True)
    report = analyzer.analyze(
        model, X_train, y_train,
        X_test=X_test, y_test=y_test,
        pair="EURUSD", timeframe="H1", model_name="RandomForest",
    )

    print(cmd_feature_importance_report(report))
    print(f"\n  Optimal features: {report.optimal_features}")
    print(f"  Discarded: {report.discarded_features}")

"""
prediction_lab/validation_engine.py — Fase 5.6 (Prediction Lab)

Entrena de verdad el pipeline generado (5.5) y lo valida con holdout,
k-fold o walk-forward (WFV para forex/timeseries), según la estrategia
que definió el Model Planner (5.4).

Es el primer módulo de la Fase 5 que efectivamente entrena modelos —
todo lo anterior solo analizaba/planificaba.

Decisiones de diseño (vs. el draft de referencia revisado):
  - `GeneratedPipeline` no carga el `ModelPlan` — se recibe explícito como
    parámetro (evita acoplar 5.5 a 5.4 con un campo cruzado).
  - `_score()` interpreta la métrica del plan y, para regresión, retorna un
    score "mayor-es-mejor" derivado de RMSE (mismo criterio 0-1 que el resto
    del sistema para comparar contra `expected_min_metric`), pero además
    reporta RMSE y R² crudos en el resultado para lectura humana — el draft
    solo mostraba el score invertido, poco interpretable.
  - Feature importance: si el pipeline usa OneHotEncoder (columnas
    categóricas), el nombre de columnas expandidas se obtiene de
    `ColumnTransformer.get_feature_names_out()` — el draft de referencia
    hacía `zip(feature_names_originales, importances)` a ciegas, lo que
    desalinea nombres e importancias apenas hay una sola columna categórica
    (el one-hot expande N columnas y desincroniza el zip).
  - SMOTE solo se intenta si `strategy.use_smote` Y el target es
    categórico (lo valida además `model_planner`, fix aplicado ahí mismo).
  - Walk-forward (WFV): tamaño de ventana/step derivados de `n_splits` y
    del tamaño real del dataset, no hardcodeados — se degradan solos si el
    dataset es chico.

Patrón "graceful fail": nunca lanza — cualquier error interno queda en
`ok=False` + `error`.

API pública:
  validate_pipeline(generated_pipeline, model_plan, df) -> ValidationResult
  validate_from_csv(generated_pipeline, model_plan, csv_path) -> ValidationResult
  cmd_lab_valida(csv_path, idea) -> str
"""

import warnings
warnings.filterwarnings("ignore")

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .pipeline_generator import GeneratedPipeline
from .model_planner import ModelPlan, ValidationStrategy


@dataclass
class FoldResult:
    fold:       int
    train_size: int
    test_size:  int
    score:      float


@dataclass
class ValidationResult:
    ok:                 bool = True
    error:              Optional[str] = None

    method:             str = ""
    metric:             str = ""
    mean_score:         float = 0.0
    std_score:          float = 0.0
    passes:             bool = False
    min_expected:       float = 0.5
    fold_results:       List[FoldResult] = field(default_factory=list)
    feature_importance: Dict[str, float] = field(default_factory=dict)
    extra_metrics:      Dict[str, float] = field(default_factory=dict)  # rmse/r2 crudos si aplica
    trained_pipeline:   Any = None
    warnings_list:      List[str] = field(default_factory=list)

    def summary(self) -> str:
        if not self.ok:
            return f"[VALIDATION ENGINE] Error: {self.error}"

        verdict = "PASA ✔" if self.passes else "NO PASA ✘"
        lines = [
            "═" * 62,
            " VALIDATION ENGINE — Resultado del entrenamiento",
            "═" * 62,
            f" Método       : {self.method}",
            f" Métrica      : {self.metric}",
            f" Score medio  : {self.mean_score:.4f}  (±{self.std_score:.4f})",
            f" Mínimo req.  : {self.min_expected:.4f}",
            f" Veredicto    : {verdict}",
        ]
        if self.extra_metrics:
            lines.append("")
            for k, v in self.extra_metrics.items():
                lines.append(f" {k:12s}: {v:.4f}")

        lines.append("")
        lines.append(" Por fold:")
        for fr in self.fold_results:
            lines.append(f"   Fold {fr.fold:2d}: {fr.score:.4f}  (train={fr.train_size:,}  test={fr.test_size:,})")

        if self.feature_importance:
            lines.append("")
            lines.append(" Top features (importancia):")
            for feat, imp in list(self.feature_importance.items())[:10]:
                lines.append(f"   {feat:<30s}: {imp:.4f}")

        if self.warnings_list:
            lines.append("")
            lines.append(" Avisos:")
            for w in self.warnings_list:
                lines.append(f"   ! {w}")

        lines.append("═" * 62)
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════
#  SCORING
# ══════════════════════════════════════════════════════════

def _score(pipeline, X_test, y_test, metric: str, extra: Dict[str, float]) -> float:
    try:
        y_pred = pipeline.predict(X_test)
    except Exception:
        return 0.0

    try:
        if metric == "accuracy":
            from sklearn.metrics import accuracy_score
            return float(accuracy_score(y_test, y_pred))
        if metric == "f1":
            from sklearn.metrics import f1_score
            return float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
        if metric == "precision":
            from sklearn.metrics import precision_score
            return float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
        if metric == "roc_auc":
            try:
                y_prob = pipeline.predict_proba(X_test)[:, 1]
                from sklearn.metrics import roc_auc_score
                return float(roc_auc_score(y_test, y_prob))
            except Exception:
                from sklearn.metrics import accuracy_score
                return float(accuracy_score(y_test, y_pred))

        # Regresión (rmse u otra métrica no reconocida). BUGFIX: usar R2 como score
        # principal (0-1, mayor-es-mejor, misma escala universal que expected_min_metric
        # 0.5-0.85) — usar 1/(1+RMSE) como antes hacía que el veredicto PASA/NO PASA
        # dependiera de la magnitud absoluta del target (con targets grandes, ej. ventas
        # en miles, el score quedaba ~0.001 y SIEMPRE fallaba pese a un fit excelente).
        # RMSE crudo se conserva en extra_metrics solo para lectura humana.
        from sklearn.metrics import mean_squared_error, r2_score
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        r2 = float(r2_score(y_test, y_pred))
        extra["rmse"] = rmse
        extra["r2"] = r2
        return max(0.0, r2)
    except Exception:
        return 0.0


def _feature_importance(pipeline, top_n: int = 15) -> Dict[str, float]:
    """
    Extrae feature importances alineando nombres reales post-encoding
    (incluye columnas expandidas por OneHotEncoder) — no los nombres
    originales pre-encoding, que desalinean apenas hay categóricas.
    """
    try:
        estimator = pipeline.named_steps.get("estimator")
        if estimator is None:
            return {}

        # Ensembles (VotingClassifier/VotingRegressor): promediar importancias
        # de los miembros que sí las expongan.
        members = getattr(estimator, "estimators_", None)
        candidates = members if members else [estimator]

        importances = None
        for est in candidates:
            fi = getattr(est, "feature_importances_", None)
            if fi is not None:
                importances = fi if importances is None else (importances + fi)
        if importances is None:
            return {}
        importances = importances / len(candidates)

        # Nombres reales de columnas tras el ColumnTransformer (incluye one-hot expandido)
        preprocessor = pipeline.named_steps.get("preprocessor")
        try:
            names = list(preprocessor.get_feature_names_out())
        except Exception:
            names = [f"feature_{i}" for i in range(len(importances))]

        n = min(len(names), len(importances))
        pairs = sorted(zip(names[:n], importances[:n]), key=lambda x: -x[1])[:top_n]
        return {k: round(float(v), 4) for k, v in pairs}
    except Exception:
        return {}


def _apply_smote(X, y, strategy: ValidationStrategy):
    if not strategy.use_smote:
        return X, y, None
    try:
        from imblearn.over_sampling import SMOTE
        min_class = int(y.value_counts().min())
        if min_class < 2:
            return X, y, "SMOTE omitido: alguna clase tiene <2 muestras."
        k = min(5, min_class - 1)
        sm = SMOTE(random_state=42, k_neighbors=max(1, k))
        X_res, y_res = sm.fit_resample(X, y)
        return X_res, y_res, None
    except ImportError:
        return X, y, "SMOTE recomendado pero 'imblearn' no está instalado — se entrenó sin oversampling."
    except Exception as e:
        return X, y, f"SMOTE falló ({e}) — se entrenó sin oversampling."


def _clone_pipeline(pipeline):
    from sklearn.base import clone
    return clone(pipeline)


# ══════════════════════════════════════════════════════════
#  ESTRATEGIAS DE VALIDACIÓN
# ══════════════════════════════════════════════════════════

def _holdout(pipeline, X, y, strategy: ValidationStrategy, min_expected: float, warn: List[str]):
    from sklearn.model_selection import train_test_split
    stratify = y if strategy.metric in ("accuracy", "f1", "precision", "roc_auc") and y.nunique() > 1 else None
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=strategy.test_size, random_state=42, stratify=stratify)
    except ValueError:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=strategy.test_size, random_state=42)

    X_train, y_train, smote_note = _apply_smote(X_train, y_train, strategy)
    if smote_note:
        warn.append(smote_note)

    fitted = _clone_pipeline(pipeline)
    fitted.fit(X_train, y_train)
    extra = {}
    score = _score(fitted, X_test, y_test, strategy.metric, extra)
    return ([FoldResult(1, len(X_train), len(X_test), score)], [score], fitted, extra)


def _kfold(pipeline, X, y, strategy: ValidationStrategy, warn: List[str]):
    from sklearn.model_selection import KFold, StratifiedKFold
    is_clf_metric = strategy.metric in ("accuracy", "f1", "precision", "roc_auc")
    try:
        if is_clf_metric:
            cv = StratifiedKFold(n_splits=strategy.n_splits, shuffle=True, random_state=42)
            splits = list(cv.split(X, y))
        else:
            raise ValueError("no stratify for regression")
    except Exception:
        cv = KFold(n_splits=strategy.n_splits, shuffle=True, random_state=42)
        splits = list(cv.split(X, y))

    fold_results, scores, last_fitted, last_extra = [], [], None, {}
    for i, (tr, te) in enumerate(splits, 1):
        X_tr, X_te = X.iloc[tr], X.iloc[te]
        y_tr, y_te = y.iloc[tr], y.iloc[te]
        X_tr, y_tr, smote_note = _apply_smote(X_tr, y_tr, strategy)
        if smote_note and i == 1:
            warn.append(smote_note)
        fitted = _clone_pipeline(pipeline)
        fitted.fit(X_tr, y_tr)
        extra = {}
        s = _score(fitted, X_te, y_te, strategy.metric, extra)
        scores.append(s)
        fold_results.append(FoldResult(i, len(X_tr), len(X_te), s))
        last_fitted, last_extra = fitted, extra
    return fold_results, scores, last_fitted, last_extra


def _wfv(pipeline, X, y, strategy: ValidationStrategy, warn: List[str]):
    """Walk-forward deslizante con purge gap — sin mezclar pasado/futuro."""
    n = len(X)
    n_splits = max(2, strategy.n_splits)
    purge = 10

    # ventana/step derivados del tamaño real, no hardcodeados: reserva ~60% para
    # entrenar la primera ventana y reparte el resto entre folds solicitados.
    window = max(50, int(n * 0.5))
    remaining = max(0, n - window - purge)
    step = max(20, remaining // n_splits) if remaining > 0 else max(10, n // (n_splits + 1))

    if window + step + purge > n:
        # dataset muy chico para WFV real — degrada a una sola ventana amplia
        window = max(20, int(n * 0.7))
        step = max(10, n - window - purge)
        warn.append("Dataset pequeño para WFV — se usó una sola ventana ampliada en vez de folds deslizantes.")

    fold_results, scores, last_fitted, last_extra = [], [], None, {}
    fold, start = 0, 0
    while start + window + purge + step <= n and fold < n_splits:
        fold += 1
        train_end = start + window
        test_start = train_end + purge
        test_end = test_start + step
        X_tr, y_tr = X.iloc[start:train_end], y.iloc[start:train_end]
        X_te, y_te = X.iloc[test_start:test_end], y.iloc[test_start:test_end]

        X_tr, y_tr, smote_note = _apply_smote(X_tr, y_tr, strategy)
        if smote_note and fold == 1:
            warn.append(smote_note)

        fitted = _clone_pipeline(pipeline)
        fitted.fit(X_tr, y_tr)
        extra = {}
        s = _score(fitted, X_te, y_te, strategy.metric, extra)
        scores.append(s)
        fold_results.append(FoldResult(fold, len(X_tr), len(X_te), s))
        last_fitted, last_extra = fitted, extra
        start += step

    if not scores:
        warn.append("No se pudo formar ni un fold WFV — dataset insuficiente para esta estrategia.")
        return [FoldResult(1, 0, 0, 0.0)], [0.0], None, {}

    return fold_results, scores, last_fitted, last_extra


# ══════════════════════════════════════════════════════════
#  API PÚBLICA
# ══════════════════════════════════════════════════════════

def validate_pipeline(generated: GeneratedPipeline, model_plan: ModelPlan, df: pd.DataFrame) -> ValidationResult:
    if not generated.ok:
        return ValidationResult(ok=False, error=generated.error)
    if not model_plan.ok or model_plan.validation is None:
        return ValidationResult(ok=False, error=model_plan.error or "ModelPlan sin estrategia de validación.")
    if df is None or df.empty:
        return ValidationResult(ok=False, error="DataFrame vacío o no provisto.")

    target = generated.target_variable
    if target not in df.columns:
        return ValidationResult(ok=False, error=f"Target '{target}' no está en el CSV provisto.")

    available = [c for c in generated.feature_names if c in df.columns]
    if not available:
        return ValidationResult(ok=False, error="Ninguna de las features del pipeline está presente en el CSV.")

    X = df[available].copy()
    y = df[target].copy()
    mask = y.notna()
    X, y = X[mask], y[mask]
    if len(X) < 10:
        return ValidationResult(ok=False, error=f"Muy pocas filas válidas ({len(X)}) tras filtrar NaN del target.")

    strategy = model_plan.validation
    warn: List[str] = []

    try:
        if strategy.method == "holdout":
            fold_results, scores, fitted, extra = _holdout(generated.pipeline, X, y, strategy,
                                                             model_plan.expected_min_metric, warn)
        elif strategy.method == "kfold":
            fold_results, scores, fitted, extra = _kfold(generated.pipeline, X, y, strategy, warn)
        else:  # wfv
            fold_results, scores, fitted, extra = _wfv(generated.pipeline, X, y, strategy, warn)
    except Exception as e:
        return ValidationResult(ok=False, error=f"Fallo durante el entrenamiento/validación: {e}")

    mean_s = float(np.mean(scores)) if scores else 0.0
    std_s = float(np.std(scores)) if scores else 0.0
    passes = mean_s >= model_plan.expected_min_metric

    if mean_s < 0.50:
        warn.append(f"Score muy bajo ({mean_s:.4f}) — el modelo apenas supera (o no supera) el azar.")
    if std_s > 0.15:
        warn.append(f"Alta varianza entre folds (±{std_s:.4f}) — el modelo es inestable, revisa el tamaño de datos/features.")

    fi = _feature_importance(fitted) if fitted is not None else {}

    return ValidationResult(
        ok=True,
        method=strategy.method,
        metric=strategy.metric,
        mean_score=round(mean_s, 4),
        std_score=round(std_s, 4),
        passes=passes,
        min_expected=model_plan.expected_min_metric,
        fold_results=fold_results,
        feature_importance=fi,
        extra_metrics=extra,
        trained_pipeline=fitted,
        warnings_list=warn,
    )


def validate_from_csv(generated: GeneratedPipeline, model_plan: ModelPlan, csv_path: str) -> ValidationResult:
    import os
    if not csv_path or not os.path.exists(csv_path):
        return ValidationResult(ok=False, error=f"Archivo no encontrado: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return ValidationResult(ok=False, error=f"No se pudo leer el CSV: {e}")
    return validate_pipeline(generated, model_plan, df)


def cmd_lab_valida(csv_path: str, idea: str, target_variable=None) -> str:
    """Comando CLI: 'lab valida <csv> \"<idea>\" [target]' — encadena 5.1 → 5.6 completo."""
    if not csv_path or not idea:
        return 'Uso: lab valida <archivo.csv> "<describe tu idea>" [columna_target]'

    from .model_planner import plan_model
    from .pipeline_generator import generate_pipeline

    plan = plan_model(csv_path, idea, target_variable=target_variable)
    if not plan.ok or not plan.algorithms or plan.validation is None:
        reason = plan.error or "viabilidad insuficiente — revisa 'lab planea' primero."
        return f"[VALIDATION ENGINE] No se pudo validar: {reason}"

    import os
    try:
        df = pd.read_csv(csv_path) if os.path.exists(csv_path) else None
    except Exception as e:
        return f"[VALIDATION ENGINE] No se pudo leer el CSV: {e}"

    generated = generate_pipeline(plan, df)
    if not generated.ok:
        return f"[VALIDATION ENGINE] No se pudo generar el pipeline: {generated.error}"

    result = validate_pipeline(generated, plan, df)
    return result.summary()

"""
prediction_lab/model_planner.py — Fase 5.4 (Prediction Lab)

Dado un ProblemSpec (5.1) + DatasetReport (5.2) + FeasibilityReport (5.3),
genera un ModelPlan concreto: qué algoritmos usar, cómo preparar las
features, qué estrategia de validación aplicar, y cuál es la métrica
mínima esperada.

No entrena nada — solo planifica. El plan resultante es lo que Pipeline
Generator (5.5) usará para escribir código real.

Insight clave de ASTRA: si la idea + dominio calzan con el pipeline forex
o business ya existentes (forex/prediction/, forex/business/), el plan
lo señala explícitamente en vez de proponer construir todo desde cero —
evita reinventar lo que ya está probado y en producción.

Patrón "graceful fail": si la viabilidad es insuficiente, no se genera un
plan — se explica por qué (mismo criterio que Feasibility Engine).

API pública:
  plan_models_from(problem_spec, dataset_report, feasibility_report) -> ModelPlan
  plan_model(csv_path, idea, target_variable=None)                   -> ModelPlan
  cmd_lab_planea(csv_path, idea)                                     -> str
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

from .prompt_analyzer import analyze_prompt, ProblemSpec
from .dataset_analyzer import analyze_dataset, DatasetReport
from .feasibility_engine import assess_feasibility_from, FeasibilityReport


# ══════════════════════════════════════════════════════════
#  ESTRUCTURAS DEL PLAN
# ══════════════════════════════════════════════════════════

@dataclass
class AlgorithmConfig:
    name:       str
    library:    str
    class_name: str
    params:     Dict[str, Any]
    role:       str      # "primary" | "ensemble_member" | "baseline"
    rationale:  str


@dataclass
class FeaturePlan:
    keep_as_is:  List[str] = field(default_factory=list)
    to_encode:   List[str] = field(default_factory=list)
    to_impute:   List[str] = field(default_factory=list)
    to_create:   List[str] = field(default_factory=list)
    to_drop:     List[str] = field(default_factory=list)


@dataclass
class ValidationStrategy:
    method:     str      # "wfv" | "kfold" | "holdout"
    n_splits:   int
    test_size:  float
    metric:     str
    use_smote:  bool
    calibrate:  bool


@dataclass
class ModelPlan:
    ok:                  bool = True
    error:               Optional[str] = None

    target_variable:     Optional[str] = None
    problem_type:        str = "unknown"
    domain:               str = "general"

    reuse_existing:      Optional[str] = None   # si aplica, qué módulo de ASTRA ya cubre esto
    algorithms:          List[AlgorithmConfig] = field(default_factory=list)
    feature_plan:        FeaturePlan = field(default_factory=FeaturePlan)
    validation:          ValidationStrategy = None
    preprocessing_steps: List[str] = field(default_factory=list)
    expected_min_metric: float = 0.5
    notes:               List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        if not self.ok:
            return f"[MODEL PLANNER] Error: {self.error}"

        lines = [
            "═" * 62,
            " MODEL PLANNER — Plan de Modelo",
            "═" * 62,
            f" Target       : {self.target_variable}",
            f" Tipo problema: {self.problem_type}   Dominio: {self.domain}",
        ]

        # Sin validation/algorithms no hay plan real que mostrar (ej: viabilidad
        # insuficiente) — se corta aquí y solo se listan las notas/motivos.
        if self.validation is None or not self.algorithms:
            lines += ["", " No se generó un plan de modelo."]
            if self.notes:
                lines.append("")
                lines.append(" Motivo:")
                for n in self.notes:
                    lines.append(f"   * {n}")
            lines.append("═" * 62)
            return "\n".join(lines)

        if self.reuse_existing:
            lines += [
                "",
                f" ⚠ REUTILIZAR EXISTENTE: {self.reuse_existing}",
                "   Antes de construir un pipeline nuevo, considera si el módulo",
                "   de arriba ya resuelve esto — evita duplicar trabajo ya probado.",
            ]

        v = self.validation
        lines += [
            "",
            f" Validación   : {v.method}  ({v.n_splits} folds, test={v.test_size:.0%})",
            f" Métrica      : {v.metric}  (mínimo esperado: {self.expected_min_metric:.2f})",
            f" SMOTE        : {'sí' if v.use_smote else 'no'}",
            f" Calibración  : {'sí' if v.calibrate else 'no'}",
            "",
            " Algoritmos:",
        ]
        for a in self.algorithms:
            lines.append(f"   [{a.role:<16}] {a.name:<16} ({a.library}) — {a.rationale}")

        if self.feature_plan.to_create:
            lines.append("")
            lines.append(" Features a crear:")
            for f in self.feature_plan.to_create:
                lines.append(f"   + {f}")

        if self.feature_plan.to_drop:
            lines.append("")
            lines.append(f" Columnas a descartar (>70% NaN): {', '.join(self.feature_plan.to_drop)}")

        if self.preprocessing_steps:
            lines.append("")
            lines.append(" Preprocesamiento:")
            for s in self.preprocessing_steps:
                lines.append(f"   - {s}")

        if self.notes:
            lines.append("")
            lines.append(" Notas:")
            for n in self.notes:
                lines.append(f"   * {n}")

        lines.append("═" * 62)
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════
#  SELECCIÓN DE ALGORITMOS
# ══════════════════════════════════════════════════════════

def _xgb_cfg(role: str, rows: int, regression: bool) -> AlgorithmConfig:
    n_est = 300 if rows >= 3000 else 150
    cls = "XGBRegressor" if regression else "XGBClassifier"
    params = {
        "n_estimators": n_est, "max_depth": 4, "learning_rate": 0.05,
        "subsample": 0.8, "colsample_bytree": 0.8, "random_state": 42,
    }
    if not regression:
        params["eval_metric"] = "logloss"
    return AlgorithmConfig("XGBoost", "xgboost", cls, params, role,
                            "Robusto ante outliers, maneja features mixtas")


def _lgbm_cfg(role: str, regression: bool) -> AlgorithmConfig:
    cls = "LGBMRegressor" if regression else "LGBMClassifier"
    params = {"n_estimators": 200, "max_depth": 4, "learning_rate": 0.05,
              "num_leaves": 31, "verbose": -1, "random_state": 42}
    return AlgorithmConfig("LightGBM", "lightgbm", cls, params, role,
                            "Rápido en datasets medianos/grandes, buen complemento del ensemble")


def _rf_cfg(role: str, regression: bool) -> AlgorithmConfig:
    cls = "RandomForestRegressor" if regression else "RandomForestClassifier"
    params = {"n_estimators": 100, "max_depth": 6, "n_jobs": -1, "random_state": 42}
    return AlgorithmConfig("RandomForest", "sklearn", cls, params, role,
                            "Diversifica el ensemble, resistente al sobreajuste")


def _linear_cfg(role: str, regression: bool) -> AlgorithmConfig:
    if regression:
        return AlgorithmConfig("LinearRegression", "sklearn", "LinearRegression", {}, role,
                                "Baseline interpretable")
    return AlgorithmConfig("LogisticRegression", "sklearn", "LogisticRegression",
                            {"max_iter": 1000, "random_state": 42}, role,
                            "Baseline interpretable")


def _kmeans_cfg() -> AlgorithmConfig:
    return AlgorithmConfig("KMeans", "sklearn", "KMeans",
                            {"n_clusters": 3, "n_init": 10, "random_state": 42}, "primary",
                            "Clustering simple — ajustar n_clusters según el caso")


def _select_algorithms(problem_type: str, n_rows: int) -> List[AlgorithmConfig]:
    if problem_type == "clustering":
        return [_kmeans_cfg()]

    regression = problem_type == "regression"
    algos = [_xgb_cfg("primary", n_rows, regression)]
    if n_rows >= 500:
        algos.append(_lgbm_cfg("ensemble_member", regression))
    if n_rows >= 1000:
        algos.append(_rf_cfg("ensemble_member", regression))
    algos.append(_linear_cfg("baseline", regression))
    return algos


# ══════════════════════════════════════════════════════════
#  PLAN DE FEATURES
# ══════════════════════════════════════════════════════════

_DATETIME_NAME_HINTS = ("timestamp", "date", "datetime", "fecha", "time")


def _looks_like_datetime_col(col_name: str) -> bool:
    """Heurística de nombre para detectar columnas de fecha/hora que NO deben
    pasar por OneHot/Ordinal encoding (crearían una dummy por cada valor único)."""
    name = col_name.lower()
    return any(h in name for h in _DATETIME_NAME_HINTS)


def _build_feature_plan(dataset_report: DatasetReport, problem_spec: Optional[ProblemSpec]) -> FeaturePlan:
    target = dataset_report.target_variable
    missing = dataset_report.missing_pct

    to_drop = [c for c, pct in missing.items() if pct > 70 and c != target]
    # Columnas de fecha/hora crudas: nunca se encodean como categóricas —
    # se descartan del pipeline directo (lag/rolling features ya cubren la
    # información temporal útil; ver to_create más abajo).
    datetime_cols = [c for c in dataset_report.non_numeric_cols
                      if c != target and _looks_like_datetime_col(c)]
    to_drop = to_drop + [c for c in datetime_cols if c not in to_drop]
    to_impute = [c for c in dataset_report.numeric_cols
                 if c != target and 0 < missing.get(c, 0) <= 70]
    to_encode = [c for c in dataset_report.non_numeric_cols
                 if c != target and c not in to_drop]
    keep = [c for c in dataset_report.numeric_cols
            if c != target and c not in to_drop and c not in to_impute]

    to_create: List[str] = []
    domain = problem_spec.domain if problem_spec else "general"
    is_timeseries = (problem_spec and problem_spec.problem_type == "timeseries") or domain == "forex"

    if is_timeseries:
        to_create += ["lag_1, lag_2, lag_3", "rolling_mean_5, rolling_std_5", "rolling_mean_20"]
    if domain == "forex":
        to_create.append(
            "(ya disponibles en forex/prediction/feature_engineering.py: ADX, stochastic, "
            "Williams %R, OBV, Bollinger width/squeeze/%B, patrones de vela, cruces EMA)"
        )
    if domain == "business":
        to_create += ["revenue_growth_mom", "rolling_margin_3m", "lag_revenue_1"]

    return FeaturePlan(
        keep_as_is=keep, to_encode=to_encode, to_impute=to_impute,
        to_create=to_create, to_drop=to_drop,
    )


# ══════════════════════════════════════════════════════════
#  ESTRATEGIA DE VALIDACIÓN
# ══════════════════════════════════════════════════════════

def _build_validation(problem_type: str, domain: str, n_rows: int,
                       dimension_scores: Dict[str, float]) -> ValidationStrategy:
    # BUGFIX: SMOTE solo tiene sentido para clasificación (sobremuestrea clases minoritarias);
    # el score de "balance" también se calcula para regresión (distribución del target), así
    # que sin este guard se podía activar SMOTE para un target continuo y romper el fit.
    use_smote = problem_type == "classification" and dimension_scores.get("balance", 100.0) < 55
    calibrate = problem_type in ("classification", "timeseries")

    if problem_type == "timeseries" or domain == "forex":
        method, n_splits, metric = "wfv", 5, "precision"
    elif problem_type == "regression":
        method, n_splits, metric = ("kfold", 5, "rmse") if n_rows >= 1000 else ("holdout", 1, "rmse")
    elif n_rows >= 3000:
        method, n_splits, metric = "kfold", 5, "f1"
    else:
        method, n_splits, metric = "holdout", 1, "roc_auc"

    return ValidationStrategy(
        method=method, n_splits=n_splits, test_size=0.20,
        metric=metric, use_smote=use_smote, calibrate=calibrate,
    )


def _preprocessing_steps(dataset_report: DatasetReport, feature_plan: FeaturePlan) -> List[str]:
    steps = []
    if any(v > 0 for v in dataset_report.missing_pct.values()):
        steps.append("Imputar NaN numéricos (SimpleImputer — strategy='median')")
    if feature_plan.to_encode:
        steps.append(f"Encodear {len(feature_plan.to_encode)} columna(s) no numérica(s) (OneHot / OrdinalEncoder)")
    if dataset_report.high_vif_features:
        steps.append(f"Revisar/eliminar multicolinealidad: {', '.join(dataset_report.high_vif_features[:5])}")
    steps.append("VarianceThreshold(threshold=0.01) para eliminar features casi constantes")
    return steps


def _reuse_hint(domain: str, problem_type: str) -> Optional[str]:
    if domain == "forex":
        return ("forex/prediction/integrated_pipeline.py — pipeline forex completo (MTF, ensemble "
                "XGB+LGB+RF calibrado, WFV, circuit breaker) ya implementado y validado.")
    if domain == "business":
        return ("forex/business/business_pipeline.py — pipeline de BI/PYME (KPIs, forecast, "
                "predictor de crecimiento) ya implementado.")
    return None


# ══════════════════════════════════════════════════════════
#  API PÚBLICA
# ══════════════════════════════════════════════════════════

def plan_models_from(problem_spec: ProblemSpec, dataset_report: DatasetReport,
                      feasibility_report: FeasibilityReport) -> ModelPlan:
    """Genera el ModelPlan ya con ProblemSpec + DatasetReport + FeasibilityReport en mano."""
    if not feasibility_report.ok:
        return ModelPlan(ok=False, error=feasibility_report.error)

    if not feasibility_report.is_viable:
        return ModelPlan(
            ok=True,
            target_variable=feasibility_report.target_variable,
            problem_type=feasibility_report.problem_type,
            domain=feasibility_report.domain,
            notes=[
                f"Viabilidad insuficiente ({feasibility_report.viability_index:.1f}/100 — mínimo 40) "
                "para generar un plan de modelo. Revisa 'lab viabilidad' antes de continuar.",
            ] + feasibility_report.blocking_issues,
        )

    n_rows = dataset_report.n_rows
    problem_type = feasibility_report.problem_type
    domain = feasibility_report.domain

    # BUGFIX: si el texto de la idea fue ambiguo (problem_type="unknown"), no asumir
    # classification por defecto — confiar en la evidencia real del dataset (el target
    # ya fue tipificado por el Dataset Analyzer) antes que en una interpretación de texto
    # libre que no pudo determinar nada.
    inferred_from_data = False
    if problem_type == "unknown":
        problem_type = "regression" if dataset_report.target_is_numeric else "classification"
        inferred_from_data = True

    algorithms = _select_algorithms(problem_type, n_rows)
    feature_plan = _build_feature_plan(dataset_report, problem_spec)
    validation = _build_validation(problem_type, domain, n_rows, feasibility_report.dimension_scores)
    preprocessing = _preprocessing_steps(dataset_report, feature_plan)

    # Métrica mínima esperada escala con la viabilidad: mientras mejor el dataset, más exigimos.
    expected_min_metric = round(max(0.50, min(0.85, 0.45 + feasibility_report.viability_index / 100 * 0.45)), 2)

    notes = []
    if inferred_from_data:
        notes.append(
            f"El tipo de problema no quedó claro en la idea — se infirió '{problem_type}' "
            f"a partir del target real del dataset ({'numérico' if dataset_report.target_is_numeric else 'categórico'})."
        )
    if feasibility_report.viability_index < 60:
        notes.append("Viabilidad moderada — trata el primer modelo como baseline exploratorio, no como final.")
    if problem_spec and problem_spec.confidence < 0.5:
        notes.append("El Prompt Analyzer tuvo baja confianza al interpretar la idea — revisa el problem_type antes de entrenar.")
    notes.extend(feasibility_report.suggestions)

    return ModelPlan(
        ok=True,
        target_variable=feasibility_report.target_variable,
        problem_type=problem_type,
        domain=domain,
        reuse_existing=_reuse_hint(domain, problem_type),
        algorithms=algorithms,
        feature_plan=feature_plan,
        validation=validation,
        preprocessing_steps=preprocessing,
        expected_min_metric=expected_min_metric,
        notes=notes,
    )


def plan_model(csv_path: str, idea: str, target_variable: Optional[str] = None) -> ModelPlan:
    """
    Punto de entrada de alto nivel: idea en lenguaje natural + CSV -> ModelPlan.
    Encadena internamente 5.1 -> 5.2 -> 5.3 -> 5.4.
    """
    problem_spec = analyze_prompt(idea)
    dataset_report = analyze_dataset(csv_path, target_variable=target_variable, problem_spec=problem_spec)
    feasibility_report = assess_feasibility_from(problem_spec, dataset_report)
    return plan_models_from(problem_spec, dataset_report, feasibility_report)


def cmd_lab_planea(csv_path: str, idea: str, target_variable=None) -> str:
    """Comando CLI: 'lab planea <csv> \"<idea>\" [target]' — para wiring en main.py."""
    if not csv_path or not idea:
        return 'Uso: lab planea <archivo.csv> "<describe tu idea>" [columna_target]'
    plan = plan_model(csv_path, idea, target_variable=target_variable)
    return plan.summary()

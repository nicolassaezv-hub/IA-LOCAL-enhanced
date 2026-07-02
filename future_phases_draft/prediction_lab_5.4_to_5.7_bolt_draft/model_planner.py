"""
prediction_lab/model_planner.py — ASTRA Phase 5.4

Dado un FeasibilityScore + ProblemSpec, genera un ModelPlan.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .feasibility_engine import FeasibilityScore
from .prompt_analyzer import ProblemSpec


@dataclass
class AlgorithmConfig:
    name: str
    library: str
    class_name: str
    params: Dict
    role: str
    rationale: str


@dataclass
class FeaturePlan:
    keep_as_is: List[str]
    to_encode: List[str]
    to_impute: List[str]
    to_create: List[str]
    to_drop: List[str]


@dataclass
class ValidationStrategy:
    method: str
    n_splits: int
    test_size: float
    metric: str
    use_smote: bool
    calibrate: bool

    def metric_threshold(self, base: float) -> float:
        return base


@dataclass
class ModelPlan:
    algorithms: List[AlgorithmConfig]
    feature_plan: FeaturePlan
    validation: ValidationStrategy
    target_col: str
    preprocessing_steps: List[str]
    expected_min_metric: float
    notes: List[str] = field(default_factory=list)

    def summary(self) -> str:
        algo_lines = [f"  [{a.role.upper()}] {a.name} ({a.library}) — {a.rationale}" for a in self.algorithms]
        lines = [
            f"Target       : {self.target_col}",
            f"Validación   : {self.validation.method}  ({self.validation.n_splits} folds / test={self.validation.test_size:.0%})",
            f"Métrica      : {self.validation.metric}  (mínimo: {self.expected_min_metric:.2f})",
            f"SMOTE        : {'Sí' if self.validation.use_smote else 'No'}",
            "", "Algoritmos:",
        ] + algo_lines + ["", "Features a crear:"] + [f"  + {f}" for f in self.feature_plan.to_create]
        if self.notes:
            lines += ["", "Notas:"] + [f"  * {n}" for n in self.notes]
        return "\n".join(lines)


def _xgb_cfg(role="primary", rows=1000):
    n_est = 300 if rows >= 3000 else 150
    return AlgorithmConfig("XGBoost", "xgboost", "XGBClassifier",
        {"n_estimators": n_est, "max_depth": 4, "learning_rate": 0.05, "subsample": 0.8,
         "colsample_bytree": 0.8, "use_label_encoder": False, "eval_metric": "logloss", "random_state": 42},
        role, "Robusto ante outliers, maneja features mixtas")

def _lgbm_cfg(role="ensemble_member", rows=1000):
    return AlgorithmConfig("LightGBM", "lightgbm", "LGBMClassifier",
        {"n_estimators": 200, "max_depth": 4, "learning_rate": 0.05, "num_leaves": 31, "verbose": -1, "random_state": 42},
        role, "Más rápido en datasets grandes, buen complemento")

def _rf_cfg(role="ensemble_member"):
    return AlgorithmConfig("RandomForest", "sklearn", "RandomForestClassifier",
        {"n_estimators": 100, "max_depth": 6, "n_jobs": -1, "random_state": 42},
        role, "Diversifica el ensemble, resistente al sobreajuste")

def _lr_cfg(role="baseline"):
    return AlgorithmConfig("LogisticRegression", "sklearn", "LogisticRegression",
        {"max_iter": 1000, "random_state": 42}, role, "Baseline interpretable")

def _iso_forest_cfg():
    return AlgorithmConfig("IsolationForest", "sklearn", "IsolationForest",
        {"n_estimators": 100, "contamination": 0.05, "random_state": 42},
        "primary", "Detector de anomalías no supervisado")


class ModelPlanner:
    def plan(self, feasibility: FeasibilityScore, spec: Optional[ProblemSpec] = None) -> ModelPlan:
        da = feasibility.dataset_analysis
        ptype = spec.problem_type if spec else "classification"
        rows = da.rows
        algorithms = self._select_algorithms(ptype, rows)
        feature_plan = self._build_feature_plan(da, spec)
        validation = self._build_validation(ptype, da, feasibility)
        target = (spec.target_column if spec and spec.target_column
                  else (da.target_candidates[0] if da.target_candidates else "target"))
        preprocessing = self._preprocessing_steps(da, spec)
        min_metric = round(max(0.50, min(0.85, 0.45 + feasibility.viability_index / 100 * 0.45)), 2)
        notes = []
        if feasibility.estimated_effort == "high":
            notes.append("Dataset requiere preparación significativa")
        if spec and spec.confidence < 0.50:
            notes.append("Descripción ambigua — revisa el problem_type")
        return ModelPlan(algorithms=algorithms, feature_plan=feature_plan, validation=validation,
            target_col=target, preprocessing_steps=preprocessing, expected_min_metric=min_metric, notes=notes)

    def _select_algorithms(self, ptype, rows):
        if ptype == "anomaly":
            return [_iso_forest_cfg(), _lr_cfg("baseline")]
        algos = [_xgb_cfg("primary", rows)]
        if rows >= 500: algos.append(_lgbm_cfg("ensemble_member", rows))
        if rows >= 1000: algos.append(_rf_cfg("ensemble_member"))
        algos.append(_lr_cfg("baseline"))
        return algos

    def _build_feature_plan(self, da, spec):
        to_drop = [p.name for p in da.column_profiles if p.missing_pct > 70]
        to_impute = [p.name for p in da.column_profiles if 0 < p.missing_pct <= 70 and p.is_numeric]
        to_encode = [p.name for p in da.column_profiles if p.is_categorical and p.unique_count <= 20]
        keep = [p.name for p in da.column_profiles if p.name not in to_drop and p.name not in to_encode]
        to_create = []
        if da.is_timeseries:
            to_create += ["lag_1, lag_2, lag_3", "rolling_mean_5, rolling_std_5", "rolling_mean_20"]
        if spec and spec.domain == "forex":
            to_create += ["RSI_14, MACD, ATR_14, EMA20, EMA50", "BB_position, ADX_14", "session_tokyo, session_london, session_newyork"]
        if spec and spec.domain == "business":
            to_create += ["revenue_growth_mom", "rolling_margin_3m", "lag_revenue_1"]
        return FeaturePlan(keep_as_is=keep, to_encode=to_encode, to_impute=to_impute, to_create=to_create, to_drop=to_drop)

    def _build_validation(self, ptype, da, fs):
        use_smote = fs.scores.get("target_balance", 100) < 55
        calibrate = ptype in ("classification", "timeseries")
        if ptype == "timeseries" or da.is_timeseries:
            method, n_splits, metric = "wfv", 5, "precision"
        elif da.rows >= 3000:
            method, n_splits, metric = "kfold", 5, "f1"
        else:
            method, n_splits, metric = "holdout", 1, "roc_auc"
        return ValidationStrategy(method=method, n_splits=n_splits, test_size=0.20,
            metric=metric, use_smote=use_smote, calibrate=calibrate)

    def _preprocessing_steps(self, da, spec):
        steps = []
        if da.missing_pct_overall > 0:
            steps.append("Imputar NaN (SimpleImputer — strategy='median')")
        cats = [p for p in da.column_profiles if p.is_categorical and p.unique_count <= 20]
        if cats:
            steps.append(f"Encodear {len(cats)} columnas categóricas")
        steps.append("VarianceThreshold(threshold=0.01) para eliminar features near-zero")
        return steps


_planner = ModelPlanner()


def plan_models(feasibility: FeasibilityScore, spec: Optional[ProblemSpec] = None) -> ModelPlan:
    return _planner.plan(feasibility, spec)


def cmd_lab_planear(filepath: str, prompt: str = "") -> str:
    if not filepath:
        return "Uso: lab planear <archivo.csv> [descripción]"
    try:
        from .prompt_analyzer import analyze_prompt
        from .feasibility_engine import check_feasibility_from_file
        spec = analyze_prompt(prompt) if prompt else None
        fs = check_feasibility_from_file(filepath, spec)
        if not fs.is_viable:
            return f"Viabilidad insuficiente ({fs.viability_index:.1f}/100)."
        plan = plan_models(fs, spec)
        return (
            f"\n{'═' * 60}\n"
            f"  ASTRA Prediction Lab — Plan de Modelo\n"
            f"{'═' * 60}\n"
            f"{plan.summary()}\n"
            f"{'═' * 60}"
        )
    except Exception as e:
        return f"Error planeando modelo: {e}"

"""
prediction_lab/pipeline_generator.py — ASTRA Phase 5.5

Construye un sklearn Pipeline ejecutable desde un ModelPlan.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from .model_planner import AlgorithmConfig, ModelPlan


@dataclass
class GeneratedPipeline:
    pipeline: Any
    feature_names: List[str]
    target_col: str
    model_plan: ModelPlan
    code_snippet: str
    meta: Dict = field(default_factory=dict)

    def summary(self) -> str:
        steps = [(name, type(obj).__name__) for name, obj in self.pipeline.steps]
        step_lines = [f"  {i+1}. {name}: {cls}" for i, (name, cls) in enumerate(steps)]
        return (
            f"Pipeline generado ({len(steps)} pasos):\n"
            + "\n".join(step_lines)
            + f"\n\nFeatures usadas : {len(self.feature_names)}\nTarget          : {self.target_col}"
        )


def _build_estimator(cfg: AlgorithmConfig) -> Any:
    if cfg.library == "xgboost":
        try:
            import xgboost as xgb
            return getattr(xgb, cfg.class_name)(**cfg.params)
        except ImportError:
            pass
    if cfg.library == "lightgbm":
        try:
            import lightgbm as lgb
            return getattr(lgb, cfg.class_name)(**cfg.params)
        except ImportError:
            pass
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression, Ridge
    sklearn_map = {
        "RandomForestClassifier": RandomForestClassifier,
        "LogisticRegression": LogisticRegression,
        "Ridge": Ridge,
        "GradientBoostingClassifier": GradientBoostingClassifier,
        "XGBClassifier": GradientBoostingClassifier,
        "XGBRegressor": Ridge,
        "LGBMClassifier": GradientBoostingClassifier,
        "IsolationForest": __import__("sklearn.ensemble", fromlist=["IsolationForest"]).IsolationForest,
    }
    cls = sklearn_map.get(cfg.class_name, RandomForestClassifier)
    safe_params = {k: v for k, v in cfg.params.items() if k in ("n_estimators", "max_depth", "random_state", "n_jobs")}
    return cls(**safe_params)


class PipelineGenerator:
    def generate(self, plan: ModelPlan, df: Optional[pd.DataFrame] = None) -> GeneratedPipeline:
        from sklearn.pipeline import Pipeline
        from sklearn.impute import SimpleImputer
        from sklearn.feature_selection import VarianceThreshold

        if df is not None:
            num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            feature_names = [c for c in num_cols if c != plan.target_col]
        else:
            feature_names = [f for f in plan.feature_plan.keep_as_is if f != plan.target_col]
        feature_names = [f for f in feature_names if f not in plan.feature_plan.to_drop]

        primaries = [a for a in plan.algorithms if a.role == "primary"] or plan.algorithms[:1]
        members = [a for a in plan.algorithms if a.role == "ensemble_member"]
        primary = primaries[0]

        if members:
            from sklearn.ensemble import VotingClassifier
            estimators = [(primary.name, _build_estimator(primary))] + [(m.name, _build_estimator(m)) for m in members]
            estimator = VotingClassifier(estimators=estimators, voting="soft")
        else:
            estimator = _build_estimator(primary)

        steps = [
            ("imputer", SimpleImputer(strategy="median")),
            ("variance", VarianceThreshold(threshold=0.01)),
            ("estimator", estimator),
        ]
        pipeline = Pipeline(steps)
        code = self._generate_code(plan, feature_names)
        return GeneratedPipeline(
            pipeline=pipeline, feature_names=feature_names, target_col=plan.target_col,
            model_plan=plan, code_snippet=code,
            meta={"n_features": len(feature_names), "estimator": type(estimator).__name__, "n_steps": len(steps)},
        )

    def _generate_code(self, plan, feature_names):
        primary = next((a for a in plan.algorithms if a.role == "primary"), plan.algorithms[0])
        val = plan.validation
        feat_repr = str(feature_names[:15])
        return "\n".join([
            "# generado por ASTRA Prediction Lab",
            "import pandas as pd, numpy as np",
            "from sklearn.pipeline import Pipeline",
            "from sklearn.impute import SimpleImputer",
            "from sklearn.feature_selection import VarianceThreshold",
            "from sklearn.model_selection import train_test_split",
            "",
            f"FEATURES = {feat_repr}",
            f"TARGET = '{plan.target_col}'",
            "",
            "df = pd.read_csv('tu_dataset.csv')",
            "X = df[FEATURES]",
            "y = df[TARGET]",
            "",
            f"# Primary: {primary.name} | Validation: {val.method}, metric={val.metric}",
            "X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)",
            "# pipeline.fit(X_train, y_train)",
            "# print('Score:', pipeline.score(X_test, y_test))",
        ])


_generator = PipelineGenerator()


def generate_pipeline(plan: ModelPlan, df: Optional[pd.DataFrame] = None) -> GeneratedPipeline:
    return _generator.generate(plan, df)

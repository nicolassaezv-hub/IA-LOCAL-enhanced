"""
prediction_lab/validation_engine.py — ASTRA Phase 5.6

Entrena el pipeline y valida con holdout/kfold/WFV.
"""

from __future__ import annotations
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")
from .pipeline_generator import GeneratedPipeline
from .model_planner import ValidationStrategy


@dataclass
class FoldResult:
    fold: int
    train_size: int
    test_size: int
    score: float
    metric: str


@dataclass
class ValidationResult:
    method: str
    metric: str
    mean_score: float
    std_score: float
    fold_results: List[FoldResult]
    feature_importance: Dict[str, float]
    passes: bool
    min_expected: float
    trained_pipeline: Any
    warnings: List[str] = field(default_factory=list)

    def summary(self) -> str:
        verdict = "PASA" if self.passes else "NO PASA"
        lines = [
            f"Método       : {self.method}",
            f"Métrica      : {self.metric}",
            f"Score medio  : {self.mean_score:.4f}  ±{self.std_score:.4f}",
            f"Mínimo req.  : {self.min_expected:.4f}",
            f"Veredicto    : {verdict}",
            "", "Por fold:",
        ]
        for fr in self.fold_results:
            lines.append(f"  Fold {fr.fold:2d}: {fr.score:.4f}  (train={fr.train_size:,}  test={fr.test_size:,})")
        if self.feature_importance:
            lines += ["", "Top features:"]
            for feat, imp in sorted(self.feature_importance.items(), key=lambda x: -x[1])[:10]:
                lines.append(f"  {feat:30s}: {imp:.4f}")
        if self.warnings:
            lines += ["", "Avisos:"] + [f"  ! {w}" for w in self.warnings]
        return "\n".join(lines)


class ValidationEngine:
    def validate(self, gp: GeneratedPipeline, df: pd.DataFrame) -> ValidationResult:
        strategy = gp.model_plan.validation
        features = self._align_features(gp, df)
        target = gp.target_col
        if target not in df.columns:
            raise ValueError(f"Target '{target}' no encontrado")
        X = df[features].copy()
        y = df[target].copy()
        if strategy.method == "holdout":
            return self._holdout(gp, X, y, strategy)
        if strategy.method == "kfold":
            return self._kfold(gp, X, y, strategy)
        return self._wfv(gp, X, y, strategy)

    def _holdout(self, gp, X, y, strategy):
        from sklearn.model_selection import train_test_split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=strategy.test_size, random_state=42)
        X_train, y_train = self._apply_smote(X_train, y_train, strategy)
        pipeline = self._clone_pipeline(gp)
        pipeline.fit(X_train, y_train)
        score = self._score(pipeline, X_test, y_test, strategy.metric)
        fi = self._feature_importance(pipeline, list(X.columns))
        return ValidationResult(method="holdout", metric=strategy.metric, mean_score=score, std_score=0.0,
            fold_results=[FoldResult(1, len(X_train), len(X_test), score, strategy.metric)],
            feature_importance=fi, passes=score >= gp.model_plan.expected_min_metric,
            min_expected=gp.model_plan.expected_min_metric, trained_pipeline=pipeline,
            warnings=self._check_warnings(score, strategy))

    def _kfold(self, gp, X, y, strategy):
        from sklearn.model_selection import StratifiedKFold, KFold
        try:
            cv = StratifiedKFold(n_splits=strategy.n_splits, shuffle=True, random_state=42)
            list(cv.split(X, y))
        except Exception:
            cv = KFold(n_splits=strategy.n_splits, shuffle=True, random_state=42)
        scores, fold_results, last_pipeline = [], [], None
        for fold, (tr, te) in enumerate(cv.split(X, y), 1):
            X_tr, X_te = X.iloc[tr], X.iloc[te]
            y_tr, y_te = y.iloc[tr], y.iloc[te]
            X_tr, y_tr = self._apply_smote(X_tr, y_tr, strategy)
            pipeline = self._clone_pipeline(gp)
            pipeline.fit(X_tr, y_tr)
            s = self._score(pipeline, X_te, y_te, strategy.metric)
            scores.append(s)
            fold_results.append(FoldResult(fold, len(X_tr), len(X_te), s, strategy.metric))
            last_pipeline = pipeline
        mean_s, std_s = float(np.mean(scores)), float(np.std(scores))
        fi = self._feature_importance(last_pipeline, list(X.columns))
        return ValidationResult(method="kfold", metric=strategy.metric, mean_score=round(mean_s, 4), std_score=round(std_s, 4),
            fold_results=fold_results, feature_importance=fi, passes=mean_s >= gp.model_plan.expected_min_metric,
            min_expected=gp.model_plan.expected_min_metric, trained_pipeline=last_pipeline,
            warnings=self._check_warnings(mean_s, strategy))

    def _wfv(self, gp, X, y, strategy, window=2000, step=500, purge=10):
        n = len(X)
        if n < window + step:
            window, step = int(n * 0.6), int(n * 0.2)
        scores, fold_results, last_pipeline, fold, start = [], [], None, 0, 0
        while start + window + step <= n:
            fold += 1
            train_end = start + window
            test_start = train_end + purge
            test_end = test_start + step
            if test_end > n:
                break
            X_tr, y_tr = X.iloc[start:train_end], y.iloc[start:train_end]
            X_te, y_te = X.iloc[test_start:test_end], y.iloc[test_start:test_end]
            X_tr, y_tr = self._apply_smote(X_tr, y_tr, strategy)
            pipeline = self._clone_pipeline(gp)
            pipeline.fit(X_tr, y_tr)
            s = self._score(pipeline, X_te, y_te, strategy.metric)
            scores.append(s)
            fold_results.append(FoldResult(fold, len(X_tr), len(X_te), s, strategy.metric))
            last_pipeline = pipeline
            start += step
        if not scores:
            scores, fold_results = [0.0], [FoldResult(1, 0, 0, 0.0, strategy.metric)]
        mean_s, std_s = float(np.mean(scores)), float(np.std(scores))
        fi = self._feature_importance(last_pipeline, list(X.columns)) if last_pipeline else {}
        passes = mean_s >= gp.model_plan.expected_min_metric or (
            len(scores) >= 2 and float(np.median(scores)) >= gp.model_plan.expected_min_metric + 0.05)
        return ValidationResult(method="wfv", metric=strategy.metric, mean_score=round(mean_s, 4), std_score=round(std_s, 4),
            fold_results=fold_results, feature_importance=fi, passes=passes,
            min_expected=gp.model_plan.expected_min_metric, trained_pipeline=last_pipeline,
            warnings=self._check_warnings(mean_s, strategy))

    def _clone_pipeline(self, gp):
        from sklearn.base import clone
        return clone(gp.pipeline)

    def _align_features(self, gp, df):
        available = set(df.columns)
        aligned = [f for f in gp.feature_names if f in available]
        if not aligned:
            aligned = [c for c in df.select_dtypes(include=[np.number]).columns if c != gp.target_col]
        return aligned

    def _apply_smote(self, X, y, strategy):
        if not strategy.use_smote:
            return X, y
        try:
            from imblearn.over_sampling import SMOTE
            sm = SMOTE(random_state=42, k_neighbors=min(5, y.value_counts().min() - 1))
            return sm.fit_resample(X, y)
        except Exception:
            return X, y

    def _score(self, pipeline, X_test, y_test, metric):
        try:
            y_pred = pipeline.predict(X_test)
            if metric == "accuracy":
                from sklearn.metrics import accuracy_score
                return accuracy_score(y_test, y_pred)
            if metric == "f1":
                from sklearn.metrics import f1_score
                return f1_score(y_test, y_pred, average="weighted", zero_division=0)
            if metric == "precision":
                from sklearn.metrics import precision_score
                return precision_score(y_test, y_pred, average="weighted", zero_division=0)
            if metric == "roc_auc":
                try:
                    y_prob = pipeline.predict_proba(X_test)[:, 1]
                    from sklearn.metrics import roc_auc_score
                    return roc_auc_score(y_test, y_prob)
                except Exception:
                    from sklearn.metrics import accuracy_score
                    return accuracy_score(y_test, y_pred)
            from sklearn.metrics import mean_squared_error
            return 1.0 / (1.0 + np.sqrt(mean_squared_error(y_test, y_pred)))
        except Exception:
            return 0.0

    def _feature_importance(self, pipeline, feature_names):
        if pipeline is None:
            return {}
        try:
            estimator = pipeline.named_steps.get("estimator") or pipeline.named_steps.get("model")
            if estimator is None:
                return {}
            if hasattr(estimator, "estimators_"):
                estimator = estimator.estimators_[0]
            if hasattr(estimator, "feature_importances_"):
                fi = estimator.feature_importances_
                n = min(len(fi), len(feature_names))
                pairs = sorted(zip(feature_names[:n], fi[:n]), key=lambda x: -x[1])[:15]
                return {k: round(float(v), 4) for k, v in pairs}
        except Exception:
            pass
        return {}

    def _check_warnings(self, score, strategy):
        warns = []
        if score < 0.50:
            warns.append(f"Score muy bajo ({score:.4f}) — el modelo no es mejor que azar")
        return warns


_engine = ValidationEngine()


def validate_models(gp: GeneratedPipeline, df: pd.DataFrame) -> ValidationResult:
    return _engine.validate(gp, df)

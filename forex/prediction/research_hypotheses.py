"""Frozen, non-production helpers for explicitly authorized Forex research.

Nothing in this module persists artifacts or integrates with prediction,
retraining, lifecycle eligibility, activation, or promotion.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import NotFittedError


_FIXED_H1_RANDOM_FOREST_CONFIG = {
    "n_estimators": 300,
    "max_depth": 8,
    "min_samples_leaf": 15,
    "class_weight_strategy": "TRAIN_NEGATIVE_TO_POSITIVE_RATIO",
    "random_state": 42,
    "n_jobs": -1,
}


def fixed_h1_random_forest_config() -> dict:
    """Return a copy of the exact configuration frozen by the benchmark."""
    return dict(_FIXED_H1_RANDOM_FOREST_CONFIG)


class FixedHorizonRandomForestClassifier:
    """Small research-only wrapper around the frozen H1 Random Forest."""

    def __init__(self):
        self.model_: RandomForestClassifier | None = None
        self.resolved_config_: dict | None = None

    def fit(self, X, y):
        targets = np.asarray(y)
        positives = int(np.sum(targets == 1))
        negatives = int(np.sum(targets == 0))
        if positives == 0 or negatives == 0 or positives + negatives != len(targets):
            raise ValueError("RESEARCH_TARGET_REQUIRES_BOTH_BINARY_CLASSES")

        class_weight = {0: 1.0, 1: negatives / positives}
        self.resolved_config_ = {
            **fixed_h1_random_forest_config(),
            "class_weight": class_weight,
        }
        self.model_ = RandomForestClassifier(
            n_estimators=_FIXED_H1_RANDOM_FOREST_CONFIG["n_estimators"],
            max_depth=_FIXED_H1_RANDOM_FOREST_CONFIG["max_depth"],
            min_samples_leaf=_FIXED_H1_RANDOM_FOREST_CONFIG[
                "min_samples_leaf"
            ],
            class_weight=class_weight,
            random_state=_FIXED_H1_RANDOM_FOREST_CONFIG["random_state"],
            n_jobs=_FIXED_H1_RANDOM_FOREST_CONFIG["n_jobs"],
        )
        self.model_.fit(X, targets)
        return self

    def _fitted_model(self) -> RandomForestClassifier:
        if self.model_ is None:
            raise NotFittedError(
                "FixedHorizonRandomForestClassifier is not fitted"
            )
        return self.model_

    def predict_proba(self, X):
        return self._fitted_model().predict_proba(X)

    def predict(self, X):
        return self._fitted_model().predict(X)


def mean_reversion_score(close, *, horizon: int = 12) -> pd.Series:
    """Return the frozen binary mean-reversion score using only past closes."""
    horizon = int(horizon)
    if horizon <= 0:
        raise ValueError(f"COMPARATOR_HORIZON_OUT_OF_RANGE: {horizon}")
    close_series = pd.Series(close, copy=False)
    past_return = close_series / close_series.shift(horizon) - 1.0
    score = pd.Series(np.nan, index=close_series.index, dtype=float)
    available = past_return.notna()
    score.loc[available] = (past_return.loc[available] <= 0.0).astype(float)
    return score


def current_outer_research_gate(
    rf_folds: list[dict], comparator_folds: list[dict]
) -> bool:
    """Evaluate the immutable, research-only current-outer acceptance gate."""
    if len(rf_folds) != 2 or len(comparator_folds) != 2:
        return False
    try:
        rf_auc = [float(fold["auc"]) for fold in rf_folds]
        rf_lift = [float(fold["ap_lift"]) for fold in rf_folds]
        comparator_auc = [float(fold["auc"]) for fold in comparator_folds]
        comparator_lift = [
            float(fold["ap_lift"]) for fold in comparator_folds
        ]
    except (KeyError, TypeError, ValueError):
        return False

    values = rf_auc + rf_lift + comparator_auc + comparator_lift
    if not all(math.isfinite(value) for value in values):
        return False

    rf_median_auc = float(np.median(rf_auc))
    rf_median_lift = float(np.median(rf_lift))
    comparator_median_auc = float(np.median(comparator_auc))
    comparator_median_lift = float(np.median(comparator_lift))
    return bool(
        all(value > 0.50 for value in rf_auc)
        and rf_median_auc >= 0.55
        and all(value > 0.0 for value in rf_lift)
        and rf_median_lift > 0.0
        and rf_median_auc > comparator_median_auc
        and rf_median_lift > comparator_median_lift
    )

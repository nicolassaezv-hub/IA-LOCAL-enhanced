"""
xgb_trainer.py — Ensemble trainer: XGBoost + LightGBM + RandomForest

Key improvements vs original:
- Soft-voting ensemble averaging probabilities across 3 model types
- Probability calibration (isotonic) so confidence scores are trustworthy
- Optimizes PRECISION (fewer false signals) not just accuracy
- Accepts pre-tuned hyperparameters from ForexHyperparameterTuner
- Auto-loads saved tuned params per pair when available
"""

import json
import os
import warnings
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    precision_score,
    f1_score,
)
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.calibration import CalibratedClassifierCV
from .model_storage import ModelStorage

warnings.filterwarnings("ignore")

try:
    from xgboost import XGBClassifier
    _HAS_XGB = True
except ImportError:
    _HAS_XGB = False

try:
    import lightgbm as lgb
    _HAS_LGB = True
except ImportError:
    _HAS_LGB = False

PARAMS_DIR = "models/forex/params"


def _load_tuned_params(pair: str) -> dict:
    """Load Optuna-tuned params saved for a specific pair, if they exist."""
    if not pair:
        return {}
    clean = pair.upper().replace("/", "").replace("_", "")
    path  = os.path.join(PARAMS_DIR, f"best_params_{clean}.json")
    if os.path.exists(path):
        with open(path) as f:
            params = json.load(f)
        print(f"[ENSEMBLE] Loaded tuned params for {clean} from {path}")
        return params
    return {}


class ForexEnsembleTrainer:
    """
    Soft-voting ensemble of XGBoost + LightGBM + RandomForest.
    Falls back gracefully if a library is missing.
    Uses Optuna-tuned params automatically when available.

    Why ensemble?
    - Each model has different inductive biases.
    - Averaged probabilities are better calibrated than a single model.
    - When all three agree, the signal is genuinely stronger.
    """

    def __init__(self, pair: str = None):
        self.storage      = ModelStorage()
        self.best_score   = 0.0
        self.best_model   = None
        self.model        = None
        self.pair         = pair
        self._tuned       = _load_tuned_params(pair) if pair else {}

    # -----------------------------
    # BUILD INDIVIDUAL MODELS
    # Uses tuned params if available, else sensible defaults.
    # -----------------------------
    def _build_xgb(self, scale: float = 1.0):
        p = self._tuned.get("xgb", {})
        if p:
            p = {k: v for k, v in p.items() if k != "early_stopping_rounds"}
            return XGBClassifier(
                **p,
                scale_pos_weight=scale,
                eval_metric="logloss",
                early_stopping_rounds=40,
                verbosity=0,
            )
        return XGBClassifier(
            n_estimators=600,
            max_depth=6,
            learning_rate=0.04,
            subsample=0.8,
            colsample_bytree=0.75,
            min_child_weight=3,
            gamma=0.1,
            reg_alpha=0.1,
            reg_lambda=1.0,
            scale_pos_weight=scale,
            random_state=42,
            eval_metric="logloss",
            early_stopping_rounds=40,
            verbosity=0,
        )

    def _build_lgb(self, scale: float = 1.0):
        p = self._tuned.get("lgb", {})
        if p:
            return lgb.LGBMClassifier(**p, scale_pos_weight=scale, verbose=-1)
        return lgb.LGBMClassifier(
            n_estimators=600,
            max_depth=6,
            learning_rate=0.04,
            subsample=0.8,
            colsample_bytree=0.75,
            min_child_samples=20,
            scale_pos_weight=scale,
            random_state=42,
            verbose=-1,
        )

    def _build_rf(self, scale: float = 1.0):
        return RandomForestClassifier(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=10,
            class_weight={0: 1.0, 1: scale},
            random_state=42,
            n_jobs=-1,
        )

    # -----------------------------
    # TIME-BASED SPLIT (NO LEAKAGE)
    # -----------------------------
    def train_test_split(self, X, y, train_ratio: float = 0.80):
        split = int(len(X) * train_ratio)
        return X.iloc[:split], X.iloc[split:], y.iloc[:split], y.iloc[split:]

    # -----------------------------
    # TRAIN ENSEMBLE
    # -----------------------------
    def train(self, X, y, save: bool = True):
        X_train, X_test, y_train, y_test = self.train_test_split(X, y)

        # Split test set into calibration + evaluation to avoid data leakage
        cal_split = max(1, len(X_test) // 2)
        X_cal, X_eval = X_test.iloc[:cal_split], X_test.iloc[cal_split:]
        y_cal, y_eval = y_test.iloc[:cal_split], y_test.iloc[cal_split:]

        n_pos = int(y_train.sum())
        n_neg = int((y_train == 0).sum())
        scale = n_neg / n_pos if n_pos > 0 else 1.0

        using_tuned = "YES ✓" if self._tuned else "NO (using defaults)"
        print(f"\n[ENSEMBLE] Training on {len(X_train)} rows | calibrating on {len(X_cal)} | validating on {len(X_eval)} rows")
        print(f"[ENSEMBLE] Pair: {self.pair or 'unknown'} | Tuned params: {using_tuned}")
        print(f"[ENSEMBLE] Class balance — bullish: {n_pos} | bearish: {n_neg} | weight: {scale:.2f}")

        estimators = []

        if _HAS_XGB:
            print("[ENSEMBLE] Fitting XGBoost...")
            xgb_m = self._build_xgb(scale)
            xgb_m.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
                verbose=False,
            )
            estimators.append(("xgb", xgb_m))

        if _HAS_LGB:
            print("[ENSEMBLE] Fitting LightGBM...")
            lgb_m = self._build_lgb(scale)
            lgb_m.fit(X_train, y_train)
            estimators.append(("lgb", lgb_m))

        print("[ENSEMBLE] Fitting RandomForest...")
        rf_m = self._build_rf(scale)
        rf_m.fit(X_train, y_train)
        estimators.append(("rf", rf_m))

        if len(estimators) == 1:
            raw_model = estimators[0][1]
        else:
            raw_model = VotingClassifier(estimators=estimators, voting="soft")
            raw_model.fit(X_train, y_train)

        # Calibrate probabilities on a separate holdout (prevents data leakage)
        self.model = CalibratedClassifierCV(raw_model, method="isotonic", cv="prefit")
        self.model.fit(X_cal, y_cal)

        preds = self.model.predict(X_eval)
        acc   = accuracy_score(y_eval, preds)
        prec  = precision_score(y_eval, preds, zero_division=0)
        f1    = f1_score(y_eval, preds, zero_division=0)

        print(f"\n=== ENSEMBLE PERFORMANCE ===")
        print(f"Accuracy   : {acc:.4f}")
        print(f"Precision  : {prec:.4f}  ← key metric for profitability")
        print(f"F1 Score   : {f1:.4f}")
        print(f"\n{classification_report(y_eval, preds, target_names=['Bearish', 'Bullish'], zero_division=0)}")

        self._print_feature_importance(estimators, list(X_train.columns))

        if prec > self.best_score:
            self.best_score = prec
            self.best_model = self.model
            print(f"[ENSEMBLE] New BEST model (precision={prec:.4f}) — saving...")
            if save:
                name = f"ensemble_{self.pair or 'forex'}_best"
                self.storage.save_model(model=self.model, name=name)
        else:
            print(f"[ENSEMBLE] Not better than current best precision ({self.best_score:.4f}). Not saved.")

        return acc, prec

    # -----------------------------
    # FEATURE IMPORTANCE
    # -----------------------------
    def _print_feature_importance(self, estimators, feature_names):
        for name, est in estimators:
            if name in ("xgb", "lgb") and hasattr(est, "feature_importances_"):
                ranking = sorted(
                    zip(feature_names, est.feature_importances_),
                    key=lambda x: x[1], reverse=True,
                )
                print(f"\n=== {name.upper()} FEATURE IMPORTANCE (top 15) ===")
                for feat, score in ranking[:15]:
                    bar = "█" * int(score * 100)
                    print(f"  {feat:<25} {score:.5f}  {bar}")
                break

    # backward compat name
    feature_importance = _print_feature_importance

    def save_best(self):
        if self.best_model is None:
            raise ValueError("No model trained yet.")
        return self.storage.save_model(self.best_model, name="ensemble_forex_best_manual")


# Alias for backward compatibility
ForexXGBTrainer = ForexEnsembleTrainer

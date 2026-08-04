"""
hyperparameter_tuner.py — Optuna-based hyperparameter optimizer

FIX #5: El objetivo de Optuna es maximizar precision con umbral >= 0.65
         (coherente con el nuevo MIN_PRECISION_THRESHOLD del trainer).
"""

import json
import os
import warnings
import numpy as np

from sklearn.metrics import precision_score

warnings.filterwarnings("ignore")

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    _HAS_OPTUNA = True
except ImportError:
    _HAS_OPTUNA = False

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

# FIX #5: Coherente con MIN_PRECISION_THRESHOLD
MIN_PRECISION_THRESHOLD = 0.65


class ForexHyperparameterTuner:
    """
    Optuna-driven tuner para XGBoost y LightGBM.
    Objetivo: maximizar precision en val con umbral >= 0.65.
    """

    def __init__(self, pair: str = "default", params_dir: str = PARAMS_DIR):
        self.pair       = pair.upper().replace("/", "").replace("_", "").replace("-", "")
        self.params_dir = params_dir
        os.makedirs(self.params_dir, exist_ok=True)
        self.best_params: dict = {}

    def _params_path(self) -> str:
        return os.path.join(self.params_dir, f"best_params_{self.pair}.json")

    def save_params(self, params: dict):
        with open(self._params_path(), "w") as f:
            json.dump(params, f, indent=2)
        print(f"[TUNER] Best params guardados → {self._params_path()}")

    def load_params(self) -> dict:
        path = self._params_path()
        if not os.path.exists(path):
            return {}
        with open(path) as f:
            params = json.load(f)
        print(f"[TUNER] Params cargados para {self.pair}")
        return params

    # ─────────────────────────────────────────────────────────
    # XGBOOST OBJECTIVE — maximizar precision real con threshold busqueda
    # ─────────────────────────────────────────────────────────
    def _xgb_objective(self, trial, X_train, y_train, X_val, y_val, scale):
        from sklearn.isotonic import IsotonicRegression
        from sklearn.metrics import precision_recall_curve

        params = {
            "n_estimators":       trial.suggest_int("n_estimators", 200, 1000),
            "max_depth":          trial.suggest_int("max_depth", 3, 10),
            "learning_rate":      trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "subsample":          trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree":   trial.suggest_float("colsample_bytree", 0.4, 1.0),
            "min_child_weight":   trial.suggest_int("min_child_weight", 1, 20),
            "gamma":              trial.suggest_float("gamma", 0.0, 2.0),
            "reg_alpha":          trial.suggest_float("reg_alpha", 0.0, 2.0),
            "reg_lambda":         trial.suggest_float("reg_lambda", 0.5, 5.0),
            "scale_pos_weight":   scale,
            "random_state":       42,
            "eval_metric":        "logloss",
            "early_stopping_rounds": 30,
            "verbosity":          0,
        }
        model = XGBClassifier(**params)
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        # Calibración + búsqueda de umbral con prec >= 0.65
        probs_train = model.predict_proba(X_train)[:, 1]
        ir = IsotonicRegression(out_of_bounds="clip")
        ir.fit(probs_train, y_train)
        cal_probs = ir.predict(model.predict_proba(X_val)[:, 1])

        prec_arr, _, thresh_arr = precision_recall_curve(y_val, cal_probs)
        prec_arr = prec_arr[:-1]
        mask = prec_arr >= MIN_PRECISION_THRESHOLD
        if mask.any():
            return float(prec_arr[mask].max())
        return float(prec_arr.max())

    # ─────────────────────────────────────────────────────────
    # LIGHTGBM OBJECTIVE
    # ─────────────────────────────────────────────────────────
    def _lgb_objective(self, trial, X_train, y_train, X_val, y_val, scale):
        from sklearn.isotonic import IsotonicRegression
        from sklearn.metrics import precision_recall_curve

        params = {
            "n_estimators":      trial.suggest_int("n_estimators", 200, 1000),
            "max_depth":         trial.suggest_int("max_depth", 3, 10),
            "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.4, 1.0),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
            "num_leaves":        trial.suggest_int("num_leaves", 20, 150),
            "reg_alpha":         trial.suggest_float("reg_alpha", 0.0, 2.0),
            "reg_lambda":        trial.suggest_float("reg_lambda", 0.5, 5.0),
            "scale_pos_weight":  scale,
            "random_state":      42,
            "verbose":           -1,
        }
        model = lgb.LGBMClassifier(**params)
        model.fit(X_train, y_train)

        probs_train = model.predict_proba(X_train)[:, 1]
        ir = IsotonicRegression(out_of_bounds="clip")
        ir.fit(probs_train, y_train)
        cal_probs = ir.predict(model.predict_proba(X_val)[:, 1])

        prec_arr, _, thresh_arr = precision_recall_curve(y_val, cal_probs)
        prec_arr = prec_arr[:-1]
        mask = prec_arr >= MIN_PRECISION_THRESHOLD
        if mask.any():
            return float(prec_arr[mask].max())
        return float(prec_arr.max())

    # ─────────────────────────────────────────────────────────
    # MAIN TUNE
    # ─────────────────────────────────────────────────────────
    def tune(self, X_train, y_train, X_val, y_val,
             n_trials: int = 50, timeout: int = None) -> dict:

        if not _HAS_OPTUNA:
            print("[TUNER] Optuna no instalado. Instala: pip install optuna")
            return {}

        n_pos = int(y_train.sum())
        n_neg = int((y_train == 0).sum())
        scale = n_neg / n_pos if n_pos > 0 else 1.0

        print(f"\n{'='*60}")
        print(f" OPTUNA TUNING — {self.pair}")
        print(f" Objetivo: MAXIMIZAR PRECISION ≥ {MIN_PRECISION_THRESHOLD:.0%}")
        print(f" Train: {len(X_train)} | Val: {len(X_val)} | Trials: {n_trials}")
        print(f"{'='*60}\n")

        results = {}

        if _HAS_XGB:
            print(f"[TUNER] Tuning XGBoost ({n_trials} trials)...")
            xgb_study = optuna.create_study(
                direction="maximize",
                sampler=optuna.samplers.TPESampler(seed=42),
                pruner=optuna.pruners.MedianPruner(n_startup_trials=10),
            )
            xgb_study.optimize(
                lambda t: self._xgb_objective(t, X_train, y_train, X_val, y_val, scale),
                n_trials=n_trials, timeout=timeout, show_progress_bar=False,
            )
            best_xgb           = xgb_study.best_params
            best_xgb["scale_pos_weight"] = scale
            print(f"[TUNER] XGBoost mejor precision calibrada: {xgb_study.best_value:.4f}")
            results["xgb"] = best_xgb

        if _HAS_LGB:
            print(f"[TUNER] Tuning LightGBM ({n_trials} trials)...")
            lgb_study = optuna.create_study(
                direction="maximize",
                sampler=optuna.samplers.TPESampler(seed=42),
                pruner=optuna.pruners.MedianPruner(n_startup_trials=10),
            )
            lgb_study.optimize(
                lambda t: self._lgb_objective(t, X_train, y_train, X_val, y_val, scale),
                n_trials=n_trials, timeout=timeout, show_progress_bar=False,
            )
            best_lgb           = lgb_study.best_params
            best_lgb["scale_pos_weight"] = scale
            print(f"[TUNER] LightGBM mejor precision calibrada: {lgb_study.best_value:.4f}")
            results["lgb"] = best_lgb

        self.best_params = results
        self.save_params(results)
        print(f"[TUNER] Tuning completo. Params guardados para {self.pair}.")
        return results

    @staticmethod
    def recommend_trials(n_rows: int) -> int:
        if n_rows < 500:
            return 30
        elif n_rows < 2000:
            return 50
        elif n_rows < 10000:
            return 75
        else:
            return 100

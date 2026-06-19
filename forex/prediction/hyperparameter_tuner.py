"""
hyperparameter_tuner.py — Optuna-based hyperparameter optimizer

What this does:
- Runs separate Optuna studies for XGBoost and LightGBM
- Objective = maximize PRECISION on the validation set
  (precision = of all BUY signals fired, how many were actually profitable?)
- Saves best params to JSON per pair so they persist across sessions
- Automatically loads saved params when you train again

Why Optuna over GridSearch/RandomSearch?
- TPE sampler learns which regions of the search space are promising and
  focuses trials there — far more efficient than random or exhaustive search
- Pruning (MedianPruner) cuts off bad trials early → faster overall search
- Handles 20+ hyperparameters well where grid search would take days

Usage:
    tuner = ForexHyperparameterTuner(pair="EURUSD")
    best = tuner.tune(X_train, y_train, X_val, y_val, n_trials=50)
    # best = {"xgb": {...}, "lgb": {...}}
"""

import json
import os
import warnings
import numpy as np

from sklearn.metrics import precision_score
from sklearn.calibration import CalibratedClassifierCV

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


class ForexHyperparameterTuner:
    """
    Optuna-driven tuner for XGBoost and LightGBM.

    Parameters
    ----------
    pair : str
        Forex pair name (e.g. "EURUSD"). Used to save/load params per pair.
    params_dir : str
        Directory where best params JSON files are stored.
    """

    def __init__(self, pair: str = "default", params_dir: str = PARAMS_DIR):
        self.pair       = pair.upper().replace("/", "").replace("_", "")
        self.params_dir = params_dir
        os.makedirs(self.params_dir, exist_ok=True)

        self.best_params: dict = {}

    # -------------------------------------------------------
    # PERSISTENCE — save / load per pair
    # -------------------------------------------------------
    def _params_path(self) -> str:
        return os.path.join(self.params_dir, f"best_params_{self.pair}.json")

    def save_params(self, params: dict):
        with open(self._params_path(), "w") as f:
            json.dump(params, f, indent=2)
        print(f"[TUNER] Best params saved → {self._params_path()}")

    def load_params(self) -> dict:
        path = self._params_path()
        if not os.path.exists(path):
            return {}
        with open(path) as f:
            params = json.load(f)
        print(f"[TUNER] Loaded saved params for {self.pair} from {path}")
        return params

    # -------------------------------------------------------
    # XGBOOST OBJECTIVE
    # -------------------------------------------------------
    def _xgb_objective(self, trial, X_train, y_train, X_val, y_val, scale):
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
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        preds = model.predict(X_val)
        return precision_score(y_val, preds, zero_division=0)

    # -------------------------------------------------------
    # LIGHTGBM OBJECTIVE
    # -------------------------------------------------------
    def _lgb_objective(self, trial, X_train, y_train, X_val, y_val, scale):
        params = {
            "n_estimators":       trial.suggest_int("n_estimators", 200, 1000),
            "max_depth":          trial.suggest_int("max_depth", 3, 10),
            "learning_rate":      trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "subsample":          trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree":   trial.suggest_float("colsample_bytree", 0.4, 1.0),
            "min_child_samples":  trial.suggest_int("min_child_samples", 5, 50),
            "num_leaves":         trial.suggest_int("num_leaves", 20, 150),
            "reg_alpha":          trial.suggest_float("reg_alpha", 0.0, 2.0),
            "reg_lambda":         trial.suggest_float("reg_lambda", 0.5, 5.0),
            "scale_pos_weight":   scale,
            "random_state":       42,
            "verbose":            -1,
        }

        model = lgb.LGBMClassifier(**params)
        model.fit(X_train, y_train)

        preds = model.predict(X_val)
        return precision_score(y_val, preds, zero_division=0)

    # -------------------------------------------------------
    # MAIN TUNE METHOD
    # -------------------------------------------------------
    def tune(
        self,
        X_train,
        y_train,
        X_val,
        y_val,
        n_trials: int = 50,
        timeout: int = None,
    ) -> dict:
        """
        Run Optuna studies for XGBoost and LightGBM.

        Parameters
        ----------
        X_train, y_train : training data
        X_val, y_val     : validation data (time-based split, no leakage)
        n_trials         : number of Optuna trials per model (default 50)
        timeout          : optional max seconds per study

        Returns
        -------
        dict with keys "xgb" and/or "lgb" containing best hyperparameters
        """

        if not _HAS_OPTUNA:
            print("[TUNER] Optuna not installed. Run: pip install optuna")
            print("[TUNER] Falling back to default parameters.")
            return {}

        n_pos = int(y_train.sum())
        n_neg = int((y_train == 0).sum())
        scale = n_neg / n_pos if n_pos > 0 else 1.0

        print(f"\n{'='*60}")
        print(f" OPTUNA HYPERPARAMETER TUNING — {self.pair}")
        print(f"{'='*60}")
        print(f" Train rows : {len(X_train)}  |  Val rows : {len(X_val)}")
        print(f" Class scale: {scale:.2f}  |  Trials: {n_trials} per model")
        print(f" Objective  : MAXIMIZE PRECISION on validation set")
        print(f"{'='*60}\n")

        results = {}

        # ---- XGBoost study ----
        if _HAS_XGB:
            print(f"[TUNER] Tuning XGBoost ({n_trials} trials)...")
            xgb_study = optuna.create_study(
                direction="maximize",
                sampler=optuna.samplers.TPESampler(seed=42),
                pruner=optuna.pruners.MedianPruner(n_startup_trials=10),
            )
            xgb_study.optimize(
                lambda trial: self._xgb_objective(
                    trial, X_train, y_train, X_val, y_val, scale
                ),
                n_trials=n_trials,
                timeout=timeout,
                show_progress_bar=True,
            )

            best_xgb = xgb_study.best_params
            best_xgb["scale_pos_weight"] = scale
            best_xgb_precision = xgb_study.best_value

            print(f"\n[TUNER] XGBoost best precision : {best_xgb_precision:.4f}")
            self._print_params("XGBoost", best_xgb)
            results["xgb"] = best_xgb

        # ---- LightGBM study ----
        if _HAS_LGB:
            print(f"\n[TUNER] Tuning LightGBM ({n_trials} trials)...")
            lgb_study = optuna.create_study(
                direction="maximize",
                sampler=optuna.samplers.TPESampler(seed=42),
                pruner=optuna.pruners.MedianPruner(n_startup_trials=10),
            )
            lgb_study.optimize(
                lambda trial: self._lgb_objective(
                    trial, X_train, y_train, X_val, y_val, scale
                ),
                n_trials=n_trials,
                timeout=timeout,
                show_progress_bar=True,
            )

            best_lgb = lgb_study.best_params
            best_lgb["scale_pos_weight"] = scale
            best_lgb_precision = lgb_study.best_value

            print(f"\n[TUNER] LightGBM best precision : {best_lgb_precision:.4f}")
            self._print_params("LightGBM", best_lgb)
            results["lgb"] = best_lgb

        self.best_params = results
        self.save_params(results)

        print(f"\n[TUNER] Tuning complete. Best params saved for {self.pair}.")
        return results

    # -------------------------------------------------------
    # QUICK TRIAL COUNT RECOMMENDATION
    # Based on available data size — more data = more reliable trials.
    # -------------------------------------------------------
    @staticmethod
    def recommend_trials(n_rows: int) -> int:
        """
        Suggest how many Optuna trials to run based on dataset size.
        Small datasets overfit quickly, so fewer trials are needed.
        """
        if n_rows < 500:
            return 30
        elif n_rows < 2000:
            return 50
        elif n_rows < 10000:
            return 75
        else:
            return 100

    # -------------------------------------------------------
    # BUILD XGB MODEL FROM TUNED PARAMS
    # -------------------------------------------------------
    def build_xgb(self, params: dict = None):
        if not _HAS_XGB:
            raise ImportError("XGBoost not installed.")
        p = params or self.best_params.get("xgb", {})
        if not p:
            raise ValueError("No XGBoost params found. Run tune() first.")
        p = {k: v for k, v in p.items()
             if k not in ("early_stopping_rounds",)}
        return XGBClassifier(
            **p,
            eval_metric="logloss",
            early_stopping_rounds=40,
            verbosity=0,
        )

    # -------------------------------------------------------
    # BUILD LGB MODEL FROM TUNED PARAMS
    # -------------------------------------------------------
    def build_lgb(self, params: dict = None):
        if not _HAS_LGB:
            raise ImportError("LightGBM not installed.")
        p = params or self.best_params.get("lgb", {})
        if not p:
            raise ValueError("No LightGBM params found. Run tune() first.")
        return lgb.LGBMClassifier(**p, verbose=-1)

    # -------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------
    def _print_params(self, name: str, params: dict):
        print(f"\n  Best {name} params:")
        for k, v in params.items():
            if isinstance(v, float):
                print(f"    {k:<25} {v:.6f}")
            else:
                print(f"    {k:<25} {v}")

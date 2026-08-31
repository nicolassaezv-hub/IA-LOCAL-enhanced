"""
hyperparameter_tuner.py — Optuna-based hyperparameter optimizer

FIX #5: El objetivo de Optuna es maximizar precision con umbral >= 0.65
         (coherente con el nuevo MIN_PRECISION_THRESHOLD del trainer).
"""

import hashlib
import json
import math
import os
import warnings
import numpy as np

from sklearn.metrics import accuracy_score, precision_score
from runtime_paths import forex_model_root
from .xgb_trainer import (
    MIN_PRECISION_THRESHOLD as PRODUCTION_MIN_PRECISION,
    WFV_MEDIAN_PRECISION_THRESHOLD,
    ForexEnsembleTrainer,
    WalkForwardValidator,
)

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

PARAMS_DIR = forex_model_root() / "params"

# FIX #5: Coherente con MIN_PRECISION_THRESHOLD
MIN_PRECISION_THRESHOLD = 0.65
INNER_TUNING_WINDOW = 500
INNER_TUNING_STEP = 200
INNER_TUNING_PURGE = 20
MIN_INNER_FOLDS = 2
MIN_INNER_SIGNAL_RATE = 0.10
INSUFFICIENT_EVIDENCE_SCORE = -1.0
WFV_SELECTION_SEED = 42


def canonical_params_sha256(params: dict) -> str:
    """Return an order-independent identity for an explicit parameter set."""
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def summarize_inner_evidence(folds: list[dict]) -> dict:
    """Aggregate nested tuning evidence without treating tiny samples as signal."""
    normalized = []
    counts_valid = True
    for number, source in enumerate(folds or [], start=1):
        try:
            validation_size = int(source["validation_size"])
            tp = int(source["tp"])
            fp = int(source["fp"])
            signals = int(source["signals"])
            accuracy = float(source["accuracy"])
        except (KeyError, TypeError, ValueError):
            counts_valid = False
            continue
        if (
            validation_size <= 0
            or min(tp, fp, signals) < 0
            or signals != tp + fp
            or signals > validation_size
            or not math.isfinite(accuracy)
            or not 0.0 <= accuracy <= 1.0
        ):
            counts_valid = False
            continue
        precision = tp / signals if signals else 0.0
        reported_precision = source.get("precision")
        try:
            if not math.isclose(
                float(reported_precision), precision, rel_tol=1e-12, abs_tol=1e-12
            ):
                counts_valid = False
        except (TypeError, ValueError):
            counts_valid = False
        min_signals = int(math.ceil(validation_size * MIN_INNER_SIGNAL_RATE))
        normalized.append({
            **source,
            "fold": int(source.get("fold", number)),
            "validation_size": validation_size,
            "min_signals": min_signals,
            "tp": tp,
            "fp": fp,
            "signals": signals,
            "precision": precision,
            "accuracy": accuracy,
        })

    precisions = [fold["precision"] for fold in normalized]
    total_tp = sum(fold["tp"] for fold in normalized)
    total_fp = sum(fold["fp"] for fold in normalized)
    total_signals = total_tp + total_fp
    avg_precision = float(np.mean(precisions)) if precisions else 0.0
    median_precision = float(np.median(precisions)) if precisions else 0.0
    pooled_precision = total_tp / total_signals if total_signals else 0.0
    avg_accuracy = (
        float(np.mean([fold["accuracy"] for fold in normalized]))
        if normalized
        else 0.0
    )
    evidence_sufficient = bool(
        counts_valid
        and len(normalized) >= MIN_INNER_FOLDS
        and all(fold["signals"] >= fold["min_signals"] for fold in normalized)
    )
    metric_gate = bool(
        avg_precision >= PRODUCTION_MIN_PRECISION
        or median_precision >= WFV_MEDIAN_PRECISION_THRESHOLD
    )
    inner_wfv_passed = bool(
        evidence_sufficient
        and pooled_precision >= PRODUCTION_MIN_PRECISION
        and metric_gate
    )
    objective_score = (
        min(avg_precision, pooled_precision)
        if evidence_sufficient
        else INSUFFICIENT_EVIDENCE_SCORE
    )
    return {
        "inner_folds": normalized,
        "inner_fold_count": len(normalized),
        "inner_avg_precision": avg_precision,
        "inner_median_precision": median_precision,
        "inner_pooled_precision": pooled_precision,
        "inner_avg_accuracy": avg_accuracy,
        "inner_total_tp": total_tp,
        "inner_total_fp": total_fp,
        "inner_total_signals": total_signals,
        "inner_evidence_sufficient": evidence_sufficient,
        "inner_wfv_passed": inner_wfv_passed,
        "objective_score": objective_score,
    }


class ForexHyperparameterTuner:
    """
    Optuna-driven tuner para XGBoost y LightGBM.
    Objetivo: maximizar precision en val con umbral >= 0.65.
    """

    def __init__(self, pair: str = "default", params_dir=None):
        self.pair       = pair.upper().replace("/", "").replace("_", "").replace("-", "")
        self.params_dir = os.fspath(
            forex_model_root() / "params" if params_dir is None else params_dir
        )
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

    def _nested_geometry(self, n_rows: int) -> dict:
        """Reserve outer production folds and derive an isolated inner pool."""
        outer_validator = WalkForwardValidator(purge=20, n_folds=5)
        outer_positions = outer_validator.split_positions(int(n_rows))
        if not outer_positions:
            raise ValueError("NO_OUTER_WFV_FOLDS")

        first_outer = outer_positions[0]
        tuning_pool = {
            "start": first_outer["train_start"],
            "end": first_outer["train_end"],
            "row_count": first_outer["train_end"] - first_outer["train_start"],
        }
        inner_validator = WalkForwardValidator(
            window=INNER_TUNING_WINDOW,
            step=INNER_TUNING_STEP,
            purge=INNER_TUNING_PURGE,
            n_folds=MIN_INNER_FOLDS,
        )
        inner_positions = inner_validator.split_positions(tuning_pool["row_count"])
        if len(inner_positions) < MIN_INNER_FOLDS:
            raise ValueError("INSUFFICIENT_INNER_WFV_FOLDS")

        return {
            "tuning_pool": tuning_pool,
            "outer_positions": outer_positions,
            "outer_validation_reserved": [
                {
                    "fold": number,
                    "start": position["validation_start"],
                    "end": position["validation_end"],
                }
                for number, position in enumerate(outer_positions, start=1)
            ],
            "inner_positions": inner_positions,
            "inner_geometry": {
                "window": INNER_TUNING_WINDOW,
                "step": INNER_TUNING_STEP,
                "purge": INNER_TUNING_PURGE,
                "n_folds": MIN_INNER_FOLDS,
            },
        }

    @staticmethod
    def _suggest_wfv_params(trial) -> dict:
        """Suggest only XGB/LGB model parameters; contracts are not tunable."""
        params = {}
        if _HAS_XGB:
            params["xgb"] = {
                "n_estimators": trial.suggest_int("xgb_n_estimators", 200, 1000),
                "max_depth": trial.suggest_int("xgb_max_depth", 3, 10),
                "learning_rate": trial.suggest_float(
                    "xgb_learning_rate", 0.01, 0.15, log=True
                ),
                "subsample": trial.suggest_float("xgb_subsample", 0.5, 1.0),
                "colsample_bytree": trial.suggest_float(
                    "xgb_colsample_bytree", 0.4, 1.0
                ),
                "min_child_weight": trial.suggest_int(
                    "xgb_min_child_weight", 1, 20
                ),
                "gamma": trial.suggest_float("xgb_gamma", 0.0, 2.0),
                "reg_alpha": trial.suggest_float("xgb_reg_alpha", 0.0, 2.0),
                "reg_lambda": trial.suggest_float("xgb_reg_lambda", 0.5, 5.0),
            }
        if _HAS_LGB:
            params["lgb"] = {
                "n_estimators": trial.suggest_int("lgb_n_estimators", 200, 1000),
                "max_depth": trial.suggest_int("lgb_max_depth", 3, 10),
                "learning_rate": trial.suggest_float(
                    "lgb_learning_rate", 0.01, 0.15, log=True
                ),
                "subsample": trial.suggest_float("lgb_subsample", 0.5, 1.0),
                "colsample_bytree": trial.suggest_float(
                    "lgb_colsample_bytree", 0.4, 1.0
                ),
                "min_child_samples": trial.suggest_int(
                    "lgb_min_child_samples", 5, 50
                ),
                "num_leaves": trial.suggest_int("lgb_num_leaves", 20, 150),
                "reg_alpha": trial.suggest_float("lgb_reg_alpha", 0.0, 2.0),
                "reg_lambda": trial.suggest_float("lgb_reg_lambda", 0.5, 5.0),
            }
        return params

    def _evaluate_inner_params(
        self,
        X_pool,
        y_pool,
        inner_positions: list[dict[str, int]],
        params: dict,
    ) -> dict:
        """Evaluate one explicit ensemble configuration on temporal inner folds."""
        folds = []
        for number, position in enumerate(inner_positions, start=1):
            X_train = X_pool.iloc[
                position["train_start"] : position["train_end"]
            ]
            y_train = y_pool.iloc[
                position["train_start"] : position["train_end"]
            ]
            X_validation = X_pool.iloc[
                position["validation_start"] : position["validation_end"]
            ]
            y_validation = y_pool.iloc[
                position["validation_start"] : position["validation_end"]
            ]
            trainer = ForexEnsembleTrainer(
                pair=self.pair,
                tuned_params_override=params,
            )
            trainer.train(
                X_train,
                y_train,
                X_validation,
                y_validation,
                save=False,
            )
            predictions = (
                trainer.model.predict(X_validation)
                if trainer.model is not None
                else np.zeros(len(X_validation), dtype=int)
            )
            expected = np.asarray(y_validation)
            predicted = np.asarray(predictions)
            tp = int(np.sum((predicted == 1) & (expected == 1)))
            fp = int(np.sum((predicted == 1) & (expected == 0)))
            signals = tp + fp
            folds.append({
                "fold": number,
                **position,
                "validation_size": len(y_validation),
                "tp": tp,
                "fp": fp,
                "signals": signals,
                "precision": precision_score(
                    y_validation, predictions, zero_division=0
                ),
                "accuracy": accuracy_score(y_validation, predictions),
            })
        return summarize_inner_evidence(folds)

    def tune_wfv_aligned(
        self,
        X,
        y,
        *,
        snapshot_sha256: str,
        n_trials: int = 50,
        timeout: int | None = None,
        persist: bool = False,
        use_cache: bool = False,
    ) -> dict:
        """Select params on inner folds while reserving outer WFV for certification."""
        if use_cache:
            raise ValueError("WFV_ALIGNED_CACHE_IS_NOT_SNAPSHOT_BOUND")
        if not _HAS_OPTUNA:
            raise RuntimeError("OPTUNA_NOT_AVAILABLE")
        if not isinstance(snapshot_sha256, str) or not snapshot_sha256.strip():
            raise ValueError("SNAPSHOT_SHA256_REQUIRED")
        if len(X) != len(y):
            raise ValueError("TUNING_FEATURE_TARGET_LENGTH_MISMATCH")
        if int(n_trials) <= 0:
            raise ValueError("N_TRIALS_MUST_BE_POSITIVE")

        geometry = self._nested_geometry(len(X))
        pool = geometry["tuning_pool"]
        X_pool = X.iloc[pool["start"] : pool["end"]]
        y_pool = y.iloc[pool["start"] : pool["end"]]
        evaluations = []

        def objective(trial):
            params = self._suggest_wfv_params(trial)
            summary = self._evaluate_inner_params(
                X_pool,
                y_pool,
                geometry["inner_positions"],
                params,
            )
            evaluation = {
                "trial": int(getattr(trial, "number", len(evaluations))),
                "params": params,
                **summary,
            }
            evaluations.append(evaluation)
            trial.set_user_attr("params_sha256", canonical_params_sha256(params))
            trial.set_user_attr(
                "inner_evidence_sufficient",
                summary["inner_evidence_sufficient"],
            )
            trial.set_user_attr("inner_wfv_passed", summary["inner_wfv_passed"])
            return summary["objective_score"]

        study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=WFV_SELECTION_SEED),
        )
        study.optimize(
            objective,
            n_trials=int(n_trials),
            timeout=timeout,
            show_progress_bar=False,
        )
        if not evaluations:
            raise RuntimeError("NO_TUNING_TRIALS_COMPLETED")

        sufficient = [
            item for item in evaluations if item["inner_evidence_sufficient"]
        ]
        if sufficient:
            selected = max(
                sufficient,
                key=lambda item: (item["objective_score"], -item["trial"]),
            )
            selected_params = selected["params"]
            status = (
                "SELECTED_FOR_OUTER_WFV"
                if selected["inner_wfv_passed"]
                else "INNER_WFV_NOT_PASSED"
            )
            diagnostic_params = None
        else:
            selected = max(
                evaluations,
                key=lambda item: (
                    item["inner_pooled_precision"],
                    item["inner_avg_precision"],
                    item["inner_total_signals"],
                    -item["trial"],
                ),
            )
            selected_params = {}
            diagnostic_params = selected["params"]
            status = "NO_INNER_EVIDENCE_SUFFICIENT_CANDIDATE"

        params_identity = canonical_params_sha256(selected_params)
        persisted = False
        if persist and selected["inner_wfv_passed"]:
            self.save_params(selected_params)
            persisted = True
        self.best_params = selected_params

        inner_metrics = {
            key: selected[key]
            for key in (
                "inner_folds",
                "inner_fold_count",
                "inner_avg_precision",
                "inner_median_precision",
                "inner_pooled_precision",
                "inner_avg_accuracy",
                "inner_total_tp",
                "inner_total_fp",
                "inner_total_signals",
                "inner_evidence_sufficient",
                "inner_wfv_passed",
                "objective_score",
            )
        }
        provenance = {
            "mode": "nested_wfv_tuning",
            "pair": self.pair,
            "snapshot_sha256": snapshot_sha256,
            "params_sha256": params_identity,
            "selection_seed": WFV_SELECTION_SEED,
            "trial_count": len(evaluations),
            "tuning_pool": pool,
            "inner_geometry": geometry["inner_geometry"],
            "inner_metrics": inner_metrics,
            "persisted": persisted,
        }
        return {
            "status": status,
            "params": selected_params,
            "diagnostic_params": diagnostic_params,
            "params_sha256": params_identity,
            **inner_metrics,
            "tuning_pool": pool,
            "outer_validation_reserved": geometry["outer_validation_reserved"],
            "n_trials": len(evaluations),
            "seed": WFV_SELECTION_SEED,
            "persisted": persisted,
            "use_cache": False,
            "hyperparameter_provenance": provenance,
        }

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
             n_trials: int = 50, timeout: int = None,
             horizon: str = "H1", csv_path: str = "") -> dict:

        # VI.1.A — Smart Hyperparameter Cache
        try:
            from .hyperparameter_cache import HyperparameterCache
            cached = HyperparameterCache().get(pair=self.pair, horizon=horizon, csv_path=csv_path)
            if cached:
                print(f"[TUNER] Cache HIT — reutilizando hiperparámetros para {self.pair} ({horizon})")
                self.best_params = cached
                return cached
        except Exception:
            pass

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
        # VI.1.A — persistir en caché SQLite
        try:
            from .hyperparameter_cache import HyperparameterCache
            HyperparameterCache().save(pair=self.pair, horizon=horizon,
                                        params=results, csv_path=csv_path,
                                        n_trials=n_trials)
        except Exception:
            pass
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

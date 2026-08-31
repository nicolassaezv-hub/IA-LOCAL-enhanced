"""
xgb_trainer.py — Ensemble XGB+LGB+RF con Walk-Forward Validation deslizante,
                 calibración isotónica y umbral de precision ≥ 0.65.

CAMBIOS CLAVE vs versión anterior:
- WFV DESLIZANTE (ventana fija) en vez de acumulativa.
  El modelo se entrena en los últimos `window` registros y valida en los
  siguientes `step`. Esto simula el re-entrenamiento periódico real y
  evita que períodos muy antiguos contaminen el modelo actual.
- PURGE GAP entre train y val: elimina las últimas `purge` filas del
  training set y las primeras del val para evitar leakage temporal
  (las filas adyacentes al split comparten información del target).
- MIN_PRECISION_THRESHOLD = 0.65 (sin cambios).
- WFV conserva el gate avg/mediana y exige además evidencia direccional
  suficiente y precision agrupada ≥ 65%.
"""

import json
import math
import os
import warnings
from numbers import Integral
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    precision_score,
    recall_score,
    f1_score,
    precision_recall_curve,
)
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from runtime_paths import forex_model_root
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

try:
    from imblearn.over_sampling import SMOTE
    _HAS_SMOTE = True
except ImportError:
    _HAS_SMOTE = False

PARAMS_DIR = forex_model_root() / "params"
MIN_PRECISION_THRESHOLD = 0.65
WFV_MEDIAN_PRECISION_THRESHOLD = 0.70
MIN_WFV_FOLDS = 2
MIN_WFV_SIGNALS_PER_FOLD = 30
MIN_CALIBRATION_ROWS = 60
MIN_CALIBRATION_SIGNAL_RATE = 0.10


def _validated_wfv_evidence(result: dict) -> dict | None:
    """Recompute and validate the complete persisted WFV evidence."""
    folds = result.get("folds")
    if not isinstance(folds, list) or not folds:
        return None

    precisions = []
    total_tp = 0
    total_fp = 0
    for fold in folds:
        if not isinstance(fold, dict):
            return None
        counts = {}
        for key in ("tp", "fp", "signals", "validation_size"):
            value = fold.get(key)
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
                return None
            counts[key] = int(value)
            if counts[key] < 0:
                return None

        tp = counts["tp"]
        fp = counts["fp"]
        signals = counts["signals"]
        validation_size = counts["validation_size"]
        if signals != tp + fp or signals > validation_size:
            return None

        try:
            precision = float(fold["precision"])
            accuracy = float(fold["accuracy"])
        except (KeyError, TypeError, ValueError):
            return None
        if (
            not math.isfinite(precision)
            or not 0.0 <= precision <= 1.0
            or not math.isfinite(accuracy)
            or not 0.0 <= accuracy <= 1.0
        ):
            return None
        expected_precision = tp / signals if signals > 0 else 0.0
        if not math.isclose(precision, expected_precision, abs_tol=1e-12):
            return None

        precisions.append(precision)
        total_tp += tp
        total_fp += fp

    total_signals = total_tp + total_fp
    pooled_precision = total_tp / total_signals if total_signals > 0 else 0.0
    avg_precision = float(np.mean(precisions))
    median_precision = float(np.median(precisions))
    evidence_sufficient = bool(
        len(folds) >= MIN_WFV_FOLDS
        and all(
            int(fold["signals"]) >= MIN_WFV_SIGNALS_PER_FOLD
            for fold in folds
        )
    )
    existing_metric_gate = bool(
        avg_precision >= MIN_PRECISION_THRESHOLD
        or median_precision >= WFV_MEDIAN_PRECISION_THRESHOLD
    )
    computed_pass = bool(
        existing_metric_gate
        and evidence_sufficient
        and pooled_precision >= MIN_PRECISION_THRESHOLD
    )

    try:
        reported_avg = float(result["avg_precision"])
        reported_median = float(result["median_precision"])
        reported_pooled = float(result["pooled_precision"])
    except (KeyError, TypeError, ValueError):
        return None
    reported_counts = {}
    for key in ("total_tp", "total_fp", "total_signals"):
        value = result.get(key)
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
            return None
        reported_counts[key] = int(value)
    if (
        not math.isclose(reported_avg, round(avg_precision, 4), abs_tol=1e-12)
        or not math.isclose(
            reported_median, round(median_precision, 4), abs_tol=1e-12
        )
        or not math.isclose(reported_pooled, pooled_precision, abs_tol=1e-12)
        or reported_counts["total_tp"] != total_tp
        or reported_counts["total_fp"] != total_fp
        or reported_counts["total_signals"] != total_signals
        or result.get("evidence_sufficient") is not evidence_sufficient
    ):
        return None

    return {
        "existing_metric_gate": existing_metric_gate,
        "evidence_sufficient": evidence_sufficient,
        "pooled_precision": pooled_precision,
        "wfv_passed": computed_pass,
    }


def wfv_quality_passed(result: dict) -> bool:
    """Evaluate the canonical out-of-sample WFV production contract."""
    if (
        not isinstance(result, dict)
        or result.get("error")
        or result.get("wfv_passed") is not True
    ):
        return False
    evidence = _validated_wfv_evidence(result)
    return bool(evidence and evidence["wfv_passed"])


def _load_tuned_params(pair: str) -> dict:
    if not pair:
        return {}
    clean = pair.upper().replace("/", "").replace("_", "").replace("-", "")
    path  = os.path.join(PARAMS_DIR, f"best_params_{clean}.json")
    if os.path.exists(path):
        with open(path) as f:
            params = json.load(f)
        print(f"[ENSEMBLE] Params tuned cargados para {clean}")
        return params
    return {}


# ─────────────────────────────────────────────────────────────
# BACKWARD COMPATIBILITY SHIM
# Allows loading of models pickled before Roadmap V (pre-SoftVotingEnsemble).
# ─────────────────────────────────────────────────────────────
class _PreFitEnsemble:
    """Legacy ensemble class — kept for unpickling old saved models."""
    def __init__(self, estimators, weights=None):
        self.estimators = estimators
        self.classes_   = np.array([0, 1])

    def predict_proba(self, X) -> np.ndarray:
        proba = np.mean([est.predict_proba(X) for _, est in self.estimators], axis=0)
        return proba

    def predict(self, X) -> np.ndarray:
        return np.argmax(self.predict_proba(X), axis=1)


# ─────────────────────────────────────────────────────────────
# SOFT VOTING ENSEMBLE
# ─────────────────────────────────────────────────────────────
class SoftVotingEnsemble:
    def __init__(self, models: list):
        self.models   = models
        self.classes_ = np.array([0, 1])

    def predict_proba(self, X) -> np.ndarray:
        probs = [m.predict_proba(X) for _, m in self.models]
        return np.mean(probs, axis=0)

    def predict(self, X, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= threshold).astype(int)


# ─────────────────────────────────────────────────────────────
# CALIBRATED ENSEMBLE
# ─────────────────────────────────────────────────────────────
class CalibratedEnsemble:
    def __init__(self, base: SoftVotingEnsemble, method: str = "isotonic"):
        if method not in {"isotonic", "sigmoid"}:
            raise ValueError(f"CALIBRATION_METHOD_UNSUPPORTED: {method}")
        self.base                    = base
        self.method                  = method
        self.cal_1                   = (
            IsotonicRegression(out_of_bounds="clip")
            if method == "isotonic"
            else LogisticRegression(random_state=42)
        )
        self.threshold               = 0.5
        self.classes_                = np.array([0, 1])
        self.precision_at_threshold  = 0.0
        self.recall_at_threshold     = 0.0
        self.signals_at_threshold    = 0
        self.sufficient              = False
        self.calibration_size = 0
        self.minimum_calibration_signals = 0
        self.calibration_evidence_sufficient = False

    def _set_reported_metrics(self, y_true, probabilities) -> None:
        """Report calibration metrics at the threshold that will be applied."""
        predictions = (probabilities >= self.threshold).astype(int)
        self.precision_at_threshold = float(
            precision_score(y_true, predictions, zero_division=0)
        )
        self.recall_at_threshold = float(
            recall_score(y_true, predictions, zero_division=0)
        )
        self.signals_at_threshold = int(predictions.sum())

    def _set_evidence_diagnostics(self, calibration_size: int) -> None:
        self.calibration_size = int(calibration_size)
        self.minimum_calibration_signals = int(
            math.ceil(self.calibration_size * MIN_CALIBRATION_SIGNAL_RATE)
        )
        self.calibration_evidence_sufficient = bool(
            self.calibration_size >= MIN_CALIBRATION_ROWS
            and self.signals_at_threshold >= self.minimum_calibration_signals
        )

    def fit(self, X_cal, y_cal):
        y_arr = y_cal.values if hasattr(y_cal, "values") else np.array(y_cal)
        raw   = self.base.predict_proba(X_cal)
        if self.method == "isotonic":
            self.cal_1.fit(raw[:, 1], y_arr)
        else:
            self.cal_1.fit(raw[:, 1].reshape(-1, 1), y_arr)

        cal_probs = self.predict_proba(X_cal)[:, 1]
        prec_arr, rec_arr, thresh_arr = precision_recall_curve(y_arr, cal_probs)
        prec_arr  = prec_arr[:-1]
        thresh_arr = thresh_arr

        # Estrategia: entre los umbrales con prec>=65% Y recall>=5%,
        # elegir el que maximiza precision (más conservador = más confiable).
        # Si no hay ninguno, tomar el de mayor precision con recall>5%.
        # Recall mide positivos reales recuperados; no equivale a cobertura
        # ni a porcentaje de señales emitidas.
        MIN_RECALL = 0.05
        mask_prec  = prec_arr >= MIN_PRECISION_THRESHOLD
        mask_rec   = rec_arr[:-1] >= MIN_RECALL
        mask       = mask_prec & mask_rec

        if mask.any():
            best_idx = np.argmax(prec_arr[mask])   # máxima precisión
            raw_thresh = float(thresh_arr[mask][best_idx])
            # Clamp: threshold > 0.90 significa pocos datos en cal set → 
            # el calibrador no tiene suficiente resolución y bloquearía todas las señales.
            # En ese caso, usar 0.90 como techo conservador pero funcional.
            MAX_THRESHOLD = 0.90
            if raw_thresh > MAX_THRESHOLD:
                print(f"[CALIBRATOR] ⚠ Umbral óptimo {raw_thresh:.3f} > {MAX_THRESHOLD} (cal set pequeño) → clamped a {MAX_THRESHOLD}")
                raw_thresh = MAX_THRESHOLD
            self.threshold = raw_thresh
            self._set_reported_metrics(y_arr, cal_probs)
            self._set_evidence_diagnostics(len(y_arr))
            self.sufficient = bool(
                self.precision_at_threshold >= MIN_PRECISION_THRESHOLD
                and self.recall_at_threshold >= MIN_RECALL
            )
            calibration_status = (
                "APROBADA" if self.sufficient else "NO APROBADA"
            )
            calibration_marker = "✓" if self.sufficient else "⚠"
            print(
                f"[CALIBRATOR] {calibration_marker} Umbral {self.threshold:.3f} → "
                f"precision={self.precision_at_threshold:.2%} "
                f"recall={self.recall_at_threshold:.2%} "
                f"señales={self.signals_at_threshold}/{len(y_arr)} "
                f"← CALIBRACIÓN {calibration_status}"
            )
        else:
            # Fallback: máxima precisión con algo de recall
            mask_rec_only = mask_rec if mask_rec.any() else np.ones(len(prec_arr), dtype=bool)
            best_idx = np.argmax(prec_arr[mask_rec_only])
            self.threshold = float(thresh_arr[mask_rec_only][best_idx])
            self._set_reported_metrics(y_arr, cal_probs)
            self._set_evidence_diagnostics(len(y_arr))
            self.sufficient = False
            print(
                f"[CALIBRATOR] ⚠ Mejor resultado al umbral {self.threshold:.3f}: "
                f"precision={self.precision_at_threshold:.2%} "
                f"recall={self.recall_at_threshold:.2%} "
                f"señales={self.signals_at_threshold}/{len(y_arr)} "
                f"— bajo mínimo {MIN_PRECISION_THRESHOLD:.0%}"
            )
        return self

    def predict_proba(self, X) -> np.ndarray:
        raw = self.base.predict_proba(X)
        if self.method == "isotonic":
            calibrated = self.cal_1.predict(raw[:, 1])
        else:
            calibrated = self.cal_1.predict_proba(
                raw[:, 1].reshape(-1, 1)
            )[:, 1]
        p1 = np.clip(calibrated, 0, 1)
        return np.column_stack([1.0 - p1, p1])

    def predict(self, X) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= self.threshold).astype(int)


# ─────────────────────────────────────────────────────────────
# WALK-FORWARD DESLIZANTE (NUEVO)
# ─────────────────────────────────────────────────────────────
class WalkForwardValidator:
    """
    Walk-Forward con ventana deslizante:
      - Entrena en los últimos `window` registros
      - Valida en los siguientes `step` registros
      - Purge de `purge` filas en la frontera train/val para evitar leakage

    Esto imita el re-entrenamiento periódico real:
    no usa datos de 3 años atrás para predecir hoy.
    """

    def __init__(self, window: int = None, step: int = None,
                 purge: int = 12, n_folds: int = 4,
                 min_train_ratio: float = 0.60):
        self.window          = window    # None = auto-calculado
        self.step            = step      # None = auto-calculado
        self.purge           = purge
        self.n_folds         = n_folds
        self.min_train_ratio = min_train_ratio

    def _auto_params(self, n: int):
        # Ventana = 40% del dataset, paso = 10%
        window = max(int(n * 0.40), 1000)
        step   = max(int(n * 0.10), 300)
        return window, step

    def split_positions(self, n: int) -> list[dict[str, int]]:
        """Return the half-open positional bounds used by ``split``."""
        window  = self.window or self._auto_params(n)[0]
        step    = self.step   or self._auto_params(n)[1]
        purge   = self.purge
        positions = []
        pos     = 0

        while pos + window + purge + step <= n:
            train_end = pos + window - purge
            validation_start = pos + window + purge
            validation_end = validation_start + step
            if train_end - pos >= 200 and validation_end - validation_start >= 50:
                positions.append({
                    "train_start": pos,
                    "train_end": train_end,
                    "validation_start": validation_start,
                    "validation_end": validation_end,
                })
            pos += step

        # Si hay más de n_folds, usar solo los últimos (más representativos)
        if len(positions) > self.n_folds:
            positions = positions[-self.n_folds:]

        return positions

    def split(self, X, y):
        folds = []
        for position in self.split_positions(len(X)):
            X_tr = X.iloc[position["train_start"] : position["train_end"]]
            y_tr = y.iloc[position["train_start"] : position["train_end"]]
            X_val = X.iloc[
                position["validation_start"] : position["validation_end"]
            ]
            y_val = y.iloc[
                position["validation_start"] : position["validation_end"]
            ]
            folds.append((X_tr, y_tr, X_val, y_val))

        return folds

    def evaluate(
        self,
        trainer_cls,
        X,
        y,
        pair: str = None,
        tuned_params_override: dict | None = None,
    ):
        folds   = self.split(X, y)
        results = []

        print(f"\n[WFV] Walk-Forward Deslizante — {len(folds)} folds (purge={self.purge})")
        print(f"{'─'*55}")

        for k, (X_tr, y_tr, X_val, y_val) in enumerate(folds):
            n_pos = int(y_tr.sum())
            n_neg = int((y_tr == 0).sum())
            if n_pos < 20 or n_neg < 20:
                print(f"[WFV] Fold {k+1}: insuficiente — skip")
                continue

            trainer = (
                trainer_cls(pair=pair)
                if tuned_params_override is None
                else trainer_cls(
                    pair=pair,
                    tuned_params_override=tuned_params_override,
                )
            )
            trainer.train(X_tr, y_tr, X_val, y_val, save=False)  # NO guardar folds intermedios

            if trainer.model is None:
                continue

            preds = trainer.model.predict(X_val)
            prec  = precision_score(y_val, preds, zero_division=0)
            acc   = accuracy_score(y_val, preds)
            y_val_array = np.asarray(y_val)
            pred_array = np.asarray(preds)
            tp = int(np.sum((pred_array == 1) & (y_val_array == 1)))
            fp = int(np.sum((pred_array == 1) & (y_val_array == 0)))
            n_sig = tp + fp

            print(f"[WFV] Fold {k+1}/{len(folds)}  train={len(X_tr)}  val={len(X_val)}  "
                  f"prec={prec:.2%}  acc={acc:.2%}  signals={n_sig}")
            results.append({
                "fold": k + 1,
                "tp": tp,
                "fp": fp,
                "signals": n_sig,
                "validation_size": len(y_val),
                "precision": prec,
                "accuracy": acc,
            })

        if not results:
            return {"error": "WFV sin resultados válidos.", "folds": []}

        avg_prec    = float(np.mean([r["precision"]  for r in results]))
        avg_acc     = float(np.mean([r["accuracy"]   for r in results]))
        median_prec = float(np.median([r["precision"] for r in results]))
        total_tp = sum(r["tp"] for r in results)
        total_fp = sum(r["fp"] for r in results)
        total_signals = total_tp + total_fp
        pooled_precision = (
            total_tp / total_signals if total_signals > 0 else 0.0
        )
        evidence_sufficient = bool(
            len(results) >= MIN_WFV_FOLDS
            and all(
                result["signals"] >= MIN_WFV_SIGNALS_PER_FOLD
                for result in results
            )
        )

        print(f"{'─'*55}")
        print(
            f"[WFV] avg_prec={avg_prec:.2%}  median_prec={median_prec:.2%}  "
            f"pooled_prec={pooled_precision:.2%}  avg_acc={avg_acc:.2%}"
        )

        # Preserve the existing metric gate and add only stricter evidence gates.
        existing_metric_gate = (
            avg_prec >= MIN_PRECISION_THRESHOLD
            or median_prec >= WFV_MEDIAN_PRECISION_THRESHOLD
        )
        wfv_passed = bool(
            existing_metric_gate
            and evidence_sufficient
            and pooled_precision >= MIN_PRECISION_THRESHOLD
        )

        return {
            "folds":          results,
            "avg_precision":  round(avg_prec,    4),
            "median_precision": round(median_prec, 4),
            "avg_accuracy":   round(avg_acc,     4),
            "total_tp": total_tp,
            "total_fp": total_fp,
            "total_signals": total_signals,
            "pooled_precision": pooled_precision,
            "evidence_sufficient": evidence_sufficient,
            "wfv_passed":     wfv_passed,
        }


# ─────────────────────────────────────────────────────────────
# MAIN TRAINER
# ─────────────────────────────────────────────────────────────
class ForexEnsembleTrainer:

    def __init__(
        self,
        pair: str = None,
        tuned_params_override: dict | None = None,
        calibration_method: str = "isotonic",
    ):
        if calibration_method not in {"isotonic", "sigmoid"}:
            raise ValueError(
                f"CALIBRATION_METHOD_UNSUPPORTED: {calibration_method}"
            )
        self.storage    = ModelStorage()
        self.best_score = 0.0
        self.best_model = None
        self.model      = None
        self.calibration_sufficient = False
        self.calibration_evidence_sufficient = False
        self.validation_sufficient = False
        self.model_valid = False
        self.pair       = pair
        self.calibration_method = calibration_method
        self._tuned     = (
            tuned_params_override
            if tuned_params_override is not None
            else (_load_tuned_params(pair) if pair else {})
        )

    def _build_xgb(self, scale: float = 1.0):
        # Eliminar claves que se pasan explicitamente para evitar duplicados
        _exclude = ("early_stopping_rounds", "scale_pos_weight",
                    "eval_metric", "verbosity", "random_state")
        p = {k: v for k, v in self._tuned.get("xgb", {}).items()
             if k not in _exclude}
        if p:
            return XGBClassifier(**p, scale_pos_weight=scale,
                                 eval_metric="logloss", verbosity=0, random_state=42)
        return XGBClassifier(
            n_estimators=500, max_depth=5, learning_rate=0.04,
            subsample=0.8, colsample_bytree=0.75,
            min_child_weight=5, gamma=0.2, reg_alpha=0.2, reg_lambda=1.5,
            scale_pos_weight=scale, random_state=42,
            eval_metric="logloss", verbosity=0,
        )

    def _build_lgb(self, scale: float = 1.0):
        _exclude = ("scale_pos_weight", "verbose", "random_state")
        p = {k: v for k, v in self._tuned.get("lgb", {}).items()
             if k not in _exclude}
        if p:
            return lgb.LGBMClassifier(**p, scale_pos_weight=scale,
                                      verbose=-1, random_state=42)
        return lgb.LGBMClassifier(
            n_estimators=500, max_depth=5, learning_rate=0.04,
            subsample=0.8, colsample_bytree=0.75, min_child_samples=25,
            scale_pos_weight=scale, random_state=42, verbose=-1,
        )

    def _build_rf(self, scale: float = 1.0):
        return RandomForestClassifier(
            n_estimators=300, max_depth=8, min_samples_leaf=15,
            class_weight={0: 1.0, 1: scale}, random_state=42, n_jobs=-1,
        )

    @staticmethod
    def _time_split(X, y, train_r=0.72, cal_r=0.14):
        n  = len(X)
        s1 = int(n * train_r)
        s2 = int(n * (train_r + cal_r))
        return (
            X.iloc[:s1], y.iloc[:s1],
            X.iloc[s1:s2], y.iloc[s1:s2],
            X.iloc[s2:],  y.iloc[s2:],
        )

    def train(self, X, y, X_val_ext=None, y_val_ext=None, save: bool = True):
        if X_val_ext is not None and y_val_ext is not None:
            n  = len(X)
            s1 = int(n * 0.85)
            X_tr,  y_tr  = X.iloc[:s1], y.iloc[:s1]
            X_cal, y_cal = X.iloc[s1:],  y.iloc[s1:]
            X_val, y_val = X_val_ext, y_val_ext
        else:
            X_tr, y_tr, X_cal, y_cal, X_val, y_val = self._time_split(X, y)

        n_pos = int(y_tr.sum())
        n_neg = int((y_tr == 0).sum())
        if n_pos < 5 or n_neg < 5:
            print("[ENSEMBLE] ⚠ Clases insuficientes.")
            return 0.0, 0.0

        scale = n_neg / n_pos if n_pos > 0 else 1.0

        using_tuned = "SÍ ✓" if self._tuned else "NO (defaults)"
        print(f"\n[ENSEMBLE] Train={len(X_tr)} | Cal={len(X_cal)} | Val={len(X_val)}")
        print(f"[ENSEMBLE] Par: {self.pair or '?'} | Params tuned: {using_tuned}")
        print(f"[ENSEMBLE] Balance — BUY:{n_pos} SELL:{n_neg} escala:{scale:.2f}")

        # SMOTE
        X_tr_fit, y_tr_fit = X_tr, y_tr
        if _HAS_SMOTE and scale > 1.2:
            try:
                sm = SMOTE(random_state=42, k_neighbors=min(5, n_pos - 1))
                X_tr_fit, y_tr_fit = sm.fit_resample(X_tr, y_tr)
                print(f"[ENSEMBLE] SMOTE: {len(X_tr)} → {len(X_tr_fit)} filas")
                scale = 1.0
            except Exception as e:
                print(f"[ENSEMBLE] SMOTE falló: {e}")

        models = []
        if _HAS_XGB:
            xgb_m = self._build_xgb(scale)
            xgb_m.fit(X_tr_fit, y_tr_fit)
            models.append(("xgb", xgb_m))
        if _HAS_LGB:
            lgb_m = self._build_lgb(scale)
            lgb_m.fit(X_tr_fit, y_tr_fit)
            models.append(("lgb", lgb_m))
        rf_m = self._build_rf(scale)
        rf_m.fit(X_tr_fit, y_tr_fit)
        models.append(("rf", rf_m))

        ensemble   = SoftVotingEnsemble(models)
        calibrated = (
            CalibratedEnsemble(ensemble)
            if self.calibration_method == "isotonic"
            else CalibratedEnsemble(ensemble, method=self.calibration_method)
        )
        calibrated.fit(X_cal, y_cal)
        self.model = calibrated
        self.calibration_sufficient = bool(calibrated.sufficient)
        self.calibration_evidence_sufficient = bool(
            getattr(calibrated, "calibration_evidence_sufficient", False)
        )

        preds = calibrated.predict(X_val)
        acc   = accuracy_score(y_val, preds)
        prec  = precision_score(y_val, preds, zero_division=0)
        f1    = f1_score(y_val, preds, zero_division=0)
        n_buy = int(preds.sum())
        self.validation_sufficient = bool(
            n_buy > 0 and prec >= MIN_PRECISION_THRESHOLD
        )
        self.model_valid = bool(
            self.calibration_sufficient and self.validation_sufficient
        )

        print(f"\n[ENSEMBLE] === MÉTRICAS ===")
        print(f"  Accuracy  : {acc:.2%}  | Precision BUY: {prec:.2%}  | F1: {f1:.4f}")
        print(f"  Umbral    : {calibrated.threshold:.3f}  | Señales: {n_buy}/{len(y_val)}")
        print(
            f"  Válido    : "
            f"{'✓ SÍ' if self.model_valid else '✗ NO (calibración/validación)'}"
        )
        print(f"\n{classification_report(y_val, preds, target_names=['Bearish','Bullish'], zero_division=0)}")

        self._print_importance(models, list(X_tr.columns))

        if save and self.model_valid:
            if prec > self.best_score or self.best_model is None:
                self.best_score = prec
                self.best_model = calibrated
                name = f"ensemble_{(self.pair or 'forex').replace('/', '')}"
                # Guardar feature_names junto al modelo para evitar mismatch en predict
                self.storage.save_model(calibrated, name=name, pair=self.pair,
                                        feature_names=list(X_tr.columns))
                print(f"[ENSEMBLE] ✓ Modelo guardado (precision={prec:.4f})")
        elif save and not self.model_valid:
            print(
                "[ENSEMBLE] ✗ Modelo NO guardado "
                f"(calibracion={self.calibration_sufficient}, "
                f"precision validacion={prec:.2%}, senales={n_buy})"
            )
            print(f"[ENSEMBLE]   Usa 'tune forex <csv>' para optimizar.")

        return acc, prec

    def _print_importance(self, models, feature_names):
        for name, est in models:
            if name in ("xgb", "lgb") and hasattr(est, "feature_importances_"):
                ranked = sorted(zip(feature_names, est.feature_importances_),
                                key=lambda x: x[1], reverse=True)
                print(f"\n[ENSEMBLE] TOP 10 FEATURES ({name.upper()}):")
                for feat, imp in ranked[:10]:
                    bar = "█" * int(imp * 200)
                    print(f"  {feat:<35} {imp:.4f}  {bar}")
                break


# ─────────────────────────────────────────────────────────────
# ENTRENAMIENTO CON WFV DESLIZANTE
# ─────────────────────────────────────────────────────────────
def train_with_wfv(
    X,
    y,
    pair: str = None,
    save: bool = True,
    force: bool = False,
    tuned_params_override: dict | None = None,
):
    print(f"\n{'═'*58}")
    print(f" ENTRENAMIENTO CON WALK-FORWARD DESLIZANTE")
    print(f" Par: {pair or '?'} | Filas: {len(X)} | Features: {len(X.columns)}")
    print(f"{'═'*58}")

    wfv   = WalkForwardValidator(purge=20, n_folds=5)
    wfv_r = (
        wfv.evaluate(ForexEnsembleTrainer, X, y, pair=pair)
        if tuned_params_override is None
        else wfv.evaluate(
            ForexEnsembleTrainer,
            X,
            y,
            pair=pair,
            tuned_params_override=tuned_params_override,
        )
    )

    # BUGFIX: el WFV es el chequeo "honesto" (out-of-sample, sin leakage). Si
    # reprueba, el modelo NO debe guardarse ni quedar disponible para señales
    # reales, sin importar qué tan bien le vaya en el split de calibración
    # final (ese split es un solo corte del mismo dataset y puede engañar).
    # Antes este resultado solo se imprimía como texto y no bloqueaba nada.
    wfv_ok = (not wfv_r.get("error")) and wfv_r.get("wfv_passed", False)
    # ``force`` may request an attempted training run, but it is never quality
    # evidence and cannot authorize publication of a production model.
    can_save = save and wfv_ok

    if "error" in wfv_r:
        print(f"[WFV] Error: {wfv_r['error']}")
    else:
        status = "✓ APROBADO" if wfv_r["wfv_passed"] else "✗ NO APROBADO"
        print(f"\n[WFV] {status} — avg={wfv_r['avg_precision']:.2%}  median={wfv_r['median_precision']:.2%}")

    if save and not can_save:
        print(f"[WFV] ⛔ Modelo NO se guardará ni quedará disponible para señales reales "
              "— reprobó el contrato Walk-Forward Validation.")
        print(f"[WFV]   Usa 'tune forex <csv>' para optimizar hiperparámetros y reintenta.")

    # Entrenamiento final con dataset completo
    print(f"\n[ENSEMBLE] Entrenamiento final (dataset completo)...")
    trainer = (
        ForexEnsembleTrainer(pair=pair)
        if tuned_params_override is None
        else ForexEnsembleTrainer(
            pair=pair,
            tuned_params_override=tuned_params_override,
        )
    )
    # Pair-specific publication is coordinated only by RetrainManager in the
    # integrated pipeline.  This helper may still maintain the generic legacy
    # alias when no pair is supplied.
    generic_save = bool(can_save and pair is None)
    acc, prec = trainer.train(X, y, save=generic_save)

    # Guardar también las feature_names en el modelo final
    if generic_save and trainer.model is not None and trainer.best_model is not None:
        from .model_storage import ModelStorage
        ModelStorage().save_model(
            trainer.best_model,
            name=f"ensemble_{(pair or 'forex').replace('/','').replace('_','')}",
            pair=pair,
            feature_names=list(X.columns),
        )

    wfv_r["model_deployed"] = bool(
        generic_save and trainer.best_model is not None
    )

    return trainer, wfv_r, acc, prec

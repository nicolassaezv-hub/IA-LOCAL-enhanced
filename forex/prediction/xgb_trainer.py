"""
xgb_trainer.py — Ensemble trainer: XGBoost + LightGBM + RandomForest

Bugs corregidos:
  1. XGBoost early_stopping_rounds dentro de VotingClassifier → SoftVotingEnsemble manual
  2. CalibratedClassifierCV(cv='prefit') deprecado en sklearn ≥1.4 → IsotonicCalibrator propio
  3. Desequilibrio de clases severo (62% SELL / 38% BUY) → SMOTE en set de entrenamiento
  4. Umbral de decisión fijo en 0.5 → umbral óptimo buscado en calibración (maximiza F1)
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
    precision_recall_curve,
)
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
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

PARAMS_DIR = "models/forex/params"


def _load_tuned_params(pair: str) -> dict:
    if not pair:
        return {}
    clean = pair.upper().replace("/", "").replace("_", "")
    path  = os.path.join(PARAMS_DIR, f"best_params_{clean}.json")
    if os.path.exists(path):
        with open(path) as f:
            params = json.load(f)
        print(f"[ENSEMBLE] Params tuned cargados para {clean}")
        return params
    return {}


# ─────────────────────────────────────────────────────────────
# SOFT VOTING ENSEMBLE
# ─────────────────────────────────────────────────────────────
class SoftVotingEnsemble:
    """Promedia predict_proba de modelos ya entrenados. No re-entrena."""
    def __init__(self, models: list):
        self.models   = models
        self.classes_ = np.array([0, 1])

    def predict_proba(self, X) -> np.ndarray:
        probs = [m.predict_proba(X) for _, m in self.models]
        return np.mean(probs, axis=0)

    def predict(self, X, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= threshold).astype(int)


# ─────────────────────────────────────────────────────────────
# ISOTONIC CALIBRATOR + OPTIMAL THRESHOLD
# ─────────────────────────────────────────────────────────────
class CalibratedEnsemble:
    """
    Wraper final que:
      1. Calibra probabilidades con regresión isotónica en holdout
      2. Busca el umbral óptimo (max F1 en calibración) para evitar colapso a clase mayoritaria
    """
    def __init__(self, base: SoftVotingEnsemble):
        self.base      = base
        self.cal_1     = IsotonicRegression(out_of_bounds="clip")
        self.threshold = 0.5
        self.classes_  = np.array([0, 1])

    def fit(self, X_cal, y_cal):
        raw = self.base.predict_proba(X_cal)
        self.cal_1.fit(raw[:, 1], y_cal.values if hasattr(y_cal, 'values') else y_cal)

        # Buscar umbral óptimo: maximizar F1 en calibración
        cal_probs = self.predict_proba(X_cal)[:, 1]
        prec_arr, rec_arr, thresh_arr = precision_recall_curve(y_cal, cal_probs)
        # fix: thresh tiene len(prec)-1 elementos
        prec_arr, rec_arr, thresh_arr = prec_arr[:-1], rec_arr[:-1], thresh_arr
        f1_arr = np.where(
            (prec_arr + rec_arr) > 0,
            2 * prec_arr * rec_arr / (prec_arr + rec_arr + 1e-9),
            0,
        )
        # Solo considerar umbrales donde precision >= 0.40 (señales útiles)
        mask = prec_arr >= 0.40
        if mask.any():
            best_idx = np.argmax(f1_arr[mask])
            self.threshold = float(thresh_arr[mask][best_idx])
        else:
            self.threshold = 0.5
        print(f"[CALIBRATOR] Umbral óptimo: {self.threshold:.3f} (F1-max con prec≥40%)")
        return self

    def predict_proba(self, X) -> np.ndarray:
        raw = self.base.predict_proba(X)
        p1  = np.clip(self.cal_1.predict(raw[:, 1]), 0, 1)
        p0  = 1.0 - p1
        return np.column_stack([p0, p1])

    def predict(self, X) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= self.threshold).astype(int)


# ─────────────────────────────────────────────────────────────
# MAIN TRAINER
# ─────────────────────────────────────────────────────────────
class ForexEnsembleTrainer:

    def __init__(self, pair: str = None):
        self.storage    = ModelStorage()
        self.best_score = 0.0
        self.best_model = None
        self.model      = None
        self.pair       = pair
        self._tuned     = _load_tuned_params(pair) if pair else {}

    def _build_xgb(self, scale: float = 1.0):
        p = {k: v for k, v in self._tuned.get("xgb", {}).items()
             if k not in ("early_stopping_rounds",)}
        if p:
            return XGBClassifier(**p, scale_pos_weight=scale,
                                 eval_metric="logloss", verbosity=0, random_state=42)
        return XGBClassifier(
            n_estimators=400, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.75,
            min_child_weight=3, gamma=0.1, reg_alpha=0.1, reg_lambda=1.0,
            scale_pos_weight=scale, random_state=42,
            eval_metric="logloss", verbosity=0,
        )

    def _build_lgb(self, scale: float = 1.0):
        p = self._tuned.get("lgb", {})
        if p:
            return lgb.LGBMClassifier(**p, scale_pos_weight=scale,
                                      verbose=-1, random_state=42)
        return lgb.LGBMClassifier(
            n_estimators=400, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.75, min_child_samples=20,
            scale_pos_weight=scale, random_state=42, verbose=-1,
        )

    def _build_rf(self, scale: float = 1.0):
        return RandomForestClassifier(
            n_estimators=200, max_depth=7, min_samples_leaf=10,
            class_weight={0: 1.0, 1: scale}, random_state=42, n_jobs=-1,
        )

    @staticmethod
    def _time_split(X, y, train_r=0.70, cal_r=0.15):
        """70% train | 15% calibración | 15% validación — sin solapamiento."""
        n  = len(X)
        s1 = int(n * train_r)
        s2 = int(n * (train_r + cal_r))
        return (
            X.iloc[:s1], y.iloc[:s1],
            X.iloc[s1:s2], y.iloc[s1:s2],
            X.iloc[s2:],  y.iloc[s2:],
        )

    def train(self, X, y, save: bool = True):
        X_tr, y_tr, X_cal, y_cal, X_val, y_val = self._time_split(X, y)

        n_pos = int(y_tr.sum())
        n_neg = int((y_tr == 0).sum())
        scale = n_neg / n_pos if n_pos > 0 else 1.0

        using_tuned = "SÍ ✓" if self._tuned else "NO (defaults)"
        print(f"\n[ENSEMBLE] Train={len(X_tr)} | Cal={len(X_cal)} | Val={len(X_val)}")
        print(f"[ENSEMBLE] Par: {self.pair or '?'} | Params tuned: {using_tuned}")
        print(f"[ENSEMBLE] Balance — bullish:{n_pos} bearish:{n_neg} peso:{scale:.2f}")

        # SMOTE en training set (solo si disponible y hay desbalance significativo)
        X_tr_fit, y_tr_fit = X_tr, y_tr
        if _HAS_SMOTE and scale > 1.3:
            try:
                sm = SMOTE(random_state=42, k_neighbors=min(5, n_pos - 1))
                X_tr_fit, y_tr_fit = sm.fit_resample(X_tr, y_tr)
                print(f"[ENSEMBLE] SMOTE aplicado: {len(X_tr)} → {len(X_tr_fit)} filas")
                # Después de SMOTE: scale=1 (balanceado)
                scale = 1.0
            except Exception as e:
                print(f"[ENSEMBLE] SMOTE falló ({e}), usando datos originales")
                X_tr_fit, y_tr_fit = X_tr, y_tr

        models = []

        if _HAS_XGB:
            print("[ENSEMBLE] Entrenando XGBoost...")
            xgb_m = self._build_xgb(scale)
            xgb_m.fit(X_tr_fit, y_tr_fit)
            models.append(("xgb", xgb_m))

        if _HAS_LGB:
            print("[ENSEMBLE] Entrenando LightGBM...")
            lgb_m = self._build_lgb(scale)
            lgb_m.fit(X_tr_fit, y_tr_fit)
            models.append(("lgb", lgb_m))

        print("[ENSEMBLE] Entrenando RandomForest...")
        rf_m = self._build_rf(scale)
        rf_m.fit(X_tr_fit, y_tr_fit)
        models.append(("rf", rf_m))

        ensemble   = SoftVotingEnsemble(models)
        calibrated = CalibratedEnsemble(ensemble)
        calibrated.fit(X_cal, y_cal)

        self.model = calibrated

        preds = calibrated.predict(X_val)
        acc   = accuracy_score(y_val, preds)
        prec  = precision_score(y_val, preds, zero_division=0)
        f1    = f1_score(y_val, preds, zero_division=0)
        n_buy_signals = int(preds.sum())

        print(f"\n[ENSEMBLE] === MÉTRICAS DE VALIDACIÓN ===")
        print(f"  Accuracy      : {acc:.4f}  ({acc*100:.1f}%)")
        print(f"  Precision BUY : {prec:.4f}  ({prec*100:.1f}%)  ← señales BUY correctas")
        print(f"  F1 Score      : {f1:.4f}")
        print(f"  Umbral usado  : {calibrated.threshold:.3f}")
        print(f"  Señales BUY   : {n_buy_signals}/{len(y_val)}")
        print(f"\n{classification_report(y_val, preds, target_names=['Bearish','Bullish'], zero_division=0)}")

        self._print_importance(models, list(X_tr.columns))

        if prec > self.best_score or self.best_model is None:
            self.best_score = prec
            self.best_model = calibrated
            if save:
                name = f"ensemble_{(self.pair or 'forex').replace('/','')}"
                self.storage.save_model(calibrated, name=name)
                print(f"[ENSEMBLE] Modelo guardado (precision={prec:.4f})")

        return acc, prec

    def _print_importance(self, models, feature_names):
        for name, est in models:
            if name in ("xgb", "lgb") and hasattr(est, "feature_importances_"):
                ranked = sorted(zip(feature_names, est.feature_importances_),
                                key=lambda x: x[1], reverse=True)
                print(f"\n[ENSEMBLE] === TOP 15 FEATURES ({name.upper()}) ===")
                for feat, score in ranked[:15]:
                    bar = "█" * max(1, int(score * 200))
                    print(f"  {feat:<28} {score:.5f}  {bar}")
                break


# Alias legacy
ForexXGBTrainer = ForexEnsembleTrainer

"""
integrated_pipeline.py — Pipeline completo de predicción Forex

Modos:
  train          — entrena ensemble sobre CSV
  predict        — señal de la última vela
  multi_horizon  — consenso entre horizontes 5/10/20 velas
  backtest       — simulación en datos retenidos
  tune           — Optuna + train
  full           — train + predict + backtest en un solo paso
"""

import numpy as np
import pandas as pd

from .feature_engineering  import build_features
from .dataset_builder      import DatasetBuilder
from .predictor            import ForexPredictor
from .backtester           import ForexBacktester
from .xgb_trainer          import ForexEnsembleTrainer
from .hyperparameter_tuner import ForexHyperparameterTuner
from .csv_adapter          import adapt_csv


def _load(filepath: str, pair: str = None) -> pd.DataFrame:
    return adapt_csv(filepath, pair=pair)


def _infer_pair(df: pd.DataFrame, pair: str = None) -> str:
    if pair:
        return pair
    if "pair" in df.columns:
        return str(df["pair"].iloc[-1])
    return "UNKNOWN"


class ForexIntegratedPipeline:

    def __init__(
        self,
        horizon: int          = 10,
        rr_ratio: float       = 1.5,
        min_confidence: float = 0.62,
        min_adx: float        = 22.0,
    ):
        self.horizon        = horizon
        self.rr_ratio       = rr_ratio
        self.min_confidence = min_confidence
        self.min_adx        = min_adx
        self.predictor      = ForexPredictor(
            min_confidence=min_confidence,
            min_adx=min_adx,
        )
        self.backtester     = ForexBacktester()

    # ─────────────────────────────────────────────────────────
    # TUNE — Optuna → train
    # ─────────────────────────────────────────────────────────
    def tune(self, filepath: str, pair: str = None,
             n_trials: int = None, rr_ratio: float = None,
             horizon: int = None) -> dict:
        df   = _load(filepath, pair=pair)
        df   = build_features(df)
        pair = _infer_pair(df, pair)
        rr   = rr_ratio or self.rr_ratio
        hz   = horizon  or self.horizon

        X, y = DatasetBuilder(df).build(horizon=hz, rr_ratio=rr)
        if len(X) < 100:
            return {"error": f"Filas insuficientes: {len(X)}. Mínimo 100."}

        if n_trials is None:
            n_trials = ForexHyperparameterTuner.recommend_trials(len(X))

        split   = int(len(X) * 0.80)
        X_tr, y_tr = X.iloc[:split], y.iloc[:split]
        X_val, y_val = X.iloc[split:], y.iloc[split:]

        tuner = ForexHyperparameterTuner(pair=pair)
        best  = tuner.tune(X_tr, y_tr, X_val, y_val, n_trials=n_trials)

        trainer   = ForexEnsembleTrainer(pair=pair)
        acc, prec = trainer.train(X, y, save=True)
        signal    = self.predictor.signal(X, pair=pair)

        return {
            "type":      "tune_complete",
            "pair":      pair,
            "rows":      len(X),
            "n_trials":  n_trials,
            "accuracy":  round(acc,  4),
            "precision": round(prec, 4),
            "signal":    signal,
        }

    # ─────────────────────────────────────────────────────────
    # TRAIN
    # ─────────────────────────────────────────────────────────
    def train(self, filepath: str, pair: str = None) -> dict:
        df   = _load(filepath, pair=pair)
        df   = build_features(df)
        pair = _infer_pair(df, pair)

        X, y = DatasetBuilder(df).build(horizon=self.horizon, rr_ratio=self.rr_ratio)
        if len(X) < 100:
            return {"error": f"Filas insuficientes: {len(X)}. Mínimo 100."}

        trainer   = ForexEnsembleTrainer(pair=pair)
        acc, prec = trainer.train(X, y, save=True)

        return {
            "type":      "training_complete",
            "pair":      pair,
            "rows":      len(X),
            "features":  len(X.columns),
            "accuracy":  round(acc,  4),
            "precision": round(prec, 4),
            "model":     "guardado en models/forex/",
        }

    # ─────────────────────────────────────────────────────────
    # PREDICT — señal de la última vela
    # ─────────────────────────────────────────────────────────
    def predict(self, filepath: str, pair: str = None) -> dict:
        df   = _load(filepath, pair=pair)
        df   = build_features(df)
        pair = _infer_pair(df, pair)

        X, _ = DatasetBuilder(df).build(horizon=self.horizon, rr_ratio=self.rr_ratio)
        if len(X) == 0:
            return {"error": "Sin filas tras feature engineering."}

        signal = self.predictor.signal(X, pair=pair)
        return {"type": "prediction", "rows_processed": len(X), **signal}

    # ─────────────────────────────────────────────────────────
    # MULTI-HORIZON — consenso 5/10/20 velas
    # ─────────────────────────────────────────────────────────
    def predict_multi_horizon(self, filepath: str, pair: str = None) -> dict:
        df   = _load(filepath, pair=pair)
        df   = build_features(df)
        pair = _infer_pair(df, pair)

        votes = []
        for h in [5, 10, 20]:
            X, y = DatasetBuilder(df).build(horizon=h, rr_ratio=self.rr_ratio)
            if len(X) < 100:
                continue

            trainer = ForexEnsembleTrainer(pair=pair)
            trainer.train(X, y, save=False)

            if trainer.model is None:
                continue

            probs = trainer.model.predict_proba(X.tail(1))[0]
            pred  = int(np.argmax(probs))
            conf  = float(np.max(probs))
            votes.append({
                "horizon":    h,
                "direction":  "bullish" if pred == 1 else "bearish",
                "confidence": round(conf, 4),
            })

        if not votes:
            return {"error": "No se pudo entrenar en ningún horizonte."}

        bull = sum(1 for v in votes if v["direction"] == "bullish")
        bear = len(votes) - bull
        avg_conf = round(float(np.mean([v["confidence"] for v in votes])), 4)

        if bull >= 2 and avg_conf >= self.min_confidence:
            action = "BUY";  dir_ = "bullish"
        elif bear >= 2 and avg_conf >= self.min_confidence:
            action = "SELL"; dir_ = "bearish"
        else:
            action = "HOLD"; dir_ = "mixed"

        return {
            "type":           "multi_horizon",
            "pair":           pair,
            "action":         action,
            "direction":      dir_,
            "avg_confidence": avg_conf,
            "horizon_votes":  votes,
            "bullish_votes":  bull,
            "bearish_votes":  bear,
        }

    # ─────────────────────────────────────────────────────────
    # BACKTEST
    # ─────────────────────────────────────────────────────────
    def backtest(self, filepath: str, pair: str = None) -> dict:
        df   = _load(filepath, pair=pair)
        df   = build_features(df)

        X, _ = DatasetBuilder(df).build(horizon=self.horizon, rr_ratio=self.rr_ratio)
        if len(X) < 50:
            return {"error": "Datos insuficientes para backtest."}

        return self.backtester.run(X)

    # ─────────────────────────────────────────────────────────
    # FULL — train + predict + backtest
    # ─────────────────────────────────────────────────────────
    def run(self, filepath: str, mode: str = "full", pair: str = None) -> dict:
        if mode == "train":
            return self.train(filepath, pair=pair)
        if mode == "predict":
            return self.predict(filepath, pair=pair)
        if mode == "backtest":
            return self.backtest(filepath, pair=pair)
        if mode == "multi_horizon":
            return self.predict_multi_horizon(filepath, pair=pair)

        # full
        train_r   = self.train(filepath, pair=pair)
        predict_r = self.predict(filepath, pair=pair)
        back_r    = self.backtest(filepath, pair=pair)

        return {
            "type":     "full_pipeline",
            "training": train_r,
            "signal":   predict_r,
            "backtest": back_r,
        }

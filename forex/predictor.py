"""
integrated_pipeline.py — Pipeline completo de predicción Forex

NUEVO: soporte MTF real — train/predict aceptan path_h4 y path_d1
       para enriquecer el CSV H1 con features de H4 y D1 vía merge_asof.

Modos:
  train          — entrena ensemble (WFV deslizante)
  predict        — señal de la última vela real
  multi_horizon  — consenso horizontes 5/10/20
  backtest       — simulación histórica
  tune           — Optuna + train
  full           — train + predict + backtest
"""

import numpy as np
import pandas as pd

from .feature_engineering  import build_features
from .dataset_builder      import DatasetBuilder, get_pair_config
from .predictor            import ForexPredictor
from .backtester           import ForexBacktester
from .xgb_trainer          import ForexEnsembleTrainer, train_with_wfv
from .hyperparameter_tuner import ForexHyperparameterTuner
from .csv_adapter          import adapt_csv


def _load(filepath: str, pair: str = None,
          path_h4: str = None, path_d1: str = None) -> pd.DataFrame:
    return adapt_csv(filepath, pair=pair, path_h4=path_h4, path_d1=path_d1)


def _infer_pair(df: pd.DataFrame, pair: str = None) -> str:
    if pair:
        return pair
    if "pair" in df.columns:
        val = df["pair"].iloc[-1]
        if isinstance(val, str):
            return str(val)
    return "UNKNOWN"


class ForexIntegratedPipeline:

    def __init__(
        self,
        horizon: int          = None,
        rr_ratio: float       = None,
        min_confidence: float = 0.65,
        min_adx: float        = 22.0,
    ):
        from .model_storage import ModelStorage
        self._horizon        = horizon
        self._rr_ratio       = rr_ratio
        self.min_confidence  = min_confidence
        self.min_adx         = min_adx
        self.storage         = ModelStorage()
        self.predictor       = ForexPredictor(
            min_confidence=min_confidence,
            min_adx=min_adx,
        )
        self.backtester      = ForexBacktester()

    def _pair_params(self, pair: str):
        cfg = get_pair_config(pair)
        return (
            self._horizon  if self._horizon  is not None else cfg["horizon"],
            self._rr_ratio if self._rr_ratio is not None else cfg["rr_ratio"],
        )

    # ─────────────────────────────────────────────────────────
    # TRAIN — con WFV deslizante + MTF opcional
    # ─────────────────────────────────────────────────────────
    def train(self, filepath: str, pair: str = None,
              path_h4: str = None, path_d1: str = None,
              use_wfv: bool = True) -> dict:
        df   = _load(filepath, pair=pair, path_h4=path_h4, path_d1=path_d1)
        pair = _infer_pair(df, pair)
        df   = build_features(df)

        horizon, rr_ratio = self._pair_params(pair)

        builder = DatasetBuilder(df)
        X, y    = builder.build(horizon=horizon, rr_ratio=rr_ratio)

        if len(X) < 100:
            return {"error": f"Filas insuficientes: {len(X)}. Mínimo 100."}

        mtf_note = ""
        h4_cols = [c for c in X.columns if c.startswith("h4_")]
        d1_cols = [c for c in X.columns if c.startswith("d1_")]
        if h4_cols or d1_cols:
            mtf_note = f" | MTF: H4={len(h4_cols)} D1={len(d1_cols)} features"

        print(f"\n[PIPELINE] Par: {pair} | Horizon: {horizon} | RR: {rr_ratio}{mtf_note}")

        if use_wfv and len(X) >= 300:
            trainer, wfv_r, acc, prec = train_with_wfv(X, y, pair=pair, save=True)
            self.predictor.invalidate_cache(pair=pair)
            return {
                "type":        "training_complete",
                "pair":        pair,
                "rows":        len(X),
                "features":    len(X.columns),
                "horizon":     horizon,
                "rr_ratio":    rr_ratio,
                "mtf_features": len(h4_cols) + len(d1_cols),
                "accuracy":    round(acc,  4),
                "precision":   round(prec, 4),
                "wfv":         wfv_r,
                "model_valid": getattr(trainer.model, "sufficient", False) if trainer.model else False,
                "model":       "guardado" if prec >= 0.65 else "NO guardado (prec < 65%)",
            }
        else:
            trainer   = ForexEnsembleTrainer(pair=pair)
            acc, prec = trainer.train(X, y, save=True)
            self.predictor.invalidate_cache(pair=pair)
            return {
                "type":        "training_complete",
                "pair":        pair,
                "rows":        len(X),
                "features":    len(X.columns),
                "accuracy":    round(acc,  4),
                "precision":   round(prec, 4),
                "model_valid": getattr(trainer.model, "sufficient", False) if trainer.model else False,
                "model":       "guardado" if prec >= 0.65 else "NO guardado (prec < 65%)",
            }

    # ─────────────────────────────────────────────────────────
    # PREDICT — última vela real + MTF opcional
    # ─────────────────────────────────────────────────────────
    def predict(self, filepath: str, pair: str = None,
                path_h4: str = None, path_d1: str = None) -> dict:
        df   = _load(filepath, pair=pair, path_h4=path_h4, path_d1=path_d1)
        pair = _infer_pair(df, pair)
        df   = build_features(df)

        # Cargar feature_names guardadas junto al modelo (evita mismatch)
        train_columns = None
        try:
            _, train_columns = self.storage.load_model_with_features(pair=pair)
        except Exception:
            train_columns = None

        builder = DatasetBuilder(df)
        X_pred  = builder.predict_features(n_rows=1, train_columns=train_columns)

        if len(X_pred) == 0:
            return {"error": "Sin filas válidas tras feature engineering."}

        signal = self.predictor.signal(X_pred, pair=pair)
        return {"type": "prediction", "rows_processed": len(df), **signal}

    # ─────────────────────────────────────────────────────────
    # MULTI-HORIZON
    # ─────────────────────────────────────────────────────────
    def predict_multi_horizon(self, filepath: str, pair: str = None,
                               path_h4: str = None, path_d1: str = None) -> dict:
        df   = _load(filepath, pair=pair, path_h4=path_h4, path_d1=path_d1)
        pair = _infer_pair(df, pair)
        df   = build_features(df)

        from .model_storage import ModelStorage
        storage = ModelStorage()

        votes       = []
        horizons    = [5, 10, 20]
        _, rr_ratio = self._pair_params(pair)

        for h in horizons:
            builder = DatasetBuilder(df)
            X, y    = builder.build(horizon=h, rr_ratio=rr_ratio)
            if len(X) < 100:
                continue

            model_exists = storage.latest_exists(pair=f"{pair}_h{h}")
            model_name   = f"ensemble_{pair.replace('/','')}_h{h}"

            if not model_exists:
                print(f"[MULTI] Entrenando h={h}...")
                trainer = ForexEnsembleTrainer(pair=pair)
                trainer.train(X, y, save=False)
                if trainer.model is not None and trainer.model.sufficient:
                    storage.save_model(trainer.model, name=model_name, pair=f"{pair}_h{h}")
                model = trainer.model
            else:
                model = storage.load_model(pair=f"{pair}_h{h}")

            if model is None:
                continue

            X_pred = builder.predict_features(n_rows=1)
            if len(X_pred) == 0:
                continue

            probs = model.predict_proba(X_pred)[0]
            pred  = int(np.argmax(probs))
            conf  = float(np.max(probs))
            votes.append({
                "horizon":    h,
                "direction":  "bullish" if pred == 1 else "bearish",
                "confidence": round(conf, 4),
                "valid":      getattr(model, "sufficient", True),
            })

        if not votes:
            return {"error": "No se pudo obtener señal en ningún horizonte."}

        bull        = sum(1 for v in votes if v["direction"] == "bullish")
        bear        = len(votes) - bull
        avg_conf    = round(float(np.mean([v["confidence"] for v in votes])), 4)
        valid_votes = [v for v in votes if v["valid"]]

        if bull >= 2 and avg_conf >= self.min_confidence and len(valid_votes) >= 2:
            action = "BUY";  dir_ = "bullish"
        elif bear >= 2 and avg_conf >= self.min_confidence and len(valid_votes) >= 2:
            action = "SELL"; dir_ = "bearish"
        else:
            action = "HOLD"; dir_ = "mixed"

        return {
            "type":             "multi_horizon",
            "pair":             pair,
            "action":           action,
            "direction":        dir_,
            "avg_confidence":   avg_conf,
            "est_prob_correct": round(avg_conf * 100, 1),
            "horizon_votes":    votes,
            "bullish_votes":    bull,
            "bearish_votes":    bear,
        }

    # ─────────────────────────────────────────────────────────
    # TUNE
    # ─────────────────────────────────────────────────────────
    def tune(self, filepath: str, pair: str = None,
             n_trials: int = None, rr_ratio: float = None,
             horizon: int = None, path_h4: str = None,
             path_d1: str = None) -> dict:
        df   = _load(filepath, pair=pair, path_h4=path_h4, path_d1=path_d1)
        pair = _infer_pair(df, pair)
        df   = build_features(df)

        hz, rr = self._pair_params(pair)
        rr = rr_ratio or rr
        hz = horizon  or hz

        X, y = DatasetBuilder(df).build(horizon=hz, rr_ratio=rr)
        if len(X) < 100:
            return {"error": f"Filas insuficientes: {len(X)}."}

        if n_trials is None:
            n_trials = ForexHyperparameterTuner.recommend_trials(len(X))

        split        = int(len(X) * 0.80)
        X_tr, y_tr   = X.iloc[:split], y.iloc[:split]
        X_val, y_val = X.iloc[split:],  y.iloc[split:]

        tuner = ForexHyperparameterTuner(pair=pair)
        best  = tuner.tune(X_tr, y_tr, X_val, y_val, n_trials=n_trials)

        trainer, wfv_r, acc, prec = train_with_wfv(X, y, pair=pair, save=True)
        self.predictor.invalidate_cache(pair=pair)

        X_pred = DatasetBuilder(df).predict_features(n_rows=1)
        signal = self.predictor.signal(X_pred, pair=pair) if len(X_pred) > 0 else {}

        return {
            "type":      "tune_complete",
            "pair":      pair,
            "rows":      len(X),
            "n_trials":  n_trials,
            "accuracy":  round(acc,  4),
            "precision": round(prec, 4),
            "wfv":       wfv_r,
            "signal":    signal,
        }

    # ─────────────────────────────────────────────────────────
    # BACKTEST
    # ─────────────────────────────────────────────────────────
    def backtest(self, filepath: str, pair: str = None,
                 path_h4: str = None, path_d1: str = None) -> dict:
        df   = _load(filepath, pair=pair, path_h4=path_h4, path_d1=path_d1)
        pair = _infer_pair(df, pair)
        df   = build_features(df)

        horizon, rr_ratio = self._pair_params(pair)
        X, _ = DatasetBuilder(df).build(horizon=horizon, rr_ratio=rr_ratio)
        if len(X) < 50:
            return {"error": "Datos insuficientes."}

        return self.backtester.run(X, pair=pair)

    # ─────────────────────────────────────────────────────────
    # FULL
    # ─────────────────────────────────────────────────────────
    def run(self, filepath: str, mode: str = "full", pair: str = None,
            path_h4: str = None, path_d1: str = None) -> dict:
        kw = dict(pair=pair, path_h4=path_h4, path_d1=path_d1)
        if mode == "train":
            return self.train(filepath, **kw)
        if mode == "predict":
            return self.predict(filepath, **kw)
        if mode == "backtest":
            return self.backtest(filepath, **kw)
        if mode == "multi_horizon":
            return self.predict_multi_horizon(filepath, **kw)

        train_r   = self.train(filepath, **kw)
        predict_r = self.predict(filepath, **kw)
        back_r    = self.backtest(filepath, **kw)

        return {
            "type":     "full_pipeline",
            "training": train_r,
            "signal":   predict_r,
            "backtest": back_r,
        }

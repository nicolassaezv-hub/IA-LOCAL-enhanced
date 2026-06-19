"""
integrated_pipeline.py — Full pipeline with Optuna tuning support

Modes:
  train          — ensemble training (uses tuned params if available)
  predict        — single-candle signal with confidence + regime filter
  multi_horizon  — vote across 3 horizons, only signal on consensus
  backtest       — simulate on held-out data
  tune           — run Optuna, save best params, then train with them
  full           — train + predict + backtest in one shot
"""

import pandas as pd
import numpy as np

from .feature_engineering    import build_features
from .dataset_builder        import DatasetBuilder
from .predictor              import ForexPredictor
from .backtester             import ForexBacktester
from .xgb_trainer            import ForexEnsembleTrainer
from .hyperparameter_tuner   import ForexHyperparameterTuner
from .csv_adapter            import adapt_csv


def _load(filepath: str, pair: str = None) -> pd.DataFrame:
    """Load any supported CSV/XLSX and normalize column names automatically."""
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
        horizon: int        = 10,
        rr_ratio: float     = 1.5,
        min_confidence: float = 0.62,
        min_adx: float      = 22.0,
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

    # -------------------------------------------------------
    # TUNE — run Optuna then train with the winning params
    # -------------------------------------------------------
    def tune(
        self,
        filepath: str,
        pair: str       = None,
        n_trials: int   = None,
        rr_ratio: float = None,
        horizon: int    = None,
    ) -> dict:
        """
        Run Optuna hyperparameter search, save best params, then train.

        Parameters
        ----------
        filepath  : path to your CSV / XLSX data file
        pair      : forex pair name, e.g. "EURUSD" (used to save params)
        n_trials  : number of Optuna trials per model.
                    If None, auto-selected based on dataset size.
        rr_ratio  : override pipeline's default rr_ratio for this run
        horizon   : override pipeline's default horizon for this run
        """
        df = _load(filepath, pair=pair)
        df = build_features(df)

        pair      = _infer_pair(df, pair)
        rr_ratio  = rr_ratio or self.rr_ratio
        horizon   = horizon  or self.horizon

        builder   = DatasetBuilder(df)
        X, y      = builder.build(horizon=horizon, rr_ratio=rr_ratio)

        if len(X) < 100:
            return {
                "error": (
                    f"Too few rows: {len(X)}. "
                    "Need at least 100 for tuning."
                )
            }

        # Auto-pick trial count based on data size if not specified
        if n_trials is None:
            n_trials = ForexHyperparameterTuner.recommend_trials(len(X))

        # Split for Optuna (time-based, 80/20)
        split   = int(len(X) * 0.80)
        X_train = X.iloc[:split]
        y_train = y.iloc[:split]
        X_val   = X.iloc[split:]
        y_val   = y.iloc[split:]

        print(f"\n[PIPELINE] Starting Optuna tuning for {pair}...")
        print(f"[PIPELINE] {len(X_train)} train rows | {len(X_val)} val rows | {n_trials} trials")

        tuner      = ForexHyperparameterTuner(pair=pair)
        best_params = tuner.tune(X_train, y_train, X_val, y_val, n_trials=n_trials)

        # Now train the full ensemble using the tuned params
        print(f"\n[PIPELINE] Training final ensemble with tuned params...")
        trainer   = ForexEnsembleTrainer(pair=pair)   # auto-loads saved params
        acc, prec = trainer.train(X, y, save=True)

        signal    = self.predictor.signal(X, pair=pair)

        return {
            "type":          "tune_complete",
            "pair":          pair,
            "rows":          len(X),
            "n_trials":      n_trials,
            "rr_ratio":      rr_ratio,
            "horizon":       horizon,
            "params_tuned":  list(best_params.keys()),
            "accuracy":      round(acc,  4),
            "precision":     round(prec, 4),
            "signal":        signal,
            "note": (
                f"Tuned params saved to models/forex/params/best_params_{pair.upper()}.json. "
                "They will be loaded automatically on all future train() calls for this pair."
            ),
        }

    # -------------------------------------------------------
    # TRAIN — ensemble on CSV, uses tuned params if available
    # -------------------------------------------------------
    def train(self, filepath: str, pair: str = None) -> dict:
        df   = _load(filepath, pair=pair)
        df   = build_features(df)
        pair = _infer_pair(df, pair)

        builder   = DatasetBuilder(df)
        X, y      = builder.build(horizon=self.horizon, rr_ratio=self.rr_ratio)

        if len(X) < 100:
            return {"error": f"Too few usable rows: {len(X)}. Need at least 100."}

        n_buy  = int(y.sum())
        n_sell = int((y == 0).sum())

        trainer   = ForexEnsembleTrainer(pair=pair)
        acc, prec = trainer.train(X, y, save=True)

        return {
            "type":           "training_complete",
            "pair":           pair,
            "rows":           len(X),
            "features":       len(X.columns),
            "target_horizon": self.horizon,
            "rr_ratio":       self.rr_ratio,
            "buy_labels":     n_buy,
            "sell_labels":    n_sell,
            "accuracy":       round(acc,  4),
            "precision":      round(prec, 4),
            "model":          "saved to models/forex/",
            "tip": (
                "Run tune() first to find the best hyperparameters for this "
                "pair. Subsequent train() calls will use them automatically."
            ),
        }

    # -------------------------------------------------------
    # PREDICT — signal for the latest candle
    # -------------------------------------------------------
    def predict(self, filepath: str, pair: str = None) -> dict:
        df   = _load(filepath, pair=pair)
        df   = build_features(df)
        pair = _infer_pair(df, pair)

        builder = DatasetBuilder(df)
        X, _    = builder.build(horizon=self.horizon, rr_ratio=self.rr_ratio)

        if len(X) == 0:
            return {"error": "No rows remain after feature engineering."}

        signal = self.predictor.signal(X, pair=pair)
        return {"type": "prediction", "rows_processed": len(X), **signal}

    # -------------------------------------------------------
    # MULTI-HORIZON PREDICT — consensus across 3 horizons
    # Only fires BUY/SELL when at least 2/3 horizons agree.
    # -------------------------------------------------------
    def predict_multi_horizon(self, filepath: str, pair: str = None) -> dict:
        df   = _load(filepath, pair=pair)
        df   = build_features(df)
        pair = _infer_pair(df, pair)

        horizons = [5, 10, 20]
        votes    = []

        print(f"\n[MULTI-HORIZON] Voting across horizons {horizons} for {pair}...")

        for h in horizons:
            builder = DatasetBuilder(df)
            X, y    = builder.build(horizon=h, rr_ratio=self.rr_ratio)

            if len(X) < 100:
                print(f"  horizon={h} → insufficient data ({len(X)} rows), skipping")
                continue

            trainer = ForexEnsembleTrainer(pair=pair)
            trainer.train(X, y, save=False)

            if trainer.best_model is None:
                continue

            probs     = trainer.best_model.predict_proba(X.tail(1))[0]
            pred      = int(np.argmax(probs))
            conf      = float(np.max(probs))
            direction = "bullish" if pred == 1 else "bearish"

            votes.append({"horizon": h, "direction": direction, "confidence": round(conf, 4)})
            print(f"  horizon={h} → {direction} (conf={conf:.4f})")

        if not votes:
            return {"error": "Could not train on any horizon."}

        bullish_count = sum(1 for v in votes if v["direction"] == "bullish")
        bearish_count = len(votes) - bullish_count
        avg_conf      = round(float(np.mean([v["confidence"] for v in votes])), 4)

        if bullish_count >= 2 and avg_conf >= self.min_confidence:
            consensus, consensus_dir = "BUY",  "bullish"
        elif bearish_count >= 2 and avg_conf >= self.min_confidence:
            consensus, consensus_dir = "SELL", "bearish"
        else:
            consensus, consensus_dir = "HOLD", "mixed"

        return {
            "type":           "multi_horizon_prediction",
            "pair":           pair,
            "action":         consensus,
            "direction":      consensus_dir,
            "avg_confidence": avg_conf,
            "horizon_votes":  votes,
            "bullish_votes":  bullish_count,
            "bearish_votes":  bearish_count,
            "interpretation": (
                f"{bullish_count}/{len(votes)} horizons agree → {consensus}. "
                + ("Strong conviction." if avg_conf >= 0.70 else "Moderate conviction.")
                if consensus != "HOLD"
                else "Horizons disagree or confidence too low — HOLD."
            ),
        }

    # -------------------------------------------------------
    # BACKTEST
    # -------------------------------------------------------
    def backtest(self, filepath: str, pair: str = None) -> dict:
        df   = _load(filepath, pair=pair)
        df   = build_features(df)

        builder = DatasetBuilder(df)
        X, _    = builder.build(horizon=self.horizon, rr_ratio=self.rr_ratio)

        return {"type": "backtest", "results": self.backtester.run(X)}

    # -------------------------------------------------------
    # FULL — train + predict + backtest in one call
    # -------------------------------------------------------
    def run(self, filepath: str, mode: str = "full", pair: str = None) -> dict:
        if mode == "tune":
            return self.tune(filepath, pair=pair)

        if mode == "multi_horizon":
            return self.predict_multi_horizon(filepath, pair=pair)

        df   = _load(filepath, pair=pair)
        df   = build_features(df)
        pair = _infer_pair(df, pair)

        builder = DatasetBuilder(df)
        X, y    = builder.build(horizon=self.horizon, rr_ratio=self.rr_ratio)

        if len(X) < 100:
            return {"error": f"Too few rows: {len(X)}. Need at least 100."}

        if mode == "predict":
            return {"type": "prediction", **self.predictor.signal(X, pair=pair)}

        elif mode == "backtest":
            return {"type": "backtest", "results": self.backtester.run(X)}

        elif mode == "full":
            trainer   = ForexEnsembleTrainer(pair=pair)
            acc, prec = trainer.train(X, y, save=True)

            signal   = self.predictor.signal(X, pair=pair)
            backtest = self.backtester.run(X)

            return {
                "type":               "full_analysis",
                "pair":               pair,
                "rows_processed":     len(X),
                "training_accuracy":  round(acc,  4),
                "training_precision": round(prec, 4),
                "prediction":         signal,
                "backtest":           backtest,
                "summary": {
                    "action":           signal["action"],
                    "signal_strength":  signal["signal_strength"],
                    "regime":           signal["regime"],
                    "win_rate":         backtest.get("win_rate", 0),
                    "profit_factor":    backtest.get("profit_factor", 0),
                    "max_drawdown_pct": backtest.get("max_drawdown_pct", 0),
                },
            }

        else:
            raise ValueError(
                f"Unknown mode: '{mode}'. "
                "Use: tune | train | predict | multi_horizon | backtest | full"
            )

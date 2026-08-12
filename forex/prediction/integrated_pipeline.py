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

import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .feature_engineering  import build_features
from .dataset_builder      import DatasetBuilder, get_pair_config
from .predictor            import ForexPredictor
from .backtester           import ForexBacktester
from .xgb_trainer          import ForexEnsembleTrainer, train_with_wfv
from .hyperparameter_tuner import ForexHyperparameterTuner
from .csv_adapter          import adapt_csv

logger = logging.getLogger("forex.prediction.pipeline")

PREDICTION_TIMEFRAME = "H1"
_TRADE_ACTIONS = ("BUY", "SELL")


def _protection_failure(
    component: str,
    code: str,
    reason: str,
    *,
    critical: bool,
    exc: Exception = None,
) -> dict:
    failure = {
        "component": component,
        "code": code,
        "critical": critical,
        "reason": reason,
    }
    if exc is not None:
        failure["error_type"] = type(exc).__name__
        failure["error"] = str(exc)
    return failure


def _valid_mtf_result(mtf) -> bool:
    try:
        score = float(mtf.coherence_score)
        return (
            math.isfinite(score)
            and 0.0 <= score <= 100.0
            and isinstance(mtf.coherent, bool)
            and isinstance(mtf.forced_hold, bool)
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _valid_risk_result(risk, action: str) -> bool:
    if risk is None or getattr(risk, "valid", True) is not True:
        return False
    try:
        values = {
            "entry_price": float(risk.entry_price),
            "stop_loss": float(risk.stop_loss),
            "take_profit": float(risk.take_profit),
            "position_size": float(risk.position_size),
            "rr_ratio": float(risk.rr_ratio),
        }
    except (AttributeError, TypeError, ValueError):
        return False
    if not all(math.isfinite(value) for value in values.values()):
        return False
    if (
        getattr(risk, "decision", action) != action
        or values["entry_price"] <= 0.0
        or values["stop_loss"] <= 0.0
        or values["take_profit"] <= 0.0
        or values["position_size"] <= 0.0
        or values["rr_ratio"] <= 0.0
    ):
        return False
    if action == "BUY":
        return values["stop_loss"] < values["entry_price"] < values["take_profit"]
    return values["take_profit"] < values["entry_price"] < values["stop_loss"]


def _autoresolve_mtf(filepath: str, path_h4: str = None, path_d1: str = None):
    """Si filepath contiene _H1, deriva _H4 y _D1 automáticamente cuando existen."""
    import os
    if not filepath or ("_H1" not in filepath and "_h1" not in filepath):
        return path_h4, path_d1
    if path_h4 is None:
        cand = filepath.replace("_H1", "_H4").replace("_h1", "_h4")
        if cand != filepath and os.path.exists(cand):
            path_h4 = cand
    if path_d1 is None:
        cand = filepath.replace("_H1", "_D1").replace("_h1", "_d1")
        if cand != filepath and os.path.exists(cand):
            path_d1 = cand
    return path_h4, path_d1


def _load(filepath: str, pair: str = None,
          path_h4: str = None, path_d1: str = None) -> pd.DataFrame:
    path_h4, path_d1 = _autoresolve_mtf(filepath, path_h4, path_d1)
    return adapt_csv(filepath, pair=pair, path_h4=path_h4, path_d1=path_d1)


_PAIR_SUFFIXES = ['_TEST','_H1','_H4','_D1','_M15','_M30',
                  '_TEST2','_BACKUP','_NEW','_OLD','_2024','_2025','_2026']

def _infer_pair(df: pd.DataFrame, pair: str = None,
                filepath: str = None) -> str:
    """Infiere el par desde: 1) argumento explícito, 2) columna 'pair', 3) nombre de archivo."""
    if pair:
        return pair
    # 1. Desde columna 'pair' del dataframe
    if "pair" in df.columns:
        val = str(df["pair"].iloc[-1]).upper()
        # Limpiar sufijos comunes (_TEST, _H1, etc.)
        for sfx in _PAIR_SUFFIXES:
            if val.endswith(sfx):
                val = val[:-len(sfx)]
                break
        if val and val != "UNKNOWN":
            return val
    # 2. Desde nombre de archivo
    if filepath:
        import os
        name = os.path.splitext(os.path.basename(filepath))[0].upper()
        for sfx in _PAIR_SUFFIXES:
            if name.endswith(sfx):
                name = name[:-len(sfx)]
                break
        # Verificar que parece un par Forex (4-8 chars alfanuméricas)
        if 4 <= len(name) <= 8 and name.isalnum():
            return name
    return "UNKNOWN"


class ForexIntegratedPipeline:

    def __init__(
        self,
        horizon: int          = None,
        rr_ratio: float       = None,
        min_confidence: float = 0.65,
        min_adx: float        = 22.0,
        *,
        risk_config: dict | None = None,
        risk_config_resolver=None,
    ):
        from .model_storage import ModelStorage
        from .risk_config_resolver import RiskConfigResolver
        self._horizon        = horizon
        self._rr_ratio       = rr_ratio
        self.min_confidence  = min_confidence
        self.min_adx         = min_adx
        self.risk_config     = risk_config
        self._risk_config_override_supplied = risk_config is not None
        self.risk_config_resolver = (
            None
            if self._risk_config_override_supplied
            else risk_config_resolver or RiskConfigResolver.from_environment()
        )
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

    def _resolve_risk_config(self, pair: str) -> dict | None:
        """Return the explicit override or the canonical per-pair resolution."""
        if getattr(self, "_risk_config_override_supplied", False):
            return self.risk_config
        resolver = getattr(self, "risk_config_resolver", None)
        if resolver is None:
            # Compatibility for tests and advanced objects created without
            # running __init__; production instances always have a resolver.
            return getattr(self, "risk_config", None)
        return resolver.resolve(pair).to_engine_config()

    def _dataset_provenance(
        self, filepath: str, df: pd.DataFrame, *, horizon: int | None = None
    ) -> dict:
        configured = getattr(self, "closed_loop_dataset_provenance", None)
        if configured:
            provenance = dict(configured)
        else:
            timestamp = df["timestamp"].iloc[-1] if "timestamp" in df.columns else None
            provenance = {
                "path": str(Path(filepath).resolve()),
                "candle_count": len(df),
                "last_candle_timestamp": (
                    pd.Timestamp(timestamp).isoformat() if timestamp is not None else None
                ),
            }
        if horizon is not None:
            provenance["training_horizon_candles"] = int(horizon)
        return provenance

    def _promote_initial_training(
        self,
        model: object,
        *,
        pair: str,
        filepath: str,
        df: pd.DataFrame,
        feature_names: list[str],
        horizon: int | None = None,
        metadata: dict | None = None,
    ) -> dict:
        from forex.prediction.retrain_manager import RetrainManager

        database = getattr(self, "closed_loop_database", None)
        manager = (
            RetrainManager(database=database, storage=self.storage)
            if database is not None
            else RetrainManager(storage=self.storage)
        )
        return manager.promote_initial_model(
            model,
            pair=pair,
            timeframe=PREDICTION_TIMEFRAME,
            dataset_provenance=self._dataset_provenance(
                filepath, df, horizon=horizon
            ),
            feature_names=feature_names,
            metadata=metadata,
        )

    def _model_identity(self, pair: str) -> str | None:
        """Return only the checksum of the exact symbol alias requested."""
        base_dir = getattr(self.storage, "base_dir", None)
        if base_dir is None or not hasattr(self.storage, "checksum"):
            return None
        clean = "".join(character for character in pair.upper() if character.isalnum())
        latest = Path(base_dir) / f"latest_{clean}.pkl"
        return self.storage.checksum(latest) if latest.is_file() else None

    # ─────────────────────────────────────────────────────────
    # TRAIN — con WFV deslizante + MTF opcional
    # ─────────────────────────────────────────────────────────
    def train(self, filepath: str, pair: str = None,
              path_h4: str = None, path_d1: str = None,
              use_wfv: bool = True, force: bool = False) -> dict:
        df   = _load(filepath, pair=pair, path_h4=path_h4, path_d1=path_d1)
        pair = _infer_pair(df, pair, filepath=filepath)
        df   = build_features(df)

        # ── Roadmap V: Quality Gate (V.5) ───────────────────────────
        try:
            from forex.prediction.roadmap_v_integration import run_quality_gate
            _approved, _qr = run_quality_gate(
                df,
                pair=pair or "?",
                timeframe=PREDICTION_TIMEFRAME,
                verbose=False,
            )
            if not _approved:
                return {
                    "error": f"Quality gate rechazado (score={_qr.global_score:.0f}/100). "
                             f"Críticos: {_qr.critical_count}. {_qr.recommendation}"
                }
        except Exception as exc:
            logger.error(
                "V.5 Quality Gate no pudo verificar %s: %s. Entrenamiento bloqueado.",
                pair,
                exc,
                exc_info=True,
            )
            return {
                "error": "Quality gate no disponible; entrenamiento bloqueado.",
                "safeguard_status": "blocked",
                "blocked_by": ["quality_gate"],
                "safeguard_failures": [
                    _protection_failure(
                        "quality_gate",
                        "quality_gate_failed",
                        "V.5 Quality Gate no pudo autorizar el entrenamiento.",
                        critical=True,
                        exc=exc,
                    )
                ],
            }

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
            trainer, wfv_r, acc, prec = train_with_wfv(
                X, y, pair=pair, save=False, force=force
            )
            eligible = bool(force or wfv_r.get("wfv_passed", False))
            deployed = bool(
                eligible
                and trainer.model is not None
                and getattr(trainer.model, "sufficient", False)
            )
            if deployed:
                promotion = self._promote_initial_training(
                    trainer.model,
                    pair=pair,
                    filepath=filepath,
                    df=df,
                    feature_names=list(X.columns),
                    horizon=horizon,
                    metadata={"accuracy": acc, "precision": prec, "wfv": wfv_r},
                )
                deployed = promotion.get("status") == "PROMOTED"
            wfv_r["model_deployed"] = deployed
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
                "model":       "guardado" if deployed else "NO guardado",
            }
        else:
            trainer   = ForexEnsembleTrainer(pair=pair)
            acc, prec = trainer.train(X, y, save=False)
            deployed = bool(
                trainer.model is not None
                and getattr(trainer.model, "sufficient", False)
            )
            if deployed:
                promotion = self._promote_initial_training(
                    trainer.model,
                    pair=pair,
                    filepath=filepath,
                    df=df,
                    feature_names=list(X.columns),
                    horizon=horizon,
                    metadata={"accuracy": acc, "precision": prec},
                )
                deployed = promotion.get("status") == "PROMOTED"
            self.predictor.invalidate_cache(pair=pair)
            return {
                "type":        "training_complete",
                "pair":        pair,
                "rows":        len(X),
                "features":    len(X.columns),
                "accuracy":    round(acc,  4),
                "precision":   round(prec, 4),
                "model_valid": getattr(trainer.model, "sufficient", False) if trainer.model else False,
                "model":       "guardado" if deployed else "NO guardado",
            }

    # ─────────────────────────────────────────────────────────
    # PREDICT — última vela real + MTF de autorización
    # ─────────────────────────────────────────────────────────
    def predict(self, filepath: str, pair: str = None,
                path_h4: str = None, path_d1: str = None) -> dict:
        """Return an H1 prediction whose ``action`` is the final ASTRA decision.

        The primary dataset is H1. ``path_h4`` and ``path_d1`` remain context,
        not alternative predictions; both must be valid before a directional
        H1 signal can become executable.

        ``signal`` is a compatibility alias for ``action`` and ``raw_action``
        retains the predictor decision for diagnostics only.
        """
        path_h4, path_d1 = _autoresolve_mtf(filepath, path_h4, path_d1)
        df   = _load(filepath, pair=pair, path_h4=path_h4, path_d1=path_d1)
        pair = _infer_pair(df, pair, filepath=filepath)
        df   = build_features(df)

        # Cargar feature_names guardadas junto al modelo (evita mismatch)
        train_columns = None
        try:
            _, train_columns = self.storage.load_model_with_features(pair=pair)
        except Exception as exc:
            logger.warning("No se pudieron cargar feature_names de %s: %s", pair, exc)
            train_columns = None

        builder = DatasetBuilder(df)
        X_pred  = builder.predict_features(n_rows=1, train_columns=train_columns)

        if len(X_pred) == 0:
            return {"error": "Sin filas válidas tras feature engineering."}

        signal = self.predictor.signal(X_pred, pair=pair)
        safeguard_failures: list[dict] = []
        protection_errors: list[dict] = []

        # ── VI.5.D: Candlestick pattern boost ────────────────────────
        try:
            from forex.prediction.candlestick_patterns import detect_patterns
            cs = detect_patterns(df.tail(50))
            signal["candlestick_patterns"] = cs.get("pattern_names", [])
            signal["candlestick_bias"]     = cs.get("bias", "neutral")
        except Exception as exc:
            failure = _protection_failure(
                "candlestick_patterns",
                "candlestick_patterns_failed",
                "Los patrones de velas informativos no pudieron evaluarse.",
                critical=False,
                exc=exc,
            )
            protection_errors.append(failure)
            logger.warning("Candlestick patterns no evaluados: %s", exc, exc_info=True)

        raw_action = signal.get("action") or signal.get("signal") or "HOLD"
        _sig  = raw_action
        _conf = float(signal.get("confidence", 0.65))
        _, _rr = self._pair_params(pair)

        # ── Roadmap V: contexto completo (V.2/V.3/V.4/V.8) ──────────
        # Antes el Decision Engine se llamaba sólo con signal+confidence, así
        # que sus prioridades 1..5 nunca se activaban. Ahora recibe todo.
        ctx = None
        try:
            from forex.prediction.prediction_context import build_context
            ctx = build_context(
                df,
                pair=pair,
                timeframe=PREDICTION_TIMEFRAME,
                signal=_sig,
                model_confidence=_conf,
                ensemble_predictions=signal.get("ensemble_predictions"),
                path_h4=path_h4,
                path_d1=path_d1,
                rr_ratio=_rr,
                risk_config=self._resolve_risk_config(pair),
            )
        except Exception as exc:
            failure = _protection_failure(
                "prediction_context",
                "prediction_context_failed",
                "No se pudo construir el contexto obligatorio Roadmap V.",
                critical=True,
                exc=exc,
            )
            protection_errors.append(failure)
            if raw_action in _TRADE_ACTIONS:
                safeguard_failures.append(failure)
            logger.warning(
                "No se pudo construir el contexto Roadmap V: %s", exc, exc_info=True
            )

        if ctx is not None:
            for failure in getattr(ctx, "protection_errors", []) or []:
                if not isinstance(failure, dict):
                    continue
                protection_errors.append(failure)
                if failure.get("critical") and raw_action in _TRADE_ACTIONS:
                    safeguard_failures.append(failure)

        if raw_action in _TRADE_ACTIONS and ctx is not None:
            mtf = getattr(ctx, "mtf", None)
            if not _valid_mtf_result(mtf) and not any(
                failure.get("component") == "mtf" for failure in safeguard_failures
            ):
                failure = _protection_failure(
                    "mtf",
                    "mtf_context_invalid",
                    "El contexto MTF obligatorio está ausente o es inválido.",
                    critical=True,
                )
                safeguard_failures.append(failure)
                protection_errors.append(failure)

            risk = getattr(ctx, "risk", None)
            if not _valid_risk_result(risk, raw_action) and not any(
                failure.get("component") == "risk_engine"
                for failure in safeguard_failures
            ):
                failure = _protection_failure(
                    "risk_engine",
                    "risk_context_invalid",
                    "La protección de riesgo requerida está ausente o es inválida.",
                    critical=True,
                )
                safeguard_failures.append(failure)
                protection_errors.append(failure)

        # ── Circuit Breaker guard ─────────────────────────────────────
        cb_active = bool(getattr(ctx, "circuit_breaker_active", False))
        if cb_active:
            cb_state = getattr(ctx, "circuit_breaker_state", None) or {"open": False}
            signal["circuit_breaker"] = cb_state
            failure = _protection_failure(
                "circuit_breaker",
                "circuit_breaker_active",
                str(cb_state.get("reason") or "Circuit Breaker activo; operación bloqueada."),
                critical=True,
            )
            if raw_action in _TRADE_ACTIONS:
                safeguard_failures.append(failure)

        # ── Roadmap V: Decision Engine (V.1) con contexto completo ───
        if not safeguard_failures:
            try:
                from forex.prediction.roadmap_v_integration import run_decision_engine
                _dec = run_decision_engine(
                    ensemble_signal=_sig,
                    model_confidence=_conf,
                    ensemble_predictions=signal.get("ensemble_predictions"),
                    regime=getattr(ctx, "regime", None),
                    mtf=getattr(ctx, "mtf", None),
                    circuit_breaker_active=cb_active,
                    news_active=bool(getattr(ctx, "news_active", False)),
                    news_sentiment=str(getattr(ctx, "news_sentiment", "")),
                    volatility_level=str(getattr(ctx, "volatility_level", "normal")),
                    atr_percentile=float(getattr(ctx, "atr_percentile", 50.0)),
                    model_win_rate=getattr(ctx, "model_win_rate", None),
                    model_recent_predictions=int(getattr(ctx, "model_recent_predictions", 0)),
                    risk_info=(
                        ctx.risk.to_dict() if getattr(ctx, "risk", None) is not None else None
                    ),
                    pair=pair,
                    timeframe=PREDICTION_TIMEFRAME,
                    verbose=False,
                )
                decision = getattr(_dec, "decision", None)
                if decision not in ("BUY", "SELL", "HOLD", "NO_OPERAR"):
                    raise ValueError(f"Decision Engine devolvió decisión inválida: {decision!r}")
                signal["roadmap_v_decision"]     = decision
                signal["roadmap_v_explanation"]  = _dec.explanation
                signal["roadmap_v_risk_level"]   = getattr(_dec, "risk_level", "medium")
                signal["roadmap_v_factors_for"]     = getattr(_dec, "factors_for", [])
                signal["roadmap_v_factors_against"] = getattr(_dec, "factors_against", [])
                signal["reliability_score"]      = round(float(getattr(_dec, "reliability_score", 0.0)), 2)
                signal["quality_tier"]           = getattr(_dec, "quality_tier", "hold")

                # El Decision Engine es la autoridad final: puede vetar la señal.
                if decision in ("HOLD", "NO_OPERAR") and _sig in _TRADE_ACTIONS:
                    logger.warning(
                        "Decision Engine vetó %s en %s: %s", _sig, pair, _dec.explanation
                    )
                    signal["ensemble_signal_raw"] = _sig
                    safeguard_failures.append(
                        _protection_failure(
                            "decision_engine",
                            "decision_engine_veto",
                            str(_dec.explanation or "Decision Engine vetó la operación."),
                            critical=True,
                        )
                    )
                _sig = decision
            except Exception as exc:
                failure = _protection_failure(
                    "decision_engine",
                    "decision_engine_failed",
                    "V.1 Decision Engine no pudo autorizar la operación.",
                    critical=True,
                    exc=exc,
                )
                protection_errors.append(failure)
                if raw_action in _TRADE_ACTIONS:
                    safeguard_failures.append(failure)
                logger.warning("V.1 Decision Engine no ejecutado: %s", exc, exc_info=True)

        if (
            raw_action in _TRADE_ACTIONS
            and safeguard_failures
            and _sig in _TRADE_ACTIONS
        ):
            _sig = "HOLD"

        if raw_action not in _TRADE_ACTIONS and _sig in _TRADE_ACTIONS:
            failure = _protection_failure(
                "decision_engine",
                "decision_engine_unsafe_escalation",
                f"Decision Engine intentó convertir {raw_action} en {_sig}.",
                critical=True,
            )
            safeguard_failures.append(failure)
            protection_errors.append(failure)
            _sig = "HOLD"

        if _sig in _TRADE_ACTIONS and not _valid_risk_result(
            getattr(ctx, "risk", None), _sig
        ):
            failure = _protection_failure(
                "risk_engine",
                "risk_final_action_invalid",
                "El riesgo calculado no corresponde a la acción final.",
                critical=True,
            )
            safeguard_failures.append(failure)
            protection_errors.append(failure)
            _sig = "HOLD"

        # Canonical A-03 contract: action is the only executable decision.
        # signal remains a compatible alias; the predictor output is diagnostic.
        signal["raw_action"] = raw_action
        signal["action"] = _sig
        signal["signal"] = _sig

        if ctx is not None:
            try:
                signal["roadmap_v_context"] = ctx.to_dict()
            except Exception as exc:
                failure = _protection_failure(
                    "prediction_context",
                    "prediction_context_serialization_failed",
                    "El contexto no pudo serializarse para diagnóstico.",
                    critical=False,
                    exc=exc,
                )
                protection_errors.append(failure)
                logger.warning("No se pudo serializar PredictionContext: %s", exc, exc_info=True)
            if getattr(ctx, "risk", None) is not None and _sig in ("BUY", "SELL"):
                _r = ctx.risk
                signal["stop_loss"]     = _r.stop_loss
                signal["take_profit"]   = _r.take_profit
                signal["position_size"] = _r.position_size
                signal["rr_ratio"]      = _r.rr_ratio

        # ── V.14: persist canonical prediction evidence ─────────────
        try:
            from forex.prediction.outcome_tracker import OutcomeTracker
            if _sig in ("BUY", "SELL"):
                _price = float(df["close"].iloc[-1])
                candle_timestamp = (
                    df["timestamp"].iloc[-1]
                    if "timestamp" in df.columns
                    else None
                )
                candle_identity = None
                if candle_timestamp is not None:
                    candle_identity = pd.Timestamp(candle_timestamp)
                    if candle_identity.tzinfo is None:
                        candle_identity = candle_identity.tz_localize("UTC")
                    else:
                        candle_identity = candle_identity.tz_convert("UTC")
                    candle_identity = candle_identity.isoformat()
                horizon, _ = self._pair_params(pair)
                model_identity = self._model_identity(pair)
                tracker_database = getattr(self, "closed_loop_database", None)
                tracker = (
                    OutcomeTracker(database=tracker_database)
                    if tracker_database is not None
                    else OutcomeTracker()
                )
                provenance = getattr(
                    self,
                    "closed_loop_dataset_provenance",
                    {
                        "path": str(filepath),
                        "last_candle_timestamp": candle_identity,
                    },
                )
                prediction_id = tracker.record_prediction(
                    pair=pair, timeframe=PREDICTION_TIMEFRAME, signal=_sig,
                    entry_price=_price,
                    reliability_score=float(
                        signal.get("reliability_score", _conf * 100.0)
                    ),
                    candle_timestamp=candle_identity,
                    raw_action=raw_action,
                    horizon_candles=horizon,
                    model_identity=model_identity,
                    dataset_provenance=provenance,
                )
                if prediction_id in (None, "", -1):
                    raise RuntimeError("Outcome Tracker returned an invalid prediction identity")
                if isinstance(prediction_id, str):
                    signal["prediction_id"] = prediction_id
                signal["candle_timestamp"] = candle_identity
                signal["horizon_candles"] = horizon
                signal["model_identity"] = model_identity
        except Exception as exc:
            failure = _protection_failure(
                "outcome_tracker",
                "outcome_tracker_record_failed",
                "Outcome Tracker no pudo registrar la predicción autorizada.",
                critical=True,
                exc=exc,
            )
            protection_errors.append(failure)
            if _sig in _TRADE_ACTIONS:
                safeguard_failures.append(failure)
                _sig = "HOLD"
                signal["action"] = _sig
                signal["signal"] = _sig
            logger.warning(
                "OutcomeTracker no registró la predicción: %s", exc, exc_info=True
            )

        signal["safeguard_status"] = (
            "blocked" if safeguard_failures else "degraded" if protection_errors else "passed"
        )
        signal["safeguard_failures"] = safeguard_failures
        signal["blocked_by"] = list(dict.fromkeys(
            failure["component"] for failure in safeguard_failures
        ))
        signal["protection_errors"] = protection_errors

        return {"type": "prediction", "rows_processed": len(df), **signal}

    # ─────────────────────────────────────────────────────────
    # MULTI-HORIZON
    # ─────────────────────────────────────────────────────────
    def predict_multi_horizon(self, filepath: str, pair: str = None,
                               path_h4: str = None, path_d1: str = None) -> dict:
        df   = _load(filepath, pair=pair, path_h4=path_h4, path_d1=path_d1)
        pair = _infer_pair(df, pair, filepath=filepath)
        df   = build_features(df)

        storage = self.storage

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
                    self._promote_initial_training(
                        trainer.model,
                        pair=f"{pair}_h{h}",
                        filepath=filepath,
                        df=df,
                        feature_names=list(X.columns),
                        horizon=h,
                        metadata={"model_name": model_name},
                    )
                model = trainer.model
            else:
                model = storage.load_model(pair=f"{pair}_h{h}")

            if model is None:
                continue

            # Cargar feature_names del modelo guardado (evita mismatch)
            train_columns = None
            try:
                _, train_columns = storage.load_model_with_features(pair=f"{pair}_h{h}")
            except Exception:
                train_columns = None

            X_pred = builder.predict_features(n_rows=1, train_columns=train_columns)
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
        pair = _infer_pair(df, pair, filepath=filepath)
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

        trainer, wfv_r, acc, prec = train_with_wfv(X, y, pair=pair, save=False)
        deployed = bool(
            wfv_r.get("wfv_passed", False)
            and trainer.model is not None
            and getattr(trainer.model, "sufficient", False)
        )
        if deployed:
            promotion = self._promote_initial_training(
                trainer.model,
                pair=pair,
                filepath=filepath,
                df=df,
                feature_names=list(X.columns),
                horizon=hz,
                metadata={
                    "accuracy": acc,
                    "precision": prec,
                    "wfv": wfv_r,
                    "tuning_trials": n_trials,
                },
            )
            deployed = promotion.get("status") == "PROMOTED"
        wfv_r["model_deployed"] = deployed
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
        pair = _infer_pair(df, pair, filepath=filepath)
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

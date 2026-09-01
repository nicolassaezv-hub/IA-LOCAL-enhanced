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
from .dataset_builder      import DatasetBuilder, get_pair_config, require_ml_config
from .predictor            import ForexPredictor
from .h1_directional       import H1_MODEL_CONTRACT
from .backtester           import ForexBacktester
from .xgb_trainer          import (
    ForexEnsembleTrainer,
    train_with_wfv,
)
from infra.db.database import require_active_symbol
from .hyperparameter_tuner import ForexHyperparameterTuner
from .csv_adapter          import adapt_csv

logger = logging.getLogger("forex.prediction.pipeline")

PREDICTION_TIMEFRAME = "H1"
_TRADE_ACTIONS = ("BUY", "SELL")


def _quality_gate_metadata(approved: bool, report) -> dict:
    return {
        "passed": approved is True,
        "approved": getattr(report, "approved", approved) is True,
        "score": float(getattr(report, "global_score", 0.0)),
        "critical_count": int(getattr(report, "critical_count", 0)),
        "warning_count": int(getattr(report, "warning_count", 0)),
    }


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
    if not filepath:
        return path_h4, path_d1
    source = Path(filepath)
    filename = source.name
    if "_H1" not in filename and "_h1" not in filename:
        return path_h4, path_d1
    if path_h4 is None:
        candidate = source.with_name(
            filename.replace("_H1", "_H4").replace("_h1", "_h4")
        )
        if candidate != source and candidate.exists():
            path_h4 = str(candidate)
    if path_d1 is None:
        candidate = source.with_name(
            filename.replace("_H1", "_D1").replace("_h1", "_d1")
        )
        if candidate != source and candidate.exists():
            path_d1 = str(candidate)
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

    @staticmethod
    def _candidate_metadata(
        *,
        symbol: str,
        timeframe: str,
        promotion_type: str,
        dataset_provenance: dict,
        quality_gate: dict,
        trainer,
        wfv_result: dict,
        accuracy: float,
        precision: float,
        extra: dict | None = None,
    ) -> dict:
        from forex.prediction.retrain_manager import RetrainManager
        from forex.prediction.xgb_trainer import wfv_quality_passed

        return {
            **(extra or {}),
            "symbol": symbol,
            "timeframe": timeframe,
            "promotion_type": promotion_type,
            "dataset_provenance_sha256": (
                RetrainManager.dataset_provenance_sha256(dataset_provenance)
            ),
            "quality_gate": quality_gate,
            "accuracy": accuracy,
            "precision": precision,
            "wfv": wfv_result,
            "eligibility": {
                "quality_gate_passed": quality_gate.get("passed") is True,
                "calibration_passed": bool(
                    getattr(trainer, "calibration_sufficient", False)
                ),
                "validation_passed": bool(
                    getattr(trainer, "validation_sufficient", False)
                ),
                "validation_precision": float(precision),
                "wfv_passed": bool(wfv_quality_passed(wfv_result)),
                "model_valid": bool(getattr(trainer, "model_valid", False)),
            },
        }

    def _train_quality_candidate(
        self,
        df: pd.DataFrame,
        *,
        symbol: str,
        horizon: int,
        rr_ratio: float,
        dataset_provenance: dict,
        promotion_type: str,
        tuned_params_override: dict | None = None,
        hyperparameter_provenance: dict | None = None,
    ) -> dict:
        require_ml_config(symbol)
        """Build one candidate under the complete, non-bypassable gate order."""
        from forex.prediction.roadmap_v_integration import run_quality_gate

        if tuned_params_override is not None:
            from .hyperparameter_tuner import canonical_params_sha256

            if not isinstance(hyperparameter_provenance, dict):
                raise ValueError("HYPERPARAMETER_PROVENANCE_REQUIRED")
            if hyperparameter_provenance.get("mode") != "nested_wfv_tuning":
                raise ValueError("HYPERPARAMETER_PROVENANCE_MODE_INVALID")
            if hyperparameter_provenance.get("pair") != symbol:
                raise ValueError("HYPERPARAMETER_PROVENANCE_PAIR_MISMATCH")
            if hyperparameter_provenance.get(
                "snapshot_sha256"
            ) != dataset_provenance.get("snapshot_sha256"):
                raise ValueError("HYPERPARAMETER_PROVENANCE_SNAPSHOT_MISMATCH")
            if hyperparameter_provenance.get(
                "params_sha256"
            ) != canonical_params_sha256(tuned_params_override):
                raise ValueError("HYPERPARAMETER_PROVENANCE_PARAMS_MISMATCH")
            inner_metrics = hyperparameter_provenance.get("inner_metrics")
            if not isinstance(inner_metrics, dict) or inner_metrics.get(
                "inner_wfv_passed"
            ) is not True:
                raise ValueError("HYPERPARAMETER_INNER_WFV_REQUIRED")
        elif hyperparameter_provenance is not None:
            raise ValueError("HYPERPARAMETER_OVERRIDE_REQUIRED")

        approved, quality_report = run_quality_gate(
            df,
            pair=symbol,
            timeframe=PREDICTION_TIMEFRAME,
            verbose=False,
        )
        quality = _quality_gate_metadata(approved, quality_report)
        if not approved:
            raise ValueError(
                f"QUALITY_GATE: dataset rejected (score={quality['score']})"
            )
        builder = DatasetBuilder(df)
        X, y = builder.build(horizon=horizon, rr_ratio=rr_ratio)
        if len(X) < 300:
            raise ValueError("QUALITY_GATE: WFV requires at least 300 rows")
        train_kwargs = {
            "pair": symbol,
            "save": False,
            "force": False,
        }
        if tuned_params_override is not None:
            train_kwargs["tuned_params_override"] = tuned_params_override
        trainer, wfv_result, accuracy, precision = train_with_wfv(
            X,
            y,
            **train_kwargs,
        )
        if trainer.model is None:
            raise ValueError("QUALITY_GATE: MODEL_NOT_TRAINED")
        metadata = self._candidate_metadata(
            symbol=symbol,
            timeframe=PREDICTION_TIMEFRAME,
            promotion_type=promotion_type,
            dataset_provenance=dataset_provenance,
            quality_gate=quality,
            trainer=trainer,
            wfv_result=wfv_result,
            accuracy=accuracy,
            precision=precision,
            extra=(
                {"hyperparameter_provenance": hyperparameter_provenance}
                if hyperparameter_provenance is not None
                else None
            ),
        )
        return {
            "model": trainer.model,
            "feature_names": list(X.columns),
            "metadata": metadata,
        }

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
        provenance = self._dataset_provenance(filepath, df, horizon=horizon)
        complete_metadata = {
            **(metadata or {}),
            "symbol": pair,
            "timeframe": PREDICTION_TIMEFRAME,
            "promotion_type": "initial_training",
            "dataset_provenance_sha256": (
                RetrainManager.dataset_provenance_sha256(provenance)
            ),
        }
        return manager.promote_initial_model(
            model,
            pair=pair,
            timeframe=PREDICTION_TIMEFRAME,
            dataset_provenance=provenance,
            feature_names=feature_names,
            metadata=complete_metadata,
        )

    def bootstrap_revalidate(
        self,
        filepath: str,
        *,
        pair: str,
        path_h4: str = None,
        path_d1: str = None,
        manager=None,
    ) -> dict:
        """Retrain a provable legacy initial alias under today's full contract."""
        from forex.prediction.retrain_manager import RetrainManager

        path_h4, path_d1 = _autoresolve_mtf(filepath, path_h4, path_d1)
        df = _load(filepath, pair=pair, path_h4=path_h4, path_d1=path_d1)
        symbol = _infer_pair(df, pair, filepath=filepath)
        df = build_features(df)
        horizon, rr_ratio = self._pair_params(symbol)
        provenance = self._dataset_provenance(filepath, df, horizon=horizon)
        provenance["timeframe"] = PREDICTION_TIMEFRAME
        provenance["mtf_context"] = {
            "H4": str(Path(path_h4).resolve()) if path_h4 else None,
            "D1": str(Path(path_d1).resolve()) if path_d1 else None,
        }

        if manager is None:
            database = getattr(self, "closed_loop_database", None)
            manager = (
                RetrainManager(database=database, storage=self.storage)
                if database is not None
                else RetrainManager(storage=self.storage)
            )
        run = manager.ensure_bootstrap_revalidation(
            symbol,
            timeframe=PREDICTION_TIMEFRAME,
            dataset_provenance=provenance,
        )
        if run is None:
            return {
                "model_deployed": False,
                "error": "Alias is not eligible for bootstrap revalidation",
                "eligibility": manager.audit_pair_model(symbol),
            }

        def train_candidate(_symbol: str, _timeframe: str, _context: dict) -> dict:
            return self._train_quality_candidate(
                df,
                symbol=symbol,
                horizon=horizon,
                rr_ratio=rr_ratio,
                dataset_provenance=provenance,
                promotion_type="bootstrap_revalidation",
            )

        result = manager.execute_retrain(
            run["run_id"],
            train_candidate,
            validator=lambda model: getattr(model, "sufficient", True) is True,
        )
        audit = manager.audit_pair_model(symbol)
        error = result.get("error") or ""
        return {
            "run_id": result["run_id"],
            "retrain_status": result["status"],
            "trigger": result["trigger"],
            "model_deployed": bool(
                result["status"] == "PROMOTED" and audit.get("eligible")
            ),
            "quality_gate_failed": "QUALITY_GATE:" in error,
            "error": error,
            "eligibility": audit,
        }

    def manual_quality_retrain(
        self,
        *,
        pair: str,
        request_id: str,
        timeframe: str = PREDICTION_TIMEFRAME,
        manager=None,
    ) -> dict:
        """Run one deliberate quality retrain against an immutable MTF snapshot."""
        from forex.prediction.retrain_manager import RetrainManager

        database = getattr(self, "closed_loop_database", None)
        if manager is None:
            manager = (
                RetrainManager(database=database, storage=self.storage)
                if database is not None
                else RetrainManager(storage=self.storage)
            )
        run = manager.ensure_manual_quality_retrain(
            pair,
            request_id=request_id,
            timeframe=timeframe,
        )

        def train_candidate(symbol: str, _timeframe: str, context: dict) -> dict:
            provenance = context["dataset_provenance"]
            snapshot = provenance["snapshot"]
            manager.validate_training_snapshot(snapshot)
            datasets = snapshot["datasets"]
            frame = _load(
                datasets["H1"]["canonical_path"],
                pair=symbol,
                path_h4=datasets["H4"]["canonical_path"],
                path_d1=datasets["D1"]["canonical_path"],
            )
            manager.validate_training_snapshot(snapshot)
            frame = build_features(frame)
            horizon, rr_ratio = self._pair_params(symbol)
            return self._train_quality_candidate(
                frame,
                symbol=symbol,
                horizon=horizon,
                rr_ratio=rr_ratio,
                dataset_provenance=provenance,
                promotion_type="manual_quality_retrain",
            )

        result = manager.execute_retrain(
            run["run_id"],
            train_candidate,
            validator=lambda model: getattr(model, "sufficient", True) is True,
        )
        audit = manager.audit_pair_model(pair)
        error = result.get("error") or ""
        failed_gate = None
        for gate in (
            "WFV_GATE",
            "CALIBRATION_GATE",
            "VALIDATION_GATE",
            "MODEL_VALID_GATE",
            "PRECISION_EVIDENCE_MISSING",
            "PRECISION_EVIDENCE_MISMATCH",
            "DATASET_PROVENANCE_MISMATCH",
            "DATASET_SNAPSHOT_CONFLICT",
            "SOURCE_ALIAS_CONFLICT",
            "QUALITY_GATE",
        ):
            if gate in error:
                failed_gate = gate
                break
        return {
            "ok": bool(result["status"] == "PROMOTED" and audit.get("eligible")),
            "run_id": result["run_id"],
            "request_id": result.get("request_id") or request_id,
            "symbol": result["symbol"],
            "trigger": result["trigger"],
            "status": result["status"],
            "model_deployed": bool(
                result["status"] == "PROMOTED" and audit.get("eligible")
            ),
            "source_sha256": result.get("source_model_sha256"),
            "candidate_path": result.get("artifact_path"),
            "candidate_sha256": result.get("artifact_sha256"),
            "eligibility": audit,
            "failed_gate": failed_gate,
            "error": error,
        }

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
        require_ml_config(pair)
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
            quality_gate = _quality_gate_metadata(_approved, _qr)
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
            eligible = bool(
                not wfv_r.get("error") and wfv_r.get("wfv_passed", False)
            )
            deployed = bool(
                eligible
                and trainer.model is not None
                and getattr(trainer, "model_valid", False)
            )
            if deployed:
                promotion = self._promote_initial_training(
                    trainer.model,
                    pair=pair,
                    filepath=filepath,
                    df=df,
                    feature_names=list(X.columns),
                    horizon=horizon,
                    metadata={
                        "quality_gate": quality_gate,
                        "accuracy": acc,
                        "precision": prec,
                        "wfv": wfv_r,
                        "eligibility": {
                            "quality_gate_passed": True,
                            "calibration_passed": bool(
                                getattr(trainer, "calibration_sufficient", False)
                            ),
                            "validation_passed": bool(
                                getattr(trainer, "validation_sufficient", False)
                            ),
                            "validation_precision": float(prec),
                            "wfv_passed": True,
                            "model_valid": bool(
                                getattr(trainer, "model_valid", False)
                            ),
                        },
                    },
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
                "model_valid": bool(getattr(trainer, "model_valid", False)),
                "model":       "guardado" if deployed else "NO guardado",
                "model_deployed": deployed,
            }
        else:
            trainer   = ForexEnsembleTrainer(pair=pair)
            acc, prec = trainer.train(X, y, save=False)
            # A run without WFV is diagnostic only and cannot publish a
            # pair-specific production alias.
            deployed = False
            self.predictor.invalidate_cache(pair=pair)
            return {
                "type":        "training_complete",
                "pair":        pair,
                "rows":        len(X),
                "features":    len(X.columns),
                "accuracy":    round(acc,  4),
                "precision":   round(prec, 4),
                "model_valid": bool(getattr(trainer, "model_valid", False)),
                "model":       "guardado" if deployed else "NO guardado",
                "model_deployed": deployed,
                "quality_gate": "WFV_REQUIRED",
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
        require_ml_config(pair)
        require_active_symbol(
            pair,
            database=getattr(self, "closed_loop_database", None),
        )
        df   = build_features(df)

        # Cargar feature_names guardadas junto al modelo (evita mismatch)
        loaded_model = None
        train_columns = None
        try:
            loaded_model, train_columns = self.storage.load_model_with_features(pair=pair)
        except Exception as exc:
            logger.warning("No se pudieron cargar feature_names de %s: %s", pair, exc)
            train_columns = None

        builder = DatasetBuilder(df)
        if getattr(loaded_model, "model_contract", None) == H1_MODEL_CONTRACT:
            X_pred = self.predictor.prepare_features(df, pair=pair, n_rows=1)
        else:
            X_pred = builder.predict_features(n_rows=1, train_columns=train_columns)

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
                    model_contract=signal.get("model_contract"),
                    target_profile=signal.get("target_profile"),
                    target_definition_version=signal.get(
                        "target_definition_version"
                    ),
                    feature_profile=signal.get("feature_profile"),
                    score_type=signal.get("score_type"),
                    direction_score=signal.get("direction_score"),
                    decision_percentile=signal.get("decision_percentile"),
                    decision_policy=signal.get("decision_policy"),
                    confidence_semantics=signal.get("confidence_semantics"),
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

        try:
            from forex.prediction.roadmap_v_integration import run_quality_gate

            multi_approved, multi_report = run_quality_gate(
                df,
                pair=pair,
                timeframe=PREDICTION_TIMEFRAME,
                verbose=False,
            )
            multi_quality_gate = _quality_gate_metadata(
                multi_approved, multi_report
            )
        except Exception as exc:
            return {"error": f"Quality gate no disponible: {exc}"}
        if not multi_approved:
            return {"error": "Quality gate rechazado para multi-horizon"}

        votes       = []
        horizons    = [5, 10, 20]
        _, rr_ratio = self._pair_params(pair)
        audit_manager = None

        for h in horizons:
            builder = DatasetBuilder(df)
            X, y    = builder.build(horizon=h, rr_ratio=rr_ratio)
            if len(X) < 100:
                continue

            model_exists = storage.latest_exists(pair=f"{pair}_h{h}")
            model_name   = f"ensemble_{pair.replace('/','')}_h{h}"

            if not model_exists:
                print(f"[MULTI] Entrenando h={h}...")
                if len(X) >= 300:
                    trainer, horizon_wfv, horizon_acc, horizon_prec = train_with_wfv(
                        X, y, pair=f"{pair}_h{h}", save=False
                    )
                else:
                    trainer = ForexEnsembleTrainer(pair=pair)
                    horizon_acc, horizon_prec = trainer.train(X, y, save=False)
                    horizon_wfv = {"error": "WFV requires at least 300 rows"}
                from .xgb_trainer import wfv_quality_passed
                horizon_eligible = bool(
                    wfv_quality_passed(horizon_wfv)
                    and getattr(trainer, "model_valid", False)
                    and getattr(trainer, "calibration_sufficient", False)
                    and getattr(trainer, "validation_sufficient", False)
                )
                if trainer.model is None or not horizon_eligible:
                    continue
                try:
                    promotion = self._promote_initial_training(
                        trainer.model,
                        pair=f"{pair}_h{h}",
                        filepath=filepath,
                        df=df,
                        feature_names=list(X.columns),
                        horizon=h,
                        metadata={
                            "quality_gate": multi_quality_gate,
                            "model_name": model_name,
                            "accuracy": horizon_acc,
                            "precision": horizon_prec,
                            "wfv": horizon_wfv,
                            "eligibility": {
                                "quality_gate_passed": True,
                                "calibration_passed": bool(
                                    getattr(trainer, "calibration_sufficient", False)
                                ),
                                "validation_passed": bool(
                                    getattr(trainer, "validation_sufficient", False)
                                ),
                                "validation_precision": float(horizon_prec),
                                "wfv_passed": True,
                                "model_valid": bool(
                                    getattr(trainer, "model_valid", False)
                                ),
                            },
                        },
                    )
                except Exception as exc:
                    logger.warning(
                        "Multi-horizon promotion failed for %s h=%s: %s",
                        pair,
                        h,
                        exc,
                    )
                    continue
                if promotion.get("status") != "PROMOTED":
                    continue
                try:
                    model = storage.load_model(pair=f"{pair}_h{h}")
                except Exception as exc:
                    logger.warning(
                        "Promoted multi-horizon alias could not be loaded for %s h=%s: %s",
                        pair,
                        h,
                        exc,
                    )
                    continue
            else:
                if audit_manager is None:
                    from forex.prediction.retrain_manager import RetrainManager

                    database = getattr(self, "closed_loop_database", None)
                    audit_manager = (
                        RetrainManager(database=database, storage=storage)
                        if database is not None
                        else RetrainManager(storage=storage)
                    )
                if not audit_manager.audit_pair_model(f"{pair}_h{h}")["eligible"]:
                    continue
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
        # Tuning is diagnostic/parameter generation only.  Production aliases
        # are published exclusively by train() or explicit retrain contracts.
        deployed = False
        wfv_r["model_deployed"] = deployed
        self.predictor.invalidate_cache(pair=pair)

        signal = {}
        if self.storage.latest_exists(pair=pair):
            X_pred = DatasetBuilder(df).predict_features(n_rows=1)
            if len(X_pred) > 0:
                signal = self.predictor.signal(X_pred, pair=pair)

        return {
            "type":      "tune_complete",
            "pair":      pair,
            "rows":      len(X),
            "n_trials":  n_trials,
            "accuracy":  round(acc,  4),
            "precision": round(prec, 4),
            "wfv":       wfv_r,
            "model_deployed": False,
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

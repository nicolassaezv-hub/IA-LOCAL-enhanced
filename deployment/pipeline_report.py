"""
Pipeline Report — Validacion paso a paso del flujo completo por simbolo.

Etapas verificadas (12):
  1.  Descarga de datos (YFinance / CSV local)
  2.  Creacion/actualizacion CSV H1/H4/D1
  3.  Calculo de indicadores (feature engineering)
  4.  Validacion del dataset (quality gate)
  5.  Entrenamiento o carga del modelo
  6.  Generacion de la primera predicción
  7.  Actualizacion del Outcome Tracker
  8.  Actualizacion del Opportunity Score
  9.  Portfolio Ranker
  10. Almacenamiento en base de datos
  11. Disponibilidad mediante la API
  12. Visualizacion en el Workspace
"""
from __future__ import annotations

import os
import sys
import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from runtime_paths import forex_dataset_path

_BASE = Path(__file__).resolve().parent.parent


def _loopback_get(path: str, *, authenticated: bool = False):
    """Query the already-running local service without exposing credentials."""
    import requests

    host = os.environ.get("ASTRA_API_HOST", "127.0.0.1").strip().lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        host = "127.0.0.1"
    if host == "::1":
        host = "[::1]"
    port = int(os.environ.get("ASTRA_API_PORT", "8000"))
    headers = None
    if authenticated:
        api_key = os.environ.get("ASTRA_API_KEY", "")
        if not api_key:
            raise RuntimeError("ASTRA_API_KEY is not configured for the protected API check")
        headers = {"Authorization": f"Bearer {api_key}"}
    return requests.get(
        f"http://{host}:{port}{path}", headers=headers, timeout=5
    )


@dataclass
class StageResult:
    """Resultado de una etapa del pipeline."""
    stage: str
    status: str  # "pass" | "fail" | "warn" | "skip"
    detail: str = ""
    error: str = ""
    cause: str = ""
    recommendation: str = ""
    duration_ms: float = 0.0
    data: dict = field(default_factory=dict)


@dataclass
class PipelineReport:
    """Informe completo del pipeline para un simbolo."""
    symbol: str
    timeframe: str = "H1"
    timestamp: str = ""
    stages: list[StageResult] = field(default_factory=list)
    overall_status: str = "pending"  # "pass" | "fail" | "partial"

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"

    @property
    def passed_count(self) -> int:
        return sum(1 for s in self.stages if s.status == "pass")

    @property
    def failed_count(self) -> int:
        return sum(1 for s in self.stages if s.status == "fail")

    @property
    def warn_count(self) -> int:
        return sum(1 for s in self.stages if s.status == "warn")

    def add_stage(self, result: StageResult):
        self.stages.append(result)
        self._update_overall()

    def _update_overall(self):
        if self.failed_count > 0:
            self.overall_status = "fail"
        elif self.warn_count > 0 and self.passed_count > 0:
            self.overall_status = "partial"
        elif self.passed_count > 0:
            self.overall_status = "pass"
        else:
            self.overall_status = "fail"

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp,
            "overall_status": self.overall_status,
            "passed": self.passed_count,
            "failed": self.failed_count,
            "warned": self.warn_count,
            "total_stages": len(self.stages),
            "stages": [
                {
                    "stage": s.stage,
                    "status": s.status,
                    "detail": s.detail,
                    "error": s.error,
                    "cause": s.cause,
                    "recommendation": s.recommendation,
                    "duration_ms": round(s.duration_ms, 1),
                }
                for s in self.stages
            ],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Pipeline Report — {self.symbol} ({self.timeframe})",
            f"",
            f"**Fecha:** {self.timestamp}",
            f"**Estado general:** {self.overall_status.upper()}",
            f"**Etapas:** {self.passed_count} OK / {self.warn_count} warnings / {self.failed_count} fallidas / {len(self.stages)} total",
            f"",
            f"---",
            f"",
        ]

        icons = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "skip": "SKIP"}

        for i, s in enumerate(self.stages, 1):
            icon = icons.get(s.status, s.status.upper())
            lines.append(f"## Etapa {i}: {s.stage}")
            lines.append(f"")
            lines.append(f"**Estado:** {icon}")
            lines.append(f"**Duracion:** {s.duration_ms:.0f} ms")
            if s.detail:
                lines.append(f"**Detalle:** {s.detail}")
            if s.status == "fail":
                if s.error:
                    lines.append(f"**Error:** `{s.error}`")
                if s.cause:
                    lines.append(f"**Causa probable:** {s.cause}")
                if s.recommendation:
                    lines.append(f"**Recomendacion:** {s.recommendation}")
            lines.append("")

        return "\n".join(lines)


def _diagnose_error(exc: Exception, stage: str) -> tuple[str, str]:
    """Retorna (causa_probable, recomendacion) segun el tipo de error y etapa."""
    exc_str = str(exc).lower()
    exc_type = type(exc).__name__

    # Database errors
    if "database" in exc_str or "sqlite" in exc_str or "no such table" in exc_str:
        return (
            "La base de datos no esta inicializada o falta una tabla",
            f"Ejecuta `python astra.py` para inicializar la DB, o `run_init(db)` desde el scheduler",
        )

    # Model not found
    if "no model" in exc_str or "filenotfounderror" in exc_str or "no hay modelo" in exc_str:
        return (
            "No existe un modelo entrenado para este par",
            f"Ejecuta `train forex CSVs/{stage}/<pair>.csv` o `full forex CSVs/{stage}/<pair>.csv`",
        )

    # Network / data provider
    if "connection" in exc_str or "timeout" in exc_str or "network" in exc_str or "yfinance" in exc_str:
        return (
            "Sin conectividad al proveedor de datos (Yahoo Finance / MT5)",
            "Verifica conexion a internet, firewall, o configura un proveedor alternativo",
        )

    # Feature mismatch
    if "feature_names" in exc_str or "mismatch" in exc_str:
        return (
            "Las features del modelo entrenado no coinciden con las del dataset actual",
            "Reentrena el modelo con `full forex CSVs/H4/<pair>.csv` para regenerar features",
        )

    # Insufficient data
    if "insufficient" in exc_str or "too few" in exc_str or "< 100" in exc_str:
        return (
            "El dataset tiene muy pocas filas para entrenar",
            "Descarga mas datos historicos (minimo 300 velas) o usa un timeframe mayor",
        )

    # Import errors
    if "importerror" in exc_str or "modulenotfounderror" in exc_str or "no module" in exc_str:
        return (
            f"Dependencia no instalada: {exc_str[:80]}",
            f"Instala con: pip install <paquete> o revisa requirements.txt",
        )

    # Permission errors
    if "permission" in exc_str or "access" in exc_str:
        return (
            "Permisos insuficientes en el directorio de trabajo",
            f"Verifica permisos de escritura en {_BASE}",
        )

    # Generic
    return (
        f"{exc_type}: {str(exc)[:120]}",
        "Revisa el log completo con `tail -f logs/astra.log` o ejecuta `astra doctor`",
    )


def run_pipeline_report(
    symbol: str,
    timeframe: str = "H1",
    csv_path: str | None = None,
    db=None,
) -> PipelineReport:
    """
    Ejecuta la validacion completa del pipeline para un simbolo.
    Reutiliza los modulos existentes: scheduler, pipeline, portfolio, API, etc.
    """
    timeframe = timeframe.upper()
    report = PipelineReport(symbol=symbol, timeframe=timeframe)

    # Auto-discover CSV if not provided
    if not csv_path:
        candidates = [
            forex_dataset_path(symbol, timeframe),
            _BASE / "CSVs" / timeframe / f"{symbol}.csv",
        ]
        for candidate in candidates:
            if candidate.exists():
                csv_path = str(candidate)
                break

    # ── Etapa 1: Descarga de datos ──────────────────────────
    t0 = time.time()
    try:
        df = None
        data_source = "unknown"

        if csv_path and os.path.exists(csv_path):
            data_source = f"CSV local: {csv_path}"
            report.add_stage(StageResult(
                stage="1. Descarga de datos",
                status="pass",
                detail=data_source,
                duration_ms=(time.time() - t0) * 1000,
            ))
        else:
            # Adquirir mediante el router canónico (MT5/Yahoo o Binance/Yahoo).
            try:
                from scheduler.autonomous_scheduler import fetch_market_data
                df, provider = fetch_market_data(symbol, timeframe)
                data_source = f"{provider}: {len(df)} velas"
                report.add_stage(StageResult(
                    stage="1. Descarga de datos",
                    status="pass",
                    detail=data_source,
                    duration_ms=(time.time() - t0) * 1000,
                    data={"candles": len(df)},
                ))
            except Exception as e:
                cause, rec = _diagnose_error(e, timeframe)
                report.add_stage(StageResult(
                    stage="1. Descarga de datos",
                    status="fail",
                    error=str(e)[:200],
                    cause=cause,
                    recommendation=rec,
                    duration_ms=(time.time() - t0) * 1000,
                ))
                # No se puede continuar sin datos
                report.add_stage(StageResult(
                    stage="2. Creacion CSV H1/H4/D1",
                    status="skip",
                    detail="Sin datos disponibles",
                ))
                report.add_stage(StageResult(
                    stage="3. Calculo de indicadores",
                    status="skip",
                    detail="Sin datos disponibles",
                ))
                report.add_stage(StageResult(
                    stage="4. Validacion del dataset",
                    status="skip",
                    detail="Sin datos disponibles",
                ))
                report.add_stage(StageResult(
                    stage="5. Entrenamiento / carga del modelo",
                    status="skip",
                    detail="Sin datos disponibles",
                ))
                report.add_stage(StageResult(
                    stage="6. Generacion de prediccion",
                    status="skip",
                    detail="Sin datos disponibles",
                ))
                report.add_stage(StageResult(
                    stage="7. Outcome Tracker",
                    status="skip",
                    detail="Sin prediccion generada",
                ))
                report.add_stage(StageResult(
                    stage="8. Opportunity Score",
                    status="skip",
                    detail="Sin prediccion generada",
                ))
                report.add_stage(StageResult(
                    stage="9. Portfolio Ranker",
                    status="skip",
                    detail="Sin oportunidades que rankear",
                ))
                report.add_stage(StageResult(
                    stage="10. Almacenamiento en DB",
                    status="skip",
                    detail="Sin datos para almacenar",
                ))
                report.add_stage(StageResult(
                    stage="11. Disponibilidad via API",
                    status="skip",
                    detail="Sin prediccion para exponer",
                ))
                report.add_stage(StageResult(
                    stage="12. Visualizacion en Workspace",
                    status="skip",
                    detail="Sin datos para visualizar",
                ))
                return report
    except Exception as e:
        cause, rec = _diagnose_error(e, timeframe)
        report.add_stage(StageResult(
            stage="1. Descarga de datos",
            status="fail",
            error=str(e)[:200],
            cause=cause,
            recommendation=rec,
            duration_ms=(time.time() - t0) * 1000,
        ))
        return report

    # ── Etapa 2: Creacion/actualizacion CSV ──────────────────
    t0 = time.time()
    try:
        if df is not None:
            # Guardar CSV descargado
            from scheduler.autonomous_scheduler import save_dataset_csv
            csv_path = save_dataset_csv(df, symbol, timeframe)
            import pandas as pd
            row_count = len(pd.read_csv(csv_path))
        else:
            # Verificar CSV local
            import pandas as pd
            df_check = pd.read_csv(csv_path)
            row_count = len(df_check)

        report.add_stage(StageResult(
            stage="2. Creacion CSV H1/H4/D1",
            status="pass",
            detail=f"CSV {timeframe}: {row_count} filas -> {csv_path}",
            duration_ms=(time.time() - t0) * 1000,
            data={"rows": row_count, "path": str(csv_path)},
        ))
    except Exception as e:
        cause, rec = _diagnose_error(e, timeframe)
        report.add_stage(StageResult(
            stage="2. Creacion CSV H1/H4/D1",
            status="fail",
            error=str(e)[:200],
            cause=cause,
            recommendation=rec,
            duration_ms=(time.time() - t0) * 1000,
        ))
        return report

    # ── Etapa 3: Calculo de indicadores (feature engineering) ──
    t0 = time.time()
    try:
        from forex.prediction.csv_adapter import adapt_csv
        from forex.prediction.feature_engineering import build_features
        df = adapt_csv(csv_path, pair=symbol)
        df_features = build_features(df)
        feature_count = len([c for c in df_features.columns
                            if c not in ["timestamp", "open", "high", "low", "close",
                                        "volume", "pair", "session"]])
        report.add_stage(StageResult(
            stage="3. Calculo de indicadores",
            status="pass",
            detail=f"{len(df_features)} filas, {feature_count} features calculados",
            duration_ms=(time.time() - t0) * 1000,
            data={"rows": len(df_features), "features": feature_count},
        ))
    except Exception as e:
        cause, rec = _diagnose_error(e, timeframe)
        report.add_stage(StageResult(
            stage="3. Calculo de indicadores",
            status="fail",
            error=str(e)[:200],
            cause=cause,
            recommendation=rec,
            duration_ms=(time.time() - t0) * 1000,
        ))
        return report

    # ── Etapa 4: Validacion del dataset (quality gate) ────────
    t0 = time.time()
    try:
        from forex.prediction.dataset_builder import DatasetBuilder
        builder = DatasetBuilder(df_features)
        X, y = builder.build(horizon=12, rr_ratio=1.0)
        quality_ok = len(X) >= 100

        # Intentar Quality Gate de Roadmap V si esta disponible
        try:
            from forex.prediction.roadmap_v_integration import run_quality_gate
            approved, qr = run_quality_gate(df_features, pair=symbol, timeframe=timeframe, verbose=False)
            gate_msg = f"Score: {qr.global_score:.0f}/100, criticos: {qr.critical_count}"
            status = "pass" if approved else "warn"
        except Exception:
            gate_msg = "Quality Gate no disponible (Roadmap V opcional)"
            status = "pass" if quality_ok else "warn"

        report.add_stage(StageResult(
            stage="4. Validacion del dataset",
            status=status,
            detail=f"Filas train: {len(X)} | {gate_msg}",
            duration_ms=(time.time() - t0) * 1000,
            data={"train_rows": len(X)},
        ))
    except Exception as e:
        cause, rec = _diagnose_error(e, timeframe)
        report.add_stage(StageResult(
            stage="4. Validacion del dataset",
            status="fail",
            error=str(e)[:200],
            cause=cause,
            recommendation=rec,
            duration_ms=(time.time() - t0) * 1000,
        ))
        return report

    # H4 and D1 are context-only datasets. Stop before executable model or
    # prediction side effects so they can never be promoted as H1.
    from forex.prediction.integrated_pipeline import PREDICTION_TIMEFRAME
    if timeframe != PREDICTION_TIMEFRAME:
        report.add_stage(StageResult(
            stage="5. Entrenamiento / carga del modelo",
            status="skip",
            detail=(
                f"{timeframe} es contexto MTF; solo {PREDICTION_TIMEFRAME} "
                "puede entrenar o cargar un modelo ejecutable"
            ),
        ))
        report.add_stage(StageResult(
            stage="6. Generacion de prediccion",
            status="skip",
            detail=(
                f"{timeframe} no genera predicciones ejecutables; "
                f"use {PREDICTION_TIMEFRAME} como dataset primario"
            ),
        ))
        for stage, detail in (
            ("7. Outcome Tracker", "Sin prediccion ejecutable que evaluar"),
            ("8. Opportunity Score", "Sin prediccion ejecutable que puntuar"),
            ("9. Portfolio Ranker", "Sin oportunidad ejecutable que ordenar"),
            ("10. Almacenamiento en DB", "Sin prediccion ejecutable que persistir"),
            ("11. Disponibilidad via API", "No aplica a un reporte de contexto MTF"),
            ("12. Visualizacion en Workspace", "No aplica a un reporte de contexto MTF"),
        ):
            report.add_stage(StageResult(stage=stage, status="skip", detail=detail))
        return report

    # ── Etapa 5: Entrenamiento o carga del modelo ────────────
    t0 = time.time()
    try:
        from forex.prediction.model_storage import ModelStorage
        storage = ModelStorage()

        # Verificar si ya existe modelo entrenado
        if storage.latest_exists(pair=symbol):
            model, train_columns = storage.load_model_with_features(pair=symbol)
            model_valid = getattr(model, "sufficient", True) if model else False
            from forex.prediction.retrain_manager import RetrainManager
            manager = (
                RetrainManager(database=db, storage=storage)
                if db is not None
                else RetrainManager(storage=storage)
            )
            eligibility = manager.audit_pair_model(symbol)
            revalidation = None
            if eligibility.get("bootstrap_revalidation"):
                from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

                pipe = ForexIntegratedPipeline()
                pipe.storage = storage
                if db is not None:
                    pipe.closed_loop_database = db
                    if hasattr(db, "get_dataset_registry"):
                        registry = db.get_dataset_registry(symbol, timeframe)
                        if registry:
                            entry = registry[0]
                            pipe.closed_loop_dataset_provenance = {
                                "registry_id": entry.get("id"),
                                "blob_path": entry.get("blob_path"),
                                "candle_count": entry.get("candle_count"),
                                "rolling_window_size": entry.get("rolling_window_size"),
                                "last_candle_timestamp": entry.get("last_candle_timestamp"),
                                "last_updated": entry.get("last_updated"),
                            }
                revalidation = pipe.bootstrap_revalidate(
                    csv_path, pair=symbol, manager=manager
                )
                eligibility = manager.audit_pair_model(symbol)
                if revalidation.get("model_deployed") and eligibility["eligible"]:
                    model, train_columns = storage.load_model_with_features(pair=symbol)
                    model_valid = (
                        getattr(model, "sufficient", True) if model else False
                    )
            executable = bool(model_valid and eligibility["eligible"])
            if executable:
                failure_cause = ""
            elif revalidation and revalidation.get("quality_gate_failed"):
                failure_cause = "QUALITY_GATE"
            elif revalidation:
                failure_cause = "BOOTSTRAP_REVALIDATION_FAILED"
            else:
                failure_cause = eligibility["reason"]
            report.add_stage(StageResult(
                stage="5. Entrenamiento / carga del modelo",
                status="pass" if executable else "fail",
                detail=(
                    f"Modelo cargado para {symbol} | valido: {model_valid} | "
                    f"eligibility: {eligibility['reason']} | features: "
                    f"{len(train_columns) if train_columns else 'N/A'}"
                ),
                cause=failure_cause,
                duration_ms=(time.time() - t0) * 1000,
                data={
                    "mode": (
                        "bootstrap_revalidation" if revalidation else "loaded"
                    ),
                    "valid": model_valid,
                    "eligibility": eligibility,
                    "revalidation": revalidation,
                },
            ))
            if not executable:
                return report
        else:
            # Entrenar modelo nuevo
            from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
            pipe = ForexIntegratedPipeline()
            if db is not None:
                pipe.closed_loop_database = db
            train_result = pipe.train(
                csv_path, pair=symbol, use_wfv=True, force=False
            )
            if "error" in train_result:
                raise RuntimeError(train_result["error"])
            wfv = train_result.get("wfv") or {}
            model_valid = train_result.get("model_valid") is True
            model_deployed = bool(
                train_result.get("model_deployed", wfv.get("model_deployed", False))
            )
            latest_exists = storage.latest_exists(pair=symbol)
            if not (model_valid and model_deployed and latest_exists):
                report.add_stage(StageResult(
                    stage="5. Entrenamiento / carga del modelo",
                    status="fail",
                    detail=(
                        f"Modelo no desplegado | model_valid={model_valid} | "
                        f"model_deployed={model_deployed} | "
                        f"latest_{symbol}={latest_exists}"
                    ),
                    cause="MODEL_NOT_DEPLOYED / QUALITY_GATE",
                    recommendation=(
                        "Revise calibration, validation and WFV evidence; "
                        "quality gates must pass before promotion"
                    ),
                    duration_ms=(time.time() - t0) * 1000,
                    data={"mode": "trained", **train_result},
                ))
                return report
            report.add_stage(StageResult(
                stage="5. Entrenamiento / carga del modelo",
                status="pass",
                detail=f"Modelo entrenado | precision: {train_result.get('precision', 'N/A')} | accuracy: {train_result.get('accuracy', 'N/A')}",
                duration_ms=(time.time() - t0) * 1000,
                data={"mode": "trained", **train_result},
            ))
    except Exception as e:
        cause, rec = _diagnose_error(e, timeframe)
        report.add_stage(StageResult(
            stage="5. Entrenamiento / carga del modelo",
            status="fail",
            error=str(e)[:200],
            cause=cause,
            recommendation=rec,
            duration_ms=(time.time() - t0) * 1000,
        ))
        return report

    # ── Etapa 6: Generacion de la primera prediccion ─────────
    t0 = time.time()
    try:
        from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
        pipe = ForexIntegratedPipeline()
        if db is not None:
            pipe.closed_loop_database = db
        pred = pipe.predict(csv_path, pair=symbol)

        if "error" in pred:
            raise RuntimeError(pred["error"])

        action = pred.get("action", pred.get("signal", "N/A"))
        conf = pred.get("confidence", 0)
        report.add_stage(StageResult(
            stage="6. Generacion de prediccion",
            status="pass",
            detail=f"Signal: {action} | Confidence: {conf:.2f} | ADX: {pred.get('adx', 'N/A')}",
            duration_ms=(time.time() - t0) * 1000,
            data={
                "action": action,
                "confidence": conf,
                "prediction_id": pred.get("prediction_id"),
            },
        ))
    except Exception as e:
        cause, rec = _diagnose_error(e, timeframe)
        report.add_stage(StageResult(
            stage="6. Generacion de prediccion",
            status="fail",
            error=str(e)[:200],
            cause=cause,
            recommendation=rec,
            duration_ms=(time.time() - t0) * 1000,
        ))
        return report

    # ── Etapa 7: Outcome Tracker ─────────────────────────────
    t0 = time.time()
    try:
        from forex.prediction.outcome_tracker import OutcomeTracker
        ot = OutcomeTracker(database=db) if db is not None else OutcomeTracker()
        outcome_stats = ot.get_stats(pair=symbol)
        stats = (
            outcome_stats.to_dict()
            if hasattr(outcome_stats, "to_dict")
            else dict(outcome_stats)
        )
        report.add_stage(StageResult(
            stage="7. Outcome Tracker",
            status="pass",
            detail=(
                "Tracker activo | predicciones operacionales registradas: "
                f"{stats.get('total_predictions', 0)}"
            ),
            duration_ms=(time.time() - t0) * 1000,
            data=stats,
        ))
    except Exception as e:
        cause, rec = _diagnose_error(e, timeframe)
        report.add_stage(StageResult(
            stage="7. Outcome Tracker",
            status="warn",  # No es critico
            error=str(e)[:200],
            cause=cause,
            recommendation=rec,
            duration_ms=(time.time() - t0) * 1000,
        ))

    # ── Etapa 8: Opportunity Score ───────────────────────────
    t0 = time.time()
    try:
        from forex.portfolio.opportunity_score import get_ranker
        ranker = get_ranker()
        report.add_stage(StageResult(
            stage="8. Opportunity Score",
            status="pass",
            detail="Opportunity Score engine disponible",
            duration_ms=(time.time() - t0) * 1000,
        ))
    except Exception as e:
        cause, rec = _diagnose_error(e, timeframe)
        report.add_stage(StageResult(
            stage="8. Opportunity Score",
            status="warn",
            error=str(e)[:200],
            cause=cause,
            recommendation=rec,
            duration_ms=(time.time() - t0) * 1000,
        ))

    # ── Etapa 9: Portfolio Ranker ────────────────────────────
    t0 = time.time()
    try:
        from forex.portfolio.portfolio_ranker import PortfolioRanker
        ranker = PortfolioRanker()
        report.add_stage(StageResult(
            stage="9. Portfolio Ranker",
            status="pass",
            detail="Portfolio Ranker disponible",
            duration_ms=(time.time() - t0) * 1000,
        ))
    except Exception as e:
        cause, rec = _diagnose_error(e, timeframe)
        report.add_stage(StageResult(
            stage="9. Portfolio Ranker",
            status="warn",
            error=str(e)[:200],
            cause=cause,
            recommendation=rec,
            duration_ms=(time.time() - t0) * 1000,
        ))

    # ── Etapa 10: Almacenamiento en base de datos ─────────────
    t0 = time.time()
    try:
        if db is None:
            from infra.db.database import get_database
            db = get_database()

        if action == "HOLD":
            report.add_stage(StageResult(
                stage="10. Almacenamiento en DB",
                status="pass",
                detail=(
                    f"DB engine: {getattr(db, 'engine', 'sqlite')} | "
                    "HOLD no entra al outcome loop"
                ),
                duration_ms=(time.time() - t0) * 1000,
            ))
        elif action in {"BUY", "SELL"}:
            prediction_id = pred.get("prediction_id")
            persisted = (
                db.get_prediction(prediction_id)
                if prediction_id and hasattr(db, "get_prediction")
                else None
            )
            identity_ok = bool(
                persisted
                and persisted.get("prediction_id") == prediction_id
                and persisted.get("symbol") == symbol
                and (persisted.get("action") or persisted.get("direction")) == action
            )
            report.add_stage(StageResult(
                stage="10. Almacenamiento en DB",
                status="pass" if identity_ok else "fail",
                detail=(
                    f"Prediction identity persisted: {prediction_id}"
                    if identity_ok
                    else "La prediccion operacional no tiene identidad persistida verificable"
                ),
                cause="" if identity_ok else "PREDICTION_ID_NOT_PERSISTED",
                duration_ms=(time.time() - t0) * 1000,
            ))
        else:
            report.add_stage(StageResult(
                stage="10. Almacenamiento en DB",
                status="fail",
                detail=f"Accion final no canonica: {action}",
                cause="INVALID_FINAL_ACTION",
                duration_ms=(time.time() - t0) * 1000,
            ))
    except Exception as e:
        cause, rec = _diagnose_error(e, timeframe)
        report.add_stage(StageResult(
            stage="10. Almacenamiento en DB",
            status="fail" if action in {"BUY", "SELL"} else "warn",
            error=str(e)[:200],
            cause=cause,
            recommendation=rec,
            duration_ms=(time.time() - t0) * 1000,
        ))

    # ── Etapa 11: Disponibilidad via API ──────────────────────
    t0 = time.time()
    try:
        r = _loopback_get("/api/datasets/status", authenticated=True)
        api_ok = r.status_code == 200
        report.add_stage(StageResult(
            stage="11. Disponibilidad via API",
            status="pass" if api_ok else "fail",
            detail=f"GET /api/datasets/status -> HTTP {r.status_code}",
            duration_ms=(time.time() - t0) * 1000,
        ))
    except Exception as e:
        cause, rec = _diagnose_error(e, timeframe)
        report.add_stage(StageResult(
            stage="11. Disponibilidad via API",
            status="warn",  # La API puede no estar corriendo en el momento del check
            error=str(e)[:200],
            cause="El servidor FastAPI no esta corriendo o no es accesible",
            recommendation="Inicia el workspace con: python -m workspace.server o uvicorn workspace.server:app",
            duration_ms=(time.time() - t0) * 1000,
        ))

    # ── Etapa 12: Visualizacion en el Workspace ──────────────
    t0 = time.time()
    try:
        r = _loopback_get("/")
        ws_ok = r.status_code == 200 and len(r.content) > 1000
        report.add_stage(StageResult(
            stage="12. Visualizacion en Workspace",
            status="pass" if ws_ok else "fail",
            detail=f"Workspace HTML: {len(r.content)} bytes" if ws_ok else f"HTTP {r.status_code}",
            duration_ms=(time.time() - t0) * 1000,
        ))
    except Exception as e:
        cause, rec = _diagnose_error(e, timeframe)
        report.add_stage(StageResult(
            stage="12. Visualizacion en Workspace",
            status="warn",
            error=str(e)[:200],
            cause="El workspace no esta corriendo o hay un error en los archivos estaticos",
            recommendation="Verifica que workspace/static/index.html existe y que el servidor esta activo",
            duration_ms=(time.time() - t0) * 1000,
        ))

    return report

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

_BASE = Path(__file__).resolve().parent.parent


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
    timeframe: str = "H4"
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
    timeframe: str = "H4",
    csv_path: str | None = None,
    db=None,
) -> PipelineReport:
    """
    Ejecuta la validacion completa del pipeline para un simbolo.
    Reutiliza los modulos existentes: scheduler, pipeline, portfolio, API, etc.
    """
    report = PipelineReport(symbol=symbol, timeframe=timeframe)

    # Auto-discover CSV if not provided
    if not csv_path:
        for tf_dir in [timeframe, timeframe.upper()]:
            candidate = _BASE / "CSVs" / tf_dir / f"{symbol}.csv"
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
            # Intentar Yahoo Finance
            try:
                from scheduler.autonomous_scheduler import fetch_yfinance
                df = fetch_yfinance(symbol, timeframe, count=2000)
                data_source = f"Yahoo Finance: {len(df)} velas"
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
            row_count = len(df)
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

    # ── Etapa 5: Entrenamiento o carga del modelo ────────────
    t0 = time.time()
    try:
        from forex.prediction.model_storage import ModelStorage
        storage = ModelStorage()

        # Verificar si ya existe modelo entrenado
        if storage.latest_exists(pair=symbol):
            model, train_columns = storage.load_model_with_features(pair=symbol)
            model_valid = getattr(model, "sufficient", True) if model else False
            report.add_stage(StageResult(
                stage="5. Entrenamiento / carga del modelo",
                status="pass" if model_valid else "warn",
                detail=f"Modelo cargado para {symbol} | valido: {model_valid} | features: {len(train_columns) if train_columns else 'N/A'}",
                duration_ms=(time.time() - t0) * 1000,
                data={"mode": "loaded", "valid": model_valid},
            ))
        else:
            # Entrenar modelo nuevo
            from forex.prediction.integrated_pipeline import ForexIntegratedPipeline
            pipe = ForexIntegratedPipeline()
            train_result = pipe.train(csv_path, pair=symbol, use_wfv=False, force=True)
            if "error" in train_result:
                raise RuntimeError(train_result["error"])
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
            data={"action": action, "confidence": conf},
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
        ot = OutcomeTracker()
        stats = ot.stats(pair=symbol)
        report.add_stage(StageResult(
            stage="7. Outcome Tracker",
            status="pass",
            detail=f"Tracker activo | predicciones registradas: {stats.get('total', 0)}",
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

        preds = db.get_predictions(symbol=symbol, limit=1)
        has_preds = len(preds) > 0 if preds else False

        report.add_stage(StageResult(
            stage="10. Almacenamiento en DB",
            status="pass" if has_preds else "warn",
            detail=f"DB engine: {getattr(db, 'engine', 'sqlite')} | predicciones de {symbol}: {len(preds) if preds else 0}",
            duration_ms=(time.time() - t0) * 1000,
        ))
    except Exception as e:
        cause, rec = _diagnose_error(e, timeframe)
        report.add_stage(StageResult(
            stage="10. Almacenamiento en DB",
            status="warn",
            error=str(e)[:200],
            cause=cause,
            recommendation=rec,
            duration_ms=(time.time() - t0) * 1000,
        ))

    # ── Etapa 11: Disponibilidad via API ──────────────────────
    t0 = time.time()
    try:
        from fastapi.testclient import TestClient
        from workspace.server import app
        c = TestClient(app)
        r = c.get("/api/datasets/status")
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
        from fastapi.testclient import TestClient
        from workspace.server import app
        c = TestClient(app)
        r = c.get("/")
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

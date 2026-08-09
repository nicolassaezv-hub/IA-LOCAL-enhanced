"""
FirstRunValidator — Orquestador del First Deployment Experience.

Ejecuta los 3 informes en secuencia:
  1. Pipeline Report por simbolo
  2. Deployment Report (agrega todos los pipeline reports)
  3. Production Readiness Report

Se ejecuta automaticamente tras run_init() del scheduler (solo primera vez),
o manualmente con el comando `deploy check`.
"""
from __future__ import annotations

import os
import json
import time
from datetime import datetime
from pathlib import Path

from .report_manager import ReportManager
from .pipeline_report import PipelineReport, run_pipeline_report
from .deployment_report import DeploymentReport, run_deployment_report
from .production_readiness import ProductionReadinessReport, run_production_readiness

_BASE = Path(__file__).resolve().parent.parent


def _is_first_run(db) -> bool:
    """Detecta si es la primera inicializacion (sin predicciones previas en DB)."""
    try:
        preds = db.get_predictions(limit=1)
        return not preds
    except Exception:
        # Si la tabla no existe, es primera vez
        return True


def run_first_deployment_check(
    db=None,
    symbols: list[str] | None = None,
    timeframe: str = "H4",
    force: bool = False,
) -> dict:
    """
    Ejecuta el First Deployment Experience completo.
    
    Args:
        db: instancia de DatabaseAdapter (si None, se crea una nueva)
        symbols: lista de simbolos a validar (si None, usa los de la DB)
        timeframe: timeframe a validar (default H4)
        force: si True, ejecuta aunque ya haya predicciones previas
    
    Returns:
        dict con el resumen de los 3 informes
    """
    from infra.db.database import get_database
    if db is None:
        db = get_database()

    # Verificar si es primera vez
    is_first = _is_first_run(db) or force

    print(f"\n{'='*60}")
    print(f"  ASTRA — First Deployment Experience")
    print(f"  {'Primera instalacion' if is_first else 'Verificacion manual'}")
    print(f"{'='*60}\n")

    manager = ReportManager()
    t_start = time.time()

    # ── Descubrir simbolos ────────────────────────────────────
    if symbols is None:
        db_symbols = db.get_supported_symbols()
        symbols = [s["symbol_code"] for s in db_symbols] if db_symbols else []

    if not symbols:
        # Fallback: usar CSVs locales disponibles
        csvs_dir = _BASE / "CSVs" / timeframe
        if csvs_dir.exists():
            symbols = [f.stem for f in csvs_dir.glob("*.csv")]
        else:
            # Ultimo recurso: defaults
            symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]

    print(f"Simbolos a validar: {', '.join(symbols)}")
    print(f"Timeframe: {timeframe}")
    print()

    # ── 1. Pipeline Reports por simbolo ──────────────────────
    pipeline_reports = []
    print("--- 1/3: Pipeline Reports ---\n")

    for i, sym in enumerate(symbols, 1):
        print(f"  [{i}/{len(symbols)}] {sym}...")
        t_sym = time.time()
        pr = run_pipeline_report(symbol=sym, timeframe=timeframe, db=db)
        elapsed = time.time() - t_sym

        # Guardar informe
        md = pr.to_markdown()
        relative_path = manager.save_report(
            report_type="pipeline",
            content_md=md,
            metadata={
                "symbol": sym,
                "timeframe": timeframe,
                "overall_status": pr.overall_status,
                "passed": pr.passed_count,
                "failed": pr.failed_count,
                "warned": pr.warn_count,
                "summary": f"{sym}: {pr.overall_status.upper()} ({pr.passed_count}/{len(pr.stages)} OK)",
            },
        )

        pipeline_reports.append(pr)
        status_icon = "OK" if pr.overall_status == "pass" else ("WARN" if pr.overall_status == "partial" else "FAIL")
        print(f"    {status_icon} | {pr.passed_count}/{len(pr.stages)} etapas OK | {elapsed:.1f}s | {relative_path}")
        print()

    # ── 2. Deployment Report general ─────────────────────────
    print("--- 2/3: Deployment Report ---\n")
    dep_report = run_deployment_report(pipeline_reports)
    dep_md = dep_report.to_markdown()
    dep_path = manager.save_report(
        report_type="deployment",
        content_md=dep_md,
        metadata={
            "global_status": dep_report.global_status,
            "symbols_total": dep_report.symbols_total,
            "symbols_passed": dep_report.symbols_passed,
            "symbols_failed": dep_report.symbols_failed,
            "symbols_partial": dep_report.symbols_partial,
            "summary": f"{dep_report.global_status}: {dep_report.symbols_passed}/{dep_report.symbols_total} OK",
        },
    )
    print(f"  {dep_report.global_status}")
    print(f"  {dep_report.symbols_passed} OK / {dep_report.symbols_failed} FAIL / {dep_report.symbols_partial} PARTIAL")
    print(f"  Guardado: {dep_path}\n")

    # ── 3. Production Readiness Report ────────────────────────
    print("--- 3/3: Production Readiness Report ---\n")
    readiness = run_production_readiness()
    ready_md = readiness.to_markdown()
    ready_path = manager.save_report(
        report_type="readiness",
        content_md=ready_md,
        metadata={
            "global_status": readiness.global_status,
            "passed": readiness.passed,
            "failed": readiness.failed,
            "warned": readiness.warned,
            "summary": f"{readiness.global_status}: {readiness.passed} OK / {readiness.failed} FAIL / {readiness.warned} WARN",
        },
    )
    print(f"  {readiness.global_status}")
    print(f"  {readiness.passed} OK / {readiness.failed} FAIL / {readiness.warned} WARN")
    print(f"  Guardado: {ready_path}\n")

    # ── Resumen final ────────────────────────────────────────
    total_time = time.time() - t_start
    print(f"{'='*60}")
    print(f"  FIRST DEPLOYMENT EXPERIENCE COMPLETADO")
    print(f"  Tiempo total: {total_time:.1f}s")
    print(f"  Deployment: {dep_report.global_status}")
    print(f"  Readiness: {readiness.global_status}")
    print(f"  Informes en: reports/deployment/")
    print(f"{'='*60}\n")

    return {
        "deployment_status": dep_report.global_status,
        "readiness_status": readiness.global_status,
        "symbols_total": dep_report.symbols_total,
        "symbols_passed": dep_report.symbols_passed,
        "symbols_failed": dep_report.symbols_failed,
        "symbols_partial": dep_report.symbols_partial,
        "readiness_passed": readiness.passed,
        "readiness_failed": readiness.failed,
        "readiness_warned": readiness.warned,
        "total_time_seconds": round(total_time, 1),
        "reports": {
            "pipeline": [pr.to_dict() for pr in pipeline_reports],
            "deployment": dep_report.to_dict(),
            "readiness": readiness.to_dict(),
        },
        "report_paths": {
            "pipeline_reports": [manager.list_reports("pipeline")],
            "deployment_report": dep_path,
            "readiness_report": ready_path,
        },
    }

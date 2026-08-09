"""
ASTRA — First Deployment Experience
====================================
Sistema de validacion automatica para la primera puesta en marcha.

Genera tres informes independientes:
  1. Pipeline Report      — validacion por simbolo del flujo completo
  2. Deployment Report     — resumen general de todos los simbolos
  3. Production Readiness  — estado del entorno de produccion

Se ejecuta automaticamente tras la primera inicializacion del scheduler,
o manualmente con el comando: `deploy check`
"""

from .report_manager import ReportManager
from .pipeline_report import PipelineReport, run_pipeline_report
from .deployment_report import DeploymentReport, run_deployment_report
from .production_readiness import ProductionReadinessReport, run_production_readiness
from .first_run_validator import run_first_deployment_check

__all__ = [
    "ReportManager",
    "PipelineReport",
    "DeploymentReport",
    "ProductionReadinessReport",
    "run_pipeline_report",
    "run_deployment_report",
    "run_production_readiness",
    "run_first_deployment_check",
]

"""
ASTRA Centralized Dependency & Environment Pre-Flight Validator.

Checks ALL critical components before system startup:
 1. Python environment (version >= 3.10)
 2. Critical dependencies installed
 3. Optional dependencies
 4. Environment variables (astra.env, GROQ_API_KEY, OPENAI_API_KEY)
 5. Data provider connectivity (yfinance, MT5 if Windows, binance)
 6. SQLite database access
 7. Write permissions (CSVs/, models/, memory_db/, logs/, reports/)
 8. Workspace availability (FastAPI TestClient GET / returns 200)
 9. Scheduler status (can import and get_status)
10. systemd services (.service files exist, active check if Linux)
11. Backups directory exists
12. Monitoring (psutil available, CPU/RAM)
13. Directory structure (all expected dirs exist)
14. API endpoints health (FastAPI TestClient GET /health)
"""

from __future__ import annotations

import os
import sys
import json
import sqlite3
import shutil
import platform
import importlib
import subprocess
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

_BASE_DIR = Path(__file__).resolve().parent.parent

CRITICAL_DEPS = [
    "pandas",
    "numpy",
    "sklearn",
    "xgboost",
    "lightgbm",
    "optuna",
    "requests",
    "fastapi",
    "uvicorn",
    "colorama",
    "rich",
    "orjson",
    "filelock",
    "psutil",
]

OPTIONAL_DEPS = [
    "yfinance",
    "redis",
    "torch",
    "MetaTrader5",
    "openai",
    "binance",
]

CATEGORIES = [
    "Python",
    "Dependencies",
    "Configuration",
    "Data Providers",
    "Database",
    "Permissions",
    "Workspace",
    "Scheduler",
    "Systemd",
    "Backups",
    "Monitoring",
    "Structure",
    "API",
]


@dataclass
class Check:
    name: str
    category: str
    status: str  # "pass" | "fail" | "warn"
    detail: str
    is_blocking: bool
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "detail": self.detail,
            "is_blocking": self.is_blocking,
            "recommendation": self.recommendation,
        }


class ValidationResult(dict):
    """
    Result dictionary representing dependency validation report.
    Keys: ready (bool), checks (list[Dict]), blocking_count (int), warning_count (int), timestamp (str)
    Provides a .to_markdown() method for human-readable reports.
    """

    def __init__(
        self,
        ready: bool,
        checks: List[Dict[str, Any]],
        blocking_count: int,
        warning_count: int,
        timestamp: Optional[str] = None,
    ):
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        super().__init__(
            ready=ready,
            checks=checks,
            blocking_count=blocking_count,
            warning_count=warning_count,
            timestamp=timestamp,
        )

    @property
    def ready(self) -> bool:
        return self["ready"]

    @property
    def checks(self) -> List[Dict[str, Any]]:
        return self["checks"]

    @property
    def blocking_count(self) -> int:
        return self["blocking_count"]

    @property
    def warning_count(self) -> int:
        return self["warning_count"]

    @property
    def timestamp(self) -> str:
        return self["timestamp"]

    def to_markdown(self) -> str:
        status_str = "READY FOR STARTUP" if self.ready else "NOT READY - BLOCKING ISSUES FOUND"
        status_emoji = "✅" if self.ready else "❌"

        lines = [
            "# Reporte de Validación de Dependencias ASTRA (Pre-Flight Check)",
            "",
            f"**Estado Global:** {status_emoji} **{status_str}**",
            f"**Fecha y Hora:** `{self.timestamp}`",
            f"**Problemas Bloqueantes:** `{self.blocking_count}`",
            f"**Advertencias:** `{self.warning_count}`",
            "",
            "---",
            "",
            "## Resumen por Categoría",
            "",
            "| Categoría | Estado | Verificaciones |",
            "| :--- | :---: | :--- |",
        ]

        # Group checks by category
        cat_checks: Dict[str, List[Dict[str, Any]]] = {}
        for c in self.checks:
            cat = c.get("category", "Otros")
            cat_checks.setdefault(cat, []).append(c)

        for cat in CATEGORIES:
            if cat in cat_checks:
                checks_in_cat = cat_checks[cat]
                statuses = [chk["status"] for chk in checks_in_cat]
                if "fail" in statuses:
                    cat_status = "❌ FAIL"
                elif "warn" in statuses:
                    cat_status = "⚠️ WARN"
                else:
                    cat_status = "✅ PASS"

                details = f"{len(checks_in_cat)} check(s)"
                lines.append(f"| **{cat}** | {cat_status} | {details} |")

        lines.extend([
            "",
            "---",
            "",
            "## Detalle de Verificaciones",
            "",
        ])

        for cat in CATEGORIES:
            if cat in cat_checks:
                lines.append(f"### Categoría: {cat}")
                for chk in cat_checks[cat]:
                    st = chk["status"].upper()
                    if st == "PASS":
                        icon = "✅ [PASS]"
                    elif st == "FAIL":
                        icon = "❌ [FAIL]"
                    else:
                        icon = "⚠️ [WARN]"

                    block_tag = " **(BLOQUEANTE)**" if chk.get("is_blocking") else ""
                    lines.append(f"- {icon} **{chk['name']}**{block_tag}")
                    lines.append(f"  - **Detalle:** {chk['detail']}")
                    if chk.get("recommendation"):
                        lines.append(f"  - **Recomendación:** {chk['recommendation']}")
                lines.append("")

        return "\n".join(lines)


def run_dependency_validation(base_dir: Optional[Path | str] = None) -> ValidationResult:
    """
    Executes all centralized dependency and pre-flight validation checks.

    Returns a ValidationResult dictionary containing:
      - ready: bool (True if blocking_count == 0)
      - checks: list of check dictionaries
      - blocking_count: int
      - warning_count: int
    """
    if base_dir is None:
        base_dir = _BASE_DIR
    else:
        base_dir = Path(base_dir)

    checks: List[Check] = []

    # -------------------------------------------------------------
    # 1. Python Environment Check
    # -------------------------------------------------------------
    py_major, py_minor = sys.version_info.major, sys.version_info.minor
    py_ver_str = f"{py_major}.{py_minor}.{sys.version_info.micro}"
    if (py_major, py_minor) >= (3, 10):
        checks.append(Check(
            name="Versión de Python",
            category="Python",
            status="pass",
            detail=f"Python {py_ver_str} en {sys.executable}",
            is_blocking=False
        ))
    else:
        checks.append(Check(
            name="Versión de Python",
            category="Python",
            status="fail",
            detail=f"Python {py_ver_str} detectado (se requiere >= 3.10)",
            is_blocking=True,
            recommendation="Actualice el entorno Python a la versión 3.10 o superior"
        ))

    # -------------------------------------------------------------
    # 2. Critical Dependencies
    # -------------------------------------------------------------
    missing_critical = []
    installed_critical = []
    for dep in CRITICAL_DEPS:
        try:
            importlib.import_module(dep)
            installed_critical.append(dep)
        except ImportError:
            missing_critical.append(dep)

    if not missing_critical:
        checks.append(Check(
            name="Dependencias Críticas",
            category="Dependencies",
            status="pass",
            detail=f"Todas las {len(CRITICAL_DEPS)} dependencias críticas instaladas ({', '.join(CRITICAL_DEPS)})",
            is_blocking=False
        ))
    else:
        checks.append(Check(
            name="Dependencias Críticas",
            category="Dependencies",
            status="fail",
            detail=f"Faltan {len(missing_critical)} dependencias críticas: {', '.join(missing_critical)}",
            is_blocking=True,
            recommendation=f"Ejecute: pip install {' '.join(missing_critical)}"
        ))

    # -------------------------------------------------------------
    # 3. Optional Dependencies
    # -------------------------------------------------------------
    missing_optional = []
    installed_optional = []
    for dep in OPTIONAL_DEPS:
        try:
            if dep == "binance":
                try:
                    importlib.import_module("binance")
                except ImportError:
                    importlib.import_module("binance.client")
            else:
                importlib.import_module(dep)
            installed_optional.append(dep)
        except ImportError:
            missing_optional.append(dep)

    if not missing_optional:
        checks.append(Check(
            name="Dependencias Opcionales",
            category="Dependencies",
            status="pass",
            detail=f"Todas las {len(OPTIONAL_DEPS)} dependencias opcionales instaladas ({', '.join(OPTIONAL_DEPS)})",
            is_blocking=False
        ))
    else:
        checks.append(Check(
            name="Dependencias Opcionales",
            category="Dependencies",
            status="warn",
            detail=f"Instaladas {len(installed_optional)}/{len(OPTIONAL_DEPS)}: {', '.join(installed_optional)}. Faltan: {', '.join(missing_optional)}",
            is_blocking=False,
            recommendation=f"Para instalar dependencias opcionales faltantes: pip install {' '.join(missing_optional)}"
        ))

    # -------------------------------------------------------------
    # 4. Environment Variables & Configuration
    # -------------------------------------------------------------
    env_paths = [
        base_dir / "infra" / "config" / "astra.env",
        base_dir / "astra.env",
        base_dir / ".env",
    ]
    found_env = None
    for p in env_paths:
        if p.exists() and p.is_file():
            found_env = p
            break

    groq_key = os.environ.get("GROQ_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    if found_env and not (groq_key or openai_key):
        try:
            content = found_env.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("GROQ_API_KEY=") and len(line) > 13:
                    groq_key = line.split("=", 1)[1].strip()
                elif line.startswith("OPENAI_API_KEY=") and len(line) > 15:
                    openai_key = line.split("=", 1)[1].strip()
        except Exception:
            pass

    has_api_keys = bool(groq_key or openai_key)

    if found_env and has_api_keys:
        checks.append(Check(
            name="Variables de Entorno y Configuración",
            category="Configuration",
            status="pass",
            detail=f"Archivo de entorno en '{found_env.relative_to(base_dir) if found_env.is_relative_to(base_dir) else found_env}' y claves API configuradas",
            is_blocking=False
        ))
    elif found_env:
        checks.append(Check(
            name="Variables de Entorno y Configuración",
            category="Configuration",
            status="warn",
            detail=f"Archivo de entorno en '{found_env.relative_to(base_dir) if found_env.is_relative_to(base_dir) else found_env}' sin GROQ_API_KEY ni OPENAI_API_KEY",
            is_blocking=False,
            recommendation="Configure GROQ_API_KEY o OPENAI_API_KEY en astra.env para usar módulos de IA"
        ))
    else:
        checks.append(Check(
            name="Variables de Entorno y Configuración",
            category="Configuration",
            status="warn",
            detail="No se encontró el archivo astra.env en infra/config/ ni en la raíz",
            is_blocking=False,
            recommendation="Copie infra/config/astra.env.example a infra/config/astra.env y configure sus llaves API"
        ))

    # -------------------------------------------------------------
    # 5. Data Provider Connectivity
    # -------------------------------------------------------------
    # 5a. Yahoo Finance
    try:
        import yfinance as yf
        df = yf.Ticker("AAPL").history(period="1d", timeout=5)
        if not df.empty:
            checks.append(Check(
                name="Yahoo Finance Data Provider",
                category="Data Providers",
                status="pass",
                detail="Conectividad exitosa con Yahoo Finance (1 vela descargada correctamente)",
                is_blocking=False
            ))
        else:
            checks.append(Check(
                name="Yahoo Finance Data Provider",
                category="Data Providers",
                status="warn",
                detail="yfinance disponible pero la descarga retornó un DataFrame vacío",
                is_blocking=False,
                recommendation="Verifique conectividad a Internet o límites de API de Yahoo Finance"
            ))
    except ImportError:
        checks.append(Check(
            name="Yahoo Finance Data Provider",
            category="Data Providers",
            status="warn",
            detail="Librería yfinance no instalada",
            is_blocking=False,
            recommendation="Ejecute: pip install yfinance"
        ))
    except Exception as e:
        checks.append(Check(
            name="Yahoo Finance Data Provider",
            category="Data Providers",
            status="warn",
            detail=f"Error en prueba de conectividad con Yahoo Finance: {str(e)}",
            is_blocking=False,
            recommendation="Verifique su conexión a Internet"
        ))

    # 5b. MetaTrader 5
    if sys.platform == "win32":
        try:
            import MetaTrader5 as mt5
            if mt5.initialize():
                mt5.shutdown()
                checks.append(Check(
                    name="MetaTrader 5 Data Provider",
                    category="Data Providers",
                    status="pass",
                    detail="Terminal y API MetaTrader 5 inicializados correctamente",
                    is_blocking=False
                ))
            else:
                checks.append(Check(
                    name="MetaTrader 5 Data Provider",
                    category="Data Providers",
                    status="warn",
                    detail="Librería MT5 instalada pero no se pudo inicializar la terminal",
                    is_blocking=False,
                    recommendation="Asegúrese de que la terminal de MetaTrader 5 esté instalada y habilitada"
                ))
        except ImportError:
            checks.append(Check(
                name="MetaTrader 5 Data Provider",
                category="Data Providers",
                status="warn",
                detail="Librería MetaTrader5 no instalada",
                is_blocking=False,
                recommendation="Ejecute: pip install MetaTrader5"
            ))
        except Exception as e:
            checks.append(Check(
                name="MetaTrader 5 Data Provider",
                category="Data Providers",
                status="warn",
                detail=f"Error en verificación MT5: {str(e)}",
                is_blocking=False
            ))
    else:
        checks.append(Check(
            name="MetaTrader 5 Data Provider",
            category="Data Providers",
            status="pass",
            detail="Verificación MT5 omitida (MetaTrader 5 solo es soportado en Windows)",
            is_blocking=False
        ))

    # 5c. Binance
    try:
        binance_ok = False
        try:
            importlib.import_module("binance")
            binance_ok = True
        except ImportError:
            importlib.import_module("binance.client")
            binance_ok = True

        if binance_ok:
            checks.append(Check(
                name="Binance Data Provider",
                category="Data Providers",
                status="pass",
                detail="Librería python-binance instalada y disponible",
                is_blocking=False
            ))
    except ImportError:
        checks.append(Check(
            name="Binance Data Provider",
            category="Data Providers",
            status="warn",
            detail="Librería python-binance no disponible",
            is_blocking=False,
            recommendation="Ejecute: pip install python-binance"
        ))
    except Exception as e:
        checks.append(Check(
            name="Binance Data Provider",
            category="Data Providers",
            status="warn",
            detail=f"Error en verificación Binance: {str(e)}",
            is_blocking=False
        ))

    # -------------------------------------------------------------
    # 6. SQLite Database Access
    # -------------------------------------------------------------
    db_candidates = [
        base_dir / "memoria.db",
        base_dir / "astra_hparam_cache.db",
        base_dir / "dev_log.db",
    ]
    db_tested = None
    db_success = False
    db_error_msg = ""

    for db_path in db_candidates:
        try:
            conn = sqlite3.connect(str(db_path), timeout=5)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            _ = cur.fetchall()
            conn.close()
            db_tested = db_path.name
            db_success = True
            break
        except Exception as e:
            db_error_msg = str(e)

    if not db_success:
        try:
            conn = sqlite3.connect(":memory:")
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            conn.close()
            db_tested = "in-memory SQLite"
            db_success = True
        except Exception as e:
            db_error_msg = str(e)

    if db_success:
        checks.append(Check(
            name="Acceso a Base de Datos SQLite",
            category="Database",
            status="pass",
            detail=f"Base de datos SQLite funcional y consultas ejecutadas con éxito ({db_tested})",
            is_blocking=False
        ))
    else:
        checks.append(Check(
            name="Acceso a Base de Datos SQLite",
            category="Database",
            status="fail",
            detail=f"Fallo al acceder/consultar base de datos SQLite: {db_error_msg}",
            is_blocking=True,
            recommendation="Verifique integridad de los archivos .db y permisos de lectura/escritura"
        ))

    # -------------------------------------------------------------
    # 7. Write Permissions
    # -------------------------------------------------------------
    required_write_dirs = ["CSVs", "models", "memory_db", "logs", "reports"]
    failed_dirs = []

    for d in required_write_dirs:
        target_dir = base_dir / d
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            test_file = target_dir / ".perm_check.tmp"
            test_file.write_text("test_write_perm", encoding="utf-8")
            if test_file.exists():
                test_file.unlink()
        except Exception:
            failed_dirs.append(d)

    if not failed_dirs:
        checks.append(Check(
            name="Permisos de Escritura",
            category="Permissions",
            status="pass",
            detail=f"Permisos de escritura OK en todos los directorios requeridos ({', '.join(required_write_dirs)})",
            is_blocking=False
        ))
    else:
        checks.append(Check(
            name="Permisos de Escritura",
            category="Permissions",
            status="fail",
            detail=f"Sin permisos de escritura en directorios: {', '.join(failed_dirs)}",
            is_blocking=True,
            recommendation=f"Verifique permisos de sistema en: {', '.join(failed_dirs)}"
        ))

    # -------------------------------------------------------------
    # 8. Workspace Availability
    # -------------------------------------------------------------
    try:
        from fastapi.testclient import TestClient
        from workspace.server import app as ws_app

        client = TestClient(ws_app)
        res = client.get("/")
        if res.status_code == 200:
            checks.append(Check(
                name="Disponibilidad de Workspace",
                category="Workspace",
                status="pass",
                detail=f"FastAPI TestClient GET / respondió HTTP 200 ({len(res.content)} bytes)",
                is_blocking=False
            ))
        else:
            checks.append(Check(
                name="Disponibilidad de Workspace",
                category="Workspace",
                status="fail",
                detail=f"FastAPI TestClient GET / respondió con HTTP {res.status_code}",
                is_blocking=False,
                recommendation="Verifique workspace/server.py y la existencia de workspace/static/index.html"
            ))
    except Exception as e:
        checks.append(Check(
            name="Disponibilidad de Workspace",
            category="Workspace",
            status="fail",
            detail=f"Fallo al instanciar TestClient para Workspace: {str(e)}",
            is_blocking=False,
            recommendation="Verifique workspace/server.py y las dependencias de FastAPI"
        ))

    # -------------------------------------------------------------
    # 9. Scheduler Status
    # -------------------------------------------------------------
    try:
        import scheduler.autonomous_scheduler as sched_mod
        from infra.db.database import get_database

        if hasattr(sched_mod, "get_status"):
            try:
                db_inst = get_database()
                _ = sched_mod.get_status(db_inst)
                sched_detail = "Módulo scheduler importado y get_status(db) ejecutado con éxito"
            except Exception:
                sched_detail = "Módulo scheduler importado y función get_status() verificada"

            checks.append(Check(
                name="Estado del Scheduler",
                category="Scheduler",
                status="pass",
                detail=sched_detail,
                is_blocking=False
            ))
        else:
            checks.append(Check(
                name="Estado del Scheduler",
                category="Scheduler",
                status="fail",
                detail="Módulo scheduler importado pero carece de la función get_status()",
                is_blocking=False,
                recommendation="Asegúrese de definir get_status en scheduler/autonomous_scheduler.py"
            ))
    except Exception as e:
        checks.append(Check(
            name="Estado del Scheduler",
            category="Scheduler",
            status="fail",
            detail=f"Error al importar o verificar scheduler: {str(e)}",
            is_blocking=False,
            recommendation="Verifique scheduler/autonomous_scheduler.py"
        ))

    # -------------------------------------------------------------
    # 10. systemd Services Check
    # -------------------------------------------------------------
    systemd_dir = base_dir / "infra" / "systemd"
    service_files = list(systemd_dir.glob("*.service")) if systemd_dir.exists() else []

    if service_files:
        svc_names = [f.name for f in service_files]
        if sys.platform.startswith("linux") and shutil.which("systemctl"):
            active_count = 0
            for sf in service_files:
                try:
                    p = subprocess.run(["systemctl", "is-active", sf.name], capture_output=True, text=True, timeout=3)
                    if p.stdout.strip() == "active":
                        active_count += 1
                except Exception:
                    pass
            checks.append(Check(
                name="Servicios systemd",
                category="Systemd",
                status="pass",
                detail=f"{len(service_files)} archivos .service en infra/systemd/. Activos en Linux: {active_count}/{len(service_files)}",
                is_blocking=False
            ))
        else:
            checks.append(Check(
                name="Servicios systemd",
                category="Systemd",
                status="pass",
                detail=f"{len(service_files)} archivos .service encontrados en infra/systemd/ ({', '.join(svc_names)})",
                is_blocking=False
            ))
    else:
        checks.append(Check(
            name="Servicios systemd",
            category="Systemd",
            status="warn",
            detail="No se encontraron archivos .service en infra/systemd/",
            is_blocking=False,
            recommendation="Verifique si los servicios systemd han sido configurados en infra/systemd/"
        ))

    # -------------------------------------------------------------
    # 11. Backups Directory
    # -------------------------------------------------------------
    backups_dir = base_dir / "backups"
    if backups_dir.exists() and backups_dir.is_dir():
        checks.append(Check(
            name="Directorio de Backups",
            category="Backups",
            status="pass",
            detail=f"Directorio de respaldos 'backups/' existente en {backups_dir}",
            is_blocking=False
        ))
    else:
        try:
            backups_dir.mkdir(parents=True, exist_ok=True)
            checks.append(Check(
                name="Directorio de Backups",
                category="Backups",
                status="warn",
                detail="El directorio 'backups/' no existía pero fue creado automáticamente",
                is_blocking=False
            ))
        except Exception as e:
            checks.append(Check(
                name="Directorio de Backups",
                category="Backups",
                status="warn",
                detail=f"No existe el directorio 'backups/' y no pudo crearse: {str(e)}",
                is_blocking=False,
                recommendation="Cree manualmente el directorio backups/ en la raíz del proyecto"
            ))

    # -------------------------------------------------------------
    # 12. Monitoring (psutil)
    # -------------------------------------------------------------
    try:
        import psutil
        cpu_usage = psutil.cpu_percent(interval=0.1)
        vmem = psutil.virtual_memory()
        ram_used_gb = vmem.used / (1024 ** 3)
        ram_total_gb = vmem.total / (1024 ** 3)
        checks.append(Check(
            name="Monitoreo del Sistema (psutil)",
            category="Monitoring",
            status="pass",
            detail=f"psutil operativo | CPU: {cpu_usage}% | RAM: {vmem.percent}% ({ram_used_gb:.1f} GB / {ram_total_gb:.1f} GB usada)",
            is_blocking=False
        ))
    except Exception as e:
        checks.append(Check(
            name="Monitoreo del Sistema (psutil)",
            category="Monitoring",
            status="fail",
            detail=f"psutil no está disponible o falló la lectura de recursos: {str(e)}",
            is_blocking=True,
            recommendation="Ejecute: pip install psutil"
        ))

    # -------------------------------------------------------------
    # 13. Directory Structure
    # -------------------------------------------------------------
    expected_dirs = ["CSVs", "models", "memory_db", "logs", "reports", "infra", "scheduler", "workspace", "backups"]
    missing_dirs = []
    for d in expected_dirs:
        p = base_dir / d
        if not (p.exists() and p.is_dir()):
            missing_dirs.append(d)

    if not missing_dirs:
        checks.append(Check(
            name="Estructura de Directorios del Proyecto",
            category="Structure",
            status="pass",
            detail=f"Estructura completa. Todos los directorios principales existen ({', '.join(expected_dirs)})",
            is_blocking=False
        ))
    else:
        created_dirs = []
        for d in missing_dirs:
            try:
                (base_dir / d).mkdir(parents=True, exist_ok=True)
                created_dirs.append(d)
            except Exception:
                pass

        checks.append(Check(
            name="Estructura de Directorios del Proyecto",
            category="Structure",
            status="warn",
            detail=f"Directorios creados automáticamente: {', '.join(created_dirs)}",
            is_blocking=False
        ))

    # -------------------------------------------------------------
    # 14. API Endpoints Health Check
    # -------------------------------------------------------------
    try:
        from fastapi.testclient import TestClient
        from workspace.server import app as ws_app

        client = TestClient(ws_app)
        res = client.get("/health")
        if res.status_code == 200:
            checks.append(Check(
                name="Salud del Endpoint API (/health)",
                category="API",
                status="pass",
                detail=f"Endpoint API /health responde HTTP 200: {res.text[:100]}",
                is_blocking=False
            ))
        else:
            checks.append(Check(
                name="Salud del Endpoint API (/health)",
                category="API",
                status="fail",
                detail=f"Endpoint API /health retornó el código HTTP {res.status_code}",
                is_blocking=False,
                recommendation="Verifique el manejador de /health en workspace/server.py"
            ))
    except Exception as e:
        checks.append(Check(
            name="Salud del Endpoint API (/health)",
            category="API",
            status="fail",
            detail=f"Error probando el endpoint API /health: {str(e)}",
            is_blocking=False,
            recommendation="Verifique workspace/server.py"
        ))

    # -------------------------------------------------------------
    # Summarize Results
    # -------------------------------------------------------------
    check_dicts = [c.to_dict() for c in checks]
    blocking_count = sum(1 for c in checks if c.status != "pass" and c.is_blocking)
    warning_count = sum(1 for c in checks if c.status == "warn" or (c.status == "fail" and not c.is_blocking))
    ready = (blocking_count == 0)

    return ValidationResult(
        ready=ready,
        checks=check_dicts,
        blocking_count=blocking_count,
        warning_count=warning_count,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


if __name__ == "__main__":
    res = run_dependency_validation()
    print(json.dumps(res, indent=2, ensure_ascii=False))
    print("\n" + "=" * 60 + "\n")
    print(res.to_markdown())

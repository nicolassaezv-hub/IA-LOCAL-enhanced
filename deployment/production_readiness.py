"""
Production Readiness Report — Valida el entorno completo de produccion.

Verifica 15+ aspectos criticos:
  1.  Version de Python
  2.  Dependencias instaladas (requirements.txt)
  3.  Variables de entorno (astra.env)
  4.  Acceso a la base de datos
  5.  Disponibilidad de modelos
  6.  Existencia de datasets (CSVs)
  7.  Scheduler funcional
  8.  Servicios systemd
  9.  Temporizadores (timers)
  10. Workspace responde
  11. API responde
  12. Conectividad con proveedor de datos
  13. Permisos de escritura
  14. Estructura de directorios
  15. Logs y rotacion
  16. Memoria/Recursos del sistema

Emite un estado global: READY FOR PRODUCTION / READY WITH WARNINGS / NOT READY
"""
from __future__ import annotations

import os
import sys
import json
import time
import platform
import subprocess
import importlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

_BASE = Path(__file__).resolve().parent.parent

# Dependencias criticas y opcionales
_CRITICAL_DEPS = [
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("sklearn", "scikit-learn"),
    ("xgboost", "xgboost"),
    ("lightgbm", "lightgbm"),
    ("optuna", "optuna"),
    ("requests", "requests"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("colorama", "colorama"),
    ("rich", "rich"),
    ("orjson", "orjson"),
    ("filelock", "filelock"),
    ("psutil", "psutil"),
]

_OPTIONAL_DEPS = [
    ("yfinance", "yfinance"),
    ("redis", "redis"),
    ("faiss", "faiss-cpu"),
    ("torch", "torch"),
    ("tensorflow", "tensorflow"),
    ("MetaTrader5", "MetaTrader5"),
    ("openai", "openai"),
]

# Directorios esperados
_EXPECTED_DIRS = [
    "CSVs", "CSVs/H1", "CSVs/H4", "CSVs/D1",
    "models", "models/forex",
    "memory_db",
    "logs",
    "reports",
    "reports/deployment",
    "workspace", "workspace/static", "workspace/static/js", "workspace/static/css",
    "scheduler",
    "forex", "forex/prediction", "forex/data", "forex/portfolio",
    "infra", "infra/db", "infra/config",
    "deployment",
    "constitution", "evolution", "feedback",
]


@dataclass
class ReadinessCheck:
    """Resultado de un check de readiness."""
    category: str
    check: str
    status: str  # "pass" | "fail" | "warn"
    detail: str = ""
    recommendation: str = ""


@dataclass
class ProductionReadinessReport:
    """Informe de readiness del entorno de produccion."""
    timestamp: str = ""
    checks: list[ReadinessCheck] = field(default_factory=list)
    global_status: str = "pending"
    summary: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status == "pass")

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if c.status == "fail")

    @property
    def warned(self) -> int:
        return sum(1 for c in self.checks if c.status == "warn")

    def add_check(self, check: ReadinessCheck):
        self.checks.append(check)

    def finalize(self):
        if self.failed > 0:
            self.global_status = "NOT READY"
        elif self.warned > 0:
            self.global_status = "READY WITH WARNINGS"
        else:
            self.global_status = "READY FOR PRODUCTION"

        self.summary = {
            "total_checks": len(self.checks),
            "passed": self.passed,
            "failed": self.failed,
            "warned": self.warned,
            "global_status": self.global_status,
        }

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "global_status": self.global_status,
            "summary": self.summary,
            "checks": [
                {
                    "category": c.category,
                    "check": c.check,
                    "status": c.status,
                    "detail": c.detail,
                    "recommendation": c.recommendation,
                }
                for c in self.checks
            ],
        }

    def to_markdown(self) -> str:
        icons = {"pass": "PASS", "fail": "FAIL", "warn": "WARN"}

        lines = [
            f"# Production Readiness Report",
            f"",
            f"**Fecha:** {self.timestamp}",
            f"**Estado global:** {self.global_status}",
            f"",
            f"| Metrica | Valor |",
            f"|---------|-------|",
            f"| Checks totales | {len(self.checks)} |",
            f"| Pasados | {self.passed} |",
            f"| Fallidos | {self.failed} |",
            f"| Warnings | {self.warned} |",
            f"",
            f"---",
            f"",
        ]

        # Agrupar por categoria
        categories = {}
        for c in self.checks:
            categories.setdefault(c.category, []).append(c)

        for cat, checks in categories.items():
            lines.append(f"## {cat}")
            lines.append(f"")
            for c in checks:
                icon = icons.get(c.status, c.status.upper())
                lines.append(f"### {c.check}")
                lines.append(f"")
                lines.append(f"- **Estado:** {icon}")
                lines.append(f"- **Detalle:** {c.detail}")
                if c.recommendation:
                    lines.append(f"- **Recomendacion:** {c.recommendation}")
                lines.append("")

        lines.append("---")
        lines.append("")

        if self.global_status == "READY FOR PRODUCTION":
            lines.append("## Conclusion")
            lines.append("")
            lines.append("El sistema esta listo para produccion. Todos los checks criticos pasaron.")
        elif self.global_status == "READY WITH WARNINGS":
            lines.append("## Conclusion")
            lines.append("")
            lines.append("El sistema esta listo con advertencias. Los componentes criticos funcionan,")
            lines.append("pero hay warnings que deberian revisarse:")
            failed_items = [c.check for c in self.checks if c.status == "warn"]
            for item in failed_items:
                lines.append(f"  - {item}")
        else:
            lines.append("## Conclusion")
            lines.append("")
            lines.append("El sistema NO esta listo para produccion. Los siguientes checks fallaron:")
            failed_items = [(c.check, c.recommendation) for c in self.checks if c.status == "fail"]
            for check_name, rec in failed_items:
                lines.append(f"  - **{check_name}**: {rec}")

        return "\n".join(lines)


def _try_import(mod_name: str) -> tuple[bool, str]:
    try:
        m = importlib.import_module(mod_name)
        version = getattr(m, "__version__", "OK")
        return True, version
    except ImportError:
        return False, "No instalado"
    except Exception as e:
        return False, f"Error: {e}"


def run_production_readiness() -> ProductionReadinessReport:
    """Ejecuta todos los checks de readiness y retorna el informe completo."""
    report = ProductionReadinessReport()

    # ── 1. Entorno Python ────────────────────────────────────
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    report.add_check(ReadinessCheck(
        category="1. Entorno Python",
        check="Version de Python",
        status="pass" if py_ok else "fail",
        detail=f"Python {py_version} en {platform.system()} {platform.machine()}",
        recommendation="" if py_ok else "Actualiza a Python 3.10+ (recomendado 3.11)",
    ))

    # ── 2. Dependencias instaladas ───────────────────────────
    missing_critical = []
    for mod, label in _CRITICAL_DEPS:
        ok, ver = _try_import(mod)
        status = "pass" if ok else "fail"
        if not ok:
            missing_critical.append(label)
        report.add_check(ReadinessCheck(
            category="2. Dependencias",
            check=f"{label} ({mod})",
            status=status,
            detail=ver if ok else "No instalado",
            recommendation="" if ok else f"pip install {label}",
        ))

    for mod, label in _OPTIONAL_DEPS:
        ok, ver = _try_import(mod)
        if ok:
            report.add_check(ReadinessCheck(
                category="2. Dependencias",
                check=f"{label} (opcional)",
                status="pass",
                detail=f"Instalado ({ver})",
            ))
        else:
            report.add_check(ReadinessCheck(
                category="2. Dependencias",
                check=f"{label} (opcional)",
                status="warn",
                detail="No instalado (opcional)",
                recommendation=f"Opcional: pip install {label} si necesitas esta funcionalidad",
            ))

    # ── 3. Variables de entorno ──────────────────────────────
    env_path = _BASE / "infra" / "config" / "astra.env"
    env_exists = env_path.exists()
    report.add_check(ReadinessCheck(
        category="3. Configuracion",
        check="Archivo astra.env",
        status="pass" if env_exists else "warn",
        detail=str(env_path) if env_exists else "No encontrado",
        recommendation="" if env_exists else f"Copia infra/config/astra.env.example a infra/config/astra.env y edita los valores",
    ))

    # API keys
    groq_key = os.getenv("GROQ_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    has_any_key = bool(groq_key or openai_key)
    report.add_check(ReadinessCheck(
        category="3. Configuracion",
        check="API Keys (Groq/OpenAI)",
        status="pass" if has_any_key else "warn",
        detail=f"Groq: {'configurada' if groq_key else 'vacia'} | OpenAI: {'configurada' if openai_key else 'vacia'}",
        recommendation="" if has_any_key else "Configura GROQ_API_KEY o OPENAI_API_KEY en astra.env para usar el chat con LLM",
    ))

    # ── 4. Base de datos ──────────────────────────────────────
    try:
        from infra.db.database import get_database
        db = get_database()
        db_engine = getattr(db, "engine", getattr(db, "_engine", "unknown"))
        symbols = db.get_supported_symbols()
        report.add_check(ReadinessCheck(
            category="4. Base de datos",
            check="Conexion y inicializacion",
            status="pass",
            detail=f"Engine: {db_engine} | Simbolos: {len(symbols)} | Tablas: OK",
        ))
    except Exception as e:
        report.add_check(ReadinessCheck(
            category="4. Base de datos",
            check="Conexion y inicializacion",
            status="fail",
            detail=f"Error: {e}",
            recommendation="Ejecuta `python astra.py` para inicializar la base de datos",
        ))

    # ── 5. Modelos disponibles ────────────────────────────────
    models_dir = _BASE / "models" / "forex"
    if models_dir.exists():
        pkl_files = list(models_dir.glob("*.pkl"))
        latest_files = [f for f in pkl_files if f.name.startswith("latest_")]
        report.add_check(ReadinessCheck(
            category="5. Modelos",
            check="Modelos entrenados",
            status="pass" if latest_files else "warn",
            detail=f"{len(pkl_files)} archivos .pkl | {len(latest_files)} modelos 'latest'",
            recommendation="" if latest_files else "Entrena al menos un modelo: `full forex CSVs/H4/USDJPY.csv`",
        ))
    else:
        report.add_check(ReadinessCheck(
            category="5. Modelos",
            check="Directorio de modelos",
            status="warn",
            detail="models/forex no existe",
            recommendation="El directorio se creara automaticamente al entrenar el primer modelo",
        ))

    # ── 6. Datasets (CSVs) ────────────────────────────────────
    csvs_dir = _BASE / "CSVs"
    csv_count = 0
    if csvs_dir.exists():
        csv_count = len(list(csvs_dir.rglob("*.csv")))
    report.add_check(ReadinessCheck(
        category="6. Datasets",
        check="Archivos CSV disponibles",
        status="pass" if csv_count > 0 else "warn",
        detail=f"{csv_count} archivos CSV en CSVs/",
        recommendation="" if csv_count > 0 else "Genera CSVs con: `generar csvs forex H1,H4,D1` o descarga datos manualmente",
    ))

    # ── 7. Scheduler ─────────────────────────────────────────
    try:
        from scheduler.autonomous_scheduler import get_status
        from infra.db.database import get_database
        db = get_database()
        status = get_status(db)
        sched_ok = status.get("healthy", False)
        report.add_check(ReadinessCheck(
            category="7. Scheduler",
            check="Estado del scheduler",
            status="pass" if sched_ok else "warn",
            detail=f"Healthy: {sched_ok} | Symbols: {status.get('symbols_active', 0)} | Datasets: {status.get('datasets_ready', 0)}",
            recommendation="" if sched_ok else "Ejecuta `python astra.py` y luego `scheduler start` para activar el scheduler",
        ))
    except Exception as e:
        report.add_check(ReadinessCheck(
            category="7. Scheduler",
            check="Estado del scheduler",
            status="fail",
            detail=f"Error: {e}",
            recommendation="Verifica que scheduler/autonomous_scheduler.py este accesible",
        ))

    # ── 8. Servicios systemd ─────────────────────────────────
    systemd_dir = _BASE / "infra" / "systemd"
    if systemd_dir.exists():
        services = list(systemd_dir.glob("*.service"))
        timers = list(systemd_dir.glob("*.timer"))
        report.add_check(ReadinessCheck(
            category="8. Servicios systemd",
            check="Archivos de servicio",
            status="pass" if services else "warn",
            detail=f"{len(services)} .service | {len(timers)} .timer",
            recommendation="" if services else "Crea archivos .service en infra/systemd/ para despliegue automatico",
        ))

        # Verificar si estan activos (solo en Linux)
        if platform.system() == "Linux":
            for svc in services:
                svc_name = svc.stem
                try:
                    result = subprocess.run(
                        ["systemctl", "is-active", svc_name],
                        capture_output=True, text=True, timeout=5
                    )
                    is_active = result.returncode == 0
                    report.add_check(ReadinessCheck(
                        category="8. Servicios systemd",
                        check=f"systemd: {svc_name}",
                        status="pass" if is_active else "warn",
                        detail=result.stdout.strip() if result.stdout else "inactive",
                        recommendation="" if is_active else f"sudo systemctl start {svc_name} && sudo systemctl enable {svc_name}",
                    ))
                except Exception:
                    report.add_check(ReadinessCheck(
                        category="8. Servicios systemd",
                        check=f"systemd: {svc_name}",
                        status="warn",
                        detail="No se pudo verificar (posiblemente no ejecutandose como root)",
                    ))
        else:
            report.add_check(ReadinessCheck(
                category="8. Servicios systemd",
                check="systemd activo",
                status="warn",
                detail="systemd solo disponible en Linux",
                recommendation="En Windows/Mac: usa los scripts en infra/ para iniciar el scheduler manualmente",
            ))
    else:
        report.add_check(ReadinessCheck(
            category="8. Servicios systemd",
            check="Directorio systemd",
            status="warn",
            detail="infra/systemd/ no existe",
        ))

    # ── 9. Workspace ─────────────────────────────────────────
    try:
        from fastapi.testclient import TestClient
        from workspace.server import app
        c = TestClient(app)
        r = c.get("/")
        ws_ok = r.status_code == 200 and len(r.content) > 1000
        report.add_check(ReadinessCheck(
            category="9. Workspace y API",
            check="Workspace HTML responde",
            status="pass" if ws_ok else "fail",
            detail=f"HTTP {r.status_code} | {len(r.content)} bytes",
            recommendation="" if ws_ok else "Verifica que workspace/static/index.html existe",
        ))

        r2 = c.get("/health")
        api_ok = r2.status_code == 200
        report.add_check(ReadinessCheck(
            category="9. Workspace y API",
            check="API /health responde",
            status="pass" if api_ok else "fail",
            detail=f"HTTP {r2.status_code}",
            recommendation="" if api_ok else "El servidor FastAPI no responde. Inicia con: uvicorn workspace.server:app",
        ))

        r3 = c.get("/api/datasets/status")
        ds_ok = r3.status_code == 200
        report.add_check(ReadinessCheck(
            category="9. Workspace y API",
            check="API /api/datasets/status",
            status="pass" if ds_ok else "warn",
            detail=f"HTTP {r3.status_code}",
            recommendation="" if ds_ok else "Verifica que la DB esta inicializada",
        ))
    except Exception as e:
        report.add_check(ReadinessCheck(
            category="9. Workspace y API",
            check="Servidor FastAPI",
            status="warn",
            detail=f"Error: {e}",
            recommendation="Inicia el servidor: uvicorn workspace.server:app --host 0.0.0.0 --port 8000",
        ))

    # ── 10. Conectividad con proveedor de datos ───────────────
    # Yahoo Finance
    try:
        ok, _ = _try_import("yfinance")
        if ok:
            import yfinance as yf
            # Test rapido: descargar 1 vela
            ticker = yf.Ticker("EURUSD=X")
            hist = ticker.history(period="1d")
            yf_ok = len(hist) > 0
            report.add_check(ReadinessCheck(
                category="10. Proveedor de datos",
                check="Yahoo Finance",
                status="pass" if yf_ok else "warn",
                detail=f"Conectividad: {'OK' if yf_ok else 'Sin datos'}",
                recommendation="" if yf_ok else "Verifica conexion a internet o firewall",
            ))
        else:
            report.add_check(ReadinessCheck(
                category="10. Proveedor de datos",
                check="Yahoo Finance",
                status="warn",
                detail="yfinance no instalado",
                recommendation="pip install yfinance para descargar datos automaticamente",
            ))
    except Exception as e:
        report.add_check(ReadinessCheck(
            category="10. Proveedor de datos",
            check="Yahoo Finance",
            status="warn",
            detail=f"Error de conectividad: {e}",
            recommendation="Verifica conexion a internet. Como alternativa, usa CSVs locales",
        ))

    # MT5
    try:
        ok, _ = _try_import("MetaTrader5")
        if ok:
            import MetaTrader5 as mt5
            mt5_ok = mt5.initialize()
            report.add_check(ReadinessCheck(
                category="10. Proveedor de datos",
                check="MetaTrader 5",
                status="pass" if mt5_ok else "warn",
                detail=f"MT5 inicializado: {mt5_ok}",
                recommendation="" if mt5_ok else "Verifica que MetaTrader 5 esta corriendo y las credenciales son correctas",
            ))
            mt5.shutdown()
        else:
            report.add_check(ReadinessCheck(
                category="10. Proveedor de datos",
                check="MetaTrader 5",
                status="warn",
                detail="MetaTrader5 no instalado (solo Windows)",
                recommendation="Opcional: instala MetaTrader5 en Windows para datos en tiempo real",
            ))
    except Exception:
        report.add_check(ReadinessCheck(
            category="10. Proveedor de datos",
            check="MetaTrader 5",
            status="warn",
            detail="No disponible (posiblemente no es Windows)",
        ))

    # ── 11. Permisos de escritura ─────────────────────────────
    write_dirs = ["CSVs", "models", "memory_db", "logs", "reports"]
    for dirname in write_dirs:
        dirpath = _BASE / dirname
        if not dirpath.exists():
            dirpath.mkdir(parents=True, exist_ok=True)
        try:
            test_file = dirpath / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            report.add_check(ReadinessCheck(
                category="11. Permisos",
                check=f"Escritura: {dirname}/",
                status="pass",
                detail="Permisos OK",
            ))
        except Exception as e:
            report.add_check(ReadinessCheck(
                category="11. Permisos",
                check=f"Escritura: {dirname}/",
                status="fail",
                detail=f"Sin permisos: {e}",
                recommendation=f"chmod 755 {dirname}/ o verifica el propietario del directorio",
            ))

    # ── 12. Estructura de directorios ────────────────────────
    missing_dirs = []
    for dirname in _EXPECTED_DIRS:
        dirpath = _BASE / dirname
        if not dirpath.exists():
            missing_dirs.append(dirname)

    if missing_dirs:
        report.add_check(ReadinessCheck(
            category="12. Estructura de directorios",
            check="Directorios del proyecto",
            status="warn",
            detail=f"Faltan: {', '.join(missing_dirs)}",
            recommendation="Algunos directorios se crean automaticamente. Si el error persiste, descomprime el ZIP completo",
        ))
    else:
        report.add_check(ReadinessCheck(
            category="12. Estructura de directorios",
            check="Directorios del proyecto",
            status="pass",
            detail=f"Todos los {len(_EXPECTED_DIRS)} directorios existen",
        ))

    # ── 13. Logs y rotacion ───────────────────────────────────
    log_dir = _BASE / "logs"
    log_files = list(log_dir.glob("*.log")) if log_dir.exists() else []
    logrotate = _BASE / "infra" / "logging" / "logrotate.conf"
    report.add_check(ReadinessCheck(
        category="13. Logs",
        check="Directorio de logs",
        status="pass" if log_dir.exists() else "warn",
        detail=f"{len(log_files)} archivos de log",
        recommendation="" if log_dir.exists() else "Crea logs/ manualmente",
    ))
    report.add_check(ReadinessCheck(
        category="13. Logs",
        check="Configuracion logrotate",
        status="pass" if logrotate.exists() else "warn",
        detail=str(logrotate) if logrotate.exists() else "No encontrado",
        recommendation="" if logrotate.exists() else "Configura logrotate para evitar que los logs crezcan indefinidamente",
    ))

    # ── 14. Recursos del sistema ──────────────────────────────
    try:
        import psutil
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(_BASE))
        report.add_check(ReadinessCheck(
            category="14. Recursos del sistema",
            check="Memoria RAM",
            status="pass" if mem.available > 512 * 1024 * 1024 else "warn",
            detail=f"{mem.available / 1024**3:.1f} GB disponibles / {mem.total / 1024**3:.1f} GB total",
            recommendation="" if mem.available > 512 * 1024 * 1024 else "Memoria baja. Cierra aplicaciones innecesarias",
        ))
        report.add_check(ReadinessCheck(
            category="14. Recursos del sistema",
            check="Espacio en disco",
            status="pass" if disk.free > 1 * 1024**3 else "warn",
            detail=f"{disk.free / 1024**3:.1f} GB libres / {disk.total / 1024**3:.1f} GB total",
            recommendation="" if disk.free > 1 * 1024**3 else "Espacio en disco bajo. Limpia logs y backups antiguos",
        ))
    except Exception:
        report.add_check(ReadinessCheck(
            category="14. Recursos del sistema",
            check="Monitorizacion (psutil)",
            status="warn",
            detail="psutil no disponible",
            recommendation="pip install psutil para monitoreo del sistema",
        ))

    # Finalizar
    report.finalize()
    return report

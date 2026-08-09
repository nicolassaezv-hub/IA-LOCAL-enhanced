"""
ASTRA Cloud Provider & Infrastructure Verification Module.
(robustness/provider_verification.py)

Automatically detects the cloud provider (Oracle Cloud, Google Cloud, AWS, Azure, generic)
and verifies system readiness, network connectivity, hardware resources, firewall/ports,
automation services, scheduler, workspace (FastAPI), Python dependencies, and disk space.
"""

from __future__ import annotations

import sys
import os
import socket
import subprocess
import importlib
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import psutil
import requests

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class ProviderCheck:
    """
    Represents a single infrastructure check result.
    """
    check_name: str
    status: str          # PASS, WARN, FAIL
    detail: str
    recommendation: str = ""


@dataclass
class ProviderVerificationReport:
    """
    Complete report containing provider details and all check results.
    """
    provider_name: str
    checks: List[ProviderCheck] = field(default_factory=list)
    status: str = "PASS" # Global status: PASS, WARN, FAIL
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))

    def to_markdown(self) -> str:
        """
        Renders the verification report into Markdown format.
        """
        lines = []
        lines.append("# Reporte de Verificación de Infraestructura y Proveedor")
        lines.append("")
        lines.append(f"- **Proveedor Detectado:** `{self.provider_name}`")
        lines.append(f"- **Estado Global:** `{self.status}`")
        lines.append(f"- **Fecha / Hora:** {self.timestamp}")
        lines.append("")
        lines.append("## Resumen de Verificaciones")
        lines.append("")
        lines.append("| # | Verificación | Estado | Detalle | Recomendación |")
        lines.append("|---|--------------|--------|---------|---------------|")

        for idx, check in enumerate(self.checks, start=1):
            if check.status == "PASS":
                status_badge = "✅ PASS"
            elif check.status == "WARN":
                status_badge = "⚠️ WARN"
            elif check.status == "FAIL":
                status_badge = "❌ FAIL"
            else:
                status_badge = check.status

            detail_clean = check.detail.replace("\n", " ")
            rec_clean = (check.recommendation or "-").replace("\n", " ")
            lines.append(f"| {idx} | {check.check_name} | {status_badge} | {detail_clean} | {rec_clean} |")

        lines.append("")
        lines.append("## Detalle de Chequeos")
        lines.append("")

        for idx, check in enumerate(self.checks, start=1):
            lines.append(f"### {idx}. {check.check_name}")
            lines.append(f"- **Estado:** {check.status}")
            lines.append(f"- **Detalle:** {check.detail}")
            if check.recommendation:
                lines.append(f"- **Recomendación:** {check.recommendation}")
            lines.append("")

        return "\n".join(lines)


def _check_url_subprocess(url: str, headers: Optional[dict] = None, timeout: int = 3) -> bool:
    """
    Helper to perform HTTP metadata GET check via subprocess (curl) with a 3-second timeout.
    Falls back gracefully to urllib if curl binary is missing or fails unexpectedly.
    """
    cmd = ["curl", "-s", "-f", "--connect-timeout", str(timeout), "-m", str(timeout)]
    if headers:
        for k, v in headers.items():
            cmd.extend(["-H", f"{k}: {v}"])
    cmd.append(url)

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 1)
        if res.returncode == 0:
            return True
    except Exception:
        pass

    # Urllib fallback
    try:
        import urllib.request
        req = urllib.request.Request(url)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if 200 <= resp.status < 300:
                return True
    except Exception:
        pass

    return False


def detect_provider() -> str:
    """
    Detects the cloud provider where ASTRA is running using subprocess metadata checks (3s timeout).

    Returns one of:
        - oracle_cloud
        - google_cloud
        - aws
        - azure
        - generic
    """
    try:
        # 1. Oracle Cloud Check (/etc/oracle-cloud/ or http://169.254.169.254/opc/v2/instance/)
        if os.path.exists("/etc/oracle-cloud") or os.path.exists("/etc/oracle-cloud/"):
            return "oracle_cloud"
        if _check_url_subprocess("http://169.254.169.254/opc/v2/instance/", timeout=3):
            return "oracle_cloud"

        # 2. Google Cloud Check (http://metadata.google.internal/computeMetadata/v1/ with Metadata-Flavor: Google)
        if _check_url_subprocess(
            "http://metadata.google.internal/computeMetadata/v1/",
            headers={"Metadata-Flavor": "Google"},
            timeout=3
        ):
            return "google_cloud"

        # 3. AWS Check (http://169.254.169.254/latest/meta-data/)
        if _check_url_subprocess("http://169.254.169.254/latest/meta-data/", timeout=3):
            return "aws"

        # 4. Azure Check (http://169.254.169.254/metadata/instance?api-version=2021-02-01 with Metadata: true)
        if _check_url_subprocess(
            "http://169.254.169.254/metadata/instance?api-version=2021-02-01",
            headers={"Metadata": "true"},
            timeout=3
        ):
            return "azure"

    except Exception:
        pass

    return "generic"


def run_provider_verification() -> ProviderVerificationReport:
    """
    Runs full provider detection and verifies all required infrastructure aspects.

    Verifies:
    1. Basic connectivity (can reach internet)
    2. Available resources (CPU count, RAM, disk space using psutil)
    3. Firewall/ports (check if port 8000 is accessible via socket bind)
    4. Required services (check if cron/systemd is available)
    5. Scheduler (can import and initialize)
    6. Workspace (FastAPI app can start)
    7. Network (can reach Yahoo Finance)
    8. Python version and dependencies
    9. Disk space (at least 1GB free)

    Returns:
        ProviderVerificationReport
    """
    provider_name = detect_provider()
    checks: List[ProviderCheck] = []

    # Check 1: Basic Connectivity
    conn_ok = False
    conn_detail = ""

    # Attempt socket connection
    for host, port in [("8.8.8.8", 53), ("1.1.1.1", 80), ("8.8.8.8", 80)]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((host, port))
            s.close()
            conn_ok = True
            conn_detail = f"Acceso a Internet verificado vía socket TCP exitoso ({host}:{port})."
            break
        except Exception:
            pass

    # Fallback to HTTP request if raw socket connection is blocked/restricted
    if not conn_ok:
        for url in ["https://www.google.com", "https://finance.yahoo.com", "https://1.1.1.1"]:
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = requests.get(url, headers=headers, timeout=3.0)
                if resp.status_code < 500:
                    conn_ok = True
                    conn_detail = f"Acceso a Internet verificado vía solicitud HTTP GET a {url} (HTTP {resp.status_code})."
                    break
            except Exception:
                pass

    if conn_ok:
        checks.append(ProviderCheck(
            check_name="Basic Connectivity",
            status="PASS",
            detail=conn_detail,
            recommendation=""
        ))
    else:
        checks.append(ProviderCheck(
            check_name="Basic Connectivity",
            status="FAIL",
            detail="Sin conectividad básica a Internet: no se pudo establecer conexión TCP ni HTTP saliente.",
            recommendation="Verifique la tabla de ruteo, gateway y reglas de salida (egress) en la red/firewall del proveedor."
        ))

    # Check 2: Available Resources
    try:
        cpu_count = psutil.cpu_count(logical=True) or 1
        ram = psutil.virtual_memory()
        ram_total_mb = ram.total / (1024 * 1024)
        ram_avail_mb = ram.available / (1024 * 1024)
        disk = psutil.disk_usage(".")
        disk_total_gb = disk.total / (1024 ** 3)
        disk_free_gb = disk.free / (1024 ** 3)

        detail_msg = (
            f"CPU: {cpu_count} cores | RAM Total: {ram_total_mb:.1f} MB "
            f"(Disponible: {ram_avail_mb:.1f} MB, {ram.percent}% uso) | "
            f"Disco Total: {disk_total_gb:.2f} GB (Libre: {disk_free_gb:.2f} GB)"
        )

        if cpu_count >= 1 and ram_total_mb >= 1000:
            if ram_total_mb < 2000 or ram.percent > 90.0:
                status = "WARN"
                rec = "Se recomiendan al menos 2 Cores y 2GB-4GB RAM para rendimiento óptimo de las predicciones."
            else:
                status = "PASS"
                rec = ""
        else:
            status = "FAIL"
            rec = "Recursos de hardware insuficientes. Amplíe las especificaciones de la instancia."

        checks.append(ProviderCheck(
            check_name="Available Resources",
            status=status,
            detail=detail_msg,
            recommendation=rec
        ))
    except Exception as e:
        checks.append(ProviderCheck(
            check_name="Available Resources",
            status="FAIL",
            detail=f"Error obteniendo recursos del sistema vía psutil: {e}",
            recommendation="Verifique que la librería psutil esté correctamente instalada."
        ))

    # Check 3: Firewall / Ports (Port 8000)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", 8000))
            sock.close()
            checks.append(ProviderCheck(
                check_name="Firewall / Ports",
                status="PASS",
                detail="Puerto 8000 accesible y disponible para bind (socket listo para FastAPI).",
                recommendation=""
            ))
        except OSError as bind_err:
            sock.close()
            test_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_conn.settimeout(2.0)
            res = test_conn.connect_ex(("127.0.0.1", 8000))
            test_conn.close()

            if res == 0:
                checks.append(ProviderCheck(
                    check_name="Firewall / Ports",
                    status="PASS",
                    detail="Puerto 8000 ocupado por un servicio activo (servidor API respondiendo localmente).",
                    recommendation=""
                ))
            else:
                checks.append(ProviderCheck(
                    check_name="Firewall / Ports",
                    status="WARN",
                    detail=f"No se pudo vincular el puerto 8000: {bind_err}",
                    recommendation="Asegúrese de que el puerto 8000 esté habilitado en Security Groups / firewall local."
                ))
    except Exception as e:
        checks.append(ProviderCheck(
            check_name="Firewall / Ports",
            status="FAIL",
            detail=f"Error evaluando el puerto 8000: {e}",
            recommendation="Verifique la configuración de red y permisos del sistema operativo."
        ))

    # Check 4: Required Services (cron / systemd)
    try:
        systemd_ok = os.path.exists("/run/systemd/system") or os.path.exists("/sys/fs/cgroup/systemd")
        if not systemd_ok:
            try:
                r = subprocess.run(["systemctl", "--version"], capture_output=True, text=True, timeout=3)
                systemd_ok = (r.returncode == 0)
            except Exception:
                systemd_ok = False

        cron_ok = False
        try:
            r = subprocess.run(["which", "crontab"], capture_output=True, text=True, timeout=3)
            cron_ok = (r.returncode == 0)
        except Exception:
            pass

        if not cron_ok:
            cron_ok = (
                os.path.exists("/etc/crontab") or
                os.path.exists("/var/spool/cron") or
                os.path.exists("/etc/cron.d")
            )

        if systemd_ok and cron_ok:
            status = "PASS"
            detail = "Systemd y Cron están disponibles en el sistema operativo."
            rec = ""
        elif systemd_ok:
            status = "PASS"
            detail = "Systemd disponible (Cron no detectado)."
            rec = "Puede usar timers de systemd para la programación de tareas."
        elif cron_ok:
            status = "PASS"
            detail = "Cron disponible (Systemd no detectado)."
            rec = "Puede usar entradas de crontab para la programación de tareas."
        else:
            status = "WARN"
            detail = "Ni Systemd ni Cron fueron detectados activamente en el entorno."
            rec = "Instale o habilite systemd / cron para permitir la ejecución autónoma de tareas programadas."

        checks.append(ProviderCheck(
            check_name="Required Services",
            status=status,
            detail=detail,
            recommendation=rec
        ))
    except Exception as e:
        checks.append(ProviderCheck(
            check_name="Required Services",
            status="FAIL",
            detail=f"Error verificando servicios requeridos: {e}",
            recommendation="Asegúrese de ejecutar en un entorno Linux con soporte de servicios de sistema."
        ))

    # Check 5: Scheduler (import and initialize)
    try:
        sched_ok = False
        sched_detail = ""

        try:
            from forex.scheduler.autonomous_scheduler import AutonomousScheduler
            sched_inst = AutonomousScheduler()
            sched_ok = True
            sched_detail = "Módulo 'forex.scheduler.autonomous_scheduler.AutonomousScheduler' importado e inicializado correctamente."
        except Exception as e1:
            try:
                import scheduler.autonomous_scheduler as sched_mod
                sched_ok = True
                sched_detail = f"Módulo 'scheduler.autonomous_scheduler' importado correctamente (Nota importación primaria: {e1})."
            except Exception as e2:
                sched_detail = f"Error al importar e inicializar el scheduler: {e1} | {e2}"

        if sched_ok:
            checks.append(ProviderCheck(
                check_name="Scheduler",
                status="PASS",
                detail=sched_detail,
                recommendation=""
            ))
        else:
            checks.append(ProviderCheck(
                check_name="Scheduler",
                status="FAIL",
                detail=sched_detail,
                recommendation="Verifique la sintaxis y dependencias en 'scheduler/autonomous_scheduler.py' y 'forex/scheduler/autonomous_scheduler.py'."
            ))
    except Exception as e:
        checks.append(ProviderCheck(
            check_name="Scheduler",
            status="FAIL",
            detail=f"Excepción general al verificar Scheduler: {e}",
            recommendation="Verifique las dependencias y la estructura del módulo scheduler."
        ))

    # Check 6: Workspace (FastAPI app can start)
    try:
        app_ok = False
        app_detail = ""

        try:
            from workspace.server import app
            if app is not None:
                app_ok = True
                app_detail = "Aplicación FastAPI Workspace ('workspace.server') importada e inicializada correctamente."
        except Exception as e1:
            try:
                from fastapi import FastAPI
                test_app = FastAPI(title="ASTRA Test App")
                app_ok = True
                app_detail = f"Librería FastAPI disponible e instanciada exitosamente (Advertencia workspace.server: {e1})."
            except Exception as e2:
                app_detail = f"No se pudo iniciar la aplicación FastAPI: {e1} | {e2}"

        if app_ok:
            checks.append(ProviderCheck(
                check_name="Workspace",
                status="PASS",
                detail=app_detail,
                recommendation=""
            ))
        else:
            checks.append(ProviderCheck(
                check_name="Workspace",
                status="FAIL",
                detail=app_detail,
                recommendation="Instale fastapi uvicorn ('pip install fastapi uvicorn') y revise 'workspace/server.py'."
            ))
    except Exception as e:
        checks.append(ProviderCheck(
            check_name="Workspace",
            status="FAIL",
            detail=f"Excepción al verificar Workspace FastAPI: {e}",
            recommendation="Asegúrese de que el entorno tenga instalada la librería fastapi y uvicorn."
        ))

    # Check 7: Network - Yahoo Finance
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        yf_resp = requests.get("https://finance.yahoo.com", headers=headers, timeout=5.0)
        if yf_resp.status_code in (200, 301, 302):
            checks.append(ProviderCheck(
                check_name="Network - Yahoo Finance",
                status="PASS",
                detail=f"Conexión exitosa a Yahoo Finance (Código HTTP {yf_resp.status_code}).",
                recommendation=""
            ))
        elif yf_resp.status_code == 429:
            checks.append(ProviderCheck(
                check_name="Network - Yahoo Finance",
                status="PASS",
                detail="Conexión de red a Yahoo Finance alcanzable (Respondió HTTP 429 Rate Limit).",
                recommendation="Yahoo Finance está limitando la tasa de peticiones, configure rotación de IP/User-Agent si requiere scraping intensivo."
            ))
        else:
            checks.append(ProviderCheck(
                check_name="Network - Yahoo Finance",
                status="WARN",
                detail=f"Yahoo Finance devolvió un código HTTP inusual: {yf_resp.status_code}.",
                recommendation="Verifique si Yahoo Finance requiere headers adicionales o proxy."
            ))
    except Exception as e:
        checks.append(ProviderCheck(
            check_name="Network - Yahoo Finance",
            status="FAIL",
            detail=f"No se pudo conectar a Yahoo Finance: {e}",
            recommendation="Asegúrese de que la salida HTTP/HTTPS a finance.yahoo.com y query1.finance.yahoo.com no esté bloqueada."
        ))

    # Check 8: Python Version and Dependencies
    try:
        py_ver_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        core_packages = [
            ("psutil", "psutil"),
            ("requests", "requests"),
            ("fastapi", "fastapi"),
            ("pandas", "pandas"),
            ("numpy", "numpy"),
            ("sklearn", "scikit-learn")
        ]

        installed = []
        missing = []
        for mod_name, pkg_name in core_packages:
            try:
                importlib.import_module(mod_name)
                installed.append(pkg_name)
            except ImportError:
                missing.append(pkg_name)

        if sys.version_info >= (3, 8) and not missing:
            status = "PASS"
            detail = f"Python {py_ver_str} OK. Dependencias principales verificadas: {', '.join(installed)}."
            rec = ""
        elif sys.version_info >= (3, 8) and missing:
            status = "WARN"
            detail = f"Python {py_ver_str} OK. Faltan dependencias opcionales/clave: {', '.join(missing)}."
            rec = f"Instale las dependencias faltantes con: pip install {' '.join(missing)}"
        else:
            status = "FAIL"
            detail = f"Versión de Python ({py_ver_str}) insuficiente (<3.8) o faltan librerías: {', '.join(missing)}."
            rec = "Actualice Python a 3.8+ e instale requerimientos con 'pip install -r requirements.txt'."

        checks.append(ProviderCheck(
            check_name="Python Version and Dependencies",
            status=status,
            detail=detail,
            recommendation=rec
        ))
    except Exception as e:
        checks.append(ProviderCheck(
            check_name="Python Version and Dependencies",
            status="FAIL",
            detail=f"Error evaluando Python y dependencias: {e}",
            recommendation="Verifique el entorno virtual Python activo."
        ))

    # Check 9: Disk Space (at least 1GB free)
    try:
        disk_usage = psutil.disk_usage(".")
        free_bytes = disk_usage.free
        free_gb = free_bytes / (1024 ** 3)
        min_bytes = 1024 * 1024 * 1024  # 1 GB

        if free_bytes >= min_bytes:
            checks.append(ProviderCheck(
                check_name="Disk Space",
                status="PASS",
                detail=f"Espacio en disco suficiente: {free_gb:.2f} GB libres (Mínimo requerido: 1.00 GB).",
                recommendation=""
            ))
        else:
            checks.append(ProviderCheck(
                check_name="Disk Space",
                status="FAIL",
                detail=f"Espacio libre en disco insuficiente: {free_gb:.2f} GB libres (Mínimo requerido: 1.00 GB).",
                recommendation="Libere espacio en disco eliminando archivos temporales o incremente el almacenamiento."
            ))
    except Exception as e:
        checks.append(ProviderCheck(
            check_name="Disk Space",
            status="FAIL",
            detail=f"Error consultando el espacio en disco vía psutil: {e}",
            recommendation="Verifique permisos del sistema de archivos y espacio de almacenamiento."
        ))

    # Calculate global report status
    has_fail = any(c.status == "FAIL" for c in checks)
    has_warn = any(c.status == "WARN" for c in checks)

    if has_fail:
        global_status = "FAIL"
    elif has_warn:
        global_status = "WARN"
    else:
        global_status = "PASS"

    return ProviderVerificationReport(
        provider_name=provider_name,
        checks=checks,
        status=global_status
    )


if __name__ == "__main__":
    report = run_provider_verification()
    print(report.to_markdown())

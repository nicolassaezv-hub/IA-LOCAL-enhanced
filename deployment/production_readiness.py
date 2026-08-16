"""Evidence-based, fail-closed production readiness for ASTRA.

The report is diagnostic and read-only.  It never creates datasets, models,
configuration, databases, or directories.  Provider traffic is performed only
when ``probe_providers=True``.
"""
from __future__ import annotations

import importlib
import os
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from runtime_paths import forex_model_root


_BASE = Path(__file__).resolve().parent.parent

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

_EXPECTED_DIRS = [
    "CSVs", "CSVs/H1", "CSVs/H4", "CSVs/D1",
    "models", "models/forex", "memory_db", "logs", "reports",
    "reports/deployment", "workspace", "scheduler", "forex",
    "forex/prediction", "forex/data", "infra", "infra/config",
    "deployment",
]

_PLACEHOLDER_MARKERS = {
    "dummy", "fake", "mock", "placeholder", "sample", "synthetic", "test",
}


@dataclass
class ReadinessCheck:
    """One evidence item in the production-readiness decision."""

    category: str
    check: str
    status: str  # pass | fail | warn | pending
    detail: str = ""
    recommendation: str = ""
    blocking: bool = False
    evidence_state: str = ""


@dataclass
class ProductionReadinessReport:
    """Structured production-readiness result."""

    timestamp: str = ""
    checks: list[ReadinessCheck] = field(default_factory=list)
    global_status: str = "PENDING"
    status: str = "pending"
    summary: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def passed(self) -> int:
        return sum(check.status == "pass" for check in self.checks)

    @property
    def failed(self) -> int:
        return sum(check.status == "fail" for check in self.checks)

    @property
    def warned(self) -> int:
        return sum(check.status == "warn" for check in self.checks)

    @property
    def pending(self) -> int:
        return sum(check.status == "pending" for check in self.checks)

    @property
    def ready(self) -> bool:
        return self.status in {"ready", "degraded"}

    @property
    def blocking_reasons(self) -> list[str]:
        return [
            f"{check.check}: {check.detail}"
            for check in self.checks
            if check.blocking and check.status in {"fail", "pending"}
        ]

    @property
    def warnings(self) -> list[str]:
        return [
            f"{check.check}: {check.detail}"
            for check in self.checks
            if check.status == "warn"
        ]

    def add_check(self, check: ReadinessCheck) -> None:
        self.checks.append(check)

    def finalize(self) -> None:
        blocking_failures = any(
            check.blocking and check.status == "fail" for check in self.checks
        )
        blocking_pending = any(
            check.blocking and check.status == "pending" for check in self.checks
        )
        if blocking_failures:
            self.global_status = "NOT READY"
            self.status = "error"
        elif blocking_pending:
            self.global_status = "PENDING"
            self.status = "pending"
        elif self.warned:
            self.global_status = "READY WITH WARNINGS"
            self.status = "degraded"
        else:
            self.global_status = "READY FOR PRODUCTION"
            self.status = "ready"

        self.summary = {
            "ready": self.ready,
            "status": self.status,
            "total_checks": len(self.checks),
            "passed": self.passed,
            "failed": self.failed,
            "warned": self.warned,
            "pending": self.pending,
            "blocking_count": len(self.blocking_reasons),
            "global_status": self.global_status,
        }

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "ready": self.ready,
            "status": self.status,
            "global_status": self.global_status,
            "summary": self.summary,
            "blocking_reasons": self.blocking_reasons,
            "warnings": self.warnings,
            "checks": [
                {
                    "category": check.category,
                    "check": check.check,
                    "status": check.status,
                    "detail": check.detail,
                    "recommendation": check.recommendation,
                    "blocking": check.blocking,
                    "evidence_state": check.evidence_state,
                }
                for check in self.checks
            ],
        }

    def to_markdown(self) -> str:
        icons = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "pending": "PENDING"}
        lines = [
            "# Production Readiness Report",
            "",
            f"**Fecha:** {self.timestamp}",
            f"**Estado global:** {self.global_status}",
            f"**Ready:** {self.ready}",
            "",
            "| Métrica | Valor |",
            "|---------|-------|",
            f"| Checks totales | {len(self.checks)} |",
            f"| Pasados | {self.passed} |",
            f"| Fallidos | {self.failed} |",
            f"| Pendientes | {self.pending} |",
            f"| Warnings | {self.warned} |",
            f"| Bloqueos | {len(self.blocking_reasons)} |",
            "",
        ]
        categories: dict[str, list[ReadinessCheck]] = {}
        for check in self.checks:
            categories.setdefault(check.category, []).append(check)
        for category, checks in categories.items():
            lines.extend([f"## {category}", ""])
            for check in checks:
                lines.extend([
                    f"### {check.check}",
                    "",
                    f"- **Estado:** {icons.get(check.status, check.status.upper())}",
                    f"- **Bloqueante:** {'sí' if check.blocking else 'no'}",
                    f"- **Detalle:** {check.detail}",
                ])
                if check.evidence_state:
                    lines.append(f"- **Evidencia:** {check.evidence_state}")
                if check.recommendation:
                    lines.append(f"- **Recomendación:** {check.recommendation}")
                lines.append("")

        lines.extend(["---", "", "## Conclusión", ""])
        if self.ready:
            lines.append(
                "La evidencia crítica está completa; revise las advertencias no bloqueantes."
            )
        else:
            lines.append("ASTRA no está listo para producción.")
            for reason in self.blocking_reasons:
                lines.append(f"- {reason}")
        return "\n".join(lines)


def _try_import(mod_name: str) -> tuple[bool, str]:
    try:
        module = importlib.import_module(mod_name)
        return True, str(getattr(module, "__version__", "OK"))
    except ImportError:
        return False, "No instalado"
    except Exception as exc:
        return False, f"Error: {exc}"


def _contains_placeholder_marker(path: Path, metadata: dict | None = None) -> str | None:
    file_tokens = {token for token in path.stem.lower().replace("-", "_").split("_") if token}
    matches = sorted(file_tokens & _PLACEHOLDER_MARKERS)
    if matches:
        return f"artifact filename contains marker {matches[0]!r}"

    metadata = metadata or {}
    for key in ("source", "provenance", "artifact_type", "data_type"):
        value = str(metadata.get(key, "")).lower()
        if any(marker in value for marker in _PLACEHOLDER_MARKERS):
            return f"registry {key}={metadata.get(key)!r} is non-production provenance"
    if metadata.get("is_synthetic") is True:
        return "registry explicitly marks the artifact as synthetic"
    return None


def evaluate_dataset_registry_entry(
    entry: dict | None,
    *,
    base_dir: Path | str | None = None,
) -> dict:
    """Evaluate one registry row through the canonical rolling contract."""
    from scheduler.autonomous_scheduler import registry_entry_readiness

    root = Path(base_dir) if base_dir is not None else _BASE
    evidence = registry_entry_readiness(entry, project_root=root)
    path_value = evidence.get("path")
    if entry and path_value:
        marker = _contains_placeholder_marker(Path(path_value), entry)
        if marker:
            evidence = dict(evidence)
            evidence["ready"] = False
            evidence["status"] = "invalid"
            evidence["reasons"] = [*evidence.get("reasons", []), marker]
    return evidence


def _find_model_path(models_dir: Path, symbol: str) -> Path | None:
    """Return only the artifact promoted through ModelStorage's latest contract."""
    exact = models_dir / f"latest_{symbol.upper()}.pkl"
    return exact if exact.is_file() else None


def evaluate_model_artifact(
    model_path: Path | str | None,
    symbol: str,
    *,
    checker: Callable[[str, str], object] | None = None,
) -> dict:
    """Classify a mandatory model without recovery or retraining."""
    if model_path is None:
        return {"valid": False, "state": "MISSING", "reasons": ["Model artifact is missing"]}
    path = Path(model_path)
    if not path.is_file():
        return {"valid": False, "state": "MISSING", "reasons": [f"Model artifact does not exist: {path}"]}
    marker = _contains_placeholder_marker(path)
    if marker:
        return {"valid": False, "state": "INVALID/CORRUPT", "reasons": [marker]}

    try:
        if checker is None:
            from robustness.model_integrity_checker import _check_single_model

            result = _check_single_model(
                str(path), expected_symbol=symbol, auto_recover=False
            )
        else:
            result = checker(str(path), symbol)
        status = result.get("status") if isinstance(result, dict) else result.status
        issues = list(result.get("issues", [])) if isinstance(result, dict) else list(result.issues)
    except Exception as exc:
        message = f"Integrity checker raised {type(exc).__name__}: {exc}"
        state = "INCOMPATIBLE" if any(
            token in str(exc).lower() for token in ("version", "incompatib", "module")
        ) else "INVALID/CORRUPT"
        return {"valid": False, "state": state, "reasons": [message]}

    if status not in {"ok", "valid"}:
        joined = " ".join(issues).lower()
        state = "INCOMPATIBLE" if any(
            token in joined for token in ("version", "incompatib", "module")
        ) else "INVALID/CORRUPT"
        return {
            "valid": False,
            "state": state,
            "reasons": issues or [f"Integrity status is {status!r}"],
        }
    return {"valid": True, "state": "VALID", "reasons": [], "warnings": issues}


def _default_provider_probe(active_symbols: Iterable[str]) -> dict:
    """Probe one active symbol per DataRouter acquisition route."""
    from forex.data.data_router import DataRouter

    routes: dict[str, tuple[str, object]] = {}
    for symbol in active_symbols:
        router = DataRouter(symbol, "H1")
        route = "crypto" if router.asset_type == "crypto" else "forex"
        routes.setdefault(route, (symbol, router))

    if not routes:
        return {
            "operational": False,
            "provider": "none",
            "detail": "No active production route is configured",
        }

    details: list[str] = []
    providers: list[str] = []
    operational = True
    for route, (symbol, router) in sorted(routes.items()):
        try:
            frame = router.fetch(bars=2, raise_on_failure=True)
            if frame is None or len(frame) == 0:
                raise RuntimeError("no candles returned")
            provider = router.source_used or "unknown"
            providers.append(f"{route}={provider}")
            details.append(
                f"{route} route via {symbol}: {len(frame)} candle(s) from {provider}"
            )
        except Exception as exc:
            operational = False
            details.append(
                f"{route} route via {symbol}: {type(exc).__name__}: {exc}"
            )

    return {
        "operational": operational,
        "provider": ", ".join(providers) or "none",
        "detail": "; ".join(details),
    }


def _existing_sqlite_path(_base_dir: Path) -> Path:
    from infra.db.database import configured_sqlite_path

    return configured_sqlite_path()


def _add_environment_checks(report: ProductionReadinessReport, base_dir: Path) -> None:
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info[:2] == (3, 12)
    report.add_check(ReadinessCheck(
        "1. Entorno Python", "Versión de Python", "pass" if py_ok else "fail",
        f"Python {py_version} en {platform.system()} {platform.machine()}",
        "Use Python 3.12 on the production VM" if not py_ok else "",
        blocking=True,
    ))

    for module, label in _CRITICAL_DEPS:
        ok, version = _try_import(module)
        report.add_check(ReadinessCheck(
            "2. Dependencias", f"{label} ({module})", "pass" if ok else "fail",
            version, f"Instale la dependencia crítica {label}" if not ok else "",
            blocking=True,
        ))
    for module, label in _OPTIONAL_DEPS:
        ok, version = _try_import(module)
        report.add_check(ReadinessCheck(
            "2. Dependencias", f"{label} (opcional)", "pass" if ok else "warn",
            version if ok else "No instalado (opcional)",
            f"Instale {label} solo si necesita esa funcionalidad" if not ok else "",
            blocking=False,
        ))

    configured_env_path = os.getenv("ASTRA_ENV_FILE")
    env_path = (
        Path(configured_env_path)
        if configured_env_path
        else base_dir / "infra" / "config" / "astra.env"
    )
    report.add_check(ReadinessCheck(
        "3. Configuración", "Archivo astra.env",
        "pass" if env_path.is_file() else "warn",
        str(env_path) if env_path.is_file() else "No encontrado",
        "Configure el entorno desde el archivo example; readiness no lo crea",
        blocking=False,
    ))
    has_api_key = bool(os.getenv("ASTRA_API_KEY"))
    report.add_check(ReadinessCheck(
        "3. Configuración", "Autenticación API",
        "pass" if has_api_key else "fail",
        "ASTRA_API_KEY configurada" if has_api_key else "ASTRA_API_KEY ausente",
        "Configure ASTRA_API_KEY en el EnvironmentFile externo" if not has_api_key else "",
        blocking=True,
    ))
    has_chat_key = bool(os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY"))
    report.add_check(ReadinessCheck(
        "3. Configuración", "API Keys de chat",
        "pass" if has_chat_key else "warn",
        "Al menos una key configurada" if has_chat_key else "Chat cloud no configurado",
        "Configure una key solo si el chat cloud es requerido",
        blocking=False,
    ))


def run_production_readiness(
    *,
    base_dir: Path | str | None = None,
    db=None,
    required_timeframes: Iterable[str] = ("H1", "H4", "D1"),
    require_models: bool = True,
    probe_providers: bool = False,
    provider_probe: Callable[[], dict] | None = None,
    model_checker: Callable[[str, str], object] | None = None,
) -> ProductionReadinessReport:
    """Run read-only production readiness and return structured evidence."""
    root = Path(base_dir).resolve() if base_dir is not None else _BASE
    report = ProductionReadinessReport()
    _add_environment_checks(report, root)

    # Database: do not call the SQLite factory when its file is absent because
    # the factory initializes schema and would make readiness mutate resources.
    active_symbols: list[str] = []
    database = db
    if database is None:
        try:
            engine = os.environ.get("ASTRA_DB_ENGINE", "sqlite").lower()
            if engine in {"sqlite", ""} and not _existing_sqlite_path(root).is_file():
                raise FileNotFoundError(f"Database does not exist: {_existing_sqlite_path(root)}")
            from infra.db.database import get_database

            database = get_database()
        except Exception as exc:
            report.add_check(ReadinessCheck(
                "4. Base de datos", "Conexión y registry", "fail",
                f"{type(exc).__name__}: {exc}",
                "Inicialice la DB mediante el flujo explícito de first-run",
                blocking=True,
                evidence_state="MISSING/UNAVAILABLE",
            ))

    if database is not None:
        try:
            rows = database.get_supported_symbols()
            active_symbols = [
                row["symbol_code"] for row in rows
                if str(row.get("status", "active")).lower() == "active"
            ]
            report.add_check(ReadinessCheck(
                "4. Base de datos", "Conexión y registry",
                "pass" if active_symbols else "pending",
                f"{len(active_symbols)} símbolo(s) activo(s)",
                "Configure al menos un símbolo productivo" if not active_symbols else "",
                blocking=True,
                evidence_state="QUERY_VERIFIED",
            ))
        except Exception as exc:
            report.add_check(ReadinessCheck(
                "4. Base de datos", "Conexión y registry", "fail",
                f"Critical DB check raised {type(exc).__name__}: {exc}",
                "Revise integridad y acceso a la DB",
                blocking=True,
                evidence_state="ERROR",
            ))
            database = None

    # Datasets: registry and persisted bytes must satisfy the canonical contract.
    if database is not None:
        for symbol in active_symbols:
            for timeframe in tuple(required_timeframes):
                try:
                    entries = database.get_dataset_registry(symbol, timeframe)
                    entry = entries[0] if entries else None
                    evidence = evaluate_dataset_registry_entry(entry, base_dir=root)
                    state = evidence["status"]
                    check_status = "pass" if evidence["ready"] else (
                        "pending" if state in {"missing", "pending"} else "fail"
                    )
                    report.add_check(ReadinessCheck(
                        "5. Datasets", f"Dataset {symbol}/{timeframe}", check_status,
                        "; ".join(evidence.get("reasons", [])) or (
                            f"Canonical contract verified at {evidence.get('path')}"
                        ),
                        "Complete la rolling window canónica con datos reales"
                        if not evidence["ready"] else "",
                        blocking=True,
                        evidence_state=state.upper(),
                    ))
                except Exception as exc:
                    report.add_check(ReadinessCheck(
                        "5. Datasets", f"Dataset {symbol}/{timeframe}", "fail",
                        f"Critical dataset check raised {type(exc).__name__}: {exc}",
                        "Revise registry y CSV persistido",
                        blocking=True,
                        evidence_state="ERROR",
                    ))

    # Models are mandatory for the H1 executable prediction cycle.
    if require_models:
        models_dir = forex_model_root(root)
        for symbol in active_symbols:
            model_path = _find_model_path(models_dir, symbol)
            evidence = evaluate_model_artifact(
                model_path, symbol, checker=model_checker
            )
            warnings = evidence.get("warnings", [])
            status = "pass" if evidence["valid"] and not warnings else (
                "warn" if evidence["valid"] else "fail"
            )
            report.add_check(ReadinessCheck(
                "6. Modelos", f"Modelo {symbol}/H1", status,
                "; ".join(evidence.get("reasons", []) or warnings)
                or f"Integrity verified: {model_path}",
                "Proporcione un modelo válido; readiness nunca entrena ni recupera modelos"
                if not evidence["valid"] else "",
                blocking=not evidence["valid"],
                evidence_state=evidence["state"],
            ))

    # Scheduler state must come from an actual recorded run, not the DB's
    # superficial healthy boolean.
    if database is not None:
        try:
            runs = database.get_scheduler_runs(limit=100)
            last_run = next(
                (run for run in runs if str(run.get("timeframe", "")).upper() == "H1"),
                None,
            )
            if not last_run:
                scheduler_status = "pending"
                detail = "No H1 scheduler run has been recorded"
                evidence_state = "UNVERIFIED"
            elif (
                last_run.get("status") == "completed"
                and not last_run.get("errors_count")
                and int(last_run.get("symbols_processed") or 0) > 0
            ):
                scheduler_status = "pass"
                detail = (
                    f"Recorded completed H1 run #{last_run.get('id')} | "
                    f"symbols_processed={last_run.get('symbols_processed')} | "
                    f"predictions_generated={last_run.get('predictions_generated') or 0}"
                )
                evidence_state = "PROCESSED_CYCLE"
            elif (
                last_run.get("status") == "completed"
                and not last_run.get("errors_count")
                and active_symbols
                and int(last_run.get("symbols_processed") or 0) == 0
            ):
                scheduler_status = "pending"
                detail = (
                    f"Completed H1 run #{last_run.get('id')} was a no-op/blocked cycle | "
                    f"active_symbols={len(active_symbols)} | symbols_processed=0"
                )
                evidence_state = "COMPLETED_NOOP"
            elif last_run.get("status") == "running":
                scheduler_status = "pending"
                detail = f"Run #{last_run.get('id')} is still running"
                evidence_state = "RUNNING"
            else:
                scheduler_status = "fail"
                detail = (
                    f"Last run status={last_run.get('status')!r}, "
                    f"errors={last_run.get('errors_count')!r}"
                )
                evidence_state = "RECORDED_FAILURE"
            report.add_check(ReadinessCheck(
                "7. Scheduler", "Ejecución registrada", scheduler_status, detail,
                "Ejecute y verifique un ciclo scheduler real",
                blocking=True,
                evidence_state=evidence_state,
            ))
        except Exception as exc:
            report.add_check(ReadinessCheck(
                "7. Scheduler", "Ejecución registrada", "fail",
                f"Critical scheduler check raised {type(exc).__name__}: {exc}",
                "Revise la tabla scheduler_runs",
                blocking=True,
                evidence_state="ERROR",
            ))

    # Provider package availability is configuration evidence only.
    yahoo_available, _ = _try_import("yfinance")
    mt5_available, _ = _try_import("MetaTrader5")
    configured = yahoo_available or (platform.system() == "Windows" and mt5_available)
    report.add_check(ReadinessCheck(
        "8. Proveedores", "Proveedor Forex configurado",
        "pass" if configured else "fail",
        f"Yahoo importable={yahoo_available}; MT5 importable={mt5_available}",
        "Configure Yahoo en Linux o un proveedor soportado",
        blocking=True,
        evidence_state="AVAILABLE/CONFIGURED" if configured else "MISSING",
    ))

    if probe_providers:
        try:
            probe_result = (
                provider_probe()
                if provider_probe is not None
                else _default_provider_probe(active_symbols)
            )
            operational = bool(probe_result.get("operational"))
            report.add_check(ReadinessCheck(
                "8. Proveedores", "Adquisición operacional verificada",
                "pass" if operational else "fail",
                f"{probe_result.get('provider', 'unknown')}: {probe_result.get('detail', '')}",
                "Revise conectividad y el proveedor configurado",
                blocking=True,
                evidence_state="VERIFIED_OPERATIONAL" if operational else "VERIFIED_FAILED",
            ))
        except Exception as exc:
            report.add_check(ReadinessCheck(
                "8. Proveedores", "Adquisición operacional verificada", "fail",
                f"Provider probe raised {type(exc).__name__}: {exc}",
                "Revise conectividad y el proveedor configurado",
                blocking=True,
                evidence_state="ERROR",
            ))
    else:
        report.add_check(ReadinessCheck(
            "8. Proveedores", "Adquisición operacional verificada", "pending",
            "Probe de red no ejecutado; disponibilidad de import no prueba operación",
            "Ejecute explícitamente run_production_readiness(probe_providers=True)",
            blocking=True,
            evidence_state="UNVERIFIED",
        ))

    # Read-only filesystem and deployment-manifest evidence.  Runtime service
    # installation belongs to A-07 and is intentionally not inferred here.
    missing_dirs = [name for name in _EXPECTED_DIRS if not (root / name).is_dir()]
    report.add_check(ReadinessCheck(
        "9. Filesystem", "Estructura de directorios",
        "warn" if missing_dirs else "pass",
        f"Faltan: {', '.join(missing_dirs)}" if missing_dirs else "Estructura esperada presente",
        "Cree directorios mediante setup explícito; readiness es de solo lectura",
        blocking=False,
    ))
    non_writable = [
        name for name in ("CSVs", "models", "memory_db", "logs", "reports")
        if (root / name).exists() and not os.access(root / name, os.W_OK)
    ]
    report.add_check(ReadinessCheck(
        "9. Filesystem", "Permisos declarados de escritura",
        "fail" if non_writable else "pass",
        f"Sin acceso de escritura: {', '.join(non_writable)}" if non_writable
        else "os.access confirma escritura en directorios existentes",
        "Corrija propietario/permisos en la VM",
        blocking=bool(non_writable),
        evidence_state="READ_ONLY_PERMISSION_CHECK",
    ))

    service_files = list((root / "infra" / "systemd").glob("*.service"))
    report.add_check(ReadinessCheck(
        "10. Deployment", "Manifiestos systemd",
        "pass" if service_files else "warn",
        f"{len(service_files)} archivo(s) .service; presencia no implica servicio activo",
        "La instalación/activación real se valida fuera de A-08",
        blocking=False,
        evidence_state="MANIFEST_ONLY",
    ))

    workspace_contract = (root / "workspace" / "server.py").is_file()
    report.add_check(ReadinessCheck(
        "11. Workplace", "Contrato FastAPI presente",
        "pass" if workspace_contract else "fail",
        "workspace/server.py presente; no afirma proceso operativo"
        if workspace_contract else "workspace/server.py ausente",
        "Restaure Workplace/FastAPI",
        blocking=not workspace_contract,
        evidence_state="STATIC_CONTRACT_ONLY",
    ))

    try:
        import psutil

        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(str(root))
        enough_memory = memory.available > 512 * 1024 * 1024
        enough_disk = disk.free > 1024 ** 3
        report.add_check(ReadinessCheck(
            "12. Recursos", "RAM disponible", "pass" if enough_memory else "warn",
            f"{memory.available / 1024 ** 3:.1f} GB disponibles",
            "Libere memoria" if not enough_memory else "",
            blocking=False,
        ))
        report.add_check(ReadinessCheck(
            "12. Recursos", "Disco disponible", "pass" if enough_disk else "warn",
            f"{disk.free / 1024 ** 3:.1f} GB libres",
            "Libere espacio" if not enough_disk else "",
            blocking=False,
        ))
    except Exception as exc:
        report.add_check(ReadinessCheck(
            "12. Recursos", "Lectura de recursos", "warn",
            f"No se pudo verificar: {type(exc).__name__}: {exc}",
            "Instale/configure psutil",
            blocking=False,
        ))

    report.finalize()
    return report

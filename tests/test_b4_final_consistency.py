"""Offline consistency checks for B4 (A19 version and A22 metadata)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import astra_api
import forex
from astra_version import ASTRA_VERSION


ROOT = Path(__file__).resolve().parents[1]
VERSION_SOURCE = ROOT / "astra_version.py"
DEV_ENV = ROOT / ".env.example"
PROD_ENV = ROOT / "infra" / "config" / "astra.env.example"
DEPLOYMENT_DOC = ROOT / "docs" / "infraestructure" / "DEPLOYMENT.md"
VM_DOC = ROOT / "docs" / "infraestructure" / "ORACLE_VM.md"

RUNTIME_VERSION_FILES = (
    ROOT / "main.py",
    ROOT / "astra_api.py",
    ROOT / "workspace" / "server.py",
    ROOT / "forex" / "__init__.py",
    ROOT / "scheduler" / "autonomous_scheduler.py",
    ROOT / "infra" / "db" / "database.py",
)
GENERAL_DOCS = (
    ROOT / "README.md",
    ROOT / "MANUAL.md",
    ROOT / "docs" / "ORACLE_CLOUD.md",
    DEPLOYMENT_DOC,
    VM_DOC,
)
AUDITED_TEXT = GENERAL_DOCS + (DEV_ENV, PROD_ENV)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _env_assignments(path: Path) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for raw_line in _text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        assignments[key.strip()] = value.split("#", 1)[0].strip()
    return assignments


def _function_node(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(_text(path), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path}")


def test_exactly_one_canonical_version_source_exists():
    definitions: list[Path] = []
    roots = [ROOT, ROOT / "forex", ROOT / "workspace", ROOT / "scheduler", ROOT / "infra"]
    for source_root in roots:
        candidates = source_root.glob("*.py") if source_root == ROOT else source_root.rglob("*.py")
        for path in candidates:
            if "legacy" in path.parts or "tests" in path.parts:
                continue
            if re.search(r"(?m)^ASTRA_VERSION\s*=", _text(path)):
                definitions.append(path)
    assert definitions == [VERSION_SOURCE]


def test_canonical_version_matches_established_project_version():
    assert ASTRA_VERSION == "7.1.0"
    module = ast.parse(_text(VERSION_SOURCE))
    assignment = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "ASTRA_VERSION" for target in node.targets)
    )
    assert ast.literal_eval(assignment.value) == "7.1.0"


def test_version_consumers_use_canonical_source():
    assert forex.__version__ == ASTRA_VERSION
    assert astra_api._handle_root({})["version"] == ASTRA_VERSION
    assert f"v{ASTRA_VERSION}" in astra_api._ROOT_HTML
    assert "__ASTRA_VERSION__" not in astra_api._ROOT_HTML

    workspace_source = _text(ROOT / "workspace" / "server.py")
    scheduler_source = _text(ROOT / "scheduler" / "autonomous_scheduler.py")
    database_source = _text(ROOT / "infra" / "db" / "database.py")
    assert "from astra_version import ASTRA_VERSION" in workspace_source
    assert '"version": ASTRA_VERSION' in workspace_source
    assert '"pipeline_version": f"v{ASTRA_VERSION}"' in scheduler_source
    assert '_PIPELINE_VERSION = f"v{ASTRA_VERSION}"' in database_source


def test_public_health_endpoints_remain_minimal_and_versionless():
    assert astra_api._ROUTES["/api/astra/health"]({}) == {"ok": True}

    health = _function_node(ROOT / "workspace" / "server.py", "get_health")
    constants = {node.value for node in ast.walk(health) if isinstance(node, ast.Constant)}
    assert "/health" in constants
    assert "/api/health" in constants
    assert "version" not in constants
    assert "ASTRA_VERSION" not in {node.id for node in ast.walk(health) if isinstance(node, ast.Name)}


def test_selected_runtime_files_have_no_contradictory_product_literals():
    semver_literal = re.compile(r"(?P<quote>['\"])(\d+\.\d+\.\d+(?:-prod)?)(?P=quote)")
    found: list[tuple[str, str]] = []
    for path in RUNTIME_VERSION_FILES:
        for match in semver_literal.finditer(_text(path)):
            found.append((path.relative_to(ROOT).as_posix(), match.group(2)))
    assert found == []


def test_examples_systemd_and_docs_contain_no_hardcoded_secrets():
    private_material = re.compile(
        r"BEGIN [A-Z ]*PRIVATE KEY|\b(?:gsk|sk|key)_[A-Za-z0-9_-]{16,}|\bsk-[A-Za-z0-9_-]{16,}|"
        r"\bocid1\.[A-Za-z0-9._-]+|Authorization:\s*Bearer\s+[A-Za-z0-9._-]{12,}",
        re.IGNORECASE,
    )
    for path in AUDITED_TEXT:
        assert not private_material.search(_text(path)), path

    sensitive_name = re.compile(r"(?:API_KEY|TOKEN|PASSWORD|SECRET|PRIVATE_KEY)$")
    for path in (DEV_ENV, PROD_ENV):
        assignments = _env_assignments(path)
        populated = {key: value for key, value in assignments.items() if sensitive_name.search(key) and value}
        assert populated == {}, path

    for service in (ROOT / "infra" / "systemd").glob("*.service"):
        assert "ASTRA_API_KEY=" not in _text(service), service


def test_environment_examples_keep_loopback_and_empty_api_key():
    for path in (DEV_ENV, PROD_ENV):
        values = _env_assignments(path)
        assert values["ASTRA_HOST"] == "127.0.0.1"
        assert values["ASTRA_API_HOST"] == "127.0.0.1"
        assert values["ASTRA_API_KEY"] == ""
        assert values["ASTRA_ROLLING_WINDOW_SIZE"] == "2000"

    assert "ejemplo para desarrollo local" in _text(DEV_ENV)
    assert "/etc/astra/astra.env" in _text(PROD_ENV)


def test_environment_examples_use_canonical_b1_database_path():
    expected = "memory_db/astra_autonomous.db"
    for path in (DEV_ENV, PROD_ENV):
        assert _env_assignments(path)["ASTRA_DB_PATH"] == expected, path


def test_environment_examples_use_persistent_dev_log_database_path():
    expected = "memory_db/dev_log.db"
    for path in (DEV_ENV, PROD_ENV):
        assert _env_assignments(path)["ASTRA_DEV_LOG_DB_PATH"] == expected, path


def test_deployment_docs_do_not_claim_https_or_proxy_is_implemented():
    deployment = _text(DEPLOYMENT_DOC)
    vm = _text(VM_DOC)
    assert "todavía se requiere un reverse proxy HTTPS" in deployment
    assert "no abre firewall,\nOCI ingress, DNS ni TLS" in deployment
    assert "operador configure por separado reverse proxy HTTPS" in vm
    assert "no afirma que esos componentes estén implementados" in vm


def test_product_docs_and_config_have_no_personal_windows_paths():
    personal_path = re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\|\\Downloads\\", re.IGNORECASE)
    for path in AUDITED_TEXT:
        assert not personal_path.search(_text(path)), path


def test_general_docs_have_no_operational_ips():
    ipv4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
    allowed = {"127.0.0.1"}
    for path in GENERAL_DOCS:
        addresses = set(ipv4.findall(_text(path)))
        assert addresses <= allowed, (path, addresses - allowed)


def test_historical_readiness_claims_are_not_presented_as_current():
    verification = _text(ROOT / "VERIFICACION_COMPLETA.md")
    audit = _text(ROOT / "AUDIT_REPORT.md")
    changelog = _text(ROOT / "CHANGELOG.md")
    manual = _text(ROOT / "MANUAL.md")
    assert "Registro histórico" in verification
    assert "Registro histórico de v7.0.2-prod" in audit
    assert "Historial permanente de cambios" in changelog
    assert "Snapshot histórico de componentes (v7.0.2-prod)" in manual
    assert "no representa readiness actual" in verification

    historical_claim_docs = (
        "CORRECCIONES_APLICADAS.md",
        "docs/CORRECCIONES_APLICADAS.md",
        "GUIA_RAPIDA_IMPLEMENTACION.md",
        "docs/GUIA_RAPIDA_IMPLEMENTACION.md",
        "INICIO_AQUI.md",
        "docs/INICIO_AQUI.md",
        "INTEGRATION_PLAN.md",
        "docs/INTEGRATION_PLAN.md",
    )
    for relative in historical_claim_docs:
        content = _text(ROOT / relative)
        assert "históric" in content.lower(), relative
        assert "no " in content.lower(), relative


def test_python_312_and_arm64_remain_documented():
    requirements = _text(ROOT / "requirements.txt")
    readme = _text(ROOT / "README.md")
    deployment = _text(DEPLOYMENT_DOC)
    vm = _text(VM_DOC)
    assert "Python 3.12" in requirements
    assert "Python 3.12" in readme
    assert "Python 3.12" in deployment
    assert "Python: 3.12" in vm
    assert "Python 3.12" in _text(ROOT / "FOREX_USER_GUIDE.md")
    assert "Python 3.12" in _text(ROOT / "replit.md")
    assert "ARM64" in readme and "aarch64" in readme
    assert "ARM64" in vm and "aarch64" in vm


def test_b1_b2_b3_documentation_contracts_are_explicit():
    manual = _text(ROOT / "MANUAL.md")
    deployment = _text(DEPLOYMENT_DOC)
    required_manual_fragments = (
        "sólo H1 genera predicciones",
        "H4 y D1 aportan contexto sin\nlookahead",
        "`action` es la decisión final canónica",
        "exactamente 2000 velas",
        "no habilita fallback sintético de producción",
        "`latest_<SYMBOL>.pkl`",
        "no hay fallback genérico cross-symbol",
        "sólo outcomes finales",
        "health/readiness",
    )
    for fragment in required_manual_fragments:
        assert fragment in manual
    for fragment in ("Ubuntu 24.04", "Python 3.12", "systemd", "127.0.0.1:8000", "DEPLOYED_NOT_READY"):
        assert fragment in deployment


def test_roadmap_versions_remain_historical_not_product_replacements():
    main_source = _text(ROOT / "main.py")
    prediction_lab = _text(ROOT / "prediction_lab" / "__init__.py")
    manual = _text(ROOT / "MANUAL.md")
    assert "Roadmap V" in main_source
    assert "Roadmap VI" in main_source
    assert "Fase 5 histórica de ASTRA v4.0" in prediction_lab
    assert "Roadmap V/VI" in manual


def test_relevant_b4_files_are_utf8_without_stored_mojibake():
    mojibake = re.compile(r"Ã.|â€|â€”|â”|â•|Â.")
    paths = set(AUDITED_TEXT) | set(RUNTIME_VERSION_FILES) | {VERSION_SOURCE}
    for path in paths:
        content = path.read_bytes().decode("utf-8")
        assert not mojibake.search(content), path

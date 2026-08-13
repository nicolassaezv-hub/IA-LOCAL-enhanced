from __future__ import annotations

import asyncio
import ast
import importlib
import io
from pathlib import Path

import pytest

import astra_api
from deployment.report_manager import ReportManager
from robustness import pipeline_benchmark
from runtime_security import (
    AuthResult,
    authenticate_headers,
    configured_bind_host,
    configured_cors_origins,
)
from workspace.path_safety import (
    UnsafePathError,
    resolve_user_path,
    resolve_user_path_in_roots,
)
from workspace.upload_storage import store_upload

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _Upload:
    def __init__(self, filename: str, chunks: list[bytes], fail_after: int | None = None):
        self.filename = filename
        self._chunks = iter(chunks)
        self._reads = 0
        self._fail_after = fail_after

    async def read(self, _size: int) -> bytes:
        if self._fail_after is not None and self._reads >= self._fail_after:
            raise OSError("simulated upload failure")
        self._reads += 1
        return next(self._chunks, b"")


class _InspectingUpload(_Upload):
    def __init__(self, filename: str, chunks: list[bytes], upload_root: Path):
        super().__init__(filename, chunks)
        self._upload_root = upload_root
        self.published_csvs_during_stream: list[Path] = []
        self.staging_files_during_stream: list[Path] = []

    async def read(self, size: int) -> bytes:
        if self._reads:
            self.published_csvs_during_stream.extend(self._upload_root.glob("*.csv"))
            self.staging_files_during_stream.extend(self._upload_root.glob("*.part"))
        return await super().read(size)


class _CancelledUpload(_Upload):
    async def read(self, _size: int) -> bytes:
        if self._reads:
            raise asyncio.CancelledError("simulated upload cancellation")
        self._reads += 1
        return b"partial"


@pytest.mark.parametrize(
    "candidate",
    [
        "../.env",
        r"..\..\memory_db\astra.db",
        r"C:\Windows\win.ini",
        r"\\server\share\secret.txt",
        "/etc/passwd",
    ],
)
def test_user_paths_reject_traversal_and_cross_platform_absolute_paths(tmp_path, candidate):
    with pytest.raises(UnsafePathError):
        resolve_user_path(tmp_path, candidate)


def test_allowed_file_resolves_from_stable_root_when_cwd_changes(tmp_path, monkeypatch):
    root = tmp_path / "project"
    allowed = root / "uploads"
    elsewhere = tmp_path / "elsewhere"
    allowed.mkdir(parents=True)
    elsewhere.mkdir()
    expected = allowed / "safe.csv"
    expected.write_text("open,high,low,close\n1,1,1,1\n", encoding="utf-8")
    monkeypatch.chdir(elsewhere)

    resolved = resolve_user_path_in_roots(
        root,
        "uploads/safe.csv",
        (allowed,),
        require_file=True,
    )

    assert resolved == expected.resolve()


def test_symlink_escape_is_rejected_when_supported(tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    link = root / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not available in this environment")

    with pytest.raises(UnsafePathError):
        resolve_user_path(root, "link/secret.txt", require_file=True)


@pytest.mark.parametrize("filename", ["../evil.csv", r"..\evil.csv", r"C:\evil.csv", "/tmp/evil.csv"])
def test_upload_rejects_traversal_and_absolute_names(tmp_path, filename):
    with pytest.raises(UnsafePathError):
        asyncio.run(store_upload(_Upload(filename, [b"data"]), tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_upload_uses_unique_server_name_and_cannot_overwrite_sensitive_files(tmp_path):
    project = tmp_path / "project"
    uploads = project / "workspace" / "uploads"
    uploads.mkdir(parents=True)
    protected = {
        project / ".env": "environment",
        project / "memory.db": "database",
        project / "models" / "latest_EURUSD.pkl": "model",
    }
    for path, content in protected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    stored, original, size = asyncio.run(store_upload(_Upload(".env", [b"attacker"]), uploads))

    assert stored.parent == uploads.resolve()
    assert stored.name != ".env"
    assert original == ".env"
    assert size == len(b"attacker")
    assert stored.read_bytes() == b"attacker"
    for path, content in protected.items():
        assert path.read_text(encoding="utf-8") == content


def test_failed_upload_removes_partial_file_and_temp_directory_is_deletable(tmp_path):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    upload = _Upload("data.csv", [b"partial"], fail_after=1)

    with pytest.raises(OSError, match="simulated"):
        asyncio.run(store_upload(upload, upload_root))

    assert list(upload_root.iterdir()) == []
    upload_root.rmdir()
    assert not upload_root.exists()


def test_upload_does_not_publish_partial_csv_during_streaming(tmp_path):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    upload = _InspectingUpload("data.csv", [b"first", b"second"], upload_root)

    stored, _original, _size = asyncio.run(store_upload(upload, upload_root))

    assert upload.published_csvs_during_stream == []
    assert upload.staging_files_during_stream
    assert all(path.name.startswith(".") for path in upload.staging_files_during_stream)
    assert list(upload_root.glob("*.csv")) == [stored]


def test_successful_upload_only_leaves_final_file_with_sanitized_suffix(tmp_path):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()

    stored, original, size = asyncio.run(
        store_upload(_Upload("report.xlsx", [b"workbook"]), upload_root)
    )

    assert original == "report.xlsx"
    assert size == len(b"workbook")
    assert stored.suffix == ".xlsx"
    assert "report" not in stored.stem
    assert stored.read_bytes() == b"workbook"
    assert list(upload_root.iterdir()) == [stored]


def test_streaming_failure_leaves_no_part_or_final_file(tmp_path):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()

    with pytest.raises(OSError, match="simulated upload failure"):
        asyncio.run(
            store_upload(_Upload("data.csv", [b"partial"], fail_after=1), upload_root)
        )

    assert list(upload_root.glob("*.part")) == []
    assert list(upload_root.glob("*.csv")) == []
    assert list(upload_root.iterdir()) == []


def test_upload_cancellation_cleans_up_partial_file(tmp_path):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()

    with pytest.raises(asyncio.CancelledError, match="simulated upload cancellation"):
        asyncio.run(store_upload(_CancelledUpload("data.csv", []), upload_root))

    assert list(upload_root.iterdir()) == []


def test_same_original_filename_produces_distinct_final_paths(tmp_path):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()

    first, _original, _size = asyncio.run(
        store_upload(_Upload("data.csv", [b"first"]), upload_root)
    )
    second, _original, _size = asyncio.run(
        store_upload(_Upload("data.csv", [b"second"]), upload_root)
    )

    assert first != second
    assert first.read_bytes() == b"first"
    assert second.read_bytes() == b"second"
    assert set(upload_root.iterdir()) == {first, second}


def test_report_download_boundary_allows_report_and_rejects_escape(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    allowed = reports / "readiness_20260812.md"
    allowed.write_text("# evidence", encoding="utf-8")
    outside = tmp_path / "secret.md"
    outside.write_text("secret", encoding="utf-8")
    manager = ReportManager(report_dir=reports)

    assert manager.get_report_content(allowed.name) == "# evidence"
    assert manager.get_report_content("../secret.md") is None
    assert manager.get_report_content(str(outside.resolve())) is None
    assert manager.get_report_content(r"C:\Windows\win.ini") is None


def test_default_bind_is_loopback_and_public_bind_is_explicit():
    assert configured_bind_host("ASTRA_HOST", {}) == "127.0.0.1"
    assert configured_bind_host("ASTRA_HOST", {"ASTRA_HOST": "0.0.0.0"}) == "0.0.0.0"
    assert configured_bind_host("ASTRA_API_HOST", {}) == "127.0.0.1"


def test_api_authentication_is_fail_closed_and_accepts_valid_credentials():
    environment = {"ASTRA_API_KEY": "correct-horse-battery-staple"}
    assert authenticate_headers({}, {}) is AuthResult.NOT_CONFIGURED
    assert authenticate_headers({}, environment) is AuthResult.MISSING
    assert authenticate_headers({"Authorization": "Bearer wrong"}, environment) is AuthResult.INVALID
    assert (
        authenticate_headers(
            {"Authorization": "Bearer correct-horse-battery-staple"},
            environment,
        )
        is AuthResult.OK
    )
    assert authenticate_headers({"X-API-Key": environment["ASTRA_API_KEY"]}, environment) is AuthResult.OK


def test_cors_requires_explicit_origins_and_ignores_wildcard():
    origins = configured_cors_origins(
        {"ASTRA_CORS_ORIGINS": "*, https://astra.example, https://ops.example/"}
    )
    assert origins == frozenset({"https://astra.example", "https://ops.example"})


def test_internal_http_api_authentication_is_fail_closed(monkeypatch):
    handler = object.__new__(astra_api.AstraAPIHandler)
    responses = []
    handler._send_json = lambda data, status=200: responses.append((status, data))

    monkeypatch.delenv("ASTRA_API_KEY", raising=False)
    handler.headers = {}
    assert handler._authorized("/api/astra/status") is False
    assert responses[-1][0] == 503

    monkeypatch.setenv("ASTRA_API_KEY", "internal-secret")
    handler.headers = {"Authorization": "Bearer wrong"}
    assert handler._authorized("/api/astra/status") is False
    assert responses[-1][0] == 401

    handler.headers = {"Authorization": "Bearer internal-secret"}
    assert handler._authorized("/api/astra/status") is True
    handler.headers = {}
    assert handler._authorized("/api/astra/health") is True


@pytest.mark.parametrize("method_name", ["do_GET", "do_POST"])
def test_internal_http_api_exact_api_path_requires_authentication(monkeypatch, method_name):
    handler = object.__new__(astra_api.AstraAPIHandler)
    responses = []
    handler.path = "/api"
    handler.headers = {}
    handler.rfile = io.BytesIO(b"")
    handler._send_json = lambda data, status=200: responses.append((status, data))
    monkeypatch.setenv("ASTRA_API_KEY", "internal-secret")

    getattr(handler, method_name)()

    assert responses[-1][0] == 401


def test_internal_http_api_binds_loopback_unless_host_is_explicit(monkeypatch):
    addresses = []

    class FakeServer:
        def __init__(self, address, _handler):
            addresses.append(address)

        def serve_forever(self):
            return None

        def shutdown(self):
            return None

    monkeypatch.setattr(astra_api, "HTTPServer", FakeServer)
    monkeypatch.delenv("ASTRA_API_HOST", raising=False)
    astra_api._server_instance = None
    try:
        assert astra_api.start_api_server(port=8766)
        assert addresses[-1] == ("127.0.0.1", 8766)
        astra_api.stop_api_server()

        monkeypatch.setenv("ASTRA_API_HOST", "0.0.0.0")
        assert astra_api.start_api_server(port=8767)
        assert addresses[-1] == ("0.0.0.0", 8767)
    finally:
        astra_api.stop_api_server()


def test_benchmark_reports_unavailable_without_evidence(monkeypatch):
    class EmptyBenchmark:
        def get_stats(self):
            return {}

        def get_history(self, **_kwargs):
            return []

    monkeypatch.setattr(pipeline_benchmark, "get_benchmark", lambda: EmptyBenchmark())
    evidence = pipeline_benchmark.get_benchmark_evidence()
    assert evidence["status"] == "UNAVAILABLE"
    assert pipeline_benchmark.cmd_benchmark().startswith("[UNAVAILABLE]")


def test_benchmark_failure_is_error_not_success(monkeypatch):
    def fail():
        raise OSError("benchmark database unavailable")

    monkeypatch.setattr(pipeline_benchmark, "get_benchmark", fail)
    evidence = pipeline_benchmark.get_benchmark_evidence()
    result = pipeline_benchmark.cmd_benchmark()
    assert evidence["status"] == "ERROR"
    assert result.startswith("[ERROR]")
    assert "SUCCESS" not in result


def test_benchmark_aliases_are_registered_to_real_callable():
    try:
        registry = importlib.import_module("tool_registry")
    except ModuleNotFoundError as exc:
        pytest.skip(f"optional runtime dependency unavailable: {exc.name}")

    canonical = registry.TOOLS["robustness_benchmark"]
    assert callable(canonical)
    assert registry.TOOLS["robustez_benchmark"] is canonical
    assert canonical is pipeline_benchmark.cmd_benchmark


def test_cli_benchmark_branch_calls_canonical_command_and_recording_is_reachable():
    source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    dispatch = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "dispatch_command")
    full_forex = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_forex_full")

    dispatch_source = ast.get_source_segment(source, dispatch)
    full_source = ast.get_source_segment(source, full_forex)
    assert "cmd_benchmark(benchmark_args)" in dispatch_source
    assert "robustez benchmark" in dispatch_source
    assert full_source.index("record_stage") < full_source.rindex('return ""')


def test_full_forex_benchmark_uses_primary_h1_pipeline_timeframe():
    main_source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
    main_tree = ast.parse(main_source)
    full_forex = next(
        node
        for node in main_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_forex_full"
    )
    benchmark_call = next(
        node
        for node in ast.walk(full_forex)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "record_stage"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "total_pipeline"
    )

    pipeline_source = (
        PROJECT_ROOT / "forex" / "prediction" / "integrated_pipeline.py"
    ).read_text(encoding="utf-8")
    pipeline_tree = ast.parse(pipeline_source)
    primary_timeframe = next(
        node.value.value
        for node in pipeline_tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "PREDICTION_TIMEFRAME"
            for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
    )
    pipeline_import = next(
        node
        for node in full_forex.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "forex.prediction.integrated_pipeline"
    )

    assert primary_timeframe == "H1"
    assert "PREDICTION_TIMEFRAME" in {alias.name for alias in pipeline_import.names}
    assert isinstance(benchmark_call.args[3], ast.Name)
    assert benchmark_call.args[3].id == "PREDICTION_TIMEFRAME"


def test_frontend_auth_protects_exact_api_path_and_keeps_health_public():
    source = (PROJECT_ROOT / "workspace" / "static" / "js" / "api_client.js").read_text(
        encoding="utf-8"
    )

    assert 'url.pathname === "/api" || url.pathname.startsWith("/api/")' in source
    assert 'url.pathname !== "/api/health"' in source


def _workspace_client(monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    monkeypatch.setenv("ASTRA_API_KEY", "b2-test-secret")
    try:
        server = importlib.import_module("workspace.server")
        testclient = importlib.import_module("fastapi.testclient")
    except (ModuleNotFoundError, RuntimeError) as exc:
        pytest.skip(f"Workspace HTTP dependencies unavailable: {exc}")
    return server, testclient.TestClient(server.app)


def test_workspace_api_static_order_and_unknown_api_behavior(monkeypatch):
    server, client = _workspace_client(monkeypatch)
    auth = {"Authorization": "Bearer b2-test-secret"}
    try:
        valid = client.get("/api/status", headers=auth)
        missing = client.get("/api/not-a-real-endpoint", headers=auth)
        static = client.get("/css/style.css")
        frontend = client.get("/")
    finally:
        client.close()

    assert valid.status_code == 200
    assert valid.headers["content-type"].startswith("application/json")
    assert missing.status_code == 404
    assert "<!doctype html" not in missing.text.lower()
    assert static.status_code == 200
    assert "text/css" in static.headers["content-type"]
    assert frontend.status_code == 200
    assert "ASTRA" in frontend.text
    mount_index = next(
        index for index, route in enumerate(server.app.routes)
        if getattr(route, "name", None) == "static"
    )
    api_indices = [index for index, route in enumerate(server.app.routes) if route.path.startswith("/api/")]
    assert api_indices and max(api_indices) < mount_index


def test_workspace_sensitive_auth_health_and_secret_redaction(monkeypatch):
    server, client = _workspace_client(monkeypatch)
    del server  # the client is the contract under test
    try:
        missing = client.get("/api/status")
        invalid = client.get("/api/status", headers={"Authorization": "Bearer invalid"})
        valid = client.get("/api/config", headers={"Authorization": "Bearer b2-test-secret"})
        monkeypatch.delenv("ASTRA_API_KEY")
        not_configured = client.get("/api/status")
        health = client.get("/health")
    finally:
        client.close()

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert valid.status_code == 200
    assert not_configured.status_code == 503
    assert "b2-test-secret" not in valid.text
    assert "root_dir" not in valid.json()
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}


def test_workspace_command_failure_is_not_reported_as_success(monkeypatch):
    server, client = _workspace_client(monkeypatch)
    monkeypatch.setattr(server, "dispatch_command", lambda _command: "[ERROR] benchmark failed")
    try:
        response = client.post(
            "/api/command",
            headers={"Authorization": "Bearer b2-test-secret"},
            json={"command": "robustness benchmark"},
        )
    finally:
        client.close()

    assert response.status_code == 500
    assert response.json()["ok"] is False
    assert response.json()["status"] == "ERROR"


def test_workspace_benchmark_preserves_public_history_fields(monkeypatch):
    _server, client = _workspace_client(monkeypatch)
    monkeypatch.setattr(
        pipeline_benchmark,
        "get_benchmark_evidence",
        lambda **_kwargs: {
            "status": "SUCCESS",
            "stats": {"total_pipeline": {"avg": 1.0}},
            "history": [{
                "stage_name": "total_pipeline",
                "duration_seconds": 1.0,
                "timestamp": "2026-08-12T00:00:00",
                "pair": "EURUSD",
                "timeframe": "H1",
                "metadata": {},
            }],
        },
    )
    try:
        response = client.get(
            "/api/robustness/benchmark",
            headers={"Authorization": "Bearer b2-test-secret"},
        )
    finally:
        client.close()

    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"
    assert response.json()["history"][0]["stage"] == "total_pipeline"
    assert response.json()["history"][0]["duration"] == 1.0

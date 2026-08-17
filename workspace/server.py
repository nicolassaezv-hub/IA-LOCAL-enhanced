"""
ASTRA Workspace — Backend (Roadmap IV)
========================================================================
Sirve la SPA (static/) y expone los endpoints reales del Workspace.

Sección 1 — Workspace Principal:
  GET  /api/status     -> barra superior: modelo LLM, proyecto activo, tools,
                          estado de conexión, hora del servidor.

Sección 2 — Barra de Estado Permanente:
  GET  /api/telemetry  -> barra inferior: CPU/RAM/GPU, estado del Active
                          Engine (watchers/jobs), Cognitive Core (memoria/
                          sesión), Evolution Engine (eventos/propuestas
                          pendientes), contador de peticiones a la API y
                          tiempo promedio de respuesta — todo real, medido
                          en este mismo proceso o leído de memoria.db.

Sección 3 — Chat Center:
  POST /api/chat        -> puente real hacia dispatch_command() (el mismo
                           dispatcher estricto de main.py: full forex,
                           monitor snapshot, reglas ver, feedback votar,
                           etc.) con fallback a process_request() (intent
                           router + chat) cuando no hay comando estricto.
                           Devuelve también metadatos: tiempo de ejecución
                           y módulo de ASTRA que respondió.
  GET  /api/chat/history -> últimos turnos reales desde memoria.db.
  POST /api/upload       -> guarda un archivo adjunto en workspace/uploads/.

Sección 4 — Forex Lab Workspace:
  GET  /api/forex/pairs        -> pares con CSV y/o análisis guardado.
  GET  /api/forex/csvs         -> lista de CSVs reales por timeframe.
  GET  /api/forex/csv/info     -> valida estructura + columnas + stats reales.
  GET  /api/forex/csv/ohlc     -> datos OHLC reales para el gráfico de velas.
  GET  /api/forex/dashboard    -> métricas reales por timeframe + último
                                  modelo entrenado (desde forex_memory).
  GET  /api/forex/circuit      -> estado real del Circuit Breaker.
  POST /api/forex/train/start  -> lanza 'full forex <csv>' real en background.
  GET  /api/forex/train/status -> progreso real (parseado del stdout real
                                  del pipeline — sin datos simulados).
  GET  /api/forex/alerts       -> alertas reales generadas por el Workspace.

Sección 7 — Cognitive Center:
  GET  /api/cognitive/*        -> memoria explorable (conversaciones,
                                  proyectos, modelos, timeline, knowledge
                                  graph) + POST /search en lenguaje natural.

Sección 8 — Evolution Center:
  GET  /api/evolution/overview            -> stats agregadas del ciclo
                                             evolutivo (propuestas por
                                             status, ultimo snapshot, audit,
                                             rollback points).
  GET  /api/evolution/timeline            -> historial evolution_events.
  GET  /api/evolution/performance_history -> historial de snapshots.
  GET  /api/evolution/proposals           -> lista (filtro opcional status).
  GET  /api/evolution/proposals/{{id}}      -> detalle + validacion
                                             constitucional en vivo
                                             (preview, no cambia estado).
  POST /api/evolution/proposals/{{id}}/approve   -> aprobacion manual real
                                             (crea rollback point).
  POST /api/evolution/proposals/{{id}}/reject    -> rechazo real.
  POST /api/evolution/proposals/{{id}}/validate   -> flujo de aprobacion
                                             completo (valida contra la
                                             constitucion y aprueba/rechaza).
  GET  /api/evolution/rules               -> catalogo de reglas
                                             constitucionales (builtin+custom).
  GET  /api/evolution/audit               -> audit log inmutable.
  GET  /api/evolution/rollback_points     -> rollback points disponibles.
  POST /api/evolution/rollback_points/{{id}}/apply -> aplica un rollback real.
  POST /api/evolution/cycle/run           -> corre el ciclo evolutivo
                                             completo real (monitor->
                                             detecta->propone->valida->
                                             aprueba->feedback->audit).

Sección 9 — Activity Center:
  GET  /api/activity/feed  -> feed unificado en vivo (alertas + comandos +
                              senales forex + eventos de evolucion),
                              filtrable por fuente (?sources=alert,signal).
  GET  /api/activity/stats -> conteos totales por fuente para tiles.

Cómo correrlo:
  pip install -r requirements.txt   # incluye fastapi, uvicorn, python-multipart
  python workspace/server.py
  -> abre http://localhost:8000
"""
from __future__ import annotations

import os
import re
import sys
import io
import time
import json
import threading
import contextlib
import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ROOT = str(_PROJECT_ROOT)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from astra_version import ASTRA_VERSION
from runtime_security import AuthResult, authenticate_headers, configured_bind_host
from workspace.path_safety import UnsafePathError, resolve_user_path_in_roots
from workspace.upload_storage import store_upload

import memory
import project_memory
from ai_models import _active_model, _GROQ_MODEL, get_session_length
from astra_agent import process_request
from intent_router import analyze_request
from tool_registry import TOOLS
from main import dispatch_command, _category_from_cmd, _extract_pair, _summarize_result
from forex.market_universe import get_market_type
import cognitive_center as _cognitive
import activity_center as _activity
import notification_center as _notif
import live_thinking as _thinking

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    psutil = None
    _HAS_PSUTIL = False

app = FastAPI(title="ASTRA Workspace")

_WORKSPACE_ROOT = Path(__file__).resolve().parent
_STATIC_ROOT = _WORKSPACE_ROOT / "static"
_UPLOAD_ROOT = _WORKSPACE_ROOT / "uploads"
_CSV_ROOT = _PROJECT_ROOT / "CSVs"
_STATIC_DIR = str(_STATIC_ROOT)
_UPLOAD_DIR = str(_UPLOAD_ROOT)
_CSV_BASE = str(_CSV_ROOT)
_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

_PUBLIC_MINIMAL_PATHS = frozenset({"/health", "/api/health"})
_AUTHENTICATED_METADATA_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})


@app.middleware("http")
async def require_api_authentication(request: Request, call_next):
    """Protect every API operation except the deliberately minimal health check."""
    path = request.url.path
    protected = path == "/api" or path.startswith("/api/") or path in _AUTHENTICATED_METADATA_PATHS
    if protected and path not in _PUBLIC_MINIMAL_PATHS:
        auth = authenticate_headers(request.headers)
        if auth is AuthResult.NOT_CONFIGURED:
            return JSONResponse(
                {"error": "API authentication is not configured"},
                status_code=503,
            )
        if auth is not AuthResult.OK:
            return JSONResponse(
                {"error": "Invalid or missing API credentials"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
    return await call_next(request)


def _resolve_client_file(
    candidate: str,
    allowed_roots: tuple[Path, ...],
    suffixes: tuple[str, ...],
) -> Path:
    resolved = resolve_user_path_in_roots(
        _PROJECT_ROOT,
        candidate,
        allowed_roots,
        require_file=True,
    )
    if resolved.suffix.lower() not in suffixes:
        raise UnsafePathError("file type is not allowed for this endpoint")
    return resolved


def _normalized_asset(value: str) -> str:
    asset = value.upper().strip()
    if not re.fullmatch(r"[A-Z0-9_-]{2,24}", asset):
        raise ValueError("asset identifier is invalid")
    return asset


def _normalized_timeframe(value: str) -> str:
    timeframe = value.upper().strip()
    if timeframe not in {"H1", "H4", "D1"}:
        raise ValueError("timeframe is invalid")
    return timeframe


def _cli_result_status(result: object) -> str:
    text = re.sub(r"\x1b\[[0-9;]*m", "", str(result or "")).strip().upper()
    if text.startswith("[ERROR]") or text.startswith("ERROR:"):
        return "ERROR"
    if text.startswith("[UNAVAILABLE]") or "NO DISPONIBLE" in text:
        return "UNAVAILABLE"
    return "SUCCESS"

_SERVER_START = time.time()

# ── Telemetría real de la sesión del Workspace (Sección 2) ──────────────────
_api_request_count = 0
_response_times_ms: list[float] = []  # ventana móvil, últimas N mediciones


def _get_active_project() -> str | None:
    try:
        activos = project_memory.list_projects(status="active")
        if activos:
            return activos[0].get("name")
    except Exception:
        pass
    return None


def _has_api_key() -> bool:
    return bool(os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def _module_label(user_input: str, matched_strict_command: bool) -> str:
    """
    Heurística de etiquetado para metadatos de respuesta (Sección 3.3):
    qué módulo de ASTRA respondió. No cambia la ejecución real, solo
    clasifica el comando ya ejecutado para mostrarlo en el chat.
    """
    t = user_input.lower().strip()
    if not matched_strict_command:
        try:
            analysis = analyze_request(user_input)
            intent = analysis.get("intent", "chat")
        except Exception:
            intent = "chat"
        mapping = {
            "forex_analysis": "Forex Lab", "forex_history": "Forex Lab",
            "forex_compare": "Forex Lab", "forex_markets": "Forex Lab",
            "schedule_forex": "Forex Lab", "watch_forex": "Forex Lab",
            "signal_history": "Forex Lab", "signal_stats": "Forex Lab",
            "news_forex": "Forex Lab", "news_predict": "Forex Lab",
            "lab_analiza": "Prediction Lab",
            "business_analysis": "Business Lab", "business_consult": "Business Lab",
            "business_train": "Business Lab",
            "list_models_memory": "Cognitive Core", "list_projects": "Cognitive Core",
            "memory": "Cognitive Core",
            "system": "Sistema",
        }
        return mapping.get(intent, "Chat General")

    if t.startswith(("full forex", "completo forex", "tune forex", "afinar forex",
                      "train forex", "predict forex", "backtest forex",
                      "watch forex", "watch stop", "watch status", "watch check",
                      "schedule forex", "schedule stop", "schedule status", "schedule run",
                      "señales", "signals", "stats señales", "analiza forex", "noticias")):
        return "Forex Lab"
    if t.startswith("lab "):
        return "Prediction Lab"
    if t.startswith(("feedback", "thresholds", "contextual", "evolucion historial")):
        return "Feedback System"
    if t.startswith(("monitor", "mejoras", "evolucionar", "propuesta", "propuestas", "salud sistema")):
        return "Evolution Engine"
    if t.startswith(("reglas", "audit", "rollback")):
        return "Constitution Engine"
    if t.startswith(("mis proyectos", "nuevo proyecto", "cerrar proyecto", "pausar proyecto",
                      "tareas", "nueva tarea", "completar tarea", "mis modelos", "info modelo")):
        return "Cognitive Core"
    if t.startswith(("estado pc", "cpu", "ram", "circuit", "position size")):
        return "Sistema"
    return "ASTRA Core"


@app.on_event("startup")
def _startup() -> None:
    memory.init_db()
    project_memory.init_project_db()
    # ── Roadmap VI: auto-init sentinel con el par que tiene datos ──
    _auto_init_sentinel()
    # ── Roadmap VI: iniciar scanner de señales en background ───────
    threading.Thread(target=_sentinel_scan_loop, daemon=True).start()


def _auto_init_sentinel() -> None:
    """Registra pares con CSV disponibles en el Market Sentinel al arrancar."""
    import glob
    csv_dirs = {
        "H1": os.path.join(_CSV_BASE, "H1"),
        "H4": os.path.join(_CSV_BASE, "H4"),
        "D1": os.path.join(_CSV_BASE, "D1"),
    }
    pairs_found: set = set()
    for tf, d in csv_dirs.items():
        if not os.path.isdir(d):
            continue
        for f in glob.glob(os.path.join(d, "*.csv")):
            pair = os.path.splitext(os.path.basename(f))[0].upper()
            # Excluir archivos test/broken
            if any(x in pair for x in ("TEST", "TPAIR", "BROKEN")):
                continue
            pairs_found.add(pair)
    for pair in sorted(pairs_found):
        if pair not in _sentinel_state["assets"]:
            _sentinel_state["assets"][pair] = {
                "last_signal": "HOLD",
                "last_reliability": 0.0,
                "scan_count": 0,
            }
    _sentinel_state["assets_monitored"] = len(_sentinel_state["assets"])
    if _sentinel_state["assets"]:
        _sentinel_state["state"] = "running"


_sentinel_scan_results: dict = {}  # pair -> último resultado de predicción

def _sentinel_scan_loop() -> None:
    """Escanea señales de los pares vigilados cada 20 min en background."""
    import time as _time
    _time.sleep(15)  # Esperar a que el servidor arranque completamente
    while True:
        if not _scheduler_paused:
            try:
                _run_sentinel_scans()
            except Exception:
                pass
        _time.sleep(1200)  # 20 minutos


def _run_sentinel_scans() -> None:
    """Ejecuta una predicción rápida sobre cada par vigilado y actualiza el estado."""
    for pair in list(_sentinel_state["assets"].keys()):
        # Buscar CSV H1 del par
        csv_h1 = os.path.join(_CSV_BASE, "H1", f"{pair}.csv")
        if not os.path.exists(csv_h1):
            continue
        try:
            result_str = dispatch_command(f"analiza forex {pair} {csv_h1}")
            if result_str:
                # Parsear señal del resultado
                signal = "HOLD"
                reliability = 0.0
                for line in str(result_str).splitlines():
                    line_l = line.lower()
                    if "signal:" in line_l or "señal:" in line_l:
                        if "buy" in line_l:
                            signal = "BUY"
                        elif "sell" in line_l:
                            signal = "SELL"
                    if "confidence:" in line_l or "confianza:" in line_l:
                        import re as _re
                        m = _re.search(r"[\d.]+", line)
                        if m:
                            try:
                                reliability = round(float(m.group()) * 100, 1)
                            except Exception:
                                pass
                _sentinel_state["assets"][pair] = {
                    "last_signal": signal,
                    "last_reliability": reliability,
                    "scan_count": _sentinel_state["assets"].get(pair, {}).get("scan_count", 0) + 1,
                }
                _sentinel_state["total_scans"] = sum(
                    a.get("scan_count", 0) for a in _sentinel_state["assets"].values()
                )
                _sentinel_scan_results[pair] = {
                    "signal": signal,
                    "reliability": reliability,
                    "full_report": str(result_str)[:2000],
                    "timestamp": datetime.datetime.now().isoformat(),
                }
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════
#  SECCIÓN 1 — Workspace Principal
# ══════════════════════════════════════════════════════════════════


@app.get("/health")
@app.get("/api/health")
def get_health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/api/status")
def get_status() -> JSONResponse:
    connected = _has_api_key()
    data = {
        "astra_status": "online",
        "model": _active_model() if connected else "sin API key",
        "model_configured": _GROQ_MODEL,
        "active_project": _get_active_project(),
        "tools_loaded": len(TOOLS),
        "connected": connected,
        "server_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "uptime_seconds": round(time.time() - _SERVER_START, 1),
    }
    return JSONResponse(data)


# ══════════════════════════════════════════════════════════════════
#  SECCIÓN 2 — Barra de Estado Permanente (telemetría)
# ══════════════════════════════════════════════════════════════════

@app.get("/api/telemetry")
def get_telemetry() -> JSONResponse:
    if _HAS_PSUTIL:
        cpu_pct = psutil.cpu_percent(interval=0.1)
        ram_pct = psutil.virtual_memory().percent
    else:
        cpu_pct, ram_pct = None, None

    gpu_pct = None  # no hay librería de monitoreo GPU en el proyecto — no se simula.

    try:
        from forex_watcher import get_watcher
        active_watchers = len(get_watcher()._watchers)
    except Exception:
        active_watchers = 0
    try:
        from active_engine import get_engine
        active_jobs = len(get_engine()._jobs)
    except Exception:
        active_jobs = 0

    try:
        memory_entries = memory.contar_entradas()
    except Exception:
        memory_entries = 0
    try:
        session_len = get_session_length()
    except Exception:
        session_len = 0

    try:
        from feedback.evolution_memory import get_evolution_history
        evolution_events = len(get_evolution_history(limit=1000))
    except Exception:
        evolution_events = 0
    try:
        from evolution.proposal_store import get_proposals
        pending_proposals = len(get_proposals(status="pending", limit=1000))
    except Exception:
        pending_proposals = 0

    avg_response_ms = (
        round(sum(_response_times_ms) / len(_response_times_ms), 1)
        if _response_times_ms else None
    )

    data = {
        "cpu_percent": cpu_pct,
        "ram_percent": ram_pct,
        "gpu_percent": gpu_pct,
        "gpu_available": False,
        "active_engine": {"watchers_activos": active_watchers, "jobs_programados": active_jobs},
        "cognitive_core": {"memoria_total": memory_entries, "turnos_sesion": session_len},
        "evolution_engine": {"eventos_totales": evolution_events, "propuestas_pendientes": pending_proposals},
        "api_request_count": _api_request_count,
        "avg_response_time_ms": avg_response_ms,
        "connected": _has_api_key(),
        "server_time": datetime.datetime.now().strftime("%H:%M:%S"),
    }
    return JSONResponse(data)


# ══════════════════════════════════════════════════════════════════
#  SECCIÓN 3 — Chat Center
# ══════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
def post_chat(req: ChatRequest) -> JSONResponse:
    global _api_request_count

    user_input = (req.message or "").strip()
    if not user_input:
        return JSONResponse({"response": "", "module": None, "elapsed_ms": 0})

    _api_request_count += 1
    t0 = time.perf_counter()

    try:
        respuesta = dispatch_command(user_input)
    except Exception as e:
        respuesta = f"Error en ASTRA: {e}"

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    _response_times_ms.append(elapsed_ms)
    if len(_response_times_ms) > 50:
        _response_times_ms.pop(0)

    matched_strict = not user_input.lower().startswith(("ayuda", "help", "?"))
    modulo = _module_label(user_input, matched_strict)

    try:
        if user_input.lower() not in ["ayuda", "help", "?"]:
            cat = _category_from_cmd(user_input)
            pair = _extract_pair(user_input)
            summ = _summarize_result(respuesta)
            if summ and len(summ) > 10:
                memory.log_command(user_input, summ, pair=pair, category=cat)
                memory.guardar_memoria(user_input, summ)
    except Exception:
        pass

    return JSONResponse({"response": respuesta, "module": modulo, "elapsed_ms": elapsed_ms})


@app.get("/api/chat/history")
def get_chat_history(limit: int = 20) -> JSONResponse:
    try:
        turnos = memory.cargar_turnos(limit=limit)
    except Exception:
        turnos = []
    return JSONResponse({"turns": turnos})


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)) -> JSONResponse:
    try:
        destination, original_name, size = await store_upload(file, _UPLOAD_ROOT)
    except UnsafePathError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception:
        return JSONResponse({"error": "No se pudo guardar el archivo."}, status_code=500)
    rel_path = destination.relative_to(_PROJECT_ROOT).as_posix()
    return JSONResponse({
        "filename": destination.name,
        "original_filename": original_name,
        "path": rel_path,
        "size": size,
    })


# ══════════════════════════════════════════════════════════════════
#  SECCIÓN 4 — Forex Lab Workspace
# ══════════════════════════════════════════════════════════════════

# ── 4 (Alertas) — feed real de eventos generados por el propio Workspace ──
# Movido a activity_center.py (Sección 9) para que el store de alertas sea
# standalone e importable sin levantar el server. _push_alert queda como
# alias fino para no tocar los ~10 call-sites existentes en este archivo.
_push_alert = _activity.push_alert


@app.get("/api/forex/alerts")
def get_alerts(limit: int = 20) -> JSONResponse:
    return JSONResponse({"alerts": _activity.get_alerts(limit=limit)})


# ── 4 (Pares disponibles) ──────────────────────────────────────────
@app.get("/api/forex/pairs")
def forex_pairs() -> JSONResponse:
    pairs = set()
    h1_dir = os.path.join(_CSV_BASE, "H1")
    if os.path.isdir(h1_dir):
        for f in os.listdir(h1_dir):
            if f.lower().endswith(".csv"):
                pairs.add(f[:-4].upper())
    try:
        from forex.forex_memory import list_saved_markets
        for m in list_saved_markets():
            pairs.add(m.upper())
    except Exception:
        pass
    return JSONResponse({"pairs": sorted(pairs)})


# ── 4 (Gestión de CSV) ──────────────────────────────────────────────
@app.get("/api/forex/csvs")
def list_csvs(timeframe: str = "H1") -> JSONResponse:
    normalized_timeframe = timeframe.upper()
    if normalized_timeframe not in {"H1", "H4", "D1"}:
        return JSONResponse({"error": "Timeframe no permitido"}, status_code=400)
    tf_dir = os.path.join(_CSV_BASE, normalized_timeframe)
    files = []
    if os.path.isdir(tf_dir):
        for f in sorted(os.listdir(tf_dir)):
            if f.lower().endswith(".csv"):
                full = os.path.join(tf_dir, f)
                files.append({
                    "name": f,
                    "path": os.path.relpath(full, _ROOT),
                    "size_kb": round(os.path.getsize(full) / 1024, 1),
                })
    return JSONResponse({"timeframe": normalized_timeframe, "files": files})


_REQUIRED_OHLC = ["open", "high", "low", "close"]


@app.get("/api/forex/csv/info")
def csv_info(path: str) -> JSONResponse:
    try:
        full = _resolve_client_file(path, (_CSV_ROOT, _UPLOAD_ROOT), (".csv",))
    except UnsafePathError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except FileNotFoundError:
        return JSONResponse({"error": "Archivo no encontrado"}, status_code=404)
    try:
        df = pd.read_csv(full)
    except Exception as e:
        _push_alert("error", f"CSV inválido: {path} ({e})")
        return JSONResponse({"error": f"No se pudo leer el CSV: {e}"}, status_code=400)

    cols = list(df.columns)
    lower_cols = [c.lower() for c in cols]
    missing = [r for r in _REQUIRED_OHLC if r not in lower_cols]
    valid = len(missing) == 0

    stats = {}
    close_col = next((c for c in cols if c.lower() == "close"), None)
    if close_col:
        stats = {
            "close_min": round(float(df[close_col].min()), 4),
            "close_max": round(float(df[close_col].max()), 4),
            "close_mean": round(float(df[close_col].mean()), 4),
        }

    date_col = next((c for c in cols if c.lower() in ("timestamp", "date", "datetime", "time")), None)
    date_range = None
    if date_col and len(df) > 0:
        try:
            date_range = {"from": str(df[date_col].iloc[0]), "to": str(df[date_col].iloc[-1])}
        except Exception:
            pass

    if not valid:
        _push_alert("warning", f"Dataset inválido: {path} (faltan columnas: {', '.join(missing)})")

    preview = json.loads(df.head(5).to_json(orient="records"))

    return JSONResponse({
        "path": path, "rows": len(df), "columns": cols, "missing_required": missing,
        "valid": valid, "stats": stats, "date_range": date_range, "preview": preview,
    })


@app.get("/api/forex/csv/ohlc")
def csv_ohlc(path: str, limit: int = 400) -> JSONResponse:
    try:
        full = _resolve_client_file(path, (_CSV_ROOT, _UPLOAD_ROOT), (".csv",))
    except UnsafePathError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except FileNotFoundError:
        return JSONResponse({"error": "Archivo no encontrado"}, status_code=404)
    try:
        df = pd.read_csv(full)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    cols_lower = {c.lower(): c for c in df.columns}
    missing = [r for r in _REQUIRED_OHLC if r not in cols_lower]
    if missing:
        return JSONResponse({"error": f"CSV sin columnas requeridas: {missing}"}, status_code=400)

    date_col = next((cols_lower[c] for c in ("timestamp", "date", "datetime", "time") if c in cols_lower), None)
    df = df.tail(max(1, min(limit, 5000)))

    records = []
    for i, row in df.iterrows():
        t = str(row[date_col])[:10] if date_col else str(i)
        records.append({
            "time": t,
            "open": float(row[cols_lower["open"]]),
            "high": float(row[cols_lower["high"]]),
            "low": float(row[cols_lower["low"]]),
            "close": float(row[cols_lower["close"]]),
        })
    return JSONResponse({"path": path, "data": records})


# ── 4 (Dashboard multi-timeframe) ───────────────────────────────────
@app.get("/api/forex/dashboard")
def forex_dashboard(pair: str) -> JSONResponse:
    try:
        pair_u = _normalized_asset(pair)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    result = {"pair": pair_u, "market_type": get_market_type(pair_u), "timeframes": {}, "model": None}

    for tf in ("H1", "H4", "D1"):
        tf_path = os.path.join(_CSV_BASE, tf, f"{pair_u}.csv")
        if os.path.isfile(tf_path):
            try:
                df = pd.read_csv(tf_path)
                cols_lower = {c.lower(): c for c in df.columns}
                close_col = cols_lower.get("close")
                date_col = next((cols_lower[c] for c in ("timestamp", "date") if c in cols_lower), None)
                result["timeframes"][tf] = {
                    "available": True,
                    "rows": len(df),
                    "last_close": round(float(df[close_col].iloc[-1]), 4) if close_col else None,
                    "date_from": str(df[date_col].iloc[0]) if date_col else None,
                    "date_to": str(df[date_col].iloc[-1]) if date_col else None,
                }
            except Exception as e:
                result["timeframes"][tf] = {"available": True, "error": str(e)}
        else:
            result["timeframes"][tf] = {"available": False}

    try:
        from forex.forex_memory import get_latest_analysis
        report = get_latest_analysis(pair_u)
        if report:
            result["model"] = {
                "trend": report.trend,
                "confidence": report.confidence,
                "ai_summary": report.ai_summary,
                "created_at": report.created_at,
                **(report.metadata or {}),
            }
        else:
            result["model_note"] = "Sin análisis registrado aún — corré 'full forex' para este par."
    except Exception:
        pass

    # Nota de arquitectura: ASTRA entrena UN modelo por par usando features
    # fusionadas de H1+H4+D1 (no 3 modelos independientes por timeframe) —
    # por eso 'model' es compartido y cada timeframe solo aporta datos/stats.
    result["model_architecture_note"] = (
        "El modelo es único por par (fusiona features de H1+H4+D1); "
        "cada timeframe muestra aquí sus datos reales, no un modelo independiente."
    )
    return JSONResponse(result)


# ── 4 (Circuit Breaker visual) ──────────────────────────────────────
@app.get("/api/forex/circuit")
def get_circuit() -> JSONResponse:
    try:
        from forex.prediction.circuit_breaker import get_circuit_breaker
        cb = get_circuit_breaker()
        return JSONResponse(cb.check())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── 4 (Entrenamiento visual — async real con progreso parseado del pipeline) ──
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

_STAGE_LABELS = {
    1: "Optimización de hiperparámetros (Optuna)",
    2: "Entrenamiento del ensemble (XGB+LGB+RF)",
    3: "Generando señal (predicción)",
    4: "Backtesting histórico",
}

_train_lock = threading.Lock()
_train_state = {
    "running": False, "csv_path": None, "pair": None,
    "stage": None, "stage_num": 0, "progress_pct": 0,
    "accuracy": None, "precision": None, "wfv_avg_precision": None, "confidence": None,
    "model_used": "XGBoost + LightGBM + RandomForest (Ensemble calibrado)",
    "started_at": None, "finished_at": None,
    "result_summary": None, "error": None, "log_tail": [], "wfv_blocked": False,
}


class _TrainingStreamTee(io.TextIOBase):
    """
    Reenvía stdout real al proceso Y parsea, en vivo, los marcadores reales
    que ya imprime `_forex_full()` de main.py ([1/4]..[4/4], Accuracy,
    Precision, WFV avg, Confidence) para alimentar la barra de progreso del
    Workspace. No inventa ningún valor — solo interpreta el output real del
    pipeline mientras corre.
    """

    def __init__(self, real_stream):
        self._real = real_stream

    def write(self, s):
        self._real.write(s)
        clean = _ANSI_RE.sub("", s)
        for raw_line in clean.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            with _train_lock:
                _train_state["log_tail"].append(line)
                if len(_train_state["log_tail"]) > 80:
                    _train_state["log_tail"].pop(0)

                m = re.search(r"\[(\d)/4\]", line)
                if m:
                    stage_num = int(m.group(1))
                    prev_stage_num = _train_state["stage_num"]
                    _train_state["stage_num"] = stage_num
                    _train_state["stage"] = _STAGE_LABELS.get(stage_num, line)
                    _train_state["progress_pct"] = round(stage_num / 4 * 100)
                    # Live Thinking (Roadmap IV, Sección 11) — mismo primitivo
                    # transversal que usa Prediction Lab, alimentado aquí desde
                    # el stdout real ya parseado (no se inventa nada nuevo).
                    if prev_stage_num and 1 <= prev_stage_num <= 4:
                        _thinking.set_step("forex_train", prev_stage_num - 1, "done")
                    if 1 <= stage_num <= 4:
                        _thinking.set_step("forex_train", stage_num - 1, "running")

                m2 = re.search(r"Accuracy\s*:\s*([\d.]+)%\s*\|\s*Precision:\s*([\d.]+)%", line)
                if m2:
                    _train_state["accuracy"] = float(m2.group(1))
                    _train_state["precision"] = float(m2.group(2))

                m3 = re.search(r"WFV avg\s*:\s*([\d.]+)%", line)
                if m3:
                    _train_state["wfv_avg_precision"] = float(m3.group(1))

                m4 = re.search(r"Confidence\s*:\s*([\d.]+)", line)
                if m4:
                    _train_state["confidence"] = float(m4.group(1))

                m5 = re.search(r"Par\s*:\s*(\S+)", line)
                if m5:
                    _train_state["pair"] = m5.group(1)

                if "[BLOQUEADO]" in line:
                    _train_state["wfv_blocked"] = True
        return len(s)

    def flush(self):
        self._real.flush()


def _run_training_job(csv_path: str) -> None:
    with _train_lock:
        _train_state.update({
            "running": True, "csv_path": csv_path, "pair": None,
            "stage": "Iniciando", "stage_num": 0, "progress_pct": 0,
            "accuracy": None, "precision": None, "wfv_avg_precision": None, "confidence": None,
            "started_at": time.time(), "finished_at": None,
            "result_summary": None, "error": None, "log_tail": [], "wfv_blocked": False,
        })
    _push_alert("info", f"Entrenamiento iniciado: {csv_path}")
    _thinking.start_thinking("forex_train", list(_STAGE_LABELS.values()), "Forex Full Pipeline")

    real_stdout = sys.stdout
    tee = _TrainingStreamTee(real_stdout)
    try:
        with contextlib.redirect_stdout(tee):
            respuesta = dispatch_command(f"full forex {csv_path}")
        with _train_lock:
            if _train_state.get("wfv_blocked"):
                _train_state["result_summary"] = (
                    "Bloqueado — el modelo reprobó Walk-Forward Validation y no fue "
                    "guardado (no se generó señal ni backtest). Ver log."
                )
            elif _train_state["stage_num"] >= 4:
                _train_state["result_summary"] = _summarize_result(respuesta) or "Pipeline completado — ver métricas y log."
            elif respuesta:
                _train_state["result_summary"] = _summarize_result(respuesta)
            else:
                _train_state["result_summary"] = "El entrenamiento no llegó a completarse — ver log."
            _train_state["progress_pct"] = 100
            _train_state["stage"] = "Completado"
        pair_label = _train_state.get("pair") or csv_path
        _push_alert("success", f"Entrenamiento completado: {pair_label}")
        _notif.push_notification(
            "training_completed", f"Entrenamiento completado: {pair_label}",
            _train_state.get("result_summary") or "", {"csv_path": csv_path, "pair": _train_state.get("pair")},
        )
        # Cognitive Center (Sección 7) lee el historial vía command_log — sin
        # esto, entrenar desde el Forex Lab quedaba invisible para
        # tools_usage/timeline aunque sí generara alerta y notificación.
        try:
            memory.log_command(
                f"full forex {csv_path}",
                _train_state.get("result_summary") or "Entrenamiento completado",
                pair=_train_state.get("pair"), category="forex",
            )
        except Exception:
            pass
        _thinking.finish_thinking("forex_train", ok=True)
    except Exception as e:
        with _train_lock:
            _train_state["error"] = str(e)
        _push_alert("error", f"Error durante entrenamiento: {e}")
        _notif.push_notification(
            "problem_detected", f"Error de entrenamiento: {csv_path}", str(e), {"csv_path": csv_path},
        )
        _thinking.finish_thinking("forex_train", ok=False, error=str(e))
    finally:
        with _train_lock:
            _train_state["running"] = False
            _train_state["finished_at"] = time.time()


class TrainRequest(BaseModel):
    csv_path: str


@app.post("/api/forex/train/start")
def start_training(req: TrainRequest) -> JSONResponse:
    with _train_lock:
        if _train_state["running"]:
            return JSONResponse({"error": "Ya hay un entrenamiento en curso."}, status_code=409)
    try:
        full = _resolve_client_file(req.csv_path, (_CSV_ROOT, _UPLOAD_ROOT), (".csv",))
    except UnsafePathError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except FileNotFoundError:
        return JSONResponse({"error": "CSV no encontrado."}, status_code=404)
    thread = threading.Thread(target=_run_training_job, args=(str(full),), daemon=True)
    thread.start()
    return JSONResponse({"started": True})


@app.get("/api/forex/train/status")
def get_training_status() -> JSONResponse:
    with _train_lock:
        state = dict(_train_state)
    if state["started_at"]:
        end = state["finished_at"] or time.time()
        state["elapsed_seconds"] = round(end - state["started_at"], 1)
    else:
        state["elapsed_seconds"] = 0
    return JSONResponse(state)


# ══════════════════════════════════════════════════════════════════
#  SECCIÓN 5 — Prediction Lab Workspace
# ══════════════════════════════════════════════════════════════════

from prediction_lab.report_generator import run_full_lab, list_lab_reports, _load_lab_report_raw

_lab_lock = threading.Lock()
_lab_state = {
    "running": False, "csv_path": None, "idea": None, "target_variable": None,
    "started_at": None, "finished_at": None,
    "ok": None, "error": None, "stage_reached": None, "saved_path": None,
}


_LAB_THINKING_STEPS = [
    "Analizando Prompt", "Analizando Dataset y variables", "Evaluando viabilidad",
    "Planificando modelos", "Generando pipeline", "Validando y comparando resultados",
]


def _run_lab_job(csv_path: str, idea: str, target_variable: str | None) -> None:
    with _lab_lock:
        _lab_state.update({
            "running": True, "csv_path": csv_path, "idea": idea, "target_variable": target_variable,
            "started_at": time.time(), "finished_at": None,
            "ok": None, "error": None, "stage_reached": None, "saved_path": None,
        })
    _push_alert("info", f"Prediction Lab iniciado: {csv_path}")
    _thinking.start_thinking("prediction_lab", _LAB_THINKING_STEPS, "Prediction Lab")

    def _on_progress(step_idx: int, status: str, detail: str) -> None:
        _thinking.set_step("prediction_lab", step_idx, status, detail)

    try:
        report = run_full_lab(csv_path, idea, target_variable=target_variable or None, progress_cb=_on_progress)
        saved_path = None
        try:
            saved_path = report.save()
        except Exception:
            pass
        with _lab_lock:
            _lab_state["ok"] = report.ok
            _lab_state["error"] = report.error
            _lab_state["stage_reached"] = report.stage_reached
            _lab_state["saved_path"] = saved_path
        if report.ok and report.validation and report.validation.ok:
            _push_alert("success", f"Prediction Lab completado: {report.name} "
                                    f"(score={report.validation.mean_score:.3f}, "
                                    f"{'PASA' if report.validation.passes else 'NO PASA'})")
            _notif.push_notification(
                "prediction_ready", f"Reporte listo: {report.name}",
                f"score={report.validation.mean_score:.3f}, {'PASA' if report.validation.passes else 'NO PASA'}",
                {"csv_path": csv_path, "saved_path": saved_path},
            )
            # Cognitive Center (Sección 7) — mismo motivo que en el fix de
            # Forex train: sin esto, correr el Lab desde el Workspace no
            # aparecía en tools_usage/timeline.
            try:
                memory.log_command(
                    f"lab analiza {csv_path}",
                    f"{report.name}: score={report.validation.mean_score:.3f}, "
                    f"{'PASA' if report.validation.passes else 'NO PASA'}",
                    category="prediction_lab",
                )
            except Exception:
                pass
        elif report.ok:
            _push_alert("warning", f"Prediction Lab detenido en etapa '{report.stage_reached}': {report.error or 'viabilidad insuficiente'}")
            _notif.push_notification(
                "problem_detected", f"Prediction Lab detenido en '{report.stage_reached}'",
                report.error or "viabilidad insuficiente", {"csv_path": csv_path},
            )
        else:
            _push_alert("error", f"Prediction Lab falló en etapa '{report.stage_reached}': {report.error}")
            _notif.push_notification(
                "problem_detected", f"Prediction Lab falló en '{report.stage_reached}'",
                report.error or "", {"csv_path": csv_path},
            )
    except Exception as e:
        with _lab_lock:
            _lab_state["ok"] = False
            _lab_state["error"] = str(e)
        _push_alert("error", f"Error inesperado en Prediction Lab: {e}")
        _notif.push_notification(
            "problem_detected", "Error inesperado en Prediction Lab", str(e), {"csv_path": csv_path},
        )
        _thinking.finish_thinking("prediction_lab", ok=False, error=str(e))
    else:
        _thinking.finish_thinking("prediction_lab", ok=report.ok, error=report.error)
    finally:
        with _lab_lock:
            _lab_state["running"] = False
            _lab_state["finished_at"] = time.time()


class LabRunRequest(BaseModel):
    csv_path: str
    idea: str
    target_variable: str | None = None


@app.post("/api/lab/run")
def lab_run(req: LabRunRequest) -> JSONResponse:
    with _lab_lock:
        if _lab_state["running"]:
            return JSONResponse({"error": "Ya hay un análisis del Prediction Lab en curso."}, status_code=409)
    try:
        full = _resolve_client_file(req.csv_path, (_CSV_ROOT, _UPLOAD_ROOT), (".csv",))
    except UnsafePathError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except FileNotFoundError:
        return JSONResponse({"error": "CSV no encontrado."}, status_code=404)
    if not req.idea or not req.idea.strip():
        return JSONResponse({"error": "Falta describir la idea/problema a resolver."}, status_code=400)
    thread = threading.Thread(target=_run_lab_job, args=(str(full), req.idea, req.target_variable), daemon=True)
    thread.start()
    return JSONResponse({"started": True})


@app.get("/api/lab/run/status")
def lab_run_status() -> JSONResponse:
    with _lab_lock:
        state = dict(_lab_state)
    if state["started_at"]:
        end = state["finished_at"] or time.time()
        state["elapsed_seconds"] = round(end - state["started_at"], 1)
    else:
        state["elapsed_seconds"] = 0
    return JSONResponse(state)


@app.get("/api/lab/projects")
def lab_projects() -> JSONResponse:
    entries = list_lab_reports()
    entries_sorted = sorted(entries, key=lambda e: e.get("timestamp") or "", reverse=True)
    for i, e in enumerate(entries_sorted, start=1):
        e["index"] = i
    return JSONResponse({"projects": entries_sorted})


@app.get("/api/lab/projects/{identifier}")
def lab_project_detail(identifier: str) -> JSONResponse:
    data = _load_lab_report_raw(identifier)
    if data is None:
        return JSONResponse({"error": f"No se encontró el proyecto '{identifier}'."}, status_code=404)
    return JSONResponse(data)


@app.get("/api/lab/available_csvs")
def lab_available_csvs() -> JSONResponse:
    """Escanea ubicaciones conocidas del proyecto para ofrecer un selector rápido
    de CSVs (Forex CSVs/ + adjuntos subidos al Workspace). El usuario también
    puede escribir cualquier otra ruta manualmente — no es una lista cerrada."""
    found = []
    for tf in ("H1", "H4", "D1"):
        tf_dir = os.path.join(_CSV_BASE, tf)
        if os.path.isdir(tf_dir):
            for f in sorted(os.listdir(tf_dir)):
                if f.lower().endswith(".csv"):
                    found.append(os.path.relpath(os.path.join(tf_dir, f), _ROOT))
    if os.path.isdir(_UPLOAD_DIR):
        for f in sorted(os.listdir(_UPLOAD_DIR)):
            if f.lower().endswith(".csv"):
                found.append(os.path.relpath(os.path.join(_UPLOAD_DIR, f), _ROOT))
    return JSONResponse({"csvs": found})


# ══════════════════════════════════════════════════════════════════
#  SECCIÓN 6 — Business Lab Workspace
# ══════════════════════════════════════════════════════════════════
# Todo real sobre forex/business/ (kpi_engine + business_predictor,
# ya existentes y probados) — sin simulación. La proyección de forecast
# reutiliza la MISMA fórmula que sme_consultant.sme_forecast() (extrapolación
# lineal con banda de incertidumbre según trend_strength/R^2), pero devuelve
# números crudos en JSON en vez de un string coloreado para consola.

from forex.business.business_csv_adapter import adapt_business_csv, detect_business_type
from forex.business.kpi_engine import KPIEngine
from forex.business.business_predictor import BusinessPredictor


@app.get("/api/business/csvs")
def business_csvs() -> JSONResponse:
    """Escanea adjuntos subidos al Workspace para el selector — el usuario
    también puede escribir cualquier otra ruta manualmente."""
    found = []
    if os.path.isdir(_UPLOAD_DIR):
        for f in sorted(os.listdir(_UPLOAD_DIR)):
            if f.lower().endswith((".csv", ".xlsx", ".xls")):
                found.append(os.path.relpath(os.path.join(_UPLOAD_DIR, f), _ROOT))
    return JSONResponse({"files": found})


def _business_resolve_path(path: str) -> str | None:
    try:
        full = _resolve_client_file(path, (_UPLOAD_ROOT,), (".csv", ".xlsx", ".xls"))
    except (UnsafePathError, FileNotFoundError):
        return None
    return str(full)


@app.get("/api/business/csv/info")
def business_csv_info(path: str) -> JSONResponse:
    full = _business_resolve_path(path)
    if not full:
        return JSONResponse({"error": "Archivo no encontrado"}, status_code=404)
    try:
        raw = pd.read_csv(full) if full.lower().endswith(".csv") else pd.read_excel(full)
        btype = detect_business_type(raw)
        df = adapt_business_csv(full)
    except Exception as e:
        return JSONResponse({"error": f"No se pudo leer/normalizar el archivo: {e}"}, status_code=400)

    preview = json.loads(df.head(5).to_json(orient="records", date_format="iso"))
    return JSONResponse({
        "path": path,
        "rows": len(df),
        "business_type": btype,
        "raw_columns": list(raw.columns),
        "normalized_columns": [c for c in df.columns if df[c].notna().any()],
        "preview": preview,
    })


@app.post("/api/business/analyze")
def business_analyze(req: dict) -> JSONResponse:
    """
    Corre el análisis real completo en un solo paso (síncrono — KPIEngine y
    LogisticRegression sobre datos tabulares de negocio son rápidos, no
    necesitan hilo de fondo como el entrenamiento Forex/Optuna):
      1. Normaliza el CSV/Excel real (business_csv_adapter).
      2. KPIs reales (KPIEngine.compute_all()).
      3. Entrena el predictor real sobre el propio dataset (BusinessPredictor.train()).
      4. Predicción real del próximo período con el modelo recién entrenado
         (o heurística si hay pocos datos — igual que el fallback real de
         BusinessPredictor.predict()).
      5. Proyección de forecast real (misma fórmula que sme_forecast()).
    """
    csv_path = (req or {}).get("csv_path", "")
    months = int((req or {}).get("months", 6) or 6)
    full = _business_resolve_path(csv_path)
    if not full:
        return JSONResponse({"error": "Archivo no encontrado"}, status_code=404)

    try:
        df = adapt_business_csv(full)
    except Exception as e:
        return JSONResponse({"error": f"No se pudo normalizar el archivo: {e}"}, status_code=400)

    kpis = KPIEngine(df).compute_all()

    predictor = BusinessPredictor()
    train_result = predictor.train(df)
    predict_result = predictor.predict(df)

    slope = kpis.get("trend_slope") or 0.0
    strength = kpis.get("trend_strength") or 0.0
    latest = kpis.get("latest_revenue")
    avg_rev = kpis.get("avg_revenue")
    forecast = None
    if latest is not None and avg_rev:
        uncertainty = max((1 - strength) * abs(avg_rev) * 0.20, abs(avg_rev) * 0.03)
        points = []
        for i in range(1, months + 1):
            expected = latest + slope * i
            points.append({
                "month": i,
                "optimistic": round(expected + uncertainty * (1 + i * 0.05), 2),
                "expected": round(expected, 2),
                "conservative": round(expected - uncertainty * (1 + i * 0.05), 2),
            })
        final_expected = points[-1]["expected"]
        pct_change = ((final_expected - latest) / abs(latest) * 100) if latest else 0
        forecast = {
            "months": months,
            "points": points,
            "confidence_pct": round(strength * 100, 1),
            "final_expected": final_expected,
            "pct_change_vs_latest": round(pct_change, 1),
            "uncertainty_band": round(uncertainty, 2),
        }

    _push_alert("success", f"Business Lab: análisis completado para {os.path.basename(csv_path)} "
                            f"(health={kpis.get('health_score')}/100, {kpis.get('trend_direction')})")
    _notif.push_notification(
        "business_analysis_ready", f"Análisis listo: {os.path.basename(csv_path)}",
        f"health={kpis.get('health_score')}/100, {kpis.get('trend_direction')}",
        {"csv_path": csv_path},
    )
    # Cognitive Center (Sección 7) — mismo fix que en Forex train / Prediction
    # Lab: sin esto, correr el análisis desde el Workspace no quedaba en
    # tools_usage/timeline aunque sí generara alerta y notificación.
    try:
        memory.log_command(
            f"forecast negocio {csv_path} {months}",
            f"health={kpis.get('health_score')}/100, {kpis.get('trend_direction')}",
            category="business",
        )
    except Exception:
        pass

    return JSONResponse({
        "csv_path": csv_path,
        "business_type": kpis.get("business_type"),
        "kpis": kpis,
        "train": train_result,
        "predict": predict_result,
        "forecast": forecast,
    })


# ══════════════════════════════════════════════════════════════
# COGNITIVE CENTER — Roadmap IV, Seccion 7
# Ventana exclusiva para la memoria: conversaciones, proyectos,
# modelos, herramientas, preferencias, timeline y knowledge graph
# sobre memory.py / project_memory.py / feedback/*, mas busqueda en
# lenguaje natural (LLM con fallback heuristico). Todo real, sin
# datos simulados — ver cognitive_center.py.
# ══════════════════════════════════════════════════════════════

@app.get("/api/cognitive/overview")
def cognitive_overview() -> JSONResponse:
    """Resumen agregado para el panel principal del Cognitive Center."""
    try:
        overview = _cognitive.get_projects_overview()
        tools = _cognitive.get_tools_usage()
        prefs = _cognitive.get_learned_preferences()
        return JSONResponse({
            "conversations_total": memory.contar_entradas(),
            "projects_total": len(overview["projects"]),
            "models_total": len(overview["models"]),
            "tasks_pending": sum(1 for t in overview["tasks"] if not t.get("done")),
            "tasks_total": len(overview["tasks"]),
            "commands_logged": tools["total_logged"],
            "by_category": tools["by_category"],
            "top_commands": tools["top_commands"],
            "pairs_with_custom_thresholds": len(prefs["adaptive_thresholds"]),
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/cognitive/conversations")
def cognitive_conversations(limit: int = 50) -> JSONResponse:
    try:
        return JSONResponse({"conversations": _cognitive.get_conversations(limit=limit)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/cognitive/projects")
def cognitive_projects() -> JSONResponse:
    try:
        return JSONResponse(_cognitive.get_projects_overview())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/cognitive/tools_usage")
def cognitive_tools_usage(limit: int = 200) -> JSONResponse:
    try:
        return JSONResponse(_cognitive.get_tools_usage(limit=limit))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/cognitive/preferences")
def cognitive_preferences() -> JSONResponse:
    try:
        return JSONResponse(_cognitive.get_learned_preferences())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/cognitive/timeline")
def cognitive_timeline(limit: int = 100) -> JSONResponse:
    try:
        return JSONResponse({"events": _cognitive.get_timeline(limit=limit)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/cognitive/knowledge_graph")
def cognitive_knowledge_graph() -> JSONResponse:
    try:
        return JSONResponse(_cognitive.build_knowledge_graph())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/cognitive/search")
def cognitive_search(req: dict) -> JSONResponse:
    query = (req or {}).get("query", "").strip()
    if not query:
        return JSONResponse({"error": "query vacia"}, status_code=400)
    try:
        return JSONResponse(_cognitive.search_memory(query))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ══════════════════════════════════════════════════════════════
# EVOLUTION CENTER — Roadmap IV, Seccion 8
# Ventana sobre evolution/ + constitution/ + evolutionary_cycle.py
# (Fases 7-9, ya operativas): panel del ciclo evolutivo, revision
# y aprobacion/rechazo de propuestas, reglas constitucionales,
# audit log y rollback points. Todo real — ver evolution_center.py.
# ══════════════════════════════════════════════════════════════

import evolution_center as _evolution


def _evo_response(result: dict, not_found_msg: str = "no encontrada") -> JSONResponse:
    """Traduce el patron {"ok": bool, "error": ...} de evolution_center.py
    a status codes HTTP (404 si el error menciona 'no encontrada', 500 en
    cualquier otro error, 200 si ok)."""
    if result.get("ok") is False:
        err = str(result.get("error", ""))
        status = 404 if not_found_msg in err else 400
        return JSONResponse(result, status_code=status)
    return JSONResponse(result)


@app.get("/api/evolution/overview")
def evolution_overview() -> JSONResponse:
    return _evo_response(_evolution.get_cycle_overview())


@app.get("/api/evolution/timeline")
def evolution_timeline(limit: int = 40) -> JSONResponse:
    return _evo_response(_evolution.get_evolution_timeline(limit=limit))


@app.get("/api/evolution/performance_history")
def evolution_performance_history(limit: int = 20) -> JSONResponse:
    return _evo_response(_evolution.get_performance_history(limit=limit))


@app.get("/api/evolution/proposals")
def evolution_proposals(status: str = "", limit: int = 50) -> JSONResponse:
    return _evo_response(_evolution.get_proposals_list(status=status or None, limit=limit))


@app.get("/api/evolution/proposals/{proposal_id}")
def evolution_proposal_detail(proposal_id: int) -> JSONResponse:
    return _evo_response(_evolution.get_proposal_detail(proposal_id))


@app.post("/api/evolution/proposals/{proposal_id}/approve")
def evolution_proposal_approve(proposal_id: int, req: dict = None) -> JSONResponse:
    justification = (req or {}).get("justification", "")
    return _evo_response(_evolution.approve_proposal(proposal_id, justification))


@app.post("/api/evolution/proposals/{proposal_id}/reject")
def evolution_proposal_reject(proposal_id: int, req: dict = None) -> JSONResponse:
    reason = (req or {}).get("reason", "")
    return _evo_response(_evolution.reject_proposal(proposal_id, reason))


@app.post("/api/evolution/proposals/{proposal_id}/validate")
def evolution_proposal_validate(proposal_id: int) -> JSONResponse:
    return _evo_response(_evolution.validate_proposal_constitutional(proposal_id))


@app.get("/api/evolution/rules")
def evolution_rules() -> JSONResponse:
    return _evo_response(_evolution.get_constitution_rules())


@app.get("/api/evolution/audit")
def evolution_audit(target: str = "", limit: int = 50) -> JSONResponse:
    return _evo_response(_evolution.get_audit_log(target=target or None, limit=limit))


@app.get("/api/evolution/rollback_points")
def evolution_rollback_points(limit: int = 30) -> JSONResponse:
    return _evo_response(_evolution.get_rollback_points(limit=limit))


@app.post("/api/evolution/rollback_points/{point_id}/apply")
def evolution_rollback_apply(point_id: int) -> JSONResponse:
    return _evo_response(_evolution.apply_rollback(point_id))


@app.post("/api/evolution/cycle/run")
def evolution_cycle_run(req: dict = None) -> JSONResponse:
    auto_approve_minor = bool((req or {}).get("auto_approve_minor", False))
    return _evo_response(_evolution.trigger_evolutionary_cycle(auto_approve_minor=auto_approve_minor))


# ══════════════════════════════════════════════════════════════
# ACTIVITY CENTER — Roadmap IV, Seccion 9
# Feed unificado en vivo: alertas del Workspace + comandos ejecutados +
# senales forex + eventos de evolucion, fusionados y ordenados por
# timestamp real. Ver activity_center.py.
# ══════════════════════════════════════════════════════════════

@app.get("/api/activity/feed")
def activity_feed(limit: int = 50, sources: str = "") -> JSONResponse:
    src_list = [s.strip() for s in sources.split(",") if s.strip()] or None
    try:
        return JSONResponse(_activity.get_activity_feed(limit=limit, sources=src_list))
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/activity/stats")
def activity_stats() -> JSONResponse:
    try:
        return JSONResponse(_activity.get_activity_stats())
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ══════════════════════════════════════════════════════════════
# LIVE THINKING — Roadmap IV, Seccion 11
# Razonamiento operativo visible, TRANSVERSAL a los Labs (Prediction Lab
# y Forex full pipeline publican aqui su avance paso a paso). Ver
# live_thinking.py.
# ══════════════════════════════════════════════════════════════

@app.get("/api/thinking")
def thinking_all() -> JSONResponse:
    """Devuelve el estado de TODAS las sesiones de pensamiento conocidas
    (prediction_lab, forex_train), activas o no. El frontend decide cual
    mostrar (activa) o si mostrar ninguna."""
    return JSONResponse({"ok": True, "sessions": _thinking.get_all_thinking()})


@app.get("/api/thinking/{task_key}")
def thinking_one(task_key: str) -> JSONResponse:
    session = _thinking.get_thinking(task_key)
    if session is None:
        return JSONResponse({"ok": False, "error": f"sin sesión para '{task_key}'"})
    return JSONResponse({"ok": True, "session": session})


# ══════════════════════════════════════════════════════════════
# NOTIFICATION CENTER — Roadmap IV, Seccion 10
# Notificaciones PERSISTIDAS y consultables (sobreviven a un reinicio),
# a diferencia del feed en vivo/efimero del Activity Center. Ver
# notification_center.py.
# ══════════════════════════════════════════════════════════════

@app.get("/api/notifications")
def notifications_list(limit: int = 30, unread_only: bool = False, ntype: str = "") -> JSONResponse:
    items = _notif.get_notifications(limit=limit, unread_only=unread_only, ntype=ntype or None)
    return JSONResponse({"ok": True, "items": items, "total": len(items)})


@app.get("/api/notifications/stats")
def notifications_stats() -> JSONResponse:
    return JSONResponse(_notif.get_notification_stats())


@app.post("/api/notifications/{notification_id}/read")
def notifications_mark_read(notification_id: int) -> JSONResponse:
    changed = _notif.mark_read(notification_id)
    return JSONResponse({"ok": changed})


@app.post("/api/notifications/read-all")
def notifications_mark_all_read() -> JSONResponse:
    count = _notif.mark_all_read()
    return JSONResponse({"ok": True, "marked": count})


# ══════════════════════════════════════════════════════════════
# DASHBOARD ACTIVO — Roadmap V, Sección 13 (V.16)
# Estado en tiempo real del sistema autónomo: Market Sentinel (V.10),
# Scheduler Inteligente (V.12), Señales Activas (V.1+V.8),
# Datasets (V.11) y controles de Reentrenamiento (V.13).
# ══════════════════════════════════════════════════════════════

# Estado en memoria del Sentinel y Scheduler (se actualiza vía endpoints POST)
_sentinel_state: dict = {
    "state": "idle",
    "circuit_breaker_active": False,
    "assets_monitored": 0,
    "total_scans": 0,
    "assets": {},
}
_scheduler_paused: bool = False


@app.get("/api/sentinel/status")
def sentinel_status() -> JSONResponse:
    """Estado actual del Market Sentinel (V.10)."""
    try:
        import sqlite3
        recent: list = []
        db_path = os.path.join(_ROOT, "memoria.db")
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                try:
                    rows = conn.execute(
                        "SELECT command, result, created_at FROM command_log "
                        "WHERE command LIKE '%sentinel%' OR command LIKE '%market%' "
                        "ORDER BY created_at DESC LIMIT 10"
                    ).fetchall()
                    recent = [dict(r) for r in rows]
                except Exception:
                    pass
        return JSONResponse({
            "ok": True,
            "state": _sentinel_state["state"],
            "circuit_breaker_active": _sentinel_state["circuit_breaker_active"],
            "assets_monitored": _sentinel_state["assets_monitored"],
            "total_scans": _sentinel_state["total_scans"],
            "assets": _sentinel_state["assets"],
            "recent_activity": recent,
        })
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/scheduler/tasks")
def scheduler_tasks() -> JSONResponse:
    """Tareas del Scheduler Inteligente (V.12)."""
    try:
        tasks: dict = {}
        try:
            import active_engine as _engine
            fn = getattr(_engine, "get_scheduler_status", None)
            if callable(fn):
                result = fn()
                if isinstance(result, dict):
                    tasks = result
        except Exception:
            pass
        return JSONResponse({
            "ok": True,
            "running": not _scheduler_paused,
            "task_count": len(tasks),
            "tasks": tasks,
        })
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/signals/active")
def signals_active() -> JSONResponse:
    """Señales activas con Reliability >= 50 (V.1 + V.8)."""
    try:
        import sqlite3
        signals: list = []
        db_path = os.path.join(_ROOT, "memoria.db")
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                try:
                    rows = conn.execute(
                        "SELECT pair, timeframe, signal, confidence, reliability, regime, created_at "
                        "FROM forex_analytics ORDER BY created_at DESC LIMIT 30"
                    ).fetchall()
                    for r in rows:
                        row = dict(r)
                        rel = float(row.get("reliability") or 0)
                        if rel >= 50:
                            signals.append({
                                "pair": row.get("pair", ""),
                                "timeframe": row.get("timeframe", "H1"),
                                "signal": row.get("signal", "HOLD"),
                                "confidence": round(float(row.get("confidence") or 0), 2),
                                "reliability": round(rel, 1),
                                "regime": row.get("regime", ""),
                                "ts": row.get("created_at", ""),
                            })
                except Exception:
                    pass
        return JSONResponse({"ok": True, "signals": signals, "count": len(signals)})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e), "signals": []})


@app.get("/api/datasets/status")
def datasets_status() -> JSONResponse:
    """Estado y antigüedad de los datasets CSV disponibles (V.11)."""
    try:
        datasets: list = []
        for tf in ("H1", "H4", "D1"):
            tf_dir = os.path.join(_CSV_BASE, tf)
            if not os.path.isdir(tf_dir):
                continue
            for fname in sorted(os.listdir(tf_dir)):
                if not fname.endswith(".csv"):
                    continue
                pair = fname[:-4]
                fpath = os.path.join(tf_dir, fname)
                age_h = (time.time() - os.path.getmtime(fpath)) / 3600
                try:
                    df = pd.read_csv(fpath, nrows=0)
                    with open(fpath) as fh:
                        rows = sum(1 for _ in fh) - 1
                except Exception:
                    rows = 0
                datasets.append({
                    "pair": pair,
                    "timeframe": tf,
                    "rows": rows,
                    "age_hours": round(age_h, 1),
                })
        return JSONResponse({"ok": True, "datasets": datasets, "count": len(datasets)})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e), "datasets": []})


class _SentinelPairBody(BaseModel):
    pair: str


@app.post("/api/sentinel/add")
def sentinel_add(body: _SentinelPairBody) -> JSONResponse:
    """Añade un par al Market Sentinel (V.10)."""
    try:
        pair = _normalized_asset(body.pair)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    if pair not in _sentinel_state["assets"]:
        _sentinel_state["assets"][pair] = {
            "last_signal": "HOLD",
            "last_reliability": 0.0,
            "scan_count": 0,
        }
        _sentinel_state["assets_monitored"] = len(_sentinel_state["assets"])
        _sentinel_state["state"] = "running"
    return JSONResponse({"ok": True, "pair": pair,
                         "assets_monitored": _sentinel_state["assets_monitored"]})


@app.post("/api/sentinel/remove")
def sentinel_remove(body: _SentinelPairBody) -> JSONResponse:
    """Quita un par del Market Sentinel (V.10)."""
    try:
        pair = _normalized_asset(body.pair)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    _sentinel_state["assets"].pop(pair, None)
    _sentinel_state["assets_monitored"] = len(_sentinel_state["assets"])
    if not _sentinel_state["assets"]:
        _sentinel_state["state"] = "idle"
    return JSONResponse({"ok": True, "pair": pair,
                         "assets_monitored": _sentinel_state["assets_monitored"]})


@app.post("/api/scheduler/pause")
def scheduler_pause() -> JSONResponse:
    """Pausa el Scheduler Inteligente (V.12)."""
    global _scheduler_paused
    _scheduler_paused = True
    return JSONResponse({"ok": True, "running": False})


@app.post("/api/scheduler/resume")
def scheduler_resume() -> JSONResponse:
    """Reanuda el Scheduler Inteligente (V.12)."""
    global _scheduler_paused
    _scheduler_paused = False
    return JSONResponse({"ok": True, "running": True})


class _DatasetUpdateBody(BaseModel):
    pair: str
    timeframe: str = "H1"


@app.post("/api/datasets/force_update")
def datasets_force_update(body: _DatasetUpdateBody) -> JSONResponse:
    """Fuerza actualización incremental de un dataset (V.11)."""
    try:
        pair = _normalized_asset(body.pair)
        tf = _normalized_timeframe(body.timeframe)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    try:
        result = dispatch_command(f"actualizar csv {pair} {tf}")
        return JSONResponse({"ok": True, "pair": pair, "timeframe": tf,
                              "result": str(result)[:500]})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


class _RetrainBody(BaseModel):
    pair: str
    timeframe: str = "H1"


@app.post("/api/retrain/force")
def retrain_force(body: _RetrainBody) -> JSONResponse:
    """Legacy-named full run that cannot bypass production promotion gates.

    The route name remains for compatibility and is semantically misleading:
    tune is diagnostic-only, while train can publish solely through the full
    RetrainManager eligibility contract.
    """
    try:
        pair = _normalized_asset(body.pair)
        tf = _normalized_timeframe(body.timeframe)
        csv_path = resolve_user_path_in_roots(
            _CSV_ROOT,
            f"{tf}/{pair}.csv",
            (_CSV_ROOT,),
            require_file=True,
        )
    except (ValueError, UnsafePathError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    except FileNotFoundError:
        return JSONResponse({"ok": False, "error": "CSV no encontrado"}, status_code=404)
    def _run() -> None:
        try:
            dispatch_command(f"full forex {csv_path}")
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"ok": True, "pair": pair, "timeframe": tf,
                          "status": "entrenamiento iniciado en background"})


# ══════════════════════════════════════════════════════════════════
#  SECCIÓN 14 — Configuración del sistema
# ══════════════════════════════════════════════════════════════════

@app.get("/api/config")
def get_config() -> JSONResponse:
    """Panel Configuración: estado completo del sistema, versión, API key, entorno."""
    import sys, platform
    connected = _has_api_key()
    has_groq = bool(os.environ.get("GROQ_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))

    uptime_s = round(time.time() - _SERVER_START, 0)
    h, rem = divmod(int(uptime_s), 3600)
    m, s = divmod(rem, 60)
    uptime_str = f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

    # Conteos de memoria
    total_mem = 0
    try:
        import memory as _mem
        rows = _mem.get_history(limit=9999)
        total_mem = len(rows) if rows else 0
    except Exception:
        pass

    # Módulos cargados
    n_cognitive = sum(1 for m in ["cognitive_center", "activity_center",
                                   "evolution_center", "notification_center",
                                   "live_thinking"] if m in sys.modules)

    return JSONResponse({
        "ok": True,
        "version": ASTRA_VERSION,
        "astra_status": "online",
        "connected": connected,
        "api_keys": {
            "groq": has_groq,
            "openai": has_openai,
            "active_provider": "Groq" if has_groq else ("OpenAI" if has_openai else "ninguno"),
        },
        "model_active": _active_model() if connected else "sin API key",
        "model_configured": _GROQ_MODEL,
        "tools_loaded": len(TOOLS),
        "memory_entries": total_mem,
        "workspace_modules": n_cognitive,
        "python_version": sys.version.split()[0],
        "platform": platform.system(),
        "uptime": uptime_str,
        "uptime_seconds": int(uptime_s),
        "server_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "csv_base": "CSVs",
        "upload_dir": "workspace/uploads",
    })


# ══════════════════════════════════════════════════════════════════
#  SECCIÓN 15 — Roadmap VI: Data Intelligence & Autonomía
# ══════════════════════════════════════════════════════════════════

@app.get("/api/roadmap6/status")
def roadmap6_status() -> JSONResponse:
    """Estado completo del ecosistema Roadmap VI: scheduler, sentinel, hparam cache,
    model cache, rolling datasets, opportunity ranking y data intelligence."""
    result: dict = {"ok": True}

    # ── Hyperparameter Cache ──────────────────────────────────────
    try:
        from forex.prediction.hyperparameter_cache import get_cache
        cache = get_cache()
        entries = cache.list_cached()
        result["hparam_cache"] = {
            "ok": True,
            "total": len(entries),
            "entries": [
                {
                    "pair": e.get("pair", "?"),
                    "horizon": e.get("horizon", "?"),
                    "accuracy": round(float(e.get("accuracy", 0)) * 100, 1),
                    "trials": e.get("n_trials", 0),
                    "updated": str(e.get("updated_at", ""))[:19],
                }
                for e in (entries or [])[:10]
            ],
        }
    except Exception as ex:
        result["hparam_cache"] = {"ok": False, "error": str(ex)[:120]}

    # ── Model Cache ───────────────────────────────────────────────
    try:
        from forex.prediction.model_cache import get_model_cache
        # ModelCacheManager no tiene list_cached() — query SQLite directa
        import sqlite3 as _sqlite3
        _mc_db = os.path.join(_ROOT, "astra_hparam_cache.db")
        entries_mc = []
        if os.path.exists(_mc_db):
            with _sqlite3.connect(_mc_db) as _conn:
                _conn.row_factory = _sqlite3.Row
                try:
                    rows_mc = _conn.execute(
                        "SELECT pair, horizon, accuracy, row_count, created_at "
                        "FROM model_version_log WHERE is_active=1 "
                        "ORDER BY created_at DESC LIMIT 10"
                    ).fetchall()
                    entries_mc = [dict(r) for r in rows_mc]
                except Exception:
                    pass
        result["model_cache"] = {
            "ok": True,
            "total": len(entries_mc),
            "entries": [
                {
                    "pair": e.get("pair", "?"),
                    "horizon": e.get("horizon", "?"),
                    "accuracy": round(float(e.get("accuracy") or 0) * 100, 1),
                    "rows": e.get("row_count", 0),
                    "updated": str(e.get("created_at", ""))[:19],
                }
                for e in entries_mc
            ],
        }
    except Exception as ex:
        result["model_cache"] = {"ok": False, "error": str(ex)[:120]}

    # ── Rolling Datasets — usa csv_dir (directorio), no csv_path ──
    try:
        import glob as _glob
        from forex.data.rolling_dataset import RollingDataset
        rolling: list = []
        for tf_dir in ["H1", "H4", "D1"]:
            d = os.path.join(_CSV_BASE, tf_dir)
            if not os.path.isdir(d):
                continue
            for csv_f in _glob.glob(os.path.join(d, "*.csv")):
                pair_name = os.path.splitext(os.path.basename(csv_f))[0].upper()
                if any(x in pair_name for x in ("TEST", "TPAIR", "BROKEN")):
                    continue
                try:
                    rd = RollingDataset(pair_name, tf_dir, csv_dir=d)
                    loaded = rd.load()
                    if not loaded:
                        continue
                    val = rd.validate()
                    is_ok = val.get("ok", True) if isinstance(val, dict) else True
                    errs = val.get("issues", []) if isinstance(val, dict) else []
                    rows = len(rd._df) if rd._df is not None else 0
                    rolling.append({
                        "pair": pair_name,
                        "timeframe": tf_dir,
                        "rows": rows,
                        "valid": is_ok,
                        "errors": errs[:3] if isinstance(errs, list) else [],
                    })
                except Exception:
                    pass
        result["rolling_datasets"] = {"ok": True, "datasets": rolling, "total": len(rolling)}
    except Exception as ex:
        result["rolling_datasets"] = {"ok": False, "error": str(ex)[:120]}

    # ── Autonomous Scheduler ──────────────────────────────────────
    try:
        sched_text = dispatch_command("scheduler info")
        running = "activo" in str(sched_text).lower() or "running" in str(sched_text).lower()
        result["autonomous_scheduler"] = {
            "ok": True,
            "running": running,
            "text": str(sched_text)[:500],
        }
    except Exception as ex:
        result["autonomous_scheduler"] = {"ok": False, "error": str(ex)[:120]}

    # ── Opportunity Ranking — vía dispatch_command (ya funciona) ──
    try:
        rank_text = dispatch_command("opportunity ranking 10")
        # Parsear número de elegibles del texto
        eligible = 0
        ops_parsed = []
        for line in str(rank_text).splitlines():
            if "elegibles:" in line.lower():
                import re as _re2
                m = _re2.search(r"(\d+)", line)
                if m:
                    eligible = int(m.group(1))
            if "BUY" in line or "SELL" in line:
                parts = line.split()
                if len(parts) >= 2:
                    ops_parsed.append({"pair": parts[0].strip(), "signal": "BUY" if "BUY" in line else "SELL",
                                       "score": 0.0, "regime": ""})
        result["opportunity_ranking"] = {
            "ok": True,
            "eligible": eligible,
            "opportunities": ops_parsed[:10],
            "total": len(ops_parsed),
            "text": str(rank_text)[:800],
        }
    except Exception as ex:
        result["opportunity_ranking"] = {"ok": False, "error": str(ex)[:120], "opportunities": []}

    # ── Sentinel scan results ─────────────────────────────────────
    result["sentinel"] = {
        "state": _sentinel_state["state"],
        "assets_monitored": _sentinel_state["assets_monitored"],
        "total_scans": _sentinel_state["total_scans"],
        "assets": _sentinel_state["assets"],
        "scan_results": {
            pair: {"signal": v["signal"], "reliability": v["reliability"],
                   "timestamp": v["timestamp"]}
            for pair, v in _sentinel_scan_results.items()
        },
    }

    return JSONResponse(result)


@app.get("/api/roadmap6/hparam_cache")
def roadmap6_hparam_cache() -> JSONResponse:
    """Hyperparameter Cache status (VI.1.A)."""
    try:
        result_str = dispatch_command("hparam cache")
        return JSONResponse({"ok": True, "text": str(result_str)})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/roadmap6/model_cache")
def roadmap6_model_cache() -> JSONResponse:
    """Model Cache status (VI.1.C)."""
    try:
        result_str = dispatch_command("model cache")
        return JSONResponse({"ok": True, "text": str(result_str)})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


class _CandlestickBody(BaseModel):
    csv_path: str
    pair: str = "UNKNOWN"
    timeframe: str = "H1"


@app.post("/api/roadmap6/candlestick")
def roadmap6_candlestick(body: _CandlestickBody) -> JSONResponse:
    """Detecta patrones de vela japonesa (VI.5.D)."""
    try:
        csv_path = _resolve_client_file(body.csv_path, (_CSV_ROOT, _UPLOAD_ROOT), (".csv",))
        result_str = dispatch_command(f"candlestick {csv_path}")
        return JSONResponse({"ok": True, "text": str(result_str)})
    except UnsafePathError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    except FileNotFoundError:
        return JSONResponse({"ok": False, "error": "CSV no encontrado"}, status_code=404)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/roadmap6/opportunity_ranking")
def roadmap6_opportunity_ranking(n: int = 10) -> JSONResponse:
    """Opportunity Ranking (VI.8.A) — Top N señales por OpScore."""
    try:
        result_str = dispatch_command(f"opportunity ranking {n}")
        return JSONResponse({"ok": True, "text": str(result_str)})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/roadmap6/self_test")
def roadmap6_self_test() -> JSONResponse:
    """Diagnóstico rápido del sistema (VI.2.B) — verifica módulos, DBs, CSVs y API."""
    ok_checks: list = []
    warnings: list = []
    errors: list = []

    def _chk(label: str, fn):
        try:
            result = fn()
            if result is False:
                errors.append(label)
            elif isinstance(result, str) and result:
                ok_checks.append(f"{label}: {result}")
            else:
                ok_checks.append(label)
        except ImportError as e:
            warnings.append(f"{label}: módulo no instalado ({str(e)[:60]})")
        except Exception as e:
            errors.append(f"{label}: {str(e)[:80]}")

    # ── Core modules ──
    _chk("memory.db", lambda: __import__("memory").init_db() or True)
    _chk("intent_router", lambda: __import__("intent_router"))
    _chk("tool_registry", lambda: __import__("tool_registry"))
    _chk("astra_agent", lambda: __import__("astra_agent"))
    _chk("argument_parser", lambda: __import__("argument_parser"))
    _chk("io_files", lambda: __import__("io_files"))
    _chk("security", lambda: __import__("security"))
    _chk("web_tools", lambda: __import__("web_tools"))

    # ── Roadmap V modules ──
    for mod in [
        "forex.prediction.decision_engine",
        "forex.prediction.risk_engine",
        "forex.prediction.reliability_score",
        "forex.prediction.regime_detector",
        "forex.prediction.mtf_coherence",
        "forex.prediction.model_selector",
    ]:
        _chk(mod, lambda m=mod: __import__(m))

    # ── Roadmap VI modules ──
    for mod in [
        "forex.prediction.hyperparameter_cache",
        "forex.prediction.model_cache",
        "forex.scheduler.autonomous_scheduler",
        "forex.portfolio.opportunity_score",
        "forex.portfolio.portfolio_ranker",
        "check_system",
    ]:
        _chk(mod, lambda m=mod: __import__(m))

    # ── API key ──
    _chk("GROQ_API_KEY", lambda: os.environ.get("GROQ_API_KEY", "") != "" or False)

    # ── Hyperparameter cache DB ──
    import sqlite3 as _sql
    _hp_db = os.path.join(_ROOT, "astra_hparam_cache.db")
    _chk("hparam_cache.db", lambda: os.path.exists(_hp_db) or False)

    # ── CSV files ──
    import glob as _gl
    h1_csvs = _gl.glob(os.path.join(_CSV_BASE, "H1", "*.csv"))
    _chk(f"CSVs H1 ({len(h1_csvs)} archivos)", lambda c=len(h1_csvs): c > 0 or False)

    # ── Sentinel state ──
    _chk(f"Market Sentinel ({_sentinel_state['state']}, {_sentinel_state['assets_monitored']} pares)",
         lambda: True)

    total = len(ok_checks) + len(warnings) + len(errors)
    summary = (f"Self-Test VI completado: {len(ok_checks)} OK / "
               f"{len(warnings)} WARN / {len(errors)} ERROR (total={total})")
    return JSONResponse({
        "ok": len(errors) == 0,
        "summary": summary,
        "ok_checks": ok_checks,
        "warnings": warnings,
        "errors": errors,
    })


@app.post("/api/roadmap6/sentinel/scan")
def roadmap6_sentinel_scan() -> JSONResponse:
    """Fuerza un ciclo de escaneo del Market Sentinel ahora mismo."""
    try:
        threading.Thread(target=_run_sentinel_scans, daemon=True).start()
        return JSONResponse({"ok": True, "message": "Escaneo iniciado en background"})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/roadmap6/csvs_activos")
def roadmap6_csvs_activos() -> JSONResponse:
    """Lista el índice de CSVs activos (VI.3.C)."""
    try:
        result_str = dispatch_command("csvs activos")
        return JSONResponse({"ok": True, "text": str(result_str)})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# Monta la SPA al final para que /api/* tenga prioridad sobre el catch-all estático.

# ─── Command Palette endpoint (Ctrl+Shift+P) ────────────────────────────────

class _CommandBody(BaseModel):
    command: str

@app.post("/api/command")
def run_command(req: _CommandBody) -> JSONResponse:
    """Ejecuta un comando desde el Command Palette (Ctrl+Shift+P)."""
    try:
        cmd = req.command.strip()
        if not cmd:
            return JSONResponse({"ok": False, "error": "empty command"}, status_code=400)
        result = dispatch_command(cmd)
        status = _cli_result_status(result)
        status_code = 500 if status == "ERROR" else (503 if status == "UNAVAILABLE" else 200)
        return JSONResponse(
            {
                "ok": status == "SUCCESS",
                "status": status,
                "result": str(result),
                "module": "dispatcher",
            },
            status_code=status_code,
        )
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ═══════════════════════════════════════════════════════════════
# DEPLOYMENT REPORTS — First Deployment Experience API
# ═══════════════════════════════════════════════════════════════

@app.get("/api/deployment/summary")
async def deployment_summary():
    """Resumen de todos los informes de despliegue disponibles."""
    try:
        from deployment.report_manager import ReportManager
        mgr = ReportManager()
        return mgr.get_summary()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/deployment/reports")
async def deployment_reports_list(report_type: str = None):
    """Lista todos los informes, opcionalmente filtrados por tipo."""
    try:
        from deployment.report_manager import ReportManager
        mgr = ReportManager()
        reports = mgr.list_reports(report_type)
        return {"reports": reports, "total": len(reports)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/deployment/reports/{filename}")
async def deployment_report_content(filename: str):
    """Lee el contenido Markdown de un informe especifico."""
    try:
        from deployment.report_manager import ReportManager
        mgr = ReportManager()
        content = mgr.get_report_content(filename)
        if content is None:
            return JSONResponse({"error": "Report not found"}, status_code=404)
        return {"filename": filename, "content": content}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/deployment/latest/{report_type}")
async def deployment_latest(report_type: str):
    """Obtiene el informe mas reciente del tipo especificado."""
    try:
        from deployment.report_manager import ReportManager
        mgr = ReportManager()
        content = mgr.get_latest_content(report_type)
        latest_meta = mgr.get_latest(report_type)
        if content is None:
            return {"error": "No reports found for this type", "report_type": report_type}
        return {
            "report_type": report_type,
            "metadata": latest_meta,
            "content": content,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/deployment/run")
async def deployment_run(payload: dict = None):
    """Ejecuta el First Deployment Experience completo manualmente."""
    try:
        from deployment.first_run_validator import run_first_deployment_check
        symbols = None
        timeframe = "H4"
        if payload:
            symbols = payload.get("symbols")
            timeframe = payload.get("timeframe", "H4")
        result = run_first_deployment_check(
            symbols=symbols,
            timeframe=timeframe,
            force=True,
        )
        return result
    except Exception as e:
        import traceback; traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/deployment/run-readiness")
async def deployment_run_readiness():
    """Ejecuta solo el Production Readiness Report."""
    try:
        from deployment.production_readiness import run_production_readiness
        report = run_production_readiness()
        from deployment.report_manager import ReportManager
        mgr = ReportManager()
        path = mgr.save_report(
            report_type="readiness",
            content_md=report.to_markdown(),
            metadata={
                "global_status": report.global_status,
                "passed": report.passed,
                "failed": report.failed,
                "warned": report.warned,
                "summary": f"{report.global_status}: {report.passed} OK / {report.failed} FAIL / {report.warned} WARN",
            },
        )
        return {"status": report.global_status, "report_path": path, **report.to_dict()}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)



# ── ROBUSTNESS API ────────────────────────────────────────────────────
@app.get("/api/robustness/dependency-check")
async def robustness_dependency():
    """Validacion centralizada de dependencias."""
    try:
        from robustness.dependency_validator import run_dependency_validation
        return run_dependency_validation()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/robustness/data-integrity")
async def robustness_data():
    """Verifica integridad de datasets CSV."""
    try:
        from robustness.data_integrity_checker import run_data_integrity_check
        report = run_data_integrity_check("CSVs")
        return {
            "total_files": report.total_files,
            "ok_count": report.ok_count,
            "warning_count": report.warning_count,
            "error_count": report.error_count,
            "results": [
                {
                    "file": r.file, "pair": r.pair, "timeframe": r.timeframe,
                    "rows": r.rows, "status": r.status,
                    "issues": [{"type": i.issue_type, "severity": i.severity, "detail": i.detail, "recommendation": i.recommendation} for i in r.issues]
                } for r in report.results
            ]
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/robustness/model-integrity")
async def robustness_models():
    """Verifica integridad de modelos ML."""
    try:
        from robustness.model_integrity_checker import run_model_integrity_check
        report = run_model_integrity_check(auto_recover=False)
        return {
            "total_models": report.total_models,
            "ok_count": report.ok_count,
            "recovered_count": report.recovered_count,
            "blocked_count": report.blocked_count,
            "checks": [
                {
                    "symbol": c.symbol, "status": c.status,
                    "issues": c.issues, "recovery_action": c.recovery_action,
                    "recommendation": c.recommendation
                } for c in report.checks
            ]
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/robustness/provider")
async def robustness_provider():
    """Verifica el proveedor cloud."""
    try:
        from robustness.provider_verification import run_provider_verification
        report = run_provider_verification()
        return {
            "provider": report.provider_name,
            "status": report.status,
            "checks": [{"name": c.check_name, "status": c.status, "detail": c.detail, "recommendation": c.recommendation} for c in report.checks]
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/robustness/recovery-history")
async def robustness_recovery(limit: int = 20):
    """Historial de eventos de recuperacion."""
    try:
        from robustness.auto_recovery_history import get_recovery_history
        hist = get_recovery_history()
        events = hist.get_recent_events(limit)
        stats = hist.get_stats()
        return {
            "stats": stats,
            "events": [
                {
                    "id": e.id, "timestamp": e.timestamp, "component": e.component,
                    "incident_type": e.incident_type, "error_message": e.error_message,
                    "recovery_action": e.recovery_action, "downtime_seconds": e.downtime_seconds,
                    "recovery_status": e.recovery_status
                } for e in events
            ]
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/robustness/benchmark")
async def robustness_benchmark(limit: int = 50, pair: str = None, stage: str = None):
    """Estadisticas de benchmark del pipeline."""
    from robustness.pipeline_benchmark import get_benchmark_evidence

    evidence = get_benchmark_evidence(limit=limit, pair=pair, stage=stage)
    if evidence["status"] == "ERROR":
        return JSONResponse(evidence, status_code=500)
    payload = dict(evidence)
    payload["history"] = [
        {
            "stage": item["stage_name"],
            "duration": item["duration_seconds"],
            "pair": item.get("pair"),
            "timeframe": item.get("timeframe"),
            "timestamp": item["timestamp"],
        }
        for item in evidence["history"]
    ]
    return JSONResponse(payload)

@app.get("/api/robustness/all")
async def robustness_all():
    """Ejecuta todos los checks de robustez."""
    try:
        results = {}
        from robustness.dependency_validator import run_dependency_validation
        results["dependency"] = run_dependency_validation()
        from robustness.data_integrity_checker import run_data_integrity_check
        dr = run_data_integrity_check("CSVs")
        results["data_integrity"] = {"total": dr.total_files, "ok": dr.ok_count, "warn": dr.warning_count, "err": dr.error_count}
        from robustness.model_integrity_checker import run_model_integrity_check
        mr = run_model_integrity_check(auto_recover=False)
        results["model_integrity"] = {"total": mr.total_models, "ok": mr.ok_count, "blocked": mr.blocked_count}
        from robustness.provider_verification import run_provider_verification
        pv = run_provider_verification()
        results["provider"] = {"name": pv.provider_name, "status": pv.status}
        from robustness.auto_recovery_history import get_recovery_history
        results["recovery"] = get_recovery_history().get_stats()
        from robustness.pipeline_benchmark import get_benchmark_evidence
        results["benchmark"] = get_benchmark_evidence(limit=1)
        return results
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.api_route(
    "/api",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
@app.api_route(
    "/api/{unmatched_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
async def api_not_found(unmatched_path: str):
    """Keep unknown API requests inside the JSON backend boundary."""
    return JSONResponse({"error": "API endpoint not found"}, status_code=404)


# Static/HTML catch-all is deliberately registered after every backend route.
app.mount("/", StaticFiles(directory=_STATIC_ROOT, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("ASTRA_PORT", os.environ.get("PORT", 8000)))
    host = configured_bind_host("ASTRA_HOST")
    print(f"ASTRA Workspace disponible en http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

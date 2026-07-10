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

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
_CSV_BASE = os.path.join(_ROOT, "CSVs")
os.makedirs(_UPLOAD_DIR, exist_ok=True)

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


# ══════════════════════════════════════════════════════════════════
#  SECCIÓN 1 — Workspace Principal
# ══════════════════════════════════════════════════════════════════

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
    safe_name = os.path.basename(file.filename or "archivo")
    dest_path = os.path.join(_UPLOAD_DIR, safe_name)
    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)
    rel_path = os.path.relpath(dest_path, _ROOT)
    return JSONResponse({"filename": safe_name, "path": rel_path, "size": len(content)})


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
    tf_dir = os.path.join(_CSV_BASE, timeframe.upper())
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
    return JSONResponse({"timeframe": timeframe.upper(), "files": files})


_REQUIRED_OHLC = ["open", "high", "low", "close"]


@app.get("/api/forex/csv/info")
def csv_info(path: str) -> JSONResponse:
    full = os.path.normpath(os.path.join(_ROOT, path))
    if not full.startswith(_ROOT) or not os.path.isfile(full):
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
    full = os.path.normpath(os.path.join(_ROOT, path))
    if not full.startswith(_ROOT) or not os.path.isfile(full):
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
    pair_u = pair.upper()
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
    full = os.path.normpath(os.path.join(_ROOT, req.csv_path))
    if not full.startswith(_ROOT) or not os.path.isfile(full):
        return JSONResponse({"error": "CSV no encontrado."}, status_code=404)
    thread = threading.Thread(target=_run_training_job, args=(req.csv_path,), daemon=True)
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
    full = os.path.normpath(os.path.join(_ROOT, req.csv_path)) if not os.path.isabs(req.csv_path) else req.csv_path
    if not os.path.isfile(full):
        return JSONResponse({"error": "CSV no encontrado."}, status_code=404)
    if not req.idea or not req.idea.strip():
        return JSONResponse({"error": "Falta describir la idea/problema a resolver."}, status_code=400)
    thread = threading.Thread(target=_run_lab_job, args=(req.csv_path, req.idea, req.target_variable), daemon=True)
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
    full = os.path.normpath(os.path.join(_ROOT, path)) if not os.path.isabs(path) else path
    if not full.startswith(_ROOT) or not os.path.isfile(full):
        return None
    return full


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


# Monta la SPA al final para que /api/* tenga prioridad sobre el catch-all estático.
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    print("ASTRA Workspace disponible en http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)

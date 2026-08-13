"""
ASTRA Internal API Server
Servidor REST interno (http.server) para que el Workplace consulte predicciones,
rankings, estado del sistema y estadísticas.
Puerto: 8000 (por defecto; sobreescribible con ASTRA_API_PORT)
Desacoplado del backend Python del frontend Node.js.
"""
from __future__ import annotations
import json
import os
import sys
import time
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from runtime_security import (
    AuthResult,
    authenticate_headers,
    configured_bind_host,
    configured_cors_origins,
)

_BASE = Path(__file__).resolve().parent
_PORT = int(os.environ.get("ASTRA_API_PORT", "8000"))

# ── State helpers ─────────────────────────────────────────────────────────────

def _state_path() -> Path:
    return _BASE / "astra_state.json"


def _load_state() -> dict:
    try:
        p = _state_path()
        if p.exists():
            with open(p) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_state(data: dict):
    try:
        current = _load_state()
        current.update(data)
        current["ts"] = datetime.now().isoformat()
        with open(_state_path(), "w") as f:
            json.dump(current, f, indent=2)
    except Exception as _e:
        import logging as _l
        _l.getLogger("astra.api").debug("State write skipped: %s", _e)


# ── Route handlers ────────────────────────────────────────────────────────────

def _handle_status(_params: dict) -> dict:
    state = _load_state()
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        mem_used_pct = mem.percent
    except Exception:
        cpu = -1
        mem_used_pct = -1

    try:
        from forex.scheduler.autonomous_scheduler import get_scheduler
        sched = get_scheduler()
        scheduler_running = sched.is_running
        job_count = len(sched._jobs) if hasattr(sched, '_jobs') else 0
    except Exception:
        scheduler_running = False
        job_count = 0

    return {
        "ok": True,
        "ts": datetime.now().isoformat(),
        "version": "6.0.0",
        "scheduler_running": scheduler_running,
        "scheduler_jobs": job_count,
        "cpu_pct": cpu,
        "mem_pct": mem_used_pct,
        "last_update": state.get("last_update"),
        "active_pairs": state.get("active_pairs", []),
    }


def _handle_predictions(params: dict) -> dict:
    pair = (params.get("pair", [""])[0] or "").upper()
    limit = int(params.get("limit", [20])[0])
    try:
        import sqlite3
        db = _BASE / "memoria.db"
        if not db.exists():
            return {"ok": True, "predictions": [], "pair": pair}
        conn = sqlite3.connect(str(db))
        cursor = conn.cursor()
        if pair:
            rows = cursor.execute(
                "SELECT pair, timeframe, signal, confidence, ts FROM predictions WHERE pair=? ORDER BY ts DESC LIMIT ?",
                (pair, limit)
            ).fetchall()
        else:
            rows = cursor.execute(
                "SELECT pair, timeframe, signal, confidence, ts FROM predictions ORDER BY ts DESC LIMIT ?",
                (limit,)
            ).fetchall()
        conn.close()
        predictions = [
            {"pair": r[0], "tf": r[1], "signal": r[2], "confidence": r[3], "ts": r[4]}
            for r in rows
        ]
        return {"ok": True, "predictions": predictions, "pair": pair, "count": len(predictions)}
    except Exception as e:
        return {"ok": True, "predictions": [], "error": str(e)}


def _handle_ranking(params: dict) -> dict:
    try:
        from forex.portfolio.opportunity_score import get_ranker, SignalInput
        state = _load_state()
        signals_raw = state.get("live_signals", [])
        if not signals_raw:
            return {"ok": True, "top_buy": [], "top_sell": [], "count": 0,
                    "note": "Sin señales activas — inicia el scheduler"}
        signals = [
            SignalInput(
                pair=s["pair"],
                direction=s.get("direction", "BUY"),
                reliability_score=float(s.get("reliability_score", 0)),
                win_rate_pct=float(s.get("win_rate_pct", 0)),
                regime=s.get("regime", "unknown"),
                mtf_coherent=bool(s.get("mtf_coherent", False)),
                candlestick_confirm=bool(s.get("candlestick_confirm", False)),
                current_price=float(s.get("current_price", 0)),
            )
            for s in signals_raw
        ]
        ranker = get_ranker(top_n=int(params.get("top_n", [10])[0]))
        ranking = ranker.rank(signals)
        return {
            "ok": True,
            "top_buy":  [r.__dict__ for r in ranking.get("top_buy", [])],
            "top_sell": [r.__dict__ for r in ranking.get("top_sell", [])],
            "total_evaluated": ranking.get("total_evaluated", 0),
            "total_eligible":  ranking.get("total_eligible", 0),
            "ts": ranking.get("ts"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "top_buy": [], "top_sell": []}


def _handle_outcome_stats(params: dict) -> dict:
    pair = (params.get("pair", [""])[0] or "").upper()
    try:
        from forex.prediction.outcome_tracker import OutcomeTracker
        tracker = OutcomeTracker()
        stats = tracker.get_stats(pair=pair)
        return {"ok": True, "pair": pair or "all", "stats": stats.to_dict()}
    except Exception as e:
        return {"ok": True, "pair": pair, "stats": {}, "error": str(e)}


def _handle_history(params: dict) -> dict:
    pair = (params.get("pair", [""])[0] or "").upper()
    try:
        from forex.prediction.model_quality_history import get_quality_history
        qh = get_quality_history()
        history = qh.list_history(limit=int(params.get("limit", [20])[0]))
        return {"ok": True, "pair": pair, "history": history}
    except Exception as e:
        return {"ok": True, "history": [], "error": str(e)}


def _handle_datasets(params: dict) -> dict:
    try:
        from forex.data.csv_migrator import list_active_csvs
        csvs = list_active_csvs()
        return {"ok": True, "datasets": csvs, "count": len(csvs)}
    except Exception as e:
        return {"ok": True, "datasets": [], "error": str(e)}


def _handle_scheduler(params: dict) -> dict:
    try:
        from forex.scheduler.autonomous_scheduler import get_scheduler
        sched = get_scheduler()
        return {"ok": True, "running": sched.is_running, "status": sched.status()}
    except Exception as e:
        return {"ok": False, "running": False, "error": str(e)}


def _handle_doctor(_params: dict) -> dict:
    try:
        report_path = _BASE / "astra_doctor_report.json"
        if report_path.exists():
            age_s = time.time() - report_path.stat().st_mtime
            if age_s < 3600:
                with open(report_path) as f:
                    return {"ok": True, "from_cache": True, "report": json.load(f)}
        from astra_doctor import run_doctor
        report = run_doctor(verbose=False)
        return {"ok": True, "from_cache": False, "report": report}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _handle_root(_params: dict) -> dict:
    return {
        "ok": True,
        "name": "ASTRA API",
        "version": "6.1.1",
        "port": _PORT,
        "ts": datetime.now().isoformat(),
        "endpoints": [
            "/api/astra/health",
            "/api/astra/status",
            "/api/astra/predictions",
            "/api/astra/ranking",
            "/api/astra/outcomes",
            "/api/astra/history",
            "/api/astra/datasets",
            "/api/astra/scheduler",
            "/api/astra/doctor",
        ],
    }


_ROUTES: dict[str, callable] = {
    "/":                      _handle_root,
    "/api/astra/status":      _handle_status,
    "/api/astra/predictions": _handle_predictions,
    "/api/astra/ranking":     _handle_ranking,
    "/api/astra/outcomes":    _handle_outcome_stats,
    "/api/astra/history":     _handle_history,
    "/api/astra/datasets":    _handle_datasets,
    "/api/astra/scheduler":   _handle_scheduler,
    "/api/astra/doctor":      _handle_doctor,
    "/api/astra/health":      lambda p: {"ok": True},
}


# ── Root HTML dashboard (served to browsers at /) ─────────────────────────────

_ROOT_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>ASTRA API — v6.1.1</title>
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:'Courier New',monospace;background:#0d1117;color:#e6edf3;min-height:100vh;padding:40px 20px;display:flex;justify-content:center}
    .wrap{max-width:720px;width:100%}
    .logo{font-size:2.2rem;font-weight:700;color:#58a6ff;letter-spacing:5px}
    .sub{color:#8b949e;font-size:.8rem;margin-top:4px;margin-bottom:30px}
    .badge{display:inline-flex;align-items:center;gap:8px;background:#1c2a1c;border:1px solid #2ea043;border-radius:20px;padding:6px 16px;margin-bottom:30px}
    .dot{width:9px;height:9px;border-radius:50%;background:#3fb950;box-shadow:0 0 6px #3fb950;animation:pulse 2s infinite}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
    .badge-text{color:#3fb950;font-size:.85rem;font-weight:600}
    .section{margin-bottom:28px}
    .section-title{color:#8b949e;font-size:.68rem;letter-spacing:1.5px;text-transform:uppercase;border-bottom:1px solid #21262d;padding-bottom:6px;margin-bottom:12px}
    .ep-grid{display:grid;gap:6px}
    .ep{display:grid;grid-template-columns:1fr 1fr auto;align-items:center;background:#161b22;border:1px solid #21262d;border-radius:6px;padding:10px 14px;gap:12px;text-decoration:none;transition:border-color .15s}
    .ep:hover{border-color:#388bfd}
    .ep-path{color:#58a6ff;font-size:.85rem}
    .ep-desc{color:#8b949e;font-size:.8rem}
    .ep-badge{font-size:.7rem;padding:2px 8px;border-radius:10px;text-align:center}
    .get{background:#0d2f5a;color:#58a6ff;border:1px solid #1f6feb}
    .status-box{background:#161b22;border:1px solid #21262d;border-radius:6px;padding:14px 16px;font-size:.8rem}
    .status-row{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #21262d}
    .status-row:last-child{border-bottom:none}
    .skey{color:#8b949e}
    .sval{color:#e6edf3}
    .sval.ok{color:#3fb950}
    .footer{margin-top:28px;font-size:.7rem;color:#484f58;line-height:1.8}
    code{background:#21262d;padding:1px 6px;border-radius:4px;color:#e6edf3}
  </style>
</head>
<body>
<div class="wrap">
  <div class="logo">ASTRA</div>
  <div class="sub">Modular AI System &nbsp;&middot;&nbsp; v6.1.1 &nbsp;&middot;&nbsp; Python REST API &nbsp;&middot;&nbsp; puerto 8000</div>
  <div class="badge"><div class="dot"></div><span class="badge-text">API Online</span></div>

  <div class="section">
    <div class="section-title">Estado del sistema</div>
    <div class="status-box" id="sysbox">
      <div class="status-row"><span class="skey">Servidor</span><span class="sval ok">http://localhost:8000</span></div>
      <div class="status-row"><span class="skey">Version</span><span class="sval">6.1.1</span></div>
      <div class="status-row"><span class="skey">CPU</span><span class="sval" id="cpu">cargando...</span></div>
      <div class="status-row"><span class="skey">RAM</span><span class="sval" id="ram">cargando...</span></div>
      <div class="status-row"><span class="skey">Pares activos</span><span class="sval" id="pairs">cargando...</span></div>
      <div class="status-row"><span class="skey">Scheduler</span><span class="sval" id="sched">cargando...</span></div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">Endpoints disponibles</div>
    <div class="ep-grid">
      <a class="ep" href="/api/astra/health"><span class="ep-path">/api/astra/health</span><span class="ep-desc">Health check</span><span class="ep-badge get">GET</span></a>
      <a class="ep" href="/api/astra/status"><span class="ep-path">/api/astra/status</span><span class="ep-desc">CPU, RAM, scheduler, pares</span><span class="ep-badge get">GET</span></a>
      <a class="ep" href="/api/astra/predictions"><span class="ep-path">/api/astra/predictions</span><span class="ep-desc">Predicciones recientes</span><span class="ep-badge get">GET</span></a>
      <a class="ep" href="/api/astra/ranking"><span class="ep-path">/api/astra/ranking</span><span class="ep-desc">Top oportunidades Forex</span><span class="ep-badge get">GET</span></a>
      <a class="ep" href="/api/astra/outcomes"><span class="ep-path">/api/astra/outcomes</span><span class="ep-desc">Estadísticas de outcomes</span><span class="ep-badge get">GET</span></a>
      <a class="ep" href="/api/astra/datasets"><span class="ep-path">/api/astra/datasets</span><span class="ep-desc">Datasets activos</span><span class="ep-badge get">GET</span></a>
      <a class="ep" href="/api/astra/scheduler"><span class="ep-path">/api/astra/scheduler</span><span class="ep-desc">Estado del scheduler</span><span class="ep-badge get">GET</span></a>
      <a class="ep" href="/api/astra/doctor"><span class="ep-path">/api/astra/doctor</span><span class="ep-desc">Diagnóstico completo</span><span class="ep-badge get">GET</span></a>
    </div>
  </div>

  <div class="footer">
    Accede desde ASTRA CLI escribiendo <code>api start</code> &nbsp;&middot;&nbsp;
    Proxy Node.js disponible en <code>/api/astra/*</code><br/>
    Para Oracle Cloud ver <code>docs/ORACLE_CLOUD.md</code>
  </div>
</div>
<script>
  const apiKeyStorage = 'astra.internal.apiKey';
  let apiKey = sessionStorage.getItem(apiKeyStorage) || '';
  if (!apiKey) {
    apiKey = (window.prompt('ASTRA API key') || '').trim();
    if (apiKey) sessionStorage.setItem(apiKeyStorage, apiKey);
  }
  async function refreshStatus() {
    try {
      const r = await fetch('/api/astra/status', {
        headers: apiKey ? {Authorization: `Bearer ${apiKey}`} : {}
      });
      const d = await r.json();
      if (d.ok !== false) {
        document.getElementById('cpu').textContent  = d.cpu_percent != null ? d.cpu_percent + '%' : '—';
        document.getElementById('ram').textContent  = d.ram_percent != null ? d.ram_percent + '%' : '—';
        document.getElementById('pairs').textContent = Array.isArray(d.active_pairs) ? d.active_pairs.length : (d.active_pairs ?? '—');
        document.getElementById('sched').textContent = d.scheduler_running ? 'Activo' : 'Inactivo';
      }
    } catch(e) { /* silencioso */ }
  }
  refreshStatus();
  setInterval(refreshStatus, 10000);
</script>
</body>
</html>"""


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class AstraAPIHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # silenciar logs de acceso

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_origin()
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_origin()
        self.end_headers()
        self.wfile.write(body)

    def _wants_html(self) -> bool:
        accept = self.headers.get("Accept", "")
        return "text/html" in accept

    def _send_cors_origin(self) -> None:
        origin = (self.headers.get("Origin") or "").rstrip("/")
        if origin and origin in configured_cors_origins():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _authorized(self, path: str) -> bool:
        if path == "/api/astra/health":
            return True
        auth = authenticate_headers(self.headers)
        if auth is AuthResult.OK:
            return True
        if auth is AuthResult.NOT_CONFIGURED:
            self._send_json({"ok": False, "error": "API authentication is not configured"}, 503)
        else:
            self._send_json({"ok": False, "error": "Invalid or missing API credentials"}, 401)
        return False

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_origin()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-API-Key")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        path   = parsed.path

        if (path == "/api" or path.startswith("/api/")) and not self._authorized(path):
            return

        # Root path: serve HTML dashboard for browsers, JSON for API clients
        if path == "/" and self._wants_html():
            self._send_html(_ROOT_HTML)
            return

        handler = _ROUTES.get(path)
        if handler:
            try:
                result = handler(params)
                self._send_json(result)
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
        else:
            self._send_json({"ok": False, "error": f"Unknown endpoint: {path}"}, 404)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except Exception:
            body = {}

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        path   = parsed.path

        if (path == "/api" or path.startswith("/api/")) and not self._authorized(path):
            return

        if path == "/api/astra/signal":
            _save_state({"live_signals": body.get("signals", [])})
            self._send_json({"ok": True})
        elif path == "/api/astra/state":
            _save_state(body)
            self._send_json({"ok": True})
        else:
            handler = _ROUTES.get(path)
            if handler:
                self._send_json(handler(params))
            else:
                self._send_json({"ok": False, "error": f"Unknown: {path}"}, 404)


# ── Server lifecycle ──────────────────────────────────────────────────────────

_server_instance: HTTPServer | None = None
_server_thread:   threading.Thread | None = None


def start_api_server(port: int = _PORT, daemon: bool = True, host: str | None = None) -> bool:
    global _server_instance, _server_thread
    if _server_instance is not None:
        return False
    try:
        bind_host = host if host is not None else configured_bind_host("ASTRA_API_HOST")
        _server_instance = HTTPServer((bind_host, port), AstraAPIHandler)
        _server_thread = threading.Thread(
            target=_server_instance.serve_forever,
            name="AstraAPIServer",
            daemon=daemon,
        )
        _server_thread.start()
        return True
    except Exception as e:
        print(f"[AstraAPI] Error iniciando servidor: {e}")
        _server_instance = None
        return False


def stop_api_server():
    global _server_instance, _server_thread
    if _server_instance:
        _server_instance.shutdown()
        _server_instance = None
        _server_thread = None


def is_api_running() -> bool:
    return _server_instance is not None


def api_status() -> str:
    if is_api_running():
        return f"✅ ASTRA API corriendo en http://localhost:{_PORT}"
    return "🔴 ASTRA API detenida"


if __name__ == "__main__":
    print(f"[AstraAPI] Iniciando servidor en puerto {_PORT}...")
    start_api_server(port=_PORT, daemon=False)

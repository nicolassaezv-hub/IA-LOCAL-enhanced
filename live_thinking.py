"""
ASTRA Workspace — Live Thinking (Roadmap IV, Sección 11)
==================================================================
Razonamiento operativo VISIBLE — que el usuario nunca perciba que ASTRA
solo "está pensando" sin mostrar qué hace. Primitiva TRANSVERSAL (no
exclusiva de un Lab): cualquier tarea larga y multi-etapa publica su
progreso paso a paso aquí, y cualquier panel puede consultarlo.

Estado en memoria (no persistido — es "qué está pasando ahora", no
historial; para eso ya existen Activity Center y Notification Center).
Modelo singleton por `task_key` (un job activo a la vez por tarea, mismo
patrón que `_lab_state` / `_train_state` de workspace/server.py).

API pública:
  start_thinking(task_key, step_labels, task_label="") -> dict
  set_step(task_key, step_index, status, detail="")     -> dict
  finish_thinking(task_key, ok, error=None)              -> dict
  get_thinking(task_key)                                  -> dict | None
  get_all_thinking()                                       -> dict[str, dict]

Estados de paso: "pending" | "running" | "done" | "error" | "skipped".
"""
from __future__ import annotations

import time
import threading
from typing import Optional, List, Dict, Any

_lock = threading.Lock()
_SESSIONS: Dict[str, Dict[str, Any]] = {}


def start_thinking(task_key: str, step_labels: List[str], task_label: str = "") -> Dict[str, Any]:
    """Inicia (o reinicia) una sesión de pensamiento visible para task_key.
    Todos los pasos arrancan en 'pending'."""
    with _lock:
        session = {
            "task_key": task_key,
            "task_label": task_label or task_key,
            "steps": [
                {"index": i, "label": lbl, "status": "pending", "detail": "", "started_at": None, "finished_at": None}
                for i, lbl in enumerate(step_labels)
            ],
            "active": True,
            "ok": None,
            "error": None,
            "started_at": time.time(),
            "finished_at": None,
        }
        _SESSIONS[task_key] = session
        return dict(session)


def set_step(task_key: str, step_index: int, status: str, detail: str = "") -> Optional[Dict[str, Any]]:
    """Actualiza el estado de un paso puntual. Graceful: si task_key o el
    índice no existen (p.ej. progress_cb llamado antes de start_thinking,
    o un caller desincronizado), no rompe nada — solo no hace nada."""
    with _lock:
        session = _SESSIONS.get(task_key)
        if not session:
            return None
        if step_index < 0 or step_index >= len(session["steps"]):
            return None
        step = session["steps"][step_index]
        step["status"] = status
        if detail:
            step["detail"] = detail
        now = time.time()
        if status == "running" and step["started_at"] is None:
            step["started_at"] = now
        if status in ("done", "error", "skipped"):
            step["finished_at"] = now
        return dict(session)


def finish_thinking(task_key: str, ok: bool, error: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Cierra la sesión. Cualquier paso que haya quedado 'running' se marca
    'done' (si ok) o 'error' (si no) — evita que un paso quede "pensando"
    para siempre en la UI si el job terminó sin marcar explícitamente su
    último paso."""
    with _lock:
        session = _SESSIONS.get(task_key)
        if not session:
            return None
        for step in session["steps"]:
            if step["status"] == "running":
                step["status"] = "done" if ok else "error"
                step["finished_at"] = time.time()
        session["active"] = False
        session["ok"] = ok
        session["error"] = error
        session["finished_at"] = time.time()
        return dict(session)


def get_thinking(task_key: str) -> Optional[Dict[str, Any]]:
    with _lock:
        session = _SESSIONS.get(task_key)
        return dict(session) if session else None


def get_all_thinking() -> Dict[str, Dict[str, Any]]:
    with _lock:
        return {k: dict(v) for k, v in _SESSIONS.items()}

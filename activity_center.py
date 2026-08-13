"""
ASTRA Workspace — Activity Center (Roadmap IV, Sección 9)
===========================================================
"Qué está pasando ahora mismo en ASTRA" — feed unificado y en vivo que
fusiona 4 fuentes reales:

  1. Alertas del Workspace (`push_alert()` — antes vivían como estado
     global dentro de workspace/server.py, movidas aquí para que el
     Activity Center sea standalone e importable sin levantar el server,
     mismo patrón que cognitive_center.py / evolution_center.py).
  2. Comandos ejecutados (memory.py, tabla `command_log`).
  3. Señales Forex generadas (signal_tracker.py, tabla `forex_signals`).
  4. Eventos de evolución (feedback/evolution_memory.py, tabla
     `evolution_events`).

Todo real, sin datos simulados. Graceful-fail en cada función pública:
si una fuente falla o no existe todavía, se omite en el feed en vez de
romper el resto.

API pública:
  push_alert(kind, message)         -> dict (registra una alerta nueva)
  get_alerts(limit, kind)           -> list[dict]
  get_activity_feed(limit, sources) -> dict (feed fusionado, más reciente
                                        primero, con conteos por fuente)
  get_activity_stats()              -> dict (resumen para tiles del panel)
"""
from __future__ import annotations

import os
import threading
import datetime
from datetime import datetime as _dt
from typing import Optional, List, Dict, Any

from runtime_paths import configured_project_path

DB_PATH = str(configured_project_path("ASTRA_MEMORY_DB_PATH", "memoria.db"))

_VALID_KINDS = ("info", "success", "warning", "error")

# ══════════════════════════════════════════════════════════════════
# Timestamps mixtos (ctime / isoformato) — mismo patrón que
# cognitive_center.py / evolution_center.py.
# ══════════════════════════════════════════════════════════════════
_TS_FORMATS = ("%a %b %d %H:%M:%S %Y", "%Y-%m-%d %H:%M:%S")


def _parse_ts(ts: Optional[str]) -> Optional[_dt]:
    if not ts:
        return None
    ts = str(ts).strip()
    for fmt in _TS_FORMATS:
        try:
            return _dt.strptime(ts, fmt)
        except ValueError:
            continue
    try:
        return _dt.fromisoformat(ts)
    except Exception:
        return None


def _sort_key(ts: Optional[str]) -> _dt:
    return _parse_ts(ts) or _dt.min


# ══════════════════════════════════════════════════════════════════
# 1 — Alertas del Workspace (en memoria, proceso local)
# ══════════════════════════════════════════════════════════════════
_alerts_lock = threading.Lock()
_alerts: List[Dict[str, Any]] = []
_alert_id_counter = 0
_MAX_ALERTS = 200


def push_alert(kind: str, message: str) -> Dict[str, Any]:
    """Registra una alerta nueva. kind: info | success | warning | error."""
    global _alert_id_counter
    if kind not in _VALID_KINDS:
        kind = "info"
    with _alerts_lock:
        _alert_id_counter += 1
        entry = {
            "id": _alert_id_counter,
            "kind": kind,
            "message": str(message),
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        _alerts.insert(0, entry)
        if len(_alerts) > _MAX_ALERTS:
            _alerts.pop()
        return entry


def get_alerts(limit: int = 20, kind: Optional[str] = None) -> List[Dict[str, Any]]:
    with _alerts_lock:
        items = list(_alerts)
    if kind:
        items = [a for a in items if a["kind"] == kind]
    return items[:limit]


# ══════════════════════════════════════════════════════════════════
# 2 — Comandos ejecutados (memory.py / command_log)
# ══════════════════════════════════════════════════════════════════

def get_recent_commands(limit: int = 30) -> List[Dict[str, Any]]:
    try:
        from memory import get_command_log
        return get_command_log(limit=limit)
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════
# 3 — Señales Forex (signal_tracker.py / forex_signals)
# ══════════════════════════════════════════════════════════════════

def get_recent_signals(limit: int = 30) -> List[Dict[str, Any]]:
    try:
        from signal_tracker import get_signals
        return get_signals(pair=None, limit=limit)
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════
# 4 — Eventos de evolución (feedback/evolution_memory.py)
# ══════════════════════════════════════════════════════════════════

def get_recent_evolution_events(limit: int = 30) -> List[Dict[str, Any]]:
    try:
        from feedback.evolution_memory import get_evolution_history
        events = get_evolution_history(limit=limit)
        return [
            {
                "event_type": e.event_type, "component": e.component,
                "description": e.description, "data": e.data,
                "timestamp": e.timestamp,
            }
            for e in events
        ]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════
# Feed fusionado
# ══════════════════════════════════════════════════════════════════
_SOURCE_KINDS = {
    "alert": {"info": "info", "success": "success", "warning": "warning", "error": "error"},
}


def _alert_to_item(a: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": "alert", "kind": a["kind"],
        "title": a["message"], "detail": "",
        "timestamp": a["timestamp"],
    }


def _command_to_item(c: Dict[str, Any]) -> Dict[str, Any]:
    pair_tag = f" [{c['pair']}]" if c.get("pair") else ""
    return {
        "source": "command", "kind": "info",
        "title": f"{c.get('command', '')}{pair_tag}",
        "detail": c.get("summary", ""),
        "timestamp": c.get("executed_at", ""),
    }


def _signal_to_item(s: Dict[str, Any]) -> Dict[str, Any]:
    action = str(s.get("action", "")).upper()
    kind = "success" if action == "BUY" else "warning" if action == "SELL" else "info"
    conf = s.get("confidence")
    conf_txt = f", confianza={conf:.2f}" if isinstance(conf, (int, float)) else ""
    return {
        "source": "signal", "kind": kind,
        "title": f"Señal {action} — {s.get('pair', '?')}",
        "detail": f"ADX={s.get('adx')}{conf_txt} · régimen={s.get('regime') or 'n/d'}"
                  + (f" · {s.get('hold_reason')}" if s.get("hold_reason") else ""),
        "timestamp": s.get("generated_at", ""),
    }


def _evolution_to_item(e: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": "evolution", "kind": "info",
        "title": f"{e.get('event_type', '')} — {e.get('component', '')}",
        "detail": e.get("description", ""),
        "timestamp": e.get("timestamp", ""),
    }


_ALL_SOURCES = ("alert", "command", "signal", "evolution")


def get_activity_feed(limit: int = 50, sources: Optional[List[str]] = None) -> Dict[str, Any]:
    """Feed unificado, más reciente primero. `sources` filtra por
    alert/command/signal/evolution (None = todas)."""
    wanted = set(sources) if sources else set(_ALL_SOURCES)
    items: List[Dict[str, Any]] = []

    if "alert" in wanted:
        items += [_alert_to_item(a) for a in get_alerts(limit=limit)]
    if "command" in wanted:
        items += [_command_to_item(c) for c in get_recent_commands(limit=limit)]
    if "signal" in wanted:
        items += [_signal_to_item(s) for s in get_recent_signals(limit=limit)]
    if "evolution" in wanted:
        items += [_evolution_to_item(e) for e in get_recent_evolution_events(limit=limit)]

    items.sort(key=lambda it: _sort_key(it["timestamp"]), reverse=True)
    items = items[:limit]

    by_source: Dict[str, int] = {}
    for it in items:
        by_source[it["source"]] = by_source.get(it["source"], 0) + 1

    return {"ok": True, "items": items, "total": len(items), "by_source": by_source}


def get_activity_stats() -> Dict[str, Any]:
    """Resumen para las tarjetas del panel: conteos totales por fuente
    (sin límite artificial de la vista fusionada) + alertas por severidad."""
    try:
        alerts = get_alerts(limit=_MAX_ALERTS)
        commands = get_recent_commands(limit=200)
        signals = get_recent_signals(limit=200)
        events = get_recent_evolution_events(limit=200)

        alerts_by_kind: Dict[str, int] = {}
        for a in alerts:
            alerts_by_kind[a["kind"]] = alerts_by_kind.get(a["kind"], 0) + 1

        signals_by_action: Dict[str, int] = {}
        for s in signals:
            act = str(s.get("action", "?")).upper()
            signals_by_action[act] = signals_by_action.get(act, 0) + 1

        return {
            "ok": True,
            "alerts_total": len(alerts), "alerts_by_kind": alerts_by_kind,
            "commands_total": len(commands),
            "signals_total": len(signals), "signals_by_action": signals_by_action,
            "evolution_events_total": len(events),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

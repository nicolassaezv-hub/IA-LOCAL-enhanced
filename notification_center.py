"""
ASTRA Workspace — Notification Center (Roadmap IV, Sección 10)
==================================================================
Sistema centralizado de notificaciones PERSISTIDAS y consultables —
distinto del Activity Center (Sección 9), que es un feed en vivo/efímero.
Aquí lo que importa es: "¿qué pasó mientras no estaba mirando?" —
predicciones listas, entrenamientos completados, problemas detectados,
actualizaciones. Sobreviven a un reinicio del server (tabla SQLite real
en memoria.db, no estado en memoria como las alertas de Activity Center).

Tipos soportados (`NOTIFICATION_TYPES`):
  training_completed   — un entrenamiento Forex terminó (con o sin éxito)
  prediction_ready      — un reporte de Prediction Lab quedó listo
  problem_detected       — algo requiere atención (viabilidad insuficiente,
                            error de pipeline, circuit breaker abierto, etc.)
  business_analysis_ready — un análisis de Business Lab quedó listo
  system_update          — actualizaciones del propio sistema (reservado)

API pública:
  push_notification(ntype, title, message, data=None) -> dict
  get_notifications(limit, unread_only, ntype)         -> list[dict]
  mark_read(notification_id)                           -> bool
  mark_all_read()                                       -> int
  get_notification_stats()                              -> dict
"""
from __future__ import annotations

import os
import json
import sqlite3
import datetime
from typing import Optional, List, Dict, Any

from runtime_paths import configured_project_path

DB_PATH = str(configured_project_path("ASTRA_MEMORY_DB_PATH", "memoria.db"))

NOTIFICATION_TYPES = (
    "training_completed",
    "prediction_ready",
    "problem_detected",
    "business_analysis_ready",
    "system_update",
)


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_notifications_db() -> None:
    """Crea la tabla si no existe. Graceful — se puede llamar tantas veces
    como se quiera, idempotente."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ntype TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT DEFAULT '',
            data TEXT DEFAULT '{}',
            is_read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def push_notification(
    ntype: str, title: str, message: str = "", data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Persiste una notificación nueva. ntype fuera de NOTIFICATION_TYPES
    se acepta igual (graceful) pero se normaliza a 'system_update' para no
    perder el evento por un typo del caller."""
    if ntype not in NOTIFICATION_TYPES:
        ntype = "system_update"
    try:
        init_notifications_db()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        created_at = _now()
        data_json = json.dumps(data or {}, ensure_ascii=False)
        c.execute(
            "INSERT INTO notifications (ntype, title, message, data, is_read, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (ntype, str(title), str(message), data_json, created_at),
        )
        new_id = c.lastrowid
        conn.commit()
        conn.close()
        return {
            "ok": True, "id": new_id, "ntype": ntype, "title": title,
            "message": message, "data": data or {}, "is_read": False,
            "created_at": created_at,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_notifications(
    limit: int = 30, unread_only: bool = False, ntype: Optional[str] = None
) -> List[Dict[str, Any]]:
    try:
        init_notifications_db()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        conditions, params = [], []
        if unread_only:
            conditions.append("is_read = 0")
        if ntype:
            conditions.append("ntype = ?")
            params.append(ntype)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)
        c.execute(
            f"SELECT id, ntype, title, message, data, is_read, created_at "
            f"FROM notifications {where} ORDER BY id DESC LIMIT ?",
            params,
        )
        rows = c.fetchall()
        conn.close()
        result = []
        for r in rows:
            try:
                data = json.loads(r[4]) if r[4] else {}
            except Exception:
                data = {}
            result.append({
                "id": r[0], "ntype": r[1], "title": r[2], "message": r[3],
                "data": data, "is_read": bool(r[5]), "created_at": r[6],
            })
        return result
    except Exception:
        return []


def mark_read(notification_id: int) -> bool:
    try:
        init_notifications_db()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
        changed = c.rowcount > 0
        conn.commit()
        conn.close()
        return changed
    except Exception:
        return False


def mark_all_read() -> int:
    try:
        init_notifications_db()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE notifications SET is_read = 1 WHERE is_read = 0")
        changed = c.rowcount
        conn.commit()
        conn.close()
        return changed
    except Exception:
        return 0


def get_notification_stats() -> Dict[str, Any]:
    try:
        init_notifications_db()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM notifications")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM notifications WHERE is_read = 0")
        unread = c.fetchone()[0]
        c.execute("SELECT ntype, COUNT(*) FROM notifications WHERE is_read = 0 GROUP BY ntype")
        by_type = {row[0]: row[1] for row in c.fetchall()}
        conn.close()
        return {"ok": True, "total": total, "unread": unread, "unread_by_type": by_type}
    except Exception as e:
        return {"ok": False, "error": str(e)}

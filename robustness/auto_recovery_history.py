"""
robustness/auto_recovery_history.py — ASTRA Robustness Module
Records and tracks automatic recovery events in a persistent SQLite database.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Union


@dataclass
class RecoveryEvent:
    id: Optional[int] = None
    timestamp: str = ""
    component: str = ""
    incident_type: str = ""
    error_message: Optional[str] = None
    recovery_action: Optional[str] = None
    downtime_seconds: float = 0.0
    recovery_status: str = "unknown"
    context: Optional[str] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class AutoRecoveryHistory:
    def __init__(self, db_path: str = "memory_db/recovery_history.db"):
        self.db_path = db_path
        self._ensure_dir()
        self._init_db()

    def _ensure_dir(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recovery_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    component TEXT NOT NULL,
                    incident_type TEXT NOT NULL,
                    error_message TEXT,
                    recovery_action TEXT,
                    downtime_seconds REAL DEFAULT 0,
                    recovery_status TEXT DEFAULT 'unknown',
                    context TEXT
                )
                """
            )
            conn.commit()

    def record_event(
        self,
        component: str,
        incident_type: str,
        error_message: Optional[str],
        recovery_action: Optional[str],
        downtime_seconds: float,
        recovery_status: str,
        context: Optional[Union[str, dict, Any]] = None,
    ) -> int:
        timestamp = datetime.now().isoformat()
        if context is not None and not isinstance(context, str):
            try:
                context_str = json.dumps(context, ensure_ascii=False)
            except Exception:
                context_str = str(context)
        else:
            context_str = context

        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO recovery_events (
                    timestamp, component, incident_type, error_message,
                    recovery_action, downtime_seconds, recovery_status, context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    component,
                    incident_type,
                    error_message,
                    recovery_action,
                    float(downtime_seconds or 0.0),
                    recovery_status,
                    context_str,
                ),
            )
            conn.commit()
            return cur.lastrowid

    def get_recent_events(self, limit: int = 20) -> List[RecoveryEvent]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT id, timestamp, component, incident_type, error_message,
                       recovery_action, downtime_seconds, recovery_status, context
                FROM recovery_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cur.fetchall()

        events = []
        for r in rows:
            events.append(
                RecoveryEvent(
                    id=r[0],
                    timestamp=r[1],
                    component=r[2],
                    incident_type=r[3],
                    error_message=r[4],
                    recovery_action=r[5],
                    downtime_seconds=float(r[6] or 0.0),
                    recovery_status=r[7],
                    context=r[8],
                )
            )
        return events

    def get_events_by_component(
        self, component: str, limit: int = 50
    ) -> List[RecoveryEvent]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT id, timestamp, component, incident_type, error_message,
                       recovery_action, downtime_seconds, recovery_status, context
                FROM recovery_events
                WHERE component = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (component, limit),
            )
            rows = cur.fetchall()

        events = []
        for r in rows:
            events.append(
                RecoveryEvent(
                    id=r[0],
                    timestamp=r[1],
                    component=r[2],
                    incident_type=r[3],
                    error_message=r[4],
                    recovery_action=r[5],
                    downtime_seconds=float(r[6] or 0.0),
                    recovery_status=r[7],
                    context=r[8],
                )
            )
        return events

    def get_stats(self) -> Dict[str, Any]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT COUNT(*), COALESCE(AVG(downtime_seconds), 0.0) FROM recovery_events"
            )
            row = cur.fetchone()
            total_events = row[0] if row else 0
            avg_downtime = float(row[1]) if row and row[1] is not None else 0.0

            cur = conn.execute(
                "SELECT component, COUNT(*) FROM recovery_events GROUP BY component"
            )
            by_component = {r[0]: r[1] for r in cur.fetchall()}

            cur = conn.execute(
                "SELECT recovery_status, COUNT(*) FROM recovery_events GROUP BY recovery_status"
            )
            by_status = {r[0]: r[1] for r in cur.fetchall()}

        return {
            "total_events": total_events,
            "by_component": by_component,
            "by_status": by_status,
            "avg_downtime": avg_downtime,
            "avg_downtime_seconds": avg_downtime,
        }

    def to_markdown(self, limit: int = 20) -> str:
        events = self.get_recent_events(limit=limit)
        stats = self.get_stats()

        lines = [
            "# Auto Recovery History Report",
            "",
            "## Summary",
            f"- **Total Events**: {stats['total_events']}",
            f"- **Average Downtime**: {stats['avg_downtime']:.2f} seconds",
            "",
            "### Events by Component",
        ]

        if stats["by_component"]:
            for comp, count in sorted(stats["by_component"].items()):
                lines.append(f"- **{comp}**: {count}")
        else:
            lines.append("- None")

        lines.extend(["", "### Events by Status"])
        if stats["by_status"]:
            for status, count in sorted(stats["by_status"].items()):
                lines.append(f"- **{status}**: {count}")
        else:
            lines.append("- None")

        lines.extend(["", f"## Recent Recovery Events (Max {limit})", ""])

        if not events:
            lines.append("No recovery events recorded.")
        else:
            lines.append(
                "| ID | Timestamp | Component | Incident Type | Action | Status | Downtime (s) | Error |"
            )
            lines.append(
                "|---|---|---|---|---|---|---|---|"
            )
            for e in events:
                err_msg = (e.error_message or "").replace("\n", " ")
                if len(err_msg) > 30:
                    err_msg = err_msg[:27] + "..."
                action_str = (e.recovery_action or "").replace("\n", " ")
                if len(action_str) > 30:
                    action_str = action_str[:27] + "..."

                ts = e.timestamp[:19].replace("T", " ") if e.timestamp else ""
                lines.append(
                    f"| {e.id} | {ts} | {e.component} | {e.incident_type} | {action_str} | {e.recovery_status} | {e.downtime_seconds:.2f} | {err_msg} |"
                )

        return "\n".join(lines)


_history_instance: Optional[AutoRecoveryHistory] = None


def get_recovery_history(
    db_path: str = "memory_db/recovery_history.db",
) -> AutoRecoveryHistory:
    global _history_instance
    if _history_instance is None:
        _history_instance = AutoRecoveryHistory(db_path=db_path)
    return _history_instance

"""
feedback/evolution_memory.py — ASTRA Phase 6.6
Persiste eventos de evolución del sistema en SQLite.
"""
from __future__ import annotations
import json, sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

# BUGFIX: ruta relativa a cwd causaba que este módulo escribiera en un
# memoria.db distinto al usado por memory.py si el proceso corría desde
# otro directorio (ej. cron, .bat launcher). Se importa la MISMA ruta
# absoluta que usa memory.py — fuente única de verdad para la DB.
from memory import DB_PATH as _DB_PATH

@dataclass
class EvolutionEvent:
    event_type: str
    component: str
    description: str
    data: Dict[str, Any]
    timestamp: str = ""
    event_id: Optional[int] = None
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

class EvolutionMemory:
    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path
        self._init_db()
    def _conn(self): return sqlite3.connect(self.db_path)
    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS evolution_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
                component TEXT NOT NULL, description TEXT NOT NULL,
                data TEXT, timestamp TEXT NOT NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ev_type ON evolution_events(event_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ev_ts ON evolution_events(timestamp)")
            conn.commit()
    def log(self, event: EvolutionEvent) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO evolution_events (event_type, component, description, data, timestamp) VALUES (?,?,?,?,?)",
                (event.event_type, event.component, event.description, json.dumps(event.data, ensure_ascii=False), event.timestamp))
            conn.commit()
            return cur.lastrowid
    def get_recent(self, limit: int = 20, event_type: Optional[str] = None) -> List[EvolutionEvent]:
        with self._conn() as conn:
            if event_type:
                rows = conn.execute("SELECT id,event_type,component,description,data,timestamp FROM evolution_events WHERE event_type=? ORDER BY id DESC LIMIT ?", (event_type, limit)).fetchall()
            else:
                rows = conn.execute("SELECT id,event_type,component,description,data,timestamp FROM evolution_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [EvolutionEvent(event_type=r[1],component=r[2],description=r[3],data=json.loads(r[4] or "{}"),timestamp=r[5],event_id=r[0]) for r in rows]
    def count(self, event_type: Optional[str] = None) -> int:
        with self._conn() as conn:
            if event_type: return conn.execute("SELECT COUNT(*) FROM evolution_events WHERE event_type=?", (event_type,)).fetchone()[0]
            return conn.execute("SELECT COUNT(*) FROM evolution_events").fetchone()[0]
    def stats(self) -> Dict[str, Any]:
        with self._conn() as conn:
            rows = conn.execute("SELECT event_type, COUNT(*) FROM evolution_events GROUP BY event_type").fetchall()
        return {r[0]: r[1] for r in rows}
    def summary_text(self) -> str:
        stats = self.stats()
        total = sum(stats.values())
        if total == 0: return "Sin eventos de evolución registrados."
        lines = [f"Total eventos: {total}"]
        for etype, count in sorted(stats.items(), key=lambda x: -x[1]):
            lines.append(f"  {etype:30s}: {count}")
        return "\n".join(lines)

_memory = EvolutionMemory()

def log_evolution(event_type: str, component: str, description: str, data: Optional[Dict] = None) -> int:
    return _memory.log(EvolutionEvent(event_type=event_type, component=component, description=description, data=data or {}))

def get_evolution_history(limit: int = 20, event_type: Optional[str] = None) -> List[EvolutionEvent]:
    return _memory.get_recent(limit, event_type)

def cmd_evolution_history(limit: int = 10) -> str:
    events = _memory.get_recent(limit)
    if not events: return "Sin eventos de evolución registrados."
    lines = [f"{'═'*60}", "  ASTRA — Historial de Evolución", f"{'═'*60}"]
    for ev in events:
        lines.append(f"[{ev.timestamp[:19]}] [{ev.event_type}] {ev.component}: {ev.description}")
    lines.append(f"{'═'*60}")
    return "\n".join(lines)

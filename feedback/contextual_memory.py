"""
feedback/contextual_memory.py — ASTRA Phase 6.4
Persiste hallazgos contextuales sobre condiciones de mercado.
"""
from __future__ import annotations
import json, sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from .evolution_memory import log_evolution

# BUGFIX: ruta relativa a cwd causaba que este módulo escribiera en un
# memoria.db distinto al usado por memory.py si el proceso corría desde
# otro directorio (ej. cron, .bat launcher). Se importa la MISMA ruta
# absoluta que usa memory.py — fuente única de verdad para la DB.
from memory import DB_PATH as _DB_PATH

@dataclass
class MemoryEntry:
    context_key: str; outcome: str; features: Dict[str, Any]; score: float
    timestamp: str = ""; entry_id: Optional[int] = None
    def __post_init__(self):
        if not self.timestamp: self.timestamp = datetime.now().isoformat()

class ContextualMemory:
    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path; self._init_db()
    def _conn(self): return sqlite3.connect(self.db_path)
    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS contextual_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT, context_key TEXT NOT NULL,
                outcome TEXT NOT NULL, features TEXT, score REAL, timestamp TEXT NOT NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ctx_key ON contextual_memory(context_key)")
            conn.commit()
    def save(self, entry: MemoryEntry) -> int:
        with self._conn() as conn:
            cur = conn.execute("INSERT INTO contextual_memory (context_key,outcome,features,score,timestamp) VALUES (?,?,?,?,?)",
                (entry.context_key, entry.outcome, json.dumps(entry.features, ensure_ascii=False), entry.score, entry.timestamp))
            conn.commit()
            eid = cur.lastrowid
        log_evolution("context_saved","ContextualMemory",f"Saved {entry.outcome} for context '{entry.context_key}'",{"context_key": entry.context_key,"outcome": entry.outcome})
        return eid
    def get_for_key(self, context_key: str, limit: int = 50) -> List[MemoryEntry]:
        with self._conn() as conn:
            rows = conn.execute("SELECT id,context_key,outcome,features,score,timestamp FROM contextual_memory WHERE context_key=? ORDER BY id DESC LIMIT ?", (context_key, limit)).fetchall()
        return [MemoryEntry(entry_id=r[0],context_key=r[1],outcome=r[2],features=json.loads(r[3] or "{}"),score=r[4] or 0.0,timestamp=r[5]) for r in rows]
    def success_rate(self, context_key: str) -> float:
        entries = self.get_for_key(context_key)
        if not entries: return 0.5
        return sum(1 for e in entries if e.outcome == "correct") / len(entries)
    def top_contexts(self, n: int = 10) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("""SELECT context_key, COUNT(*) as total,
                SUM(CASE WHEN outcome='correct' THEN 1 ELSE 0 END) as correct
                FROM contextual_memory GROUP BY context_key ORDER BY total DESC LIMIT ?""", (n,)).fetchall()
        return sorted([{"context_key":r[0],"total":r[1],"correct":r[2],"success_rate":round(r[2]/max(1,r[1]),3)} for r in rows], key=lambda x: -x["success_rate"])
    def summary_text(self) -> str:
        tops = self.top_contexts(10)
        if not tops: return "Sin contextos en memoria."
        lines = ["Top contextos por tasa de éxito:"]
        for t in tops:
            lines.append(f"  {t['context_key']:40s}: {t['success_rate']:.0%}  ({t['correct']}/{t['total']})")
        return "\n".join(lines)

_memory = ContextualMemory()

def save_context_memory(context_key: str, outcome: str, features: Optional[Dict] = None, score: float = 0.0) -> int:
    return _memory.save(MemoryEntry(context_key=context_key, outcome=outcome, features=features or {}, score=score))

def get_context_success_rate(context_key: str) -> float:
    return _memory.success_rate(context_key)

def cmd_contextual_memory() -> str:
    return f"\n{'═'*56}\n  ASTRA — Memoria Contextual\n{'═'*56}\n{_memory.summary_text()}\n{'═'*56}"

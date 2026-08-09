"""
feedback/feedback_collector.py — ASTRA Phase 6.1
Recibe votos del usuario sobre predicciones y las persiste en SQLite.
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
class FeedbackEntry:
    target_id: str
    target_type: str
    vote: int
    comment: str
    context: Dict[str, Any]
    timestamp: str = ""
    entry_id: Optional[int] = None
    def __post_init__(self):
        if not self.timestamp: self.timestamp = datetime.now().isoformat()
        self.vote = max(-1, min(1, int(self.vote)))

class FeedbackCollector:
    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path
        self._init_db()
    def _conn(self): return sqlite3.connect(self.db_path)
    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS feedback_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT, target_id TEXT NOT NULL,
                target_type TEXT NOT NULL, vote INTEGER NOT NULL,
                comment TEXT, context TEXT, timestamp TEXT NOT NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fb_target ON feedback_entries(target_id)")
            conn.commit()
    def submit(self, entry: FeedbackEntry) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO feedback_entries (target_id,target_type,vote,comment,context,timestamp) VALUES (?,?,?,?,?,?)",
                (entry.target_id, entry.target_type, entry.vote, entry.comment, json.dumps(entry.context, ensure_ascii=False), entry.timestamp))
            conn.commit()
            eid = cur.lastrowid
        log_evolution("feedback_received","FeedbackCollector",f"Vote {entry.vote:+d} on {entry.target_type}:{entry.target_id}",
            {"vote": entry.vote, "target_type": entry.target_type, "target_id": entry.target_id})
        return eid
    def get_for_target(self, target_id: str) -> List[FeedbackEntry]:
        with self._conn() as conn:
            rows = conn.execute("SELECT id,target_id,target_type,vote,comment,context,timestamp FROM feedback_entries WHERE target_id=? ORDER BY id DESC", (target_id,)).fetchall()
        return [FeedbackEntry(entry_id=r[0],target_id=r[1],target_type=r[2],vote=r[3],comment=r[4] or "",context=json.loads(r[5] or "{}"),timestamp=r[6]) for r in rows]
    def get_recent(self, limit: int = 20) -> List[FeedbackEntry]:
        with self._conn() as conn:
            rows = conn.execute("SELECT id,target_id,target_type,vote,comment,context,timestamp FROM feedback_entries ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [FeedbackEntry(entry_id=r[0],target_id=r[1],target_type=r[2],vote=r[3],comment=r[4] or "",context=json.loads(r[5] or "{}"),timestamp=r[6]) for r in rows]
    def score_for(self, target_id: str) -> float:
        entries = self.get_for_target(target_id)
        if not entries: return 0.0
        return sum(e.vote for e in entries) / len(entries)
    def summary_by_type(self) -> Dict[str, Dict]:
        with self._conn() as conn:
            rows = conn.execute("""SELECT target_type, COUNT(*) as total, AVG(vote) as avg_vote,
                SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN vote=-1 THEN 1 ELSE 0 END) as negative
                FROM feedback_entries GROUP BY target_type""").fetchall()
        return {r[0]: {"total":r[1],"avg_vote":round(r[2],3),"positive":r[3],"negative":r[4],"approval_rate":round(r[3]/max(1,r[1]),3)} for r in rows}

_collector = FeedbackCollector()

def collect_feedback(target_id: str, vote: int, target_type: str = "signal", comment: str = "", context: Optional[Dict] = None) -> int:
    return _collector.submit(FeedbackEntry(target_id=target_id,target_type=target_type,vote=vote,comment=comment,context=context or {}))

def cmd_feedback_votar(target_id: str, vote_str: str, comment: str = "") -> str:
    try: vote = int(vote_str)
    except ValueError: return "Voto debe ser 1 (correcto) o -1 (incorrecto)"
    eid = collect_feedback(target_id, vote, comment=comment)
    return f"Feedback registrado (id={eid}): {'Correcto' if vote > 0 else 'Incorrecto'} para '{target_id}'"

def cmd_feedback_ver(target_id: str) -> str:
    entries = _collector.get_for_target(target_id)
    if not entries: return f"Sin feedback registrado para '{target_id}'"
    lines = [f"Feedback para '{target_id}' ({len(entries)} entradas):"]
    for e in entries:
        sym = "+" if e.vote > 0 else ("-" if e.vote < 0 else "=")
        lines.append(f"  [{e.timestamp[:19]}] {sym}1  {e.comment or '(sin comentario)'}")
    lines.append(f"\nPuntuación neta: {_collector.score_for(target_id):+.2f}")
    return "\n".join(lines)

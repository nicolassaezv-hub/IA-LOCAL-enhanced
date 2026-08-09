"""
constitution/audit_log.py — ASTRA Phase 8.5
Registro inmutable (append-only) de todas las decisiones del sistema.
"""
from __future__ import annotations
import json, sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

# BUGFIX: ruta relativa a cwd (mismo patron de bug que en Fase 6/7) —
# se importa la MISMA ruta absoluta que usa memory.py.
from memory import DB_PATH as _DB_PATH

@dataclass
class AuditEntry:
    action: str; actor: str; target: str; outcome: str; details: Dict[str, Any]
    timestamp: str = ""; entry_id: Optional[int] = None
    def __post_init__(self):
        if not self.timestamp: self.timestamp = datetime.now().isoformat()
    def summary(self) -> str:
        return f"[{self.timestamp[:19]}] [{self.outcome.upper()}] {self.action} on {self.target} by {self.actor}"

class AuditLog:
    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path; self._init_db()
    def _conn(self): return sqlite3.connect(self.db_path)
    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
                actor TEXT NOT NULL, target TEXT NOT NULL, outcome TEXT NOT NULL,
                details TEXT, timestamp TEXT NOT NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_outcome ON audit_log(outcome)")
            conn.commit()
    def log(self, entry: AuditEntry) -> int:
        with self._conn() as conn:
            cur = conn.execute("INSERT INTO audit_log (action,actor,target,outcome,details,timestamp) VALUES (?,?,?,?,?,?)",
                (entry.action, entry.actor, entry.target, entry.outcome, json.dumps(entry.details, ensure_ascii=False), entry.timestamp))
            conn.commit(); return cur.lastrowid
    def get_trail(self, target: Optional[str] = None, limit: int = 50) -> List[AuditEntry]:
        with self._conn() as conn:
            if target:
                rows = conn.execute("SELECT id,action,actor,target,outcome,details,timestamp FROM audit_log WHERE target=? ORDER BY id DESC LIMIT ?", (target, limit)).fetchall()
            else:
                rows = conn.execute("SELECT id,action,actor,target,outcome,details,timestamp FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [AuditEntry(entry_id=r[0],action=r[1],actor=r[2],target=r[3],outcome=r[4],details=json.loads(r[5] or "{}"),timestamp=r[6]) for r in rows]
    def stats(self) -> Dict[str, int]:
        with self._conn() as conn:
            rows = conn.execute("SELECT outcome, COUNT(*) FROM audit_log GROUP BY outcome").fetchall()
        return {r[0]: r[1] for r in rows}
    def render(self, limit: int = 20) -> str:
        entries = self.get_trail(limit=limit)
        if not entries: return "Audit log vacío."
        lines = [f"{'═'*64}", "  ASTRA — Audit Log", f"{'═'*64}"]
        for e in entries: lines.append(f"  {e.summary()}")
        stats = self.stats(); total = sum(stats.values())
        lines += [f"{'─'*64}", f"  Total: {total}  |  " + "  |  ".join(f"{k}: {v}" for k,v in sorted(stats.items())), f"{'═'*64}"]
        return "\n".join(lines)

_audit = AuditLog()

def log_audit(action: str, actor: str, target: str, outcome: str, details: Optional[Dict] = None) -> int:
    return _audit.log(AuditEntry(action=action, actor=actor, target=target, outcome=outcome, details=details or {}))

def get_audit_trail(target: Optional[str] = None, limit: int = 50) -> List[AuditEntry]:
    return _audit.get_trail(target, limit)

def cmd_audit_log(limit: int = 20) -> str:
    return _audit.render(limit)

"""
evolution/proposal_store.py — ASTRA Phase 7.4
Persiste y gestiona propuestas de evolución en SQLite.
Status: pending | approved | applied | rejected | rolled_back
"""
from __future__ import annotations
import json, sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from feedback.evolution_memory import log_evolution

# BUGFIX: ruta relativa a cwd causaba que este módulo escribiera en un
# memoria.db distinto al usado por memory.py si el proceso corría desde
# otro directorio. Se importa la MISMA ruta absoluta que usa memory.py.
from memory import DB_PATH as _DB_PATH

@dataclass
class Proposal:
    proposal_type: str; component: str; description: str; rationale: str
    payload: Dict[str, Any]; priority: int; status: str = "pending"
    created_at: str = ""; applied_at: str = ""; result: str = ""
    proposal_id: Optional[int] = None
    def __post_init__(self):
        if not self.created_at: self.created_at = datetime.now().isoformat()
        self.priority = max(1, min(3, self.priority))
        if self.status not in ("pending","approved","applied","rejected","rolled_back"): self.status = "pending"
    def summary(self) -> str:
        pri_label = {1:"ALTA",2:"MEDIA",3:"BAJA"}.get(self.priority, "?")
        return (f"[#{self.proposal_id or '?'}] [{self.status.upper()}] [{pri_label}] {self.proposal_type} → {self.component}\n"
                f"  {self.description}\n  Razón: {self.rationale}")

class ProposalStore:
    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path; self._init_db()
    def _conn(self): return sqlite3.connect(self.db_path)
    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS evolution_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, proposal_type TEXT NOT NULL,
                component TEXT NOT NULL, description TEXT NOT NULL, rationale TEXT,
                payload TEXT, priority INTEGER DEFAULT 2, status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL, applied_at TEXT, result TEXT)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prop_status ON evolution_proposals(status)")
            conn.commit()
    def save(self, proposal: Proposal) -> int:
        with self._conn() as conn:
            cur = conn.execute("""INSERT INTO evolution_proposals (proposal_type,component,description,rationale,payload,priority,status,created_at) VALUES (?,?,?,?,?,?,?,?)""",
                (proposal.proposal_type, proposal.component, proposal.description, proposal.rationale,
                 json.dumps(proposal.payload, ensure_ascii=False), proposal.priority, proposal.status, proposal.created_at))
            conn.commit(); pid = cur.lastrowid
        log_evolution("proposal_created","ProposalStore",f"New {proposal.proposal_type} proposal for {proposal.component}",{"proposal_id": pid,"priority": proposal.priority})
        return pid
    def get(self, proposal_id: int) -> Optional[Proposal]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM evolution_proposals WHERE id=?", (proposal_id,)).fetchone()
        return _row_to_proposal(row) if row else None
    def get_pending(self, priority: Optional[int] = None) -> List[Proposal]:
        with self._conn() as conn:
            if priority:
                rows = conn.execute("SELECT * FROM evolution_proposals WHERE status='pending' AND priority=? ORDER BY priority, created_at", (priority,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM evolution_proposals WHERE status='pending' ORDER BY priority, created_at").fetchall()
        return [_row_to_proposal(r) for r in rows]
    def get_all(self, status: Optional[str] = None, limit: int = 50) -> List[Proposal]:
        with self._conn() as conn:
            if status:
                rows = conn.execute("SELECT * FROM evolution_proposals WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM evolution_proposals ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [_row_to_proposal(r) for r in rows]
    def update_status(self, proposal_id: int, status: str, result: str = "") -> bool:
        applied_at = datetime.now().isoformat() if status == "applied" else None
        with self._conn() as conn:
            if applied_at:
                conn.execute("UPDATE evolution_proposals SET status=?, result=?, applied_at=? WHERE id=?", (status, result, applied_at, proposal_id))
            else:
                conn.execute("UPDATE evolution_proposals SET status=?, result=? WHERE id=?", (status, result, proposal_id))
            conn.commit()
        log_evolution("proposal_status_changed","ProposalStore",f"Proposal #{proposal_id} → {status}",{"proposal_id": proposal_id,"status": status})
        return True
    def stats(self) -> Dict[str, int]:
        with self._conn() as conn:
            rows = conn.execute("SELECT status, COUNT(*) FROM evolution_proposals GROUP BY status").fetchall()
        return {r[0]: r[1] for r in rows}
    def summary_text(self) -> str:
        stats = self.stats(); total = sum(stats.values())
        if total == 0: return "Sin propuestas de evolución."
        lines = [f"Total propuestas: {total}"]
        for st, count in sorted(stats.items()):
            lines.append(f"  {st:15s}: {count}")
        pending = self.get_pending()
        if pending:
            lines.append(f"\nPendientes ({len(pending)}):")
            for p in pending[:5]:
                lines.append(f"  [{p.priority}] {p.proposal_type:20s} → {p.component}: {p.description[:60]}")
        return "\n".join(lines)

def _row_to_proposal(r) -> Proposal:
    return Proposal(proposal_id=r[0],proposal_type=r[1],component=r[2],description=r[3],rationale=r[4] or "",
        payload=json.loads(r[5] or "{}"),priority=r[6],status=r[7],created_at=r[8],applied_at=r[9] or "",result=r[10] or "")

_store = ProposalStore()

def save_proposal(proposal: Proposal) -> int: return _store.save(proposal)
def get_proposals(status: Optional[str] = None, limit: int = 50) -> List[Proposal]: return _store.get_all(status, limit)

def cmd_proposals_ver(status: Optional[str] = None) -> str:
    proposals = get_proposals(status, 20)
    if not proposals: return f"Sin propuestas{' con status ' + status if status else ''}."
    lines = [f"{'═'*64}", "  ASTRA — Propuestas de Evolución", f"{'═'*64}"]
    for p in proposals: lines.append(p.summary()); lines.append("")
    lines.append(f"{'═'*64}")
    return "\n".join(lines)

def cmd_aprobar_propuesta(proposal_id_str: str) -> str:
    """Aprueba una propuesta pendiente para que luego pueda aplicarse con 'propuesta aplicar'."""
    try: pid = int(proposal_id_str)
    except ValueError: return "ID debe ser número entero"
    proposal = _store.get(pid)
    if not proposal: return f"Propuesta #{pid} no encontrada"
    if proposal.status != "pending": return f"Propuesta #{pid} no está pendiente (status={proposal.status})"
    _store.update_status(pid, "approved")
    return f"Propuesta #{pid} aprobada. Ejecuta 'propuesta aplicar {pid}' para aplicarla."

def cmd_rechazar_propuesta(proposal_id_str: str) -> str:
    """Rechaza una propuesta pendiente."""
    try: pid = int(proposal_id_str)
    except ValueError: return "ID debe ser número entero"
    proposal = _store.get(pid)
    if not proposal: return f"Propuesta #{pid} no encontrada"
    if proposal.status != "pending": return f"Propuesta #{pid} no está pendiente (status={proposal.status})"
    _store.update_status(pid, "rejected")
    return f"Propuesta #{pid} rechazada."

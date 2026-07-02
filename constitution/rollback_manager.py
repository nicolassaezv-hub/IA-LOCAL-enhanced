"""
constitution/rollback_manager.py — ASTRA Phase 8.3
Gestiona rollback points para deshacer cambios aplicados.
"""
from __future__ import annotations
import json, sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from .audit_log import log_audit

# BUGFIX: ruta relativa a cwd (mismo patron de bug que en Fase 6/7) —
# se importa la MISMA ruta absoluta que usa memory.py.
from memory import DB_PATH as _DB_PATH

@dataclass
class RollbackPoint:
    component: str; snapshot: Dict[str, Any]; description: str
    proposal_id: Optional[int] = None; created_at: str = ""; point_id: Optional[int] = None
    def __post_init__(self):
        if not self.created_at: self.created_at = datetime.now().isoformat()
    def summary(self) -> str:
        return f"[#{self.point_id or '?'}] {self.component} @ {self.created_at[:19]}\n  {self.description}"

class RollbackManager:
    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path; self._init_db()
    def _conn(self): return sqlite3.connect(self.db_path)
    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS rollback_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT, component TEXT NOT NULL,
                snapshot TEXT NOT NULL, description TEXT, proposal_id INTEGER, created_at TEXT NOT NULL)""")
            conn.commit()
    def create(self, component: str, description: str, proposal_id: Optional[int] = None) -> RollbackPoint:
        snapshot = self._capture_snapshot(component)
        point = RollbackPoint(component=component, snapshot=snapshot, description=description, proposal_id=proposal_id)
        with self._conn() as conn:
            cur = conn.execute("INSERT INTO rollback_points (component,snapshot,description,proposal_id,created_at) VALUES (?,?,?,?,?)",
                (component, json.dumps(snapshot, ensure_ascii=False), description, proposal_id, point.created_at))
            conn.commit(); point.point_id = cur.lastrowid
        log_audit("rollback_point_created","system",component,"applied",{"point_id":point.point_id,"description":description})
        return point
    def rollback(self, point_id: int) -> str:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM rollback_points WHERE id=?", (point_id,)).fetchone()
        if not row: return f"Rollback point #{point_id} no encontrado"
        point = RollbackPoint(point_id=row[0],component=row[1],snapshot=json.loads(row[2]),description=row[3] or "",proposal_id=row[4],created_at=row[5])
        result = self._apply_snapshot(point)
        log_audit("rollback_applied","user",point.component,"rolled_back",{"point_id":point_id,"result":result})
        return result
    def get_recent(self, component: Optional[str] = None, limit: int = 10) -> List[RollbackPoint]:
        with self._conn() as conn:
            if component:
                rows = conn.execute("SELECT * FROM rollback_points WHERE component=? ORDER BY id DESC LIMIT ?", (component, limit)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM rollback_points ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [RollbackPoint(point_id=r[0],component=r[1],snapshot=json.loads(r[2]),description=r[3] or "",proposal_id=r[4],created_at=r[5]) for r in rows]
    def _capture_snapshot(self, component: str) -> Dict[str, Any]:
        # BUGFIX: el borrador comparaba component == "adaptive_thresholds" (string literal
        # que NUNCA ocurre en la práctica — las propuestas reales usan el nombre del PAR,
        # ej. component="EURUSD"), por lo que el rollback jamás capturaba los umbrales
        # reales y caía siempre al snapshot generico ("requiere revisión manual").
        # Ahora se captura el estado de umbrales del PAR especifico (component=pair),
        # que es como evolution_proposal.py arma sus propuestas de threshold_adjust.
        try:
            from feedback.adaptive_thresholds import _thresholds
            return {"pair": component, "thresholds": _thresholds.get(component)}
        except Exception:
            return {"component": component, "captured_at": datetime.now().isoformat()}
    def _apply_snapshot(self, point: RollbackPoint) -> str:
        snapshot = point.snapshot
        if snapshot and "thresholds" in snapshot:
            try:
                from feedback.adaptive_thresholds import _thresholds
                th = snapshot["thresholds"]
                pair = snapshot.get("pair", point.component)
                _thresholds.update(pair, th.get("confidence", 0.65), th.get("adx", 22.0), f"rollback to #{point.point_id}")
                return f"Umbrales de {pair} restaurados: confidence={th.get('confidence'):.4f}, adx={th.get('adx'):.1f}"
            except Exception as e:
                return f"Error: {e}"
        # Compat con snapshots antiguos guardados como {pair: {confidence,adx}, ...}
        if snapshot and all(isinstance(v, dict) and "confidence" in v for v in snapshot.values()):
            try:
                from feedback.adaptive_thresholds import _thresholds
                for pair, data in snapshot.items():
                    _thresholds.update(pair, data.get("confidence", 0.65), data.get("adx", 22.0), f"rollback to #{point.point_id}")
                return f"Umbrales restaurados para {len(snapshot)} pares"
            except Exception as e:
                return f"Error: {e}"
        return f"Rollback de '{point.component}' requiere revisión manual. Snapshot ID #{point.point_id}."
    def summary_text(self) -> str:
        points = self.get_recent(limit=10)
        if not points: return "Sin rollback points registrados."
        lines = ["Últimos rollback points:"]
        for p in points: lines.append(f"  {p.summary()}")
        return "\n".join(lines)

_rollback = RollbackManager()

def create_rollback_point(component: str, description: str, proposal_id: Optional[int] = None) -> RollbackPoint:
    return _rollback.create(component, description, proposal_id)

def rollback_to(point_id: int) -> str: return _rollback.rollback(point_id)

def cmd_rollback_ver() -> str:
    return f"\n{'═'*56}\n  ASTRA — Rollback Points\n{'═'*56}\n{_rollback.summary_text()}\n{'═'*56}"

def cmd_rollback_aplicar(point_id_str: str) -> str:
    try: pid = int(point_id_str)
    except ValueError: return "ID debe ser número entero"
    return rollback_to(pid)

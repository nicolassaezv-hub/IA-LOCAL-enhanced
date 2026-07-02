"""
evolution/performance_monitor.py — ASTRA Phase 7.1
Mide el rendimiento continuo del sistema tomando snapshots.
"""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from feedback.evolution_memory import log_evolution

_DB_PATH = "memoria.db"

@dataclass
class PerformanceSnapshot:
    timestamp: str; total_signals: int; signal_accuracy: float
    feedback_approval: float; models_trained: int; active_pairs: int
    avg_confidence: float; avg_adx: float; evolution_events: int
    snapshot_id: Optional[int] = None; meta: Dict[str, Any] = field(default_factory=dict)
    def summary(self) -> str:
        return (f"[{self.timestamp[:19]}] Señales: {self.total_signals}  |  "
                f"Aprobación: {self.feedback_approval:.1%}  |  Modelos: {self.models_trained}  |  "
                f"Pares: {self.active_pairs}  |  Conf: {self.avg_confidence:.3f}  |  "
                f"Eventos evol.: {self.evolution_events}")

class PerformanceMonitor:
    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path; self._init_db()
    def _conn(self): return sqlite3.connect(self.db_path)
    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS performance_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
                total_signals INTEGER DEFAULT 0, signal_accuracy REAL DEFAULT 0,
                feedback_approval REAL DEFAULT 0, models_trained INTEGER DEFAULT 0,
                active_pairs INTEGER DEFAULT 0, avg_confidence REAL DEFAULT 0,
                avg_adx REAL DEFAULT 0, evolution_events INTEGER DEFAULT 0)""")
            conn.commit()
    def snapshot(self) -> PerformanceSnapshot:
        ts = datetime.now().isoformat()
        data = self._collect_metrics()
        with self._conn() as conn:
            cur = conn.execute("""INSERT INTO performance_snapshots
                (timestamp,total_signals,signal_accuracy,feedback_approval,models_trained,active_pairs,avg_confidence,avg_adx,evolution_events)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (ts,data["total_signals"],data["signal_accuracy"],data["feedback_approval"],
                 data["models_trained"],data["active_pairs"],data["avg_confidence"],data["avg_adx"],data["evolution_events"]))
            conn.commit(); sid = cur.lastrowid
        snap = PerformanceSnapshot(timestamp=ts, snapshot_id=sid, **data)
        log_evolution("performance_snapshot","PerformanceMonitor",f"Snapshot taken: approval={data['feedback_approval']:.2f}",data)
        return snap
    def _collect_metrics(self) -> Dict[str, Any]:
        result = {"total_signals":0,"signal_accuracy":0.0,"feedback_approval":0.0,"models_trained":0,"active_pairs":0,"avg_confidence":0.0,"avg_adx":0.0,"evolution_events":0}
        with self._conn() as conn:
            try:
                row = conn.execute("SELECT COUNT(*) FROM forex_signals").fetchone()
                if row: result["total_signals"] = row[0]
                row = conn.execute("SELECT AVG(confidence), AVG(adx) FROM forex_signals").fetchone()
                if row and row[0]: result["avg_confidence"] = round(row[0], 4); result["avg_adx"] = round(row[1] or 0, 2)
                row = conn.execute("SELECT COUNT(DISTINCT pair) FROM forex_signals").fetchone()
                if row: result["active_pairs"] = row[0]
            except Exception: pass
            try:
                row = conn.execute("SELECT COUNT(*), AVG(CASE WHEN vote=1 THEN 1.0 ELSE 0.0 END) FROM feedback_entries").fetchone()
                if row and row[0]: result["feedback_approval"] = round(row[1] or 0, 4)
            except Exception: pass
            try:
                row = conn.execute("SELECT COUNT(*) FROM models").fetchone()
                if row: result["models_trained"] = row[0]
            except Exception: pass
            try:
                row = conn.execute("SELECT COUNT(*) FROM evolution_events").fetchone()
                if row: result["evolution_events"] = row[0]
            except Exception: pass
        return result
    def get_history(self, limit: int = 20) -> List[PerformanceSnapshot]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM performance_snapshots ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [PerformanceSnapshot(snapshot_id=r[0],timestamp=r[1],total_signals=r[2],signal_accuracy=r[3],feedback_approval=r[4],models_trained=r[5],active_pairs=r[6],avg_confidence=r[7],avg_adx=r[8],evolution_events=r[9]) for r in rows]
    def trend(self, metric: str = "feedback_approval", n: int = 10) -> str:
        history = self.get_history(n)
        if len(history) < 2: return "stable"
        values = [getattr(s, metric, 0) for s in reversed(history)]
        slope = (values[-1] - values[0]) / max(1, len(values))
        if slope > 0.02: return "improving"
        if slope < -0.02: return "degrading"
        return "stable"
    def summary_text(self) -> str:
        history = self.get_history(5)
        if not history: return "Sin snapshots. Ejecuta 'monitor snapshot' primero."
        lines = ["Últimos snapshots de rendimiento:"]
        for s in reversed(history): lines.append(f"  {s.summary()}")
        lines.append(f"\nTendencia general: {self.trend()}")
        return "\n".join(lines)

_monitor = PerformanceMonitor()

def take_snapshot() -> PerformanceSnapshot: return _monitor.snapshot()

def cmd_monitor_snapshot() -> str:
    snap = take_snapshot()
    return f"\n{'═'*60}\n  ASTRA — Snapshot de Rendimiento\n{'═'*60}\n{snap.summary()}\n{'═'*60}"

def cmd_monitor_historial(n: int = 10) -> str:
    return _monitor.summary_text()

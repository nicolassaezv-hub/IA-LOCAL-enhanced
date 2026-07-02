"""
feedback/adaptive_thresholds.py — ASTRA Phase 6.3
Ajusta dinámicamente umbrales de confianza y ADX basado en feedback.
"""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from .evolution_memory import log_evolution

_DB_PATH = "memoria.db"
_MIN_CONFIDENCE = 0.55; _MAX_CONFIDENCE = 0.85
_MIN_ADX = 18.0; _MAX_ADX = 35.0
_LEARNING_RATE = 0.02; _MIN_SAMPLES = 10

@dataclass
class ThresholdUpdate:
    pair: str; old_confidence: float; new_confidence: float
    old_adx: float; new_adx: float; reason: str; timestamp: str = ""
    def __post_init__(self):
        if not self.timestamp: self.timestamp = datetime.now().isoformat()
    def summary(self) -> str:
        dc = self.new_confidence - self.old_confidence
        da = self.new_adx - self.old_adx
        return (f"Par {self.pair}: confidence {self.old_confidence:.3f} → {self.new_confidence:.3f} ({dc:+.3f})  |  "
                f"ADX {self.old_adx:.1f} → {self.new_adx:.1f} ({da:+.1f})\nRazón: {self.reason}")

class AdaptiveThresholds:
    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path; self._init_db()
    def _conn(self): return sqlite3.connect(self.db_path)
    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS adaptive_thresholds (
                pair TEXT PRIMARY KEY, confidence REAL NOT NULL DEFAULT 0.65,
                adx REAL NOT NULL DEFAULT 22.0, n_updates INTEGER DEFAULT 0, updated_at TEXT)""")
            conn.commit()
    def get(self, pair: str) -> Dict[str, float]:
        with self._conn() as conn:
            row = conn.execute("SELECT confidence, adx FROM adaptive_thresholds WHERE pair=?", (pair,)).fetchone()
        if row: return {"confidence": row[0], "adx": row[1]}
        return {"confidence": 0.65, "adx": 22.0}
    def get_all(self) -> Dict[str, Dict[str, float]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT pair, confidence, adx, n_updates FROM adaptive_thresholds").fetchall()
        return {r[0]: {"confidence": r[1], "adx": r[2], "n_updates": r[3]} for r in rows}
    def update(self, pair: str, confidence: float, adx: float, reason: str = "") -> ThresholdUpdate:
        current = self.get(pair)
        old_conf, old_adx = current["confidence"], current["adx"]
        new_conf = round(max(_MIN_CONFIDENCE, min(_MAX_CONFIDENCE, confidence)), 4)
        new_adx = round(max(_MIN_ADX, min(_MAX_ADX, adx)), 2)
        with self._conn() as conn:
            conn.execute("""INSERT INTO adaptive_thresholds (pair, confidence, adx, n_updates, updated_at) VALUES (?,?,?,1,?)
                ON CONFLICT(pair) DO UPDATE SET confidence=excluded.confidence, adx=excluded.adx,
                n_updates=n_updates+1, updated_at=excluded.updated_at""",
                (pair, new_conf, new_adx, datetime.now().isoformat()))
            conn.commit()
        update = ThresholdUpdate(pair=pair, old_confidence=old_conf, new_confidence=new_conf, old_adx=old_adx, new_adx=new_adx, reason=reason)
        log_evolution("threshold_update","AdaptiveThresholds",f"Updated thresholds for {pair}",
            {"pair": pair,"old_conf": old_conf,"new_conf": new_conf,"old_adx": old_adx,"new_adx": new_adx})
        return update
    def adapt_from_feedback(self, pair: str, feedback_scores: List[int]) -> Optional[ThresholdUpdate]:
        if len(feedback_scores) < _MIN_SAMPLES: return None
        approval = sum(1 for v in feedback_scores if v > 0) / len(feedback_scores)
        current = self.get(pair)
        conf, adx = current["confidence"], current["adx"]
        reason_parts = []
        if approval < 0.40:
            conf = min(_MAX_CONFIDENCE, conf + _LEARNING_RATE * 1.5)
            adx = min(_MAX_ADX, adx + 1.0)
            reason_parts.append(f"baja aprobación ({approval:.0%}) → umbrales más altos")
        elif approval > 0.75:
            conf = max(_MIN_CONFIDENCE, conf - _LEARNING_RATE * 0.5)
            reason_parts.append(f"alta aprobación ({approval:.0%}) → umbral reducido levemente")
        else:
            return None
        return self.update(pair, conf, adx, "; ".join(reason_parts))

_thresholds = AdaptiveThresholds()

def update_thresholds(pair: str, confidence: float, adx: float, reason: str = "") -> ThresholdUpdate:
    return _thresholds.update(pair, confidence, adx, reason)

def get_thresholds(pair: str) -> Dict[str, float]:
    return _thresholds.get(pair)

def adapt_thresholds_from_feedback(pair: str, feedback_scores: List[int]) -> Optional[ThresholdUpdate]:
    return _thresholds.adapt_from_feedback(pair, feedback_scores)

def cmd_thresholds_ver() -> str:
    all_t = _thresholds.get_all()
    if not all_t: return "Sin umbrales personalizados. Usando defaults (confidence=0.65, ADX=22.0)"
    lines = [f"{'═'*60}","  ASTRA — Umbrales Adaptativos",f"{'═'*60}",f"  {'Par':<12} {'Confianza':>10} {'ADX':>8} {'Ajustes':>10}",f"  {'─'*12} {'─'*10} {'─'*8} {'─'*10}"]
    for pair, d in sorted(all_t.items()):
        lines.append(f"  {pair:<12} {d['confidence']:>10.4f} {d['adx']:>8.1f} {d.get('n_updates',0):>10}")
    lines.append(f"{'═'*60}")
    return "\n".join(lines)

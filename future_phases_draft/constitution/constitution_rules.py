"""
constitution/constitution_rules.py — ASTRA Phase 8.2
Catálogo de reglas constitucionales inmutables.
"""
from __future__ import annotations
import json, sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from .audit_log import log_audit

_DB_PATH = "memoria.db"

@dataclass
class Rule:
    rule_id: str; name: str; description: str; rule_type: str
    constraint: Dict[str, Any]; is_builtin: bool = True; enabled: bool = True
    created_at: str = ""; db_id: Optional[int] = None
    def __post_init__(self):
        if not self.created_at: self.created_at = datetime.now().isoformat()
    def summary(self) -> str:
        sym = "BUILTIN" if self.is_builtin else "CUSTOM"
        status = "ON" if self.enabled else "OFF"
        return f"[{sym}][{status}] {self.rule_id}: {self.name}\n  Tipo: {self.rule_type}  |  Constraint: {self.constraint}\n  {self.description}"

BUILTIN_RULES = [
    Rule("max_risk_per_trade","Riesgo máximo por operación","Ninguna señal puede implicar más del 2% del balance","hard_limit",{"field":"risk_pct","max_value":0.02}),
    Rule("min_confidence_threshold","Confianza mínima","El sistema nunca puede emitir señal con confianza < 55%","hard_limit",{"field":"confidence","min_value":0.55}),
    Rule("min_adx_threshold","ADX mínimo","No emitir señales en mercados ranging (ADX < 18)","hard_limit",{"field":"adx","min_value":18.0}),
    Rule("wfv_required_for_deploy","WFV obligatorio","Ningún modelo puede desplegarse sin Walk-Forward Validation","process",{"requirement":"wfv_passed","min_avg_precision":0.65}),
    Rule("max_daily_drawdown","Drawdown diario máximo","No operar si drawdown diario > 3%","hard_limit",{"field":"daily_drawdown_pct","max_value":0.03}),
    Rule("proposal_requires_approval","Propuestas requieren aprobación","retrain/strategy_change requieren aprobación explícita","process",{"proposal_types":["retrain","strategy_change"],"require_approval":True}),
    Rule("no_auto_rollback_beyond_3","Máximo 3 rollbacks consecutivos","Si hay 3 rollbacks seguidos → modo seguro","soft_limit",{"max_consecutive_rollbacks":3}),
]

class ConstitutionRules:
    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path; self._init_db(); self._seed_builtins()
    def _conn(self): return sqlite3.connect(self.db_path)
    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS constitution_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT, rule_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL, description TEXT, rule_type TEXT NOT NULL,
                constraint_ TEXT, is_builtin INTEGER DEFAULT 1, enabled INTEGER DEFAULT 1, created_at TEXT NOT NULL)""")
            conn.commit()
    def _seed_builtins(self):
        with self._conn() as conn:
            for rule in BUILTIN_RULES:
                conn.execute("""INSERT OR IGNORE INTO constitution_rules (rule_id,name,description,rule_type,constraint_,is_builtin,enabled,created_at)
                    VALUES (?,?,?,?,?,?,?,?)""", (rule.rule_id,rule.name,rule.description,rule.rule_type,json.dumps(rule.constraint),int(rule.is_builtin),int(rule.enabled),rule.created_at))
            conn.commit()
    def get_all(self, enabled_only: bool = True) -> List[Rule]:
        with self._conn() as conn:
            if enabled_only:
                rows = conn.execute("SELECT * FROM constitution_rules WHERE enabled=1 ORDER BY is_builtin DESC, id").fetchall()
            else:
                rows = conn.execute("SELECT * FROM constitution_rules ORDER BY is_builtin DESC, id").fetchall()
        return [Rule(db_id=r[0],rule_id=r[1],name=r[2],description=r[3] or "",rule_type=r[4],constraint=json.loads(r[5] or "{}"),is_builtin=bool(r[6]),enabled=bool(r[7]),created_at=r[8]) for r in rows]
    def get(self, rule_id: str) -> Optional[Rule]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM constitution_rules WHERE rule_id=?", (rule_id,)).fetchone()
        if not row: return None
        return Rule(db_id=row[0],rule_id=row[1],name=row[2],description=row[3] or "",rule_type=row[4],constraint=json.loads(row[5] or "{}"),is_builtin=bool(row[6]),enabled=bool(row[7]),created_at=row[8])
    def add_custom(self, rule: Rule) -> int:
        rule.is_builtin = False
        with self._conn() as conn:
            cur = conn.execute("""INSERT INTO constitution_rules (rule_id,name,description,rule_type,constraint_,is_builtin,enabled,created_at) VALUES (?,?,?,?,?,?,?,?)""",
                (rule.rule_id,rule.name,rule.description,rule.rule_type,json.dumps(rule.constraint),0,1,rule.created_at))
            conn.commit()
        log_audit("add_rule","user",rule.rule_id,"applied",{"name":rule.name})
        return cur.lastrowid
    def render(self) -> str:
        rules = self.get_all(enabled_only=False)
        lines = [f"{'═'*60}","  ASTRA — Reglas Constitucionales",f"{'═'*60}"]
        for r in rules: lines.append(r.summary()); lines.append("")
        lines += [f"Total: {len(rules)} reglas", f"{'═'*60}"]
        return "\n".join(lines)

_rules = ConstitutionRules()

def get_rules(enabled_only: bool = True) -> List[Rule]: return _rules.get_all(enabled_only)
def add_rule(rule_id, name, description, rule_type, constraint) -> int:
    return _rules.add_custom(Rule(rule_id=rule_id,name=name,description=description,rule_type=rule_type,constraint=constraint,is_builtin=False))
def cmd_reglas_ver() -> str: return _rules.render()

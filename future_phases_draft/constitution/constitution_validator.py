"""
constitution/constitution_validator.py — ASTRA Phase 8.1
Valida propuestas de evolución contra reglas constitucionales.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from evolution.proposal_store import Proposal
from .constitution_rules import ConstitutionRules, Rule, _rules as _global_rules
from .audit_log import log_audit

@dataclass
class ValidationDecision:
    is_valid: bool; proposal_id: Optional[int]
    violations: List[str]; warnings: List[str]; checked_rules: List[str]
    def summary(self) -> str:
        status = "VALIDA" if self.is_valid else "BLOQUEADA"
        lines = [f"Propuesta #{self.proposal_id}: {status}"]
        if self.violations: lines += ["  Violaciones:"] + [f"    ! {v}" for v in self.violations]
        if self.warnings: lines += ["  Advertencias:"] + [f"    * {w}" for w in self.warnings]
        lines.append(f"  Reglas verificadas: {', '.join(self.checked_rules)}")
        return "\n".join(lines)

class ConstitutionValidator:
    def __init__(self, rules: ConstitutionRules = _global_rules):
        self.rules = rules
    def validate(self, proposal: Proposal) -> ValidationDecision:
        active_rules = self.rules.get_all(enabled_only=True)
        violations, warnings, checked = [], [], []
        for rule in active_rules:
            checked.append(rule.rule_id)
            v, w = self._check_rule(rule, proposal)
            violations.extend(v); warnings.extend(w)
        is_valid = len(violations) == 0
        decision = ValidationDecision(is_valid=is_valid, proposal_id=proposal.proposal_id,
            violations=violations, warnings=warnings, checked_rules=checked)
        log_audit("validate_proposal","ConstitutionValidator",f"proposal#{proposal.proposal_id or '?'}",
            "approved" if is_valid else "blocked",{"violations":violations,"proposal_type":proposal.proposal_type})
        return decision
    def _check_rule(self, rule: Rule, proposal: Proposal):
        violations, warnings = [], []
        constraint = rule.constraint; payload = proposal.payload
        if rule.rule_id == "proposal_requires_approval":
            if proposal.proposal_type in constraint.get("proposal_types",[]) and proposal.status == "applied":
                violations.append(f"Tipo '{proposal.proposal_type}' requiere aprobación explícita")
        elif rule.rule_id == "min_confidence_threshold":
            if "new_confidence" in payload and payload["new_confidence"] < constraint.get("min_value",0.55):
                violations.append(f"Confianza propuesta ({payload['new_confidence']:.3f}) < mínimo ({constraint['min_value']})")
        elif rule.rule_id == "min_adx_threshold":
            if "new_adx" in payload and payload["new_adx"] < constraint.get("min_value",18.0):
                violations.append(f"ADX propuesto ({payload['new_adx']:.1f}) < mínimo ({constraint['min_value']})")
        elif rule.rule_id == "wfv_required_for_deploy":
            if proposal.proposal_type == "retrain":
                if payload.get("wfv_passed") is False:
                    violations.append("El modelo no pasó WFV — no puede desplegarse")
                elif payload.get("avg_precision") is not None and payload["avg_precision"] < constraint.get("min_avg_precision",0.65):
                    violations.append(f"Precisión WFV ({payload['avg_precision']:.3f}) < mínimo")
                elif payload.get("wfv_passed") is None and payload.get("avg_precision") is None:
                    warnings.append("Sin métricas WFV en payload — verifica antes de aplicar")
        return violations, warnings

_validator = ConstitutionValidator()

def validate_proposal(proposal: Proposal) -> ValidationDecision: return _validator.validate(proposal)

def cmd_validar_propuesta(proposal_id_str: str) -> str:
    try: pid = int(proposal_id_str)
    except ValueError: return "ID debe ser número entero"
    try:
        from evolution.proposal_store import _store
        proposal = _store.get(pid)
        if not proposal: return f"Propuesta #{pid} no encontrada"
        decision = validate_proposal(proposal)
        return f"\n{'═'*56}\n  ASTRA — Validación Constitucional\n{'═'*56}\n{decision.summary()}\n{'═'*56}"
    except Exception as e: return f"Error: {e}"

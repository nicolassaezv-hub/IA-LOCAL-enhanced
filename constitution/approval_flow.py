"""
constitution/approval_flow.py — ASTRA Phase 8.4
Flujo de aprobación de propuestas de evolución.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from evolution.proposal_store import Proposal, ProposalStore, _store
from .constitution_validator import ConstitutionValidator, ValidationDecision, _validator
from .rollback_manager import RollbackManager, _rollback
from .audit_log import log_audit

@dataclass
class ApprovalRequest:
    proposal_id: int; requester: str; justification: str; timestamp: str = ""
    def __post_init__(self):
        if not self.timestamp: self.timestamp = datetime.now().isoformat()

class ApprovalFlow:
    def __init__(self, store=_store, validator=_validator, rollback_mgr=_rollback):
        self.store = store; self.validator = validator; self.rollback_mgr = rollback_mgr
    def submit(self, request: ApprovalRequest) -> str:
        proposal = self.store.get(request.proposal_id)
        if not proposal: return f"Propuesta #{request.proposal_id} no encontrada"
        if proposal.status != "pending": return f"Propuesta #{request.proposal_id} ya tiene status '{proposal.status}'"
        decision = self.validator.validate(proposal)
        if not decision.is_valid:
            self.store.update_status(request.proposal_id,"rejected","Bloqueada: " + "; ".join(decision.violations))
            log_audit("approval_rejected",request.requester,f"proposal#{request.proposal_id}","rejected",{"violations":decision.violations})
            return f"Propuesta #{request.proposal_id} RECHAZADA:\n" + "\n".join(f"  - {v}" for v in decision.violations)
        rp = self.rollback_mgr.create(proposal.component, f"Pre-approval snapshot for proposal #{request.proposal_id}", proposal_id=request.proposal_id)
        self.store.update_status(request.proposal_id,"approved",f"Aprobada por {request.requester}. Rollback #{rp.point_id}.")
        log_audit("approval_granted",request.requester,f"proposal#{request.proposal_id}","approved",{"rollback_point":rp.point_id})
        result = f"Propuesta #{request.proposal_id} APROBADA. Rollback point: #{rp.point_id}"
        if decision.warnings: result += "\nAdvertencias:\n" + "\n".join(f"  * {w}" for w in decision.warnings)
        return result
    def manual_approve(self, proposal_id: int, justification: str = "manual") -> str:
        proposal = self.store.get(proposal_id)
        if not proposal: return f"Propuesta #{proposal_id} no encontrada"
        rp = self.rollback_mgr.create(proposal.component, f"Manual approval for #{proposal_id}", proposal_id=proposal_id)
        self.store.update_status(proposal_id,"approved",f"Aprobación manual: {justification}. Rollback #{rp.point_id}.")
        log_audit("manual_approval","user",f"proposal#{proposal_id}","approved",{"justification":justification,"rollback_point":rp.point_id})
        return f"Propuesta #{proposal_id} aprobada manualmente. Rollback: #{rp.point_id}"
    def reject(self, proposal_id: int, reason: str = "user rejected") -> str:
        proposal = self.store.get(proposal_id)
        if not proposal: return f"Propuesta #{proposal_id} no encontrada"
        self.store.update_status(proposal_id,"rejected",reason)
        log_audit("manual_rejection","user",f"proposal#{proposal_id}","rejected",{"reason":reason})
        return f"Propuesta #{proposal_id} rechazada: {reason}"
    def apply_approved(self, proposal_id: int) -> str:
        proposal = self.store.get(proposal_id)
        if not proposal: return f"Propuesta #{proposal_id} no encontrada"
        if proposal.status != "approved": return f"No está aprobada (status={proposal.status})"
        try:
            from evolution.evolution_proposal import _proposer
            result = _proposer.apply(proposal_id)
            status = "applied" if "error" not in result.lower() else "rejected"
            self.store.update_status(proposal_id, status, result)
            log_audit("proposal_applied","system",f"proposal#{proposal_id}",status,{"result":result[:200]})
            return result
        except Exception as e:
            err = f"Error aplicando #{proposal_id}: {e}"
            self.store.update_status(proposal_id,"rejected",err)
            return err

_flow = ApprovalFlow()

def submit_for_approval(proposal_id: int, requester: str = "system", justification: str = "") -> str:
    return _flow.submit(ApprovalRequest(proposal_id=proposal_id, requester=requester, justification=justification))

def approve(proposal_id: int, justification: str = "manual") -> str:
    return _flow.manual_approve(proposal_id, justification)

def reject(proposal_id: int, reason: str = "user rejected") -> str:
    return _flow.reject(proposal_id, reason)

def cmd_aprobar_propuesta(proposal_id_str: str, justification: str = "") -> str:
    try: pid = int(proposal_id_str)
    except ValueError: return "ID debe ser número entero"
    return approve(pid, justification or "manual approval via CLI")

def cmd_rechazar_propuesta(proposal_id_str: str, reason: str = "") -> str:
    try: pid = int(proposal_id_str)
    except ValueError: return "ID debe ser número entero"
    return reject(pid, reason or "rejected via CLI")
